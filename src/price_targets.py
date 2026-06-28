# -*- coding: utf-8 -*-
"""
price_targets.py — price target engine (spec §14).

For every stock we surface:
  current_price, analyst_average_target, analyst_upside_percent,
  fair_value_estimate (rough, labelled), bear / base / bull case prices,
  suggested_holding_period, and exit_conditions (NOT guaranteed sell dates).

We NEVER promise a stock will reach a specific price. Bear/base/bull are
scenarios anchored on the analyst range (when available) or on price bands.
"""


def _round(x, n=2):
    return round(x, n) if isinstance(x, (int, float)) else None


def _dcf_per_share(rec, cfg):
    """A SIMPLE fading-growth DCF cross-check (NOT a full model): project FCF with
    growth fading to a terminal rate, discount, add a Gordon terminal value, and
    scale to a per-share number via market cap. Returns None unless inputs are sane.

    Honesty: free data gives only TTM FCF + a rough growth proxy, so this is a
    sanity anchor, not a precise valuation. It is one of several anchors we cross-check."""
    th = cfg.get("thresholds", {}) or {}
    fcf = rec.get("fcf")
    mcap = rec.get("market_cap")
    price = rec.get("price")
    if not fcf or fcf <= 0 or not mcap or mcap <= 0 or not price or price <= 0:
        return None
    r = th.get("dcf_discount_rate", 0.10)
    tg = th.get("dcf_terminal_growth", 0.03)
    H = int(th.get("dcf_high_growth_years", 10))
    if r <= tg:
        return None
    cap = th.get("dcf_growth_cap", 0.25)
    g0 = rec.get("rev_cagr_3y")
    if g0 is None:
        g0 = rec.get("rev_growth")
    if g0 is None:
        g0 = rec.get("eps_growth_fwd")
    if g0 is None:
        g0 = 0.06
    g0 = max(0.0, min(cap, g0))                       # conservative: floor 0, cap config
    pv = 0.0
    f = float(fcf)
    for yr in range(1, H + 1):
        g = g0 + (tg - g0) * (yr - 1) / max(1, H - 1)  # fade g0 → terminal over H years
        f *= (1.0 + g)
        pv += f / ((1.0 + r) ** yr)
    terminal = f * (1.0 + tg) / (r - tg)               # Gordon growth terminal value
    pv += terminal / ((1.0 + r) ** H)
    equity_value = pv                                  # FCF≈FCFE proxy on free data
    per_share = equity_value * price / mcap            # scale by shares = mcap/price
    if per_share <= 0:
        return None
    return max(price * 0.3, min(price * 3.0, per_share))


