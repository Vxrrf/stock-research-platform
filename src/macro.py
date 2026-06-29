"""
macro.py — إشارات كلّية حيّة من FRED (تنزيل CSV بلا مفتاح — مجاني وموثوق في السحابة):
  • VIX (VIXCLS)            — مقياس الخوف.
  • فروقات ائتمان العائد العالي (BAMLH0A0HYM2, HY OAS) — أصدق مقياس ضغطٍ نظامي:
    تتّسع قبل/أثناء الأزمات وتضيق في التعافي.

تُغذّي «العقل العاقل» بقراءةٍ مباشرة للضغط واتجاهه بدل الاعتماد على الأخبار وحدها — فيفرّق
بين أنواع الضغط ويؤكّد «اشترِ وقت الخوف» بإشارة سوقٍ حقيقية. سلسلة أمان: جلب فاشل →
يستعمل آخر قيمة محفوظة → وإن غابت يرجع None (والعقل يكمّل بالأخبار). بلا مفتاح، بلا تبعية هشّة.
"""

import datetime as _dt
import json
import os

from config_loader import state_dir
from schema import now_utc, iso, now_local

_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s"
_SERIES = {"vix": "VIXCLS", "hy": "BAMLH0A0HYM2"}
_CACHE = "macro.json"
_UA = "Mozilla/5.0 (compatible; mazer-research/1.0)"


def _fetch_series(series_id, timeout=15, days=200):
    # LIMIT to recent history (cosd) — the full multi-decade series is a huge CSV that times out.
    start = (now_local().replace(tzinfo=None) - _dt.timedelta(days=days)).strftime("%Y-%m-%d")
    url = _FRED % (series_id, start)
    text = None
    # PRIMARY: curl — reliable on macOS AND CI; some hosts block Python's socket stack to FRED.
    try:
        import subprocess
        r = subprocess.run(["curl", "-sS", "--max-time", str(timeout), "-A", _UA, url],
                           capture_output=True, text=True, timeout=timeout + 5)
        if r.returncode == 0 and r.stdout.strip():
            text = r.stdout
    except Exception:
        text = None
    # FALLBACK: requests (same client the platform uses for Finnhub/FMP).
    if text is None:
        import requests
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
        resp.raise_for_status()
        text = resp.text
    rows = []
    for line in text.splitlines()[1:]:                  # skip header
        parts = line.split(",")
        if len(parts) < 2:
            continue
        v = parts[1].strip()
        if v in ("", "."):                              # FRED uses '.' for missing
            continue
        try:
            rows.append(float(v))
        except ValueError:
            continue
    return rows                                         # chronological values only


def _dir(rows, lookback=5):
    if not rows:
        return None, "flat"
    latest = rows[-1]
    prior = rows[-1 - lookback] if len(rows) > lookback else rows[0]
    if latest > prior * 1.02:
        d = "rising"
    elif latest < prior * 0.98:
        d = "falling"
    else:
        d = "flat"
    return latest, d


def _vix_rank(v):
    return 3 if v >= 40 else (2 if v >= 28 else (1 if v >= 20 else 0))


def _hy_rank(h):
    return 3 if h >= 8.0 else (2 if h >= 5.5 else (1 if h >= 4.0 else 0))


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
    """آخر جلب أحدث من max_age_h ساعة؟ (يومي من FRED — لا داعي لجلبٍ متكرّر)."""
    ts = (cached or {}).get("fetched_local")
    if not ts:
        return False
    try:
        then = now_local().strptime(ts, "%Y-%m-%d %H:%M")
        # نقارن بالساعة المحلّية الحالية بفارق بسيط؛ أي خطأ → اعتبره قديماً
        now = now_local().replace(tzinfo=None)
        return (now - then).total_seconds() < max_age_h * 3600
    except Exception:
        return False


def signals(cfg=None, timeout=20, max_age_h=6, persist=True):
    """يرجّع dict إشارات كلّية أو None. يَستعمل كاشاً طازجاً (<max_age_h) قبل الجلب."""
    cfg = cfg or {}
    cached = _load(cfg)
    if cached and _fresh(cached, max_age_h):
        return _derive(cached)

    out = None
    try:
        vix_rows = _fetch_series(_SERIES["vix"], timeout)
        hy_rows = _fetch_series(_SERIES["hy"], timeout)
        vix, vix_dir = _dir(vix_rows)
        hy, hy_dir = _dir(hy_rows)
        if vix is not None and hy is not None:
            out = {"vix": round(vix, 2), "vix_dir": vix_dir,
                   "hy": round(hy, 2), "hy_dir": hy_dir,
                   "fetched_local": now_local().strftime("%Y-%m-%d %H:%M"),
                   "updated_utc": iso(now_utc())}
            if persist:
                try:
                    with open(_path(cfg), "w", encoding="utf-8") as f:
                        json.dump(out, f, ensure_ascii=False, indent=1)
                except Exception:
                    pass
    except Exception as e:
        print(f"  macro (FRED) fetch failed: {e}")

    if out is None:                                     # fallback → last good cache
        out = cached
    return _derive(out) if out else None


def _derive(d):
    """يضيف stress_rank + easing/rising + وصفاً عربياً مشتقّاً من VIX والفروقات."""
    if not d:
        return None
    vix, hy = d.get("vix"), d.get("hy")
    d = dict(d)
    d["stress_rank"] = max(_vix_rank(vix or 0), _hy_rank(hy or 0))
    d["easing"] = (d.get("vix_dir") == "falling" and d.get("hy_dir") in ("falling", "flat"))
    d["rising"] = (d.get("vix_dir") == "rising" or d.get("hy_dir") == "rising")
    lvl = {0: "هادئ", 1: "مرتفع قليلاً", 2: "ضغط", 3: "أزمة"}[d["stress_rank"]]
    dirw = "ويتّسع" if d.get("rising") else ("وينحسر" if d.get("easing") else "ومستقر")
    d["label_ar"] = ("الخوف %s %s — VIX %s، فروقات الائتمان %s%%"
                     % (lvl, dirw, _num(vix), _num(hy)))
    return d


def _num(x):
    return ("%.1f" % x) if isinstance(x, (int, float)) else "—"
