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
                "ticker": sym,
                "name": rec.get("name"),
                "first_discovery_date": run_date,
                "discovery_score": score,
                "highest_score": score,
                "current_score": score,
                "number_of_appearances": 1,
                "previous_rankings": [],
                "last_score": None,
            }
            rec["discovery_status"] = "new_discovery"
            deltas[sym] = 0.0
        else:
            entry["last_score"] = entry.get("current_score")
            deltas[sym] = score - (entry["last_score"] if entry["last_score"] is not None else score)
            entry["name"] = rec.get("name") or entry.get("name")
            entry["current_score"] = score
            entry["highest_score"] = max(entry.get("highest_score", score), score)
            entry["number_of_appearances"] = entry.get("number_of_appearances", 1) + 1
            rec["discovery_status"] = "returning_discovery"
        # record this run's ranking if present
        if sym in rank_of:
            entry.setdefault("previous_rankings", []).append([run_date, rank_of[sym]])
            entry["previous_rankings"] = entry["previous_rankings"][-12:]  # keep last 12
        entry["current_score"] = score
        mem[sym] = entry

    save_memory(cfg, mem)
    return mem, deltas


def memory_rows(mem, records_by_ticker):
    """Build watchlist.csv rows from memory, attaching provenance from this run."""
    rows = []
    for sym, e in mem.items():
        rec = records_by_ticker.get(sym, {})
        rows.append({
            "ticker": sym,
            "name": e.get("name"),
            "first_discovery_date": e.get("first_discovery_date"),
            "discovery_score": e.get("discovery_score"),
            "highest_score": e.get("highest_score"),
            "current_score": e.get("current_score"),
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
