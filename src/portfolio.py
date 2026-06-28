# -*- coding: utf-8 -*-
"""
portfolio.py — portfolio builder (spec §16) + rebalancing rules (spec §17).

Default model for a 25-year-old, high-risk, growth-focused investor who still
wants crisis protection (editable in config.yaml portfolio.allocation):
  55% growth stocks · 20% broad-market ETF · 10% semi/AI ETF
  5% healthcare/defensive ETF · 5% gold ETF · 5% cash

Rebalancing (every ~3 months): flag any single stock > 15%, any position down
25% from buy price. No automatic selling. Down + improving fundamentals =>
"Accumulation Candidate"; down + worsening => "Danger".
"""

import os
import csv

from config_loader import ROOT


def _fwd_tilt(r):
    """Forward-outlook tilt for portfolio sorting — ONLY when confidence is HIGH/MED, so a
    LOW/empty outlook can never jump the queue. Portfolio leans toward who's trending up."""
    return (r.get("forward_outlook_score") or 0) if r.get("forward_outlook_confidence") in ("HIGH", "MED") else 0


def _bucket(records, engine, cap, cfg):
    """Members of an engine, halal not-fail, investable (data/gates ok), sorted by conviction
    then forward tilt then total. NOTE: halal 'unknown' is KEPT (verify-first, not exclude)."""
    mode = ((cfg.get("halal", {}) or {}).get("mode") or "gate").lower()
    out = [r for r in records
           if engine in (r.get("engines") or []) and r.get("investable", True)
           and (mode == "info" or r.get("halal_status") != "fail")]   # info: rank by quality, verify halal yourself
    out.sort(key=lambda r: (r.get("conviction_score") or 0, _fwd_tilt(r), r.get("total_score") or 0), reverse=True)
    return out[:cap]


def _gold_picks(candidates, cfg, n=2):
    """Best gold / precious-metals names from the scan — so the hedge bucket auto-picks
    the strongest gold play (replacing AEM if something scores better), not a hardcoded one."""
    mode = ((cfg.get("halal", {}) or {}).get("mode") or "gate").lower()
    out = []
    for r in candidates:
        ind = (r.get("industry") or "").lower()
        # gold/silver/precious ONLY — the hedge bucket must stay a true gold play, not a
        # copper/lithium miner that happens to out-score (if none qualify, _gold_row → RMAU).
        is_gold = "gold" in ind or "silver" in ind or "precious" in ind
        if is_gold and r.get("investable", True) and (mode == "info" or r.get("halal_status") != "fail"):
            out.append(r)
    out.sort(key=lambda r: (r.get("conviction_score") or 0, _fwd_tilt(r)), reverse=True)
    return out[:n]


def _spec_picks(candidates, cfg, n=3):
    """Speculation sleeve — hot, high-MOMENTUM, non-core punts (TTWO-style). Kept SMALL by
    design (high risk, exit fast). Ranked by 1-year momentum among names that are NOT steady
    compounders and NOT funds; data-artifact runs (>+350%/yr) excluded as suspect."""
    mode = ((cfg.get("halal", {}) or {}).get("mode") or "gate").lower()

    def ok(r):
        return (r.get("investable", True) and not r.get("is_fund") and not r.get("data_suspect")
                and (mode == "info" or r.get("halal_status") != "fail"))

    pool = [r for r in candidates if ok(r)
            and "compounder" not in (r.get("engines") or [])      # core quality belongs in نواة, not مضاربات
            and 0.4 <= (r.get("one_year_return") or 0) <= 3.5]    # hot (+40%↑) but not a split artifact
    pool.sort(key=lambda r: (r.get("one_year_return") or 0, _fwd_tilt(r)), reverse=True)
    return pool[:n]


def _gold_row(gold, total_pct):
    """Hedge sizing: best miner from the scan + RMAU (physical halal gold), deliberately
    balanced so the actual-gold ETF keeps real ballast and isn't swamped by the miner."""
    if not gold:
        return "RMAU %.0f%%" % (total_pct * 100)          # no miner found → all physical gold
    miner = gold[0].get("ticker")
    return "%s %.0f%% · RMAU %.0f%%" % (miner, total_pct * 0.55 * 100, total_pct * 0.45 * 100)


