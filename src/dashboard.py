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
import re
from collections import Counter
import framework
import forward

# strip pictographic emoji (zero-emoji identity) while preserving arrows (↑, U+2190-21FF)
# and chevrons (⌃⌄, U+2300-23FF), which are functional in the UI
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿⬀-⯿︎️‍]+\\s?"
)


def _strip_emoji(s):
    return _EMOJI_RE.sub("", s) if s else s


# عملة العرض — تُضبَط من config في build(). المبالغ والسقوف بالريال؛ أسعار الأسهم تبقى دولاراً.
_CUR = {"symbol": "$", "rate": 1.0}


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
                  "w": "توزيع مبني على البحث لمستثمر 25 سنة، نمو عالي مع حماية: نواة مُركِّبين + مُسرِّعين + قادة مستقبل صغار + ETF حلال + ذهب + مضاربات صغيرة + كاش. كل خانة تختار الأفضل تلقائياً.",
                  "b": "يوزّع المخاطر بدل ما تحط كل فلوسك بسهم واحد؛ كل خانة لها دورها.",
                  "e": "الذهب يحميك وقت الأزمات؛ الكاش ذخيرة للشراء بالهبوط؛ المضاربات وزن صغير عالي المخاطرة."},
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
    "modes": {"t": "وضع المحفظة (محافظ/متوازن/هجومي)",
              "w": "يغيّر «توزيع محفظتك» فقط — البحث والترتيب يبقى موضوعياً (نفس الترتيب في كل الأوضاع). «هجومي» يرفع وزن قادة المستقبل والمضاربات؛ «محافظ» يرفع الجودة والذهب والكاش.",
              "b": "يشكّل محفظتك حسب شخصيتك الاستثمارية بدون ما يلمس ترتيب البحث.",
              "e": "بدّل من الأزرار فوق: «هجومي» يكبّر سلّة الفرص والمضاربات؛ «محافظ» يكبّر النواة والحماية."},
    "forward": {"t": "النظرة المستقبلية (0–10)",
                "w": "توقّع مرجّح يستبق الجاي: اتجاه تقديرات المحللين (يرفعون/يخفّضون الأهداف)، النمو المتوقّع، المحفّزات القريبة، وعنق الزجاجة. ليست وعداً ولا نبوءة.",
                "b": "تشوف من تتحسّن توقّعاته مو بس وضعه الحالي — والمحفظة تميل للأقوى مستقبلياً.",
                "e": "شارة الثقة تنزل تلقائياً لو البيانات ناقصة أو لسه ما عندنا تاريخ تقديرات: «الاتجاه غير متاح بعد»."},
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
    return ("<span class='cv %s'><b class='n cnt' data-c='%.1f' data-d='1'>%.1f</b><i style='width:%d%%'></i></span>" % (c, s, s, w))


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
    def _rs(k):
        v = r.get(k)
        return ("%.0f" % v) if isinstance(v, (int, float)) else "—"
    pro_cells = [("الأساس (خام)", _rs("fundamental_score")), ("الفرصة (خام)", _rs("opportunity_score")),
                 ("الترتيب (خام)", _rs("rank_score")), ("الإجمالي (خام)", _rs("total_score"))]
    grid = ("<div class='dgrid'>"
            + "".join("<div class='dc'><span>%s</span><b class='n'>%s</b></div>" % (l, _h(v)) for l, v in cells)
            + "".join("<div class='dc pro-only'><span>%s</span><b class='n'>%s</b></div>" % (l, _h(v)) for l, v in pro_cells)
            + "</div>")
    # if this is a suggested buy, show the exact entry/stop/target plan too
    trade = _trade_inner(r.get("trade"), pr, header="📋 لو اشتريته الحين — خطة الدخول والوقف") if r.get("trade") else ""
    return "<div class='ldetail'>%s%s%s%s%s</div>" % (
        grid, _forward_block(r), trade, _why_block(r.get("why_note")), _peers_block(r.get("peers")))


def _forward_block(r):
    """النظرة المستقبلية — a labelled weighted expectation (not advice). On-palette: sage
    score, a quiet confidence chip distinct from the conviction bar and halal dot."""
    s = r.get("forward_outlook_score")
    if s is None:
        return ""
    conf = (r.get("forward_outlook_confidence") or "LOW")
    conf_ar = {"HIGH": "ثقة عالية", "MED": "ثقة متوسطة", "LOW": "ثقة منخفضة"}.get(conf, conf)
    sval = ("%.1f" % s).rstrip("0").rstrip(".")
    drivers = "".join("<div class='fwd-d'>%s</div>" % _h(d) for d in (r.get("forward_drivers") or [])[:3])
    return ("<div class='fwd'>"
            "<div class='fwd-h'><span class='fwd-t'>نظرة مستقبلية %s</span>"
            "<b class='n fwd-s'>%s</b><span class='fwd-x'>/10</span>"
            "<span class='fwd-c fwd-%s'>%s</span></div>%s"
            "<div class='fwd-dis'>%s</div></div>"
            % (_i("forward"), sval, conf.lower(), conf_ar, drivers, _h(forward.DISCLAIMER_AR)))


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


_SELLCOL = {"exit": "#d9777f", "hold": "#67c79a", "watch": "#d9b066"}


def _trade_inner(t, cur, header=None):
    """The exact buy/sell numbers grid: forward profit targets, the DATA-DRIVEN stop with
    its reasoning, accumulate price, the rational sell verdict, and stock tracking
    (52w high, max drawdown, volatility). Shared by holdings + suggested buys."""
    if not t or not t.get("profit1"):
        return "<div class='dgrid'><div class='dc'><span>الخطة</span><b>—</b></div></div>"
    pb = framework.PLAYBOOK_AR.get(t.get("playbook"), t.get("playbook") or "—")
    p1, p2 = t["profit1"], t["profit2"]
    stp = t.get("stop") or {}
    acc = t.get("accumulate") or {}
    cells = [("الدفتر", pb)]
    if cur:
        cells.append(("السعر الحالي", "%.2f" % cur))
    if t.get("gain_from_cost") is not None:
        cells.append(("ربحك من الكلفة", "%+.0f%%" % (t["gain_from_cost"] * 100)))
    cells += [
        ("🎯 جني +%d%%" % (p1["pct"] * 100), "%.2f" % p1["price"]),
        ("🎯 جني +%d%%" % (p2["pct"] * 100), "%.2f" % p2["price"]),
    ]
    if stp.get("price"):
        cells.append(("🛑 وقف (stop)", "%.2f" % stp["price"]))
    if acc.get("price"):
        cells.append(("🟢 تجميع عند", "%.2f" % acc["price"]))
    g = ""
    if header:
        g += "<div class='dc wide'><b style='color:#8fb7da'>%s</b></div>" % _h(header)
    g += "".join("<div class='dc'><span>%s</span><b class='n'>%s</b></div>" % (l, _h(v)) for l, v in cells)
    col = _SELLCOL.get(t.get("sell_kind"), "#cfd6df")
    g += ("<div class='dc wide'><span>💡 متى تبيع؟</span>"
          "<b style='font-weight:600;color:%s'>%s</b></div>" % (col, _h(t.get("sell_advice", ""))))
    # stop reasoning (data-driven detail)
    bits = []
    if stp.get("basis"):
        bits.append(stp["basis"])
    if stp.get("loss_from_cost_pct") is not None:
        bits.append("خسارة لو انكسر ~%+.0f%% من كلفتك" % (stp["loss_from_cost_pct"] * 100))
    if bits:
        g += "<div class='dc wide'><span>الوقف غير عشوائي</span><b style='font-weight:600'>%s</b></div>" % _h(" · ".join(bits))
    # stock tracking: peaks + performance
    track = []
    if stp.get("high_52w"):
        track.append("قمة 52أ: %.0f" % stp["high_52w"])
    if stp.get("max_drawdown_1y") is not None:
        track.append("أقصى هبوط سنة: %+.0f%%" % (stp["max_drawdown_1y"] * 100))
    if stp.get("monthly_vol") is not None:
        track.append("تذبذب شهري: %.0f%%" % (stp["monthly_vol"] * 100))
    if track:
        g += "<div class='dc wide'><span>📊 تتبّع السهم</span><b class='n' style='font-weight:600'>%s</b></div>" % _h(" · ".join(track))
    g += "<div class='dc wide'><span>🌾 الحصاد</span><b style='font-weight:600'>%s</b></div>" % _h(t["harvest"])
    return "<div class='dgrid'>%s</div>" % g


def _hold_detail(r):
    """Holding deep-dive: the exact buy/sell plan + why + peers."""
    t = r.get("trade")
    extras = _why_block(r.get("why_note")) + _peers_block(r.get("peers"))
    if not t or not t.get("profit1"):
        pb = framework.PLAYBOOK_AR.get(r.get("playbook"), r.get("playbook") or "—")
        return ("<div class='ldetail'><div class='dgrid'><div class='dc'><span>الدفتر</span><b>%s</b></div>"
                "<div class='dc'><span>الخطة</span><b>عبّي سعر الشراء في holdings.csv</b></div></div>%s</div>"
                % (_h(pb), extras))
    return "<div class='ldetail'>%s%s</div>" % (_trade_inner(t, r.get("current_price")), extras)


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
    items = "".join(
        "<div class='th-row%s'><span class='te'></span><div>%s</div></div>"
        % (" rk" if ("مخاطر" in t or "مشكوك" in t) else "", t)
        for _e, t in lines)
    return "<div class='today'><div class='th-h'>اليوم</div>%s</div>" % items


