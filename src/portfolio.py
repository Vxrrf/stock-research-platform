# -*- coding: utf-8 -*-
"""
portfolio.py — portfolio builder (spec §16) + rebalancing rules (spec §17).

Default model for a 25-year-old, high-risk, growth-focused investor who still
wants crisis protection (editable in config.yaml portfolio.allocation):
  55% growth stocks · 20% broad-market ETF · 10% semi/AI ETF
  5% healthcare/defensive ETF · 5% gold ETF · 5% cash

Rebalancing (every ~3 months): flag any single stock > 15%, any position down
25% from buy price. No automatic selling. Down + improving fundamentals =>
"Accumulation Candidate"; down + worsening => "Danger".
"""

import os
import csv

from config_loader import ROOT


def build_model(candidates, cfg):
    """Returns (rows for portfolio_model.csv, growth_holdings list)."""
    p = cfg.get("portfolio", {}) or {}
    alloc = p.get("allocation", {}) or {}
    etfs = p.get("etf_suggestions", {}) or {}
    max_pos = p.get("max_growth_positions", 12)

    # growth bucket = top halal-pass Candidates/Research-More by total_score
    elig = [r for r in candidates
            if r.get("halal_status") == "pass"
            and r.get("action") in ("Candidate", "Research More")]
    elig.sort(key=lambda r: (r.get("total_score") or 0), reverse=True)
    growth = elig[:max_pos]
    # honesty fallback: with no FMP key, halal can't reach 'pass' (interest income
    # unverifiable), so nothing is a Candidate yet. Surface the strongest
    # halal-not-fail names as PENDING verification rather than show an empty book.
    pending = False
    if not growth:
        pending = True
        cand = [r for r in candidates
                if r.get("halal_status") != "fail"
                and (r.get("fundamental_score") or 0) >= 50]
        cand.sort(key=lambda r: (r.get("total_score") or 0), reverse=True)
        growth = cand[:max_pos]

    rows = []
    bucket_labels = {
        "growth_stocks": "Growth stocks",
        "broad_market_etf": "Broad-market ETF",
        "semi_ai_etf": "Semiconductor / AI ETF",
        "healthcare_defensive_etf": "Healthcare / defensive ETF",
        "gold_etf": "Gold ETF",
        "cash": "Cash",
    }
    for key, label in bucket_labels.items():
        pct = alloc.get(key, 0.0)
        if key == "growth_stocks":
            holdings = ", ".join(r["ticker"] for r in growth) or "—"
            if pending:
                notes = (f"top {len(growth)} names by score — PENDING halal verification "
                         "(add an FMP key or confirm on Zoya/Musaffa before buying)")
            else:
                notes = (f"top {len(growth)} halal-pass growth names by total score; "
                         f"each ≤ {p.get('max_single_stock_pct', 0.15):.0%} of the book")
        elif key == "cash":
            holdings = "—"
            notes = "dry powder for volatility / accumulation"
        else:
            holdings = ", ".join(etfs.get(key, [])) or "—"
            notes = "diversifier / protection sleeve"
        rows.append({
            "bucket": label,
            "allocation_pct": f"{pct:.0%}",
            "suggested_holdings": holdings,
            "notes": notes,
        })
    # sanity note if allocation doesn't sum to 1
    s = sum(alloc.values())
    if abs(s - 1.0) > 0.001:
        rows.append({"bucket": "⚠️ check", "allocation_pct": f"{s:.0%}",
                     "suggested_holdings": "—",
                     "notes": "allocation does not sum to 100% — edit config.yaml"})
    return rows, growth


def _read_holdings():
    """Optional data/holdings.csv: ticker, buy_price, weight (0..1 or %)."""
    p = os.path.join(ROOT, "data", "holdings.csv")
    if not os.path.exists(p):
        return []
    out = []
    try:
        with open(p, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    out.append({
                        "ticker": (row.get("ticker") or "").upper().strip(),
                        "buy_price": float(row.get("buy_price") or 0) or None,
                        "weight": float(row.get("weight") or 0) or None,
                    })
                except Exception:
                    continue
    except Exception:
        return []
    return [h for h in out if h["ticker"]]


def rebalance_flags(records, cfg, deltas=None):
    """Apply §17 rules to optional holdings. Returns list of flag dicts."""
    p = cfg.get("portfolio", {}) or {}
    max_single = p.get("max_single_stock_pct", 0.15)
    dd = p.get("drawdown_flag_pct", -0.25)
    deltas = deltas or {}
    by_t = {r["ticker"]: r for r in records}
    flags = []
    for h in _read_holdings():
        rec = by_t.get(h["ticker"], {})
        price = rec.get("price")
        w = h["weight"]
        if w is not None and w > 1:
            w = w / 100.0
        note = []
        if w is not None and w > max_single:
            note.append(f"position {w:.0%} > {max_single:.0%} cap — trim to rebalance (no forced sell)")
        pnl = None
        if price and h["buy_price"]:
            pnl = price / h["buy_price"] - 1.0
            if pnl <= dd:
                improving = (deltas.get(h["ticker"], 0) > 0) or ((rec.get("fundamental_score") or 0) >= 60)
                if improving:
                    note.append(f"down {pnl:+.0%} but fundamentals improving — Accumulation Candidate")
                else:
                    note.append(f"down {pnl:+.0%} and fundamentals worsening — Danger")
        if note:
            flags.append({
                "ticker": h["ticker"],
                "weight": f"{w:.0%}" if w is not None else "—",
                "pnl": f"{pnl:+.0%}" if pnl is not None else "—",
                "flags": " | ".join(note),
            })
    return flags
