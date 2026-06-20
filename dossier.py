# -*- coding: utf-8 -*-
"""
dossier.py — يجهّز "ملف البحث" للمرحلة الثانية.

يطلّع كل أرقام القائمة القصيرة بشكل خام + أسئلة موجّهة، عشان كلود (أنا)
آخذها وأبحث كل شركة بحث عميق (عقود/منتج/أخبار/مخاطر) وأطلّع ٢-٣ صيدات
بأسلوب المازر مع السبب العميق. هذا اللي يخلّي النظام "أصدق من المازر":
الفلتر يحذف الرديء، والبحث البشري+الذكي يأكّد الباقي.
"""

import json


def build_dossier(shortlist, stats):
    L = []
    L.append("# 🔬 ملف البحث العميق (المرحلة الثانية) — للمعالجة بواسطة كلود")
    L.append(f"> فُحص {stats['examined']} | نجا {stats['survivors']} | المرشّحون {len(shortlist)}")
    L.append("")
    L.append("## التعليمات لكلود")
    L.append("لكل مرشّح أدناه، ابحث بحثاً نوعياً عميقاً (بحث ويب حديث):")
    L.append("1. **المحرّك:** ليش الإيرادات تنمو؟ منتج/عقد/اتجاه كبير (AI، فضاء، دواء…)?")
    L.append("2. **الميزة التنافسية:** ليش ما ينافسها أحد بسهولة؟ من المنافسون؟")
    L.append("3. **الأخبار آخر ٣ شهور:** عقود، أرباح، تنبيهات، بيع/شراء داخلي (insider).")
    L.append("4. **المخاطر الحقيقية:** تركيز عملاء، تنظيم، ديون، منافسة، تقييم.")
    L.append("5. **هل هي «صيد»؟** نمو مبكر لسه ما انفجر سعره، ولا فاتت الفرصة؟")
    L.append("6. **الشرعية:** أكّد على Zoya/Musaffa.")
    L.append("")
    L.append("ثم اختر **٢-٣ فقط** الأقوى، واكتبهم بأسلوب المازر (الخانات الثمانية) + فقرة «ليش هذا صيد».")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## بيانات المرشّحين (خام)")
    L.append("")
    for i, d in enumerate(shortlist, 1):
        L.append(f"### {i}. {d['ticker']} — {d['name']}")
        fields = {
            "القطاع/الصناعة": f"{d['sector']} / {d['industry']}",
            "القيمة السوقية": d["market_cap"],
            "السعر": d["price"],
            "الهدف المتوسط": d["target_mean"],
            "الصعود المتوقع": d["upside"],
            "نمو الإيرادات": d["rev_growth"],
            "نمو الأرباح": d["earn_growth"],
            "هامش الربح": d["profit_margin"],
            "P/E": d["pe"],
            "P/E المستقبلي": d["forward_pe"],
            "PEG": d["peg"],
            "الدين/الملكية %": d["debt_to_equity"],
            "عائد سنة": d["one_year_return"],
            "بيتا": d["beta"],
            "إجماع المحللين (1-5)": d["rec_mean"],
            "عدد المحللين": d["num_analysts"],
            "التوزيعات": d["div_yield"],
            "النقاط": d.get("score"),
            "الشرعية (مبدئي)": d.get("halal", {}).get("status"),
        }
        for k, v in fields.items():
            L.append(f"- **{k}:** {v}")
        wk = d.get("weaknesses") or []
        if wk:
            L.append(f"- **نقاط ضعف (كمّية):** {'، '.join(wk)}")
        if d.get("summary"):
            L.append(f"- **نبذة:** {d['summary'][:400]}")
        L.append("")
    return "\n".join(L)


def build_json(shortlist, stats):
    """نسخة JSON خفيفة لو حبيت تربطها ببرنامج ثاني."""
    out = {"stats": stats, "candidates": []}
    for d in shortlist:
        c = {k: v for k, v in d.items() if k != "_info"}
        out["candidates"].append(c)
    return json.dumps(out, ensure_ascii=False, indent=2)
