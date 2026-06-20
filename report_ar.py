# -*- coding: utf-8 -*-
"""
report_ar.py — يحوّل القائمة القصيرة إلى تقرير عربي بأسلوب المازر (الخانات الثمانية).

⚠️ هذا تقرير *كمّي آلي* (المرحلة الأولى): يلخّص الأرقام بأسلوب المازر.
   "البحث العميق" (لماذا هذا صيد؟ العقود، المنتج، الأخبار، المخاطر النوعية)
   تسوّيه أنت + كلود في المرحلة الثانية فوق هالأساس.
"""

from datetime import datetime, timezone, timedelta
from config import SETTINGS


def _q_now():
    tz = timezone(timedelta(hours=SETTINGS["qatar_utc_offset"]))
    return datetime.now(tz)


def pct(x, plus=True):
    if x is None:
        return "—"
    return f"{x:+.1%}" if plus else f"{x:.1%}"


def money(x):
    if x is None:
        return "—"
    return f"${x:,.2f}"


def cap(x):
    if x is None:
        return "—"
    if x >= 1e9:
        return f"${x/1e9:.1f}B"
    return f"${x/1e6:.0f}M"


def num(x, dec=0):
    if x is None:
        return "—"
    return f"{x:.{dec}f}"


def rec_ar(key, mean):
    m = {
        "strong_buy": "🟢 Strong Buy",
        "buy": "🟢 Buy",
        "hold": "🟡 Hold",
        "underperform": "🔴 Underperform",
        "sell": "🔴 Sell",
    }
    label = m.get((key or "").lower(), key or "—")
    if mean is not None:
        label += f" (متوسط {mean:.2f}/5)"
    return label


def halal_label(h):
    return {
        "PASS": "✅ مبدئياً متوافق",
        "FLAG": "⚠️ مبدئياً متوافق — راجعه",
        "FAIL": "🔴 غير متوافق",
    }.get((h or {}).get("status"), "—")


def stock_block(d, rank):
    """الخانات الثمانية لسهم واحد."""
    L = []
    L.append(f"## {rank}️⃣ {d['name']} ({d['ticker']})")
    L.append("")
    L.append(f"> **النشاط:** {d['sector']} — {d['industry']} | **القيمة السوقية:** {cap(d['market_cap'])}")
    L.append("")

    # ① الشركة
    summ = (d.get("summary") or "").strip()
    if summ:
        L.append(f"**① الشركة:** {summ[:280]}…")
        L.append("")

    # ② المحللون
    L.append(f"**② رأي المحللين:** {rec_ar(d['rec_key'], d['rec_mean'])} — "
             f"عدد المحللين: {num(d['num_analysts'])}")
    L.append("")

    # ③ السعر والهدف
    L.append(f"**③ السعر والهدف:** الحالي {money(d['price'])} | "
             f"الهدف المتوسط {money(d['target_mean'])} (صعود {pct(d['upside'])}) | "
             f"المدى {money(d['target_low'])} – {money(d['target_high'])}")
    if d["upside"] is not None and d["upside"] < 0:
        L.append("")
        L.append("> 🔴 **تنبيه (درس Marvell):** الهدف المتوسط *أقل* من السعر الحالي — حتى المحللون يتوقعون نزول. لا تطارد.")
    L.append("")

    # ④ الأرقام
    fpe = f" (المستقبلي {num(d['forward_pe'])})" if d["forward_pe"] else ""
    de = f"{num(d['debt_to_equity'])}%" if d["debt_to_equity"] is not None else "—"
    L.append(f"**④ نظرة على الأرقام:** نمو الإيرادات {pct(d['rev_growth'])} سنوياً | "
             f"هامش الربح {pct(d['profit_margin'], plus=False)} | "
             f"P/E {num(d['pe'])}{fpe} | الدين/الملكية {de}")
    L.append("")

    # ⑤ التوزيعات
    dy = d["div_yield"]
    L.append(f"**⑤ التوزيعات:** {pct(dy, plus=False) if dy else 'لا توزيعات تُذكر'}")
    L.append("")

    # ⑥ الأداء والمخاطرة
    L.append(f"**⑥ الأداء والمخاطرة:** عائد آخر سنة {pct(d['one_year_return'])} | "
             f"بيتا {num(d['beta'], 2)}")
    L.append("")

    # ⑦ الشرعية
    h = d.get("halal", {})
    L.append(f"**⑦ الشرعية:** {halal_label(h)}")
    for r in (h.get("reasons") or [])[:3]:
        L.append(f"   - {r}")
    L.append("")

    # ⑧ نقاط الضعف (الشفافية — أصدق من المازر)
    wk = d.get("weaknesses") or []
    if wk:
        L.append(f"**⑧ نقاط ضعف (بصراحة):** " + "، ".join(wk))
    else:
        L.append("**⑧ نقاط ضعف:** لا توجد نقطة ضعف بارزة في الأرقام ✅")
    L.append("")

    # ⑨ الخلاصة الكمية
    growth_w = "قوية" if (d["rev_growth"] or 0) > 0.30 else "جيدة"
    val_w = "معقول" if (d["pe"] or 99) < 35 else "مرتفع"
    cons_w = "قوي" if (d["rec_mean"] or 5) < 2 else "إيجابي"
    L.append(f"**⑨ الخلاصة (كمّية، نقاط {num(d.get('score'), 1)}/100):** "
             f"شركة نمو {growth_w}، تقييمها {val_w}، وإجماع المحللين {cons_w}. "
             f"⏳ تنتظر بحث كلود العميق (عقود/منتج/أخبار/مخاطر) قبل أي قرار.")
    L.append("")
    L.append("---")
    return "\n".join(L)


