# -*- coding: utf-8 -*-
"""
universe.py — "الكون": قائمة الأسهم اللي يصطاد منها النظام.

الفكرة: نبدأ بقائمة منتقاة من شركات النمو متوسطة/كبيرة الحجم عبر القطاعات
(منطقة "الصيد" — مو القمار الصغير ولا العمالقة المطيّرة)، والفلتر يطحنها
لـ ٢-٣ أسماء ممتازة.

تقدر توسّعها بنفسك: أضف رموز (tickers) للقوائم، أو شغّل build_universe.py
لجلب آلاف الرموز من قائمة SEC الرسمية.

ملاحظة: وجود السهم هنا ≠ توصية. هذي فقط نقطة البداية للبحث.
"""

# قائمة منتقاة عبر القطاعات (تتوسّع مع الوقت)
SEED_UNIVERSE = [
    # ── أشباه الموصلات / عتاد AI (mid-cap نمو) ──
    "MRVL", "ARM", "MU", "ON", "MPWR", "LSCC", "ALGM", "SITM", "RMBS",
    "AMBA", "CRDO", "ALAB", "QCOM", "SWKS", "QRVO", "ENTG", "ONTO", "ACLS",
    "AEHR", "POWI", "DIOD", "SLAB", "FORM", "COHR", "LITE",
    # ── برمجيات / سحابة / أمن سيبراني ──
    "CRWD", "ZS", "S", "NET", "DDOG", "SNOW", "MDB", "PANW", "FTNT", "OKTA",
    "TEAM", "HUBS", "NOW", "WDAY", "TWLO", "GTLB", "FROG", "ESTC", "CFLT",
    "BILL", "PCTY", "PAYC", "APP", "DOCN", "BRZE", "TENB", "RPD", "PATH",
    "ASAN", "MNDY", "SMAR", "FROG", "AI", "PLTR", "U", "DV",
    # ── فنتك / مدفوعات ──
    "ADYEY", "GPN", "FOUR", "TOST", "FLYW", "AFRM", "SOFI", "NU", "STNE",
    "PAGS", "MELI", "GLOB", "WISE",
    # ── إنترنت / استهلاكي نمو ──
    "ABNB", "DASH", "RBLX", "PINS", "SHOP", "ETSY", "CHWY", "CART", "DUOL",
    "SE", "CPNG", "RDDT", "SPOT", "DKNG", "TTD", "ROKU", "PTON",
    # ── صناعي / طاقة نظيفة / فضاء ──
    "RKLB", "ASTS", "ACHR", "JOBY", "ENPH", "FSLR", "RUN", "SHLS", "NXT",
    "PWR", "BWXT", "HEI", "AXON", "PCAR", "GNRC", "VRT", "CLS", "FIX",
    "STRL", "POWL", "STM", "STEM", "BE", "OKLO", "SMR", "GEV",
    # ── صحة / تقنية حيوية / أجهزة طبية ──
    "ISRG", "DXCM", "PODD", "BSX", "RMD", "VEEV", "DOCS", "HIMS", "TEM",
    "TNDM", "SHC", "INSP", "NARI", "GKOS", "IDXX", "ALNY", "NTRA", "EXAS",
    # ── استهلاكي / علامات نمو ──
    "CAVA", "WING", "CMG", "DECK", "ELF", "CELH", "TXRH", "DPZ", "FND",
    "ANF", "BROS", "SG", "KVYO", "ONON", "BIRK",
    # ── بيانات / أنظمة / متفرقات نمو ──
    "MSCI", "FICO", "SPGI", "VRSN", "TYL", "MANH", "GDDY", "WIX", "ZI",
    "DT", "PGR", "AXON", "TDG", "WST", "ENSG", "MEDP", "LNTH",
]

def _dedup(lst):
    seen, out = set(), []
    for t in lst:
        u = str(t).strip().upper()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def get_universe():
    """
    لو موجود ملف الكون الكبير (universe_data.txt من build_universe.py) يستخدمه،
    وإلا يرجع للقائمة المنتقاة المدمجة.
    """
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    big = os.path.join(here, "universe_data.txt")
    if os.path.exists(big):
        try:
            with open(big, encoding="utf-8") as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]
            if lines:
                return _dedup(lines)
        except Exception:
            pass
    return _dedup(SEED_UNIVERSE)


if __name__ == "__main__":
    u = get_universe()
    print(f"حجم الكون: {len(u)} سهم")
    print(", ".join(u))
