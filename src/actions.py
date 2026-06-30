# -*- coding: utf-8 -*-
"""
actions.py — final action decision (spec §15 line 13).

Vocabulary (the ONLY allowed actions — there is no "BUY NOW"):
  Candidate / Research More / Watch / Verify Halal First / Avoid

Order of precedence (halal is a HARD gate):
  halal fail     -> Avoid  ("AVOID - fails Sharia screen")
  halal unknown  -> Verify Halal First
  halal pass:
    popular-not-cheap          -> Watch  (likely late entry)
    would-be Candidate + crowded/late -> Watch
    strong score + halal pass + acceptable risk + not crowded -> Candidate
      (downgraded to Research More if data confidence is LOW)
    decent score   -> Research More
    marginal score -> Watch
    weak score     -> Avoid (weak fundamentals / poor risk-reward)
"""


def compute(rec, cfg):
    out = cfg.get("output", {}) or {}
    cand_min = out.get("candidate_min_fundamental", 60)
    rm_min = out.get("research_more_min", 50)
    watch_min = out.get("watch_min", 40)

    hs = rec.get("halal_status")
    fund = rec.get("fundamental_score") or 0
    total = rec.get("total_score")
    total = total if total is not None else fund

    # ── funds/ETFs are a CORE HOLD, not a stock pick ──
    if rec.get("is_fund"):
        return "Watch", "صندوق/ETF — حيازة أساسية (core)، ليس سهماً نقيّمه فردياً"

    # ── halal: GATE (hide haram, verify unknown) OR INFO (rank by quality, you verify on Zoya) ──
    mode = ((cfg.get("halal", {}) or {}).get("mode") or "gate").lower()
    if mode != "info":
        if hs == "fail":
            reason = "AVOID - fails Sharia screen"
            if rec.get("halal_reasons"):
                reason += f" ({rec['halal_reasons'][0]})"
            return "Avoid", reason
        if hs == "unknown":
            return "Verify Halal First", (rec.get("halal_reasons") or
                                          ["halal status unverified — confirm on Zoya/Musaffa"])[0]
    # info mode: halal is shown as a flag (the dot), not a gate — quality decides the action below.

    # ── data quality gate: not-investable or suspect data can NEVER be a Candidate ──
    if not rec.get("investable", True):
        return "Watch", "بيانات غير كافية/مشكوكة — راجع قبل أي قرار (" + \
            ("؛ ".join(rec.get("not_investable_reasons") or []) or "بوابات البيانات") + ")"
    if rec.get("data_suspect"):
        return "Watch", "بيانات مشكوك فيها (" + ("؛ ".join(rec.get("data_suspect_reasons") or [])) + ") — تحقّق"

    # ── halal pass from here ──
    if rec.get("popular_not_cheap"):
        return "Watch", "POPULAR, NOT CHEAP - likely late entry, watch only"

    if rec.get("crowded_late") and fund >= cand_min:
        return "Watch", "CROWDED / LATE - strong company but near highs after a big run"

    if fund >= cand_min and total >= cand_min:   # crowded_late already returned at the check above
        if rec.get("confidence") == "LOW":
            return "Research More", "strong score but LOW data confidence — refresh data before acting"
        bits = []
        if rec.get("independent_confirmations", 0):
            bits.append(f"{rec['independent_confirmations']} confirmation group(s)")
        if rec.get("analyst_upside_percent") is not None:
            bits.append(f"{rec['analyst_upside_percent']:+.0%} to mean target")
        extra = f" ({'; '.join(bits)})" if bits else ""
        base_reason = ("جودة قوية + مخاطرة مقبولة — تأكّد الحلال على Zoya قبل الشراء"
                       if mode == "info" else "passes halal + strong fundamentals + acceptable risk-reward")
        return "Candidate", base_reason + extra

    if fund >= rm_min or total >= rm_min:
        return "Research More", "promising but not yet strong enough to be a Candidate"

    if total >= watch_min:
        return "Watch", "marginal — keep on the radar"

    return "Avoid", "weak fundamentals / poor risk-reward"


def apply(rec, cfg):
    action, reason = compute(rec, cfg)
    rec["action"] = action
    rec["action_reason"] = reason
    return rec
