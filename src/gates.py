# -*- coding: utf-8 -*-
"""
gates.py — ONE shared investability layer used by main / dashboard / CSV / portfolio.

A name is "NOT INVESTABLE YET" when we cannot evaluate it reliably:
  * data quality: LOW confidence (stale), missing core data, missing valuation,
    invalid earnings date
  * hard gates (config.gates): too few analysts, target below price, bubble run-up,
    insane valuation

IMPORTANT (corrected from a wrong council suggestion): halal == "unknown" is NOT a
reason to mark a stock not-investable. On free data EVERY name is "unknown"
(interest income unverifiable) — excluding them would empty the product. `unknown`
means "verify halal first", not "exclude". Only halal == "fail" is disqualifying,
and that is handled by the action layer (Avoid). Your OWN holdings are never
filtered out — gates attach warnings, they don't hide what you own.
"""


def evaluate(rec, cfg, is_holding=False):
    g = cfg.get("gates", {}) or {}
    reasons = []

    # ── data quality ──
    if rec.get("confidence") == "LOW":
        reasons.append("بيانات قديمة/ناقصة (ثقة منخفضة)")
    if rec.get("price") is None or rec.get("market_cap") is None:
        reasons.append("بيانات أساسية ناقصة")
    if rec.get("forward_pe") is None and rec.get("pe") is None and rec.get("ev_ebitda") is None:
        reasons.append("تقييم ناقص")
    if rec.get("_earnings_invalid"):
        reasons.append("تاريخ أرباح غير صالح")

    # ── hard gates (config) ──
    na = rec.get("num_analysts")
    if na is not None and na < g.get("min_analysts", 4):
        reasons.append(f"تغطية محللين قليلة ({int(na)})")
    up = rec.get("analyst_upside_percent")
    if up is not None and up < g.get("upside_floor", -0.05):
        reasons.append(f"الهدف أقل من السعر ({up:+.0%})")
    oyr = rec.get("one_year_return")
    if oyr is not None and oyr > g.get("one_year_return_hard_max", 4.0):
        reasons.append(f"ارتفاع مبالغ ({oyr:+.0%}) — فقاعة")
    fpe = rec.get("forward_pe")
    if fpe is not None and fpe > g.get("pe_hard_max", 90.0):
        reasons.append(f"تقييم مجنون (P/E {fpe:.0f})")

    investable = len(reasons) == 0
    rec["investable"] = investable
    rec["not_investable_reasons"] = reasons
    rec["is_holding"] = is_holding
    return investable, reasons


def apply_all(records, cfg, holdings_set):
    for rec in records:
        evaluate(rec, cfg, is_holding=(rec.get("ticker") in holdings_set))
    return records
