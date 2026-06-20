# -*- coding: utf-8 -*-
"""
scoring.py — fundamental_score (spec §1) + opportunity/risk (spec §8).

Philosophy (inherited from the original screener):
  * Strict hard gates protect you; a weighted score ranks what survives.
  * Every component is clamped to its weight so outliers can't blow up the score.
  * Missing data lowers the score modestly (coverage discount) — it never
    silently inflates it.

fundamental_score is the PRIMARY number. opportunity_score and risk_score are
the forward-looking reward/danger pair from spec §8.
"""


def _c01(x):
    if x is None:
        return None
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return None


def _tent(x, lo, peak, hi):
    """1.0 at peak, linearly 0 at lo and hi, None if x is None/out of [lo,hi]."""
    if x is None:
        return None
    if x <= lo or x >= hi:
        return 0.0
    if x == peak:
        return 1.0
    if x < peak:
        return (x - lo) / (peak - lo)
    return (hi - x) / (hi - peak)


def _components(rec, cfg):
    """Return dict component_name -> value in [0,1] (or None if no data)."""
    th = cfg.get("thresholds", {}) or {}
    c = {}

    c["revenue_growth"] = _c01((rec.get("rev_growth") or 0) / max(0.01, th.get("revenue_growth_great", 0.35))) \
        if rec.get("rev_growth") is not None else None
    c["rev_cagr_3y"] = _c01((rec.get("rev_cagr_3y") or 0) / max(0.01, th.get("rev_cagr_3y_good", 0.15) * 1.6)) \
        if rec.get("rev_cagr_3y") is not None else None
    c["rev_cagr_5y"] = _c01((rec.get("rev_cagr_5y") or 0) / max(0.01, th.get("rev_cagr_5y_good", 0.12) * 1.6)) \
        if rec.get("rev_cagr_5y") is not None else None
    c["eps_growth"] = _c01((rec.get("eps_growth") or 0) / 0.30) if rec.get("eps_growth") is not None else None
    c["eps_growth_fwd"] = _c01((rec.get("eps_growth_fwd") or 0) / 0.25) if rec.get("eps_growth_fwd") is not None else None

    if rec.get("fcf_margin") is not None:
        c["free_cash_flow"] = _c01(rec["fcf_margin"] / max(0.01, th.get("fcf_margin_good", 0.10) * 2))
    elif rec.get("fcf") is not None:
        c["free_cash_flow"] = 0.6 if rec["fcf"] > 0 else 0.1
    else:
        c["free_cash_flow"] = None

    de = rec.get("debt_to_equity")
    ceil = th.get("debt_to_equity_ceiling", 150.0)
    c["debt"] = _c01((ceil - de) / ceil) if de is not None else None

    c["roic"] = _c01((rec.get("roic") or 0) / max(0.01, th.get("roic_good", 0.12) * 1.7)) \
        if rec.get("roic") is not None else None
    c["roe"] = _c01((rec.get("roe") or 0) / max(0.01, th.get("roe_good", 0.15) * 1.7)) \
        if rec.get("roe") is not None else None
    c["gross_margin"] = _c01((rec.get("gross_margin") or 0) / max(0.01, th.get("gross_margin_good", 0.45) * 1.4)) \
        if rec.get("gross_margin") is not None else None
    c["operating_margin"] = _c01((rec.get("operating_margin") or 0) / max(0.01, th.get("operating_margin_good", 0.15) * 1.8)) \
        if rec.get("operating_margin") is not None else None

    fpe = rec.get("forward_pe")
    if fpe is not None and fpe > 0:
        # smooth, monotonic (config-driven): 1.0 at ≤ fair_min, 0 at ≥ zero_score
        fmin = th.get("forward_pe_fair_min", 20.0)
        fzero = th.get("forward_pe_zero_score", 80.0)
        c["forward_pe"] = _c01(1.0 - (fpe - fmin) / max(1.0, fzero - fmin))
    else:
        c["forward_pe"] = None

    ev = rec.get("ev_ebitda")
    if ev is not None and ev > 0:
        fair = th.get("ev_ebitda_fair_max", 25.0)
        mult = th.get("ev_ebitda_multiplier", 1.8)
        c["ev_ebitda"] = _c01(1.0 - ev / (fair * mult))
    else:
        c["ev_ebitda"] = None

    rm = rec.get("rec_mean")
    c["analyst_consensus"] = _c01((3.2 - rm) / 2.0) if rm is not None else None

    up = rec.get("analyst_upside_percent")
    c["analyst_upside"] = _c01(up / max(0.01, th.get("analyst_upside_great", 0.30))) if up is not None else None

    # being 10–35% below the 52w high = healthy room to run; near high or crashed = less
    c["dist_52w_high"] = _tent(rec.get("pct_below_52w_high"), 0.0, 0.20, 0.70)

    # healthy momentum: positive but not a bubble
    c["one_year_return"] = _tent(rec.get("one_year_return"), -0.30, 0.30, 2.0)

    isc = rec.get("insider_confidence_score")
    c["insider"] = _c01(isc / 10.0) if isc is not None else None

    # market cap: reward the mid-cap growth sweet spot (the "smart hunting" zone —
    # bigger than gambling micro-caps, smaller than already-flown mega-caps).
    mc = rec.get("market_cap")
    c["market_cap"] = _tent(mc / 1e9, 0.5, 14.0, 280.0) if mc else None

    return c


