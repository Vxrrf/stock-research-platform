# -*- coding: utf-8 -*-
"""
main.py — Investment Research Platform orchestrator (spec §22).

    python src/main.py                 # full S&P-1500 universe + watchlist
    python src/main.py --watchlist     # only your starting watchlist (fast smoke)
    python src/main.py --limit 80      # cap universe size (quick test)
    python src/main.py --no-political   # skip the Congress-trades fetch

Pipeline priority (spec): data freshness → fundamental quality → halal →
opportunity vs risk → independent confirmations → portfolio risk management.

A research system, not a buy-signal machine. It never says "BUY NOW".
"""

import os
import sys
import argparse

# allow running as `python src/main.py` (src on path) or `python -m src.main`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import schema
from schema import (now_local, now_utc, iso, RANKED_COLS, WATCHLIST_COLS,
                    DISCOVERY_LOG_COLS, EARNINGS_COLS, INSIDER_COLS, NEWS_COLS,
                    POLITICAL_COLS, PORTFOLIO_COLS, AVOID_COLS)
from config_loader import load_config, load_external_lists, output_dir, ROOT
import datasource
import themes
import halal_gate
import scoring
import cross_source
import price_targets
import flags
import earnings as earnings_mod
import insider as insider_mod
import news as news_mod
import political as political_mod
import watchlist_memory as memory_mod
import actions
import recommendation
import portfolio as portfolio_mod
import outputs
import dashboard


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def load_universe(cfg):
    f = os.path.join(ROOT, (cfg.get("universe", {}) or {}).get("universe_file", "universe_data.txt"))
    if os.path.exists(f):
        try:
            with open(f, encoding="utf-8") as fh:
                u = [ln.strip().upper() for ln in fh if ln.strip()]
            if u:
                return u
        except Exception:
            pass
    # fallback: a small seed if no universe file
    return list((cfg.get("starting_watchlist") or []))


