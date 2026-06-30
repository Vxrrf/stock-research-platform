# -*- coding: utf-8 -*-
"""
news.py — Smart News & Macro Impact (spec §9).

Two layers:
  1) Macro events from data/news_events.yaml (you maintain these). Each event
     has impact_score 1-10, direction, affected_sectors, time_horizon, and
     feeds market_risk_today and a small sector sentiment tilt.
  2) Per-stock headline sentiment (best-effort, free) from yfinance .news for a
     FOCUSED set, as a tiny keyword-based score.

For investors, news moves the total score only lightly — capped by
config.news.max_weight_pct (default 5%). The per-record `_news_sentiment`
(-1..1) is produced here; main.py converts it to the capped point adjustment.

Also computes market_risk_today: Low / Medium / High / Extreme.
"""

import os
import re
import yaml

from config_loader import ROOT

# MERGED: company-specific (earnings/contracts/approvals) + macro/price-action keywords — one list,
# no silent override (a 2nd definition used to clobber the 1st and lose half the signal).
_POS = ("beat", "beats", "upgrade", "raises", "raised", "record", "wins", "win", "contract",
        "surge", "surges", "expansion", "expands", "outperform", "strong demand", "all-time high",
        "approval", "launch", "partnership", "rise", "jump", "soar", "rally", "gain", "strong",
        "boost", "high", "top", "robust")
_NEG = ("miss", "misses", "downgrade", "cut", "cuts", "lawsuit", "probe", "investigation", "recall",
        "plunge", "plunges", "layoff", "layoffs", "guidance cut", "fraud", "warning", "halts",
        "delay", "delays", "subpoena", "decline", "weak demand", "bankruptcy", "fall", "drop",
        "slump", "crash", "war", "sink", "tumble", "weak", "fear", "loss", "sell-off", "slip",
        "warn", "recession", "default")

# WHOLE-WORD matchers — plain substring matching wrongly flags 'war' inside forward/toward/award,
# 'cut' inside executive/circuit, 'high' inside highlight, 'win' inside winter, etc. Count standalone only.
_POS_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in _POS) + r")\b")
_NEG_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in _NEG) + r")\b")


# keep general headlines only if they're market-relevant (incl. market-moving geopolitics);
# drops pure lifestyle/sports/crime so 'today' stays about the market, not random world news.
_MKT = ("stock", "shares", "market", "earnings", "fed", "rate", "nasdaq", "dow", "s&p", "ipo",
        "dividend", "tariff", "oil", "inflation", "gdp", "yield", "bond", "chip", "semiconductor",
        "revenue", "profit", "guidance", "analyst", "buyback", "merger", "acquisition", "sec ",
        "fund", "trade", "sanction", "war", "crude", "opec", "bank", "economy", "jobs", "cpi",
        "nvidia", "broadcom", "apple", "tesla", "microsoft", "amazon", "ai ", "gold", "etf",
        "wall street", "stocks", "shares", "investor", "rally", "selloff", "treasury", "powell")


def _direction(head):
    hl = head.lower()
    pos = len(_POS_RE.findall(hl))
    neg = len(_NEG_RE.findall(hl))
    return "positive" if pos > neg else ("negative" if neg > pos else "neutral")


# ── Arabic market news (Investing.com Arabic RSS — native عربي، متعلّق بالسوق، يصل من السحابة) ──
_AR_POS = ("صعود", "ارتفاع", "يرتفع", "مكاسب", "قفز", "يقفز", "قوي", "قوية", "تفوز", "فوز", "اتفاقية",
           "نمو", "صفقة", "ربح", "أرباح", "تعافي", "يصعد", "إيجاب", "رابح", "يربح", "تتفوّق", "تتجاوز")
_AR_NEG = ("هبوط", "تراجع", "يتراجع", "ضغوط", "تحذير", "خسائر", "خسارة", "ينخفض", "انخفاض", "سلبي",
           "سلبية", "أدنى", "يهبط", "ركود", "مخاوف", "قلق", "تخفيض", "يخفّض", "صدمة", "أزمة", "ضعف")


