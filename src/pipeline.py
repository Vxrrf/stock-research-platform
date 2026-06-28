# -*- coding: utf-8 -*-
"""
pipeline.py — the ONE shared per-record scoring pipeline.

Both the production run (src/main.py) and ad-hoc tools (tools/check_tickers.py)
call these so a record is scored identically everywhere. Keeping this in one
place is what stops an ad-hoc checker from printing a different verdict than the
real dashboard (the drift Codex flagged).

Two stages, matching main.py:
  enrich_record   — themes, halal, fundamental, cross-source, opp/risk, targets, flags
  finalize_scores — total_score (fundamental + capped bonuses − penalties), conviction,
                    engines, rank_score, weaknesses

Tracker-derived inputs (earnings_score_adj, insider_confidence_score, _news_sentiment,
political buys) are read from the record if present and default to 0 when trackers
didn't run — exactly how main behaves under --smart/--no-trackers.
"""

import themes
import halal_gate
import scoring
import cross_source
import price_targets
import flags
import conviction as conviction_mod
import engines as engines_mod
import political as political_mod
import sanity
import framework
import forward as forward_mod


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def enrich_record(rec, cfg, ext, overrides=None):
    """Core per-record enrichment (no network trackers). Mirrors main.py step 2."""
    themes.classify(rec)
    rec["is_fund"] = sanity.is_fund(rec)                        # ETF/fund? never score as a single stock
    sanity.flag_suspect(rec)                                    # implausible data → fault, not signal
    halal_gate.apply(rec, cfg, extra={}, overrides=overrides)   # extra={}: yfinance can't verify interest income
    rec["fundamental_score"] = scoring.fundamental_score(rec, cfg)
    cross_source.apply(rec, cfg, ext)
    rec["opportunity_score"] = scoring.opportunity_score(rec, cfg)
    rec["risk_score"] = scoring.risk_score(rec, cfg)
    price_targets.apply(rec, cfg)
    flags.crowding_flag(rec, cfg)
    flags.popular_not_cheap_flag(rec, cfg)
    return rec


def finalize_scores(rec, cfg, buys=None, rank_weights=None, prev_metrics=None):
    """Total score + conviction + engines + rank. Mirrors main.py step 4 EXACTLY,
    including theme bonus, external confirmations, earnings/insider/political/news
    adjustments and the hype penalty — so total_score is never just fundamental_score."""
    news_max = (cfg.get("news", {}) or {}).get("max_weight_pct", 0.05)
    base = rec.get("fundamental_score") or 0.0
    theme_b = themes.theme_bonus(rec, cfg)
    ext_b = rec.get("external_bonus", 0) or 0
    earn = rec.get("earnings_score_adj", 0) or 0
    isc = rec.get("insider_confidence_score")
    ins = max(-2.0, min(2.0, (isc - 5) * 0.4)) if isc is not None else 0.0
    # political trades = INFO only (delayed, noisy, US-specific) — surfaced in the dashboard
    # tab but no longer fed into the score (Codex review fix).
    rec["political_bonus"] = political_mod.political_bonus(rec, buys, cfg) if buys else 0
    sent = rec.get("_news_sentiment") or 0.0
    news_adj = round(sent * (news_max * base), 2)            # ≤ 5% of base
    rec["news_impact_score"] = news_adj
    hype = flags.hype_penalty(rec, cfg)
    total = _clamp(base + theme_b + ext_b + earn + ins + news_adj - hype)
    rec["total_score"] = round(total, 1)
    rec["weaknesses"] = scoring.weaknesses(rec, cfg)
    if rec.get("is_fund"):
        # ETFs/funds are a CORE HOLD, not a stock pick — don't fabricate conviction/engines.
        rec["conviction_score"] = None
        rec["conviction_tier"] = None
        rec["engines"] = []
        rec["rank_score"] = 0.0          # keep out of the stock-hunting ranks
        return rec
    conviction_mod.compute(rec, cfg)
    engines_mod.classify(rec, cfg)
    forward_mod.forward_outlook(rec, cfg, prev_metrics)               # نظرة مستقبلية — must precede rank
    rec["rank_score"] = scoring.overall_rank(rec, cfg, rank_weights)  # penalises suspect/not-investable
    framework.annotate(rec)          # personal playbook tag (Growth / Gold-Cyclical / Trading)
    return rec
