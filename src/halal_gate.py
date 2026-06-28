# -*- coding: utf-8 -*-
"""
halal_gate.py — Sharia hard gate (spec §11). Status: pass / fail / unknown.

Hard rules (from the spec, encoded literally):
  * fail    -> action "AVOID - fails Sharia screen"   (only this module decides fail)
  * unknown -> action "Verify Halal First"
  * only `pass` is eligible to become a Candidate
  * NEVER guess. If a required input is missing, status = unknown.

Required inputs considered: business activity, interest-bearing debt,
interest income, cash & interest-bearing securities, debt/market-cap,
interest-income/revenue. AAOIFI-style thresholds come from config.halal.

Honesty note: free yfinance data usually lacks interest income, so the
interest-income/revenue test is not verifiable -> status stays `unknown`
(="Verify Halal First"). Add an FMP key (which exposes interest income) to
let compliant names reach `pass`. We would rather say "verify" than guess.
"""


import re


def _txt(rec):
    # IMPORTANT: only the controlled fields — NOT the long business summary,
    # whose noisy prose causes false positives (e.g. a chipmaker that mentions
    # "gaming" GPUs, or a payments firm that mentions "banks").
    return " ".join(str(rec.get(k) or "").lower()
                    for k in ("sector", "industry", "name"))


def _has(blob, term):
    """Word-boundary match so 'bank' doesn't hit 'embankment'."""
    return re.search(r"\b" + re.escape(term.lower()) + r"\b", blob) is not None


def screen(rec, cfg, extra=None):
    """
    Returns (status, reasons[], ratios{}). Pure: also safe to call standalone.
    `extra` may carry FMP-derived fields: interest_income, total_cash,
    total_debt, revenue, receivables — used when available.
    """
    h = cfg.get("halal", {}) or {}
    extra = extra or {}
    reasons, ratios = [], {}

    blob = _txt(rec)

    # ── 1) Business activity (sector/industry/name only, word-boundary) ──
    for bad in h.get("sector_block", []):
        if bad and _has(blob, bad):
            return "fail", [f"non-compliant activity: '{bad}' in sector/industry"], ratios

    review_hit = None
    for warn in h.get("sector_review", []):
        if warn and _has(blob, warn):
            review_hit = warn
            reasons.append(f"activity needs human review: '{warn}'")
            break

    # ── 2) Financial ratios (AAOIFI-style, / market cap) ──────────
    mcap = rec.get("market_cap") or 0
    total_debt = extra.get("total_debt")
    if total_debt is None:
        total_debt = rec.get("total_debt")
    total_cash = extra.get("total_cash")
    if total_cash is None:
        total_cash = rec.get("total_cash")
    revenue = extra.get("revenue")
    if revenue is None:
        revenue = rec.get("revenue_ttm")
    receivables = extra.get("receivables")
    if receivables is None:
        receivables = rec.get("receivables")
    interest_income = extra.get("interest_income")   # FMP income statement provides this
    if interest_income is None:
        interest_income = rec.get("interest_income")

    if not mcap or mcap <= 0:
        reasons.append("market cap unavailable — cannot compute Sharia ratios")
        return "unknown", reasons, ratios

    debt_known = total_debt is not None
    if debt_known:
        dr = total_debt / mcap
        ratios["debt/marketcap"] = round(dr, 3)
        if dr >= h.get("debt_to_marketcap_max", 0.33):
            return "fail", [f"interest-bearing debt / market cap = {dr:.0%} ≥ "
                            f"{h.get('debt_to_marketcap_max', 0.33):.0%} (AAOIFI limit)"], ratios

    cash_known = total_cash is not None
    if cash_known:
        cr = total_cash / mcap
        ratios["cash+securities/marketcap"] = round(cr, 3)
        if cr >= h.get("cash_to_marketcap_max", 0.33):
            return "fail", [f"cash & interest-bearing securities / market cap = {cr:.0%} ≥ "
                            f"{h.get('cash_to_marketcap_max', 0.33):.0%} (AAOIFI limit)"], ratios

    if receivables is not None:
        rr = receivables / mcap
        ratios["receivables/marketcap"] = round(rr, 3)
        if rr >= h.get("receivables_to_marketcap_max", 0.49):
            return "fail", [f"receivables / market cap = {rr:.0%} ≥ "
                            f"{h.get('receivables_to_marketcap_max', 0.49):.0%} (AAOIFI limit)"], ratios

    # ── 3) Interest income / revenue (the < 5% purification test) ──
    income_known = (interest_income is not None and revenue not in (None, 0))
    if income_known:
        ir = interest_income / revenue
        ratios["interest_income/revenue"] = round(ir, 4)
        if ir >= h.get("interest_income_to_revenue_max", 0.05):
            return "fail", [f"interest income / revenue = {ir:.1%} ≥ "
                            f"{h.get('interest_income_to_revenue_max', 0.05):.0%} (purification limit)"], ratios

    # ── 4) Verdict (never guess) ──────────────────────────────────
    # PASS requires: clean activity + debt & cash ratios verified + interest-income verified.
    fully_verifiable = debt_known and cash_known and income_known and not review_hit
    if fully_verifiable:
        reasons.append("passes AAOIFI activity + financial ratios + interest-income screen")
        reasons.append("final confirmation still recommended on Zoya / Musaffa")
        return "pass", reasons, ratios

    # Otherwise we lack a required input (usually interest income on free data),
    # or sector needs review -> unknown, never a guessed pass.
    missing = []
    if not debt_known:
        missing.append("interest-bearing debt")
    if not cash_known:
        missing.append("cash & interest-bearing securities")
    if not income_known:
        missing.append("interest income / revenue")
    if missing:
        reasons.append("cannot verify: " + ", ".join(missing) +
                       " (free data gap) — confirm on Zoya / Musaffa")
    reasons.append("status held as 'unknown' rather than guessed")
    return "unknown", reasons, ratios


def apply(rec, cfg, extra=None, overrides=None):
    """Run the automatic screen, then honour your MANUAL verdict (Zoya/Musaffa)
    if one exists in data/halal_overrides.yaml — your verification wins, and we
    tag the source so the dashboard shows it's a human-verified call, not a guess."""
    status, reasons, ratios = screen(rec, cfg, extra=extra)
    rec["halal_source"] = "auto"
    ov = (overrides or {}).get(str(rec.get("ticker") or "").upper())
    if ov:
        auto = status
        status = ov["status"]
        rec["halal_source"] = f"manual:{ov['source']}"
        note = ov.get("note") or f"تجاوز يدوي من {ov['source']}"
        reasons = [f"✍️ تحقّق يدوي ({ov['source']}): {note}",
                   f"(الفلتر التلقائي كان: {auto})"]
    rec["halal_status"] = status
    rec["halal_reasons"] = reasons
    rec["halal_ratios"] = ratios
    return rec
