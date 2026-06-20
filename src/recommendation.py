# -*- coding: utf-8 -*-
"""
recommendation.py — تقرير بحثي من 14 بند لكل سهم قوي (عربي).
يشمل: السبب في الظهور، درجة القناعة، السيناريوهات (متفائل/أساسي/متشائم)،
وأطروحة الخروج (ليش تملكه / وش يلغي الأطروحة / متى تقلّل القناعة).

بحث، وليس توصية. لا يقول «اشترِ الآن» ولا يعد بسعر.
"""


def _pct(x, plus=True):
    if not isinstance(x, (int, float)):
        return "—"
    return f"{x:+.0%}" if plus else f"{x:.0%}"


def _money(x):
    return f"${x:,.2f}" if isinstance(x, (int, float)) else "—"


def _cap(x):
    if not isinstance(x, (int, float)):
        return "—"
    return f"${x/1e9:.1f}B" if x >= 1e9 else f"${x/1e6:.0f}M"


def _num(x, d=1):
    return f"{x:.{d}f}" if isinstance(x, (int, float)) else "—"


HALAL_AR = {"pass": "✅ حلال مبدئياً", "unknown": "⚠️ غير مؤكّد — تأكّد على Zoya/Musaffa", "fail": "🔴 غير متوافق"}
ENGINE_AR = {"compounder": "مُركِّب طويل المدى 🏛️", "accelerator": "مُسرِّع 🚀", "future_leader": "قائد مستقبل 🌱"}
THEME_AR = {"ai": "ذكاء اصطناعي", "semiconductors": "أشباه موصلات", "data_centers": "مراكز بيانات",
            "cloud": "حوسبة سحابية", "cybersecurity": "أمن سيبراني", "robotics": "روبوتات",
            "defense_tech": "تقنية دفاع", "digital_health": "صحة رقمية",
            "energy_infrastructure": "بنية الطاقة", "critical_materials": "مواد حيوية", "space": "فضاء"}


def _why_appeared(rec):
    bits = []
    for e in (rec.get("engines") or []):
        bits.append(ENGINE_AR.get(e, e))
    n = rec.get("independent_confirmations", 0) or 0
    if n:
        bits.append(f"{n} مجموعة تأكيد مستقلة")
    if (rec.get("conviction_score") or 0) >= 8:
        bits.append(f"قناعة عالية {rec['conviction_score']}/10")
    if rec.get("lifecycle_status"):
        bits.append(f"الحالة: {rec['lifecycle_status']}")
    return "، ".join(bits) if bits else "نقاط أساس قوية في الفرز الكمّي"


def _growth_drivers(rec):
    d = []
    th = [THEME_AR.get(t, t) for t in (rec.get("themes") or [])]
    if th:
        d.append("ثيمات: " + "، ".join(th))
    if (rec.get("ai_exposure_score") or 0) >= 6:
        d.append(f"تعرّض قوي للـAI ({rec['ai_exposure_score']}/10)")
    if rec.get("rev_growth") is not None:
        d.append(f"نمو إيرادات {_pct(rec['rev_growth'])}")
    if rec.get("rev_cagr_3y") is not None and rec["rev_cagr_3y"] > 0.12:
        d.append(f"نمو مركّب 3 سنوات {_pct(rec['rev_cagr_3y'])}")
    if rec.get("fcf_margin") is not None and rec["fcf_margin"] > 0.10:
        d.append(f"تدفّق نقدي حر قوي {_pct(rec['fcf_margin'], plus=False)}")
    return "، ".join(d) if d else "تحتاج بحث أعمق للمحرّكات النوعية"


def _bull(rec):
    p = rec.get("bull_case_price")
    drv = []
    if rec.get("primary_theme"):
        drv.append(THEME_AR.get(rec["primary_theme"], rec["primary_theme"]))
    up = (p / rec["price"] - 1) if (p and rec.get("price")) else None
    return (f"لو النمو استمر وتوسّعت الهوامش والثيم ({'، '.join(drv) or 'النمو'}) ساند — "
            f"المدى المتفائل نحو {_money(p)}" + (f" (صعود {_pct(up)})" if up is not None else "") + ".")


def _base(rec):
    p = rec.get("base_case_price")
    up = rec.get("analyst_upside_percent")
    return (f"السيناريو المعقول: هدف المحللين المتوسط نحو {_money(p)}"
            + (f" (صعود {_pct(up)})" if up is not None else "") + "، بافتراض استمرار النمو الحالي.")


def _bear(rec):
    p = rec.get("bear_case_price")
    risk = (rec.get("weaknesses") or ["تباطؤ النمو"])[0]
    return (f"لو تباطأ النمو أو انكمش التقييم أو ضغط الماكرو (حرب/نفط/فائدة) — "
            f"المدى المتشائم نحو {_money(p)}. الخطر الأبرز: {risk}.")


