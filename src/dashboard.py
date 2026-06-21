# -*- coding: utf-8 -*-
"""
dashboard.py — لوحة عربية (RTL) سهلة للمبتدئ (spec §19).

كل مصطلح فيه علامة (؟) — تضغط عليها يطلع شرح: وش يعني + فايدته + مثال بسيط.
تعرض: المرشّحين، تأكّد من الحلال أولاً، مزدحم/متأخر، قائمتي، تجنّب، أعلى 20،
نموذج المحفظة، التعرّض (قطاع/ثيم/ذكاء/مخاطرة)، أثر الأخبار، النشاط السياسي،
وحالة نضارة البيانات. ملف واحد مستقل (CSS مدمج).
"""

import html
import json
from collections import Counter


def _h(x):
    return html.escape(str(x)) if x is not None else "—"


def _name_sub(ticker, name):
    """Show the company name ONLY when it differs from the ticker (kills 'NVDA NVDA')."""
    n = (name or "").strip()
    if not n or n.upper() == str(ticker or "").upper():
        return ""
    return f"<div class='dim sm'>{_h(n[:22])}</div>"


# ── الترجمات العربية للقيم ──
ACTION_AR = {
    "Candidate": "مرشّح قوي", "Research More": "ابحث أكثر", "Watch": "راقب",
    "Verify Halal First": "تأكّد من الحلال أولاً", "Avoid": "تجنّب",
}
HALAL_AR = {"pass": "حلال مبدئياً", "unknown": "غير مؤكّد", "fail": "غير متوافق"}
FRESH_AR = {"FRESH": "حديثة", "STALE": "قديمة", "MISSING": "ناقصة"}
CONF_AR = {"HIGH": "عالية", "MEDIUM": "متوسطة", "LOW": "منخفضة"}
THEME_AR = {
    "ai": "ذكاء اصطناعي", "semiconductors": "أشباه موصلات", "data_centers": "مراكز بيانات",
    "cloud": "حوسبة سحابية", "cybersecurity": "أمن سيبراني", "robotics": "روبوتات",
    "defense_tech": "تقنية دفاع", "digital_health": "صحة رقمية",
    "energy_infrastructure": "بنية الطاقة", "critical_materials": "مواد حيوية", "space": "فضاء",
}
RISK_AR = {"Low": "منخفضة", "Medium": "متوسطة", "High": "عالية", "Extreme": "قصوى"}

_ACTION_CLASS = {
    "Candidate": "a-cand", "Research More": "a-res", "Watch": "a-watch",
    "Verify Halal First": "a-verify", "Avoid": "a-avoid",
}
RATING_AR = {"strong_buy": "شراء قوي", "buy": "شراء", "hold": "محايد",
             "underperform": "ضعيف", "sell": "بيع"}
RATING_CLASS = {"strong_buy": "a-cand", "buy": "a-res", "hold": "a-watch",
                "underperform": "a-avoid", "sell": "a-avoid"}
HOLD_AR = {"short": "~6 شهور", "medium": "6–18 شهر", "long": "+18 شهر"}
_HALAL_CLASS = {"pass": "h-pass", "unknown": "h-unknown", "fail": "h-fail"}
_FRESH_CLASS = {"FRESH": "f-fresh", "STALE": "f-stale", "MISSING": "f-missing"}


