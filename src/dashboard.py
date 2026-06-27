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
import framework


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
    """علامة (؟) صغيرة هادئة تفتح شرح المصطلح."""
    return "<span class='i' onclick=\"event.stopPropagation();g('%s')\">؟</span>" % key


def _conv(s):
    """رقم القناعة بلون هادئ + شريط رفيع."""
    if not isinstance(s, (int, float)):
        return "<span class='cv cv-na'>—</span>"
    c = "cv-hi" if s >= 8 else ("cv-mid" if s >= 6.5 else "cv-lo")
    w = int(max(0, min(10, s)) * 10)
    return ("<span class='cv %s'><b class='n'>%.1f</b><i style='width:%d%%'></i></span>" % (c, s, w))


_HDOT = {"pass": "d-ok", "unknown": "d-unk", "fail": "d-no"}


def _ldetail(r):
    def pct(x):
        return ("%+.0f%%" % (x * 100)) if isinstance(x, (int, float)) else "—"
    rk = r.get("risk_score")
    up = r.get("analyst_upside_percent")
    rg = r.get("rev_growth")
    hm = r.get("suggested_hold_months")
    fv = r.get("fair_value_estimate")
    pr = r.get("price")
    fvtxt = "—"
    if isinstance(fv, (int, float)) and isinstance(pr, (int, float)) and pr > 0:
        fvtxt = "~%.0f (%+.0f%%)" % (fv, (fv / pr - 1) * 100)
    rate = RATING_AR.get(r.get("rec_key"), "—") if r.get("rec_key") else "—"
    pb = framework.PLAYBOOK_AR.get(r.get("playbook"), r.get("playbook") or "—")
    cells = [
        ("المخاطرة", ("%.0f/100" % rk) if isinstance(rk, (int, float)) else "—"),
        ("الصعود المتوقع", pct(up)),
        ("نمو المبيعات", pct(rg)),
        ("مدة الاحتفاظ", ("~%d شهر" % hm) if hm else "—"),
        ("القيمة العادلة", fvtxt),
        ("تقييم المحللين", rate),
        ("الدفتر (الخطة)", pb),
    ]
    grid = "<div class='dgrid'>" + "".join(
        "<div class='dc'><span>%s</span><b class='n'>%s</b></div>" % (l, _h(v)) for l, v in cells) + "</div>"
    return "<div class='ldetail'>%s%s%s</div>" % (grid, _why_block(r.get("why_note")), _peers_block(r.get("peers")))


def _why_block(w):
    """THE WHY — live, dated, sourced. Shown automatically when a note exists."""
    if not w:
        return ""
    rows = ""
    for icon, key, lbl in (("💡", "thesis", "ليش يتحرّك"), ("⚡", "catalyst", "المحفّز"),
                           ("🏦", "street", "وول ستريت"), ("⚠️", "other_side", "الجهة الأخرى")):
        if w.get(key):
            rows += "<div class='wq'><span>%s %s</span><div>%s</div></div>" % (icon, lbl, _h(w[key]))
    foot = ""
    if w.get("as_of") or w.get("source"):
        foot = "<div class='muted xs wfoot'>🔎 بحث حي · %s · %s</div>" % (_h(w.get("as_of", "")), _h(w.get("source", "")))
    return "<div class='why'>%s%s</div>" % (rows, foot)


def _peers_block(p):
    """THE CHECK — 5-peer comparison, computed from our universe. Best per column highlighted."""
    if not p or not p.get("rows"):
        return ""
    head = "<div class='pr2 ph'><b>الأقران</b><span>نمو</span><span>هامش</span><span>P/E</span></div>"
    body = ""
    for r in p["rows"]:
        def cell(key, best, fmt):
            v = r.get(key)
            txt = fmt(v) if isinstance(v, (int, float)) and (v > 0 or key != "fpe") else "—"
            cls = "pbest" if (r["ticker"] == best and txt != "—") else ""
            return "<b class='n %s'>%s</b>" % (cls, txt)
        body += "<div class='pr2 %s'><b class='n'>%s</b>%s%s%s</div>" % (
            "pself" if r["is_self"] else "", _h(r["ticker"]),
            cell("rev_growth", p["best_growth"], lambda v: "%+.0f%%" % (v * 100)),
            cell("op_margin", p["best_margin"], lambda v: "%.0f%%" % (v * 100)),
            cell("fpe", p["best_value"], lambda v: "%.0f" % v))
    return "<div class='peers'><div class='muted xs' style='margin:2px 0 4px'>مقابل أقرب 5 منافسين (الأخضر = الأفضل):</div>%s%s</div>" % (head, body)