def _mode_bar(meta):
    nav = meta.get("modes_nav") or []
    if not nav:
        return ""
    active = meta.get("active_mode")
    seg = "".join("<a class='seg %s' href='%s'>%s</a>" % ("on" if k == active else "", _h(f), _h(l))
                  for k, l, f in nav)
    desc = meta.get("active_mode_desc") or ""
    return ("<div class='modebar'><span class='mbl'>وضع المحفظة</span>%s</div>"
            "<div class='muted xs cset'>يغيّر <b>توزيع محفظتك</b> فقط — البحث والترتيب يبقى موضوعياً. %s</div>"
            % (seg, _h(desc)))


def _trade_chips(r):
    """A compact, always-visible stop + first sell-target line for a portfolio holding —
    so you see at a glance what stop/sell prices to set (full plan still on expand)."""
    t = r.get("trade") or {}
    bits = []
    stp = t.get("stop") or {}
    if stp.get("price"):
        bits.append("وقف <b class='n'>%.2f</b>" % stp["price"])
    p1 = t.get("profit1") or {}
    if p1.get("price"):
        bits.append("جني أول <b class='n'>%.2f</b>" % p1["price"])
    acc = t.get("accumulate") or {}
    if acc.get("price"):
        bits.append("تجميع <b class='n'>%.2f</b>" % acc["price"])
    if not bits:
        return ""
    return "<div class='tchips'>%s</div>" % " · ".join(bits)


def _holdings_list(rows):
    if not rows:
        return "<p class='muted pad'>لا محفظة محمّلة — عبّي أسهمك في <b>data/holdings.csv</b>.</p>"
    out = ""
    for r in rows:
        if r.get("pnl_suspect"):
            pnl = "<span class='warn'>⚠️ سعر مشكوك</span>"
        elif r.get("pnl") is not None:
            col = "#67c79a" if r["pnl"] >= 0 else "#d9777f"
            pnl = "<span class='n %s' style='color:%s;font-weight:700'>%+.0f%%</span>" % (
                "pnl-pos" if r["pnl"] >= 0 else "pnl-neg", col, r["pnl"] * 100)
        else:
            pnl = "<span class='muted'>—</span>"
        b = r.get("better")
        bh = ("" if (b or {}).get("halal") == "pass" else
              " <span class='warn xs'>تأكّد حلاله</span>" if b else "")
        better = ("<div class='muted xs'>↑ بديل أقوى في دوره: <b class='n'>%s</b>%s</div>"
                  % (_h(b["ticker"]), bh)) if b else ""
        pbtag = ("<span class='eg'>%s</span>" % framework.PLAYBOOK_AR.get(r.get("playbook"), "")) if r.get("playbook") else ""
        out += (
            "<div class='lrow' onclick='exp(this)'><div class='lmain'>"
            "<div class='lt'><b class='n'>%s</b> <span class='vd'>%s</span>%s</div>"
            "<div class='lsub'>%s</div>%s%s</div>"
            "<div class='hpnl'>%s<div class='muted xs'>%s</div></div><span class='chev'>⌄</span></div>"
            "%s"
            % (_h(r["ticker"]), _h(r["verdict"]), pbtag, _h(r.get("why", "")), better,
               _trade_chips(r), pnl, _h(r.get("hold_label") or ""), _hold_detail(r))
        )
    return "<div class='list'>" + out + "</div>"


# bucket-label keyword → (segment color, legend name)
# single sage ramp (+ warm risk tone for the speculation sleeve) — no competing colors
_DONUT_MAP = [
    ("مُركِّبون", "#7BA79A", "نواة (مُركِّبون)"),
    ("مُسرِّعون", "#6A9086", "مُسرِّعون"),
    ("قادة",      "#597971", "قادة المستقبل"),
    ("ETF",       "#4B655F", "ETF حلال"),
    ("ذهب",       "#3D514C", "ذهب (حماية)"),
    ("مضاربات",   "#C0926E", "مضاربات"),
    ("كاش",       "#314140", "كاش"),
]


def _alloc_donut(rows, meta):
    """Clean animated allocation ring + legend — the visual face of the portfolio."""
    segs = []
    for r in rows:
        lbl = r.get("bucket", "")
        if "تحقّق" in lbl:                       # skip the sum-mismatch warning row
            continue
        try:
            pct = int(round(float(str(r.get("allocation_pct", "0")).replace("%", "").strip())))
        except Exception:
            pct = 0
        if pct <= 0:
            continue
        color, name = "#6b7480", lbl
        for key, c, nm in _DONUT_MAP:
            if key in lbl:
                color, name = c, nm
                break
        segs.append((pct, color, name))
    if not segs:
        return ""
    total = sum(p for p, _, _ in segs) or 100
    ring, cum = "", 0.0
    for i, (pct, color, _) in enumerate(segs):
        share = pct * 100.0 / total
        ring += ("<circle class='seg' cx='100' cy='100' r='72' fill='none' stroke='%s' "
                 "stroke-width='20' pathLength='100' style='--dash:%.2f 100;"
                 "stroke-dashoffset:%.2f;animation-delay:%.2fs'></circle>"
                 % (color, max(0.0, share - 0.7), -cum, 0.07 * i))   # -0.7 = hairline gap between slices
        cum += share
    nav = meta.get("modes_nav") or []
    active = meta.get("active_mode")
    mode_lbl = next((l for k, l, _f in nav if k == active), "التوزيع الذكي")
    center = ("<text x='100' y='94' class='dc-t'>محفظتي</text>"
              "<text x='100' y='116' class='dc-s'>%s</text>" % _h(mode_lbl))
    svg = ("<svg viewBox='0 0 200 200' class='donut' role='img' aria-label='توزيع المحفظة'>"
           "<g transform='rotate(-90 100 100)'>"
           "<circle class='ring-bg' cx='100' cy='100' r='72' fill='none' stroke-width='20'></circle>"
           + ring + "</g>" + center + "</svg>")
    legend = ""
    for pct, color, name in segs:
        lp = int(round(pct * 100.0 / total))      # normalized to match the ring; sums to 100
        legend += ("<div class='dli'><span class='ddot' style='background:%s'></span>"
                   "<span class='dnm'>%s</span>"
                   # static text = the real value (so prefers-reduced-motion shows it, not 0);
                   # the count-up animates from 0→value only when motion is enabled.
                   "<span class='dpc'><span class='cnt' data-c='%d' data-d='0'>%d</span>%%</span></div>"
                   % (color, _h(name), lp, lp))
    return "<div class='dchart'>%s<div class='dleg'>%s</div></div>" % (svg, legend)


def _fwd_pulse(records):
    """One-line forward pulse: how many names have analysts RAISING vs CUTTING estimates
    (only HIGH/MED confidence). Falls back to a strong-outlook count when targets are flat."""
    up = dn = strong = 0
    for r in records:
        if r.get("forward_outlook_confidence") not in ("HIGH", "MED"):
            continue
        ds = " ".join(r.get("forward_drivers") or [])
        if "يرفعون" in ds:
            up += 1
        elif "يخفّضون" in ds:
            dn += 1
        if (r.get("forward_outlook_score") or 0) >= 7 and r.get("forward_outlook_confidence") == "HIGH":
            strong += 1
    if up or dn:
        return ("<div class='fpulse'>نبض المحفظة المستقبلي: <b class='n fp-up'>%d</b> تُرفع تقديراتها · "
                "<b class='n fp-dn'>%d</b> تُخفّض %s</div>" % (up, dn, _i("forward")))
    if strong:
        return ("<div class='fpulse'>نبض المحفظة المستقبلي: <b class='n fp-up'>%d</b> اسم نظرته المستقبلية قوية "
                "(ثقة عالية) %s</div>" % (strong, _i("forward")))
    return ""


def _bucket_meta(label):
    """Map a (possibly emoji-prefixed) bucket label to its sage shade + clean name."""
    for key, color, name in _DONUT_MAP:
        if key in label:
            return color, name
    return "#646B76", label


def _kfmt(x):
    x = x or 0
    s = _CUR["symbol"]
    return (("%.1fk" % (x / 1000.0)).replace(".0k", "k") + " " + s) if x >= 1000 else ("%d %s" % (x, s))


def _portfolio_list(rows, records, cfg):
    """Each bucket → its weight + a per-stock breakdown showing each name's weight, its OWN
    cap, and (where a plan exists) the stop + first sell-target — so you see what to set."""
    base = int(round((cfg.get("portfolio") or {}).get("max_per_stock_usd", 3000) * _CUR["rate"]))
    by_t = {r.get("ticker"): r for r in records if r.get("ticker")}
    out = ""
    for r in rows:
        shade, name = _bucket_meta(r.get("bucket", ""))
        try:
            pctn = int(round(float(str(r.get("allocation_pct", "0")).replace("%", "").strip())))
        except Exception:
            pctn = 0
        barw = max(4, min(100, pctn))
        detail = ""
        for t, pp in re.findall(r"([A-Z]{2,6}) (\d+)%", r.get("suggested_holdings", "") or ""):
            rec = by_t.get(t) or {}
            chips = []
            if t not in _FUND_TICKERS:
                chips.append("سقف <b class='n'>%s</b>" % _kfmt(_position_cap(rec, base)))
            tr = rec.get("trade") or {}
            stp = (tr.get("stop") or {}).get("price")
            if stp:
                chips.append("وقف <b class='n'>%.2f</b>" % stp)
            p1 = (tr.get("profit1") or {}).get("price")
            if p1:
                chips.append("هدف <b class='n'>%.2f</b>" % p1)
            detail += ("<div class='palc'><span class='n'>%s</span>"
                       "<span class='palc-p n'>%d%%</span><span class='palc-c'>%s</span></div>"
                       % (_h(t), int(pp), " · ".join(chips)))
        if not detail and (r.get("suggested_holdings", "") not in ("", "—")):
            detail = "<div class='phold'><div class='xs n' dir='ltr'>%s</div></div>" % _h(r["suggested_holdings"])
        out += (
            "<div class='prow'>"
            "<div class='pl'><span class='pbk' style='background:%s'></span><b>%s</b></div>"
            "<div class='pr'><b class='n'>%s</b></div></div>"
            "<div class='pbar' style='background:%s;width:%d%%'></div>"
            "<div class='muted xs' style='padding:1px 14px 5px'>%s</div>%s"
            % (shade, _h(name), _h(r.get("allocation_pct", "")),
               shade, barw, _h(r.get("notes", "")), detail)
        )
    return "<div class='plist'>" + out + "</div>"