# ════════════════════════════════════════════════════════════════════
#  القاموس — شرح كل مصطلح: t=المصطلح، w=وش يعني، b=الفايدة، e=مثال
# ════════════════════════════════════════════════════════════════════
GLOSSARY = {
    "total": {"t": "النقاط الكلية (0–100)",
              "w": "رقم واحد يلخّص قوة السهم: نقاط الأساس + إضافات (ثيم، تأكيدات، أرباح) ناقص العقوبات.",
              "b": "يخليك ترتّب مئات الأسهم بسرعة وتشوف الأقوى فوق.",
              "e": "سهم نقاطه 88 إجمالاً أقوى من سهم نقاطه 60."},
    "fund": {"t": "نقاط الأساس (جودة الشركة)",
             "w": "تقييم صحّة الشركة نفسها: نمو المبيعات، الأرباح، الديون، الهوامش، كفاءة الإدارة.",
             "b": "يقيس جودة الشركة الحقيقية بعيداً عن الضجّة والإعلام.",
             "e": "شركة تنمو 30% سنوياً بأرباح قوية وديون قليلة = نقاط أساس عالية."},
    "opp": {"t": "نقاط الفرصة (المكافأة المحتملة)",
            "w": "كم ممكن يرتفع السهم: الصعود المتوقع + النمو + ارتباطه بالـAI + مجال الصعود.",
            "b": "تشوف بسرعة وين احتمال الربح أكبر.",
            "e": "صعود متوقع كبير + نمو قوي + AI = فرصة عالية."},
    "risk": {"t": "نقاط المخاطرة (الخطر)",
             "w": "كم السهم خطر: تقييم غالي، ديون عالية، تذبذب، ارتفاع مبالغ، بيانات ناقصة. (أعلى = أخطر)",
             "b": "ينبّهك قبل لا تدخل سهم خطر حتى لو فرصته مغرية.",
             "e": "سهم طار 300% بسنة بتقييم مجنون = مخاطرة عالية."},
    "ai": {"t": "درجة الذكاء الاصطناعي (0–10)",
           "w": "قد ايش الشركة مرتبطة بموجة الـAI. 10=قلب البنية التحتية، 9=شرائح AI، 6=برمجيات AI، 0=لا علاقة.",
           "b": "تركّز على أقوى اتجاه في السوق حالياً.",
           "e": "10 = شركة تصنع المعالجات الي تشغّل الـAI؛ 0 = مطعم عادي."},
    "revg": {"t": "نمو الإيرادات (المبيعات)",
             "w": "كم زادت مبيعات الشركة مقارنة بالسنة الي قبل.",
             "b": "الشركة الي مبيعاتها تكبر = تتوسّع وتكسب حصة سوق.",
             "e": "‎+27% يعني باعت أكثر بـ27% عن السنة السابقة."},
    "fpe": {"t": "مكرّر الربحية المتوقع (Forward P/E)",
            "w": "سعر السهم مقسوم على أرباحه المتوقعة للسنة الجاية. كل ما قلّ = أرخص.",
            "b": "يبيّن لك هل السهم غالي أو رخيص مقابل أرباحه.",
            "e": "سهم P/E=15 أرخص من سهم P/E=80 لنفس النمو."},
    "upside": {"t": "الصعود المتوقع",
               "w": "الفرق بين السعر الحالي ومتوسط هدف المحللين.",
               "b": "تعرف كم يتوقّع الخبراء السهم يرتفع.",
               "e": "‎+30% يعني المحللون يشوفونه يرتفع 30% للهدف."},
    "conf_groups": {"t": "التأكيدات المستقلة",
                    "w": "كم مصدر مستقل يعجبه السهم — نحسب «مجموعات» مو قوائم: (ProPicks+AI) + المحللون + قائمتك.",
                    "b": "اتفاق عدة مصادر مختلفة = إشارة أقوى من مصدر واحد.",
                    "e": "3 = أعجب نماذج Investing + المحللين + قائمتك الشخصية."},
    "halal": {"t": "الحالة الشرعية",
              "w": "فلترة تقريبية: «حلال مبدئياً» / «غير مؤكّد» / «غير متوافق». ما نخمّن أبداً.",
              "b": "تحمي توافقك الشرعي قبل أي قرار.",
              "e": "«غير مؤكّد» = ما قدرنا نتحقق من دخل الفائدة، راجع Zoya/Musaffa. «غير متوافق» = تجنّبه."},
    "fresh": {"t": "نضارة البيانات + الثقة",
              "w": "قد ايش البيانات حديثة. سعر أقدم من 48 ساعة أو أساسيات قديمة → الثقة تنزل «منخفضة».",
              "b": "قرار على بيانات قديمة = خطر. هذا يخليك تثق بالرقم أو تحدّثه.",
              "e": "«حديثة + ثقة عالية» = اعتمد عليها؛ «قديمة» = شغّل النظام من جديد."},
    "action": {"t": "القرار (التوصية البحثية)",
               "w": "خلاصة وش تسوي: مرشّح قوي / ابحث أكثر / راقب / تأكّد من الحلال أولاً / تجنّب. ما فيه «اشترِ الآن».",
               "b": "يحوّل كل الأرقام لخطوة عملية واضحة.",
               "e": "«تأكّد من الحلال أولاً» = السهم قوي بس راجع شرعيته قبل أي شي."},
    "crowded": {"t": "مزدحم / متأخر",
                "w": "السهم طار كثير (+150% بسنة) وقريب من أعلى سعر له — غالباً فاتت الفرصة.",
                "b": "يحميك من الدخول المتأخر بعد ما يرتفع السهم.",
                "e": "سهم صعد 200% وهو على بُعد 5% من قمته = دخول متأخر."},
    "watchlist": {"t": "قائمتي",
                  "w": "أسهمك الـ19 الي اخترتها بنفسك ونتابعها لك كل تشغيل.",
                  "b": "تشوف حالة قناعاتك الشخصية بنظرة واحدة.",
                  "e": "MRVL, AMD, NOW... مع نقاطها وقرارها اليوم."},
    "theme": {"t": "الثيم (الاتجاه/القطاع)",
              "w": "على أي موجة الشركة: ذكاء اصطناعي، أشباه موصلات، صحة رقمية، فضاء...",
              "b": "تعرف على أي اتجاه كبير تراهن.",
              "e": "«مراكز بيانات» = شركات تبني البنية الي تشغّل الـAI."},
    "discoveries": {"t": "اكتشافات جديدة",
                    "w": "أسهم قوية لقاها النظام في السوق (حجم 1–100 مليار $) خارج قائمتك.",
                    "b": "يوسّع أفقك لفرص ما كنت تعرفها.",
                    "e": "النظام لقى GMED (أجهزة طبية تنمو 27%) ما كانت بقائمتك."},
    "portfolio": {"t": "نموذج المحفظة",
                  "w": "توزيع مقترح لمستثمر 25 سنة، نمو عالي مع حماية: 55% أسهم نمو، 20% مؤشر عام، 10% AI، 5% صحة، 5% ذهب، 5% كاش.",
                  "b": "يوزّع المخاطر بدل ما تحط كل فلوسك بسهم واحد.",
                  "e": "ذهب 5% يحميك وقت الأزمات؛ كاش 5% فرصة للشراء بالهبوط."},
    "exposure": {"t": "التعرّض (التوزيع)",
                 "w": "كم من المرشّحين في كل قطاع/ثيم، ومتوسط الذكاء والمخاطرة.",
                 "b": "تتأكد إنك مو كله مركّز بقطاع واحد.",
                 "e": "لو كل أسهمك «أشباه موصلات» = تركيز خطر بقطاع واحد."},
    "news": {"t": "أثر الأخبار",
             "w": "أحداث الاقتصاد الكبيرة (فائدة الفيدرالي، التضخم...) وتأثيرها. تحرّك النقاط 5% كحد أقصى.",
             "b": "تربط الصورة الكبيرة بالأسهم بدون مبالغة.",
             "e": "رفع الفيدرالي الفائدة = ضغط خفيف على أسهم النمو."},
    "political": {"t": "النشاط السياسي",
                  "w": "صفقات أعضاء الكونغرس الأمريكي على الأسهم. إشارة ضعيفة جداً فقط.",
                  "b": "معلومة جانبية للفضول — مو سبب للشراء أبداً.",
                  "e": "عضو كونغرس اشترى سهم ≠ السهم حلو؛ نعرضه كاهتمام فقط."},
    "top20": {"t": "أعلى 20 سهم",
              "w": "أقوى 20 سهم بالنقاط الكلية من كل الي فحصناهم اليوم.",
              "b": "نقطة بداية سريعة لأقوى الأسماء.",
              "e": "تبدأ بحثك العميق من هالـ20 بدل آلاف الأسهم."},
    "marketrisk": {"t": "مخاطر السوق اليوم",
                   "w": "حالة السوق العامة: منخفضة / متوسطة / عالية / قصوى — من الأحداث الاقتصادية.",
                   "b": "تعرف الجو العام قبل أي قرار.",
                   "e": "«قصوى» = يوم متقلّب، خفّف المخاطرة."},
    "conviction": {"t": "درجة القناعة (0–10)",
                   "w": "رقم واحد يقول قد ايش نثق بالشركة: جودة + نمو + محللين + تقييم + ميزانية + ملكية مؤسسية + ثبات الأرباح.",
                   "b": "يجمع كل الإشارات المهمة في رقم سهل بدل ما تطالع عشر أعمدة.",
                   "e": "9+ قناعة عالية جداً · 8+ مرشّح قوي · 6–8 ابحث أكثر · أقل من 6 راقب."},
    "compounder": {"t": "مُركِّب طويل المدى 🏛️",
                   "w": "شركة جودة عالية تنمو بثبات لسنوات: CAGR إيرادات >15%، ROIC عالي، هوامش وميزانية قوية.",
                   "b": "هذي الي تمسكها سنين وتتضاعف بهدوء — أساس الثروة.",
                   "e": "شركة تنمو 20% سنوياً بأرباح وعوائد قوية تدوم = مُركِّب."},
    "accelerator": {"t": "مُسرِّع (6–24 شهر) 🚀",
                    "w": "شركة نموها يتسارع: مبيعاتها الأخيرة أسرع من معدّلها، محللون إيجابيون، وأرباح تفوق التوقعات.",
                    "b": "فرص متوسطة المدى تُكتشف قبل الجميع — مو مضاربة يومية.",
                    "e": "شركة كانت تنمو 20% صارت 35% = تسارع، غالباً السعر يلحق."},
    "future_leader": {"t": "قائد المستقبل (صيد x3–x10) 🌱",
                      "w": "شركة صغيرة/متوسطة ($1–40 مليار) نمو قوي + هوامش حقيقية + ثيم مستقبلي، لسه ما انفجرت. بانضباط: مو قصة بلا إيرادات ولا طايرة +200%.",
                      "b": "هنا يجي الـ x5–x10 على سنوات — بحصة صغيرة لكل اسم عشان الخطر محدود.",
                      "e": "مثل SanDisk قبل ما تنفجر — نصطادها بدري ونوزّع الرهان."},
    "cyclical": {"t": "دوري / تحوّط 🔄",
                 "w": "شركة أرقامها تتبع سعر سلعة (ذهب، نفط، ذاكرة) — تطير وقت ارتفاع السعر وتنهار وقت نزوله. مو نمو دائم.",
                 "b": "تعرف إنها تحوّط أو فرصة مؤقتة، مو مضاعِف ثروة طويل المدى — فما نرتّبها فوق القادة الحقيقيين.",
                 "e": "AEM (ذهب): +66% نمو بسبب الحرب، يختفي لما يهدأ الذهب. تحوّط ممتاز، لكنه ليس AVGO."},
    "better": {"t": "بديل أفضل؟",
               "w": "هل فيه سهم يسوّي نفس دور سهمك (نفس الفئة) لكن أقوى — ترتيب أعلى بوضوح + قناعة أعلى + حلال مو أسوأ؟",
               "b": "ما نخليك تتمسّك بسهم وفيه أفضل منه يعطي عائد أحسن — بس نقترح **فقط لما نكون واثقين**.",
               "e": "«✓ الأفضل في دوره» = احتفظ، ما فيه أحسن. «↑ XYZ» = فيه أقوى منه، ابحثه."},
    "signals": {"t": "إشارات المؤثرين",
                "w": "أسهم ذكرها مستثمرون تتابعهم (joe.investss وغيره). كلود يقرا منشوراتهم لما تطلب، ويطلّع الأسهم.",
                "b": "تستفيد من أفكارهم — بس بانضباط: كل سهم يُفحص على منصّتك قبل ما يصير قرار.",
                "e": "مؤثر ذكر سهم → نشوف قناعتنا فيه وحلاله قبل أي شي. إشارة ضعيفة، مو توصية."},
    "rating": {"t": "تقييم المحللين",
               "w": "خلاصة رأي محللي وول ستريت: شراء قوي / شراء / محايد / ضعيف / بيع، مع المتوسط (من 5) وعدد المحللين.",
               "b": "تشوف بسرعة هل الخبراء متحمّسين للسهم — كل المنصّة تعرض كل التقييمات، مو بس «شراء قوي».",
               "e": "«شراء قوي 1.4/5 · 45 محلل» = إجماع قوي جداً مثل AVGO."},
    "hold": {"t": "مدة الاحتفاظ المقترحة",
             "w": "تقدير لأفق السهم: ~6 شهور أو أقل / 6–18 شهر / +18 شهر — حسب متانة النمو والمخاطرة.",
             "b": "تعرف هل هو فرصة قصيرة، متوسطة، أو مُركِّب طويل تمسكه سنين.",
             "e": "مُركِّب جودة (NVDA) = +18 شهر؛ اسم دوري متعافٍ = ~6 شهور."},
    "notinv": {"t": "غير قابل للاستثمار بعد",
               "w": "أسهم ما نقدر نقيّمها بثقة: بيانات قديمة/ناقصة، تقييم ناقص، تاريخ أرباح غير صالح، أو تغطية محللين قليلة.",
               "b": "نفصلها عن المرشّحين عشان ما تبني قرار على بيانات ضعيفة. (مو «حرام» — بس ناقصة بيانات).",
               "e": "سهم بياناته أقدم من 48 ساعة أو أقل من 4 محللين → هنا لين تتحدّث."},
    "institutional": {"t": "الملكية المؤسسية",
                      "w": "نسبة أسهم الشركة المملوكة لمؤسسات كبيرة (صناديق). مال حقيقي، مو ضجّة سوشال ميديا.",
                      "b": "دخول المؤسسات إشارة أقوى وأصدق من حماس تويتر.",
                      "e": "⚠️ نعرض النسبة الحالية فقط؛ «اتجاه التجميع» (زيادة/نقص) يحتاج FMP مدفوع."},
    "modes": {"t": "أوضاع المستثمر (محافظ/متوازن/هجومي)",
              "w": "نفس البيانات، عدسة مختلفة. يغيّر أوزان الترتيب وتوزيع المحفظة: «هجومي» يرفع وزن الفرصة والصيد x5–x10، «محافظ» يرفع الجودة وانخفاض المخاطرة والحماية.",
              "b": "ترتّب نفس الأسهم حسب شخصيتك الاستثمارية بدون ما تغيّر أي بيانات.",
              "e": "بدّل من الأزرار فوق: «هجومي» يطلّع قادة المستقبل فوق؛ «محافظ» يطلّع المُركِّبين والذهب."},
    "movers": {"t": "أبرز التغيّرات (ليش تغيّر الترتيب؟)",
               "w": "أكثر الأسهم تحرّكاً في الترتيب من آخر تشغيل، مع السبب الرئيسي: هل القناعة ارتفعت؟ المخاطرة نزلت؟ الفرصة تحسّنت؟",
               "b": "ما تشوف رقم يتغيّر بدون تفسير — تعرف ليش صعد أو نزل سهم.",
               "e": "«AMD ▲ القناعة ارتفعت» = تحسّنت جودته/نموه فصعد ترتيبه."},
    "backtest": {"t": "اختبار بأثر رجعي (Backtest)",
                 "w": "نأخذ أقوى أسهمك اليوم ونشوف كيف كان أداؤها لو امتلكتها آخر ~3 سنوات، مقابل مؤشر SPY.",
                 "b": "مؤشر تعقّل: هل ترتيبنا يميل لأسماء أدّت كويس؟ — لكنه ليس إثباتاً.",
                 "e": "⚠️ فيه انحياز نظر للأمام (اخترناها ببيانات اليوم) وانحياز ناجين — اقرأ التحذيرات تحت الجدول."},
    "bottleneck": {"t": "عنق الزجاجة (Bottleneck)",
                   "w": "العنصر النادر في سلسلة ما، اللي الكل محتاجه ومحد يقدر يوفّره بسهولة. مالكه (chokepoint) يكسب أكثر من المزاحم. العنق ينتقل في السلسلة مع الوقت.",
                   "b": "تصطاد المرحلة القادمة من الموجة قبل ما ينفجر سعرها — بدل ما تطارد الفائز بعد ما طار.",
                   "e": "AI: العنق انتقل من الشرائح (NVDA) → للكهرباء (نووي مثل CEG) → للذاكرة (HBM). من يملك الكهرباء الحين يكسب."},
    "fair": {"t": "القيمة العادلة (تقاطُع المصادر)",
             "w": "تقدير تقريبي لقيمة السهم من ٣ مصادر مستقلة: إعادة تسعير مكرّر الربحية + DCF مبسّط + هدف المحللين. نأخذ المتّفق منها فقط.",
             "b": "تعرف هل السعر الحالي رخيص أو غالي مقابل تقدير متعدّد المصادر — مو مصدر واحد.",
             "e": "لو الثلاثة قريبين = ثقة أعلى بالتقدير؛ لو متباينين = نقول «غير موثوق» بدل ما نخترع رقم."},
}