def _weighted(bucket, total_pct, cap, etfs=None):
    """Position sizing INSIDE a bucket: conviction-weighted, capped per name. Returns a
    readable 'TICKER X% · TICKER Y%' string so the user sees exactly how much to put."""
    items = list(bucket or [])
    syms = [(r.get("ticker"), max(0.1, (r.get("conviction_score") or 1))) for r in items]
    syms += [(e, 1.0) for e in (etfs or [])]            # ETFs get an equal base weight
    if not syms:
        return "—"
    target = int(round(total_pct * 100))                # bucket size, in whole percentage points
    s = sum(w for _, w in syms) or 1.0
    capv = int(cap * 100) if cap else target
    raw = [min(float(capv), target * w / s) for _, w in syms]   # ideal pp per name, capped
    pts = [int(v) for v in raw]                         # floors
    rema = [raw[i] - pts[i] for i in range(len(raw))]
    short = target - sum(pts)                           # largest-remainder: hand out leftover points
    order = sorted(range(len(raw)), key=lambda i: rema[i], reverse=True)
    k = 0
    while short > 0 and order:
        idx = order[k % len(order)]
        if pts[idx] < capv:                             # never push a name past its cap
            pts[idx] += 1
            short -= 1
        k += 1
        if k > 4 * len(order):
            break
    parts = ["%s %d%%" % (syms[i][0], pts[i]) for i in range(len(syms)) if pts[i] > 0]
    leftover = target - sum(pts)
    if leftover > 0 and parts:        # caps bound (too few names) — be honest about the remainder
        parts.append("غير موزّع %d%%" % leftover)
    return " · ".join(parts) if parts else "—"