def _hold_detail(r):
    """Personal-framework alert plan for a holding: playbook + danger line + 2 upside alerts + harvest."""
    pb = framework.PLAYBOOK_AR.get(r.get("playbook"), r.get("playbook") or "—")
    a = r.get("alerts")
    extras = _why_block(r.get("why_note")) + _peers_block(r.get("peers"))
    if not a:
        return ("<div class='ldetail'><div class='dgrid'><div class='dc'><span>الدفتر</span><b>%s</b></div>"
                "<div class='dc'><span>التنبيهات</span><b>عبّي سعر الشراء في holdings.csv</b></div></div>%s</div>"
                % (_h(pb), extras))
    cells = [
        ("الدفتر", pb),
        ("⚠️ خط الخطر −40%", "%.2f" % a["danger_price"]),
        ("🎯 تنبيه +%d%%" % (a["up1_pct"] * 100), "%.2f" % a["up1_price"]),
        ("🎯 تنبيه +%d%%" % (a["up2_pct"] * 100), "%.2f" % a["up2_price"]),
    ]
    g = "".join("<div class='dc'><span>%s</span><b class='n'>%s</b></div>" % (l, _h(v)) for l, v in cells)
    g += "<div class='dc wide'><span>🌾 الحصاد</span><b style='font-weight:600'>%s</b></div>" % _h(a["harvest"])
    return "<div class='ldetail'><div class='dgrid'>%s</div>%s</div>" % (g, extras)


def _lrow(r, idx=None):
    t = r.get("ticker")
    hal = r.get("halal_status")
    src = "✓" if str(r.get("halal_source") or "").startswith("manual") else ""
    theme = THEME_AR.get(r.get("primary_theme"), r.get("primary_theme") or "")
    act = ACTION_AR.get(r.get("action"), r.get("action") or "")
    bn = "<span class='kk' title='مالك عنق زجاجة'>🔑</span>" if r.get("bottleneck_owner") else ""
    eng = "".join("<span class='eg'>%s</span>" % ENGINE_AR.get(e, e) for e in (r.get("engines") or []))
    name = (r.get("name") or "").strip()
    nm = ("<span class='nm'>%s</span>" % _h(name[:18])) if name and name.upper() != str(t).upper() else ""
    sub = " · ".join(x for x in [theme, act] if x)
    rank = ("<span class='rk'>%s</span>" % idx) if idx else ""
    return (
        "<div class='lrow' onclick='exp(this)'>"
        + rank
        + "<span class='hd %s' title='%s'>%s</span>" % (_HDOT.get(hal, "d-unk"), _h(HALAL_AR.get(hal, hal)), src)
        + "<div class='lmain'><div class='lt'><b class='n'>%s</b>%s%s%s</div>" % (_h(t), nm, bn, eng)
        + "<div class='lsub'>%s</div></div>" % _h(sub)
        + _conv(r.get("conviction_score"))
        + "<span class='chev'>⌄</span></div>"
        + _ldetail(r)
    )


def _stock_list(records, numbered=True):
    if not records:
        return "<p class='muted pad'>لا يوجد في هذا التشغيل.</p>"
    return "<div class='list'>" + "".join(
        _lrow(r, (i if numbered else None)) for i, r in enumerate(records, 1)) + "</div>"


def _today_hero(lines):
    if not lines:
        return ""
    items = "".join("<div class='th-row'><span class='te'>%s</span><div>%s</div></div>" % (e, t) for e, t in lines)
    return "<div class='today'><div class='th-h'>📌 اليوم</div>%s</div>" % items


def _mode_bar(meta):
    nav = meta.get("modes_nav") or []
    if not nav:
        return ""
    active = meta.get("active_mode")
    seg = "".join("<a class='seg %s' href='%s'>%s</a>" % ("on" if k == active else "", _h(f), _h(l))
                  for k, l, f in nav)
    desc = meta.get("active_mode_desc") or ""
    return "<div class='modebar'>%s</div><div class='muted xs cset'>%s</div>" % (seg, _h(desc))


def _holdings_list(rows):
    if not rows:
        return "<p class='muted pad'>لا محفظة محمّلة — عبّي أسهمك في <b>data/holdings.csv</b>.</p>"
    out = ""
    for r in rows:
        if r.get("pnl_suspect"):
            pnl = "<span class='warn'>⚠️ سعر مشكوك</span>"
        elif r.get("pnl") is not None:
            col = "#67c79a" if r["pnl"] >= 0 else "#d9777f"
            pnl = "<span class='n' style='color:%s;font-weight:700'>%+.0f%%</span>" % (col, r["pnl"] * 100)
        else:
            pnl = "<span class='muted'>—</span>"
        b = r.get("better")
        better = ("<div class='muted xs'>↑ بديل أقوى في دوره: <b class='n'>%s</b></div>" % _h(b["ticker"])) if b else ""
        pbtag = ("<span class='eg'>%s</span>" % framework.PLAYBOOK_AR.get(r.get("playbook"), "")) if r.get("playbook") else ""
        out += (
            "<div class='lrow' onclick='exp(this)'><div class='lmain'>"
            "<div class='lt'><b class='n'>%s</b> <span class='vd'>%s</span>%s</div>"
            "<div class='lsub'>%s</div>%s</div>"
            "<div class='hpnl'>%s<div class='muted xs'>%s</div></div><span class='chev'>⌄</span></div>"
            "%s"
            % (_h(r["ticker"]), _h(r["verdict"]), pbtag, _h(r.get("why", "")), better,
               pnl, _h(r.get("hold_label") or ""), _hold_detail(r))
        )
    return "<div class='list'>" + out + "</div>"