ENGINE_AR = {"compounder": "🏛️ مُركِّب", "accelerator": "🚀 مُسرِّع", "future_leader": "🌱 قائد قادم"}
ENGINE_CLASS = {"compounder": "e-comp", "accelerator": "e-accel", "future_leader": "e-future"}


def _i(key):
    """علامة (؟) قابلة للضغط تفتح شرح المصطلح."""
    return f'<span class="i" onclick="g(\'{key}\')" title="اضغط للشرح">؟</span>'


def _chip(text, cls):
    return f'<span class="chip {cls}">{_h(text)}</span>'


def _bar(val, kind="good"):
    """شريط بصري بدل الرقم المجرّد. kind: good (أخضر/أزرق) أو risk (أخضر→أحمر)."""
    if not isinstance(val, (int, float)):
        return "<span class='dim'>—</span>"
    v = max(0.0, min(100.0, float(val)))
    if kind == "risk":            # أعلى = أسوأ
        col = "#5ee7a0" if v < 40 else ("#e8cf5a" if v < 65 else "#ff7a8a")
    else:                          # أعلى = أفضل
        col = "#5ee7a0" if v >= 70 else ("#6cc4ff" if v >= 55 else "#8b97a8")
    return (f"<div class='sbwrap'><div class='sb'><i style='width:{v:.0f}%;background:{col}'></i></div>"
            f"<b class='n'>{val:.0f}</b></div>")


def _convbar(s):
    """شريط القناعة 0–10 — الرقم الرئيسي."""
    if not isinstance(s, (int, float)):
        return "<span class='dim'>—</span>"
    w = max(0, min(10, s)) * 10
    col = "#5ee7a0" if s >= 8 else ("#6cc4ff" if s >= 6 else "#8b97a8")
    return (f"<div class='sbwrap'><div class='sb sb-lg'><i style='width:{w:.0f}%;background:{col}'></i></div>"
            f"<b class='n' style='font-size:13.5px'>{s:.1f}</b></div>")


def _engine_badges(rec):
    out = ""
    if rec.get("cyclical"):
        out += "<span class='ebadge e-cyc'>🔄 دوري/تحوّط</span>"
    out += "".join(f"<span class='ebadge {ENGINE_CLASS.get(e,'')}'>{ENGINE_AR.get(e,e)}</span>"
                   for e in (rec.get("engines") or []))
    # merge the bottleneck lens INTO research: flag stocks that OWN a live bottleneck
    if rec.get("bottleneck_owner"):
        chains = rec.get("bottlenecks") or []
        tip = "؛ ".join(dict.fromkeys(t.get("chain", "") for t in chains if t.get("role") == "chokepoint"))
        out += f"<span class='ebadge e-bn' title='مالك عنق زجاجة: {_h(tip)}'>🔑 عنق</span>"
    return out


def _pctc(x):
    """نسبة ملوّنة: أخضر موجب، أحمر سالب."""
    if not isinstance(x, (int, float)):
        return "<span class='dim'>—</span>"
    col = "#5ee7a0" if x > 0.001 else ("#ff8a9a" if x < -0.001 else "#9fb0c6")
    return f"<span class='n' style='color:{col};font-weight:700'>{x:+.0%}</span>"


def _rating_cell(r):
    k = r.get("rec_key")
    if not k:
        return "<span class='dim'>—</span>"
    m = r.get("rec_mean")
    n = r.get("num_analysts")
    sub = []
    if m:
        sub.append(f"{m:.1f}/5")
    if n:
        sub.append(f"{int(n)} محلل")
    s = (" · ".join(sub))
    return (_chip(RATING_AR.get(k, k), RATING_CLASS.get(k, ""))
            + (f"<div class='dim sm n'>{s}</div>" if s else ""))


def _stock_rows(records):
    out = []
    for i, r in enumerate(records, 1):
        act = r.get("action")
        hal = r.get("halal_status")
        fr = r.get("data_freshness_status")
        theme = r.get("primary_theme")
        theme_chip = (f"<span class='tchip'>{_h(THEME_AR.get(theme, theme))}</span>" if theme else "")
        hsrc = r.get("halal_source") or "auto"
        hsrc_badge = (f"<div class='dim sm' style='color:#7fd0ff'>✍️ {_h(hsrc.split(':', 1)[1])}</div>"
                      if hsrc.startswith("manual") else "")
        out.append(
            "<tr>"
            f"<td class='dim'>{i}</td>"
            f"<td><b class='n'>{_h(r.get('ticker'))}</b>{_name_sub(r.get('ticker'), r.get('name'))}{theme_chip}{_engine_badges(r)}</td>"
            f"<td>{_chip(ACTION_AR.get(act, act), _ACTION_CLASS.get(act,''))}</td>"
            f"<td>{_convbar(r.get('conviction_score'))}</td>"
            f"<td>{_bar(r.get('risk_score'), 'risk')}</td>"
            f"<td>{_rating_cell(r)}</td>"
            f"<td class='r'>{_pctc(r.get('analyst_upside_percent'))}</td>"
            f"<td class='r'>{_pctc(r.get('rev_growth'))}</td>"
            f"<td class='dim sm n'>{('~'+str(r.get('suggested_hold_months'))+' شهر') if r.get('suggested_hold_months') else '—'}</td>"
            f"<td>{_chip(HALAL_AR.get(hal, hal), _HALAL_CLASS.get(hal,''))}{hsrc_badge}</td>"
            f"<td>{_chip(FRESH_AR.get(fr, fr), _FRESH_CLASS.get(fr,''))}"
            f"<div class='dim sm'>{_h(CONF_AR.get(r.get('confidence'), r.get('confidence')))}</div></td>"
            "</tr>"
        )
    return "\n".join(out)


def _thead():
    return (
        "<thead><tr>"
        "<th>#</th><th>السهم</th>"
        f"<th>القرار {_i('action')}</th>"
        f"<th>القناعة {_i('conviction')}</th>"
        f"<th>المخاطرة {_i('risk')}</th>"
        f"<th>التقييم {_i('rating')}</th>"
        f"<th>الصعود {_i('upside')}</th>"
        f"<th>النمو {_i('revg')}</th>"
        f"<th>مدة الاحتفاظ {_i('hold')}</th>"
        f"<th>الحلال {_i('halal')}</th>"
        f"<th>البيانات {_i('fresh')}</th>"
        "</tr></thead>"
    )


