# -*- coding: utf-8 -*-
"""
datasource.py — unified live data layer.

  PRIMARY  : Financial Modeling Prep (FMP)   — activated by an API key.
  FALLBACK : yfinance                        — fills any field FMP can't give.

Never uses hardcoded financial data. Every record it returns carries:
  data_source, last_updated, fundamentals_last_updated,
  data_freshness_status (FRESH/STALE/MISSING), confidence (HIGH/MEDIUM/LOW).

Freshness rules (spec):
  * price older than freshness.price_max_age_hours  => STALE
  * fundamentals older than freshness.fundamentals_max_age_days => STALE
  * any stale or missing core field => confidence downgraded (LOW).
"""

import os
import math
import time
import pickle
import json
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from schema import blank_record, now_utc, iso
from config_loader import CFG, ROOT


# ──────────────────────────────────────────────────────────────────
#  small numeric helper (shared)
# ──────────────────────────────────────────────────────────────────
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


def _cagr(latest, earliest, years):
    latest, earliest = _num(latest), _num(earliest)
    if not latest or not earliest or earliest <= 0 or years <= 0:
        return None
    try:
        return (latest / earliest) ** (1.0 / years) - 1.0
    except (ValueError, ZeroDivisionError):
        return None


# ══════════════════════════════════════════════════════════════════
#  FMP CLIENT  (primary)
# ══════════════════════════════════════════════════════════════════
class FMPClient:
    """Financial Modeling Prep — STABLE API (the v3 legacy API is discontinued).

    Stable endpoints use query params (?symbol=AMD) and live under /stable/.
    Endpoints not in the account's plan return HTTP 402/403 -> None, so the
    caller transparently falls back to yfinance / free sources.
    """

    def __init__(self, cfg):
        d = cfg.get("data", {}) or {}
        self.key = (d.get("fmp_api_key") or "").strip()
        # honour an explicit base if set, else the stable API
        base = d.get("fmp_base_url", "https://financialmodelingprep.com/api")
        if base.rstrip("/").endswith("/api"):
            base = base.rstrip("/")[:-4] + "/stable"
        self.base = base.rstrip("/")
        self.timeout = d.get("request_timeout_sec", 20)
        self.enabled = bool(self.key)
        self._sess = requests.Session()
        # circuit breaker: a free/restricted key 402s most symbols. After enough
        # subscription-blocks we stop calling FMP for the rest of the run so we
        # don't burn the daily quota or slow the scan — yfinance takes over.
        self._sub_blocks = 0
        self._block_threshold = 12
        self.degraded = False          # tripped => behaving as if no key
        self.tier_note = None          # one-line status for the run summary

    def _get(self, endpoint, params=None):
        if not self.enabled or self.degraded:
            return None
        params = dict(params or {})
        params["apikey"] = self.key
        url = f"{self.base}/{endpoint.lstrip('/')}"
        try:
            r = self._sess.get(url, params=params, timeout=self.timeout)
            if r.status_code in (401, 402, 403):         # not in plan / subscription block
                if "subscription" in r.text.lower() or "premium" in r.text.lower():
                    self._sub_blocks += 1
                    if self._sub_blocks >= self._block_threshold and not self.degraded:
                        self.degraded = True
                        self.tier_note = ("FMP key is free/restricted (most symbols blocked) — "
                                          "backing off to yfinance. Upgrade the FMP plan for full coverage.")
                return None
            if r.status_code == 404:
                return None
            if r.status_code == 429:                     # rate limited
                time.sleep(0.7)
                r = self._sess.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and data.get("Error Message"):
                return None
            return data
        except Exception:
            return None

    def _one(self, endpoint, params=None):
        d = self._get(endpoint, params)
        return d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else None)

    def quote(self, sym):
        return self._one("quote", {"symbol": sym})

    def profile(self, sym):
        return self._one("profile", {"symbol": sym})

    def income_annual(self, sym, limit=6):
        d = self._get("income-statement", {"symbol": sym, "period": "annual", "limit": limit})
        return d if isinstance(d, list) else None

    def key_metrics_ttm(self, sym):
        return self._one("key-metrics-ttm", {"symbol": sym})

    def ratios_ttm(self, sym):
        return self._one("ratios-ttm", {"symbol": sym})

    def price_target(self, sym):
        return self._one("price-target-consensus", {"symbol": sym})

    def grades(self, sym):
        return self._one("grades-consensus", {"symbol": sym})

    def insider(self, sym, limit=60):
        d = self._get("insider-trading/search", {"symbol": sym, "page": 0, "limit": limit})
        return d if isinstance(d, list) else None

    def senate(self, sym):
        d = self._get("senate-trades", {"symbol": sym})
        return d if isinstance(d, list) else None

    def house(self, sym):
        d = self._get("house-trades", {"symbol": sym})
        return d if isinstance(d, list) else None