def discovery_eligible(rec, cfg, watchlist):
    if rec["ticker"] in watchlist:
        return False          # watchlist names aren't "discoveries"
    u = cfg.get("universe", {}) or {}
    mc = rec.get("market_cap")
    if mc is None or mc < u.get("market_cap_min", 1e9) or mc > u.get("market_cap_max", 1e11):
        return False
    if rec.get("price") is not None and rec["price"] < u.get("min_price", 5.0):
        return False
    adv = rec.get("avg_dollar_volume")
    if adv is not None and adv < u.get("min_avg_dollar_volume", 5e6):
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Investment Research Platform")
    ap.add_argument("--watchlist", action="store_true", help="only the starting watchlist (fast)")
    ap.add_argument("--from-cache", action="store_true", help="reprocess today's cached records only (no fetch)")
    ap.add_argument("--limit", type=int, default=0, help="cap universe size")
    ap.add_argument("--no-political", action="store_true", help="skip Congress-trades fetch")
    ap.add_argument("--no-trackers", action="store_true", help="skip earnings/insider/news/political")
    args = ap.parse_args()

    cfg = load_config()
    ext = load_external_lists()
    off = (cfg.get("run", {}) or {}).get("qatar_utc_offset", 3)
    run_dt = now_local(off)
    run_date = run_dt.strftime("%Y-%m-%d")
    run_ts = run_dt.strftime("%Y-%m-%d %H:%M")
    out_dir = output_dir(cfg)

    watchlist = set(cfg.get("starting_watchlist") or []) | ext.get("personal_watchlist", set())

    app_name = (cfg.get("app", {}) or {}).get("name", "مرصد الأسهم")
    print("=" * 64)
    print(f"  {app_name} — منصّة بحث استثماري شخصية")
    print("=" * 64)

    # ── ticker set ──
    if args.from_cache:
        import pickle, glob
        cfiles = sorted(glob.glob(os.path.join(ROOT, "cache", "records_*.pkl")))
        cache = pickle.load(open(cfiles[-1], "rb")) if cfiles else {}
        tickers = sorted(cache.keys())
        print(f"mode: FROM-CACHE reprocess ({len(tickers)} cached names, no fetch)")
    elif args.watchlist:
        tickers = sorted(watchlist)
        print(f"mode: WATCHLIST smoke test ({len(tickers)} names)")
    else:
        uni = load_universe(cfg)
        tickers = sorted(set(uni) | watchlist)
        if args.limit:
            keep = set(list(watchlist)) | set(uni[: args.limit])
            tickers = sorted(keep)
        print(f"mode: FULL universe — {len(tickers)} tickers (incl. {len(watchlist)} watchlist)")

    fmp = datasource.FMPClient(cfg)
    print(f"FMP primary: {'ACTIVE' if fmp.enabled else 'inactive (no key) → yfinance fallback'}")

    # ── 1) fetch (freshness + provenance handled inside) ──
    records, hits = datasource.fetch_many(tickers, cfg, want_deep=True, verbose=True, fmp=fmp)
    records = [r for r in records if r and r.get("price") is not None]
    if fmp.enabled and fmp.tier_note:
        print(f"ℹ️  {fmp.tier_note}")
    print(f"fetched {len(records)} valid records.")
    if not records:
        print("No data fetched (network/rate-limit?). Try again or set --watchlist.")
        return 1

    # ── 2) per-record core enrichment ──
    for rec in records:
        themes.classify(rec)
        halal_gate.apply(rec, cfg, extra={})            # extra={} → yfinance can't verify interest income
        rec["fundamental_score"] = scoring.fundamental_score(rec, cfg)
        cross_source.apply(rec, cfg, ext)
        rec["opportunity_score"] = scoring.opportunity_score(rec, cfg)
        rec["risk_score"] = scoring.risk_score(rec, cfg)
        price_targets.apply(rec, cfg)
        flags.crowding_flag(rec, cfg)
        flags.popular_not_cheap_flag(rec, cfg)
        rec["_discovery_eligible"] = discovery_eligible(rec, cfg, watchlist)

    # ── 3) focused set for the heavier trackers ──
    non_fail = [r for r in records if r.get("halal_status") != "fail"]
    non_fail.sort(key=lambda r: (r.get("fundamental_score") or 0), reverse=True)
    focus_syms = set(watchlist) | {r["ticker"] for r in non_fail[:30]}
    focused = [r for r in records if r["ticker"] in focus_syms]

    earnings_rows, insider_rows, news_rows = [], [], []
    political_rows, buys = [], {}
    market_risk = "—"
    if not args.no_trackers:
        print(f"trackers on {len(focused)} focused names (earnings/insider/news"
              f"{'' if args.no_political else '/political'})...")
        try:
            earnings_rows = earnings_mod.track(focused, cfg, fmp)
        except Exception as e:
            print(f"  earnings tracker skipped: {e}")
        try:
            insider_rows = insider_mod.track(focused, cfg, fmp)
        except Exception as e:
            print(f"  insider tracker skipped: {e}")
        try:
            news_rows, market_risk = news_mod.build(focused, records, cfg)
        except Exception as e:
            print(f"  news module skipped: {e}")
        if not args.no_political:
            try:
                pol_universe = {r["ticker"] for r in records}
                political_rows, buys = political_mod.fetch_recent(pol_universe, cfg, fmp=fmp)
            except Exception as e:
                print(f"  political tracker skipped: {e}")

    # ── 4) total score (fundamental primary + capped bonuses − penalties) ──
    news_max = (cfg.get("news", {}) or {}).get("max_weight_pct", 0.05)
    for rec in records:
        base = rec.get("fundamental_score") or 0.0
        theme_b = themes.theme_bonus(rec, cfg)
        ext_b = rec.get("external_bonus", 0) or 0
        earn = rec.get("earnings_score_adj", 0) or 0
        isc = rec.get("insider_confidence_score")
        ins = max(-2.0, min(2.0, (isc - 5) * 0.4)) if isc is not None else 0.0
        pol = political_mod.political_bonus(rec, buys, cfg) if buys else 0
        rec["political_bonus"] = pol
        sent = rec.get("_news_sentiment") or 0.0
        news_adj = round(sent * (news_max * base), 2)     # ≤ 5% of base
        rec["news_impact_score"] = news_adj
        hype = flags.hype_penalty(rec, cfg)
        total = _clamp(base + theme_b + ext_b + earn + ins + pol + news_adj - hype)
        rec["total_score"] = round(total, 1)
        rec["weaknesses"] = scoring.weaknesses(rec, cfg)

    # ── 5) watchlist memory (rising/fallen + new/returning) ──
    ranked = sorted(records, key=lambda r: (r.get("total_score") or 0), reverse=True)
    mem, deltas = memory_mod.update(cfg, records, run_date, [r["ticker"] for r in ranked])

    # ── 6) final action ──
    for rec in records:
        actions.apply(rec, cfg)

    # ── 7) buckets ──
    buckets = {a: [] for a in schema.ACTIONS}
    for rec in ranked:
        buckets[rec["action"]].append(rec)
    buckets["crowded"] = [r for r in ranked if r.get("crowded_late")]
    buckets["watchlist"] = [r for r in ranked if r["ticker"] in watchlist]

    # ── 8) discovery CSVs (spec §3) ──
    elig = [r for r in ranked if r.get("_discovery_eligible")]
    rm_min = (cfg.get("output", {}) or {}).get("research_more_min", 50)
    # a discovery = eligible + new + not disqualified (Avoid) + strong enough.
    # halal 'unknown' (Verify Halal First) is NOT a disqualifier — it's surfaced
    # as a pending-verification discovery (without an FMP key nothing reaches 'pass').
    new_disc = [r for r in elig if r.get("discovery_status") == "new_discovery"
                and r.get("action") != "Avoid"
                and (r.get("fundamental_score") or 0) >= rm_min]
    rising = [r for r in ranked if deltas.get(r["ticker"], 0) >= 5]
    fallen = []
    for r in ranked:
        e = mem.get(r["ticker"], {})
        if e.get("highest_score") and e.get("current_score") is not None:
            if (e["highest_score"] - e["current_score"]) >= 10 and r.get("fundamental_score", 0) >= 45:
                fallen.append(r)
    high_conv = [r for r in ranked if r.get("action") != "Avoid"
                 and (r.get("independent_confirmations", 0) >= 2)
                 and (r.get("fundamental_score") or 0) >= 65]

    if not new_disc and not args.watchlist:
        print("Discovery: No high-quality new discoveries this run.")

    # ── 9) portfolio + rebalancing ──
    portfolio_rows, growth_holdings = portfolio_mod.build_model(ranked, cfg)
    rebal = portfolio_mod.rebalance_flags(records, cfg, deltas)

    # ── 10) write everything ──
    def W(name, cols, rows, append=False):
        return outputs.write_csv(os.path.join(out_dir, name), cols, rows, append=append)

    rby = {r["ticker"]: r for r in records}
    W("ranked_stocks.csv", RANKED_COLS, outputs.rows_from_records(ranked, RANKED_COLS))
    W("avoid_list.csv", AVOID_COLS, [
        {"ticker": r["ticker"], "name": r.get("name"), "sector": r.get("sector"),
         "action": r["action"], "reason": r.get("action_reason"),
         "halal_status": r.get("halal_status"), "data_source": r.get("data_source"),
         "last_updated": r.get("last_updated"), "data_freshness_status": r.get("data_freshness_status"),
         "confidence": r.get("confidence")}
        for r in buckets["Avoid"]])
    W("new_discoveries.csv", RANKED_COLS, outputs.rows_from_records(new_disc, RANKED_COLS))
    W("rising_scores.csv", RANKED_COLS, outputs.rows_from_records(rising, RANKED_COLS))
    W("fallen_angels.csv", RANKED_COLS, outputs.rows_from_records(fallen, RANKED_COLS))
    W("high_conviction.csv", RANKED_COLS, outputs.rows_from_records(high_conv, RANKED_COLS))
    W("watchlist.csv", WATCHLIST_COLS, memory_mod.memory_rows(mem, rby))

    # discovery_log: append this run's examined records
    log_rows = []
    for r in ranked:
        row = {c: r.get(c) for c in DISCOVERY_LOG_COLS}
        row["run_timestamp"] = run_ts
        log_rows.append(row)
    W("discovery_log.csv", DISCOVERY_LOG_COLS, log_rows, append=True)

    W("earnings_tracker.csv", EARNINGS_COLS, earnings_rows)
    W("insider_tracker.csv", INSIDER_COLS, insider_rows)
    W("news_impact.csv", NEWS_COLS, news_rows)
    W("political_activity.csv", POLITICAL_COLS, political_rows)
    W("portfolio_model.csv", PORTFOLIO_COLS, portfolio_rows)

    # recommendation report (top candidates + research more)
    rec_targets = (buckets["Candidate"] + buckets["Research More"])[:15]
    rep = recommendation.build_report(rec_targets, cfg, market_risk=market_risk)
    with open(os.path.join(out_dir, "recommendation_report.md"), "w", encoding="utf-8") as f:
        f.write(rep)

    # dashboard
    from collections import Counter
    fc = Counter(r.get("data_freshness_status") for r in records)
    cc = Counter(r.get("confidence") for r in records)
    meta = {
        "generated_at": run_ts,
        "data_source": "FMP (primary)" if fmp.enabled else "yfinance (FMP key not set)",
        "fresh_counts": fc, "hi": cc.get("HIGH", 0), "med": cc.get("MEDIUM", 0), "low": cc.get("LOW", 0),
        "market_risk_today": market_risk, "examined": len(records), "universe": len(tickers),
    }
    html_doc = dashboard.build(records, buckets, portfolio_rows, news_rows, political_rows, meta, cfg)
    with open(os.path.join(out_dir, "dashboard.html"), "w", encoding="utf-8") as f:
        f.write(html_doc)

    # ── summary ──
    print("\n" + "=" * 64)
    print(f"  examined {len(records)} | "
          f"Candidate {len(buckets['Candidate'])} · "
          f"Research More {len(buckets['Research More'])} · "
          f"Verify Halal {len(buckets['Verify Halal First'])} · "
          f"Watch {len(buckets['Watch'])} · Avoid {len(buckets['Avoid'])}")
    print(f"  freshness: FRESH {fc.get('FRESH',0)} / STALE {fc.get('STALE',0)} / MISSING {fc.get('MISSING',0)}"
          f"  | confidence HIGH {cc.get('HIGH',0)} / MED {cc.get('MEDIUM',0)} / LOW {cc.get('LOW',0)}")
    print(f"  market risk today: {market_risk}")
    if rebal:
        print(f"  ⚖️ rebalance flags: {len(rebal)} (see console)")
        for fl in rebal:
            print(f"     {fl['ticker']}: {fl['flags']}")
    print("=" * 64)
    print(f"📊 dashboard : {os.path.join(out_dir, 'dashboard.html')}")
    print(f"🗂️  CSVs      : {out_dir}/ (ranked_stocks, watchlist, new_discoveries, …)")
    print(f"📝 report    : {os.path.join(out_dir, 'recommendation_report.md')}")
    print("\nTop 8 by total score:")
    for i, r in enumerate(ranked[:8], 1):
        print(f"  {i}. {r['ticker']:6} {r.get('total_score'):>5} | {r['action']:<18} | "
              f"halal={r.get('halal_status'):<7} | {r.get('data_freshness_status')}/{r.get('confidence')}")
    print("\n✅ done. This is research, not advice. Confirm halal on Zoya/Musaffa. No price is promised.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
