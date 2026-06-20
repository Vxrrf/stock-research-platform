# -*- coding: utf-8 -*-
"""
schema.py — the canonical data contract every module shares.

A "record" is a plain dict (matching the existing code style). This module
defines the field names, the controlled vocabularies, and the exact column
order for every CSV the platform emits, so producers and consumers never drift.

Hard product rules encoded here:
  * Every output carries: data_source, last_updated, data_freshness_status, confidence.
  * Actions are a fixed vocabulary. There is NO "BUY NOW".
  * Halal status is pass / fail / unknown (never guessed).
"""

from datetime import datetime, timezone, timedelta

# ──────────────────────────────────────────────────────────────────
#  Controlled vocabularies
# ──────────────────────────────────────────────────────────────────
ACTIONS = [
    "Candidate",
    "Research More",
    "Watch",
    "Verify Halal First",
    "Avoid",
]

HALAL_STATUS = ["pass", "fail", "unknown"]          # never guess

FRESHNESS = ["FRESH", "STALE", "MISSING"]
CONFIDENCE = ["HIGH", "MEDIUM", "LOW"]

HOLDING_PERIODS = ["short", "medium", "long"]        # 0-6m / 6-18m / 18m+

MARKET_RISK = ["Low", "Medium", "High", "Extreme"]


# ──────────────────────────────────────────────────────────────────
#  The full record field set (documentation + defaults)
# ──────────────────────────────────────────────────────────────────
def blank_record(ticker):
    """A record pre-populated with None so every downstream key exists."""
    return {
        # identity
        "ticker": ticker,
        "name": ticker,
        "sector": None,
        "industry": None,
        "market_cap": None,
        "price": None,
        # provenance (REQUIRED on every output)
        "data_source": None,            # "FMP" | "yfinance" | "FMP+yfinance"
        "last_updated": None,           # ISO ts of price/quote retrieval
        "fundamentals_last_updated": None,  # ISO date of latest reported quarter
        "data_freshness_status": "MISSING",
        "confidence": "LOW",
        # growth
        "rev_growth": None,
        "rev_cagr_3y": None,
        "rev_cagr_5y": None,
        "eps_growth": None,
        "eps_growth_fwd": None,
        # cash / balance sheet / quality
        "fcf": None,
        "fcf_margin": None,
        "revenue_ttm": None,
        "interest_income": None,        # FMP income statement — enables halal purification test
        "receivables": None,
        "total_debt": None,
        "total_cash": None,
        "debt_to_equity": None,
        "net_debt": None,
        "roic": None,
        "roe": None,
        "gross_margin": None,
        "operating_margin": None,
        # valuation
        "pe": None,
        "forward_pe": None,
        "ev_ebitda": None,
        "peg": None,
        # analyst
        "rec_mean": None,
        "rec_key": None,
        "num_analysts": None,
        "target_mean": None,
        "target_high": None,
        "target_low": None,
        "analyst_upside_percent": None,
        # momentum / risk
        "one_year_return": None,
        "week52_high": None,
        "week52_low": None,
        "pct_below_52w_high": None,
        "beta": None,
        "avg_dollar_volume": None,
        "div_yield": None,
        # insider (spec §6)
        "insider_buy_count": None,
        "insider_sell_count": None,
        "insider_confidence_score": None,   # 0..10
        # themes / AI (spec §7)
        "themes": [],
        "primary_theme": None,
        "ai_exposure_score": 0,             # 0..10
        # scores
        "fundamental_score": None,          # 0..100 (primary)
        "opportunity_score": None,          # 0..100 (spec §8)
        "risk_score": None,                 # 0..100 (spec §8)
        "total_score": None,                # 0..100 (fundamental + capped bonuses)
        "rank_score": None,                 # 0..~120 holistic "best overall" rank
        # conviction + engines (v2 — hunting asymmetric winners)
        "conviction_score": None,           # 0..10
        "conviction_tier": None,            # High Conviction / Strong Candidate / Research More / Watch
        "engines": [],                      # subset of: compounder / accelerator / future_leader
        "future_leader_score": None,        # 0..100
        "lifecycle_status": None,           # New Discovery / Emerging / High Conviction / Compounder / Falling / Fallen Angel
        # institutional (he values this over social sentiment)
        "institutional_ownership": None,    # % held by institutions (0..1)
        "insider_ownership": None,          # % held by insiders (0..1)
        # cross-source (spec §2)
        "independent_confirmations": 0,
        "external_bonus": 0,
        "confirmation_groups": [],
        # halal (spec §11)
        "halal_status": "unknown",
        "halal_reasons": [],
        "halal_ratios": {},
        # flags (spec §12, §13)
        "crowded_late": False,
        "popular_not_cheap": False,
        # earnings (spec §5)
        "next_earnings_date": None,
        "eps_estimate": None,
        "revenue_estimate": None,
        "actual_eps": None,
        "actual_revenue": None,
        "guidance": None,                   # raised/lowered — needs FMP transcripts
        "last_beat_miss": None,             # "beat" | "miss" | None
        "beat_streak": None,
        "earnings_score_adj": 0,
        # news / political (spec §9, §10)
        "news_impact_score": 0,             # signed, tiny
        "political_bonus": 0,               # 0..3
        # price targets (spec §14)
        "fair_value_estimate": None,
        "bear_case_price": None,
        "base_case_price": None,
        "bull_case_price": None,
        "suggested_holding_period": None,
        "exit_conditions": [],
        # discovery / memory (spec §3, §4)
        "discovery_status": None,           # new_discovery | returning_discovery
        # final
        "action": None,
        "action_reason": None,
        "weaknesses": [],
        "summary": "",
    }


