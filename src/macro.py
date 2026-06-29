"""
macro.py — إشارات كلّية حيّة عبر FMP (يعمل من السحابة — ليس محجوباً مثل FRED، ويستخدم
مفتاح FMP الموجود أصلاً، بلا مفتاح جديد):
  • VIX (مؤشّر الخوف) — /stable/quote?symbol=^VIX
  • منحنى العائد (فارق 10y−2y) — /stable/treasury-rates. انعكاسه (سالب) إشارةُ ركودٍ كلاسيكية.

تُغذّي «العقل العاقل» بقراءةٍ مباشرة للخوف ولضغط منحنى العائد بدل الاعتماد على الأخبار وحدها،
فيفرّق أنواع الضغط ويؤكّد «اشترِ وقت الخوف» بإشارة سوقٍ حقيقية. سلسلة أمان: جلب فاشل →
آخر قيمة محفوظة → وإن غابت None (والعقل يكمّل بالأخبار). لا مفتاح جديد، لا تبعية هشّة.

ملاحظة صدق: فارق 10y−2y ليس فارق ائتمان الشركات (HY OAS) — بل مقياس ركود/ضغطٍ قريب منه
ومتاح مجاناً وموثوق من السحابة. فارق HY الحقيقي يحتاج مفتاح FRED (إضافة اختيارية لاحقاً).
"""

import json
import os

from config_loader import state_dir
from schema import now_utc, iso, now_local

_BASE = "https://financialmodelingprep.com/stable"
_CACHE = "macro.json"
_UA = "Mozilla/5.0 (compatible; mazer-research/1.0)"


def _get(path, key, timeout=15):
    import requests
    sep = "&" if "?" in path else "?"
    url = "%s%s%sapikey=%s" % (_BASE, path, sep, key)
    resp = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _vix_rank(v):
    return 3 if v >= 40 else (2 if v >= 28 else (1 if v >= 20 else 0))


def _path(cfg):
    return os.path.join(state_dir(cfg), _CACHE)


def _load(cfg):
    try:
        with open(_path(cfg), encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else None
    except Exception:
        return None


def _fresh(cached, max_age_h):
    ts = (cached or {}).get("fetched_local")
    if not ts:
        return False
    try:
        then = now_local().strptime(ts, "%Y-%m-%d %H:%M")
        now = now_local().replace(tzinfo=None)
        return (now - then).total_seconds() < max_age_h * 3600
    except Exception:
        return False


def signals(cfg=None, timeout=15, max_age_h=6, persist=True):
    """يرجّع dict إشارات كلّية أو None. يَستعمل كاشاً طازجاً (<max_age_h) قبل الجلب."""
    cfg = cfg or {}
    key = ((cfg.get("data", {}) or {}).get("fmp_api_key") or "").strip()
    cached = _load(cfg)
    if cached and _fresh(cached, max_age_h):
        return _derive(cached)
    if not key:                                         # بلا مفتاح → fallback لآخر كاش، وإلا None
        return _derive(cached) if cached else None

    out = None
    try:
        q = _get("/quote?symbol=%5EVIX", key, timeout)
        vix = (q[0] if isinstance(q, list) and q else {}) or {}
        vix_px = vix.get("price")
        vix_avg50 = vix.get("priceAvg50")

        tr = _get("/treasury-rates", key, timeout)       # مصفوفة بتواريخ تنازلية
        rows = [r for r in (tr or []) if isinstance(r, dict)
                and isinstance(r.get("year2"), (int, float)) and isinstance(r.get("year10"), (int, float))]
        spread = (rows[0]["year10"] - rows[0]["year2"]) if rows else None
        spread_prior = (rows[5]["year10"] - rows[5]["year2"]) if len(rows) > 5 else (
            (rows[-1]["year10"] - rows[-1]["year2"]) if rows else None)

        if isinstance(vix_px, (int, float)):
            out = {"vix": round(vix_px, 2),
                   "vix_avg50": round(vix_avg50, 2) if isinstance(vix_avg50, (int, float)) else None,
                   "yield_spread": round(spread, 2) if isinstance(spread, (int, float)) else None,
                   "yield_spread_prior": round(spread_prior, 2) if isinstance(spread_prior, (int, float)) else None,
                   "fetched_local": now_local().strftime("%Y-%m-%d %H:%M"),
                   "updated_utc": iso(now_utc())}
            if persist:
                try:
                    with open(_path(cfg), "w", encoding="utf-8") as f:
                        json.dump(out, f, ensure_ascii=False, indent=1)
                except Exception:
                    pass
    except Exception as e:
        print(f"  macro (FMP) fetch failed: {e}")

    if out is None:
        out = cached
    return _derive(out) if out else None


def _derive(d):
    """يضيف stress_rank + الاتجاه + وصفاً عربياً من VIX ومنحنى العائد."""
    if not d:
        return None
    d = dict(d)
    vix = d.get("vix")
    avg50 = d.get("vix_avg50")
    spread = d.get("yield_spread")
    prior = d.get("yield_spread_prior")

    d["stress_rank"] = _vix_rank(vix or 0)
    # اتجاه الخوف: VIX نسبةً لمتوسّطه ٥٠ يوماً (فوقه = متوتّر/يصعد، تحته = يهدأ)
    if isinstance(vix, (int, float)) and isinstance(avg50, (int, float)) and avg50 > 0:
        d["vix_dir"] = "rising" if vix > avg50 * 1.05 else ("falling" if vix < avg50 * 0.95 else "flat")
    else:
        d["vix_dir"] = "flat"
    d["inverted"] = isinstance(spread, (int, float)) and spread < 0
    # اتساع/تضيّق الفارق
    if isinstance(spread, (int, float)) and isinstance(prior, (int, float)):
        d["spread_dir"] = "widening" if spread > prior + 0.05 else ("narrowing" if spread < prior - 0.05 else "flat")
    else:
        d["spread_dir"] = "flat"
    d["easing"] = (d["vix_dir"] == "falling")
    d["rising"] = (d["vix_dir"] == "rising")

    lvl = {0: "هادئ", 1: "مرتفع قليلاً", 2: "ضغط", 3: "أزمة"}[d["stress_rank"]]
    dirw = {"rising": "ويصعد", "falling": "وينحسر", "flat": "ومستقر"}[d["vix_dir"]]
    curve = ""
    if isinstance(spread, (int, float)):
        curve = (" · منحنى العائد %s (10y−2y = %+.2f)"
                 % (("مقلوب — تحذير ركود" if d["inverted"] else "طبيعي"), spread))
    d["label_ar"] = "الخوف %s %s — VIX %s%s" % (lvl, dirw, _num(vix), curve)
    return d


def _num(x):
    return ("%.1f" % x) if isinstance(x, (int, float)) else "—"
