# -*- coding: utf-8 -*-
"""
screener.py — المرحلة الأولى: الفلتر الكمي الآلي.

فلسفة التصميم (مهمة):
  ❌ مو "٩ شروط لازم تتحقق كلها" → في سوق حامي ما ينجح ولا سهم، والنتيجة صفر.
  ✅ بدلها: **بوابات صارمة** (لا تتنازل: شرعي، تغطية محللين، الهدف مو أقل
     من السعر، مو فقاعة طايرة، تقييم مو مجنون) ثم **ترتيب بالنقاط** يطلّع
     أفضل المتاح دايماً، مع **كشف نقاط ضعف كل مرشّح بصراحة**.

كذا النظام:
  - ما يكذب (الفلتر ما "يخترع" صيدات — يرتّب الواقع ويكشف عيوبه).
  - ما يرجع فاضي (دايماً يطلّع أفضل ١٢، وأنت + كلود تبحثونهم عميق).
  - أصدق من المازر: يكتب نقاط ضعف كل سهم، مو بس محاسنه.
"""

import os
import time
import math
import pickle
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

from config import CRITERIA, SHORTLIST_SIZE, SETTINGS
from halal import screen_halal


# ──────────────────────────────────────────────────────────────────
#  كاش يومي — يخزّن البيانات المسحوبة عشان إعادة التشغيل تكون فورية
# ──────────────────────────────────────────────────────────────────
_CACHE = {}
_CACHE_PATH = None


def _today_q():
    tz = timezone(timedelta(hours=SETTINGS["qatar_utc_offset"]))
    return datetime.now(tz).strftime("%Y%m%d")


def load_cache():
    global _CACHE, _CACHE_PATH
    here = os.path.dirname(os.path.abspath(__file__))
    cdir = os.path.join(here, "cache")
    os.makedirs(cdir, exist_ok=True)
    _CACHE_PATH = os.path.join(cdir, f"cache_{_today_q()}.pkl")
    if os.path.exists(_CACHE_PATH):
        try:
            with open(_CACHE_PATH, "rb") as f:
                _CACHE = pickle.load(f)
        except Exception:
            _CACHE = {}
    return len(_CACHE)


def save_cache():
    if _CACHE_PATH:
        try:
            with open(_CACHE_PATH, "wb") as f:
                pickle.dump(_CACHE, f)
        except Exception:
            pass


def _num(x):
    try:
        if x is None:
            return None
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def fetch_one(ticker, use_cache=True):
    """يجيب بيانات سهم واحد وينظّفها. يرجّع dict أو None لو فشل."""
    if use_cache and ticker in _CACHE:
        return _CACHE[ticker]
    try:
        t = yf.Ticker(ticker)
        info = t.get_info()
        if not info or not info.get("symbol"):
            return None
    except Exception:
        return None

    price = (_num(info.get("currentPrice"))
             or _num(info.get("regularMarketPrice")))
    if price is None:
        try:
            price = _num(t.fast_info.get("last_price"))
        except Exception:
            price = None

    one_year = _num(info.get("52WeekChange"))
    if one_year is None:
        try:
            hist = t.history(period="1y")
            if len(hist) > 20:
                first = hist["Close"].iloc[0]
                last = hist["Close"].iloc[-1]
                if first:
                    one_year = (last / first) - 1.0
        except Exception:
            pass

    pe = _num(info.get("trailingPE")) or _num(info.get("forwardPE"))
    target = _num(info.get("targetMeanPrice"))
    upside = (target / price - 1.0) if (target and price) else None

    data = {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector") or "—",
        "industry": info.get("industry") or "—",
        "price": price,
        "market_cap": _num(info.get("marketCap")),
        "rev_growth": _num(info.get("revenueGrowth")),
        "earn_growth": _num(info.get("earningsGrowth")),
        "profit_margin": _num(info.get("profitMargins")),
        "debt_to_equity": _num(info.get("debtToEquity")),
        "pe": pe,
        "forward_pe": _num(info.get("forwardPE")),
        "peg": _num(info.get("pegRatio")) or _num(info.get("trailingPegRatio")),
        "one_year_return": one_year,
        "rec_mean": _num(info.get("recommendationMean")),
        "rec_key": info.get("recommendationKey") or "—",
        "num_analysts": _num(info.get("numberOfAnalystOpinions")),
        "target_mean": target,
        "target_high": _num(info.get("targetHighPrice")),
        "target_low": _num(info.get("targetLowPrice")),
        "upside": upside,
        "beta": _num(info.get("beta")),
        "div_yield": _num(info.get("dividendYield")),
        "summary": (info.get("longBusinessSummary") or "")[:600],
        "_info": info,
    }
    if use_cache:
        _CACHE[ticker] = data
    return data