def build_model(candidates, cfg):
    """Engine-based allocation with per-name sizing. Returns (rows, picks)."""
    p = cfg.get("portfolio", {}) or {}
    alloc = p.get("allocation", {}) or {}
    etfs = p.get("etf_suggestions", {}) or {}

    comp = _bucket(candidates, "compounder", p.get("max_compounders", 8), cfg)
    accel = _bucket(candidates, "accelerator", p.get("max_accelerators", 8), cfg)
    fut = _bucket(candidates, "future_leader", p.get("max_future_leaders", 10), cfg)
    gold = _gold_picks(candidates, cfg, n=1)       # data-driven best gold miner (replaces AEM if it out-scores)
    spec = _spec_picks(candidates, cfg)            # small high-risk speculation sleeve (TTWO-style)

    # de-duplicate across sleeves so each ticker is sized ONCE — a name strong in two lenses
    # is HELD once, not double-counted (priority: core > accelerator > future > speculation)
    _seen = set()

    def _dedup(lst):
        out = []
        for r in lst:
            t = r.get("ticker")
            if t in _seen:
                continue
            _seen.add(t)
            out.append(r)
        return out
    comp, accel, fut, spec = _dedup(comp), _dedup(accel), _dedup(fut), _dedup(spec)

    cap_c = p.get("max_single_compounder_pct", 0.12)
    cap_f = p.get("max_single_future_leader_pct", 0.03)

    rows = []
    a_comp, a_accel, a_fut = alloc.get("compounders", 0), alloc.get("accelerators", 0), alloc.get("future_leaders", 0)
    a_etf, a_gold = alloc.get("broad_market_etf", 0), alloc.get("gold_etf", 0)
    a_spec, a_cash = alloc.get("speculation", 0), alloc.get("cash", 0)
    specs = [
        ("🏛️ مُركِّبون (نواة)", _weighted(comp, a_comp, cap_c), a_comp,
         f"جودة تدوم — موزّعة بالقناعة، كل اسم ≤ {cap_c:.0%}"),
        ("🚀 مُسرِّعون (6–24ش)", _weighted(accel, a_accel, 0.10), a_accel, "نمو يتسارع — فرص متوسطة المدى"),
        ("🌱 قادة المستقبل", _weighted(fut, a_fut, cap_f), a_fut,
         f"رهانات صغيرة موزّعة (x3–x10) — كل اسم ≤ {cap_f:.0%} عشان -80% يبقى محتمَل"),
        ("🛡️ ETF حلال/واسع", _weighted([], a_etf, 0, etfs.get("broad_market_etf", [])), a_etf, "تحوّط واسع متوافق شرعياً"),
        ("🥇 ذهب (حماية)", _gold_row(gold, a_gold), a_gold,
         "أفضل سهم ذهب من الفحص + RMAU (ذهب حلال فعلي) — حماية وقت الأزمات"),
        ("⚡ مضاربات (صغيرة)", _weighted(spec, a_spec, max(0.02, a_spec / 2)), a_spec,
         "رهانات قصيرة المدى عالية المخاطرة (مثل TTWO) — وزن صغير بقصد، اخرج بسرعة"),
    ]
    # any non-cash sleeve with a target but NO qualifying names → roll it into cash (honest:
    # don't force a bad pick, and don't show an allocated-but-empty slice in the donut)
    rolled = 0.0
    for label, holdings, pct, note in specs:
        if pct > 0 and (not holdings or holdings == "—"):
            rolled += pct
            rows.append({"bucket": label, "allocation_pct": "0%",
                         "suggested_holdings": "—",
                         "notes": note + " · لا أسماء مؤهّلة هذا الفحص — ضُمّت للكاش"})
        else:
            rows.append({"bucket": label, "allocation_pct": f"{pct:.0%}",
                         "suggested_holdings": holdings, "notes": note})
    rows.append({"bucket": "💵 كاش (ذخيرة)", "allocation_pct": f"{a_cash + rolled:.0%}",
                 "suggested_holdings": "—",
                 "notes": "ذخيرة للتقلّب والشراء بالهبوط" + (" · يشمل خانات بلا أسماء" if rolled else "")})
    s = sum(alloc.values())
    if abs(s - 1.0) > 0.001:
        rows.append({"bucket": "⚠️ تحقّق", "allocation_pct": f"{s:.0%}",
                     "suggested_holdings": "—",
                     "notes": "المجموع لا يساوي 100% — عدّل config.yaml"})
    return rows, {"compounders": comp, "accelerators": accel, "future_leaders": fut,
                  "gold": gold, "speculation": spec}