# ══════════════════════════════════════════════════════════════════
#  FMP → record
# ══════════════════════════════════════════════════════════════════
def _fmp_fill(rec, fmp, sym, want_deep=True):
    """Fill record from FMP STABLE API. Returns True if FMP produced a usable quote."""
    q = fmp.quote(sym)
    if not q:
        return False
    rec["price"] = _num(q.get("price"))
    rec["market_cap"] = _num(q.get("marketCap"))
    rec["week52_high"] = _num(q.get("yearHigh"))
    rec["week52_low"] = _num(q.get("yearLow"))
    ts = q.get("timestamp")
    rec["last_updated"] = iso(datetime.fromtimestamp(ts, tz=timezone.utc)) if ts else iso(now_utc())
    rec["data_source"] = "FMP"

    prof = fmp.profile(sym)
    if prof:
        rec["name"] = prof.get("companyName") or rec["name"]
        rec["sector"] = prof.get("sector") or rec["sector"]
        rec["industry"] = prof.get("industry") or rec["industry"]
        rec["beta"] = _num(prof.get("beta"))
        rec["summary"] = (prof.get("description") or "")[:600]
        if rec["market_cap"] is None:
            rec["market_cap"] = _num(prof.get("marketCap"))

    if want_deep:
        inc = fmp.income_annual(sym, limit=6)
        if inc:
            revs = [(_num(r.get("revenue")), r.get("date")) for r in inc]
            revs = [(v, d) for v, d in revs if v]
            if revs:
                rec["fundamentals_last_updated"] = revs[0][1]
                rec["revenue_ttm"] = revs[0][0]
                if len(revs) >= 2 and revs[1][0]:
                    rec["rev_growth"] = (revs[0][0] / revs[1][0]) - 1.0
                if len(revs) >= 4:
                    rec["rev_cagr_3y"] = _cagr(revs[0][0], revs[3][0], 3)
                if len(revs) >= 6:
                    rec["rev_cagr_5y"] = _cagr(revs[0][0], revs[5][0], 5)
            # interest income (enables halal purification test) + eps growth
            rec["interest_income"] = _num(inc[0].get("interestIncome"))
            eps0 = _num(inc[0].get("epsDiluted")) or _num(inc[0].get("eps"))
            eps1 = (_num(inc[1].get("epsDiluted")) or _num(inc[1].get("eps"))) if len(inc) > 1 else None
            if eps0 is not None and eps1 not in (None, 0):
                rec["eps_growth"] = (eps0 / eps1) - 1.0

        km = fmp.key_metrics_ttm(sym)
        if km:
            rec["roic"] = _num(km.get("returnOnInvestedCapitalTTM"))
            rec["roe"] = _num(km.get("returnOnEquityTTM"))
            rec["ev_ebitda"] = _num(km.get("evToEBITDATTM"))
            fcf_yield = _num(km.get("freeCashFlowYieldTTM"))
            if fcf_yield is not None and rec.get("market_cap"):
                rec["fcf"] = fcf_yield * rec["market_cap"]

        rt = fmp.ratios_ttm(sym)
        if rt:
            rec["gross_margin"] = _num(rt.get("grossProfitMarginTTM"))
            rec["operating_margin"] = _num(rt.get("operatingProfitMarginTTM"))
            if rec.get("roe") is None:
                rec["roe"] = _num(rt.get("returnOnEquityTTM"))
            de = _num(rt.get("debtToEquityRatioTTM"))
            if de is not None:
                rec["debt_to_equity"] = de * 100.0 if abs(de) <= 10 else de  # → % scale
            rec["pe"] = _num(rt.get("priceToEarningsRatioTTM"))
            if rec.get("ev_ebitda") is None:
                rec["ev_ebitda"] = _num(rt.get("enterpriseValueMultipleTTM"))

        if rec.get("fcf") and rec.get("revenue_ttm"):
            rec["fcf_margin"] = rec["fcf"] / rec["revenue_ttm"]

        pt = fmp.price_target(sym)
        if pt:
            rec["target_mean"] = _num(pt.get("targetConsensus")) or _num(pt.get("targetMedian"))
            rec["target_high"] = _num(pt.get("targetHigh"))
            rec["target_low"] = _num(pt.get("targetLow"))

        gr = fmp.grades(sym)
        if gr:
            sb = _num(gr.get("strongBuy")) or 0
            b = _num(gr.get("buy")) or 0
            h = _num(gr.get("hold")) or 0
            s = _num(gr.get("sell")) or 0
            ss = _num(gr.get("strongSell")) or 0
            total = sb + b + h + s + ss
            if total:
                rec["num_analysts"] = total
                rec["rec_mean"] = (sb * 1 + b * 2 + h * 3 + s * 4 + ss * 5) / total
                rec["rec_key"] = _mean_to_key(rec["rec_mean"])
    return True


