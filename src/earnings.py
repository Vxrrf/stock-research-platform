# -*- coding: utf-8 -*-
"""
earnings.py — earnings tracker (spec §5).

Tracks: next earnings date, EPS estimate, revenue estimate, actual EPS/revenue,
beat/miss, beat streak, guidance (best-effort). Consistent beats raise the
earnings adjustment; repeated misses lower it (bounded by config.earnings).

Sources: FMP earnings calendar when a key is set; otherwise yfinance
(`calendar`, `earnings_dates`). Runs on a FOCUSED set (candidates / watchlist),
not the whole universe, to keep runs fast.
"""

from datetime import datetime, timezone


def _to_date(x):
    try:
        if hasattr(x, "strftime"):
            return x.strftime("%Y-%m-%d")
        s = str(x)
        return s[:10] if s else None
    except Exception:
        return None


def _yf_earnings(rec):
    """Best-effort yfinance earnings enrichment for one record."""
    try:
        import yfinance as yf
    except Exception:
        return {}
    sym = rec["ticker"]
    out = {}
    try:
        t = yf.Ticker(sym)
    except Exception:
        return {}

    # next earnings date + estimates from .calendar
    try:
        cal = t.calendar
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if isinstance(ed, (list, tuple)) and ed:
                out["next_earnings_date"] = _to_date(ed[0])
            elif ed:
                out["next_earnings_date"] = _to_date(ed)
            out["eps_estimate"] = cal.get("EPS Estimate")
            out["revenue_estimate"] = cal.get("Revenue Estimate")
    except Exception:
        pass

    # history of beats/misses from .earnings_dates (recent window only)
    try:
        try:
            ed = t.get_earnings_dates(limit=12)
        except Exception:
            ed = t.earnings_dates
        if ed is not None and not ed.empty:
            ed = ed.head(12)
            cols = {c.lower(): c for c in ed.columns}
            est_c = cols.get("eps estimate")
            rep_c = cols.get("reported eps")
            if est_c and rep_c:
                rows = ed[[est_c, rep_c]].dropna()
                streak = 0
                last = None
                results = []
                # earnings_dates is most-recent-first; iterate past quarters
                for _, r in rows.iterrows():
                    est, rep = r[est_c], r[rep_c]
                    if est is None:
                        continue
                    if "actual_eps" not in out:        # latest reported quarter
                        out["actual_eps"] = round(float(rep), 4)
                        out["eps_estimate"] = out.get("eps_estimate") or round(float(est), 4)
                    res = "beat" if rep >= est else "miss"
                    results.append(res)
                if results:
                    last = results[0]
                    # streak of same most-recent result (capped to the window)
                    for res in results:
                        if res == last:
                            streak += 1
                        else:
                            break
                    streak = min(streak, 12)
                    out["last_beat_miss"] = last
                    out["beat_streak"] = streak if last == "beat" else -streak
    except Exception:
        pass
    return out


def track(records, cfg, fmp=None):
    """Enrich a focused list of records with earnings fields + earnings_score_adj.
    Returns list of CSV row dicts (schema.EARNINGS_COLS)."""
    e = cfg.get("earnings", {}) or {}
    beat_bonus = e.get("beat_bonus_per_beat", 1.5)
    miss_pen = e.get("miss_penalty_per_miss", 2.0)
    cap = e.get("max_abs_adjust", 6)
    rows = []

    for rec in records:
        info = {}
        # FMP path could be added here when keyed; yfinance is the reliable free path
        info = _yf_earnings(rec)
        for k, v in info.items():
            if v is not None:
                rec[k] = v

        streak = rec.get("beat_streak") or 0
        adj = 0.0
        if streak > 0:
            adj = min(cap, beat_bonus * min(streak, 4))
        elif streak < 0:
            adj = max(-cap, miss_pen * streak)   # streak negative
        rec["earnings_score_adj"] = round(adj, 1)

        rows.append({
            "ticker": rec["ticker"],
            "name": rec.get("name"),
            "next_earnings_date": rec.get("next_earnings_date"),
            "eps_estimate": rec.get("eps_estimate"),
            "revenue_estimate": rec.get("revenue_estimate"),
            "actual_eps": rec.get("actual_eps"),
            "actual_revenue": rec.get("actual_revenue"),
            "last_beat_miss": rec.get("last_beat_miss"),
            "beat_streak": rec.get("beat_streak"),
            "guidance": rec.get("guidance"),
            "earnings_score_adj": rec.get("earnings_score_adj"),
            "data_source": rec.get("data_source"),
            "last_updated": rec.get("last_updated"),
            "data_freshness_status": rec.get("data_freshness_status"),
            "confidence": rec.get("confidence"),
        })
    return rows