def _section_table(emoji, title, info_key, records, subtitle="", limit=12, sid=""):
    badge = _i(info_key) if info_key else ""
    total = len(records)
    shown = records[:limit]
    if not shown:
        body = "<p class='dim'>لا يوجد في هذا التشغيل.</p>"
    else:
        body = (f"<div class='tablewrap'><table class='stocktbl'>{_thead()}"
                f"<tbody>{_stock_rows(shown)}</tbody></table></div>")
        if total > limit:
            subtitle = (subtitle + f" — يُعرض أقوى {limit} من {total} (الباقي في الملف).").strip(" —")
    sub = f"<div class='dim sub2'>{_h(subtitle)}</div>" if subtitle else ""
    idattr = f" id='{sid}'" if sid else ""
    count = f"{len(shown)}/{total}" if total > limit else str(total)
    return (f"<section{idattr}><h2>{emoji} {_h(title)} {badge} "
            f"<span class='count n'>{count}</span></h2>{sub}{body}</section>")


def _today_card(lines):
    """The 'what do I do today' card — the answer in 3-5 lines at the very top."""
    if not lines:
        return ""
    items = "".join(f"<div class='today-row'><span class='te'>{e}</span><div>{t}</div></div>"
                    for e, t in lines)
    return ("<section id='s-today'><div class='today'>"
            "<div class='today-h'>📌 اليوم — وش أسوّي؟</div>" + items + "</div></section>")


def _exposure(records):
    cand = [r for r in records if r.get("action") in ("Candidate", "Research More", "Watch", "Verify Halal First")]
    sectors = Counter((r.get("sector") or "—") for r in cand)
    themes = Counter(THEME_AR.get(t, t) for r in cand for t in (r.get("themes") or []))
    ai_vals = [r.get("ai_exposure_score", 0) or 0 for r in cand]
    risks = [r.get("risk_score") for r in cand if r.get("risk_score") is not None]
    avg_ai = sum(ai_vals) / len(ai_vals) if ai_vals else 0
    avg_risk = sum(risks) / len(risks) if risks else 0
    high_risk = sum(1 for x in risks if x >= 65)

    def bars(counter, n=8):
        if not counter:
            return "<p class='dim'>—</p>"
        mx = max(counter.values())
        rows = []
        for k, v in counter.most_common(n):
            w = int(100 * v / mx)
            rows.append(f"<div class='bar'><span>{_h(k)}</span>"
                        f"<div class='track'><i style='width:{w}%'></i></div><b class='n'>{v}</b></div>")
        return "".join(rows)

    return f"""
    <section><h2>📈 التعرّض (التوزيع) {_i('exposure')}</h2>
    <div class="grid3">
      <div class="card"><h3>حسب القطاع</h3>{bars(sectors)}</div>
      <div class="card"><h3>حسب الثيم</h3>{bars(themes)}</div>
      <div class="card"><h3>الذكاء والمخاطرة</h3>
        <div class="metric"><b class='n'>{avg_ai:.1f}</b><span>متوسط الذكاء الاصطناعي /10</span></div>
        <div class="metric"><b class='n'>{avg_risk:.0f}</b><span>متوسط المخاطرة /100</span></div>
        <div class="metric"><b class='n'>{high_risk}</b><span>أسهم عالية المخاطرة (≥65)</span></div>
      </div>
    </div></section>"""


def _portfolio(rows):
    body = "".join(
        f"<tr><td>{_h(r['bucket'])}</td><td class='r'><b class='n'>{_h(r['allocation_pct'])}</b></td>"
        f"<td class='n' dir='ltr'>{_h(r['suggested_holdings'])}</td><td class='dim'>{_h(r['notes'])}</td></tr>"
        for r in rows
    )
    return (f"<section><h2>💼 نموذج المحفظة {_i('portfolio')}</h2><div class='tablewrap'><table>"
            "<thead><tr><th>الفئة</th><th>النسبة</th><th>أسهم مقترحة</th><th>ملاحظات</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div></section>")


def _news(rows):
    if not rows:
        return f"<section><h2>📰 أثر الأخبار {_i('news')}</h2><p class='dim'>لا توجد أحداث محمّلة.</p></section>"
    dir_ar = {"positive": "إيجابي", "negative": "سلبي", "neutral": "محايد"}
    body = "".join(
        f"<tr><td>{_h(r['event_name'])}</td><td class='n'>{_h(r['date'])}</td>"
        f"<td class='r n'>{_h(r['impact_score'])}</td>"
        f"<td>{_chip(dir_ar.get(r['impact_direction'], r['impact_direction']), 'dir-'+str(r['impact_direction']))}</td></tr>"
        for r in rows
    )
    return (f"<section><h2>📰 أثر الأخبار {_i('news')}</h2>"
            "<div class='dim sub2'>⚠️ <b>أحداث يدوية</b> (تُحدّث يدوياً في data/news_events.yaml حسب تاريخ كل حدث) — "
            "وليست بثّاً حياً لحظياً. «مخاطر السوق اليوم» مشتقّة من هذي الأحداث اليدوية. "
            "للأخبار الحيّة العميقة اطلب من كلود «حدّث الأخبار».</div>"
            "<div class='tablewrap'><table>"
            "<thead><tr><th>الحدث</th><th>التاريخ</th><th>الأثر/10</th><th>الاتجاه</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div></section>")


def _signals_section(rows):
    head = (f"<section id='s-signals'><h2>📡 إشارات المؤثرين {_i('signals')} "
            f"<span class='count n'>{len(rows)}</span></h2>"
            "<div class='dim sub2'>أسهم ذكرها مؤثرون تتابعهم — <b>إشارة ضعيفة للمراجعة فقط</b>، وكل سهم مفحوص على منصّتك قبل أي قرار. "
            "اطلب من كلود «شوف المؤثرين» يجيب آخر منشوراتهم.</div>")
    if not rows:
        return head + "<p class='dim'>لا توجد إشارات بعد — قول لكلود «شوف المؤثرين» يفحص حساباتهم.</p></section>"
    body = ""
    for r in rows[:30]:
        body += (f"<tr><td><b class='n'>{_h(r.get('ticker'))}</b></td>"
                 f"<td class='dim'>{_h(r.get('account'))}<div class='dim sm n'>{_h(r.get('date'))}</div></td>"
                 f"<td>{_h(r.get('sentiment'))}</td>"
                 f"<td><b>{_h(r.get('platform_fit'))}</b><div class='dim sm'>{_h((r.get('note') or '')[:60])}</div></td></tr>")
    return (head + "<div class='tablewrap'><table><thead><tr><th>السهم</th><th>المصدر</th><th>الرأي</th>"
            "<th>هل يتوافق مع منصّتك؟</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div></section>")


def _not_investable_section(records, limit=20):
    if not records:
        return ""
    body = ""
    for r in records[:limit]:
        reasons = "، ".join(r.get("not_investable_reasons") or [])
        body += (f"<tr><td><b class='n'>{_h(r.get('ticker'))}</b>{_name_sub(r.get('ticker'), r.get('name'))}</td>"
                 f"<td class='dim'>{_h(reasons)}</td>"
                 f"<td>{_chip(FRESH_AR.get(r.get('data_freshness_status'), r.get('data_freshness_status')), _FRESH_CLASS.get(r.get('data_freshness_status'),''))}</td></tr>")
    return (f"<section><h2>🚫 غير قابل للاستثمار بعد {_i('notinv')} <span class='count n'>{len(records)}</span></h2>"
            "<div class='dim sub2'>بيانات ناقصة/قديمة أو بوابات صارمة لم تُستوفَ — مفصولة عن المرشّحين (ليست محرّمة، بل غير مكتملة البيانات).</div>"
            "<div class='tablewrap'><table><thead><tr><th>السهم</th><th>السبب</th><th>البيانات</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div></section>")


def _holdings_section(rows):
    head = ("<section id='s-hold'><h2>💼 محفظتي — أضِف / احتفظ / بيع</h2>"
            "<div class='dim sub2'>توصية بحثية حسب الأداء والقناعة — مو «بيع/اشترِ الآن». «بديل أفضل» يظهر فقط لما نكون واثقين. "
            "عبّي أسعار/تواريخ شرائك في data/holdings.csv.</div>")
    if not rows:
        return head + ("<p class='dim'>لا توجد محفظة محمّلة — عبّي أسهمك في "
                       "<b>data/holdings.csv</b> (التذكرة، سعر الشراء، النسبة، تاريخ الشراء).</p></section>")
    body = ""
    for r in rows:
        if r.get("pnl_suspect"):
            pnl = "<span class='chip f-stale'>⚠️ سعر مشكوك</span>"
        elif r.get("pnl") is not None:
            pnl = f"<span class='n' style='color:{'#5ee7a0' if r['pnl']>=0 else '#ff8a9a'}'>{r['pnl']:+.0%}</span>"
        else:
            pnl = "<span class='dim'>—</span>"
        conv = _convbar(r.get("conviction")) if r.get("conviction") is not None else "<span class='dim'>—</span>"
        hold = _h(r.get("hold_label") or "—")
        b = r.get("better")
        better = (f"<b style='color:#f0b46b'>↑ {_h(b['ticker'])}</b><div class='dim sm'>{_h(b['why'])}</div>"
                  if b else "<span class='dim sm'>✓ الأفضل في دوره</span>")
        body += (f"<tr><td><b class='n'>{_h(r['ticker'])}</b>{_name_sub(r['ticker'], r.get('name'))}</td>"
                 f"<td><b>{_h(r['verdict'])}</b><div class='dim sm'>{_h(r.get('why'))}</div></td>"
                 f"<td>{conv}</td><td class='r'>{pnl}</td>"
                 f"<td class='dim sm'>{hold}</td>"
                 f"<td>{better}</td></tr>")
    return (head + "<div class='tablewrap'><table class='holdtbl'><thead><tr><th>السهم</th><th>التوصية</th><th>القناعة</th><th>ربح/خسارة</th>"
            f"<th>مدة الاحتفاظ {_i('hold')}</th><th>بديل أفضل؟ {_i('better')}</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div></section>")


