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


def fair_value(rec, cfg):
    """Rough fair value: re-rate forward P/E toward a 'fair' multiple. Labelled rough."""
    th = cfg.get("thresholds", {}) or {}
    price = rec.get("price")
    fpe = rec.get("forward_pe")
    if not price or not fpe or fpe <= 0:
        return None
    fair_pe = th.get("forward_pe_fair_max", 35.0)
    # implied forward EPS = price / fpe; fair value at the fair multiple
    model_fv = price * (fair_pe / fpe)
    tgt = rec.get("target_mean")
    if tgt:
        # if model and analysts disagree a lot, don't fake a 'consensus' fair value
        if abs(model_fv - tgt) / tgt > 0.30:
            return None
        fv = 0.5 * model_fv + 0.5 * tgt
    else:
        fv = model_fv
    fv = max(price * 0.4, min(price * 2.5, fv))     # keep sane (0.4x..2.5x)
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
    rec["valuation_method"] = ("تقدير تقريبي بإعادة تسعير مكرّر الربحية — ليس نموذج DCF حقيقي"
                               if rec.get("fair_value_estimate") else None)
    hp = holding_period(rec, cfg)
    rec["suggested_holding_period"] = hp
    months = hold_months(rec, cfg)
    rec["suggested_hold_months"] = months
    rec["suggested_hold_label"] = _hold_label(months)
    rec["exit_conditions"] = exit_conditions(rec, cfg)
    return rec