def _portfolio_list(rows):
    out = ""
    for r in rows:
        out += (
            "<div class='prow'><div class='pl'><b>%s</b><div class='muted xs'>%s</div></div>"
            "<div class='pr'><b class='n'>%s</b></div></div>"
            "<div class='muted xs phold n' dir='ltr'>%s</div>"
            % (_h(r["bucket"]), _h(r["notes"]), _h(r["allocation_pct"]), _h(r["suggested_holdings"]))
        )
    return "<div class='plist'>" + out + "</div>"


def _bottleneck_v2(chains):
    intro = ("<div class='bn-intro'>🔗 <b>عنق الزجاجة</b> = العنصر النادر اللي الكل محتاجه، ومن يملكه يكسب أكثر شي. "
             "نصطاد العنق <b>القادم</b> قبل ما يغلى. "
             "<span class='muted'>⚠️ تحليل مرجّح حتى 2026 — مو نبوءة. الحرام يطلع مشطوب. الرقم = قناعتنا.</span> %s</div>"
             % _i("bottleneck"))
    if not chains:
        return intro + "<p class='muted pad'>لا توجد خريطة.</p>"
    cards = ""
    for ch in chains:
        stages = ch.get("stages") or []
        acute = next((s for s in stages if s.get("status") == "acute"), (stages[0] if stages else None))
        allt = [t for s in stages for t in (s.get("tickers") or [])]
        mine = sorted([t for t in allt if t.get("halal") != "fail" and t.get("covered")],
                      key=lambda t: (t.get("role") != "chokepoint", -(t.get("conviction") or 0)))
        pick = mine[0] if mine else None
        alts = [t["sym"] for t in mine[1:4]]
        strip = ""
        for s in stages:
            label = (s.get("name") or "").split("(")[0].strip()[:16]
            on = "on" if s is acute else ""
            strip += "<span class='stg %s'>%s</span>" % (on, _h(label))
        confdot = {"high": "cd-hi", "med": "cd-mid"}.get(ch.get("confidence"), "cd-mid")
        if pick:
            cv = ("<span class='cv cv-mid mini'><b class='n'>%.1f</b></span>" % pick["conviction"]) if pick.get("conviction") is not None else ""
            key = " <span class='kk'>🔑</span>" if pick.get("role") == "chokepoint" else ""
            altline = ("<div class='muted xs'>بدائل: %s</div>" % " · ".join(alts)) if alts else ""
            pk = "<div class='bn-pick'><span class='muted xs'>المتاح لك:</span> <b class='n big'>%s</b> %s%s%s</div>" % (
                _h(pick["sym"]), cv, key, altline)
        else:
            pk = "<div class='bn-pick muted xs'>ما فيه مالك حلال متاح لك في هذا العنق حالياً.</div>"
        cards += (
            "<div class='bn2'><div class='bn2-h'><span class='cd %s'></span><b>%s %s</b></div>"
            "<div class='muted sm bn2-idea'>%s</div>"
            "<div class='strip'>%s</div>%s</div>"
            % (confdot, ch.get("icon", "🔗"), _h(ch.get("name")), _h((ch.get("thesis") or "")[:115]), strip, pk)
        )
    return intro + "<div class='bn2-grid'>%s</div>" % cards


def _exposure_compact(records):
    cand = [r for r in records if r.get("action") in ("Candidate", "Research More", "Watch", "Verify Halal First")]
    sectors = Counter((r.get("sector") or "—") for r in cand)
    themes = Counter(THEME_AR.get(t, t) for r in cand for t in (r.get("themes") or []))

    def bars(counter, n=6):
        if not counter:
            return "<p class='muted xs'>—</p>"
        mx = max(counter.values())
        return "".join(
            "<div class='xbar'><span>%s</span><div class='xt'><i style='width:%d%%'></i></div><b class='n'>%d</b></div>"
            % (_h(k), int(100 * v / mx), v) for k, v in counter.most_common(n))
    return ("<div class='card2'><h4>حسب القطاع %s</h4>%s</div>"
            "<div class='card2'><h4>حسب الثيم</h4>%s</div>" % (_i("exposure"), bars(sectors), bars(themes)))


def _signals_compact(rows):
    if not rows:
        return "<p class='muted xs pad'>لا إشارات — قول لكلود «شوف المؤثرين».</p>"
    out = ""
    for r in rows[:20]:
        out += ("<div class='srow'><b class='n'>%s</b><span class='muted xs'>%s</span>"
                "<span class='fit'>%s</span></div>"
                % (_h(r.get("ticker")), _h(r.get("account")), _h(r.get("platform_fit"))))
    return "<div class='list'>" + out + "</div>"


