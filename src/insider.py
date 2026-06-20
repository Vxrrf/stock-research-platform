# -*- coding: utf-8 -*-
"""
insider.py — insider tracker (spec §6).

Tracks CEO buying, director buying, executive selling, heavy insider selling,
and produces insider_confidence_score (0..10). Sources: FMP insider-trading
(when keyed) else yfinance insider_transactions (spotty but free). Runs on a
FOCUSED set, not the whole universe.
"""

from datetime import datetime, timezone, timedelta


def _fmp_insider(rec, fmp):
    sym = rec["ticker"]
    data = fmp.insider(sym) if fmp and fmp.enabled else None
    if not data:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    buys = sells = ceo_buy = dir_buy = exec_sell = 0
    sell_value = 0.0
    for tx in data:
        ttype = (tx.get("transactionType") or tx.get("acquistionOrDisposition") or "").upper()
        owner = (tx.get("typeOfOwner") or "").lower()
        is_buy = ttype.startswith("P") or ttype == "A" or "purchase" in ttype.lower()
        is_sell = ttype.startswith("S") or ttype == "D" or "sale" in ttype.lower()
        if is_buy:
            buys += 1
            if "chief executive" in owner or "ceo" in owner:
                ceo_buy += 1
            if "director" in owner:
                dir_buy += 1
        elif is_sell:
            sells += 1
            if any(x in owner for x in ("officer", "chief", "president", "ceo", "cfo")):
                exec_sell += 1
            try:
                sell_value += abs(float(tx.get("securitiesTransacted", 0)) * float(tx.get("price", 0) or 0))
            except Exception:
                pass
    return {"buys": buys, "sells": sells, "ceo_buy": ceo_buy,
            "dir_buy": dir_buy, "exec_sell": exec_sell, "sell_value": sell_value}


def _yf_insider(rec):
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        t = yf.Ticker(rec["ticker"])
        df = t.insider_transactions
    except Exception:
        return None
    if df is None or df.empty:
        return None
    buys = sells = ceo_buy = dir_buy = exec_sell = 0
    cols = {c.lower(): c for c in df.columns}
    txt_col = cols.get("transaction") or cols.get("text")
    pos_col = cols.get("position")
    for _, r in df.iterrows():
        txt = str(r.get(txt_col, "")).lower() if txt_col else ""
        pos = str(r.get(pos_col, "")).lower() if pos_col else ""
        is_buy = "buy" in txt or "purchase" in txt
        is_sell = "sale" in txt or "sell" in txt
        if is_buy:
            buys += 1
            if "ceo" in pos or "chief executive" in pos:
                ceo_buy += 1
            if "director" in pos:
                dir_buy += 1
        elif is_sell:
            sells += 1
            if any(x in pos for x in ("officer", "chief", "president", "ceo", "cfo")):
                exec_sell += 1
    return {"buys": buys, "sells": sells, "ceo_buy": ceo_buy,
            "dir_buy": dir_buy, "exec_sell": exec_sell, "sell_value": 0.0}


def _score(agg):
    """0..10 insider confidence. 5 = neutral. Buys & insider conviction raise it."""
    if not agg:
        return None, False
    base = 5.0
    base += min(3.0, agg["buys"] * 0.6)
    base += min(1.5, agg["ceo_buy"] * 1.0)
    base += min(1.0, agg["dir_buy"] * 0.4)
    base -= min(3.0, agg["sells"] * 0.3)
    base -= min(1.5, agg["exec_sell"] * 0.5)
    heavy = agg["sells"] >= 8 and agg["sells"] > agg["buys"] * 3
    if heavy:
        base -= 1.5
    return round(max(0.0, min(10.0, base)), 1), heavy


def track(records, cfg, fmp=None):
    rows = []
    for rec in records:
        agg = _fmp_insider(rec, fmp) or _yf_insider(rec)
        score, heavy = _score(agg)
        if agg:
            rec["insider_buy_count"] = agg["buys"]
            rec["insider_sell_count"] = agg["sells"]
        rec["insider_confidence_score"] = score
        rows.append({
            "ticker": rec["ticker"],
            "name": rec.get("name"),
            "insider_buy_count": rec.get("insider_buy_count"),
            "insider_sell_count": rec.get("insider_sell_count"),
            "ceo_buying": (agg or {}).get("ceo_buy"),
            "director_buying": (agg or {}).get("dir_buy"),
            "exec_selling": (agg or {}).get("exec_sell"),
            "heavy_selling": heavy,
            "insider_confidence_score": score,
            "data_source": rec.get("data_source"),
            "last_updated": rec.get("last_updated"),
            "data_freshness_status": rec.get("data_freshness_status"),
            "confidence": rec.get("confidence"),
        })
    return rows