def _mean_to_key(m):
    if m is None:
        return None
    if m <= 1.5:
        return "strong_buy"
    if m <= 2.5:
        return "buy"
    if m <= 3.5:
        return "hold"
    if m <= 4.5:
        return "underperform"
    return "sell"


# ══════════════════════════════════════════════════════════════════
#  yfinance → record (fallback, and primary today)
# ══════════════════════════════════════════════════════════════════
def _yf_fill(rec, sym, want_deep=True):
    """Fill any missing fields from yfinance. Returns True if a price was found."""
    try:
        import yfinance as yf
    except Exception:
        return False
    try:
        t = yf.Ticker(sym)
        info = t.get_info()
    except Exception:
        return False
    if not info or not info.get("symbol"):
        return False

    def setif(key, val):
        if rec.get(key) is None and val is not None:
            rec[key] = val

    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    if price is None:
        try:
            price = _num(t.fast_info.get("last_price"))
        except Exception:
            price = None
    setif("price", price)
    setif("name", info.get("longName") or info.get("shortName"))
    setif("sector", info.get("sector"))
    setif("industry", info.get("industry"))
    setif("market_cap", _num(info.get("marketCap")))
    setif("rev_growth", _num(info.get("revenueGrowth")))
    setif("eps_growth", _num(info.get("earningsGrowth")) or _num(info.get("earningsQuarterlyGrowth")))
    setif("eps_growth_fwd", _num(info.get("earningsGrowth")))
    setif("roe", _num(info.get("returnOnEquity")))
    setif("gross_margin", _num(info.get("grossMargins")))
    setif("operating_margin", _num(info.get("operatingMargins")))
    setif("fcf", _num(info.get("freeCashflow")))
    setif("total_debt", _num(info.get("totalDebt")))
    setif("total_cash", _num(info.get("totalCash")))
    setif("debt_to_equity", _num(info.get("debtToEquity")))
    setif("ev_ebitda", _num(info.get("enterpriseToEbitda")))
    setif("pe", _num(info.get("trailingPE")))
    setif("forward_pe", _num(info.get("forwardPE")))
    setif("peg", _num(info.get("pegRatio")) or _num(info.get("trailingPegRatio")))
    setif("rec_mean", _num(info.get("recommendationMean")))
    setif("rec_key", info.get("recommendationKey"))
    setif("num_analysts", _num(info.get("numberOfAnalystOpinions")))
    setif("target_mean", _num(info.get("targetMeanPrice")))
    setif("target_high", _num(info.get("targetHighPrice")))
    setif("target_low", _num(info.get("targetLowPrice")))
    setif("beta", _num(info.get("beta")))
    setif("div_yield", _num(info.get("dividendYield")))
    setif("week52_high", _num(info.get("fiftyTwoWeekHigh")))
    setif("week52_low", _num(info.get("fiftyTwoWeekLow")))
    setif("institutional_ownership", _num(info.get("heldPercentInstitutions")))
    setif("insider_ownership", _num(info.get("heldPercentInsiders")))
    if not rec.get("summary"):
        rec["summary"] = (info.get("longBusinessSummary") or "")[:600]

    # fcf margin via revenue (info has totalRevenue)
    rev_ttm = _num(info.get("totalRevenue"))
    if rev_ttm and rec.get("revenue_ttm") is None:
        rec["revenue_ttm"] = rev_ttm
    if rec.get("fcf") and rev_ttm:
        if rec.get("fcf_margin") is None:
            rec["fcf_margin"] = rec["fcf"] / rev_ttm
    # net debt
    cash = _num(info.get("totalCash"))
    if rec.get("net_debt") is None and rec.get("total_debt") is not None:
        rec["net_debt"] = rec["total_debt"] - (cash or 0)

    # avg dollar volume
    avgvol = _num(info.get("averageDailyVolume10Day")) or _num(info.get("averageVolume"))
    if rec.get("avg_dollar_volume") is None and avgvol and rec.get("price"):
        rec["avg_dollar_volume"] = avgvol * rec["price"]

    # 1y return: prefer info, else compute
    oyr = _num(info.get("52WeekChange"))
    # price freshness from regularMarketTime
    mkt_ts = info.get("regularMarketTime")
    if isinstance(mkt_ts, (int, float)) and mkt_ts > 0:
        rec["last_updated"] = iso(datetime.fromtimestamp(mkt_ts, tz=timezone.utc))
    elif rec.get("last_updated") is None:
        rec["last_updated"] = iso(now_utc())

    if want_deep:
        if oyr is None or rec.get("rev_cagr_3y") is None or rec.get("fundamentals_last_updated") is None:
            _yf_deep(rec, t, oyr)
        else:
            rec["one_year_return"] = oyr
    else:
        rec["one_year_return"] = oyr

    rec["data_source"] = "yfinance" if rec["data_source"] is None else f"{rec['data_source']}+yfinance"
    return rec.get("price") is not None


