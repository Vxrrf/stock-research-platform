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


def _bucket(records, engine, cap, cfg):
    """Members of an engine, halal not-fail, sorted by conviction."""
    out = [r for r in records
           if engine in (r.get("engines") or []) and r.get("halal_status") != "fail"]
    out.sort(key=lambda r: (r.get("conviction_score") or 0, r.get("total_score") or 0), reverse=True)
    return out[:cap]


def build_model(candidates, cfg):
    """Engine-based allocation. Returns (rows for portfolio_model.csv, picks dict)."""
    p = cfg.get("portfolio", {}) or {}
    alloc = p.get("allocation", {}) or {}
    etfs = p.get("etf_suggestions", {}) or {}

    comp = _bucket(candidates, "compounder", p.get("max_compounders", 8), cfg)
    accel = _bucket(candidates, "accelerator", p.get("max_accelerators", 8), cfg)
    fut = _bucket(candidates, "future_leader", p.get("max_future_leaders", 10), cfg)

    rows = []
    specs = [
        ("compounders", "🏛️ مُركِّبون (نواة)", comp,
         f"جودة تدوم — موزّعة بالقناعة، كل اسم ≤ {p.get('max_single_compounder_pct', 0.12):.0%}"),
        ("accelerators", "🚀 مُسرِّعون (6–24ش)", accel, "نمو يتسارع — فرص متوسطة المدى"),
        ("future_leaders", "🌱 قادة المستقبل", fut,
         f"رهانات صغيرة موزّعة (x3–x10) — كل اسم ≤ {p.get('max_single_future_leader_pct', 0.03):.0%} عشان -80% يبقى محتمَل"),
        ("broad_market_etf", "🛡️ ETF حلال/واسع", None, "تحوّط واسع متوافق شرعياً"),
        ("gold_etf", "🥇 ذهب (حماية)", None, "حماية وقت الأزمات (الحرب/النفط الحين)"),
        ("cash", "💵 كاش (ذخيرة)", None, "ذخيرة للتقلّب والشراء بالهبوط"),
    ]
    for key, label, bucket, note in specs:
        pct = alloc.get(key, 0.0)
        if bucket is not None:
            holdings = ", ".join(r["ticker"] for r in bucket) or "—"
        elif key == "cash":
            holdings = "—"
        else:
            holdings = ", ".join(etfs.get(key, [])) or "—"
        rows.append({
            "bucket": label,
            "allocation_pct": f"{pct:.0%}",
            "suggested_holdings": holdings,
            "notes": note,
        })
    s = sum(alloc.values())
    if abs(s - 1.0) > 0.001:
        rows.append({"bucket": "⚠️ تحقّق", "allocation_pct": f"{s:.0%}",
                     "suggested_holdings": "—",
                     "notes": "المجموع لا يساوي 100% — عدّل config.yaml"})
    return rows, {"compounders": comp, "accelerators": accel, "future_leaders": fut}


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


def evaluate_holdings(records, cfg, deltas=None):
    """For each owned name (data/holdings.csv): recommend add / keep / review / exit
    based on conviction + lifecycle + drawdown. Research framing — never buy/sell now."""
    deltas = deltas or {}
    by = {r["ticker"]: r for r in records}
    rows = []
    for h in _read_holdings():
        r = by.get(h["ticker"])
        if not r:
            rows.append({"ticker": h["ticker"], "name": "—", "conviction": None, "rank": None,
                         "pnl": None, "halal": "—", "lifecycle": "—",
                         "verdict": "⚪ لا بيانات — حدّث", "why": "ما لقيت بيانات هالسهم هالتشغيل"})
            continue
        conv = r.get("conviction_score") or 0
        lc = r.get("lifecycle_status")
        hal = r.get("halal_status")
        pnl = (r["price"] / h["buy_price"] - 1) if (r.get("price") and h.get("buy_price")) else None
        if hal == "fail":
            verdict, why = "🔴 بيع — غير متوافق شرعياً", "فشل الفلتر الشرعي"
        elif conv >= 8:
            verdict, why = "🟢 احتفظ / زِد", f"قناعة عالية {conv}/10"
        elif pnl is not None and pnl <= cfg.get("portfolio", {}).get("drawdown_flag_pct", -0.25) and conv >= 6:
            # سهم قوي هبط = فرصة شراء، مو بيع (لا تبيع الجوهرة بالغلط)
            verdict, why = "🔵 فرصة تجميع (لا تبيع)", f"هبط {pnl:+.0%} لكن الأساسيات قوية (قناعة {conv}/10)"
        elif conv < 5 or (lc == "Falling Conviction") or (lc == "Fallen Angel" and (r.get("fundamental_score") or 0) < 45):
            # don't say 'sell' on a Fallen Angel that still has strong fundamentals (panic-sell guard)
            verdict, why = "🔴 بيع", f"قناعة ضعيفة/تنزل ({conv}/10){' · '+lc if lc else ''}"
        else:
            verdict, why = "⚪ احتفظ", f"قناعة {conv}/10، أداء مستقر"
        rows.append({"ticker": r["ticker"], "name": r.get("name"), "conviction": conv,
                     "rank": r.get("rank_score"), "pnl": pnl, "halal": hal,
                     "lifecycle": lc, "verdict": verdict, "why": why})
    # best overall first (by holistic rank), unknowns last
    rows.sort(key=lambda x: (x["rank"] is None, -(x["rank"] or 0)))
    return rows


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
