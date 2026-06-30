# -*- coding: utf-8 -*-
"""
peers.py — THE CHECK's 5-peer comparison, computed automatically from our universe.

For a stock, find its closest competitors (same sector/theme, nearest market cap)
and compare on the three numbers that matter for a quick read: revenue growth,
operating margin, and forward P/E (the cleanest valuation multiple for most
groups). Mark the best in each column. No web needed — runs every refresh.
"""

import math


def find_peers(rec, all_records, n=5):
    ind = rec.get("industry")
    sec = rec.get("sector")
    theme = rec.get("primary_theme")
    mc = rec.get("market_cap")
    sym = rec.get("ticker")
    if not mc or (isinstance(mc, float) and mc != mc) or mc <= 0:   # mc != mc rejects NaN
        return []

    def base():
        return [r for r in all_records
                if r.get("ticker") != sym and not r.get("is_fund") and r.get("market_cap")]

    # tightest match first: same INDUSTRY (e.g. Semiconductors), then theme, then sector.
    pool, have = [], set()
    for keyfn in (
        (lambda r: ind and r.get("industry") == ind),
        (lambda r: theme and r.get("primary_theme") == theme),
        (lambda r: r.get("sector") == sec),
    ):
        if len(pool) >= n:
            break
        for r in base():
            if r["ticker"] not in have and keyfn(r):
                pool.append(r)
                have.add(r["ticker"])
    # among the matched set, keep the ones closest in size (comparable peers)
    pool.sort(key=lambda r: abs(math.log10(r["market_cap"]) - math.log10(mc)))
    return pool[:n]


def compare(rec, all_records, n=5):
    """Return a peer-comparison table for the dashboard, or None if no peers found."""
    peers = find_peers(rec, all_records, n)
    if not peers:
        return None
    group = [rec] + peers
    rows = []
    for r in group:
        rows.append({
            "ticker": r.get("ticker"),
            "is_self": r.get("ticker") == rec.get("ticker"),
            "rev_growth": r.get("rev_growth"),
            "op_margin": r.get("operating_margin"),
            "fpe": r.get("forward_pe"),
            "conviction": r.get("conviction_score"),
            "halal": r.get("halal_status"),
        })

    def best(key, mode):
        vals = [(x["ticker"], x[key]) for x in rows
                if isinstance(x[key], (int, float)) and x[key] == x[key] and (x[key] > 0 if key == "fpe" else True)]
        if not vals:
            return None
        return (min if mode == "min" else max)(vals, key=lambda kv: kv[1])[0]

    return {
        "rows": rows,
        "best_growth": best("rev_growth", "max"),
        "best_margin": best("op_margin", "max"),
        "best_value": best("fpe", "min"),
    }