_FUND_TICKERS = {"HLAL", "SPUS", "VOO", "RMAU", "GLD", "IAU", "SPY", "QQQ"}


def _position_cap(rec, base):
    """A per-stock $ cap that DIFFERS by the name's importance: scales up with conviction +
    a strong forward outlook + a core role, and shrinks with risk + small-bet roles — so a
    core compounder gets a bigger ceiling than a speculative punt. (base from config)."""
    m = 1.0
    eng = rec.get("engines") or []
    if "compounder" in eng:
        m *= 1.35
    elif "accelerator" in eng:
        m *= 0.9
    if "future_leader" in eng:
        m *= 0.5
    conv = rec.get("conviction_score") or 0
    if conv >= 9:
        m *= 1.25
    elif conv >= 8:
        m *= 1.1
    elif conv and conv < 6:
        m *= 0.7
    if rec.get("forward_outlook_confidence") == "HIGH" and (rec.get("forward_outlook_score") or 0) >= 8:
        m *= 1.2
    risk = rec.get("risk_score")
    if isinstance(risk, (int, float)) and risk >= 70:
        m *= 0.7
    cap = int(round(base * m / 100.0)) * 100
    return max(500, min(int(base * 2), cap))


def _invest_panel(portfolio_rows, cfg, records):
    """Merged planner with a CUMULATIVE, PER-STOCK cap (each name's ceiling differs by quality).
    Track (in the browser) how much you've put into each name across deposits; a full stock
    stops taking new money — overflow routes to funds + rebalance — UNLESS it's a strong name."""
    base = int(round((cfg.get("portfolio") or {}).get("max_per_stock_usd", 3000) * _CUR["rate"]))
    info = {}
    for r in records:
        t = r.get("ticker")
        if not t:
            continue
        info[t] = {
            "cap": _position_cap(r, base),
            "s": bool((r.get("conviction_score") or 0) >= 9 or (
                r.get("forward_outlook_confidence") == "HIGH" and (r.get("forward_outlook_score") or 0) >= 8)),
        }
    data = []
    for r in portfolio_rows:
        try:
            pctn = float(str(r.get("allocation_pct", "0")).replace("%", "").strip())
        except Exception:
            pctn = 0.0
        if pctn <= 0:
            continue
        shade, name = _bucket_meta(r.get("bucket", ""))
        names = re.findall(r"([A-Z]{2,6}) (\d+)%", r.get("suggested_holdings", "") or "")
        rows = []
        for t, pp in names:
            nf = info.get(t, {})
            rows.append({"t": t, "p": int(pp), "s": nf.get("s", False),
                         "f": (t in _FUND_TICKERS), "cap": nf.get("cap", base)})
        # leftover when caps bind a NAMED bucket (e.g. «AAA 12% · غير موزّع 18%») — route to funds/cash.
        # Nameless buckets (cash) get lo=0: they're already shown by the name-less-bucket renderer, so
        # adding lo here too would DOUBLE-COUNT them.
        lo = max(0.0, pctn - sum(int(pp) for _, pp in names)) if names else 0.0
        data.append({"b": name, "c": shade, "pct": pctn, "names": rows, "lo": round(lo, 2)})
    return ("<div class='invest'>"
            "<div class='inv-h'>مبلغي للاستثمار الآن</div>"
            "<input type='number' id='invamt' inputmode='decimal' placeholder='مثال: 1000' "
            "class='inv-in n' oninput='splitInvest()'>"
            "<div id='invout'></div>"
            "<div class='inv-btns'>"
            "<button class='ibtn' onclick='recordInvest()'>سجّلت إني استثمرت</button>"
            "<button class='ibtn ghost' onclick='resetInvest()'>تصفير التتبّع</button></div>"
            "<div class='inv-cap muted xs'>سقف المركز <b>يختلف لكل سهم</b> حسب قناعته وتوقّعاته ومخاطره "
            "(قاعدته <b class='n'>%d</b> %s) — لمّا يمتلئ نوقف الضخ فيه (إلا لو قوي) ونوجّه فلوسه للصناديق + "
            "إعادة موازنة. التتبّع محفوظ على جهازك فقط.</div>"
            "<script>window.__CUR=%s;window.__INV=%s;</script></div>"
            % (base, _CUR["symbol"], json.dumps(_CUR["symbol"]), json.dumps(data, ensure_ascii=False)))


