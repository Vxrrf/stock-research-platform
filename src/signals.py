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
