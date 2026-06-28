"""
regime.py — الطبقة «العاقلة»: تقرأ وضع السوق من إشارات نحسبها أصلاً، ثم تُرشّح
أيّ وضعِ توزيعٍ موجود يناسب اللحظة. تستشعر الحاضر، ولا تتنبّأ بالغيب.

المدخلات (كلها موجودة على السجلّات / في meta — لا مصدر بيانات جديد، ولا شبكة):
  • market_risk            — Low / Medium / High / Extreme  (ضغط كلّي من الأخبار)
  • crowded_late / popular_not_cheap  — ازدحام / مطاردة متأخرة
  • forward_pe             — مستوى التقييم
  • action == "Candidate"  — اتّساع فرص الجودة الرخيصة

المخرَج: dict تعرضه الواجهة كرأسٍ هادئ + توصيةِ وضع. القرار يبقى للمستخدم
(يدوياً يقدر يتجاوز التوصية). نُعيد استخدام الأوضاع الثلاثة المُدقّقة — لا محرّك ميلٍ جديد.
"""

_RISK_RANK = {"low": 0, "medium": 1, "high": 2, "extreme": 3}

DISCLAIMER_AR = ("قراءة للحظة الحالية من إشاراتنا — ليست تنبؤاً بالغيب. "
                 "تُرشّح وضعاً، والقرار يبقى لك.")

# regime → أي وضعٍ *موجود* يستدعيه (نعيد استخدام التوزيعات المُدقّقة)
_MODE_FILE = {"conservative": "conservative.html", "balanced": "index.html",
              "aggressive": "aggressive.html"}
_MODE_AR = {"conservative": "محافظ", "balanced": "متوازن", "aggressive": "هجومي"}


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def detect(records, market_risk, cfg=None):
    """يرجّع قراءة وضع السوق + الوضع الموصى به. دفاعيّ ضدّ القيم الناقصة."""
    invest = [r for r in records
              if not r.get("is_fund")
              and r.get("investable", True)
              and r.get("action") != "Avoid"]
    n = len(invest) or 1

    crowded = sum(1 for r in invest if r.get("crowded_late") or r.get("popular_not_cheap"))
    crowd_pct = crowded / n

    fpes = [r.get("forward_pe") for r in invest
            if isinstance(r.get("forward_pe"), (int, float)) and 0 < r.get("forward_pe") < 200]
    med_fpe = _median(fpes)

    cands = sum(1 for r in invest if r.get("action") == "Candidate")
    cand_pct = cands / n

    risk_key = str(market_risk or "").strip().lower()
    risk_rank = _RISK_RANK.get(risk_key, 0)

    # ── قائمة الإشارات الشفّافة (اللي شفناها فعلاً) ──
    sig = []
    if risk_rank >= 2:
        sig.append("مخاطر السوق %s" % ("قصوى" if risk_rank >= 3 else "مرتفعة"))
    if crowd_pct >= 0.45:
        sig.append("ازدحام مرتفع — %d%% من الأسماء قرب القمم" % round(crowd_pct * 100))
    if med_fpe is not None and med_fpe >= 32:
        sig.append("تقييمات مرتفعة — وسيط P/E آجل %d" % round(med_fpe))
    if cand_pct >= 0.10:
        sig.append("فرص جودة وفيرة — %d%% مرشّحون رخيصون" % round(cand_pct * 100))
    if med_fpe is not None and med_fpe <= 18 and risk_rank <= 1:
        sig.append("السوق غير مكلف — وسيط P/E آجل %d" % round(med_fpe))

    # ── قرار النظام (الأولوية: حماية رأس المال أولاً) ──
    if risk_rank >= 3 or (risk_rank >= 2 and crowd_pct >= 0.40):
        regime, mode = "أزمة — وضع الدفاع", "conservative"
        why = ("ضغط كلّي مرتفع" + ("" if crowd_pct < 0.40 else " مع ازدحام")
               + " — احمِ رأس المال: كاش وذهب أعلى، وطارد أقل.")
    elif crowd_pct >= 0.50 and (med_fpe is not None and med_fpe >= 34):
        regime, mode = "فقاعة محتملة — حذر", "conservative"
        why = "ازدحام وتقييمات مرتفعة معاً — قلّل المطاردة ورجّح الجودة والحماية."
    elif risk_rank >= 2:
        regime, mode = "ضغط مرتفع — حذر دفاعي", "conservative"
        why = "مخاطر السوق مرتفعة (حتى بدون ازدحام واضح) — مِل للحماية وتمهّل في الإضافة."
    elif cand_pct >= 0.12 and risk_rank <= 1 and crowd_pct < 0.40:
        regime, mode = "فرصة — وضع الهجوم", "aggressive"
        why = "فرص جودة كثيرة ومخاطر معقولة — مِل للنمو والصيد، بحجمٍ مدروس."
    else:
        regime, mode = "طبيعي — توازن", "balanced"
        why = "لا تطرّف واضح في المخاطر ولا الازدحام ولا التقييم — التوازن الافتراضي يكفي."

    # الثقة = توافُق الإشارات. «الطبيعي» يكون أوثق كلّما قلّت الإشارات الصارخة.
    strong = len(sig)
    if mode == "balanced":
        conf = "HIGH" if strong == 0 else ("MED" if strong == 1 else "LOW")
    else:
        conf = "HIGH" if strong >= 3 else ("MED" if strong == 2 else "LOW")

    return {
        "regime": regime,
        "recommended_mode": mode,
        "recommended_mode_ar": _MODE_AR.get(mode, mode),
        "recommended_file": _MODE_FILE.get(mode, "index.html"),
        "confidence": conf,
        "why": why,
        "signals": sig,
        "metrics": {
            "market_risk": market_risk,
            "crowd_pct": round(crowd_pct, 3),
            "med_fwd_pe": round(med_fpe, 1) if med_fpe is not None else None,
            "candidate_pct": round(cand_pct, 3),
            "n": n,
        },
        "disclaimer": DISCLAIMER_AR,
    }
