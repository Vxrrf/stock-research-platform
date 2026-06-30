# -*- coding: utf-8 -*-
"""
sanity.py — data-hygiene guards (from the multi-persona audit).

Two jobs, both about NOT trusting raw free data blindly:
  * flag_suspect(rec)  — mark implausible values (yfinance split/price artifacts)
    as a DATA fault, not a bullish signal. A +4553% return or a 10x price is bad
    data, so we flag it, soften confidence, and keep it out of the top ranks —
    instead of letting noise steer the ranking.
  * is_fund(rec)       — detect ETFs/funds (HLAL, SPUS, ...) so they're never
    scored as single stocks (no conviction 0/10, no "SELL", no cross-asset
    "better alternative"). A halal core ETF is a hold, not a stock pick.
"""

# Known funds/ETFs the user may hold or that appear in the universe.
FUND_TICKERS = {
    "HLAL", "SPUS", "SPY", "VOO", "IVV", "QQQ", "QQQM", "VTI", "VEA", "VWO",
    "SCHD", "DGRO", "VIG", "GLD", "IAU", "SGOL", "GLDM", "AGG", "BND", "VT",
    "VXUS", "VYM", "ARKK", "SMH", "SOXX", "XLK", "XLE", "XLF", "DIA", "IWM",
    "SPLG", "JEPI", "JEPQ", "VGT", "RSP",
}

_FUND_NAME_HINTS = (" etf", "ucits", " index fund", "index trust", " trust etf",
                    "ishares", "spdr", "invesco qqq", " fund)")


def is_fund(rec):
    """True if this looks like an ETF/fund, not an operating company."""
    t = str(rec.get("ticker") or "").upper()
    if t in FUND_TICKERS:
        return True
    name = (rec.get("name") or "").lower()
    if any(h in name for h in _FUND_NAME_HINTS):
        return True
    # ETFs typically carry no sector/industry AND no operating fundamentals
    no_classification = not rec.get("sector") and not rec.get("industry")
    no_fundamentals = (rec.get("rev_growth") is None and rec.get("operating_margin") is None
                       and rec.get("roic") is None and rec.get("gross_margin") is None)
    if no_classification and no_fundamentals and rec.get("market_cap"):
        return True
    return False


def flag_suspect(rec):
    """Mark implausible inputs as a data-quality fault (not signal). Softens confidence."""
    reasons = []
    oyr = rec.get("one_year_return")
    if isinstance(oyr, (int, float)) and oyr > 3.5:           # >+350% in 1y ≈ split/price artifact
        reasons.append(f"عائد سنة شاذ ({oyr:+.0%})")
    rg = rec.get("rev_growth")
    if isinstance(rg, (int, float)) and rg > 2.0:             # >+200% YoY revenue ≈ bad data
        reasons.append(f"نمو إيراد شاذ ({rg:+.0%})")
    pe = rec.get("forward_pe")
    if isinstance(pe, (int, float)) and pe > 400:
        reasons.append("مكرّر ربحية شاذ")
    pr = rec.get("price")
    wh = rec.get("week52_high")
    # a price far ABOVE its own 52w high usually means a stale/split-broken quote. (pct_below_52w_high
    # is clamped to >=0 by its producer, so detect the artifact from the RAW price vs high.)
    if isinstance(pr, (int, float)) and isinstance(wh, (int, float)) and wh > 0 and pr > wh * 1.5:
        reasons.append("السعر أعلى من قمة 52 أسبوع بكثير (سعر شاذ)")
    rec["data_suspect"] = bool(reasons)
    rec["data_suspect_reasons"] = reasons
    if reasons and rec.get("confidence") == "HIGH":
        rec["confidence"] = "MEDIUM"
    return rec


def pnl_is_suspect(price, buy_price, freshness=None):
    """True when a holding's P&L shouldn't be trusted (price artifact or stale data)."""
    if price != price or buy_price != buy_price:    # NaN guard (nan != nan) — a NaN P&L is untrustworthy
        return True
    if not price or not buy_price or buy_price <= 0:
        return True
    pnl = price / buy_price - 1.0
    if abs(pnl) > 3.0:                       # >±300% on a held name ≈ broken price
        return True
    if freshness in ("STALE", "MISSING"):
        return True
    return False