def _backtest_compact(bt):
    if not bt or not bt.get("ok"):
        reason = (bt or {}).get("reason") or "لم يُشغّل بعد"
        return "<p class='muted xs pad'>%s — شغّل <b>python src/main.py --backtest</b>.</p>" % _h(reason)
    def p(x):
        return ("%+.0f%%" % (x * 100)) if isinstance(x, (int, float)) else "—"
    line = ("<div class='bt-line'>سلّة أقوى %s سهم: <b class='n' style='color:#67c79a'>%s</b> "
            "مقابل %s <b class='n'>%s</b> · الفرق <b class='n'>%s</b> "
            "<span class='muted xs'>(%s سنة)</span></div>"
            % (bt.get("n_stocks"), p(bt.get("basket_return")), _h(bt.get("benchmark")),
               p(bt.get("benchmark_return")), p(bt.get("outperformance")), bt.get("years")))
    caveats = "".join("<li>%s</li>" % _h(c) for c in (bt.get("caveats") or []))
    return (line + "<details class='mini'><summary>⚠️ اقرأ قبل تثق بالأرقام</summary>"
            "<ul class='cav'>%s</ul></details>" % caveats)


def _news_compact(rows):
    if not rows:
        return "<p class='muted xs pad'>لا أحداث محمّلة.</p>"
    dir_ar = {"positive": "إيجابي", "negative": "سلبي", "neutral": "محايد"}
    out = ""
    for r in rows[:12]:
        out += ("<div class='srow'><b>%s</b><span class='muted xs'>%s</span>"
                "<span class='muted xs'>%s</span></div>"
                % (_h(r["event_name"]), _h(r["date"]), _h(dir_ar.get(r["impact_direction"], r["impact_direction"]))))
    return "<div class='list'>" + out + "</div>"


def _political_compact(rows):
    if not rows:
        return "<p class='muted xs pad'>لا صفقات كونغرس حديثة (إشارة ضعيفة فقط).</p>"
    out = ""
    for r in rows[:20]:
        out += ("<div class='srow'><b class='n'>%s</b><span class='muted xs'>%s</span>"
                "<span class='muted xs'>%s</span></div>"
                % (_h(r["ticker"]), _h(r["politician_name"]), _h(r["transaction_type"])))
    return "<div class='list'>" + out + "</div>"


def _not_inv_compact(records):
    if not records:
        return ""
    out = ""
    for r in records[:20]:
        reasons = "، ".join(r.get("not_investable_reasons") or [])
        out += ("<div class='srow'><b class='n'>%s</b><span class='muted xs'>%s</span></div>"
                % (_h(r.get("ticker")), _h(reasons[:50])))
    return ("<h4>🚫 غير قابلة للاستثمار بعد %s</h4><div class='muted xs'>بيانات ناقصة/مشكوكة — ليست محرّمة.</div>"
            "<div class='list'>%s</div>" % (_i("notinv"), out))


