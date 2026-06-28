# -*- coding: utf-8 -*-
"""
conviction.py — Conviction Score (0–10): one number that says "how much do we
believe in this company", built from the durable signals (not noise).

Inputs (each 0..1, coverage-aware so missing data lowers — never inflates):
  quality      : ROIC / ROE + gross & operating margins (moat & efficiency)
  growth       : revenue growth + 3Y/5Y CAGR + EPS growth (durable expansion)
  analyst      : consensus + upside to mean target
  valuation    : reasonable forward P/E & EV/EBITDA (not cheap, not insane)
  balance_sheet: low debt / net cash
  institutional: % held by institutions (real money, not social sentiment)
  consistency  : earnings beat streak

Tiers:
  ≥9 High Conviction · ≥8 Strong Candidate · ≥6 Research More · <6 Watch
"""


def _c01(x):
    if x is None:
        return None
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return None


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _components(rec, cfg):
    th = cfg.get("thresholds", {}) or {}
    c = {}

    # quality — moat & efficiency
    roic = rec.get("roic")
    roe = rec.get("roe")
    q_roic = _c01((roic or 0) / max(0.01, th.get("roic_good", 0.12) * 1.6)) if roic is not None else None
    q_roe = _c01((roe or 0) / max(0.01, th.get("roe_good", 0.15) * 1.6)) if roe is not None else None
    gm = rec.get("gross_margin")
    om = rec.get("operating_margin")
    q_gm = _c01((gm or 0) / max(0.01, th.get("gross_margin_good", 0.45) * 1.3)) if gm is not None else None
    q_om = _c01((om or 0) / max(0.01, th.get("operating_margin_good", 0.15) * 1.7)) if om is not None else None
    c["quality"] = _avg([q_roic if q_roic is not None else q_roe, _avg([q_gm, q_om])])

    # growth — durable expansion
    g = []
    if rec.get("rev_growth") is not None:
        g.append(_c01(rec["rev_growth"] / 0.35))
    if rec.get("rev_cagr_3y") is not None:
        g.append(_c01(rec["rev_cagr_3y"] / 0.25))
    if rec.get("rev_cagr_5y") is not None:
        g.append(_c01(rec["rev_cagr_5y"] / 0.22))
    if rec.get("eps_growth_fwd") is not None:
        g.append(_c01(rec["eps_growth_fwd"] / 0.25))
    elif rec.get("eps_growth") is not None:
        g.append(_c01(rec["eps_growth"] / 0.30))
    c["growth"] = _avg(g)

    # analyst
    a = []
    rm = rec.get("rec_mean")
    if rm is not None:
        a.append(_c01((3.2 - rm) / 2.0))
    up = rec.get("analyst_upside_percent")
    if up is not None:
        a.append(_c01(up / max(0.01, th.get("analyst_upside_great", 0.30))))
    c["analyst"] = _avg(a)

    # valuation — smooth & monotonic: 1.0 at fwd P/E ≤ 20, down to 0 at ≥ 80
    fpe = rec.get("forward_pe")
    if fpe is not None and fpe > 0:
        c["valuation"] = _c01(1.0 - (fpe - 20.0) / 60.0)
    else:
        ev = rec.get("ev_ebitda")
        c["valuation"] = _c01(1.0 - (ev - 12.0) / 38.0) if (ev and ev > 0) else None

    # balance sheet
    de = rec.get("debt_to_equity")
    c["balance_sheet"] = _c01((th.get("debt_to_equity_ceiling", 150.0) - de) / th.get("debt_to_equity_ceiling", 150.0)) if de is not None else None

    # institutional ownership (real money). 40–85% is a healthy, accumulated range.
    io = rec.get("institutional_ownership")
    if io is not None:
        # reward 0.4–0.9; very low = undiscovered (slight); ~1.0 = crowded
        if io < 0.4:
            c["institutional"] = _c01(0.3 + io)            # 0.3..0.7 rising
        elif io <= 0.9:
            c["institutional"] = 1.0
        else:
            c["institutional"] = 0.7                        # near-saturated
    else:
        c["institutional"] = None

    # earnings consistency (beat streak; only set for focused names)
    bs = rec.get("beat_streak")
    if bs is not None:
        c["consistency"] = _c01((bs + 2) / 6.0)             # -2 → 0, +4 → 1
    else:
        c["consistency"] = None

    return c


WEIGHTS = {
    "quality": 2.0, "growth": 2.5, "analyst": 1.5, "valuation": 1.0,
    "balance_sheet": 1.0, "institutional": 1.0, "consistency": 1.0,
}


def compute(rec, cfg):
    comps = _components(rec, cfg)
    total_w = sum(WEIGHTS.values())
    got_w = 0.0
    acc = 0.0
    for k, w in WEIGHTS.items():
        v = comps.get(k)
        if v is None:
            continue
        got_w += w
        acc += w * v
    if got_w == 0:
        rec["conviction_score"] = None
        rec["conviction_tier"] = None
        return rec
    raw = acc / got_w                       # 0..1 quality of what we know
    coverage = got_w / total_w
    # heavier coverage penalty than before (less false confidence on sparse data),
    # but maxes at 1.0 so conviction stays within 0..10.
    score10 = 10.0 * raw * (0.5 + 0.5 * coverage)
    score10 = min(10.0, score10)
    # cyclical/commodity names: discount conviction — hot numbers are temporary
    # (commodity-price driven), so they shouldn't outrank durable secular leaders.
    if rec.get("cyclical"):
        score10 *= 0.82
    score10 = round(score10, 1)
    rec["conviction_score"] = score10
    rec["conviction_tier"] = tier(score10)
    rec["_conviction_components"] = {k: (round(v, 2) if v is not None else None) for k, v in comps.items()}
    return rec


def tier(s):
    if s is None:
        return None
    if s >= 9:
        return "High Conviction"
    if s >= 8:
        return "Strong Candidate"
    if s >= 6:
        return "Research More"
    return "Watch"
