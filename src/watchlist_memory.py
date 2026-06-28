# -*- coding: utf-8 -*-
"""
watchlist_memory.py — persistent memory of every stock ever discovered (spec §4).

Tracks per ticker:
  first_discovery_date, discovery_score, highest_score, current_score,
  number_of_appearances, previous_rankings, discovery_status
  (returning_discovery vs new_discovery).

Stored as JSON at data/_state/watchlist_memory.json so it survives runs and
powers rising_scores / fallen_angels / returning-vs-new discovery logic.
"""

import os
import json

from config_loader import state_dir


def _age_days(first, now):
    from datetime import datetime
    try:
        a = datetime.strptime(str(first)[:10], "%Y-%m-%d")
        b = datetime.strptime(str(now)[:10], "%Y-%m-%d")
        return (b - a).days
    except Exception:
        return 0


def _path(cfg):
    return os.path.join(state_dir(cfg), "watchlist_memory.json")


def load_memory(cfg):
    p = _path(cfg)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_memory(cfg, mem):
    try:
        with open(_path(cfg), "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  could not save watchlist memory: {e}")


def update(cfg, records, run_date, ranked):
    """
    Update memory from this run.
      records : all scored records (list of dicts)
      run_date: 'YYYY-MM-DD'
      ranked  : list of tickers in rank order (1-based) used for previous_rankings
    Mutates each record's discovery_status and returns (memory, deltas) where
    deltas[ticker] = current - previous_current (for rising/falling detection).
    """
    mem = load_memory(cfg)
    rank_of = {t: i + 1 for i, t in enumerate(ranked)}
    deltas = {}

    for rec in records:
        sym = rec["ticker"]
        score = rec.get("total_score")
        if score is None:
            continue
        entry = mem.get(sym)
        if entry is None:
            entry = {
                "ticker": sym, "name": rec.get("name"),
                "first_discovery_date": run_date, "last_seen_date": run_date,
                "discovery_score": score, "highest_score": score, "lowest_score": score,
                "current_score": score, "number_of_appearances": 1, "times_seen": 1,
                "previous_rankings": [], "last_score": None, "score_trend": "new",
                "discovery_age_days": 0,
            }
            rec["discovery_status"] = "new_discovery"
            deltas[sym] = 0.0
        else:
            entry["last_score"] = entry.get("current_score")
            d = score - (entry["last_score"] if entry["last_score"] is not None else score)
            deltas[sym] = d
            entry["name"] = rec.get("name") or entry.get("name")
            entry["current_score"] = score
            entry["last_seen_date"] = run_date
            entry["highest_score"] = max(entry.get("highest_score", score), score)
            entry["lowest_score"] = min(entry.get("lowest_score", score), score)
            entry["number_of_appearances"] = entry.get("number_of_appearances", 1) + 1
            entry["times_seen"] = entry["number_of_appearances"]
            entry["score_trend"] = "up" if d >= 3 else ("down" if d <= -3 else "flat")
            entry["discovery_age_days"] = _age_days(entry.get("first_discovery_date"), run_date)
            rec["discovery_status"] = "returning_discovery"
        rec["score_trend"] = entry.get("score_trend")
        rec["discovery_age_days"] = entry.get("discovery_age_days")
        if sym in rank_of:
            entry.setdefault("previous_rankings", []).append([run_date, rank_of[sym]])
            entry["previous_rankings"] = entry["previous_rankings"][-12:]
        entry["current_score"] = score
        # snapshot key sub-scores so next run can explain WHY the score moved
        entry["prev_metrics"] = entry.get("metrics")
        entry["metrics"] = {
            "rank": rec.get("rank_score"), "conv": rec.get("conviction_score"),
            "opp": rec.get("opportunity_score"), "risk": rec.get("risk_score"),
            "fund": rec.get("fundamental_score"), "upside": rec.get("analyst_upside_percent"),
        }
        mem[sym] = entry

    save_memory(cfg, mem)
    return mem, deltas


def _driver(cur, prev):
    """Which single sub-score moved the most → a human reason for the rank change."""
    cands = []
    def add(label, cv, pv, scale):
        if cv is None or pv is None:
            return
        cands.append((abs((cv - pv) / scale), label, cv - pv))
    add("القناعة", cur.get("conv"), prev.get("conv"), 1.0)      # 0..10
    add("الفرصة", cur.get("opp"), prev.get("opp"), 10.0)        # 0..100
    add("المخاطرة", cur.get("risk"), prev.get("risk"), 10.0)
    add("الأساس", cur.get("fund"), prev.get("fund"), 10.0)
    if not cands:
        return "تغيّر عام في البيانات"
    cands.sort(reverse=True)
    _, label, dv = cands[0]
    return f"{label} {'ارتفعت' if dv > 0 else 'نزلت'}"


def movers(mem, limit=8, min_delta=2.0):
    """Top rank movers since last run, each with its main driver — 'why score changed'.
    Empty on the first ever run (no prior snapshot to compare)."""
    out = []
    for sym, e in mem.items():
        cur, prev = e.get("metrics") or {}, e.get("prev_metrics")
        if not prev:
            continue
        cr, pr = cur.get("rank"), prev.get("rank")
        if cr is None or pr is None:
            continue
        d = cr - pr
        if abs(d) < min_delta:
            continue
        out.append({
            "ticker": sym, "name": e.get("name"),
            "rank_delta": round(d, 1), "rank_now": round(cr, 1),
            "direction": "up" if d > 0 else "down",
            "driver": _driver(cur, prev),
        })
    out.sort(key=lambda x: -abs(x["rank_delta"]))
    return out[:limit]


def memory_rows(mem, records_by_ticker):
    """Build watchlist.csv rows from memory, attaching provenance from this run."""
    rows = []
    for sym, e in mem.items():
        rec = records_by_ticker.get(sym, {})
        rows.append({
            "ticker": sym,
            "name": e.get("name"),
            "first_discovery_date": e.get("first_discovery_date"),
            "last_seen_date": e.get("last_seen_date"),
            "discovery_age_days": e.get("discovery_age_days"),
            "discovery_score": e.get("discovery_score"),
            "highest_score": e.get("highest_score"),
            "lowest_score": e.get("lowest_score"),
            "current_score": e.get("current_score"),
            "score_trend": e.get("score_trend"),
            "times_seen": e.get("times_seen", e.get("number_of_appearances")),
            "number_of_appearances": e.get("number_of_appearances"),
            "previous_rankings": ";".join(f"{d}:#{r}" for d, r in e.get("previous_rankings", [])),
            "discovery_status": rec.get("discovery_status", "returning_discovery"),
            "action": rec.get("action", ""),
            "data_source": rec.get("data_source", ""),
            "last_updated": rec.get("last_updated", ""),
            "data_freshness_status": rec.get("data_freshness_status", ""),
            "confidence": rec.get("confidence", ""),
        })
    rows.sort(key=lambda r: (r["current_score"] is None, -(r["current_score"] or 0)))
    return rows