def fundamental_score(rec, cfg):
    w = cfg.get("score_weights", {}) or {}
    comps = _components(rec, cfg)
    total_w = sum(w.values()) or 1.0
    got_w = 0.0
    acc = 0.0
    for name, weight in w.items():
        val = comps.get(name)
        if val is None:
            continue
        got_w += weight
        acc += weight * val
    if got_w == 0:
        return 0.0
    raw = acc / got_w                  # quality of what we know (0..1)
    coverage = got_w / total_w         # how much we know (0..1)
    score = 100.0 * raw * (0.60 + 0.40 * coverage)
    # cyclical/commodity names: discount fundamentals too (not just conviction) so the
    # cyclical penalty propagates through overall_rank (fatal-audit fix).
    if rec.get("cyclical"):
        score *= 0.82
    rec["_score_coverage"] = round(coverage, 2)
    return round(score, 1)


def opportunity_score(rec, cfg):
    """Forward reward (0..100): upside + growth + theme/AI + room + confirmations."""
    parts = []
    def add(val, weight):
        if val is not None:
            parts.append((weight, max(0.0, min(1.0, val))))

    th = cfg.get("thresholds", {}) or {}
    up = rec.get("analyst_upside_percent")
    add(up / max(0.01, th.get("analyst_upside_great", 0.30)) if up is not None else None, 22)
    add((rec.get("rev_growth") or 0) / 0.35 if rec.get("rev_growth") is not None else None, 18)
    add((rec.get("eps_growth_fwd") or 0) / 0.25 if rec.get("eps_growth_fwd") is not None else None, 12)
    add((rec.get("ai_exposure_score", 0) or 0) / 10.0, 12)
    add(_tent(rec.get("pct_below_52w_high"), 0.0, 0.25, 0.75), 12)
    add((rec.get("fundamental_score") or 0) / 100.0, 14)
    add(min(1.0, (rec.get("independent_confirmations", 0) or 0) / 3.0), 10)
    if not parts:
        return None
    tw = sum(p[0] for p in parts)
    val = sum(p[0] * p[1] for p in parts) / tw
    return round(100.0 * val, 1)


def risk_score(rec, cfg):
    """Danger (0..100, higher = riskier): valuation, debt, beta, crowding, drawdown,
    weak profitability, low coverage, halal not-pass, hype runup."""
    th = cfg.get("thresholds", {}) or {}
    cr = cfg.get("crowding", {}) or {}
    parts = []
    def add(val, weight):
        if val is not None:
            parts.append((weight, max(0.0, min(1.0, val))))

    fpe = rec.get("forward_pe")
    if fpe is not None and fpe > 0:
        add((fpe - th.get("forward_pe_fair_max", 35.0)) / 60.0, 16)
    ev = rec.get("ev_ebitda")
    if ev is not None and ev > 0:
        add((ev - th.get("ev_ebitda_fair_max", 25.0)) / 40.0, 10)
    de = rec.get("debt_to_equity")
    if de is not None:
        add(de / (th.get("debt_to_equity_ceiling", 150.0) * 1.5), 12)
    beta = rec.get("beta")
    if beta is not None:
        add((beta - 1.0) / 1.5, 10)
    up = rec.get("analyst_upside_percent")
    if up is not None and up < 0:                                   # analysts expect a FALL = risk
        add((-up) / max(0.01, th.get("analyst_upside_great", 0.30)), 10)
    oyr = rec.get("one_year_return")
    if oyr is not None:
        add((oyr - 0.6) / (cr.get("hype_one_year_return", 2.0)), 14)  # runup risk
    pbh = rec.get("pct_below_52w_high")
    if pbh is not None:
        add(1.0 - pbh / 0.10 if pbh < 0.10 else 0.0, 8)              # crowded near highs
    gm = rec.get("operating_margin")
    if gm is not None:
        add((0.10 - gm) / 0.30 if gm < 0.10 else 0.0, 8)             # thin/negative margins
    cov = rec.get("_score_coverage")
    if cov is not None:
        add(1.0 - cov, 8)                                            # data-gap risk
    # NOTE: halal is NOT added here — it's a hard gate (fail→Avoid, hidden;
    # unknown→Verify First). Penalising risk for it double-counts and unfairly
    # inflates risk for the normal 'unknown' state on free data. (panel fix)
    na = rec.get("num_analysts")
    if na is not None:
        add((6 - na) / 6.0 if na < 6 else 0.0, 6)

    if not parts:
        return None
    tw = sum(p[0] for p in parts)
    val = sum(p[0] * p[1] for p in parts) / tw
    return round(100.0 * val, 1)