def _political(rows):
    if not rows:
        return (f"<section><h2>🏛️ النشاط السياسي {_i('political')} <span class='count'>0</span></h2>"
                "<p class='dim'>لا توجد صفقات كونغرس حديثة لهذه الأسهم (إشارة ضعيفة فقط — ليست توصية).</p></section>")
    body = "".join(
        f"<tr><td>{_h(r['politician_name'])}</td><td><b class='n'>{_h(r['ticker'])}</b></td>"
        f"<td>{_h(r['transaction_type'])}</td><td class='n'>{_h(r['transaction_date'])}</td>"
        f"<td class='n'>{_h(r['estimated_value'])}</td></tr>"
        for r in rows[:40]
    )
    return (f"<section><h2>🏛️ النشاط السياسي {_i('political')} <span class='count n'>{len(rows)}</span></h2>"
            "<div class='dim sub2'>إشارة ضعيفة فقط — اهتمام سياسي، وليست أساس قرار استثماري.</div>"
            "<div class='tablewrap'><table>"
            "<thead><tr><th>السياسي</th><th>السهم</th><th>النوع</th><th>التاريخ</th><th>القيمة</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div></section>")


_BN_STATUS = {"acute": ("🔴 عنق حاد الآن", "bn-acute"), "building": ("🟠 قادم يتشكّل", "bn-build"),
              "easing": ("🟢 خفّ (كان عنق)", "bn-ease"), "speculative": ("🔵 مضاربي بعيد", "bn-spec")}
_BN_PROB = {"high": "مرجّح هيكلياً", "med": "محتمل", "low": "مضاربي"}
_BN_CONF = {"high": "ثقة عالية بالأطروحة", "med": "ثقة متوسطة"}


def _bn_chip(t):
    sym, role = t.get("sym"), t.get("role")
    hal, cov = t.get("halal"), t.get("covered")
    icon = "🔑 " if role == "chokepoint" else ("🌱 " if role == "early" else "")
    if not cov:
        cls = "bnc-out"          # خارج نطاقنا / غير محمّل هالتشغيل
    elif hal == "fail":
        cls = "bnc-fail"
    elif hal == "pass":
        cls = "bnc-pass"
    else:
        cls = "bnc-unk"
    conv = t.get("conviction")
    cv = f"<b class='n'> {conv:.0f}</b>" if (cov and conv is not None) else ""
    fail_mark = " ✗" if (cov and hal == "fail") else ""
    key = " bnc-key" if role == "chokepoint" else ""
    return f"<span class='bnc {cls}{key}' dir='ltr'>{icon}{_h(sym)}{cv}{fail_mark}</span>"


def _bottleneck_section(chains):
    head = (f"<section id='s-bn'><h2>🔗 عنق الزجاجة عبر القطاعات {_i('bottleneck')}</h2>"
            "<div class='note' style='border-color:#5e4420;background:#231a10;color:#f0c89a'>"
            "⚠️ <b>تحليل منطقي حتى مطلع 2026 — احتمالات مرجّحة، مو نبوءة ولا بيانات حيّة.</b> "
            "الفكرة: نصطاد العنق <b>القادم</b> قبل لا ينفجر سعره. كل سهم هنا يبقى يتفلتر على نظامنا الشرعي — "
            "<b>عنق ممتاز + حرام = مو لنا</b>.</div>"
            "<div class='dim sub2'>🔑 مالك العنق (قوة تسعير) · 🌱 بذرة مضاربية · "
            "<span style='color:#5ee7a0'>أخضر=حلال</span> · "
            "<span style='color:#f0b46b'>أصفر=تأكّد الحلال</span> · "
            "<span style='color:#ff8a9a'>أحمر=حرام عندنا ✗</span> · "
            "<span style='color:#74808f'>رمادي=خارج نطاقنا</span> · الرقم=قناعتنا.</div>")
    if not chains:
        return head + "<p class='dim'>لا توجد خريطة عنق محمّلة.</p></section>"
    cards = ""
    for ch in chains:
        conf = ch.get("confidence")
        conf_badge = (f"<span class='chip {'a-cand' if conf == 'high' else 'a-watch'}'>{_BN_CONF.get(conf, conf)}</span>"
                      if conf else "")
        stages_html = ""
        for st in ch.get("stages", []):
            slab, scls = _BN_STATUS.get(st.get("status"), (st.get("status"), ""))
            prob = _BN_PROB.get(st.get("prob"), "")
            timing = st.get("timing")
            chips = "".join(_bn_chip(t) for t in st.get("tickers", []))
            cov_note = (f"<div class='dim sm' style='font-style:italic'>ℹ️ {_h(st.get('coverage_note'))}</div>"
                        if st.get("coverage_note") else "")
            stages_html += (
                f"<div class='bn-stage'>"
                f"<div class='bn-stage-h'><span class='chip {scls}'>{slab}</span>"
                f"<b>{_h(st.get('name'))}</b>"
                f"<span class='dim sm'>{_h(prob)}{' · ' + _h(timing) if timing else ''}</span></div>"
                f"<div class='dim sm' style='margin:2px 0 6px'>{_h(st.get('note'))}</div>"
                f"<div class='bn-chips'>{chips or '<span class=\"dim sm\">—</span>'}</div>{cov_note}</div>")
        cards += (f"<div class='card bn-card'>"
                  f"<h3 style='font-size:15px;color:#e7ecf3'>{ch.get('icon', '🔗')} {_h(ch.get('name'))} {conf_badge}</h3>"
                  f"<div class='dim sm' style='margin-bottom:4px'>{_h(ch.get('thesis'))}</div>"
                  f"<div class='sm' style='color:#9ce8c4;margin-bottom:8px'>🎯 <b>ليش يفيدنا:</b> {_h(ch.get('why_us'))}</div>"
                  f"{stages_html}</div>")
    return head + f"<div class='bn-grid'>{cards}</div></section>"


def _mode_toggle(meta):
    nav = meta.get("modes_nav") or []
    if not nav:
        return ""
    active = meta.get("active_mode")
    pills = "".join(
        f"<a class='mpill {'on' if k == active else ''}' href='{_h(fname)}'>{_h(label)}</a>"
        for k, label, fname in nav)
    desc = meta.get("active_mode_desc") or ""
    return (f"<div class='moderow'><span class='dim sm'>وضع المستثمر {_i('modes')}:</span>{pills}</div>"
            f"<div class='dim sub2'>{_h(desc)}</div>")


def _movers_section(rows):
    head = (f"<section id='s-movers'><h2>🔀 أبرز التغيّرات {_i('movers')} "
            f"<span class='count n'>{len(rows or [])}</span></h2>"
            "<div class='dim sub2'>أكثر الأسهم تحرّكاً في الترتيب منذ آخر تشغيل — ومعها السبب الرئيسي.</div>")
    if not rows:
        return head + "<p class='dim'>أول تشغيل أو لا تغييرات تُذكر — التشغيل الجاي يوضّح وش تغيّر ولماذا.</p></section>"
    body = ""
    for m in rows:
        up = m.get("direction") == "up"
        col = "#5ee7a0" if up else "#ff8a9a"
        arrow = "▲" if up else "▼"
        body += (f"<tr><td><b class='n'>{_h(m.get('ticker'))}</b>"
                 f"<div class='dim sm'>{_h((m.get('name') or '')[:20])}</div></td>"
                 f"<td class='n' style='color:{col};font-weight:700'>{arrow} {abs(m.get('rank_delta', 0)):.0f}</td>"
                 f"<td class='dim'>{_h(m.get('driver'))}</td>"
                 f"<td class='n'>{m.get('rank_now', 0):.0f}</td></tr>")
    return (head + "<div class='tablewrap'><table><thead><tr><th>السهم</th><th>تغيّر الترتيب</th>"
            "<th>السبب الرئيسي</th><th>الترتيب الآن</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div></section>")


