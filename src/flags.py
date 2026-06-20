# -*- coding: utf-8 -*-
"""
flags.py — crowding / late-entry (spec §12) and popular-but-not-cheap (spec §13).
"""


def crowding_flag(rec, cfg):
    cr = cfg.get("crowding", {}) or {}
    oyr = rec.get("one_year_return")
    pbh = rec.get("pct_below_52w_high")
    crowded = (
        oyr is not None and pbh is not None
        and oyr > cr.get("one_year_return_hot", 1.50)
        and pbh < cr.get("pct_below_52w_high_near", 0.10)
    )
    rec["crowded_late"] = bool(crowded)
    if crowded:
        rec.setdefault("_flag_notes", []).append(
            f"CROWDED / LATE — up {oyr:+.0%} in 1y and only {pbh:.0%} below its 52-week high; "
            "the move may already be priced in."
        )
    return rec


def popular_not_cheap_flag(rec, cfg):
    cr = cfg.get("crowding", {}) or {}
    floor = cr.get("popular_not_cheap_fund_floor", 55)
    conf = rec.get("independent_confirmations", 0) or 0
    fund = rec.get("fundamental_score") or 0
    pnc = conf >= 1 and fund < floor
    rec["popular_not_cheap"] = bool(pnc)
    if pnc:
        rec.setdefault("_flag_notes", []).append(
            f"POPULAR, NOT CHEAP — {conf} independent confirmation group(s) like it, "
            f"but the fundamental score ({fund:.0f}) is below {floor}; likely a late entry, watch only."
        )
    return rec


def hype_penalty(rec, cfg):
    """Penalise extreme run-ups unless fundamentals strongly justify (spec §3)."""
    cr = cfg.get("crowding", {}) or {}
    oyr = rec.get("one_year_return")
    if oyr is None or oyr <= cr.get("hype_one_year_return", 2.0):
        return 0.0
    fund = rec.get("fundamental_score") or 0
    # strong fundamentals (≥75) soften the penalty; weak ones get hit hard
    base = min(15.0, (oyr - cr.get("hype_one_year_return", 2.0)) * 10.0)
    relief = max(0.0, (fund - 75) / 25.0)        # 0..1 as fund goes 75..100
    pen = base * (1.0 - 0.7 * relief)
    if pen > 0:
        rec.setdefault("_flag_notes", []).append(
            f"hype penalty −{pen:.1f} (up {oyr:+.0%} in 1y; fundamentals only partly justify it)"
        )
    return round(pen, 1)
