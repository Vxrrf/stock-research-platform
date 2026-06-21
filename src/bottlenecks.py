# -*- coding: utf-8 -*-
"""
bottlenecks.py — the "bottleneck lens": map each stock to the supply-chain
chokepoint(s) it sits in, so we hunt the NEXT constraint before the crowd.

Knowledge map lives in data/bottlenecks.yaml (curated, honesty-labelled). This
module:
  * load()            → the chains map
  * classify(records) → tag each record with the bottleneck stages it belongs to
  * build_summary()   → resolve every chain/stage's tickers against THIS run's
                        records (coverage + halal + conviction) for the dashboard

Honesty: the map is reasoned analysis up to ~early 2026, not live data or a
prophecy. Every stock here still passes through the halal + conviction filters —
a great bottleneck owner that fails the Sharia screen is NOT for us.
"""

import os
import yaml

from config_loader import ROOT

_PATH = os.path.join(ROOT, "data", "bottlenecks.yaml")

ROLE_RANK = {"chokepoints": "chokepoint", "players": "player", "early": "early"}


def load():
    try:
        with open(_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"⚠️  could not load bottlenecks.yaml: {e}")
        return {}


def _stage_tickers(stage):
    """Yield (sym, role) for every ticker listed in a stage."""
    for key, role in ROLE_RANK.items():
        for sym in (stage.get(key) or []):
            yield str(sym).upper(), role


def classify(records, data=None):
    """Tag each record with rec['bottlenecks'] = [{chain, icon, stage, status, prob, role}].
    Also sets rec['bottleneck_owner'] = True when it's a chokepoint at an active
    (acute/building) high-probability stage — i.e. it OWNS a real, current bottleneck."""
    data = data or load()
    index = {}        # sym -> list of tags
    for chain in (data.get("chains") or []):
        for stage in (chain.get("stages") or []):
            for sym, role in _stage_tickers(stage):
                index.setdefault(sym, []).append({
                    "chain": chain.get("name"), "chain_id": chain.get("id"),
                    "icon": chain.get("icon", "🔗"), "stage": stage.get("name"),
                    "status": stage.get("status"), "prob": stage.get("prob"),
                    "role": role,
                })
    for rec in records:
        tags = index.get(str(rec.get("ticker") or "").upper(), [])
        rec["bottlenecks"] = tags
        rec["bottleneck_owner"] = any(
            t["role"] == "chokepoint" and t["status"] in ("acute", "building")
            and t["prob"] == "high" for t in tags)
    return records


def build_summary(data, records_by_ticker):
    """Resolve the map against this run's records for the dashboard.
    Returns a list of chains, each with stages, each stage's tickers annotated with
    covered / halal_status / conviction so the dashboard can colour + rank them."""
    out = []
    for chain in (data.get("chains") or []):
        stages = []
        for stage in (chain.get("stages") or []):
            syms = []
            for sym, role in _stage_tickers(stage):
                r = records_by_ticker.get(sym)
                syms.append({
                    "sym": sym, "role": role,
                    "covered": r is not None,
                    "halal": (r or {}).get("halal_status"),
                    "halal_source": (r or {}).get("halal_source"),
                    "conviction": (r or {}).get("conviction_score"),
                    "cyclical": bool((r or {}).get("cyclical")),
                })
            # owners first, then by our conviction (covered + high conviction floats up)
            order = {"chokepoint": 0, "player": 1, "early": 2}
            syms.sort(key=lambda s: (order.get(s["role"], 3), -(s["conviction"] or 0)))
            stages.append({
                "name": stage.get("name"), "status": stage.get("status"),
                "prob": stage.get("prob"), "timing": stage.get("timing"),
                "note": stage.get("note"), "coverage_note": stage.get("coverage_note"),
                "tickers": syms,
            })
        out.append({
            "id": chain.get("id"), "name": chain.get("name"), "icon": chain.get("icon", "🔗"),
            "confidence": chain.get("confidence"), "thesis": chain.get("thesis"),
            "why_us": chain.get("why_us"), "stages": stages,
        })
    return out