# ──────────────────────────────────────────────────────────────────
#  البوابات الصارمة — لا تتنازل (هذي اللي تحميك)
# ──────────────────────────────────────────────────────────────────
def hard_gate(d, halal):
    c = CRITERIA
    # ١) شرعي: الرفض القاطع يطير
    if halal["status"] == "FAIL":
        return False, f"شرعي: {halal['reasons'][0]}"
    # ٢) تغطية محللين (مثل المازر: أسماء معروفة مو زيرو زيرو)
    if d["num_analysts"] is None or d["num_analysts"] < c["min_analysts"]:
        return False, "تغطية محللين قليلة (اسم غير معروف)"
    # ٣) نطاق القيمة السوقية
    mc = d["market_cap"]
    if mc is None or mc < c["market_cap_min"] or mc > c["market_cap_max"]:
        return False, "خارج نطاق القيمة السوقية"
    # ٤) درس Marvell: الهدف مو أقل من السعر (نتنازل بهامش بسيط -3%)
    if d["upside"] is not None and d["upside"] < -0.03:
        return False, "الهدف المتوسط أقل من السعر (المحللون يتوقعون نزول)"
    # ٥) مو فقاعة طايرة
    if d["one_year_return"] is not None and d["one_year_return"] > c["one_year_return_max"]:
        return False, "فقاعة: طار فوق السقف خلال سنة"
    # ٦) تقييم مو مجنون (نقبل بدون P/E، بس نعاقبه بالنقاط)
    if d["pe"] is not None and d["pe"] > c["pe_hard_max"]:
        return False, f"تقييم مجنون (P/E={d['pe']:.0f})"
    return True, None


# ──────────────────────────────────────────────────────────────────
#  نقاط الضعف — الشفافية (نكتبها للمستخدم، مو نخفيها)
# ──────────────────────────────────────────────────────────────────
def weaknesses(d):
    c = CRITERIA
    w = []
    if d["rev_growth"] is None or d["rev_growth"] < c["revenue_growth_min"]:
        w.append(f"نمو إيرادات معتدل ({d['rev_growth']:+.0%})" if d["rev_growth"] is not None else "نمو غير معروف")
    if d["profit_margin"] is None or d["profit_margin"] <= 0:
        w.append("غير ربحية بعد")
    if d["pe"] is not None and d["pe"] > c["pe_max"]:
        w.append(f"تقييم مرتفع (P/E={d['pe']:.0f})")
    if d["debt_to_equity"] is not None and d["debt_to_equity"] > c["debt_to_equity_max"]:
        w.append(f"ديون مرتفعة (D/E={d['debt_to_equity']:.0f}%)")
    if d["upside"] is not None and d["upside"] < c["upside_min"]:
        w.append(f"صعود متوقع محدود ({d['upside']:+.0%})")
    if d["one_year_return"] is not None and d["one_year_return"] > 1.0:
        w.append(f"صعد كثير بالفعل ({d['one_year_return']:+.0%} بسنة)")
    if d["beta"] is not None and d["beta"] > 1.8:
        w.append(f"تذبذب عالي (بيتا {d['beta']:.1f})")
    return w


def _clamp01(x):
    """يقيّد القيمة بين 0 و 1 (يمنع تفجّر النقاط مع القيم الشاذة)."""
    if x is None:
        return 0.0
    return max(0.0, min(1.0, x))