def fair_value(rec, cfg):
    """Cross-checked fair value from up to THREE independent anchors:
      1) forward-P/E re-rate toward a fair multiple
      2) a simple fading-growth DCF
      3) analyst mean target
    We blend the anchors that AGREE (within tolerance) and refuse to fake a number
    when they disagree badly. rec['fair_value_method'] records which agreed."""
    th = cfg.get("thresholds", {}) or {}
    price = rec.get("price")
    if not price or price <= 0:
        rec["fair_value_dcf"] = None
        rec["fair_value_method"] = None
        return None

    anchors = []          # (label, value)
    fpe = rec.get("forward_pe")
    if fpe and fpe > 0:
        anchors.append(("مكرّر ربحية", price * (th.get("forward_pe_fair_max", 35.0) / fpe)))
    dcf = _dcf_per_share(rec, cfg)
    rec["fair_value_dcf"] = _round(dcf)
    if dcf:
        anchors.append(("DCF مبسّط", dcf))
    tgt = rec.get("target_mean")
    if tgt:
        anchors.append(("هدف المحللين", tgt))

    if not anchors:
        rec["fair_value_method"] = None
        return None

    # keep only anchors that agree with the median within ±35% (drop the outlier)
    vals = sorted(v for _, v in anchors)
    med = vals[len(vals) // 2]
    kept = [(lab, v) for lab, v in anchors if med and abs(v - med) / med <= 0.35]
    if not kept:
        # all three disagree → don't fabricate a consensus
        rec["fair_value_method"] = "المصادر متباينة — لا تقدير موثوق"
        return None
    fv = sum(v for _, v in kept) / len(kept)
    fv = max(price * 0.4, min(price * 2.5, fv))     # keep sane (0.4x..2.5x)
    rec["fair_value_method"] = "تقاطُع: " + " + ".join(lab for lab, _ in kept)
    return _round(fv)


def scenarios(rec, cfg):
    price = rec.get("price")
    if not price:
        return None, None, None
    hi = rec.get("target_high")
    lo = rec.get("target_low")
    mean = rec.get("target_mean")
    base = mean or price
    # if analysts are net bearish (mean<price) BUT the high target shows upside,
    # don't let 'base' collapse to a pure downside number — blend toward neutral.
    if mean and mean < price and hi and hi > price:
        base = (mean + price) / 2.0
    bull = hi or (base * 1.25)
    bear = lo or (price * 0.7)
    bear = min(bear, base)                          # ensure bear ≤ base ≤ bull
    bull = max(bull, base)
    return _round(bear), _round(base), _round(bull)


def holding_period(rec, cfg):
    """short 0-6m / medium 6-18m / long 18m+ — driven by DURABLE growth (not just AI hype)."""
    th = cfg.get("thresholds", {}) or {}
    growth = rec.get("rev_cagr_3y") or rec.get("rev_growth") or 0
    ai = rec.get("ai_exposure_score", 0) or 0
    risk = rec.get("risk_score") or 50
    # AI exposure only upgrades the horizon when there is REAL growth behind it
    durable = (growth >= th.get("rev_cagr_3y_good", 0.15)) or (growth >= 0.10 and ai >= 6)
    if durable and risk < 65 and not rec.get("cyclical"):
        return "long"
    if (growth >= th.get("revenue_growth_good", 0.18) * 0.6) or (growth >= 0.08 and ai >= 6):
        return "medium"
    return "short"


def exit_conditions(rec, cfg):
    """Condition-based, never dated. Tailored to the record."""
    th = cfg.get("thresholds", {}) or {}
    out = [
        "Thesis break: revenue growth decelerates for two consecutive quarters "
        f"(below ~{th.get('revenue_growth_good', 0.18):.0%} yoy).",
        "Fundamentals deteriorate: operating margin compresses or net debt rises materially.",
        f"Position size exceeds {cfg.get('portfolio', {}).get('max_single_stock_pct', 0.15):.0%} "
        "of the portfolio — trim to rebalance, not because of price.",
    ]
    fpe = rec.get("forward_pe")
    if fpe and fpe > 0:
        rerate = max(fpe * 1.5, th.get("forward_pe_rich", 55.0))
        out.append(f"Valuation overshoot: forward P/E re-rates above ~{rerate:.0f} without an earnings upgrade.")
    if rec.get("analyst_upside_percent") is not None:
        out.append("Analyst mean target falls below the current price and estimates are being cut.")
    if rec.get("halal_status") != "pass":
        out.append("Halal status resolves to 'fail' on Zoya/Musaffa — exit regardless of price.")
    return out


def hold_months(rec, cfg):
    """A SPECIFIC target horizon in months (not a vague bucket — count it down over time)."""
    if rec.get("cyclical"):
        return 6                                  # cyclical = a trade, shorter leash
    hp = rec.get("suggested_holding_period")       # short/medium/long
    base = {"short": 4, "medium": 12, "long": 24}.get(hp, 9)
    conv = rec.get("conviction_score") or 6
    if hp == "long" and conv >= 9:
        base = 30                                  # highest-conviction compounders → longer
    if hp == "short" and conv <= 4:
        base = 3
    return base


def _hold_label(months):
    if months is None:
        return "—"
    if months < 6:
        return f"~{months} شهر (قصير — مضاربة)"
    if months < 18:
        return f"~{months} شهر (متوسط)"
    return f"~{months} شهر (طويل — مُركِّب)"


def apply(rec, cfg):
    rec["fair_value_estimate"] = fair_value(rec, cfg)
    bear, base, bull = scenarios(rec, cfg)
    rec["bear_case_price"] = bear
    rec["base_case_price"] = base
    rec["bull_case_price"] = bull
    # honest labelling: these are ANALYST scenarios, not a real valuation model
    rec["target_source"] = "إجماع المحللين" if rec.get("target_mean") else None
    rec["valuation_method"] = (rec.get("fair_value_method")
                               if rec.get("fair_value_estimate") else None)
    hp = holding_period(rec, cfg)
    rec["suggested_holding_period"] = hp
    months = hold_months(rec, cfg)
    rec["suggested_hold_months"] = months
    rec["suggested_hold_label"] = _hold_label(months)
    rec["exit_conditions"] = exit_conditions(rec, cfg)
    return rec