def _exit_thesis(rec, cfg):
    th = cfg.get("thresholds", {}) or {}
    own = []
    if rec.get("conviction_score"):
        own.append(f"قناعة {rec['conviction_score']}/10")
    if rec.get("engines"):
        own.append("، ".join(ENGINE_AR.get(e, e) for e in rec["engines"]))
    own = " · ".join(own) or "نمو وجودة"
    invalidate = [
        f"النمو يتباطأ قطعين ربعيين متتاليين (تحت ~{th.get('revenue_growth_good', 0.18):.0%}).",
        "الهوامش تنكمش أو الدين يرتفع بشكل ملموس.",
        "هدف المحللين المتوسط ينزل تحت السعر مع خفض التقديرات.",
    ]
    if rec.get("halal_status") != "pass":
        invalidate.append("الحلال يطلع «غير متوافق» على Zoya/Musaffa — اخرج بغض النظر عن السعر.")
    reduce = [
        "درجة القناعة تنزل تحت 6.",
        "يفقد عضوية محرّكه (ما عاد مُركِّب/مُسرِّع/قائد).",
        f"التقييم يصير مجنون (P/E مستقبلي فوق ~{th.get('forward_pe_rich', 55):.0f}) بدون رفع أرباح.",
    ]
    return own, invalidate, reduce


def build(rec, cfg):
    L = []
    conv = rec.get("conviction_score")
    L.append(f"## {rec.get('name')} ({rec['ticker']}) — {rec.get('action')}"
             + (f" · قناعة {conv}/10" if conv is not None else ""))
    L.append(f"> القرار: **{rec.get('action')}** — {rec.get('action_reason')}")
    L.append("")
    L.append(f"**1) الشركة والنشاط:** {rec.get('sector') or '—'} / {rec.get('industry') or '—'} · القيمة السوقية {_cap(rec.get('market_cap'))}.")
    L.append(f"**2) رأي المحللين:** {rec.get('rec_key') or '—'}"
             + (f" (متوسط {_num(rec.get('rec_mean'),2)}/5، {int(rec['num_analysts'])} محلل)" if rec.get('num_analysts') else "") + ".")
    L.append(f"**3) السعر الحالي:** {_money(rec.get('price'))}.")
    L.append(f"**4) الأهداف السعرية:** متوسط {_money(rec.get('target_mean'))} · المدى {_money(rec.get('target_low'))} – {_money(rec.get('target_high'))} · القيمة العادلة (تقدير) {_money(rec.get('fair_value_estimate'))}.")
    L.append(f"**5) ليش ظهر؟** {_why_appeared(rec)}.")
    L.append(f"**6) محرّكات النمو:** {_growth_drivers(rec)}.")
    risks = list(rec.get("weaknesses") or [])
    if rec.get("risk_score") is not None:
        risks.insert(0, f"نقاط المخاطرة {_num(rec['risk_score'])}/100")
    L.append(f"**7) المخاطر:** {'؛ '.join(risks)}.")
    L.append(f"**8) التقييم:** P/E مستقبلي {_num(rec.get('forward_pe'),1)} · EV/EBITDA {_num(rec.get('ev_ebitda'),1)} · صعود للهدف {_pct(rec.get('analyst_upside_percent'))}.")
    L.append(f"**9) أفق الاستثمار:** {rec.get('suggested_holding_period') or '—'} (قصير 0–6ش · متوسط 6–18ش · طويل 18ش+).")
    L.append(f"**10) درجة القناعة:** {_num(conv) if conv is not None else '—'}/10 — {rec.get('conviction_tier') or '—'}.")
    L.append(f"**11) السيناريو المتفائل (Bull):** {_bull(rec)}")
    L.append(f"**12) السيناريو الأساسي (Base):** {_base(rec)}")
    L.append(f"**13) السيناريو المتشائم (Bear):** {_bear(rec)}")
    own, inval, reduce = _exit_thesis(rec, cfg)
    L.append(f"**14) أطروحة الخروج:**")
    L.append(f"   - **ليش تملكه:** {own}.")
    L.append(f"   - **وش يلغي الأطروحة:**")
    for x in inval:
        L.append(f"     • {x}")
    L.append(f"   - **متى تقلّل القناعة:**")
    for x in reduce:
        L.append(f"     • {x}")
    L.append(f"**الحلال:** {HALAL_AR.get(rec.get('halal_status'), '—')}.")
    L.append("")
    L.append("---")
    return "\n".join(L)


def build_report(records, cfg, market_risk="—"):
    from schema import now_local
    app_name = (cfg.get("app", {}) or {}).get("name", "مرصد الأسهم")
    off = (cfg.get("run", {}) or {}).get("qatar_utc_offset", 3)
    now = now_local(off)
    H = [
        f"# 📊 {app_name} — تقرير البحث (14 بند لكل سهم)",
        f"**التاريخ:** {now.strftime('%Y-%m-%d %H:%M')} (قطر) · **مخاطر السوق اليوم:** {market_risk}",
        "",
        "> بحث فقط — وليس نصيحة ولا توصية شراء ولا وعد بسعر. الحلال تقريبي؛ أكّد على Zoya/Musaffa. "
        "القرار والمسؤولية عليك وحدك.",
        "",
        "---",
        "",
    ]
    if not records:
        H.append("_لا يوجد سهم قوي بما يكفي للتقرير في هذا التشغيل._")
        return "\n".join(H)
    for rec in records:
        H.append(build(rec, cfg))
        H.append("")
    return "\n".join(H)