# ──────────────────────────────────────────────────────────────────
#  CSV column orders (spec §18). Keep stable — the dashboard relies on them.
# ──────────────────────────────────────────────────────────────────
PROVENANCE_COLS = ["data_source", "last_updated", "data_freshness_status", "confidence"]

RANKED_COLS = [
    "ticker", "name", "sector", "primary_theme", "price", "market_cap",
    "total_score", "fundamental_score", "opportunity_score", "risk_score",
    "ai_exposure_score", "rev_growth", "rev_cagr_3y", "eps_growth_fwd",
    "forward_pe", "ev_ebitda", "roic", "roe", "fcf_margin", "debt_to_equity",
    "analyst_upside_percent", "num_analysts", "rec_key",
    "one_year_return", "pct_below_52w_high",
    "independent_confirmations", "external_bonus",
    "insider_confidence_score", "earnings_score_adj", "news_impact_score",
    "political_bonus", "halal_status", "crowded_late", "popular_not_cheap",
    "fair_value_estimate", "bear_case_price", "base_case_price", "bull_case_price",
    "suggested_holding_period", "action", "action_reason",
] + PROVENANCE_COLS

WATCHLIST_COLS = [
    "ticker", "name", "first_discovery_date", "discovery_score", "highest_score",
    "current_score", "number_of_appearances", "previous_rankings",
    "discovery_status", "action",
] + PROVENANCE_COLS

DISCOVERY_LOG_COLS = [
    "run_timestamp", "ticker", "name", "total_score", "fundamental_score",
    "ai_exposure_score", "primary_theme", "independent_confirmations",
    "action", "discovery_status",
] + PROVENANCE_COLS

EARNINGS_COLS = [
    "ticker", "name", "next_earnings_date", "eps_estimate", "revenue_estimate",
    "actual_eps", "actual_revenue", "last_beat_miss", "beat_streak",
    "guidance", "earnings_score_adj",
] + PROVENANCE_COLS

INSIDER_COLS = [
    "ticker", "name", "insider_buy_count", "insider_sell_count",
    "ceo_buying", "director_buying", "exec_selling", "heavy_selling",
    "insider_confidence_score",
] + PROVENANCE_COLS

NEWS_COLS = [
    "event_name", "date", "affected_sectors", "impact_score",
    "impact_direction", "time_horizon", "source", "notes",
]

POLITICAL_COLS = [
    "politician_name", "ticker", "transaction_type", "transaction_date",
    "estimated_value", "disclosure_delay", "source_url", "note",
]

PORTFOLIO_COLS = [
    "bucket", "allocation_pct", "suggested_holdings", "notes",
]

AVOID_COLS = [
    "ticker", "name", "sector", "action", "reason", "halal_status",
] + PROVENANCE_COLS


# ──────────────────────────────────────────────────────────────────
#  Time helpers (Qatar local stamp, used across reports)
# ──────────────────────────────────────────────────────────────────
def now_utc():
    return datetime.now(timezone.utc)


def now_local(utc_offset=3):
    return datetime.now(timezone(timedelta(hours=utc_offset)))


def iso(dt):
    if dt is None:
        return None
    return dt.isoformat(timespec="seconds")