def _backtest_section(bt):
    head = f"<section id='s-bt'><h2>🧪 اختبار بأثر رجعي {_i('backtest')}</h2>"
    if not bt or not bt.get("ok"):
        reason = (bt or {}).get("reason") or "لم يُشغّل بعد"
        return (head + f"<div class='dim sub2'>{_h(reason)} — للتشغيل على جهازك: "
                "<b>python src/main.py --backtest</b> (يحمّل تاريخ ~3 سنوات، يحتاج إنترنت).</div></section>")

    def _p(x):
        return f"{x:+.0%}" if isinstance(x, (int, float)) else "—"

    out = "#5ee7a0" if (bt.get("outperformance") or 0) >= 0 else "#ff8a9a"
    kpis = f"""<div class="banner">
      <div class="kpi"><b class="n" style="color:{out}">{_p(bt.get('basket_return'))}</b><span>سلّة أفضل {bt.get('n_stocks')} سهم ({bt.get('years')} سنة)</span></div>
      <div class="kpi"><b class="n">{_p(bt.get('benchmark_return'))}</b><span>مؤشر {_h(bt.get('benchmark'))} (نفس الفترة)</span></div>
      <div class="kpi"><b class="n" style="color:{out}">{_p(bt.get('outperformance'))}</b><span>الفرق (تفوّق/تخلّف)</span></div>
      <div class="kpi"><b class="n">{_p(bt.get('basket_cagr'))}</b><span>نمو سنوي مركّب للسلّة<br><span class='dim sm'>المؤشر {_p(bt.get('benchmark_cagr'))}</span></span></div>
      <div class="kpi"><b class="n" style="color:#ff8a9a">{_p(bt.get('basket_max_drawdown'))}</b><span>أقصى هبوط للسلّة<br><span class='dim sm'>المؤشر {_p(bt.get('benchmark_max_drawdown'))}</span></span></div>
    </div>"""
    per = bt.get("per_stock") or {}
    chips = "".join(
        f"<span class='tchip' style='color:{'#5ee7a0' if v >= 0 else '#ff8a9a'};border-color:#2a3645'>{_h(k)} {v:+.0%}</span>"
        for k, v in sorted(per.items(), key=lambda kv: -kv[1]))
    caveats = "".join(f"<li>{_h(c)}</li>" for c in (bt.get("caveats") or []))
    return (head
            + "<div class='dim sub2'>سلّة وزن متساوٍ من أقوى أسهمك حالياً، شراء واحتفاظ، مقابل المؤشر.</div>"
            + kpis
            + (f"<div style='margin:8px 0'>{chips}</div>" if chips else "")
            + "<div class='note' style='border-color:#5e4420;background:#231a10;color:#f0c89a'>"
            "⚠️ <b>اقرأ قبل تثق بالأرقام:</b><ul style='margin:8px 18px 0;padding:0'>"
            + caveats + "</ul></div></section>")


CSS = """
*{box-sizing:border-box} html{-webkit-text-size-adjust:100%}
body{margin:0;background:#0b0f17;color:#e7ecf3;direction:rtl;
font-family:-apple-system,'SF Arabic','Segoe UI',Tahoma,Arial,sans-serif;line-height:1.6}
.wrap{max-width:1180px;margin:0 auto;padding:24px 16px 90px}
h1{font-size:25px;margin:0 0 4px} h2{font-size:18px;margin:30px 0 8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
h3{font-size:13px;margin:0 0 12px;color:#aeb9c9}
.count{font-size:12px;background:#1b2330;color:#8fa3bd;border-radius:20px;padding:1px 9px}
.sub{color:#8a97a8;font-size:13px;margin-top:4px} .sub2{color:#8a97a8;font-size:12.5px;margin:2px 0 8px}
.n{direction:ltr;unicode-bidi:isolate;display:inline-block}
.banner{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 6px}
.kpi{background:linear-gradient(160deg,#141b27,#0f141d);border:1px solid #1d2735;border-radius:14px;padding:12px 16px;min-width:150px;flex:1}
.kpi b{display:block;font-size:21px} .kpi span{color:#8a97a8;font-size:12px;display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.qnav{position:sticky;top:0;z-index:30;display:flex;gap:6px;flex-wrap:wrap;background:rgba(11,15,23,.93);
backdrop-filter:blur(8px);padding:10px 4px;margin:8px -4px 6px;border-bottom:1px solid #1b2330}
.qnav a{font-size:12.5px;color:#aeb9c9;background:#141b27;border:1px solid #1d2735;border-radius:20px;
padding:6px 11px;text-decoration:none;white-space:nowrap}
.qnav a:hover{background:#1d2838;color:#fff}
section{scroll-margin-top:64px}
.tablewrap{overflow-x:auto;border:1px solid #1b2330;border-radius:14px}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:820px}
th{position:sticky;top:0;background:#121a25;color:#9fb0c6;text-align:right;padding:9px 8px;font-weight:600;white-space:nowrap;font-size:12px}
td{padding:9px 8px;border-top:1px solid #18202c;vertical-align:top;text-align:right}
td.r{text-align:left} .dim{color:#94a0b0} .sm{font-size:11px}
tbody tr:hover{background:#0f141d}
.chip{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap}
.a-cand{background:#0e3a25;color:#5ee7a0}.a-res{background:#123047;color:#6cc4ff}
.a-watch{background:#3a3413;color:#e8cf5a}.a-verify{background:#3a2a12;color:#f0b46b}.a-avoid{background:#3a1820;color:#ff8a9a}
.h-pass{background:#0e3a25;color:#5ee7a0}.h-unknown{background:#3a2a12;color:#f0b46b}.h-fail{background:#3a1820;color:#ff8a9a}
.f-fresh{background:#0e3a25;color:#5ee7a0}.f-stale{background:#3a3413;color:#e8cf5a}.f-missing{background:#2a2f3a;color:#9aa6b5}
.dir-positive{background:#0e3a25;color:#5ee7a0}.dir-negative{background:#3a1820;color:#ff8a9a}.dir-neutral{background:#222934;color:#9fb0c6}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}@media(max-width:820px){.grid3{grid-template-columns:1fr}table{font-size:12px}}
.card{background:#0f141d;border:1px solid #1b2330;border-radius:14px;padding:16px}
.bar{display:flex;align-items:center;gap:8px;margin:6px 0;font-size:12px}
.bar span{width:110px;color:#aeb9c9;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar .track{flex:1;background:#161d28;border-radius:6px;height:8px;overflow:hidden}
.bar .track i{display:block;height:100%;background:linear-gradient(90deg,#3a7bd5,#5ee7a0)}
/* أشرطة النقاط داخل الجدول (بدل الأرقام المجرّدة) */
.sbwrap{display:flex;align-items:center;gap:6px;justify-content:flex-end;direction:ltr}
.sb{background:#161d28;border-radius:6px;height:8px;width:54px;overflow:hidden;position:relative;flex:0 0 auto}
.sb i{position:absolute;top:0;bottom:0;right:0;border-radius:6px}
.sbwrap b{font-size:12.5px;min-width:20px;text-align:left;color:#e7ecf3}
.tchip{display:inline-block;margin-top:4px;background:#13202e;border:1px solid #24435e;color:#7fd0ff;border-radius:20px;padding:1px 8px;font-size:10.5px}
.sb-lg{width:64px;height:10px}
.ebadge{display:inline-block;margin:4px 0 0 4px;border-radius:20px;padding:1px 7px;font-size:10px;font-weight:700}
.e-comp{background:#0e2a3a;color:#6cc4ff;border:1px solid #1d4a63}
.e-accel{background:#241a3a;color:#c4a0ff;border:1px solid #4a2d6b}
.e-future{background:#0e3a25;color:#5ee7a0;border:1px solid #1d6340}
.e-cyc{background:#3a2a12;color:#f0b46b;border:1px solid #5e4420}
.e-bn{background:#2a230e;color:#e8c454;border:1px solid #caa24a}
.metric{display:flex;align-items:baseline;gap:8px;margin:8px 0}.metric b{font-size:20px}.metric span{color:#8a97a8;font-size:12px}
.note{background:#10161f;border:1px solid #1b2330;border-radius:12px;padding:14px 16px;color:#9fb0c6;font-size:13px;margin-top:18px}
footer{color:#5c6675;font-size:12px;margin-top:40px;text-align:center}
/* علامة الشرح (؟) */
.i{display:inline-flex;align-items:center;justify-content:center;width:17px;height:17px;border-radius:50%;
background:#1f6feb;color:#fff;font-size:11px;font-weight:700;cursor:pointer;margin:0 2px;vertical-align:middle;
flex:0 0 auto;user-select:none;line-height:1}
.i:hover{background:#4a90ff}
/* النافذة المنبثقة */
.modal{display:none;position:fixed;inset:0;background:rgba(2,5,11,.72);z-index:99;align-items:center;justify-content:center;padding:18px}
.box{background:#121a26;border:1px solid #28384b;border-radius:18px;max-width:440px;width:100%;padding:22px;box-shadow:0 18px 60px rgba(0,0,0,.5)}
.box h3{font-size:18px;color:#e7ecf3;margin:0 0 14px;display:flex;justify-content:space-between;align-items:center}
.box .x{cursor:pointer;color:#8a97a8;font-size:22px;line-height:1;padding:0 4px}
.box .lbl{color:#5ee7a0;font-size:12px;font-weight:700;margin-top:12px}
.box .val{color:#cdd6e2;font-size:14px;margin-top:3px}
.box .ex{background:#0e1622;border-radius:10px;padding:10px 12px;margin-top:6px;color:#e7ecf3;font-size:13.5px}
.hint{display:inline-block;background:#13202e;border:1px solid #24435e;color:#7fd0ff;border-radius:20px;
padding:5px 12px;font-size:12.5px;margin:10px 0 0}
.updrow{display:flex;gap:10px;margin:14px 0 4px;flex-wrap:wrap}
.upd{background:#1f6feb;color:#fff;border:0;border-radius:12px;padding:12px 22px;font-size:15px;font-weight:800;cursor:pointer}
.upd:hover{background:#3a82ff}.upd:disabled{opacity:.6;cursor:wait}
.upd2{background:#13351f;color:#5ee7a0;border:1px solid #1d6340;border-radius:12px;padding:12px 18px;font-size:14px;font-weight:700;text-decoration:none}
.moderow{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:14px 0 2px}
.mpill{font-size:13px;color:#aeb9c9;background:#141b27;border:1px solid #1d2735;border-radius:20px;padding:6px 13px;text-decoration:none;font-weight:700}
.mpill:hover{background:#1d2838;color:#fff}
.mpill.on{background:#1f6feb;color:#fff;border-color:#1f6feb}
/* عنق الزجاجة */
.bn-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:820px){.bn-grid{grid-template-columns:1fr}}
.bn-card{padding:16px}
.bn-stage{border-top:1px solid #18202c;padding:9px 0}
.bn-stage-h{display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:13px}
.bn-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:2px}
.bnc{font-size:11.5px;border-radius:8px;padding:2px 8px;font-weight:700;border:1px solid transparent}
.bnc-pass{background:#0e3a25;color:#5ee7a0}.bnc-unk{background:#3a2a12;color:#f0b46b}
.bnc-fail{background:#3a1820;color:#ff8a9a;text-decoration:line-through}
.bnc-out{background:#161d28;color:#74808f}
.bnc-key{border-color:#caa24a;box-shadow:0 0 0 1px #caa24a55}
.bn-acute{background:#3a1820;color:#ff8a9a}.bn-build{background:#3a2a12;color:#f0b46b}
.bn-ease{background:#0e3a25;color:#5ee7a0}.bn-spec{background:#123047;color:#6cc4ff}
/* بطاقة «اليوم» */
.today{background:linear-gradient(160deg,#10221a,#0c1a14);border:1px solid #1d6340;border-radius:16px;padding:15px 16px;margin-top:14px}
.today-h{font-size:16px;font-weight:800;color:#9ce8c4;margin-bottom:8px}
.today-row{display:flex;gap:9px;align-items:flex-start;margin:6px 0;font-size:13.5px;color:#dbe6ef;line-height:1.5}
.today-row .te{font-size:15px;flex:0 0 auto}
/* أكورديون «المزيد» + عنق الزجاجة */
.acc{border:1px solid #1b2330;border-radius:14px;margin-top:18px;background:#0c1119}
.acc>summary{cursor:pointer;padding:13px 16px;font-weight:700;color:#aeb9c9;list-style:none;font-size:14px}
.acc>summary::-webkit-details-marker{display:none}
.acc>summary::before{content:'⌄ ';color:#6cc4ff}
.acc[open]>summary{border-bottom:1px solid #1b2330;color:#fff}
.acc[open]>summary::before{content:'⌃ '}
.acc>section,.acc>div{padding-left:14px;padding-right:14px}
/* هدف لمس أكبر لعلامة ؟ (المرئي 17px، القابل للّمس ~41px) */
.i::after{content:'';position:absolute;inset:-12px}.i{position:relative}
/* scroll-spy active */
.qnav a.on{background:#1f6feb;color:#fff;border-color:#1f6feb}
/* الجوال: جدول الأسهم بدون تمرير أفقي — نخفي الأعمدة الثانوية */
@media(max-width:600px){
  .wrap{padding:16px 12px 80px}h1{font-size:22px}
  .stocktbl{min-width:0!important;font-size:12.5px}
  .stocktbl th:nth-child(5),.stocktbl td:nth-child(5),
  .stocktbl th:nth-child(6),.stocktbl td:nth-child(6),
  .stocktbl th:nth-child(7),.stocktbl td:nth-child(7),
  .stocktbl th:nth-child(8),.stocktbl td:nth-child(8),
  .stocktbl th:nth-child(9),.stocktbl td:nth-child(9),
  .stocktbl th:nth-child(11),.stocktbl td:nth-child(11){display:none}
  .holdtbl{min-width:0!important;font-size:12.5px}
  .holdtbl th:nth-child(5),.holdtbl td:nth-child(5),
  .holdtbl th:nth-child(6),.holdtbl td:nth-child(6){display:none}
  .qnav{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  .qnav::-webkit-scrollbar{display:none}
  .kpi{min-width:130px}
  /* tighten the stock table so all 5 kept columns fit 375px with no scroll */
  .stocktbl td,.stocktbl th{padding:7px 5px}
  .stocktbl .sb-lg{width:40px;height:9px}.stocktbl .sb{width:42px}.stocktbl .sbwrap{gap:4px}
  .stocktbl .chip{padding:2px 6px;font-size:10px}
  .stocktbl .ebadge,.stocktbl .tchip{font-size:9.5px;padding:1px 5px;margin:3px 0 0 3px}
  .stocktbl .sbwrap b{font-size:11px;min-width:16px}
}
"""

