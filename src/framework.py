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


def trade_plan(buy_price, current_price, pb, conviction, lifecycle, fundamental=None, stop_override=None):
    """The exact numbers: where to take profit, a DATA-DRIVEN stop, where to add — and the
    RATIONAL sell verdict. Key rules:
      * profit targets are FORWARD from the current price (a name already up 700% shouldn't
        show a target below its price);
      * the stop is per-stock from history (stop_override) when available, with the
        −40%-from-cost danger line as the hard backstop;
      * don't dump a strong name on a temporary dip — only suggest exiting when the DATA
        says the thesis is structurally broken."""
    c = conviction or 0
    declining = (c < 5) or (lifecycle == "Falling Conviction") \
        or (lifecycle == "Fallen Angel" and (fundamental if fundamental is not None else 100) < 45)
    strong = (c >= 6) and not declining
    u1, u2 = _LADDER.get(pb, _LADDER["growth"])
    p = {"playbook": pb, "declining": declining, "strong": strong,
         "harvest": "احصد عند الهدف: الأكبر من 10% من الربح أو 1% من المركز."}

    base = current_price or buy_price
    if base and base > 0:
        # forward harvest targets — where to trim as it RISES from here
        p["profit1"] = {"pct": u1, "price": round(base * (1 + u1), 2)}
        p["profit2"] = {"pct": u2, "price": round(base * (1 + u2), 2)}
    if buy_price and current_price:
        p["gain_from_cost"] = round(current_price / buy_price - 1.0, 4)

    # STOP: data-driven (per-stock history) when available; else flat −40% backstop
    if stop_override and stop_override.get("price"):
        p["stop"] = stop_override
    elif buy_price and buy_price > 0:
        p["stop"] = {"price": round(buy_price * 0.60, 2), "basis": "−40% من كلفتك (احتياطي)", "kind": "flat"}
    elif current_price and current_price > 0:
        p["stop"] = {"price": round(current_price * 0.75, 2), "basis": "−25% احتياطي (عبّي كلفتك)", "kind": "flat"}

    if current_price and current_price > 0:
        p["accumulate"] = {"price": round(current_price * 0.90, 2)}   # ~−10% from here

    stop_px = (p.get("stop") or {}).get("price")
    if declining:
        p["sell_advice"] = ("⚠️ البيانات تدل على ضعف هيكلي (قناعة منخفضة/متراجعة) — فكّر بالخروج"
                            + (f"؛ ضع وقف بيع (stop) عند ~{stop_px}." if stop_px else "."))
        p["sell_kind"] = "exit"
    elif strong:
        p["sell_advice"] = ("الشركة قوية — لا تبيع على هبوط مؤقت."
                            + (f" لو كسر ~{stop_px} (وهو بعيد عن ضجيجه) راجع الأطروحة؛ وإلا فالهبوط فرصة تجميع." if stop_px else ""))
        p["sell_kind"] = "hold"
    else:
        p["sell_advice"] = "احتفظ حسب خطتك؛ راجع الأطروحة لو تدهورت الأساسيات."
        p["sell_kind"] = "watch"
    return p
