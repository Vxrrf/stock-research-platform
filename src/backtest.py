# -*- coding: utf-8 -*-
"""
backtest.py — a SANITY backtest of the platform's current top-ranked basket vs a
benchmark (default SPY). Equal-weight, buy-and-hold, monthly bars.

⚠️ HONESTY FIRST — read this before trusting any number it produces:
  * LOOK-AHEAD BIAS: the basket is chosen using TODAY's rankings, then applied to
    the PAST. That is not how you'd have invested back then, so it flatters results.
  * SURVIVORSHIP BIAS: we only test names that still exist now; losers that were
    delisted/acquired are invisible.
  * Equal-weight, no fees/taxes, dividends handled only via adjusted close.
This is a reasonableness check ("does the ranking pick names that have done okay?"),
NOT proof the strategy works. We label it loudly in the dashboard.

Result is cached to data/_state/backtest.json so the dashboard can show it without
re-downloading every run (network-heavy).
"""

import os
import json

from config_loader import state_dir


def _path(cfg):
    return os.path.join(state_dir(cfg), "backtest.json")


def load_cached(cfg):
    p = _path(cfg)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _cagr(total_return, years):
    if years <= 0:
        return None
    try:
        return (1.0 + total_return) ** (1.0 / years) - 1.0
    except Exception:
        return None


def _max_drawdown(series):
    """series: list of floats (an index). Returns the worst peak-to-trough drop (≤0)."""
    peak = None
    mdd = 0.0
    for v in series:
        if v is None:
            continue
        if peak is None or v > peak:
            peak = v
        if peak:
            dd = v / peak - 1.0
            mdd = min(mdd, dd)
    return round(mdd, 4)


def run(tickers, cfg, run_date, benchmark="SPY", years=3, max_names=15):
    """Download monthly adjusted closes; compare an equal-weight basket to a benchmark.
    Returns a result dict (also cached). Returns {'ok': False, ...} on any failure."""
    tickers = [t for t in dict.fromkeys(t.upper() for t in tickers if t)][:max_names]
    if not tickers:
        return {"ok": False, "reason": "لا أسهم للاختبار", "as_of": run_date}
    try:
        import yfinance as yf
        syms = tickers + [benchmark]
        data = yf.download(syms, period=f"{years}y", interval="1mo",
                           auto_adjust=True, progress=False, threads=True)
        close = data["Close"] if "Close" in data else data
    except Exception as e:
        return {"ok": False, "reason": f"تعذّر تحميل البيانات: {e}", "as_of": run_date}

    try:
        import pandas as pd  # noqa: F401
        close = close.dropna(how="all")
        if benchmark not in close.columns or len(close) < 6:
            return {"ok": False, "reason": "بيانات تاريخية غير كافية", "as_of": run_date}

        # per-stock buy-and-hold total return over the window
        per = {}
        norm_cols = []
        for t in tickers:
            if t not in close.columns:
                continue
            s = close[t].dropna()
            if len(s) < 6 or s.iloc[0] <= 0:
                continue
            per[t] = float(s.iloc[-1] / s.iloc[0] - 1.0)
            norm_cols.append((s / s.iloc[0]))
        if not per:
            return {"ok": False, "reason": "ما توفّر تاريخ كافٍ لأسهم السلة", "as_of": run_date}

        basket_return = sum(per.values()) / len(per)        # equal-weight average

        # equal-weight portfolio index (for drawdown): mean of normalized series
        import pandas as pd
        idx = pd.concat(norm_cols, axis=1).dropna(how="all").mean(axis=1)
        basket_series = [float(x) for x in idx.tolist()]

        b = close[benchmark].dropna()
        bench_return = float(b.iloc[-1] / b.iloc[0] - 1.0)
        bench_series = [float(x) for x in (b / b.iloc[0]).tolist()]

        actual_years = max(0.25, len(idx) / 12.0)
        return {
            "ok": True,
            "as_of": run_date,
            "years": round(actual_years, 1),
            "benchmark": benchmark,
            "n_stocks": len(per),
            "tickers": list(per.keys()),
            "basket_return": round(basket_return, 4),
            "benchmark_return": round(bench_return, 4),
            "basket_cagr": round(_cagr(basket_return, actual_years), 4),
            "benchmark_cagr": round(_cagr(bench_return, actual_years), 4),
            "outperformance": round(basket_return - bench_return, 4),
            "basket_max_drawdown": _max_drawdown(basket_series),
            "benchmark_max_drawdown": _max_drawdown(bench_series),
            "per_stock": {k: round(v, 4) for k, v in per.items()},
            "caveats": [
                "انحياز نظر للأمام (look-ahead): السلة اختيرت بترتيب اليوم ثم طُبّقت على الماضي — ليست طريقة استثمار واقعية.",
                "انحياز الناجين: نختبر أسهماً لا تزال موجودة؛ الي حُذفت/أفلست غير ظاهرة.",
                "وزن متساوٍ، شراء واحتفاظ، بدون عمولات/ضرائب؛ التوزيعات عبر السعر المعدّل فقط.",
                "الأداء الماضي لا يضمن المستقبل — هذا مؤشر تعقّل، وليس إثبات استراتيجية.",
            ],
        }
    except Exception as e:
        return {"ok": False, "reason": f"خطأ في الحساب: {e}", "as_of": run_date}


def run_and_cache(tickers, cfg, run_date, **kw):
    res = run(tickers, cfg, run_date, **kw)
    try:
        with open(_path(cfg), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  could not cache backtest: {e}")
    return res
