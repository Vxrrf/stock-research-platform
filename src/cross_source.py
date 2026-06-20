# -*- coding: utf-8 -*-
"""
cross_source.py — grouped cross-source confirmation (spec §2).

Grouped confirmation, NOT naive list counting:
  investing_family = propicks + investing_ai     (max 6 pts)
  analyst_consensus = analyst_strong_buy         (max 5 pts)
  my_conviction = personal_watchlist             (max 4 pts)

Rules:
  * external bonus capped at 12 (config cross_source.external_bonus_cap)
  * independent_confirmations counts GROUPS that fired, not raw list hits
  * the fundamental score stays primary — this only adds a capped bonus
"""


def apply(rec, cfg, external_lists):
    cs = cfg.get("cross_source", {}) or {}
    cap = cs.get("external_bonus_cap", 12)
    groups = cs.get("groups", {}) or {}
    sym = rec.get("ticker", "").upper()

    fired = []
    total = 0.0
    detail = {}
    for gname, gconf in groups.items():
        lists = gconf.get("lists", []) or []
        gmax = gconf.get("max_points", 0)
        hits = sum(1 for ln in lists if sym in external_lists.get(ln, set()))
        if hits <= 0:
            continue
        # group fires once; points scale with fraction of its lists that agree
        frac = hits / max(1, len(lists))
        pts = round(gmax * frac, 2)
        fired.append(gname)
        detail[gname] = {"hits": hits, "of_lists": len(lists), "points": pts}
        total += pts

    external_bonus = round(min(cap, total), 2)
    rec["independent_confirmations"] = len(fired)
    rec["external_bonus"] = external_bonus
    rec["confirmation_groups"] = fired
    rec["_confirmation_detail"] = detail
    return rec