JS = """
function g(k){var d=GL[k];if(!d)return;
 document.getElementById('gt').innerText=d.t;
 document.getElementById('gw').innerText=d.w;
 document.getElementById('gb').innerText=d.b;
 document.getElementById('ge').innerText=d.e;
 document.getElementById('gm').style.display='flex';}
function gc(){document.getElementById('gm').style.display='none';}
document.addEventListener('click',function(e){if(e.target.id==='gm')gc();});
document.addEventListener('keydown',function(e){if(e.key==='Escape')gc();});
function updateAll(b){
  if(location.protocol==='file:'){
    document.getElementById('updmsg').innerHTML='⚠️ عشان الزر يشتغل افتح الداشبورد عبر الخادم: شغّل <b>python src/server.py</b> في التيرمنال.';return;}
  if(location.hostname.indexOf('github.io')>=0 || location.hostname.indexOf('localhost')<0 && location.hostname.indexOf('127.0.0.1')<0){
    document.getElementById('updmsg').innerHTML='📱 هذا <b>رابط عرض (snapshot)</b> — يفتح من أي مكان. للتحديث الحي شغّل <b>python src/server.py</b> على جهازك وافتح localhost:8800.';return;}
  var o=b.innerText;b.disabled=true;b.innerText='⏳ يحدّث الكل...';
  document.getElementById('updmsg').innerText='يحدّث أسهمك live + يفحص السوق. أول مرة باليوم تاخذ دقائق، بعدها أسرع...';
  fetch('/update').then(function(r){return r.json();}).then(function(d){
    document.getElementById('updmsg').innerText=d.ok?'✅ تم — يعيد التحميل الآن':('⚠️ '+(d.summary||'خطأ'));
    if(d.ok){setTimeout(function(){location.reload();},900);}else{b.disabled=false;b.innerText=o;}
  }).catch(function(){document.getElementById('updmsg').innerText='⚠️ تعذّر الاتصال بالخادم — تأكد إنه شغّال';b.disabled=false;b.innerText=o;});
}
// scroll-spy: highlight the nav pill of the section in view
(function(){
  var links={};document.querySelectorAll('.qnav a').forEach(function(a){var id=a.getAttribute('href');if(id&&id[0]==='#')links[id.slice(1)]=a;});
  var ids=Object.keys(links);if(!ids.length||!('IntersectionObserver'in window))return;
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){
    ids.forEach(function(i){links[i].classList.remove('on');});
    if(links[e.target.id])links[e.target.id].classList.add('on');}});},{rootMargin:'-45% 0px -50% 0px'});
  ids.forEach(function(i){var el=document.getElementById(i);if(el)io.observe(el);});
})();
"""


