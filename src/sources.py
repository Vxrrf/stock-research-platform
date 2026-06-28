# -*- coding: utf-8 -*-
"""
sources.py — additional data sources for MULTI-SOURCE confirmation.

Philosophy: never trust one source. Gather analyst/price/news from several
(yfinance + FMP + Finnhub …), compare, and flag disagreement. This module adds
Finnhub (free key from finnhub.io) as a SECOND analyst-rating source that
cross-confirms the primary rating — agreement raises trust, disagreement flags it.
"""

import requests


class FinnhubClient:
    def __init__(self, cfg):
        self.key = ((cfg.get("data", {}) or {}).get("finnhub_api_key") or "").strip()
        self.enabled = bool(self.key)
        self.base = "https://finnhub.io/api/v1"
        self._sess = requests.Session()

    def _get(self, path, params):
        if not self.enabled:
            return None
        params = dict(params)
        params["token"] = self.key
        try:
            r = self._sess.get(self.base + path, params=params, timeout=15)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    def recommendation(self, sym):
        d = self._get("/stock/recommendation", {"symbol": sym})
        return d[0] if isinstance(d, list) and d else None   # latest period

    def price_target(self, sym):
        return self._get("/stock/price-target", {"symbol": sym})

    def quote(self, sym):
        return self._get("/quote", {"symbol": sym})

    def market_news(self, category="general"):
        """Live general market news (free). Returns a list of {headline, datetime, source, ...}."""
        d = self._get("/news", {"category": category})
        return d if isinstance(d, list) else []


def analyst_confirmation(rec, fh):
    """Add Finnhub as a 2nd analyst source and compare to the primary rating.
    Sets rec['analyst_sources'] and rec['analyst_agreement']."""
    if not fh or not fh.enabled:
        return rec
    r = fh.recommendation(rec["ticker"])
    if not r:
        return rec
    sb = r.get("strongBuy", 0) or 0
    b = r.get("buy", 0) or 0
    h = r.get("hold", 0) or 0
    s = r.get("sell", 0) or 0
    ss = r.get("strongSell", 0) or 0
    total = sb + b + h + s + ss
    if not total:
        return rec
    mean = (sb * 1 + b * 2 + h * 3 + s * 4 + ss * 5) / total
    rec["finnhub_rec_mean"] = round(mean, 2)
    own = rec.get("rec_mean")
    if own is not None:
        rec["analyst_sources"] = 2
        rec["analyst_agreement"] = "متوافق" if abs(own - mean) <= 0.6 else "مختلف ⚠️"
    else:
        rec["rec_mean"] = round(mean, 2)        # use Finnhub if primary had none
        rec["analyst_sources"] = 1
        rec["analyst_agreement"] = "Finnhub فقط"
    return rec
