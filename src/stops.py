# -*- coding: utf-8 -*-
"""
stops.py — DATA-DRIVEN stop levels per stock (no random flat %).

The owner's rule, made precise: a stop must be *hard to reach by normal noise but
still limit a real loss* — "pinches, doesn't wipe out." So we size each stock's
stop from ITS OWN history (volatility, 52-week high, max drawdown), not a flat −40%:

  stop_distance = clamp(2.0 × monthly_volatility, 15%, 35%)
     → a calm stock (low vol) gets a tighter ~15-20% stop;
     → a wild stock (high vol) gets a wider stop so daily swings don't trip it;
     → always capped: never risk more than ~35% here, and the owner's −40%-from-cost
       danger line remains the hard backstop.

Reference point:
  * profitable holding  → TRAILING stop from the recent price (locks in gains),
                          floored so it never implies a worse-than-−40% loss from cost.
  * flat/losing holding → stop from cost.
  * suggested BUY       → stop from the entry (current) price.

History is fetched once (yfinance ~1y daily) for a SMALL set (holdings + top picks)
and cached to data/_state/stops.json, so a refresh is cheap.
"""

import os
import json
import math

from config_loader import state_dir


def _path(cfg):
    return os.path.join(state_dir(cfg), "stops.json")


def load_cached(cfg):
    p = _path(cfg)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def compute_metrics(tickers, cfg):
    """Fetch ~1y daily history and derive per-ticker risk metrics. Cached + merged."""
    tickers = [t.upper() for t in dict.fromkeys(t for t in tickers if t)]
    out = load_cached(cfg)
    if not tickers:
        return out
    try:
        import yfinance as yf
        data = yf.download(tickers, period="1y", interval="1d",
                           auto_adjust=True, progress=False, threads=True)
        close = data["Close"] if "Close" in data else data
    except Exception as e:
        print(f"⚠️  stops: history fetch failed: {e}")
        return out

    import pandas as pd  # noqa: F401
    for t in tickers:
        try:
            s = close[t].dropna() if hasattr(close, "columns") and t in close.columns else (
                close.dropna() if len(tickers) == 1 else None)
            if s is None or len(s) < 60:
                continue
            rets = s.pct_change().dropna()
            dvol = float(rets.std())
            mvol = dvol * math.sqrt(21)                 # ~monthly volatility
            high52 = float(s.max())
            low52 = float(s.min())
            cur = float(s.iloc[-1])
            peak = s.cummax()
            mdd = float((s / peak - 1.0).min())          # worst peak-to-trough over the year
            dist = min(0.35, max(0.15, 2.0 * mvol))      # vol-sized, clamped (hard to reach, capped)
            out[t] = {
                "monthly_vol": round(mvol, 4),
                "stop_distance": round(dist, 4),
                "high_52w": round(high52, 2),
                "low_52w": round(low52, 2),
                "max_drawdown_1y": round(mdd, 4),
                "ref_price": round(cur, 2),
            }
        except Exception:
            continue
    try:
        with open(_path(cfg), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"⚠️  stops: could not cache: {e}")
    return out


def stop_for(metrics, buy_price, current_price):
    """Return the concrete stop dict for one stock given its history metrics.
    None if we have no metrics (caller falls back to the flat −40% danger)."""
    if not metrics:
        return None
    dist = metrics.get("stop_distance", 0.25)
    high52 = metrics.get("high_52w")
    cur = current_price or metrics.get("ref_price")
    if not cur or cur <= 0:
        return None

    profitable = bool(buy_price and current_price and current_price > buy_price * 1.05)
    if profitable:
        # trailing stop from current — locks gains; but never tighter than the −40% cost line
        stop = cur * (1 - dist)
        hard_floor = buy_price * 0.60
        stop = max(stop, hard_floor)
        basis = "متحرّك: %d%% تحت السعر (بحجم تذبذب السهم)" % round(dist * 100)
        kind = "trailing"
    elif buy_price:
        stop = buy_price * (1 - dist)
        basis = "%d%% تحت كلفتك (بحجم تذبذب السهم)" % round(dist * 100)
        kind = "from_cost"
    else:
        stop = cur * (1 - dist)
        basis = "%d%% تحت سعر الدخول (بحجم تذبذب السهم)" % round(dist * 100)
        kind = "from_entry"

    loss_from_cost = (stop / buy_price - 1.0) if buy_price else None
    below_high = (stop / high52 - 1.0) if high52 else None
    return {
        "price": round(stop, 2),
        "distance_pct": round(dist, 4),
        "basis": basis,
        "kind": kind,
        "loss_from_cost_pct": round(loss_from_cost, 4) if loss_from_cost is not None else None,
        "below_high_pct": round(below_high, 4) if below_high is not None else None,
        "high_52w": high52,
        "monthly_vol": metrics.get("monthly_vol"),
        "max_drawdown_1y": metrics.get("max_drawdown_1y"),
    }