def build(records, buckets, portfolio_rows, news_rows, political_rows, meta, cfg):
    app = (cfg.get("app", {}) or {})
    name = app.get("name", "مرصد الأسهم")
    subtitle = app.get("subtitle", "منصّة بحث استثماري شخصية — بحث، وليست توصية بالشراء")
    top_n = (cfg.get("output", {}) or {}).get("top_n_dashboard", 20)
    # نعرض فقط الأسهم المناسبة — نحذف غير المتوافق شرعياً و«تجنّب» نهائياً
    def _vis(r):
        return r.get("action") != "Avoid" and r.get("halal_status") != "fail"
    visible = [r for r in records if _vis(r)]
    # one ranking everywhere: holistic rank_score (consistency fix)
    ranked = sorted(visible, key=lambda r: (r.get("rank_score") or 0), reverse=True)
    fc = meta.get("fresh_counts", {})
    risk = meta.get("market_risk_today", "—")
    risk_cls = {"Low": "dir-positive", "Medium": "dir-neutral", "High": "a-watch", "Extreme": "a-avoid"}.get(risk, "dir-neutral")

    # honest halal split — never call unknown-halal "suitable"
    h_pass = sum(1 for r in visible if r.get("halal_status") == "pass")
    h_unknown = sum(1 for r in visible if r.get("halal_status") == "unknown")
    suspect_n = sum(1 for r in records if r.get("data_suspect"))
    banner = f"""
    <div class="banner">
      <div class="kpi"><b class="n">{len(visible)}</b><span>سهم في نطاق البحث (من {meta.get('examined',0)})<br>
        <span class='dim sm'>✅ {h_pass} حلال مؤكّد · ⚠️ {h_unknown} تحتاج تأكيد حلال</span></span></div>
      <div class="kpi"><b><span class="chip {risk_cls}">{_h(RISK_AR.get(risk, risk))}</span></b><span>مخاطر السوق اليوم {_i('marketrisk')}</span></div>
      <div class="kpi"><b class="n">{fc.get('FRESH',0)}</b><span>بياناتها حديثة {_i('fresh')}<br><span class='dim sm'>قديمة {fc.get('STALE',0)} · ناقصة {fc.get('MISSING',0)}{' · مشكوكة '+str(suspect_n) if suspect_n else ''}</span></span></div>
      <div class="kpi"><b class="n">{_h(meta.get('data_source'))}</b><span>مصدر البيانات</span></div>
    </div>"""

    # ── "today" card: the answer in a few lines ──
    he = meta.get("holdings_eval") or []
    sells = [h["ticker"] for h in he if "بيع" in (h.get("verdict") or "")]
    opps = [h["ticker"] for h in he if "فرصة" in (h.get("verdict") or "") or h.get("better")]
    pass_cands = [r for r in ranked if r.get("halal_status") == "pass" and r.get("action") == "Candidate"]
    strong_unknown = [r["ticker"] for r in ranked if r.get("halal_status") == "unknown" and not r.get("is_fund")][:3]
    today = []
    if sells:
        today.append(("⚠️", f"راجع في محفظتك: <b class='n'>{'، '.join(sells)}</b> — قناعتنا فيها ضعيفة، ابحث السبب."))
    elif opps:
        today.append(("🔵", f"فرص/بدائل في محفظتك: <b class='n'>{'، '.join(opps)}</b>."))
    else:
        today.append(("✅", "محفظتك: لا إجراء عاجل اليوم — استمر بخطّتك."))
    if pass_cands:
        today.append(("🟢", f"أقوى مرشّح حلال مؤكّد: <b class='n'>{_h(pass_cands[0]['ticker'])}</b> (قناعة {pass_cands[0].get('conviction_score')}/10)."))
    else:
        today.append(("🔍", f"لا مرشّح حلال <b>مؤكّد</b> اليوم. الأقوى تحتاج تأكيد على Zoya/Musaffa: <b class='n'>{'، '.join(strong_unknown)}</b>."))
    today.append(("📊", f"مخاطر السوق: <b>{_h(RISK_AR.get(risk, risk))}</b>"
                        + (f" · ⚠️ {suspect_n} سهم ببيانات مشكوكة استُبعدت من الترتيب." if suspect_n else ".")))

    # halal shortlist: the FEW worth paying to verify (high conviction), not 753 maybes
    halal_all = [r for r in buckets.get("Verify Halal First", []) if not r.get("is_fund")]
    halal_short = sorted([r for r in halal_all if (r.get("conviction_score") or 0) >= 7],
                         key=lambda r: (r.get("conviction_score") or 0), reverse=True)[:12]
    halal_extra = len(halal_all) - len(halal_short)

    nav = ("<nav class='qnav'>"
           "<a href='#s-today'>📌 اليوم</a>"
           "<a href='#s-hold'>💼 محفظتي</a>"
           "<a href='#s-future'>🌱 الفرص</a>"
           "<a href='#s-halal'>⚠️ تأكّد الحلال</a>"
           "<a href='#s-bn'>🔗 عنق الزجاجة</a>"
           "<a href='#s-watch'>⭐ قائمتي</a>"
           "<a href='#s-top'>🏆 الأقوى</a>"
           "<a href='#s-port'>📊 المحفظة</a>"
           "<a href='#s-more'>🧰 المزيد</a>"
           "</nav>")

    halal_sub = "أقوى الأسهم غير المؤكّدة شرعياً (قناعة ≥7) — هذي الي تستاهل تدفع تتأكّد منها على Zoya/Musaffa."
    if halal_extra > 0:
        halal_sub += f" (+{halal_extra} أخرى أقل قناعة في الملف)."

    secondary = (
        "<details class='acc' id='s-more'><summary>🧰 إشارات ثانوية وأدوات تشخيص (اضغط للعرض)</summary>"
        + _signals_section(meta.get("signals_rows") or [])
        + _backtest_section(meta.get("backtest"))
        + _not_investable_section(buckets.get("not_investable", []))
        + _news(news_rows)
        + _political(political_rows)
        + "</details>")

    bn_collapsed = ("<details class='acc' id='s-bn-wrap'><summary>🔗 عنق الزجاجة عبر القطاعات — اصطد العنق القادم (اضغط للعرض)</summary>"
                    + _bottleneck_section(meta.get("bottlenecks") or [])
                    + "</details>")

    parts = [
        f"<h1>📊 {_h(name)}</h1>",
        f"<div class='sub'>{_h(subtitle)} · حُدّث {_h(meta.get('generated_at'))} (توقيت قطر)</div>",
        "<div class='updrow'><button class='upd' onclick='updateAll(this)'>🔄 حدّث الكل</button>"
        "<a class='upd2' href='planner.html'>💼 مخطّط المحفظة</a></div>"
        "<div id='updmsg' class='dim sm'></div>",
        _mode_toggle(meta),
        banner,
        nav,
        "<div class='dim sm' style='margin:4px 0 0'>💡 اضغط أي <b style='color:#1f6feb'>؟</b> لشرح المصطلح.</div>",
        _today_card(today),
        _holdings_section(he),
        (_movers_section(meta.get("movers") or []) if meta.get("movers") else ""),
        "<div class='hint' style='background:#10221a;border-color:#1d6340;color:#9ce8c4'>🎯 محرّكات الصيد: <b>قادة المستقبل</b> (x3–x10) · <b>مُسرِّعون</b> (6–24 شهر) · <b>مُركِّبون</b> (جودة تدوم).</div>",
        _section_table("🌱", "قادة المستقبل (صيد x3–x10)", "future_leader", buckets.get("future_leader", []),
                       "أسهم صغيرة/متوسطة، نمو قوي + ثيم مستقبلي، ولسه ما انفجرت — الفرص الكبيرة على سنوات، بحصص صغيرة.", sid="s-future"),
        _section_table("🚀", "مُسرِّعون (6–24 شهر)", "accelerator", buckets.get("accelerator", []),
                       "نموها يتسارع والمحللون إيجابيون وأرباحها تفوق التوقعات — فرص متوسطة المدى.", sid="s-accel"),
        _section_table("🏛️", "مُركِّبون طويل المدى", "compounder", buckets.get("compounder", []),
                       "جودة عالية + نمو يدوم سنوات + ميزانية قوية — أساس الثروة.", sid="s-comp"),
        _section_table("⚠️", "تأكّد من الحلال أولاً (الأقوى)", "halal", halal_short, halal_sub, limit=12, sid="s-halal"),
        _section_table("⭐", "قائمتي (قناعاتي)", "watchlist",
                       [r for r in buckets.get("watchlist", []) if _vis(r)],
                       "أسهمك — التفاصيل الكاملة في watchlist.csv.", sid="s-watch"),
        f"<section id='s-top'><h2>🏆 الأقوى إجمالاً {_i('top20')} <span class='count n'>{min(top_n, len(ranked))}</span></h2>"
        "<div class='dim sub2'>الأفضل من كل النواحي أولاً (قناعة + صعود + مخاطرة منخفضة + محرّكات + بيانات حديثة).</div>"
        f"<div class='tablewrap'><table class='stocktbl'>{_thead()}<tbody>{_stock_rows(ranked[:top_n])}</tbody></table></div></section>",
        bn_collapsed,
        _exposure(visible),
        f"<span id='s-port'></span>",
        _portfolio(portfolio_rows),
        secondary,
        "<div class='note'>هذا <b>نظام بحث</b>، وليس نصيحة استثمارية. لا مخرج هنا توصية شراء ولا وعد بسعر. "
        "الحالة الشرعية تقريبية — أكّد كل سهم على Zoya/Musaffa. بيانات قديمة/ناقصة/مشكوكة → ثقة أقل. القرار والمسؤولية عليك وحدك.</div>",
        f"<footer>{_h(name)} · منصّة بحث استثماري شخصية · يُولَّد محلياً على جهازك</footer>",
        # نافذة الشرح
        "<div class='modal' id='gm'><div class='box'>"
        "<h3><span id='gt'></span><span class='x' onclick='gc()'>×</span></h3>"
        "<div class='lbl'>وش يعني؟</div><div class='val' id='gw'></div>"
        "<div class='lbl'>الفايدة</div><div class='val' id='gb'></div>"
        "<div class='lbl'>مثال</div><div class='ex' id='ge'></div>"
        "</div></div>",
        f"<script>var GL={json.dumps(GLOSSARY, ensure_ascii=False)};{JS}</script>",
    ]
    return (f"<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{_h(name)}</title><style>{CSS}</style></head>"
            f"<body><div class='wrap'>{''.join(parts)}</div></body></html>")