CSS = """
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:#0d1014;color:#e7ebf0;direction:rtl;
font-family:-apple-system,'SF Arabic','Segoe UI',Tahoma,Arial,sans-serif;line-height:1.6;font-size:15px}
.wrap{max-width:780px;margin:0 auto;padding:14px 14px 90px}
.n{direction:ltr;unicode-bidi:isolate;display:inline-block}
.muted{color:#8a94a3}.xs{font-size:11.5px}.sm{font-size:12.5px}.pad{padding:14px}
b{font-weight:700}
/* header */
.top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:4px}
.top h1{font-size:19px;margin:0;font-weight:800}
.sub{color:#7a8493;font-size:11.5px;margin-bottom:10px}
.btns{display:flex;gap:8px}
.ico{background:#171c23;border:1px solid #262d37;color:#cfd6df;border-radius:11px;padding:8px 13px;font-size:13px;
font-weight:700;cursor:pointer;text-decoration:none}
.ico:hover{background:#1d232c}.ico.pri{background:#2b5b86;border-color:#2b5b86;color:#fff}
#updmsg{font-size:12px;color:#8a94a3;margin:6px 0}
/* status strip */
.strip0{display:flex;flex-wrap:wrap;gap:7px;margin:8px 0 4px}
.pill{background:#171c23;border:1px solid #262d37;border-radius:20px;padding:5px 11px;font-size:12px;color:#b5bdc8}
.pill b{color:#e7ebf0}
.pill.risk-High,.pill.risk-Extreme{border-color:#5e3a3f;color:#e0a3a8}
.pill.risk-Low{border-color:#2f5544;color:#9fd9bd}
/* mode segmented */
.modebar{display:inline-flex;background:#13181e;border:1px solid #262d37;border-radius:12px;padding:3px;margin:10px 0 0;gap:2px}
.seg{font-size:12.5px;color:#9aa4b2;padding:6px 13px;border-radius:9px;text-decoration:none;font-weight:700}
.seg:hover{color:#fff}.seg.on{background:#2b5b86;color:#fff}
.cset{margin:5px 0 0}
/* today */
.today{background:#12171d;border:1px solid #233040;border-radius:16px;padding:14px 16px;margin:12px 0}
.th-h{font-size:13px;font-weight:800;color:#8fb7da;letter-spacing:.5px;margin-bottom:8px}
.th-row{display:flex;gap:9px;align-items:flex-start;margin:7px 0;font-size:14px;color:#dde3ea}
.th-row .te{flex:0 0 auto;font-size:15px}
/* tabs */
.tabs{position:sticky;top:0;z-index:20;display:flex;gap:4px;background:rgba(13,16,20,.95);backdrop-filter:blur(8px);
padding:9px 0;margin:6px 0 2px;border-bottom:1px solid #1c232c;overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tabbtn{flex:0 0 auto;background:none;border:0;color:#8a94a3;font-size:14px;font-weight:700;padding:8px 13px;
border-radius:10px;cursor:pointer;white-space:nowrap;font-family:inherit}
.tabbtn.on{background:#1a212a;color:#fff}
.tabpanel{display:none;animation:fade .2s ease}.tabpanel.show{display:block}
@keyframes fade{from{opacity:.4}to{opacity:1}}
h3.sec{font-size:15px;margin:18px 0 4px;font-weight:800}h3.sec .c{color:#7a8493;font-weight:600;font-size:12px}
h4{font-size:13.5px;margin:16px 0 6px;color:#c4ccd6;font-weight:700}
.lead{color:#8a94a3;font-size:12.5px;margin:0 0 8px}
/* list rows */
.list{border:1px solid #1d242d;border-radius:14px;overflow:hidden;background:#12161c}
.lrow{display:flex;align-items:center;gap:10px;padding:11px 13px;border-top:1px solid #1a212a;cursor:pointer}
.lrow:first-child{border-top:0}.lrow:hover{background:#161c23}
.rk{color:#5f6a78;font-size:12px;min-width:16px;text-align:center;direction:ltr}
.hd{width:9px;height:9px;border-radius:50%;flex:0 0 auto;font-size:7px;color:#0d1014;text-align:center;line-height:9px}
.d-ok{background:#67c79a}.d-unk{background:#d9b066}.d-no{background:#d9777f}
.lmain{flex:1;min-width:0}
.lt{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.lt b{font-size:15px}
.nm{color:#8a94a3;font-size:12px}
.kk{font-size:11px}.eg{font-size:10.5px;color:#9aa4b2;background:#1a212a;border-radius:6px;padding:1px 6px}
.lsub{color:#7a8493;font-size:12px;margin-top:2px}
.cv{display:inline-flex;flex-direction:column;align-items:flex-end;gap:3px;flex:0 0 auto;min-width:38px}
.cv b{font-size:15px}.cv i{display:block;height:3px;border-radius:3px;width:0}
.cv-hi b{color:#67c79a}.cv-hi i{background:#67c79a}
.cv-mid b{color:#6ea8de}.cv-mid i{background:#6ea8de}
.cv-lo b{color:#8a94a3}.cv-lo i{background:#4a525d}
.cv-na{color:#5f6a78}.cv.mini{flex-direction:row;min-width:0}.cv.mini i{display:none}
.chev{color:#5f6a78;font-size:13px;flex:0 0 auto}
.ldetail{display:none;border-top:1px solid #1a212a}.ldetail.open{display:block}
.dgrid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:#1a212a}
.dc{background:#12161c;padding:9px 11px}.dc span{display:block;color:#7a8493;font-size:11px}.dc b{font-size:13.5px}
.dc.wide{grid-column:1/-1}
/* THE WHY block */
.why{padding:11px 13px;background:#10161d;border-top:1px solid #1a212a}
.wq{margin:7px 0;font-size:13px}.wq:first-child{margin-top:0}
.wq span{display:block;color:#8fb7da;font-size:11.5px;font-weight:700;margin-bottom:1px}
.wq div{color:#cfd6df;line-height:1.55}
.wfoot{margin-top:8px;border-top:1px dashed #232b35;padding-top:6px}
/* THE CHECK peers */
.peers{padding:10px 13px;background:#11151b;border-top:1px solid #1a212a}
.pr2{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;gap:6px;padding:5px 6px;font-size:12.5px;align-items:center}
.pr2 span{color:#7a8493;font-size:11px;text-align:left}
.pr2 b{text-align:left}.pr2>b:first-child{text-align:right}
.pr2.ph{border-bottom:1px solid #1d242d}.pr2.ph b{color:#8a94a3;font-weight:600}
.pr2.pself{background:#15202b;border-radius:7px}.pr2.pself>b:first-child{color:#8fb7da}
.pbest{color:#67c79a!important;font-weight:800}
.vd{font-size:12.5px;color:#cfd6df;background:#1a212a;border-radius:7px;padding:2px 8px}
.hpnl{text-align:left;flex:0 0 auto}
.warn{color:#e0b06a;font-size:11.5px;font-weight:700}
/* portfolio */
.plist{border:1px solid #1d242d;border-radius:14px;overflow:hidden;background:#12161c}
.prow{display:flex;justify-content:space-between;align-items:center;padding:11px 13px;border-top:1px solid #1a212a}
.prow:first-child{border-top:0}.pl b{font-size:14px}.pr b{font-size:16px;color:#8fb7da}
.phold{padding:0 13px 10px;margin-top:-4px}
/* bottleneck v2 */
.bn-intro{background:#12171d;border:1px solid #233040;border-radius:14px;padding:13px 15px;font-size:13.5px;margin-bottom:12px;line-height:1.7}
.bn2-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.bn2{background:#12161c;border:1px solid #1d242d;border-radius:14px;padding:13px 14px}
.bn2-h{display:flex;align-items:center;gap:7px;font-size:14.5px}
.cd{width:8px;height:8px;border-radius:50%;flex:0 0 auto}.cd-hi{background:#67c79a}.cd-mid{background:#d9b066}
.bn2-idea{margin:5px 0 9px;line-height:1.55}
.strip{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px}
.stg{font-size:10.5px;color:#6f7886;background:#161c23;border:1px solid #222a33;border-radius:7px;padding:2px 7px}
.stg.on{background:#3a2225;border-color:#5e3a3f;color:#e0a3a8;font-weight:700}
.bn-pick{background:#11161c;border-top:1px solid #1d242d;padding-top:9px}
.bn-pick .big{font-size:17px;color:#fff}
/* small cards / bars (more tab) */
.card2{background:#12161c;border:1px solid #1d242d;border-radius:14px;padding:13px 15px;margin-bottom:10px}
.xbar{display:flex;align-items:center;gap:8px;margin:6px 0;font-size:12px}
.xbar span{width:96px;color:#9aa4b2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.xt{flex:1;background:#1a212a;border-radius:5px;height:7px;overflow:hidden}
.xt i{display:block;height:100%;background:#3f6f9c}
.srow{display:flex;align-items:center;gap:9px;padding:9px 13px;border-top:1px solid #1a212a}
.srow:first-child{border-top:0}.srow b{font-size:13.5px}.srow .fit{margin-right:auto;font-size:12px;color:#9aa4b2}
.bt-line{font-size:13.5px;padding:4px 0 8px}
details.mini{font-size:12px}details.mini summary{cursor:pointer;color:#9aa4b2}
.cav{margin:6px 16px 0;padding:0;color:#caa37a;font-size:12px}.cav li{margin:3px 0}
/* glossary marker + modal */
.i{position:relative;display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;
background:#233040;color:#8fb7da;font-size:10px;font-weight:700;cursor:pointer;vertical-align:middle;flex:0 0 auto;line-height:1}
.i::after{content:'';position:absolute;inset:-11px}.i:hover{background:#2b5b86;color:#fff}
.modal{display:none;position:fixed;inset:0;background:rgba(2,5,11,.74);z-index:99;align-items:center;justify-content:center;padding:18px}
.box{background:#141a21;border:1px solid #283341;border-radius:18px;max-width:430px;width:100%;padding:20px}
.box h3{font-size:17px;margin:0 0 12px;display:flex;justify-content:space-between;align-items:center}
.box .x{cursor:pointer;color:#8a94a3;font-size:22px;padding:0 4px}
.box .lbl{color:#67c79a;font-size:11.5px;font-weight:700;margin-top:11px}
.box .val{color:#cdd6e2;font-size:13.5px;margin-top:3px}
.box .ex{background:#0e141a;border-radius:10px;padding:9px 11px;margin-top:6px;font-size:13px}
footer{color:#5a6473;font-size:11.5px;margin-top:32px;text-align:center}
@media(max-width:620px){.bn2-grid{grid-template-columns:1fr}.ldetail.open{grid-template-columns:1fr 1fr}.wrap{padding:12px 11px 84px}}
"""