DEFAULT_RANK_WEIGHTS = {"conv": 0.40, "opp": 0.20, "lowrisk": 0.15, "fund": 0.15, "total": 0.10}


def overall_rank(rec, cfg, weights=None):
    """Holistic 'best across everything' score → #1 is the best all-around.
    Blends conviction (consolidated quality) + opportunity + low-risk + fundamentals
    + total, with bonuses for engine membership & confirmations, scaled by data confidence.
    `weights` (from the active investor mode) re-weights the blend; defaults to balanced."""
    w = weights or DEFAULT_RANK_WEIGHTS
    conv = (rec.get("conviction_score") or 0) * 10.0          # 0..100
    opp = rec.get("opportunity_score") or 0.0
    risk = rec.get("risk_score")
    lowrisk = (100.0 - risk) if risk is not None else 50.0
    fund = rec.get("fundamental_score") or 0.0
    total = rec.get("total_score") or 0.0
    base = (w.get("conv", 0.40) * conv + w.get("opp", 0.20) * opp
            + w.get("lowrisk", 0.15) * lowrisk + w.get("fund", 0.15) * fund
            + w.get("total", 0.10) * total)
    eng = len(rec.get("engines") or []) * 2.0                  # quality signal
    conf = (rec.get("independent_confirmations") or 0) * 1.5
    cmul = {"HIGH": 1.0, "MEDIUM": 0.96, "LOW": 0.88}.get(rec.get("confidence"), 0.92)
    return round((base + eng + conf) * cmul, 1)


def weaknesses(rec, cfg):
    """Honest, human-readable weak points (kept from the original system's spirit)."""
    th = cfg.get("thresholds", {}) or {}
    w = []
    if rec.get("rev_growth") is not None and rec["rev_growth"] < th.get("revenue_growth_good", 0.18):
        w.append(f"moderate revenue growth ({rec['rev_growth']:+.0%})")
    if rec.get("operating_margin") is not None and rec["operating_margin"] <= 0:
        w.append("not operating-profitable yet")
    if rec.get("forward_pe") is not None and rec["forward_pe"] > th.get("forward_pe_rich", 55.0):
        w.append(f"rich valuation (fwd P/E {rec['forward_pe']:.0f})")
    if rec.get("ev_ebitda") is not None and rec["ev_ebitda"] > th.get("ev_ebitda_fair_max", 25.0) * 1.5:
        w.append(f"high EV/EBITDA ({rec['ev_ebitda']:.0f})")
    if rec.get("debt_to_equity") is not None and rec["debt_to_equity"] > th.get("debt_to_equity_ceiling", 150.0):
        w.append(f"elevated debt (D/E {rec['debt_to_equity']:.0f}%)")
    if rec.get("analyst_upside_percent") is not None and rec["analyst_upside_percent"] < 0:
        w.append(f"mean target below price ({rec['analyst_upside_percent']:+.0%})")
    if rec.get("one_year_return") is not None and rec["one_year_return"] > 1.0:
        w.append(f"already ran up a lot ({rec['one_year_return']:+.0%} in 1y)")
    if rec.get("beta") is not None and rec["beta"] > 1.8:
        w.append(f"high volatility (beta {rec['beta']:.1f})")
    if rec.get("confidence") == "LOW":
        w.append("LOW data confidence (stale/missing inputs)")
    return w