def _yf_deep(rec, t, oyr):
    """Extra yfinance scrapes: price history (1y return) + annual revenue CAGR + last quarter date."""
    try:
        if oyr is None:
            hist = t.history(period="1y")
            if len(hist) > 20:
                first = hist["Close"].iloc[0]
                last = hist["Close"].iloc[-1]
                if first:
                    oyr = (last / first) - 1.0
    except Exception:
        pass
    rec["one_year_return"] = oyr if oyr is not None else rec.get("one_year_return")

    # annual revenue history → CAGR
    try:
        stmt = t.income_stmt          # annual, columns = period-end dates (recent first)
        if stmt is not None and not stmt.empty and "Total Revenue" in stmt.index:
            row = stmt.loc["Total Revenue"].dropna()
            vals = [(_num(v), c) for c, v in row.items()]
            vals = [(v, c) for v, c in vals if v]
            if vals:
                if rec.get("rev_growth") is None and len(vals) >= 2 and vals[1][0]:
                    rec["rev_growth"] = (vals[0][0] / vals[1][0]) - 1.0
                if rec.get("rev_cagr_3y") is None and len(vals) >= 4:
                    rec["rev_cagr_3y"] = _cagr(vals[0][0], vals[3][0], 3)
                if rec.get("rev_cagr_5y") is None and len(vals) >= 5:
                    rec["rev_cagr_5y"] = _cagr(vals[0][0], vals[-1][0], len(vals) - 1)
    except Exception:
        pass

    # latest reported quarter date for fundamentals freshness
    try:
        qs = t.quarterly_income_stmt
        if qs is not None and not qs.empty:
            cols = list(qs.columns)
            if cols:
                d = cols[0]
                rec["fundamentals_last_updated"] = (
                    d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
                )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  Derived fields + freshness + confidence
# ══════════════════════════════════════════════════════════════════
def _finalize(rec, cfg):
    # analyst upside
    if rec.get("target_mean") and rec.get("price"):
        rec["analyst_upside_percent"] = rec["target_mean"] / rec["price"] - 1.0
    # distance below 52w high
    if rec.get("week52_high") and rec.get("price"):
        rec["pct_below_52w_high"] = max(0.0, (rec["week52_high"] - rec["price"]) / rec["week52_high"])
    _freshness_confidence(rec, cfg)
    return rec