def build_report(shortlist, stats):
    now = _q_now()
    H = []
    H.append("# 🎯 تقرير المازر 2.0 — القائمة القصيرة")
    H.append(f"**التاريخ:** {now.strftime('%Y-%m-%d %H:%M')} (توقيت قطر)")
    H.append(f"**نطاق البحث:** فُحص {stats['examined']} سهم → نجا {stats['survivors']} → "
             f"أفضل {len(shortlist)} للبحث العميق")
    H.append("")
    H.append("> ⚠️ **تنويه:** فرز كمّي آلي بأسلوب المازر — مو توصية ولا تنبؤ. "
             "الأرقام صحيحة وقت السحب. الفلترة الشرعية تقريبية (أكّدها على Zoya/Musaffa). "
             "البحث العميق النوعي في المرحلة الثانية. القرار والمسؤولية عليك وحدك.")
    H.append("")
    H.append("---")
    H.append("")

    if not shortlist:
        H.append("**لا يوجد سهم نجا من الفلتر اليوم.** طبيعي — المعايير صارمة. "
                 "وسّع الكون (`universe.py`) أو خفّف معياراً في `config.py` وأعد التشغيل.")
        return "\n".join(H)

    # جدول ملخص
    H.append("## 📊 ملخص سريع")
    H.append("")
    H.append("| # | السهم | السعر | الهدف | الصعود | النمو | P/E | المحللون | الشرعية | النقاط |")
    H.append("|---|------|------|------|--------|------|-----|---------|---------|--------|")
    for i, d in enumerate(shortlist, 1):
        hs = {"PASS": "✅", "FLAG": "⚠️", "FAIL": "🔴"}.get(d.get("halal", {}).get("status"), "—")
        H.append(f"| {i} | **{d['ticker']}** | {money(d['price'])} | {money(d['target_mean'])} | "
                 f"{pct(d['upside'])} | {pct(d['rev_growth'])} | {num(d['pe'])} | "
                 f"{num(d['num_analysts'])} | {hs} | {num(d.get('score'), 1)} |")
    H.append("")
    H.append("---")
    H.append("")

    for i, d in enumerate(shortlist, 1):
        H.append(stock_block(d, i))
        H.append("")

    H.append("## 🔬 الخطوة التالية: البحث العميق (المرحلة الثانية)")
    H.append("افتح كلود واطلب: **«خذ القائمة القصيرة وابحث كل شركة بحث عميق — عقود، منتج، "
             "أخبار، مخاطر، ولماذا قد تكون صيداً — وطلّع لي ٢-٣ بأسلوب المازر مع السبب.»** "
             "الـ dossier جاهز في `reports/dossier_latest.md`.")
    return "\n".join(H)