def score(d):
    """نقاط مركّبة 0-100 — جودة + قيمة + إجماع + زخم صحي. كل مكوّن مقيّد بوزنه."""
    s = 0.0
    # الصعود المتوقع (٢٥)
    if d["upside"] is not None:
        s += _clamp01(d["upside"] / 0.50) * 25
    # نمو الإيرادات (٢٢)
    if d["rev_growth"] is not None:
        s += _clamp01(d["rev_growth"] / 0.50) * 22
    # إجماع المحللين (١٨): 1=StrongBuy أحسن
    if d["rec_mean"] is not None:
        s += _clamp01((3.0 - d["rec_mean"]) / 2.0) * 18
    # التقييم (١٥): داخل النطاق المثالي أحسن، فوقه يتلاشى (مقيّد)
    if d["pe"] is not None and d["pe"] > 0:
        if d["pe"] <= CRITERIA["pe_max"]:
            s += _clamp01(1.0 - d["pe"] / (CRITERIA["pe_max"] * 1.5)) * 15
        else:
            s += _clamp01((CRITERIA["pe_hard_max"] - d["pe"]) / CRITERIA["pe_hard_max"]) * 7
    # الربحية (١٠)
    if d["profit_margin"] is not None and d["profit_margin"] > 0:
        s += _clamp01(d["profit_margin"] / 0.25) * 10
    # ديون منخفضة (٦) — مقيّد (حقوق ملكية سالبة لا تفجّر النقاط)
    if d["debt_to_equity"] is not None:
        s += _clamp01((CRITERIA["debt_to_equity_max"] - d["debt_to_equity"]) / CRITERIA["debt_to_equity_max"]) * 6
    # زخم صحي (٤): موجب معتدل أحسن من سالب أو فقاعة
    if d["one_year_return"] is not None:
        oyr = d["one_year_return"]
        if 0 <= oyr <= 0.6:
            s += 4
        elif oyr > 0.6:
            s += _clamp01(1 - (oyr - 0.6) / 1.4) * 4
    return round(s, 1)


def run_screen(universe, verbose=True):
    if SETTINGS["max_universe"]:
        universe = universe[: SETTINGS["max_universe"]]
    n = len(universe)
    survivors = []
    examined = 0

    cached_n = load_cache()
    if verbose and cached_n:
        print(f"(كاش اليوم: {cached_n} سهم محفوظ — إعادة التشغيل سريعة)\n")

    # ── جلب البيانات بالخيوط المتوازية (تسريع كبير لآلاف الأسهم) ──
    workers = max(1, int(SETTINGS.get("max_workers", 8)))
    fetched = []
    done = 0
    if verbose:
        print(f"جلب بيانات {n} سهم بـ{workers} خيوط متوازية...")

    def _job(tk):
        d = fetch_one(tk)
        if SETTINGS["request_delay_sec"]:
            time.sleep(SETTINGS["request_delay_sec"])
        return d

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_job, tk): tk for tk in universe}
        for fut in as_completed(futures):
            done += 1
            try:
                d = fut.result()
            except Exception:
                d = None
            if d and d.get("price") is not None:
                fetched.append(d)
            if verbose and done % 100 == 0:
                print(f"  ... {done}/{n} (بيانات صالحة: {len(fetched)})")

    # ── الفلترة والتقييم (سريعة، بدون شبكة) ──
    for d in fetched:
        examined += 1
        h = screen_halal(d["_info"])
        d["halal"] = h
        ok, reason = hard_gate(d, h)
        if not ok:
            continue
        d["score"] = score(d)
        d["weaknesses"] = weaknesses(d)
        survivors.append(d)

    save_cache()
    survivors.sort(key=lambda x: x["score"], reverse=True)
    shortlist = survivors[:SHORTLIST_SIZE]
    stats = {"universe": n, "examined": examined, "survivors": len(survivors)}
    if verbose:
        print(f"نجا من الفلتر: {len(survivors)} سهم")
    return shortlist, stats


if __name__ == "__main__":
    from universe import get_universe
    sl, st = run_screen(get_universe())
    print(f"\n=== فُحص {st['examined']} | نجا {st['survivors']} | القائمة {len(sl)} ===")
    for d in sl:
        print(f"{d['score']:5} | {d['ticker']:6} | صعود {(d['upside'] or 0):+.0%} | نمو {(d['rev_growth'] or 0):+.0%} | P/E {d['pe']}")