def _parse_dt(s):
    if not s:
        return None
    try:
        if isinstance(s, datetime):
            return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
        s = str(s)
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _freshness_confidence(rec, cfg):
    fr = cfg.get("freshness", {}) or {}
    price_max_h = fr.get("price_max_age_hours", 48)
    fund_max_d = fr.get("fundamentals_max_age_days", 100)
    now = now_utc()

    price_status = "MISSING"
    pdt = _parse_dt(rec.get("last_updated"))
    if rec.get("price") is not None and pdt:
        age_h = (now - pdt).total_seconds() / 3600.0
        price_status = "FRESH" if age_h <= price_max_h else "STALE"

    fund_status = "MISSING"
    fdt = _parse_dt(rec.get("fundamentals_last_updated"))
    if fdt:
        age_d = (now - fdt).total_seconds() / 86400.0
        fund_status = "FRESH" if age_d <= fund_max_d else "STALE"

    # overall freshness = worst of the two relevant signals
    order = {"FRESH": 0, "STALE": 1, "MISSING": 2}
    overall = max([price_status, fund_status], key=lambda s: order[s])
    rec["data_freshness_status"] = overall
    rec["_price_freshness"] = price_status
    rec["_fundamentals_freshness"] = fund_status

    core_ok = all(rec.get(k) is not None for k in ("price", "market_cap"))
    if price_status == "STALE" or not core_ok or fund_status == "MISSING":
        conf = "LOW"
    elif price_status == "FRESH" and fund_status == "FRESH":
        conf = "HIGH"
    else:
        conf = "MEDIUM"
    rec["confidence"] = conf
    return rec


# ══════════════════════════════════════════════════════════════════
#  Daily cache
# ══════════════════════════════════════════════════════════════════
def _cache_path(cfg):
    off = (cfg.get("run", {}) or {}).get("qatar_utc_offset", 3)
    day = datetime.now(timezone(timedelta(hours=off))).strftime("%Y%m%d")
    cdir = os.path.join(ROOT, "cache")
    os.makedirs(cdir, exist_ok=True)
    return os.path.join(cdir, f"records_{day}.pkl")


def _load_cache(cfg):
    if not (cfg.get("data", {}) or {}).get("cache_enabled", True):
        return {}
    p = _cache_path(cfg)
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cfg, cache):
    if not (cfg.get("data", {}) or {}).get("cache_enabled", True):
        return
    try:
        with open(_cache_path(cfg), "wb") as f:
            pickle.dump(cache, f)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════
def fetch_record(ticker, cfg=None, fmp=None, want_deep=True):
    """Fetch one ticker → finalized record (FMP primary, yfinance fallback)."""
    cfg = cfg or CFG
    fmp = fmp if fmp is not None else FMPClient(cfg)
    sym = str(ticker).strip().upper()
    rec = blank_record(sym)

    got = False
    if fmp.enabled:
        try:
            got = _fmp_fill(rec, fmp, sym, want_deep=want_deep)
        except Exception:
            got = False
    use_fallback = (cfg.get("data", {}) or {}).get("use_yfinance_fallback", True)
    # use yfinance if FMP disabled, failed, or to fill gaps
    if (not got) or use_fallback:
        try:
            _yf_fill(rec, sym, want_deep=want_deep)
        except Exception:
            pass

    if rec.get("price") is None:
        return None
    return _finalize(rec, cfg)


def fetch_many(tickers, cfg=None, want_deep=True, verbose=True, progress_every=100, fmp=None):
    """Threaded fetch. Returns (records, cache_hits)."""
    cfg = cfg or CFG
    fmp = fmp if fmp is not None else FMPClient(cfg)
    cache = _load_cache(cfg)
    workers = max(1, int((cfg.get("data", {}) or {}).get("max_workers", 10)))
    tickers = [str(t).strip().upper() for t in tickers if str(t).strip()]

    out = []
    hits = 0
    todo = []
    for t in tickers:
        if t in cache:
            out.append(cache[t])
            hits += 1
        else:
            todo.append(t)

    if verbose:
        src = "FMP (primary)" if fmp.enabled else "yfinance (FMP key not set)"
        print(f"data source: {src} | cache hits: {hits} | to fetch: {len(todo)}")

    done = 0
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(fetch_record, t, cfg, fmp, want_deep): t for t in todo}
            for fut in as_completed(futs):
                done += 1
                try:
                    rec = fut.result()
                except Exception:
                    rec = None
                if rec:
                    out.append(rec)
                    cache[rec["ticker"]] = rec
                if verbose and done % progress_every == 0:
                    print(f"  ... {done}/{len(todo)} fetched (valid: {len(out)})")
        _save_cache(cfg, cache)

    return out, hits