def _newspaper(today, news_rows, opps, records, meta):
    """خانة اليوم كجريدة: خلاصة + أخبار بمؤشّر تأثير + فرص + تخفيضات + أبرز التحرّكات."""
    secs = []
    if today:
        rows = "".join(
            "<div class='th-row%s'><span class='te'></span><div>%s</div></div>"
            % (" rk" if ("مخاطر" in t or "مشكوك" in t) else "", t) for _e, t in today)
        secs.append("<div class='today'><div class='th-h'>خلاصة اليوم</div>%s</div>" % rows)

    if news_rows:
        col = {"positive": "fp-up", "negative": "fp-dn", "neutral": "muted"}
        ar = {"positive": "إيجابي", "negative": "سلبي", "neutral": "محايد"}
        rows = ""
        for n in news_rows[:8]:
            d = n.get("impact_direction", "neutral")
            rows += ("<div class='np-news'><span class='np-imp %s'></span>"
                     "<div class='np-h'>%s <span class='muted xs'>%s · %s</span></div></div>"
                     % (col.get(d, "muted"), _h(n.get("event_name", "")), _h(n.get("date", "")), ar.get(d, d)))
        secs.append("<div class='card2'><h4>أخبار اليوم وتأثيرها %s</h4>%s</div>" % (_i("news"), rows))

    cand = [r for r in opps if r.get("action") == "Candidate"][:5]
    if cand:
        def _rrow(r):
            rate = RATING_AR.get(r.get("rec_key"), "")
            na = r.get("num_analysts")
            rtxt = ("<span class='np-rate'>%s</span>" % _h(rate)) if rate else ""
            meta_t = "قناعة %s · نظرة %s%s" % (
                r.get("conviction_score") or "—",
                r.get("forward_outlook_score") if r.get("forward_outlook_score") is not None else "—",
                (" · %d محلل" % int(na)) if na else "")
            return ("<div class='np-row'><div class='np-rl'><b class='n'>%s</b>%s</div>"
                    "<span class='muted xs'>%s</span></div>" % (_h(r["ticker"]), rtxt, meta_t))
        rows = "".join(_rrow(r) for r in cand)
        secs.append("<div class='card2'><h4>فرص اليوم — رأي المحللين</h4>%s</div>" % rows)

    dn = [r for r in records if (not r.get("is_fund")) and (
        any("يخفّضون" in d for d in (r.get("forward_drivers") or []))
        or r.get("lifecycle_status") in ("Falling Conviction", "Fallen Angel"))][:6]
    if dn:
        rows = "".join(
            "<div class='np-row'><b class='n'>%s</b><span class='fp-dn xs'>%s</span></div>"
            % (_h(r["ticker"]), _h(next((d for d in (r.get("forward_drivers") or []) if "يخفّضون" in d),
                                        r.get("lifecycle_status") or "تراجع"))) for r in dn)
        secs.append("<div class='card2'><h4>انتبه — تقديرات/قناعة تنزل</h4>%s</div>" % rows)

    mv = meta.get("movers") or []
    if mv:
        rows = "".join(
            "<div class='np-row'><b class='n'>%s</b><span class='%s xs'>%s %s</span></div>"
            % (_h(m.get("ticker")), "fp-up" if m.get("direction") == "up" else "fp-dn",
               "▲" if m.get("direction") == "up" else "▼", _h(m.get("driver") or "")) for m in mv[:6])
        secs.append("<div class='card2'><h4>أبرز تحرّكات الترتيب %s</h4>%s</div>" % (_i("movers"), rows))

    if not secs:
        return "<p class='muted pad'>لا جديد اليوم.</p>"
    return "<h3 class='sec'>اليوم — جريدة محفظتك</h3>" + "".join(secs)


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
:root{--sage:#84B4A6;--sage16:color-mix(in oklab,#84B4A6 16%,transparent);--risk:#C0926E;
--bg:#0C0E13;--card:#13161B;--field:#15181E;--hair:rgba(255,255,255,.06);--sheen:inset 0 1px 0 rgba(255,255,255,.04);
--t1:#EEF1F5;--t2:#AEB6C2;--t3:#7B848F;--t4:#5E6670;
--s1:#7BA79A;--s2:#6A9086;--s3:#597971;--s4:#4B655F;--s5:#3D514C;--s6:#314140}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;min-height:100vh;background:#0C0E13;background-image:linear-gradient(180deg,#10131A,#0C0E13);background-attachment:fixed;
color:var(--t1);direction:rtl;font-family:'IBM Plex Sans Arabic',-apple-system,'SF Arabic','Segoe UI',Tahoma,Arial,sans-serif;line-height:1.65;font-size:15px;font-weight:400}
.wrap{max-width:780px;margin:0 auto;padding:16px 16px 92px}
.n{font-family:'IBM Plex Mono',ui-monospace,'SF Mono',Menlo,monospace;font-variant-numeric:tabular-nums;font-feature-settings:'tnum';direction:ltr;unicode-bidi:isolate;display:inline-block}
.muted{color:var(--t2)}.xs{font-size:11.5px}.sm{font-size:12.5px}.pad{padding:16px}
b{font-weight:600}
/* header */
.top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:4px}
.top h1{font-size:19px;margin:0;font-weight:700;display:flex;align-items:center;gap:9px}
.top h1::before{content:'';width:4px;height:19px;border-radius:3px;background:var(--sage);flex:none}
.sub{color:var(--t3);font-size:11.5px;margin-bottom:14px}
.btns{display:flex;gap:8px}
.ico{background:var(--field);border:1px solid var(--hair);color:var(--t2);border-radius:11px;padding:8px 13px;font-size:13px;
font-weight:500;cursor:pointer;text-decoration:none}
.ico:hover{color:var(--t1)}.ico.pri{background:var(--sage16);border-color:transparent;color:var(--sage)}
#updmsg{font-size:12px;color:var(--t2);margin:6px 0}
/* status strip (stats grid) */
.strip0{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;margin:10px 0 6px;background:var(--hair);
border:1px solid var(--hair);border-radius:13px;overflow:hidden;box-shadow:var(--sheen)}
.pill{background:var(--card);padding:11px 12px;font-size:10.5px;color:var(--t3);display:flex;flex-direction:column;gap:3px;border-radius:0}
.pill b{color:var(--t1);font-size:19px;font-weight:500;font-family:'IBM Plex Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums}
.pill.ok b{color:var(--sage)}
.pill.risk-High b,.pill.risk-Extreme b{color:var(--risk)}
.pill.risk-Low b{color:var(--sage)}
/* mode segmented (no background transition — color-mix↔transparent would freeze) */
.modebar{display:inline-flex;align-items:center;background:var(--field);border:1px solid var(--hair);border-radius:12px;padding:3px;margin:12px 0 0;gap:2px}
.mbl{font-size:11px;color:var(--t3);font-weight:500;padding:0 8px 0 6px}
.seg{font-size:12.5px;color:var(--t2);padding:7px 14px;border-radius:9px;text-decoration:none;font-weight:500}
.seg:hover{color:var(--t1)}.seg.on{background:var(--sage16);color:var(--sage);font-weight:600}
.cset{margin:6px 0 0}
/* today */
.today{background:var(--card);border:1px solid var(--hair);box-shadow:var(--sheen);border-radius:16px;padding:16px;margin:14px 0}
.th-h{font-size:11px;font-weight:600;color:var(--t3);margin-bottom:10px}
.th-row{display:flex;gap:10px;align-items:flex-start;margin:9px 0;font-size:13.5px;color:var(--t2)}
.th-row .te{flex:0 0 auto;width:7px;height:7px;border-radius:50%;background:#3A4049;margin-top:7px;font-size:0;overflow:hidden}
.th-row.rk .te{background:var(--risk)}
/* tabs (underline) */
/* شريط تنقّل سفلي زجاجي (زي التطبيقات) */
.tabs{position:fixed;bottom:0;left:0;right:0;z-index:30;display:flex;justify-content:center;gap:4px;
background:rgba(12,14,19,.78);backdrop-filter:blur(22px) saturate(1.3);-webkit-backdrop-filter:blur(22px) saturate(1.3);
border-top:1px solid var(--hair);padding:8px 12px calc(10px + env(safe-area-inset-bottom));margin:0}
.tabbtn{flex:1;max-width:118px;text-align:center;background:none;border:0;color:var(--t3);font-size:12.5px;font-weight:500;
padding:9px 6px;border-radius:12px;cursor:pointer;font-family:inherit;transition:color .2s ease,background .2s ease}
.tabbtn.on{color:var(--sage);background:var(--sage16);font-weight:600}
.tabpanel{display:none}.tabpanel.show{display:block;animation:glass .42s cubic-bezier(.22,.9,.3,1)}
@keyframes glass{from{opacity:0;transform:translateY(14px) scale(.985);filter:blur(7px)}to{opacity:1;transform:none;filter:blur(0)}}
h3.sec{font-size:15px;margin:22px 0 6px;font-weight:600}h3.sec .c{color:var(--t3);font-weight:400;font-size:12px}
h4{font-size:13px;margin:18px 0 8px;color:var(--t2);font-weight:600}
.lead{color:var(--t2);font-size:12.5px;margin:0 0 10px;line-height:1.6}
/* list rows */
.list{border:1px solid var(--hair);border-radius:14px;overflow:hidden;background:var(--card);box-shadow:var(--sheen)}
.lrow{display:flex;align-items:center;gap:11px;padding:12px 14px;border-top:1px solid var(--hair);cursor:pointer}
.lrow:first-child{border-top:0}.lrow:hover{background:rgba(255,255,255,.02)}
.rk{color:var(--t4);font-size:12px;min-width:16px;text-align:center;direction:ltr}
.hd{width:8px;height:8px;border-radius:50%;flex:0 0 auto;font-size:0;overflow:hidden}
.d-ok{background:var(--sage)}.d-unk{background:var(--t3)}.d-no{background:var(--risk)}
.lmain{flex:1;min-width:0}
.lt{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.lt b{font-size:15px;font-weight:600}
.nm{color:var(--t3);font-size:12px}
.kk{font-size:11px}.eg{font-size:10.5px;color:var(--t2);background:var(--field);border-radius:6px;padding:1px 7px}
.lsub{color:var(--t3);font-size:12px;margin-top:3px}
.tchips{font-size:12px;color:var(--t2);margin-top:5px;line-height:1.5}.tchips b{color:var(--t1);font-weight:400}
.cv{display:inline-flex;flex-direction:column;align-items:flex-end;gap:3px;flex:0 0 auto;min-width:38px}
.cv b{font-size:16px;font-weight:500}.cv i{display:block;height:3px;border-radius:3px;width:0}
.cv-hi b{color:var(--sage)}.cv-hi i{background:var(--sage)}
.cv-mid b{color:var(--s3)}.cv-mid i{background:var(--s3)}
.cv-lo b{color:var(--t2)}.cv-lo i{background:var(--t4)}
.cv-na{color:var(--t4)}.cv.mini{flex-direction:row;min-width:0}.cv.mini i{display:none}
.chev{color:var(--t4);font-size:13px;flex:0 0 auto}
.ldetail{display:none;border-top:1px solid var(--hair)}.ldetail.open{display:block}
.dgrid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:var(--hair)}
.dc{background:var(--card);padding:10px 12px}.dc span{display:block;color:var(--t3);font-size:11px}.dc b{font-size:13.5px}
.dc.wide{grid-column:1/-1}
/* THE WHY block */
.why{padding:13px 14px;background:rgba(255,255,255,.015);border-top:1px solid var(--hair)}
.wq{margin:9px 0;font-size:13px}.wq:first-child{margin-top:0}
.wq span{display:block;color:var(--sage);font-size:11px;font-weight:600;margin-bottom:2px}
.wq div{color:var(--t1);line-height:1.6}
.wfoot{margin-top:9px;border-top:1px solid var(--hair);padding-top:7px}
/* النظرة المستقبلية */
.fwd{padding:13px 14px;background:rgba(255,255,255,.015);border-top:1px solid var(--hair)}
.fwd-h{display:flex;align-items:baseline;gap:6px;flex-wrap:wrap}
.fwd-t{font-size:11px;color:var(--t3);font-weight:600}
.fwd-s{font-size:21px;color:var(--sage);font-weight:400}
.fwd-x{font-size:11px;color:var(--t3)}
.fwd-c{margin-inline-start:auto;font-size:10.5px;border-radius:7px;padding:2px 9px}
.fwd-high{background:var(--sage16);color:var(--sage)}
.fwd-med{background:var(--field);color:var(--t2)}
.fwd-low{background:var(--field);color:var(--t3)}
.fwd-d{font-size:12.5px;color:var(--t2);margin-top:7px;padding-inline-start:13px;position:relative}
.fwd-d::before{content:'';position:absolute;right:0;top:7px;width:5px;height:5px;border-radius:50%;background:var(--sage)}
.fwd-dis{font-size:10.5px;color:var(--t4);margin-top:10px;line-height:1.55;border-top:1px solid var(--hair);padding-top:8px}
.fpulse{font-size:12px;color:var(--t2);margin:0 0 10px;display:flex;align-items:center;gap:7px}
.fpulse .fp-up{color:var(--sage)}.fpulse .fp-dn{color:var(--risk)}
/* لوحة الاستثمار (مدموجة بالمحفظة) */
.invest{background:var(--card);border:1px solid var(--hair);box-shadow:var(--sheen);border-radius:16px;padding:16px;margin:12px 0 16px}
.inv-h{font-size:12px;color:var(--t2);font-weight:600;margin-bottom:9px}
.inv-in{width:100%;background:var(--field);border:1px solid var(--hair);color:var(--t1);border-radius:12px;padding:13px 15px;font-size:20px;text-align:center;outline:none;caret-color:var(--sage);font-family:'IBM Plex Mono',ui-monospace,monospace}
.inv-in:focus{border-color:color-mix(in oklab,var(--sage) 40%,var(--hair))}
.inv-cap{margin-top:11px;line-height:1.6}
.inv-b{display:flex;align-items:center;gap:8px;margin:13px 0 4px;font-size:13px;font-weight:600;border-top:1px solid var(--hair);padding-top:11px}
.inv-bk{width:9px;height:9px;border-radius:3px;flex:none}.inv-bn{flex:1}
.inv-b>b{color:var(--sage);font-weight:400}
.inv-row{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:12.5px;color:var(--t2);padding:4px 0;padding-inline-start:17px}
.inv-row>b{color:var(--t1);font-weight:400;white-space:nowrap}
.inv-prog{color:var(--t3);font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:10.5px;margin-inline-start:auto;margin-inline-end:10px;direction:ltr;unicode-bidi:isolate}
.inv-row .fp-dn,.inv-row .fp-up{font-size:10px;font-weight:600}
.inv-btns{display:flex;gap:8px;margin-top:13px}
.ibtn{flex:1;background:var(--sage16);color:var(--sage);border:0;border-radius:11px;padding:11px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit}
.ibtn:active{transform:scale(.97)}
.ibtn.ghost{background:var(--field);color:var(--t2);border:1px solid var(--hair)}
.inv-extra{margin-top:11px;background:var(--field);border:1px solid var(--hair);border-radius:11px;padding:10px 12px;font-size:12px;color:var(--sage);line-height:1.6}
/* جريدة اليوم */
.np-news{display:flex;align-items:flex-start;gap:11px;padding:9px 0;border-top:1px solid var(--hair)}
.np-news:first-child{border-top:0}
.np-imp{width:7px;height:7px;border-radius:50%;flex:none;margin-top:6px;background:var(--t3)}
.np-imp.fp-up{background:var(--sage)}.np-imp.fp-dn{background:var(--risk)}
.np-h{font-size:13px;color:var(--t1);line-height:1.55}
.np-row{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 0;border-top:1px solid var(--hair)}
.np-row:first-child{border-top:0}.np-row .fp-up{color:var(--sage)}.np-row .fp-dn{color:var(--risk)}
.np-rl{display:flex;align-items:center;gap:8px}
.np-rate{font-size:10.5px;border-radius:7px;padding:1px 8px;background:var(--sage16);color:var(--sage);font-weight:600;white-space:nowrap}
/* تفاصيل السهم داخل التوزيع: وزن + سقف + وقف + هدف */
.palc{display:flex;align-items:center;gap:9px;flex-wrap:wrap;padding:6px 14px;border-top:1px solid rgba(255,255,255,.03);font-size:12px}
.palc>.n:first-child{min-width:52px;font-weight:600;color:var(--t1)}
.palc-p{color:var(--t2);min-width:34px}
.palc-c{color:var(--t3)}.palc-c b{color:var(--t2);font-weight:400}
/* THE CHECK peers */
.peers{padding:12px 14px;background:rgba(255,255,255,.015);border-top:1px solid var(--hair)}
.pr2{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;gap:6px;padding:6px;font-size:12.5px;align-items:center}
.pr2 span{color:var(--t3);font-size:11px;text-align:left}
.pr2 b{text-align:left}.pr2>b:first-child{text-align:right}
.pr2.ph{border-bottom:1px solid var(--hair)}.pr2.ph b{color:var(--t3);font-weight:400}
.pr2.pself{background:rgba(132,180,166,.06);border-radius:8px}.pr2.pself>b:first-child{color:var(--sage)}
.pbest{color:var(--sage)!important;font-weight:600}
.vd{font-size:12.5px;color:var(--t1);background:var(--field);border-radius:7px;padding:2px 8px}
.hpnl{text-align:left;flex:0 0 auto}
.warn{color:var(--risk);font-size:11.5px;font-weight:600}
/* portfolio */
.plist{border:1px solid var(--hair);border-radius:14px;overflow:hidden;background:var(--card);box-shadow:var(--sheen)}
.prow{display:flex;justify-content:space-between;align-items:center;padding:13px 14px 4px;border-top:1px solid var(--hair)}
.prow:first-child{border-top:0}.pl{display:flex;align-items:center;gap:9px}.pl b{font-size:14px;font-weight:600}
.pbk{width:9px;height:9px;border-radius:3px;flex:none}
.pr b{font-size:23px;font-weight:400;color:var(--t1)}
.pbar{height:3px;border-radius:3px;margin:0 14px 2px;opacity:.9}
.phold{padding:0 14px 12px;margin-top:2px;color:var(--t3)}
/* desk note — صوت العقل المحترف */
.desknote{background:var(--card);border:1px solid var(--hair);box-shadow:var(--sheen);border-radius:14px;padding:14px 16px;margin-bottom:14px}
.dn-h{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:var(--t2);margin-bottom:10px}
.dn-h .c{font-weight:400;color:var(--t3);font-size:11.5px}
.dn-dot{width:7px;height:7px;border-radius:50%;background:var(--sage);flex:none;box-shadow:0 0 0 3px var(--sage16)}
.dn-line{font-size:13.5px;line-height:1.75;color:var(--t2);padding:7px 0;border-top:1px solid var(--hair)}
.dn-line:first-of-type{border-top:0}
.dn-lead{color:var(--t1);font-weight:500}
.dn-disc{margin-top:9px;font-size:10.5px;color:var(--t3);line-height:1.5}
/* regime — العقل العاقل */
.regime{background:var(--card);border:1px solid var(--hair);box-shadow:var(--sheen);border-radius:14px;padding:13px 15px;margin-bottom:14px;border-right:3px solid var(--t3)}
.regime.rg-crisis{border-right-color:var(--risk)}.regime.rg-opp{border-right-color:var(--sage)}
.rg-top{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.rg-dot{width:8px;height:8px;border-radius:50%;background:var(--t3);flex:none}
.rg-crisis .rg-dot{background:var(--risk)}.rg-opp .rg-dot{background:var(--sage)}
.rg-name{font-size:15px;font-weight:600;color:var(--t1)}
.rg-conf{font-size:11px;color:var(--t3);border:1px solid var(--hair);border-radius:20px;padding:1px 9px}
.rg-apply{margin-inline-start:auto;font-size:12.5px;color:var(--sage);text-decoration:none;font-weight:600}
.rg-ok{margin-inline-start:auto;font-size:12px;color:var(--t3)}
.rg-why{margin-top:7px;font-size:13px;line-height:1.65;color:var(--t2)}
.rg-disc{margin-top:8px;font-size:11px;color:var(--t3);line-height:1.5}
.regime.big .rgm-row{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}
.rgm{background:var(--field);border-radius:10px;padding:9px 6px;text-align:center}
.rgm span{display:block;font-size:10px;color:var(--t3);margin-bottom:3px;line-height:1.3}
.rgm b{font-size:16px;font-weight:400;color:var(--t1)}
.rg-sub{margin-top:13px;font-size:11px;color:var(--t3);letter-spacing:.04em}
.rg-sigs{margin:6px 0 0;padding:0;list-style:none}
.rg-sigs li{font-size:12.5px;color:var(--t2);padding:5px 0;border-top:1px solid var(--hair);line-height:1.5}
.rg-sigs li:first-child{border-top:0}
.rg-foot{margin-top:13px;font-size:12.5px;color:var(--t2);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rg-foot b{color:var(--t1)}
.cc-hint{margin:2px 0 8px}
.cc-row{display:flex;align-items:center;gap:8px;padding:6px 0;border-top:1px solid var(--hair)}
.cc-row:first-of-type{border-top:0}.cc-row b{font-size:13px;color:var(--t1)}
.cc-warn h4{color:var(--risk)}.cc-ok h4{color:var(--sage)}
/* bottleneck v2 */
.bn-intro{background:var(--card);border:1px solid var(--hair);box-shadow:var(--sheen);border-radius:14px;padding:14px 16px;font-size:13.5px;margin-bottom:14px;line-height:1.7;color:var(--t2)}
.bn2-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.bn2{background:var(--card);border:1px solid var(--hair);box-shadow:var(--sheen);border-radius:14px;padding:14px}
.bn2-h{display:flex;align-items:center;gap:8px;font-size:14.5px;font-weight:600}
.cd{width:7px;height:7px;border-radius:50%;flex:0 0 auto}.cd-hi{background:var(--sage)}.cd-mid{background:var(--t3)}
.bn2-idea{margin:6px 0 10px;line-height:1.6;color:var(--t2)}
.strip{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:11px}
.stg{font-size:10.5px;color:var(--t3);background:var(--field);border:1px solid var(--hair);border-radius:7px;padding:3px 8px}
.stg.on{background:var(--sage16);border-color:transparent;color:var(--sage);font-weight:600}
.bn-pick{background:transparent;border-top:1px solid var(--hair);padding-top:10px}
.bn-pick .big{font-size:17px;color:var(--t1)}
/* small cards / bars (more tab) */
.card2{background:var(--card);border:1px solid var(--hair);box-shadow:var(--sheen);border-radius:14px;padding:14px 16px;margin-bottom:10px}
.xbar{display:flex;align-items:center;gap:9px;margin:7px 0;font-size:12px}
.xbar span{width:96px;color:var(--t2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.xt{flex:1;background:var(--field);border-radius:5px;height:6px;overflow:hidden}
.xt i{display:block;height:100%;background:var(--sage)}
.srow{display:flex;align-items:center;gap:10px;padding:10px 14px;border-top:1px solid var(--hair)}
.srow:first-child{border-top:0}.srow b{font-size:13.5px;font-weight:600}.srow .fit{margin-right:auto;font-size:12px;color:var(--t2)}
.bt-line{font-size:13.5px;padding:4px 0 8px}
details.mini{font-size:12px}details.mini summary{cursor:pointer;color:var(--t2)}
.cav{margin:7px 16px 0;padding:0;color:var(--risk);font-size:12px}.cav li{margin:4px 0}
/* glossary marker + modal */
.i{position:relative;display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;border-radius:50%;
background:transparent;border:1px solid var(--hair);color:var(--t3);font-size:9.5px;font-weight:600;cursor:pointer;vertical-align:middle;flex:0 0 auto;line-height:1}
.i::after{content:'';position:absolute;inset:-11px}.i:hover{border-color:var(--sage);color:var(--sage)}
.modal{display:none;position:fixed;inset:0;background:rgba(6,8,12,.78);backdrop-filter:blur(2px);z-index:99;align-items:center;justify-content:center;padding:18px}
.box{background:var(--card);border:1px solid var(--hair);box-shadow:var(--sheen);border-radius:18px;max-width:430px;width:100%;padding:20px}
.box h3{font-size:17px;margin:0 0 12px;display:flex;justify-content:space-between;align-items:center;font-weight:600}
.box .x{cursor:pointer;color:var(--t2);font-size:22px;padding:0 4px}
.box .lbl{color:var(--sage);font-size:11px;font-weight:600;margin-top:12px}
.box .val{color:var(--t1);font-size:13.5px;margin-top:3px;line-height:1.6}
.box .ex{background:var(--field);border-radius:10px;padding:10px 12px;margin-top:7px;font-size:13px;color:var(--t2)}
footer{color:var(--t4);font-size:11.5px;margin-top:34px;text-align:center}
/* شريط البحث */
.search{position:relative;margin:12px 0 2px}
.search input{width:100%;background:var(--field);border:1px solid var(--hair);color:var(--t1);border-radius:12px;
padding:12px 14px;font-size:14px;font-family:inherit;outline:none;caret-color:var(--sage)}
.search input:focus{border-color:color-mix(in oklab,var(--sage) 40%,var(--hair))}
.search input::placeholder{color:var(--t3)}
#qx{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--t3);cursor:pointer;font-size:18px;padding:0 4px}
/* وضع المحترف — مخفي افتراضياً */
.pro-only{display:none}
body.pro .pro-only{display:block}
body.pro .top .ico[onclick*="pro"]{background:var(--sage16);color:var(--sage);border-color:transparent}
@media(max-width:620px){.bn2-grid{grid-template-columns:1fr}.ldetail.open{grid-template-columns:1fr 1fr}.wrap{padding:14px 13px 86px}}
@media(max-width:430px){.strip0{grid-template-columns:repeat(2,1fr)}}
/* ═══ موشن هادئ ولطيف (يُفعّل فقط مع JS وبدون reduce-motion؛ يتلاشى بأمان) ═══ */
.tabbtn,.mpill,.ico,.chev,.lrow,.bnc,.eg{transition:color .2s ease,transform .2s ease,border-color .2s ease}
.seg{transition:color .2s ease}
.ico:active,.tabbtn:active{transform:scale(.96)}
.lrow:hover{transform:translateX(-2px)}
body.anim .today,body.anim .list,body.anim .bn2,body.anim .card2,body.anim .plist,body.anim .acc,
body.anim .modebar,body.anim h3.sec,body.anim .bn-intro{
  opacity:0;transform:translateY(10px);transition:opacity .55s cubic-bezier(.2,.7,.2,1),transform .55s cubic-bezier(.2,.7,.2,1)}
body.anim .reveal{opacity:1!important;transform:none!important}
/* الأشرطة تكبر بنعومة عند الظهور */
body.anim .cv i,body.anim .sb i,body.anim .xt i,body.anim .track i,body.anim .pbar{transform:scaleX(0);transform-origin:right;transition:transform .7s cubic-bezier(.2,.8,.2,1)}
body.anim .reveal .cv i,body.anim .reveal .xt i,body.anim .reveal .track i,body.anim .reveal .pbar,body.anim .cv.go i{transform:scaleX(1)}
body.anim .reveal .cv i{transition-delay:.1s}
/* توسعة السطر بنعومة */
body.anim .ldetail{display:block;max-height:0;opacity:0;overflow:hidden;transition:max-height .4s ease,opacity .3s ease}
body.anim .ldetail.open{max-height:1600px;opacity:1}
/* ربح/خسارة — هادئ، باللون فقط بلا وميج صارخ */
.pnl-pos{color:var(--sage)}.pnl-neg{color:var(--risk)}
/* ═══ دونت توزيع المحفظة (الواجهة) — درجات الـ sage ═══ */
.dchart{display:flex;gap:18px;align-items:center;flex-wrap:wrap;justify-content:center;
  background:var(--card);border:1px solid var(--hair);box-shadow:var(--sheen);border-radius:16px;padding:18px 16px;margin:8px 0 16px}
.donut{width:182px;height:182px;flex:none}
.donut .ring-bg{stroke:var(--field)}
.donut .seg{stroke-dasharray:var(--dash);stroke-linecap:butt}
body.anim .donut .seg{animation:dgrow .95s cubic-bezier(.34,1,.5,1) both}
@keyframes dgrow{from{stroke-dasharray:0 100}to{stroke-dasharray:var(--dash)}}
.dc-t{fill:var(--t1);font-size:17px;font-weight:600;text-anchor:middle;dominant-baseline:middle;font-family:'IBM Plex Sans Arabic',sans-serif}
.dc-s{fill:var(--t3);font-size:9.5px;text-anchor:middle;dominant-baseline:middle;font-family:'IBM Plex Sans Arabic',sans-serif}
.dleg{display:grid;grid-template-columns:1fr 1fr;gap:9px 18px;flex:1;min-width:230px}
.dli{display:flex;align-items:center;gap:9px;font-size:12.5px}
.ddot{width:9px;height:9px;border-radius:3px;flex:none}
.dnm{color:var(--t2);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dpc{color:var(--t1);font-weight:400;font-family:'IBM Plex Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums;flex:none}
/* شريط نظرة-واحدة مكدّس */
.gbar{display:flex;height:8px;border-radius:5px;overflow:hidden;margin:2px 0 4px;border:1px solid var(--hair)}
.gbar i{display:block;height:100%}
@media(max-width:620px){.donut{width:158px;height:158px}}
@media(max-width:430px){.dleg{grid-template-columns:1fr;min-width:0}}
@media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}}
"""

JS = """
// بحث/فلترة الأسهم بالرمز
function filt(q){q=(q||'').trim().toUpperCase();
  var rows=document.querySelectorAll('.lrow'),any=false;
  for(var i=0;i<rows.length;i++){var b=rows[i].querySelector('.lt b'),t=b?b.textContent.toUpperCase():'';
    var show=!q||t.indexOf(q)>=0;rows[i].style.display=show?'':'none';if(show)any=true;
    var d=rows[i].nextElementSibling;if(d&&d.classList.contains('ldetail')&&!show)d.classList.remove('open');}
}
// عدّاد تصاعدي لطيف
function countUp(el){var t=parseFloat(el.getAttribute('data-c'));if(isNaN(t)){return;}
  var d=parseInt(el.getAttribute('data-d')||'0'),st=null,dur=650;
  function f(ts){if(!st)st=ts;var p=Math.min(1,(ts-st)/dur),e=1-Math.pow(1-p,3);
    el.textContent=(t*e).toFixed(d);if(p<1){requestAnimationFrame(f);}else{el.textContent=t.toFixed(d);}}
  requestAnimationFrame(f);}
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
// لوحة الاستثمار: قسّم المبلغ على التوزيع الذكي مع سقف تراكمي لكل سهم (محفوظ على الجهاز)
function _m(x){return Math.round(x).toLocaleString('en-US')+' '+(window.__CUR||'$');}
function _cum(){try{return JSON.parse(localStorage.getItem('inv_cum')||'{}');}catch(e){return {};}}
function _saveCum(c){try{localStorage.setItem('inv_cum',JSON.stringify(c));}catch(e){}}
function _split(){
  // cap-aware allocation for the amount in the box; each name has its OWN cap (nm.cap)
  var a=parseFloat((document.getElementById('invamt')||{}).value)||0;
  var D=window.__INV||[],cum=_cum(),names=[],extra=0;
  for(var i=0;i<D.length;i++){var b=D[i];
    if(b.lo>0){extra+=a*(b.lo/100);}   // bucket-level «غير موزّع» (caps bound) → funds/cash, never dropped
    for(var j=0;j<b.names.length;j++){var nm=b.names[j],cap=nm.cap||1e9,raw=a*(nm.p/100),give=raw,full=false,al=cum[nm.t]||0;
      if(!nm.f && !nm.s){var room=Math.max(0,cap-al);give=Math.min(raw,room);if(room<=0){full=true;}extra+=(raw-give);}
      names.push({t:nm.t,b:b.b,c:b.c,give:give,full:full,already:al,cap:cap,fund:nm.f,strong:nm.s,over:(nm.s&&al>=cap)});}
  }
  return {a:a,names:names,extra:extra};
}
function splitInvest(){
  var out=document.getElementById('invout');if(!out)return;
  var S=_split();if(S.a<=0){out.innerHTML='';return;}
  var byB={},order=[];
  S.names.forEach(function(n){if(!byB[n.b]){byB[n.b]={c:n.c,items:[],sum:0};order.push(n.b);}byB[n.b].items.push(n);byB[n.b].sum+=n.give;});
  var h='';
  order.forEach(function(bn){var b=byB[bn];
    h+='<div class="inv-b"><span class="inv-bk" style="background:'+b.c+'"></span><span class="inv-bn">'+bn+'</span><b class="n">'+_m(b.sum)+'</b></div>';
    b.items.forEach(function(n){
      var tag='';
      if(n.full){tag=' <span class="fp-dn">ممتلئ → للصناديق</span>';}
      else if(n.over){tag=' <span class="fp-up">قوي — تجاوز مسموح</span>';}
      var prog=n.fund?'':'<span class="inv-prog">'+_m(n.already)+'/'+_m(n.cap)+'</span>';
      h+='<div class="inv-row"><span class="n">'+n.t+'</span>'+prog+'<b class="n">'+_m(n.give)+tag+'</b></div>';
    });
  });
  // name-less buckets (كاش) still get their share — show it so the full amount is accounted for
  (window.__INV||[]).forEach(function(b){if((!b.names||!b.names.length)&&b.pct>0){var amt=S.a*(b.pct/100);
    if(amt>=0.5)h+='<div class="inv-b"><span class="inv-bk" style="background:'+b.c+'"></span><span class="inv-bn">'+b.b+'</span><b class="n">'+_m(amt)+'</b></div>';}});
  if(S.extra>0.5){h+='<div class="inv-extra">+ '+_m(S.extra)+' غير موزّع (أسهم ممتلئة + سقوف الخانات) → وجّهه للصناديق (ETF/كاش) وأعد الموازنة.</div>';}
  out.innerHTML=h;
}
function recordInvest(){
  var S=_split();if(S.a<=0){alert('اكتب المبلغ أول');return;}
  var cum=_cum();S.names.forEach(function(n){if(!n.fund && n.give>0){cum[n.t]=(cum[n.t]||0)+n.give;}});
  _saveCum(cum);
  var el=document.getElementById('invamt');if(el)el.value='';
  splitInvest();
  alert('سجّلت! حدّثنا كم وضعت بكل سهم — الأسهم الممتلئة بتتجاوز المرّة الجاية وفلوسها للصناديق.');
}
function resetInvest(){if(confirm('تصفير تتبّع كم استثمرت بكل سهم؟')){_saveCum({});splitInvest();}}
function exp(el){var d=el.nextElementSibling;if(!d||!d.classList.contains('ldetail'))return;
 var open=d.classList.toggle('open');var c=el.querySelector('.chev');if(c)c.textContent=open?'⌃':'⌄';}
function updateAll(b){
  if(location.protocol==='file:'){document.getElementById('updmsg').innerHTML='شغّل <b>python src/server.py</b> محلياً للتحديث الفوري.';return;}
  if(location.hostname.indexOf('github.io')>=0||location.hostname.indexOf('localhost')<0&&location.hostname.indexOf('127.0.0.1')<0){
    // المنصّة تتحدّث تلقائياً من السحابة (الماك مقفل) — هذا الزر يجلب أحدث نسخة منشورة
    document.getElementById('updmsg').innerHTML='تتحدّث <b>تلقائياً كل ~30 دقيقة</b> من السحابة — أجلب أحدث نسخة الآن…';
    b.style.opacity=.6;b.innerText='يجلب…';setTimeout(function(){location.reload(true);},900);return;}
  var o=b.innerText;b.style.opacity=.6;b.innerText='يحدّث…';
  document.getElementById('updmsg').innerText='يحدّث أسهمك + يفحص السوق...';
  fetch('/update').then(function(r){return r.json();}).then(function(d){
    document.getElementById('updmsg').innerText=d.ok?'تم':(d.summary||'خطأ');
    if(d.ok)setTimeout(function(){location.reload();},800);else{b.style.opacity=1;b.innerText=o;}
  }).catch(function(){document.getElementById('updmsg').innerText='تعذّر الاتصال بالخادم';b.style.opacity=1;b.innerText=o;});
}
/* ═══ موشن: كشف لطيف عند التمرير + تكبير الأشرطة (يحترم reduce-motion) ═══ */
(function(){
  try{ if(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return; }catch(e){}
  document.body.classList.add('anim');
  var sels='.today,.list,.bn2,.card2,.plist,.acc,.dchart,.modebar,.bn-intro,h3.sec';
  var io=new IntersectionObserver(function(es){es.forEach(function(e){
    if(e.isIntersecting){e.target.classList.add('reveal');
      e.target.querySelectorAll('.cnt').forEach(countUp);io.unobserve(e.target);}});},
    {threshold:.1,rootMargin:'0px 0px -30px 0px'});
  function wire(root){(root||document).querySelectorAll(sels).forEach(function(el){io.observe(el);});}
  wire();
  // count up any numbers already on screen (above the fold)
  setTimeout(function(){document.querySelectorAll('.reveal .cnt,.strip0 .cnt,.dchart .cnt').forEach(countUp);},120);
  // when a tab becomes visible, reveal its freshly-shown content + grow its bars
  window.addEventListener('click',function(ev){
    var b=ev.target.closest && ev.target.closest('.tabbtn'); if(!b) return;
    setTimeout(function(){var p=document.querySelector('.tabpanel.show'); if(p){p.querySelectorAll(sels).forEach(function(el){el.classList.add('reveal');el.querySelectorAll('.cnt').forEach(countUp);});}},30);
  });
})();
"""


def _conf_ar(c):
    return {"HIGH": "ثقة عالية", "MED": "ثقة متوسطة", "LOW": "ثقة منخفضة"}.get(c, c or "")


_RISK_AR = {"Low": "منخفضة", "Medium": "متوسطة", "High": "مرتفعة", "Extreme": "قصوى"}


def _regime_cls(rec):
    return "rg-crisis" if rec == "conservative" else ("rg-opp" if rec == "aggressive" else "rg-norm")


def _regime_apply(rg, active):
    if rg.get("recommended_mode") == active:
        return "<span class='rg-ok'>أنت على الوضع الموصى به</span>"
    return ("<a class='rg-apply' href='%s'>طبّق وضع %s ←</a>"
            % (_h(rg.get("recommended_file", "index.html")), _h(rg.get("recommended_mode_ar", ""))))


def _regime_banner(meta):
    """شريط هادئ أعلى «محفظتي»: وضع السوق + الوضع الموصى به. إضافة — والقرار يبقى لك."""
    rg = meta.get("regime")
    if not rg:
        return ""
    return (
        "<div class='regime %s'>"
        "<div class='rg-top'><span class='rg-dot'></span>"
        "<span class='rg-name'>%s</span><span class='rg-conf'>%s</span>%s</div>"
        "<div class='rg-why'>%s</div>"
        "<div class='rg-disc'>%s</div></div>"
        % (_regime_cls(rg.get("recommended_mode")), _h(rg.get("regime", "")),
           _conf_ar(rg.get("confidence")), _regime_apply(rg, meta.get("active_mode")),
           _h(rg.get("why", "")), _h(rg.get("disclaimer", "")))
    )


def _regime_detail(meta):
    """القراءة الكاملة لوضع السوق — قلب «نبض السوق»: الإشارات + الأرقام + التوصية."""
    rg = meta.get("regime")
    if not rg:
        return "<p class='muted xs pad'>قراءة السوق غير متاحة في هذا التشغيل.</p>"
    m = rg.get("metrics") or {}

    def metric(lbl, val):
        return "<div class='rgm'><span>%s</span><b class='n'>%s</b></div>" % (lbl, val)
    pe = m.get("med_fwd_pe")
    pe = ("%.0f" % pe) if isinstance(pe, (int, float)) else "—"
    metrics = (metric("مخاطر السوق", _RISK_AR.get(str(m.get("market_risk")), str(m.get("market_risk") or "—")))
               + metric("الازدحام", "%d%%" % round((m.get("crowd_pct") or 0) * 100))
               + metric("وسيط P/E آجل", pe)
               + metric("فرص رخيصة", "%d%%" % round((m.get("candidate_pct") or 0) * 100)))
    vix, ys = m.get("vix"), m.get("yield_spread")
    bd = m.get("breadth_down")
    extra_m = ""
    if isinstance(vix, (int, float)):
        extra_m += metric("VIX (الخوف)", "%.0f" % vix)
    if isinstance(ys, (int, float)):
        extra_m += metric("منحنى العائد" + (" (مقلوب)" if m.get("yield_inverted") else ""), "%+.2f" % ys)
    hy = m.get("hy_spread")
    if isinstance(hy, (int, float)):
        extra_m += metric("فروقات الائتمان", "%.1f%%" % hy)
    if isinstance(bd, (int, float)):
        extra_m += metric("اتساع الهبوط", "%d%%" % round(bd * 100))
    if extra_m:
        metrics += extra_m
    sigs = rg.get("signals") or []
    sig_html = (("<ul class='rg-sigs'>" + "".join("<li>%s</li>" % _h(s) for s in sigs) + "</ul>")
                if sigs else "<p class='muted xs'>لا إشارات صارخة — وضع هادئ، التوازن يكفي.</p>")
    return (
        "<div class='regime big %s'>"
        "<div class='rg-top'><span class='rg-dot'></span><span class='rg-name'>%s</span>"
        "<span class='rg-conf'>%s</span></div>"
        "<div class='rg-why'>%s</div>"
        "<div class='rgm-row'>%s</div>"
        "<div class='rg-sub'>ما رصدناه</div>%s"
        "<div class='rg-foot'>الوضع الموصى به: <b>%s</b> %s</div>"
        "<div class='rg-disc'>%s</div></div>"
        % (_regime_cls(rg.get("recommended_mode")), _h(rg.get("regime", "")),
           _conf_ar(rg.get("confidence")), _h(rg.get("why", "")), metrics, sig_html,
           _h(rg.get("recommended_mode_ar", "")), _regime_apply(rg, meta.get("active_mode")),
           _h(rg.get("disclaimer", "")))
    )


def _desk_note_card(meta):
    """«صوت العقل المحترف»: مذكّرة مكتبٍ أول-شخص — يقرأ اللوح ويقول ما يهمّ، بأرقام حقيقية."""
    dn = meta.get("desk_note") or {}
    lines = dn.get("lines") or []
    if not lines:
        return ""
    items = "".join("<div class='dn-line%s'>%s</div>"
                    % ((" dn-lead" if i == 0 else ""), _h(t)) for i, t in enumerate(lines))
    disc = _h(dn.get("disclaimer", ""))
    return ("<div class='desknote'>"
            "<div class='dn-h'><span class='dn-dot'></span>قراءة العقل <span class='c'>(يفكّر لك كل تشغيل)</span></div>"
            "%s<div class='dn-disc'>%s</div></div>" % (items, disc))


def _crowd_cheap(records):
    """عمودان قابلان للتنفيذ: أسماء مزدحمة (طاردها أقل) مقابل مرشّحين رخيصين."""
    inv = [r for r in records if not r.get("is_fund")
           and r.get("investable", True) and r.get("action") != "Avoid"]
    crowded = sorted([r for r in inv if r.get("crowded_late") or r.get("popular_not_cheap")],
                     key=lambda r: (r.get("rank_score") or 0), reverse=True)
    cheap = sorted([r for r in inv if r.get("action") == "Candidate"],
                   key=lambda r: (r.get("conviction_score") or 0), reverse=True)

    def col(title, rows, hint, kind):
        if not rows:
            body = "<p class='muted xs'>لا يوجد الآن.</p>"
        else:
            body = "".join("<div class='cc-row'><b>%s</b>%s</div>"
                           % (_h(r["ticker"]), _name_sub(r["ticker"], r.get("name", "")))
                           for r in rows[:7])
        return ("<div class='card2 cc-%s'><h4>%s</h4>"
                "<div class='muted xs cc-hint'>%s</div>%s</div>" % (kind, title, hint, body))
    return ("<div class='card2-wrap'>%s%s</div>"
            % (col("مزدحمة — طاردها أقل", crowded, "ارتفعت كثيراً وصارت مكتظة/مكلفة", "warn"),
               col("مرشّحون رخيصون", cheap, "جودة بسعرٍ معقول الآن", "ok")))


def build(records, buckets, portfolio_rows, news_rows, political_rows, meta, cfg):
    app = (cfg.get("app", {}) or {})
    name = app.get("name", "مرصد الأسهم")
    _c = (cfg.get("currency", {}) or {})            # عملة العرض (الريال) للمبالغ والسقوف
    _CUR["symbol"] = _c.get("symbol", "$")
    try:
        _CUR["rate"] = float(_c.get("usd_rate", 1.0) or 1.0)
    except Exception:
        _CUR["rate"] = 1.0
    top_n = (cfg.get("output", {}) or {}).get("top_n_dashboard", 20)

    _hmode = ((cfg.get("halal", {}) or {}).get("mode") or "gate").lower()

    def _vis(r):
        if _hmode == "info":
            return r.get("action") != "Avoid"   # info: show all (incl. haram, flagged) — Avoid = weak only
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
    top_cands = [r for r in ranked if r.get("action") == "Candidate"][:3]
    if _hmode == "info" and top_cands:
        names = "، ".join(_h(r["ticker"]) for r in top_cands)
        today.append(("🎯", "أقوى المرشّحين بالجودة: <b class='n'>%s</b> — <b>تأكّد حلالهم على Zoya قبل الشراء</b>." % names))
    elif pass_cands:
        today.append(("🟢", "أقوى مرشّح حلال مؤكّد: <b class='n'>%s</b> (قناعة %s)." % (
            _h(pass_cands[0]["ticker"]), pass_cands[0].get("conviction_score"))))
    else:
        today.append(("🔍", "لا مرشّح حلال <b>مؤكّد</b> اليوم. الأقوى للتأكيد على Zoya/Musaffa: <b class='n'>%s</b>." % "، ".join(strong_unknown)))
    today.append(("📊", "مخاطر السوق: <b>%s</b>%s" % (
        _h(RISK_AR.get(risk, risk)),
        (" · ⚠️ %d سهم ببيانات مشكوكة استُبعدت." % suspect_n) if suspect_n else ".")))

    status = (
        "<div class='strip0'>"
        "<span class='pill'><b class='n cnt' data-c='%d'>%d</b> في نطاق البحث</span>"
        "<span class='pill ok'><b class='n cnt' data-c='%d'>%d</b> حلال مؤكّد</span>"
        "<span class='pill'><b class='n cnt' data-c='%d'>%d</b> تحتاج تأكيد</span>"
        "<span class='pill'><b class='n cnt' data-c='%d'>%d</b> بياناتها حديثة</span>"
        "</div>" % (len(visible), len(visible), h_pass, h_pass, h_unknown, h_unknown,
                   fc.get("FRESH", 0), fc.get("FRESH", 0))
    )

    # tab panels — محفظتي = command center (mode + invest amount + smart allocation + positions);
    # اليوم = newspaper; البحث = ranked research with the bottleneck lens folded in.
    # search/command bar — filters the research stock lists by ticker (lives in البحث)
    search = ("<div class='search'><input id='q' autocomplete='off' spellcheck='false' "
              "placeholder='🔍 ابحث عن سهم (مثال: NVDA)…' oninput='filt(this.value)'>"
              "<span id='qx' onclick=\"document.getElementById('q').value='';filt('')\">×</span></div>")
    _opp_lead = (
        ("<p class='lead'><b>الترتيب بالجودة (القناعة)</b> — النقطة قراءة شرعية تقريبية، "
         "تأكّد الحلال على Zoya سهم سهم. الرقم على اليسار = القناعة %s.</p>" % _i("conviction"))
        if _hmode == "info" else
        ("<p class='lead'>اضغط أي سهم تفتح تفاصيله · الرقم على اليسار = القناعة %s.</p>" % _i("conviction")))
    researched = [r for r in ranked if not r.get("is_fund")]
    tab_opp = (
        "<div id='t-opp' class='tabpanel'>"
        + search
        + "<h3 class='sec'>أقوى الفرص <span class='c'>(مرتّبة بالجودة)</span></h3>%s" % _opp_lead
        + _stock_list(opps)
        + ("<h3 class='sec'>كل الأسهم المبحوثة <span class='c'>(%d · اضغط أيّ سهم للبيانات)</span></h3>"
           % len(researched))
        + "<p class='lead muted xs'>كل ما بحثناه وجمعناه — اضغط السهم تفتح القناعة والمخاطر والنظرة المستقبلية والبيانات.</p>"
        + _stock_list(researched)
        + "</div>"
    )
    tab_port = (
        "<div id='t-port' class='tabpanel show'>"
        + _desk_note_card(meta)
        + _regime_banner(meta)
        + _mode_bar(meta)
        + _invest_panel(portfolio_rows, cfg, records)
        + _fwd_pulse(records)
        + _alloc_donut(portfolio_rows, meta)
        + "<h3 class='sec'>التوزيع الذكي %s</h3>" % _i("portfolio")
        + _portfolio_list(portfolio_rows, records, cfg)
        + "<h3 class='sec'>مراكزي الحالية</h3>"
        + _holdings_list(he)
        + "</div>"
    )
    tab_today = (
        "<div id='t-today' class='tabpanel'>"
        + _newspaper(today, news_rows, opps, records, meta)
        + "</div>"
    )
    tab_more = (
        "<div id='t-more' class='tabpanel'>"
        "<h3 class='sec'>نبض السوق <span class='c'>(قراءة العقل العاقل)</span></h3>"
        + _regime_detail(meta)
        + "<h3 class='sec'>مزدحم مقابل رخيص</h3>"
        + _crowd_cheap(visible)
        + "<h3 class='sec'>📈 التعرّض %s</h3><div class='card2-wrap'>%s</div>" % (_i("exposure"), _exposure_compact(visible))
        + "<h3 class='sec'>عنق الزجاجة عبر القطاعات %s</h3>" % _i("bottleneck")
        + _bottleneck_v2(meta.get("bottlenecks") or [])
        + "<h4>🧪 اختبار بأثر رجعي %s</h4>%s" % (_i("backtest"), _backtest_compact(meta.get("backtest")))
        + _not_inv_compact(buckets.get("not_investable", []))
        + "<h4>📰 أثر الأخبار %s</h4>%s" % (_i("news"), _news_compact(news_rows))
        + "<h4>🏛️ النشاط السياسي %s</h4>%s" % (_i("political"), _political_compact(political_rows))
        + "<h4>📡 إشارات المؤثرين %s</h4><div class='muted xs'>إشارة ضعيفة للمراجعة فقط · لأحدث توصياتهم قُل لكلود «شوف المؤثرين».</div>%s" % (
            _i("signals"), _signals_compact(meta.get("signals_rows") or []))
        + "</div>"
    )

    tabs = (
        "<div class='tabs'>"
        "<button class='tabbtn on' onclick=\"tab('t-port',this)\">محفظتي</button>"
        "<button class='tabbtn' onclick=\"tab('t-today',this)\">اليوم</button>"
        "<button class='tabbtn' onclick=\"tab('t-opp',this)\">البحث</button>"
        "<button class='tabbtn' onclick=\"tab('t-more',this)\">المزيد</button>"
        "</div>"
    )

    src_txt = _h(meta.get("data_source", "yfinance"))
    header = (
        "<div class='top'><h1>%s</h1>"
        "<div class='btns'>"
        "<button class='ico pri' onclick='updateAll(this)'>حدّث</button></div></div>"
        "<div class='sub'>منصّة بحث شخصية — بحث وليست توصية · المصدر: %s · آخر فحص %s</div>"
        "<div id='updmsg'></div>" % (_h(name), src_txt, _h(meta.get("generated_at")))
    )

    modal = (
        "<div class='modal' id='gm'><div class='box'>"
        "<h3><span id='gt'></span><span class='x' onclick='gc()'>×</span></h3>"
        "<div class='lbl'>وش يعني؟</div><div class='val' id='gw'></div>"
        "<div class='lbl'>الفايدة</div><div class='val' id='gb'></div>"
        "<div class='lbl'>مثال</div><div class='ex' id='ge'></div></div></div>"
    )

    # zero-emoji identity: strip pictographs from all visible content + glossary text,
    # leave the JS code untouched (its chevrons ⌃⌄ are functional and preserved anyway)
    content = _strip_emoji(
        header + status + tabs
        + tab_port + tab_today + tab_opp + tab_more
        + "<footer>%s · يُولَّد محلياً · القرار والمسؤولية عليك</footer>" % _h(name)
        + modal)
    body = content + "<script>var GL=%s;%s</script>" % (
        _strip_emoji(json.dumps(GLOSSARY, ensure_ascii=False)), JS)

    return ("<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<link rel='preconnect' href='https://fonts.googleapis.com'>"
            "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
            "<link href='https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@300;400;500;600;700"
            "&family=IBM+Plex+Mono:wght@300;400;500;600&display=swap' rel='stylesheet'>"
            "<title>%s</title><style>%s</style></head><body><div class='wrap'>%s</div></body></html>"
            % (_h(name), CSS, body))