def _read_holdings():
    """Optional data/holdings.csv: ticker, buy_price, weight (0..1 or %)."""
    p = os.path.join(ROOT, "data", "holdings.csv")
    if not os.path.exists(p):
        return []
    out = []
    try:
        with open(p, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                t = (row.get("ticker") or "").upper().strip()
                # skip comment lines (# ...) and obvious non-tickers (spaces / too long)
                if not t or t.startswith("#") or " " in t or len(t) > 6:
                    continue
                try:
                    out.append({
                        "ticker": t,
                        "buy_price": float(row.get("buy_price") or 0) or None,
                        "weight": float(row.get("weight") or 0) or None,
                        "buy_date": (row.get("buy_date") or "").strip() or None,
                    })
                except Exception:
                    continue
    except Exception:
        return []
    return [h for h in out if h["ticker"]]


def _role(rec):
    """The 'job' a stock does in the book — to compare like-for-like.
    Cyclicals are split by sector so gold compares with gold, memory with memory
    (Newmont is NOT a substitute for Micron even though both are cyclical)."""
    if rec.get("cyclical"):
        return "cyclical:" + str(rec.get("sector") or "other")
    eng = rec.get("engines") or []
    if "compounder" in eng:
        return "compounder"
    if "future_leader" in eng:
        return "future_leader"
    if "accelerator" in eng:
        return "accelerator"
    return rec.get("primary_theme") or (rec.get("sector") or "other")


def find_better(holding, records, cfg, margin=10.0):
    """Is there a clearly BETTER stock doing the same job? Only suggest when CONFIDENT:
    same role, halal not worse, investable, and rank_score higher by a clear margin."""
    role = _role(holding)
    hrank = holding.get("rank_score") or 0
    hconv = holding.get("conviction_score") or 0
    hsym = holding.get("ticker")
    halal_rank = {"pass": 2, "unknown": 1, "fail": 0}
    h_halal = halal_rank.get(holding.get("halal_status"), 1)
    best = None
    for r in records:
        if r.get("ticker") == hsym:
            continue
        if r.get("is_fund") or r.get("data_suspect"):
            continue                                   # never suggest a fund or bad-data name
        if _role(r) != role:
            continue
        if not r.get("investable", True) or r.get("halal_status") == "fail":
            continue
        if halal_rank.get(r.get("halal_status"), 1) < h_halal:
            continue                                   # don't downgrade halal
        if (r.get("rank_score") or 0) < hrank + margin:
            continue                                   # must be CLEARLY better
        if (r.get("conviction_score") or 0) <= hconv:
            continue
        if best is None or (r.get("rank_score") or 0) > (best.get("rank_score") or 0):
            best = r
    if not best:
        return None
    up = best.get("analyst_upside_percent")
    why = f"قناعة {best.get('conviction_score')}/10 مقابل {hconv}، ترتيب أعلى"
    if up is not None:
        why += f"، صعود متوقع {up:+.0%}"
    return {"ticker": best["ticker"], "name": best.get("name"), "role": role, "why": why}


def evaluate_holdings(records, cfg, deltas=None):
    """For each owned name (data/holdings.csv): recommend add / keep / review / exit
    based on conviction + lifecycle + drawdown. Research framing — never buy/sell now."""
    deltas = deltas or {}
    by = {r["ticker"]: r for r in records}
    rows = []
    for h in _read_holdings():
        r = by.get(h["ticker"])
        if not r:
            rows.append({"ticker": h["ticker"], "name": "—", "conviction": None, "rank": None,
                         "pnl": None, "halal": "—", "lifecycle": "—",
                         "verdict": "⚪ لا بيانات — حدّث", "why": "ما لقيت بيانات هالسهم هالتشغيل"})
            continue
        conv = r.get("conviction_score") or 0
        lc = r.get("lifecycle_status")
        hal = r.get("halal_status")
        # distinguish a BROKEN price (warn) from simply no buy_price entered (quiet —)
        from sanity import pnl_is_suspect
        has_both = bool(r.get("price")) and bool(h.get("buy_price"))
        pnl_suspect = has_both and pnl_is_suspect(r.get("price"), h.get("buy_price"), r.get("data_freshness_status"))
        pnl = (r["price"] / h["buy_price"] - 1) if (has_both and not pnl_suspect) else None
        # funds/ETFs (e.g. HLAL) are a core hold — never a SELL verdict, never a stock comparison
        if r.get("is_fund"):
            rows.append({"ticker": r["ticker"], "name": r.get("name"), "conviction": None,
                         "rank": r.get("rank_score"), "pnl": pnl, "halal": hal, "lifecycle": "Core",
                         "verdict": "🟦 صندوق أساسي — احتفظ", "why": "حيازة جوهرية (core)، ليست سهماً نقيّمه فردياً",
                         "hold_label": "طويل المدى (نواة)", "better": None,
                         "days_until_earnings": None, "pnl_suspect": pnl_suspect})
            continue
        if hal == "fail":
            verdict, why = "🔴 بيع — غير متوافق شرعياً", "فشل الفلتر الشرعي"
        elif conv >= 8:
            verdict, why = "🟢 احتفظ / زِد", f"قناعة عالية {conv}/10"
        elif pnl is not None and pnl <= cfg.get("portfolio", {}).get("drawdown_flag_pct", -0.25) and conv >= 6:
            # سهم قوي هبط = فرصة شراء، مو بيع (لا تبيع الجوهرة بالغلط)
            verdict, why = "🔵 فرصة تجميع (لا تبيع)", f"هبط {pnl:+.0%} لكن الأساسيات قوية (قناعة {conv}/10)"
        elif conv < 5 or (lc == "Falling Conviction") or (lc == "Fallen Angel" and (r.get("fundamental_score") or 0) < 45):
            # don't say 'sell' on a Fallen Angel that still has strong fundamentals (panic-sell guard)
            verdict, why = "🔴 بيع", f"قناعة ضعيفة/تنزل ({conv}/10){' · '+lc if lc else ''}"
        else:
            verdict, why = "⚪ احتفظ", f"قناعة {conv}/10، أداء مستقر"
        # specific holding-period COUNTDOWN: if we know buy_date, show months remaining
        hold_label = r.get("suggested_hold_label")
        target = r.get("suggested_hold_months")
        if h.get("buy_date") and target:
            from datetime import datetime
            try:
                bd = datetime.strptime(str(h["buy_date"])[:10], "%Y-%m-%d")
                held_m = max(0, round((datetime.now() - bd).days / 30.4))
                remaining = max(0, target - held_m)
                if remaining <= 0:
                    hold_label = f"وصل الهدف (~{target} شهر) — راجع الأطروحة"
                else:
                    hold_label = f"يتبقّى ~{remaining} شهر (مرّ {held_m} من ~{target})"
            except Exception:
                pass
        better = find_better(r, records, cfg)          # only set when CONFIDENT
        import framework
        import stops as _stops
        pb = framework.playbook(r)
        _sp = _stops.stop_for(r.get("stop_metrics"), h.get("buy_price"), r.get("price"))
        rows.append({"ticker": r["ticker"], "name": r.get("name"), "conviction": conv,
                     "rank": r.get("rank_score"), "pnl": pnl, "halal": hal,
                     "lifecycle": lc, "verdict": verdict, "why": why,
                     "hold_label": hold_label, "better": better,
                     "days_until_earnings": r.get("days_until_earnings"),
                     "pnl_suspect": pnl_suspect, "playbook": pb,
                     "alerts": framework.alert_plan(h.get("buy_price"), pb),
                     "trade": framework.trade_plan(h.get("buy_price"), r.get("price"), pb, conv,
                                                   lc, r.get("fundamental_score"), stop_override=_sp),
                     "current_price": r.get("price"), "buy_price": h.get("buy_price"),
                     "why_note": r.get("why_note"), "peers": r.get("peers")})
    # best overall first (by holistic rank), unknowns last
    rows.sort(key=lambda x: (x["rank"] is None, -(x["rank"] or 0)))
    return rows


def rebalance_flags(records, cfg, deltas=None):
    """Apply §17 rules to optional holdings. Returns list of flag dicts."""
    p = cfg.get("portfolio", {}) or {}
    max_single = p.get("max_single_stock_pct", 0.15)
    dd = p.get("drawdown_flag_pct", -0.25)
    deltas = deltas or {}
    by_t = {r["ticker"]: r for r in records}
    flags = []
    for h in _read_holdings():
        rec = by_t.get(h["ticker"], {})
        price = rec.get("price")
        w = h["weight"]
        if w is not None and w > 1:
            w = w / 100.0
        note = []
        if w is not None and w > max_single:
            note.append(f"position {w:.0%} > {max_single:.0%} cap — trim to rebalance (no forced sell)")
        pnl = None
        if price and h["buy_price"]:
            pnl = price / h["buy_price"] - 1.0
            if pnl <= dd:
                improving = (deltas.get(h["ticker"], 0) > 0) or ((rec.get("fundamental_score") or 0) >= 60)
                if improving:
                    note.append(f"down {pnl:+.0%} but fundamentals improving — Accumulation Candidate")
                else:
                    note.append(f"down {pnl:+.0%} and fundamentals worsening — Danger")
        if note:
            flags.append({
                "ticker": h["ticker"],
                "weight": f"{w:.0%}" if w is not None else "—",
                "pnl": f"{pnl:+.0%}" if pnl is not None else "—",
                "flags": " | ".join(note),
            })
    return flags
