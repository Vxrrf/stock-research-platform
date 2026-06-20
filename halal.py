# -*- coding: utf-8 -*-
"""
halal.py — فلترة شرعية تقريبية بمنهجية AAOIFI.

⚠️ مهم جداً: هذا فلتر *تقريبي* يساعدك تستبعد الواضح، ويرجّح المتوافق.
التأكيد النهائي إلزامي على Zoya أو Musaffa أو عالم موثوق — لأن:
  - "الدخل غير المتوافق < 5%" ما ينحسب آلياً من البيانات المجانية.
  - تصنيف النشاط أحياناً يحتاج نظر بشري.

النتيجة: PASS (يمر) / FLAG (يمر مع تنبيه راجعه) / FAIL (مستبعد).
"""

from config import HALAL, HALAL_SECTOR_BLOCK, HALAL_SECTOR_FLAG


def _txt(info, *keys):
    parts = []
    for k in keys:
        v = info.get(k)
        if v:
            parts.append(str(v).lower())
    return " ".join(parts)


def screen_halal(info):
    """
    يرجّع dict: {status, reasons[], ratios{}}
    status ∈ {"PASS", "FLAG", "FAIL"}
    """
    reasons = []
    ratios = {}

    blob = _txt(info, "sector", "industry", "longName", "shortName")

    # ── ١) فحص النشاط (القطاع/الصناعة) ──
    for bad in HALAL_SECTOR_BLOCK:
        if bad in blob:
            return {
                "status": "FAIL",
                "reasons": [f"نشاط غير متوافق: «{bad}» ظاهر في القطاع/الصناعة"],
                "ratios": ratios,
            }

    flagged_sector = None
    for warn in HALAL_SECTOR_FLAG:
        if warn in blob:
            flagged_sector = warn
            reasons.append(f"صناعة تحتاج مراجعة نشاط: «{warn}»")
            break

    # ── ٢) النِسب المالية (AAOIFI) ──
    mcap = info.get("marketCap") or 0
    total_debt = info.get("totalDebt") or 0
    total_cash = info.get("totalCash") or 0

    if mcap and mcap > 0:
        debt_ratio = total_debt / mcap
        cash_ratio = total_cash / mcap
        ratios["debt/marketcap"] = round(debt_ratio, 3)
        ratios["cash/marketcap"] = round(cash_ratio, 3)

        if debt_ratio >= HALAL["debt_to_marketcap_max"]:
            return {
                "status": "FAIL",
                "reasons": [f"الديون/القيمة السوقية = {debt_ratio:.0%} ≥ {HALAL['debt_to_marketcap_max']:.0%} (تجاوز حد AAOIFI)"],
                "ratios": ratios,
            }
        if cash_ratio >= HALAL["cash_to_marketcap_max"]:
            # النقد العالي مو "حرام" بالضرورة، بس قريب من حد التطهير → تنبيه
            reasons.append(f"النقد/القيمة السوقية = {cash_ratio:.0%} قريب/فوق حد {HALAL['cash_to_marketcap_max']:.0%} — راجع على Zoya")
    else:
        reasons.append("القيمة السوقية غير متوفرة — تعذّر حساب النِسب الشرعية")

    # ذمم مدينة (نادراً تتوفر في البيانات المجانية)
    recv = info.get("netReceivables") or info.get("totalReceivables")
    if recv and mcap:
        rr = recv / mcap
        ratios["receivables/marketcap"] = round(rr, 3)
        if rr >= HALAL["receivables_to_marketcap_max"]:
            reasons.append(f"الذمم المدينة/القيمة = {rr:.0%} فوق حد {HALAL['receivables_to_marketcap_max']:.0%} — راجع")

    # ── ٣) التنبيه الثابت ──
    reasons.append("تأكيد نهائي إلزامي: افحص الرمز على Zoya / Musaffa قبل أي شراء (الدخل المحرّم <5% ما ينحسب آلياً)")

    status = "FLAG" if (flagged_sector or len([r for r in reasons if 'راجع' in r or 'مراجعة' in r]) > 0) else "PASS"
    # نخلي الحالة الافتراضية FLAG دائماً احتياطاً (الفلتر تقريبي)
    if status == "PASS":
        status = "FLAG"
    return {"status": status, "reasons": reasons, "ratios": ratios}
