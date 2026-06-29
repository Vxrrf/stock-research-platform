# -*- coding: utf-8 -*-
"""
signals.py — influencer/social signals layer (weak signal, FOR REVIEW only).

Reads data/social_signals.yaml (logged by Claude when you ask "شوف المؤثرين"),
and cross-checks each mentioned ticker against the platform's own evaluation so a
social mention NEVER becomes a pick without passing your plan + the dashboard.
"""

import os
import yaml

from config_loader import ROOT


def load():
    p = os.path.join(ROOT, "data", "social_signals.yaml")
    try:
        with open(p, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        return d.get("watched_accounts", []) or [], d.get("signals", []) or []
    except Exception:
        return [], []


def load_extras():
    """⭐ big_voices (الكبار) + consensus (تكرر عند المؤثرين) from the yaml."""
    p = os.path.join(ROOT, "data", "social_signals.yaml")
    try:
        with open(p, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        return d.get("big_voices", {}) or {}, d.get("consensus", []) or []
    except Exception:
        return {}, []


def consensus_board(records_by_ticker, cfg):
    """«⭐الكبار + تكرر عند المؤثرين» board: trusted big analysts + repeated tickers, each with
    OUR own verdict (conviction/halal/action). Star-tickers (shared by the big voices) sort on top."""
    big, cons = load_extras()
    stars = {str(t).upper() for t in (big.get("star_tickers") or [])}
    counts = {}
    for c in cons:
        t = str(c.get("ticker") or "").upper()
        if t:
            counts[t] = {"n": c.get("n", 0), "sentiment": c.get("sentiment", "bullish")}
    for t in stars:
        counts.setdefault(t, {"n": 0, "sentiment": "bullish"})
    rows = []
    for t, c in counts.items():
        rec = records_by_ticker.get(t, {})
        rows.append({
            "ticker": t, "n": c["n"], "sentiment": c["sentiment"], "star": t in stars,
            "conv": rec.get("conviction_score"), "halal": rec.get("halal_status"),
            "action": rec.get("action"), "in_platform": bool(rec),
        })
    # stars first, then by mention count, then by our conviction
    rows.sort(key=lambda r: (not r["star"], -(r["n"] or 0), -((r["conv"] or 0))))
    return {"analysts": big.get("analysts", []) or [], "rows": rows}


def rows(records_by_ticker, cfg):
    """Build review rows: each social signal + the platform's OWN verdict on that ticker."""
    accounts, sigs = load()
    out = []
    for s in sigs:
        tk = (s.get("ticker") or "").upper().strip()
        rec = records_by_ticker.get(tk, {})
        conv = rec.get("conviction_score")
        action = rec.get("action")
        halal = rec.get("halal_status")
        # does the platform agree it fits the plan?
        if not rec:
            fit = "❔ ما فُحص بعد — اضغط «حدّث الكل»"
        elif halal == "fail":
            fit = "🔴 لا — غير متوافق شرعياً"
        elif (conv or 0) >= 7 and action != "Avoid":
            fit = f"🟢 يتوافق (قناعة {conv}/10، {action})"
        elif (conv or 0) >= 5:
            fit = f"🟡 متوسط (قناعة {conv}/10) — ابحث أكثر"
        else:
            fit = f"⚪ ضعيف حسب منصّتنا (قناعة {conv})"
        out.append({
            "account": s.get("account"),
            "date": s.get("date"),
            "ticker": tk,
            "sentiment": s.get("sentiment", "—"),
            "note": s.get("note", ""),
            "source": s.get("source", ""),
            "platform_fit": fit,
        })
    out.sort(key=lambda r: r.get("date", ""), reverse=True)
    return accounts, out