JS = """
function g(k){var d=GL[k];if(!d)return;
 document.getElementById('gt').innerText=d.t;document.getElementById('gw').innerText=d.w;
 document.getElementById('gb').innerText=d.b;document.getElementById('ge').innerText=d.e;
 document.getElementById('gm').style.display='flex';}
function gc(){document.getElementById('gm').style.display='none';}
document.addEventListener('click',function(e){if(e.target.id==='gm')gc();});
document.addEventListener('keydown',function(e){if(e.key==='Escape')gc();});
function tab(id,btn){var ps=document.querySelectorAll('.tabpanel');for(var i=0;i<ps.length;i++)ps[i].classList.remove('show');
 document.getElementById(id).classList.add('show');
 var bs=document.querySelectorAll('.tabbtn');for(var j=0;j<bs.length;j++)bs[j].classList.remove('on');
 btn.classList.add('on');window.scrollTo({top:0,behavior:'smooth'});}
function exp(el){var d=el.nextElementSibling;if(!d||!d.classList.contains('ldetail'))return;
 var open=d.classList.toggle('open');var c=el.querySelector('.chev');if(c)c.textContent=open?'⌃':'⌄';}
function updateAll(b){
  if(location.protocol==='file:'){document.getElementById('updmsg').innerHTML='⚠️ شغّل <b>python src/server.py</b> عشان الزر يشتغل.';return;}
  if(location.hostname.indexOf('github.io')>=0||location.hostname.indexOf('localhost')<0&&location.hostname.indexOf('127.0.0.1')<0){
    document.getElementById('updmsg').innerHTML='📱 <b>رابط عرض (snapshot)</b> — للتحديث الحي شغّل <b>python src/server.py</b> على جهازك.';return;}
  var o=b.innerText;b.style.opacity=.6;b.innerText='⏳ يحدّث...';
  document.getElementById('updmsg').innerText='يحدّث أسهمك + يفحص السوق...';
  fetch('/update').then(function(r){return r.json();}).then(function(d){
    document.getElementById('updmsg').innerText=d.ok?'✅ تم':('⚠️ '+(d.summary||'خطأ'));
    if(d.ok)setTimeout(function(){location.reload();},800);else{b.style.opacity=1;b.innerText=o;}
  }).catch(function(){document.getElementById('updmsg').innerText='⚠️ تعذّر الاتصال بالخادم';b.style.opacity=1;b.innerText=o;});
}
"""


