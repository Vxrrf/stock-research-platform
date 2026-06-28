# -*- coding: utf-8 -*-
"""
political.py — political / Congress trade tracking (spec §10). WEAK SIGNAL ONLY.

Sources (best-effort, in priority order):
  1) FMP v4 senate/house disclosures   — when an FMP key is set (live, premium).
  2) Free senate-stock-watcher mirror  — keyless public JSON (may be a snapshot).

Rules (encoded literally from the spec):
  * Weak signal only — "political interest only, not investment thesis".
  * NEVER increase a score only because a politician bought.
  * A small political_bonus (≤ config.political.bonus_max, default 3) is added in
    main.py ONLY to names we already like on fundamentals AND that a politician
    bought RECENTLY (within lookback). A stale snapshot therefore yields no bonus.
  * Degrades gracefully: any failure -> empty political_activity.csv (headers only).
"""

from datetime import datetime, timezone, timedelta

import requests

SENATE_MIRROR = ("https://raw.githubusercontent.com/timothycarambat/"
                 "senate-stock-watcher-data/master/aggregate/all_transactions.json")

_BUY = ("purchase", "buy")


def _fetch_json(url, timeout, params=None):
    try:
        r = requests.get(url, timeout=timeout, params=params)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _norm_date(s):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(s)[:19], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _fmp_rows(tickers, fmp, timeout):
    """FMP stable senate + house disclosures per symbol (premium plans only)."""
    if not (fmp and fmp.enabled):
        return []
    rows = []
    for sym in list(tickers)[:60]:
        for fetch, chamber in ((fmp.senate, "Senate"), (fmp.house, "House")):
            data = fetch(sym)
            if not isinstance(data, list):
                continue
            for tx in data:
                name = (f"{tx.get('firstName','')} {tx.get('lastName','')}".strip()
                        or tx.get("office") or tx.get("representative") or chamber)
                rows.append({
                    "_chamber": chamber,
                    "ticker": (tx.get("symbol") or sym).upper(),
                    "type": tx.get("type") or "",
                    "transaction_date": tx.get("transactionDate") or "",
                    "disclosure_date": tx.get("disclosureDate") or tx.get("dateRecieved") or "",
                    "politician": name,
                    "amount": tx.get("amount") or "",
                    "source": tx.get("link") or "FMP",
                })
    return rows


def _mirror_rows(want, timeout):
    data = _fetch_json(SENATE_MIRROR, timeout)
    rows = []
    for tx in data:
        tk = (tx.get("ticker") or "").upper().strip()
        if not tk or tk in ("--", "N/A") or tk not in want:
            continue
        rows.append({
            "_chamber": "Senate",
            "ticker": tk,
            "type": tx.get("type") or "",
            "transaction_date": tx.get("transaction_date") or "",
            "disclosure_date": tx.get("disclosure_date") or "",  # mirror usually lacks it
            "politician": tx.get("senator") or tx.get("representative") or "Senate",
            "amount": tx.get("amount") or "",
            "source": tx.get("ptr_link") or SENATE_MIRROR,
        })
    return rows


def fetch_recent(tickers, cfg, lookback_days=365, timeout=30, fmp=None):
    """
    Returns (rows for political_activity.csv, buys_by_ticker).
    rows include matching historical trades for context (clearly dated).
    buys_by_ticker counts only RECENT buys (within lookback) -> feeds the
    capped, fundamentals-gated political_bonus in main.py.
    """
    if (cfg.get("political", {}) or {}).get("disabled", False):
        return [], {}

    want = {str(t).upper() for t in tickers}
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    raw = _fmp_rows(want, fmp, timeout) or _mirror_rows(want, timeout)

    rows, buys = [], {}
    for tx in raw:
        tk = tx["ticker"]
        ttype = (tx.get("type") or "").lower()
        tdate = _norm_date(tx.get("transaction_date"))
        ddate = _norm_date(tx.get("disclosure_date"))
        delay = f"{(ddate - tdate).days}d" if (tdate and ddate) else ""
        is_buy = any(b in ttype for b in _BUY)
        recent = tdate is not None and tdate >= cutoff
        if is_buy and recent:
            buys[tk] = buys.get(tk, 0) + 1
        rows.append({
            "politician_name": tx.get("politician"),
            "ticker": tk,
            "transaction_type": tx.get("type") or "—",
            "transaction_date": tdate.strftime("%Y-%m-%d") if tdate else (tx.get("transaction_date") or ""),
            "estimated_value": tx.get("amount"),
            "disclosure_delay": delay,
            "source_url": tx.get("source"),
            "note": (f"{tx['_chamber']} disclosure — political interest only, not investment thesis"
                     + ("" if recent else " (historical)")),
        })

    rows.sort(key=lambda r: r.get("transaction_date", ""), reverse=True)
    return rows, buys


def political_bonus(rec, buys_by_ticker, cfg):
    """Capped, fundamentals-gated. Never the sole reason to like a name."""
    bmax = (cfg.get("political", {}) or {}).get("bonus_max", 3)
    sym = rec.get("ticker", "").upper()
    n = buys_by_ticker.get(sym, 0)
    if n <= 0:
        return 0
    if (rec.get("fundamental_score") or 0) < 55:   # only names we already like
        return 0
    bonus = min(bmax, n)
    rec.setdefault("_flag_notes", []).append(
        f"political interest: {n} recent Congress BUY disclosure(s) — weak signal only (+{bonus}), not a thesis"
    )
    return int(bonus)