def _ar_direction(t):
    pos = sum(w in t for w in _AR_POS)
    neg = sum(w in t for w in _AR_NEG)
    return "positive" if pos > neg else ("negative" if neg > pos else "neutral")


def _ar_ago(pubdate):
    """«منذ ساعة / منذ يومين» من pubDate الـRSS — إحساس Investing.com. الصيغة: «2026-06-29 13:51:38»."""
    import datetime as _dt
    pubdate = (pubdate or "").strip()
    if not pubdate:
        return ""
    dt = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = _dt.datetime.strptime(pubdate[:19], fmt)
            break
        except Exception:
            pass
    if dt is None:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pubdate).replace(tzinfo=None)
        except Exception:
            return ""
    try:
        secs = (_dt.datetime.utcnow() - dt).total_seconds()
        if secs < 0:
            secs = 0
        if secs < 3600:
            return "منذ %d د" % max(1, int(secs // 60))
        if secs < 86400:
            return "منذ %d س" % int(secs // 3600)
        return "منذ %d يوم" % int(secs // 86400)
    except Exception:
        return ""


def _fetch_arabic_news(limit=14, timeout=12):
    """عناوين عربية متعلّقة بالسوق من Investing.com (curl أساساً — يصل من CI، requests احتياطاً)."""
    import re
    urls = ["https://sa.investing.com/rss/news_25.rss", "https://sa.investing.com/rss/news.rss"]
    out, seen = [], set()
    skip = {"كافة الأخبار", "أخبار أسواق الأسهم", "الأكثر شعبية"}
    for url in urls:
        text = None
        try:
            import subprocess
            r = subprocess.run(["curl", "-sS", "--max-time", str(timeout), "-A", "Mozilla/5.0", url],
                               capture_output=True, text=True, timeout=timeout + 5)
            if r.returncode == 0 and r.stdout.strip():
                text = r.stdout
        except Exception:
            text = None
        if not text:
            try:
                import requests
                text = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout).text
            except Exception:
                continue
        for it in re.findall(r"<item>(.*?)</item>", text, re.S):
            tm = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
            dm = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
            if not tm:
                continue
            import html as _html
            title = _html.unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
            if not title or title in skip or title.lower() in seen:
                continue
            seen.add(title.lower())
            out.append({"event_name": title, "date": _ar_ago(dm.group(1) if dm else ""),
                        "impact_direction": _ar_direction(title), "source": "Investing.com"})
            if len(out) >= limit:
                return out
    return out


def _fmt_date(dt):
    import datetime as _dt
    try:
        return _dt.datetime.utcfromtimestamp(int(dt)).strftime("%Y-%m-%d") if dt else ""
    except Exception:
        return ""


def live_news(cfg, focus_tickers=None, limit=14):
    """LIVE, MARKET-FOCUSED news — LEADS with native Arabic market headlines (Investing.com RSS,
    like the user expects), then the user's own holdings' news from Finnhub. Auto-updating + cloud-
    reachable (curl). Falls back gracefully; [] only if everything fails → caller uses the yaml."""
    import sources
    import datetime as _dt
    out, seen = [], set()

    # 0) LEAD with native ARABIC market news (gold/Fed/dollar/stocks — like Investing.com)
    try:
        for n in _fetch_arabic_news(limit=limit):
            k = (n.get("event_name") or "").lower()
            if k and k not in seen:
                seen.add(k)
                out.append(n)
    except Exception as e:
        print(f"  arabic news skipped: {e}")

    # 1) the user's holdings' news from Finnhub (holdings-specific; English, tagged by ticker)
    fh = sources.FinnhubClient(cfg)
    if fh.enabled:
        today = _dt.date.today()
        frm = (today - _dt.timedelta(days=6)).isoformat()
        for t in (focus_tickers or [])[:8]:
            for n in (fh.company_news(t, frm, today.isoformat()) or [])[:2]:
                head = (n.get("headline") or "").strip()
                if not head or head.lower() in seen:
                    continue
                seen.add(head.lower())
                out.append({"event_name": "[%s] %s" % (t, head), "date": _fmt_date(n.get("datetime")),
                            "impact_direction": _direction(head), "source": n.get("source", "")})
                if len(out) >= limit + 8:
                    break
    return out[:limit + 8]


def _load_events():
    p = os.path.join(ROOT, "data", "news_events.yaml")
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("events", []) or []
    except Exception:
        return []


def _headline_sentiment(rec):
    """yfinance .news keyword sentiment in [-1, 1]; None if no news."""
    try:
        import yfinance as yf
        items = yf.Ticker(rec["ticker"]).news or []
    except Exception:
        return None
    if not items:
        return None
    pos = neg = 0
    for it in items[:12]:
        title = ""
        if isinstance(it, dict):
            title = (it.get("title") or it.get("content", {}).get("title", "") if isinstance(it.get("content"), dict) else it.get("title", "")) or ""
        title = str(title).lower()
        pos += len(_POS_RE.findall(title))
        neg += len(_NEG_RE.findall(title))
    if pos + neg == 0:
        return 0.0
    return round((pos - neg) / (pos + neg), 3)


def _sector_tilt(events):
    """Aggregate macro events into a per-sector sentiment tilt in [-1,1]."""
    tilt = {}
    for e in events:
        secs = e.get("affected_sectors", [])
        if secs == "all" or secs == ["all"]:
            secs = ["__all__"]
        if isinstance(secs, str):
            secs = [secs]
        direction = {"positive": 1, "negative": -1, "neutral": 0}.get(e.get("impact_direction", "neutral"), 0)
        mag = (e.get("impact_score", 0) or 0) / 10.0
        for s in secs:
            key = str(s).lower()
            tilt[key] = tilt.get(key, 0.0) + direction * mag
    # clamp
    for k in tilt:
        tilt[k] = max(-1.0, min(1.0, tilt[k]))
    return tilt


def market_risk_today(events):
    """Low / Medium / High / Extreme from aggregate negative macro pressure."""
    neg = 0.0
    for e in events:
        if e.get("impact_direction") == "negative":
            neg += (e.get("impact_score", 0) or 0)
    if neg >= 24:
        return "Extreme"
    if neg >= 14:
        return "High"
    if neg >= 6:
        return "Medium"
    return "Low"


def build(focused_records, all_records, cfg, headlines=True):
    """
    Sets rec['_news_sentiment'] for focused records (sector tilt + headlines).
    Returns (event_rows for news_impact.csv, market_risk_today).
    `headlines=False` skips the slow per-ticker yfinance .news fetch (fast update);
    macro events + market_risk (from the yaml) still compute instantly.
    """
    events = _load_events()
    tilt = _sector_tilt(events)
    allt = tilt.get("__all__", 0.0)

    for rec in focused_records:
        sector = str(rec.get("sector") or "").lower()
        themes = [str(t).lower() for t in (rec.get("themes") or [])]
        sec_tilt = allt + tilt.get(sector, 0.0) + sum(tilt.get(t, 0.0) for t in themes)
        sec_tilt = max(-1.0, min(1.0, sec_tilt))
        hl = _headline_sentiment(rec) if headlines else None
        if hl is None:
            sent = sec_tilt
        else:
            sent = 0.5 * sec_tilt + 0.5 * hl
        rec["_news_sentiment"] = round(max(-1.0, min(1.0, sent)), 3)

    rows = []
    for e in events:
        secs = e.get("affected_sectors", "")
        rows.append({
            "event_name": e.get("event_name"),
            "date": e.get("date"),
            "affected_sectors": ", ".join(secs) if isinstance(secs, list) else secs,
            "impact_score": e.get("impact_score"),
            "impact_direction": e.get("impact_direction"),
            "time_horizon": e.get("time_horizon"),
            "source": e.get("source"),
            "notes": e.get("notes"),
        })
    return rows, market_risk_today(events)
