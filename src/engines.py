# -*- coding: utf-8 -*-
"""
engines.py — three discovery engines for hunting asymmetric winners.

  COMPOUNDER     : durable quality growers to hold for years.
  ACCELERATOR    : fundamentals inflecting up — 6–24 month outperformers.
  FUTURE LEADER  : sub-mega-cap emerging names with room to 3x–10x over years,
                   with discipline (real revenue/margins, not pre-revenue hype,
                   not already up >200%). This is the "find the next SNDK" engine.

A stock can belong to several. Each engine is a transparent rule set; the
future_leader_score (0–100) ranks within the emerging bucket.
"""


def _c01(x):
    if x is None:
        return 0.0
    return max(0.0, min(1.0, float(x)))


def is_compounder(rec, cfg):
    th = cfg.get("thresholds", {}) or {}
    cagr = rec.get("rev_cagr_3y")
    growth_ok = (cagr is not None and cagr >= th.get("rev_cagr_3y_good", 0.15)) or \
                (cagr is None and (rec.get("rev_growth") or 0) >= 0.15)
    roic, roe = rec.get("roic"), rec.get("roe")
    quality_ok = (roic is not None and roic >= th.get("roic_good", 0.12)) or \
                 (roe is not None and roe >= th.get("roe_good", 0.15))
    gm, om = rec.get("gross_margin"), rec.get("operating_margin")
    margin_ok = (gm is not None and gm >= 0.40) or (om is not None and om >= 0.12)
    de = rec.get("debt_to_equity")
    balance_ok = de is None or de <= 130
    size_ok = (rec.get("market_cap") or 0) >= 2e9
    eps = rec.get("eps_growth_fwd") if rec.get("eps_growth_fwd") is not None else rec.get("eps_growth")
    eps_ok = eps is None or eps >= 0.10
    return bool(growth_ok and quality_ok and margin_ok and balance_ok and size_ok and eps_ok)


def is_accelerator(rec, cfg):
    cagr = rec.get("rev_cagr_3y")
    rg = rec.get("rev_growth")
    # REAL acceleration only: needs a 3Y trend AND recent growth clearly above it.
    # (No 'high growth' fallback — that's not acceleration, and it over-fired.)
    if cagr is None or rg is None:
        return False
    accel = rg >= cagr + 0.07 and rg >= 0.15        # ≥7pts above its own trend
    if not accel:
        return False
    if (rec.get("conviction_score") or 0) < 6.0:    # only ones we have conviction in
        return False
    rm = rec.get("rec_mean")
    up = rec.get("analyst_upside_percent")
    analyst_ok = (rm is not None and rm <= 2.6) or (up is not None and up >= 0.12)
    bs = rec.get("beat_streak")
    surprise_ok = bs is None or bs >= 0             # not on a miss streak
    om = rec.get("operating_margin")
    not_broken = om is None or om > -0.10
    return bool(analyst_ok and surprise_ok and not_broken)


def future_leader_score(rec, cfg):
    """0–100 — emerging-leader strength. Disciplined: needs real margins, room, growth."""
    mc = rec.get("market_cap")
    if not mc:
        return None
    parts = []
    def add(v, w):
        parts.append((w, _c01(v)))
    # high growth
    add((rec.get("rev_growth") or 0) / 0.50, 24)
    # room to run: smaller cap = more upside headroom (peaks ~$2–12B)
    mc_b = mc / 1e9
    room = (40 - mc_b) / 38 if mc_b <= 40 else 0.0
    add(room, 18)
    # future-facing theme / AI
    add((rec.get("ai_exposure_score", 0) or 0) / 10.0, 16)
    # real, improving profitability path (gross margin = real business)
    add((rec.get("gross_margin") or 0) / 0.55, 14)
    # institutional interest (real money discovering it)
    io = rec.get("institutional_ownership")
    add((io or 0) / 0.7 if io is not None else 0.4, 12)
    # analyst support
    up = rec.get("analyst_upside_percent")
    add((up or 0) / 0.40 if up is not None else 0.4, 8)
    # discipline: penalise if already up a lot (late) — invert
    oyr = rec.get("one_year_return")
    add(1.0 - max(0.0, (oyr or 0) - 0.5) / 1.5, 8)
    tw = sum(p[0] for p in parts)
    return round(100.0 * sum(p[0] * p[1] for p in parts) / tw, 1)


def is_future_leader(rec, cfg):
    mc = rec.get("market_cap") or 0
    cap_ok = 1e9 <= mc <= 40e9                       # sub-mega-cap band
    growth_ok = (rec.get("rev_growth") or 0) >= 0.18
    real_business = (rec.get("gross_margin") or 0) >= 0.30  # not pre-revenue hype
    not_mooned = (rec.get("one_year_return") or 0) <= 2.0   # not already +200%
    score_ok = (rec.get("future_leader_score") or 0) >= 58
    return bool(cap_ok and growth_ok and real_business and not_mooned and score_ok)


def classify(rec, cfg):
    rec["future_leader_score"] = future_leader_score(rec, cfg)
    eng = []
    if is_compounder(rec, cfg):
        eng.append("compounder")
    if is_accelerator(rec, cfg):
        eng.append("accelerator")
    if is_future_leader(rec, cfg):
        eng.append("future_leader")
    rec["engines"] = eng
    return rec
