# -*- coding: utf-8 -*-
"""
framework.py — the owner's personal trading framework, encoded.

Three playbooks (each with its own alert ladder):
  GROWTH      (NVDA-style)            → upside alerts +50% / +100%
  GOLD/CYCLICAL (AEM; halal: RMAU)    → upside alerts +50% / +80%
  TRADING     (short-term, tighter)   → upside alerts +25% / +50%

Universal rules:
  Red Danger: −40% from average cost → thesis review (exit if it turns from a
              growth story into a survival story).
  Alerts per name: two upside + one downside (the −40% review).
  Harvest: when an upside alert hits, take the GREATER of 10% of profit or 1%
           of the total position.

These are RESEARCH guardrails, not buy/sell signals. The platform never says
"BUY NOW" — it surfaces your own pre-set levels so you act with discipline.
"""

PLAYBOOK_AR = {"growth": "📈 نمو", "gold_cyclical": "🥇 ذهب/دوري", "trading": "⚡ تداول"}

_LADDER = {
    "growth": (0.50, 1.00),
    "gold_cyclical": (0.50, 0.80),
    "trading": (0.25, 0.50),
}
DANGER_DRAWDOWN = -0.40        # −40% from average cost → thesis review


def playbook(rec):
    """Classify a name into one of the three playbooks from what we already know."""
    if rec.get("cyclical"):
        return "gold_cyclical"
    hm = rec.get("suggested_hold_months")
    if isinstance(hm, (int, float)) and hm <= 6:
        return "trading"
    return "growth"


def alert_plan(buy_price, pb):
    """Two upside alert prices + one downside (the −40% danger). Needs a buy price."""
    if not buy_price or buy_price <= 0:
        return None
    u1, u2 = _LADDER.get(pb, _LADDER["growth"])
    return {
        "playbook": pb,
        "up1_pct": u1, "up1_price": round(buy_price * (1 + u1), 2),
        "up2_pct": u2, "up2_price": round(buy_price * (1 + u2), 2),
        "danger_pct": DANGER_DRAWDOWN, "danger_price": round(buy_price * (1 + DANGER_DRAWDOWN), 2),
        "harvest": "احصد عند الهدف: الأكبر من 10% من الربح أو 1% من المركز.",
    }


def annotate(rec):
    """Attach the playbook to a scored record (used on opportunities + holdings)."""
    rec["playbook"] = playbook(rec)
    return rec
