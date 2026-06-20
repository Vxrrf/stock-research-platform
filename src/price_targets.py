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
    fv = price * (fair_pe / fpe)
    # blend with analyst mean target if present (anchors to the market view)
    tgt = rec.get("target_mean")
    if tgt:
        fv = 0.5 * fv + 0.5 * tgt
    # keep it sane: within 0.4x..2.5x of price
    fv = max(price * 0.4, min(price * 2.5, fv))
    return _round(fv)


def scenarios(rec, cfg):
    price = rec.get("price")
    if not price:
        return None, None, None
    hi = rec.get("target_high")
    lo = rec.get("target_low")
    mean = rec.get("target_mean")
    base = mean or price
    bull = hi or (base * 1.25)
    bear = lo or (price * 0.7)
    # ensure ordering bear <= base <= bull
    bear = min(bear, base)
    bull = max(bull, base)
    return _round(bear), _round(base), _round(bull)


def holding_period(rec, cfg):
    """short 0-6m / medium 6-18m / long 18m+ — driven by durability of growth."""
    th = cfg.get("thresholds", {}) or {}
    growth = rec.get("rev_cagr_3y") or rec.get("rev_growth") or 0
    ai = rec.get("ai_exposure_score", 0) or 0
    risk = rec.get("risk_score") or 50
    durable = (growth >= th.get("rev_cagr_3y_good", 0.15)) or (ai >= 6)
    if durable and risk < 65:
        return "long"
    if growth >= th.get("revenue_growth_good", 0.18) * 0.6 or ai >= 4:
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


def apply(rec, cfg):
    rec["fair_value_estimate"] = fair_value(rec, cfg)
    bear, base, bull = scenarios(rec, cfg)
    rec["bear_case_price"] = bear
    rec["base_case_price"] = base
    rec["bull_case_price"] = bull
    rec["suggested_holding_period"] = holding_period(rec, cfg)
    rec["exit_conditions"] = exit_conditions(rec, cfg)
    return rec