def build(records, buckets, portfolio_rows, news_rows, political_rows, meta, cfg):
    app = (cfg.get("app", {}) or {})
    name = app.get("name", "مرصد الأسهم")
    top_n = (cfg.get("output", {}) or {}).get("top_n_dashboard", 20)

    def _vis(r):
        return r.get("action") != "Avoid" and r.get("halal_status") != "fail"
    visible = [r for r in records if _vis(r)]
    ranked = sorted(visible, key=lambda r: (r.get("rank_score") or 0), reverse=True)
    opps = [r for r in ranked if not r.get("is_fund")][:top_n]

    h_pass = sum(1 for r in visible if r.get("halal_status") == "pass")
    h_unknown = sum(1 for r in visible if r.get("halal_status") == "unknown")
    suspect_n = sum(1 for r in records if r.get("data_suspect"))
    fc = meta.get("fresh_counts", {})
    risk = meta.get("market_risk_today", "—")

    # today lines
    he = meta.get("holdings_eval") or []
    sells = [h["ticker"] for h in he if "بيع" in (h.get("verdict") or "")]
    opps_h = [h["ticker"] for h in he if "فرصة" in (h.get("verdict") or "") or h.get("better")]
    pass_cands = [r for r in ranked if r.get("halal_status") == "pass" and r.get("action") == "Candidate"]
    strong_unknown = [r["ticker"] for r in opps if r.get("halal_status") == "unknown"][:3]
    today = []
    if sells:
        today.append(("⚠️", "راجع في محفظتك: <b class='n'>%s</b> — قناعتنا فيها ضعيفة." % "، ".join(sells)))
    elif opps_h:
        today.append(("🔵", "فرص/بدائل في محفظتك: <b class='n'>%s</b>." % "، ".join(opps_h)))
    else:
        today.append(("✅", "محفظتك: لا إجراء عاجل اليوم."))
    if pass_cands:
        today.append(("🟢", "أقوى مرشّح حلال مؤكّد: <b class='n'>%s</b> (قناعة %s)." % (
            _h(pass_cands[0]["ticker"]), pass_cands[0].get("conviction_score"))))
    else:
        today.append(("🔍", "لا مرشّح حلال <b>مؤكّد</b> اليوم. الأقوى للتأكيد على Zoya/Musaffa: <b class='n'>%s</b>." % "، ".join(strong_unknown)))
    today.append(("📊", "مخاطر السوق: <b>%s</b>%s" % (
        _h(RISK_AR.get(risk, risk)),
        (" · ⚠️ %d سهم ببيانات مشكوكة استُبعدت." % suspect_n) if suspect_n else ".")))

    status = (
        "<div class='strip0'>"
        "<span class='pill'><b class='n'>%d</b> في نطاق البحث</span>"
        "<span class='pill'>✅ <b class='n'>%d</b> حلال مؤكّد</span>"
        "<span class='pill'>⚠️ <b class='n'>%d</b> تحتاج تأكيد</span>"
        "<span class='pill'><b class='n'>%d</b> بياناتها حديثة</span>"
        "<span class='pill risk-%s'>مخاطر السوق: <b>%s</b></span>"
        "</div>" % (len(visible), h_pass, h_unknown, fc.get("FRESH", 0), risk, _h(RISK_AR.get(risk, risk)))
    )

    # holdings + watchlist lists
    watch = [r for r in buckets.get("watchlist", []) if _vis(r)]

    # tab panels
    tab_opp = (
        "<div id='t-opp' class='tabpanel show'>"
        "<h3 class='sec'>🎯 أقوى الفرص <span class='c'>(مفلترة على نظامك + الحلال)</span></h3>"
        "<p class='lead'>النقطة الخضراء = حلال مبدئياً · الصفراء = تحتاج تأكيد. اضغط أي سهم تفتح تفاصيله. "
        "🔑 = مالك عنق زجاجة. الرقم على اليسار = القناعة %s.</p>" % _i("conviction")
        + _stock_list(opps)
        + "</div>"
    )
    tab_port = (
        "<div id='t-port' class='tabpanel'>"
        "<h3 class='sec'>💼 محفظتي</h3>"
        "<p class='lead'>توصية بحثية حسب الأداء — مو «بيع/اشترِ الآن». اضغط أي سهم تشوف <b>خطة تنبيهاتك</b>: "
        "خط الخطر −40% + هدفين حسب الدفتر + قاعدة الحصاد.</p>"
        + _holdings_list(he)
        + "<h3 class='sec'>⭐ قائمتي %s</h3>" % _i("watchlist")
        + _stock_list(watch)
        + "<h3 class='sec'>📊 نموذج المحفظة %s</h3>" % _i("portfolio")
        + _portfolio_list(portfolio_rows)
        + "</div>"
    )
    tab_bn = (
        "<div id='t-bn' class='tabpanel'>"
        "<h3 class='sec'>🔗 عنق الزجاجة عبر القطاعات</h3>"
        + _bottleneck_v2(meta.get("bottlenecks") or [])
        + "</div>"
    )
    tab_more = (
        "<div id='t-more' class='tabpanel'>"
        "<h3 class='sec'>📈 التعرّض %s</h3><div class='card2-wrap'>%s</div>" % (_i("exposure"), _exposure_compact(visible))
        + "<h4>📡 إشارات المؤثرين %s</h4><div class='muted xs'>إشارة ضعيفة للمراجعة فقط.</div>%s" % (
            _i("signals"), _signals_compact(meta.get("signals_rows") or []))
        + "<h4>🧪 اختبار بأثر رجعي %s</h4>%s" % (_i("backtest"), _backtest_compact(meta.get("backtest")))
        + _not_inv_compact(buckets.get("not_investable", []))
        + "<h4>📰 أثر الأخبار %s</h4>%s" % (_i("news"), _news_compact(news_rows))
        + "<h4>🏛️ النشاط السياسي %s</h4>%s" % (_i("political"), _political_compact(political_rows))
        + "</div>"
    )

    tabs = (
        "<div class='tabs'>"
        "<button class='tabbtn on' onclick=\"tab('t-opp',this)\">🎯 الفرص</button>"
        "<button class='tabbtn' onclick=\"tab('t-port',this)\">💼 محفظتي</button>"
        "<button class='tabbtn' onclick=\"tab('t-bn',this)\">🔗 عنق الزجاجة</button>"
        "<button class='tabbtn' onclick=\"tab('t-more',this)\">🧰 المزيد</button>"
        "</div>"
    )

    header = (
        "<div class='top'><h1>📊 %s</h1>"
        "<div class='btns'><a class='ico' href='planner.html'>💼 المخطّط</a>"
        "<button class='ico pri' onclick='updateAll(this)'>🔄 حدّث</button></div></div>"
        "<div class='sub'>منصّة بحث شخصية — بحث وليست توصية · حُدّث %s</div>"
        "<div id='updmsg'></div>" % (_h(name), _h(meta.get("generated_at")))
    )

    modal = (
        "<div class='modal' id='gm'><div class='box'>"
        "<h3><span id='gt'></span><span class='x' onclick='gc()'>×</span></h3>"
        "<div class='lbl'>وش يعني؟</div><div class='val' id='gw'></div>"
        "<div class='lbl'>الفايدة</div><div class='val' id='gb'></div>"
        "<div class='lbl'>مثال</div><div class='ex' id='ge'></div></div></div>"
    )

    body = (header + _mode_bar(meta) + status + _today_hero(today) + tabs
            + tab_opp + tab_port + tab_bn + tab_more
            + "<footer>%s · يُولَّد محلياً · القرار والمسؤولية عليك</footer>" % _h(name)
            + modal
            + "<script>var GL=%s;%s</script>" % (json.dumps(GLOSSARY, ensure_ascii=False), JS))

    return ("<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style></head><body><div class='wrap'>%s</div></body></html>"
            % (_h(name), CSS, body))
