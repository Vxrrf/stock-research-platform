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
from config_loader import (load_config, load_external_lists, load_halal_overrides,
                           load_why_notes, output_dir, ROOT)
import datasource
import peers as peers_mod
import themes
import halal_gate
import scoring
import pipeline
import conviction as conviction_mod
import engines as engines_mod
import cross_source
import price_targets
import flags
import earnings as earnings_mod
import insider as insider_mod
import news as news_mod
import political as political_mod
import sources as sources_mod
import signals as signals_mod
import watchlist_memory as memory_mod
import actions
import gates as gates_mod
import recommendation
import portfolio as portfolio_mod
import backtest as backtest_mod
import stops as stops_mod
import framework as framework_mod
import bottlenecks as bottlenecks_mod
import regime as regime_mod
import desk_note as desk_note_mod
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


def _cloud_price_refresh(records, cfg, names):
    """Cloud-reliable live PRICE refresh via Finnhub (free key, 60/min) for the displayed names.
    yfinance is blocked from cloud IPs, so when the GitHub Action runs (Mac off) this keeps the
    key names' prices fresh on top of the cached fundamentals. No-op if no Finnhub key (renders
    cached prices, freshness stays honest)."""
    import time
    import datetime as _dt
    import sources
    fh = sources.FinnhubClient(cfg)
    if not fh.enabled:
        print("cloud refresh: no Finnhub key → rendering cached prices (freshness stays honest)")
        return 0
    by_t = {r.get("ticker"): r for r in records if r.get("ticker")}
    targets = [t for t in names if t in by_t][:250]      # ~250 fits Finnhub free (60/min) in a few min
    today = _dt.date.today().isoformat()
    done = 0
    for i, t in enumerate(targets):
        q = fh.quote(t)
        px = (q or {}).get("c")
        if px and px > 0:
            r = by_t[t]
            r["price"] = float(px)
            r["last_updated"] = iso(now_utc())           # real refresh moment (not date-only) → FRESH, consistent with datasource
            r["data_source"] = (r.get("data_source") or "yfinance") + "+finnhub"
            datasource.refresh_freshness(r, cfg)         # → FRESH (fresh price timestamp)
            done += 1
        if (i + 1) % 55 == 0:
            time.sleep(62)                                # respect the 60/min free limit
    print(f"cloud refresh: Finnhub updated {done}/{len(targets)} live prices")
    return done


def main():
    ap = argparse.ArgumentParser(description="Investment Research Platform")
    ap.add_argument("--watchlist", action="store_true", help="only the starting watchlist (fast)")
    ap.add_argument("--from-cache", action="store_true", help="reprocess today's cached records only (no fetch)")
    ap.add_argument("--limit", type=int, default=0, help="cap universe size")
    ap.add_argument("--no-political", action="store_true", help="skip Congress-trades fetch")
    ap.add_argument("--live", action="store_true", help="force fresh fetch (ignore today's cache)")
    ap.add_argument("--smart", action="store_true",
                    help="one-button update: full scan + force-refresh YOUR watchlist/holdings live")
    ap.add_argument("--no-trackers", action="store_true", help="skip earnings/insider/news/political")
    ap.add_argument("--backtest", action="store_true", help="run the (honest) top-basket vs SPY backtest + cache it")
    ap.add_argument("--cloud", action="store_true",
                    help="cloud refresh (GitHub Actions, Mac off): load cache + refresh prices via Finnhub "
                         "(yfinance is blocked from cloud IPs). No-op without a Finnhub key.")
    args = ap.parse_args()
    if args.cloud:
        args.from_cache = True          # cloud renders from the committed cache, refreshing live prices

    cfg = load_config()
    ext = load_external_lists()
    halal_overrides = load_halal_overrides()      # your manual Zoya/Musaffa verdicts
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
    cached_records = None
    if args.from_cache:
        import pickle, glob
        cfiles = sorted(glob.glob(os.path.join(ROOT, "cache", "records_*.pkl")))
        # pick the RICHEST recent cache (guard against a partial cache written by a
        # rate-limited fetch — e.g. across a midnight re-fetch). Most records wins.
        best = {}
        for cf in cfiles[-3:]:
            try:
                c = pickle.load(open(cf, "rb"))
            except Exception:
                continue
            if isinstance(c, dict) and len(c) > len(best):
                best = c
        cached_records = list(best.values())
        tickers = sorted(best.keys())
        print(f"mode: FROM-CACHE reprocess ({len(tickers)} cached names — NO fetch, NO network)")
    elif args.watchlist:
        tickers = sorted(watchlist)
        print(f"mode: WATCHLIST smoke test ({len(tickers)} names)")
    else:
        uni = load_universe(cfg)
        # always include the tickers you care about: watchlist + holdings + influencer signals
        sig_tickers = {str(s.get("ticker") or "").upper() for s in signals_mod.load()[1] if s.get("ticker")}
        always = watchlist | sig_tickers
        tickers = sorted(set(uni) | always)
        if args.limit:
            tickers = sorted(set(always) | set(uni[: args.limit]))
        print(f"mode: FULL universe — {len(tickers)} tickers "
              f"(incl. {len(watchlist)} watchlist + {len(sig_tickers)} influencer signals)")

    fmp = datasource.FMPClient(cfg)
    print(f"FMP primary: {'ACTIVE' if fmp.enabled else 'inactive (no key) → yfinance fallback'}")

    # what to refresh LIVE: everything (--live), or just your watchlist (--smart)
    if args.live:
        force_set = set(tickers)
    elif args.smart:
        force_set = set(watchlist)
        args.no_trackers = True        # keep the one-button update fast; macro news still computes
        print(f"smart update: full scan + force-refresh {len(force_set)} of your names live")
    else:
        force_set = set()

    # ── 1) fetch (freshness + provenance handled inside) — OR reuse cache verbatim ──
    if cached_records is not None:
        records = [r for r in cached_records if r and r.get("price") is not None]
        # recompute freshness against TODAY — a cached quote is not 'FRESH' a week later
        for rec in records:
            # scrub any complex values an older buggy cache may hold (would poison comparisons)
            for _k, _v in list(rec.items()):
                if isinstance(_v, complex):
                    rec[_k] = None
            datasource.refresh_freshness(rec, cfg)
        from collections import Counter as _C
        _fc = _C(r.get("data_freshness_status") for r in records)
        print(f"reusing {len(records)} cached records (no fetch) — freshness recomputed: {dict(_fc)}")
        if args.cloud:        # GitHub-Actions path: refresh live prices via Finnhub (Mac off)
            _names = sorted(set(watchlist) | set(tickers[:240]))
            _cloud_price_refresh(records, cfg, _names)
    else:
        records, hits = datasource.fetch_many(tickers, cfg, want_deep=True, verbose=True, fmp=fmp, force_set=force_set)
        records = [r for r in records if r and r.get("price") is not None]
    if fmp.enabled and fmp.tier_note:
        print(f"ℹ️  {fmp.tier_note}")
    print(f"fetched {len(records)} valid records.")
    if not records:
        print("No data fetched (network/rate-limit?). Try again or set --watchlist.")
        return 1

    # ── 2) per-record core enrichment (shared pipeline) ──
    for rec in records:
        pipeline.enrich_record(rec, cfg, ext, overrides=halal_overrides)  # manual halal verdict wins
        rec["_discovery_eligible"] = discovery_eligible(rec, cfg, watchlist)

    # ── 3) focused set for the heavier trackers ──
    non_fail = [r for r in records if r.get("halal_status") != "fail"]
    non_fail.sort(key=lambda r: (r.get("fundamental_score") or 0), reverse=True)
    focus_syms = set(watchlist) | {r["ticker"] for r in non_fail[:30]}
    focused = [r for r in records if r["ticker"] in focus_syms]

    earnings_rows, insider_rows, news_rows = [], [], []
    political_rows, buys = [], {}
    market_risk = "—"
    # macro news + market risk always compute (instant, from the yaml) — even on fast updates
    try:
        news_rows, market_risk = news_mod.build(focused, records, cfg, headlines=not args.no_trackers)
    except Exception as e:
        print(f"  news module skipped: {e}")
    try:
        # LIVE market news (Finnhub, free) so 'today' is genuinely fresh + auto-updating in the
        # cloud — independent of any hand-maintained file. Falls back to the yaml if no key.
        live = news_mod.live_news(cfg, focus_tickers=sorted(watchlist))
        if live:
            news_rows = live + news_rows
            print(f"live news: {len(live)} fresh market headlines from Finnhub")
    except Exception as e:
        print(f"  live news skipped: {e}")
    if not args.no_trackers:
        print(f"trackers on {len(focused)} focused names (earnings/insider"
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
            fh = sources_mod.FinnhubClient(cfg)
            if fh.enabled:
                for rec in focused:
                    sources_mod.analyst_confirmation(rec, fh)
                print("  ✓ Finnhub 2nd analyst source confirmed")
        except Exception as e:
            print(f"  Finnhub confirmation skipped: {e}")
        if not args.no_political:
            try:
                pol_universe = {r["ticker"] for r in records}
                political_rows, buys = political_mod.fetch_recent(pol_universe, cfg, fmp=fmp)
            except Exception as e:
                print(f"  political tracker skipped: {e}")

    # ── 4·pre) forward-outlook reads bottleneck + catalyst tags and the PRIOR analyst
    #          snapshot (for revision DIRECTION) — so attach them BEFORE scoring ──
    bn_data = bottlenecks_mod.load()
    bottlenecks_mod.classify(records, bn_data)          # tag supply-chain chokepoint(s)
    why_notes = load_why_notes()
    for rec in records:
        rec["why_note"] = why_notes.get(str(rec.get("ticker") or "").upper())
    prev_mem = memory_mod.load_memory(cfg)              # cheap read; update() still writes the new snapshot later

    # ── 4) total score + conviction + engines + forward outlook + rank (shared pipeline) ──
    for rec in records:
        pipeline.finalize_scores(rec, cfg, buys=buys,
                                 prev_metrics=(prev_mem.get(rec["ticker"]) or {}).get("metrics"))

    # ── 4a) investability gates BEFORE ranking, then re-rank — so the not-investable
    #        rank floor reaches CSVs/memory too, not just the dashboard (Codex review fix) ──
    _bal_w = (cfg.get("modes", {}) or {}).get("balanced", {}).get("rank")
    gates_mod.apply_all(records, cfg, watchlist)
    for rec in records:
        rec["rank_score"] = scoring.overall_rank(rec, cfg, _bal_w)

    # ── 4d) THE CHECK peer comparison — only for the names we actually display (holdings + top) ──
    _ranked_now = sorted(records, key=lambda r: (r.get("rank_score") or 0), reverse=True)
    _peer_targets = set(watchlist) | {r["ticker"] for r in _ranked_now[:25] if not r.get("is_fund")}
    for rec in records:
        if rec["ticker"] in _peer_targets:
            rec["peers"] = peers_mod.compare(rec, records)

    # ── 4e) DATA-DRIVEN stop levels (per-stock from price history) + buy/sell plan ──
    #  Computed (history fetch) only on a live/smart run; from-cache reuses the cached metrics.
    if cached_records is not None:
        stop_metrics = stops_mod.load_cached(cfg)
    else:
        print(f"computing data-driven stops for {len(_peer_targets)} names (1y history)...")
        stop_metrics = stops_mod.compute_metrics(_peer_targets, cfg)
    for rec in records:
        m = stop_metrics.get(rec["ticker"])
        rec["stop_metrics"] = m
        if rec["ticker"] in _peer_targets and not rec.get("is_fund"):
            sp = stops_mod.stop_for(m, None, rec.get("price"))      # suggested-BUY framing (no cost basis)
            rec["trade"] = framework_mod.trade_plan(
                None, rec.get("price"), rec.get("playbook"), rec.get("conviction_score"),
                rec.get("lifecycle_status"), rec.get("fundamental_score"), sp)

    # ── 5) watchlist memory (rising/fallen + new/returning) ──
    # rank by the holistic overall score → #1 is the best across everything
    ranked = sorted(records, key=lambda r: (r.get("rank_score") or 0), reverse=True)
    mem, deltas = memory_mod.update(cfg, records, run_date, [r["ticker"] for r in ranked])
    moves = memory_mod.movers(mem)        # "why score changed" — top rank movers since last run

    # ── 5b) lifecycle status (never drop a name just because it's not new) ──
    for rec in records:
        e = mem.get(rec["ticker"], {})
        eng = rec.get("engines") or []
        conv = rec.get("conviction_score") or 0
        highest = e.get("highest_score") or 0
        current = e.get("current_score") or 0
        d = deltas.get(rec["ticker"], 0)
        if rec.get("discovery_status") == "new_discovery":
            lc = "New Discovery"
        elif "compounder" in eng and conv >= 7:
            lc = "Long-Term Compounder"
        elif conv >= 9:
            lc = "High Conviction"
        elif highest - current >= 12 and (rec.get("fundamental_score") or 0) >= 45 and conv < 6:
            lc = "Fallen Angel"
        elif d <= -5:
            lc = "Falling Conviction"
        elif ("future_leader" in eng) or ("accelerator" in eng):
            lc = "Emerging Opportunity"
        else:
            lc = "Returning"
        rec["lifecycle_status"] = lc

    # ── 6) final action (gates already applied at step 4a) ──
    for rec in records:
        actions.apply(rec, cfg)

    # ── 7) buckets (rebuilt per investor mode, since rank order changes) ──
    _hmode = ((cfg.get("halal", {}) or {}).get("mode") or "gate").lower()

    def _ok(r):
        halal_ok = (_hmode == "info") or (r.get("halal_status") != "fail")  # info: rank by quality
        return r.get("action") != "Avoid" and halal_ok and r.get("investable", True)

    def make_buckets(ranked_list):
        b = {a: [] for a in schema.ACTIONS}
        for rec in ranked_list:
            b[rec["action"]].append(rec)
        b["crowded"] = [r for r in ranked_list if r.get("crowded_late")]
        b["watchlist"] = [r for r in ranked_list if r["ticker"] in watchlist]
        # NOT INVESTABLE YET: data/gate problems (NOT halal-unknown), excluding holdings & halal-fail
        b["not_investable"] = [r for r in ranked_list if not r.get("investable", True)
                               and r["ticker"] not in watchlist
                               and r.get("halal_status") != "fail"]
        b["compounder"] = [r for r in ranked_list if "compounder" in (r.get("engines") or []) and _ok(r)]
        b["accelerator"] = [r for r in ranked_list if "accelerator" in (r.get("engines") or []) and _ok(r)]
        b["future_leader"] = sorted(
            [r for r in ranked_list if "future_leader" in (r.get("engines") or []) and _ok(r)],
            key=lambda r: (r.get("future_leader_score") or 0), reverse=True)
        return b

    buckets = make_buckets(ranked)

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
    holdings_eval = portfolio_mod.evaluate_holdings(records, cfg, deltas)

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

    # recommendation report — strong names: any engine OR conviction ≥6, halal not fail
    rec_targets = sorted(
        [r for r in ranked if r.get("halal_status") != "fail"
         and ((r.get("engines")) or (r.get("conviction_score") or 0) >= 6)],
        key=lambda r: (r.get("conviction_score") or 0, r.get("total_score") or 0), reverse=True)[:20]
    rep = recommendation.build_report(rec_targets, cfg, market_risk=market_risk)
    with open(os.path.join(out_dir, "recommendation_report.md"), "w", encoding="utf-8") as f:
        f.write(rep)

    # ── backtest (honest sanity check; network-heavy → only on --backtest, else cached) ──
    bt = backtest_mod.load_cached(cfg)
    if args.backtest:
        bt_basket = [r["ticker"] for r in ranked if _ok(r)][:15]
        print(f"backtest: downloading ~3y history for {len(bt_basket)} top names vs SPY "
              f"(honest check — has look-ahead/survivorship bias)...")
        bt = backtest_mod.run_and_cache(bt_basket, cfg, run_date)
        print(f"  backtest: {'ok' if bt.get('ok') else 'skipped — ' + str(bt.get('reason'))}")

    # ── dashboards: generate ALL investor modes (balanced/aggressive/conservative) ──
    from collections import Counter
    fc = Counter(r.get("data_freshness_status") for r in records)
    cc = Counter(r.get("confidence") for r in records)
    base_meta = {
        "generated_at": run_ts,
        "data_source": "FMP (primary)" if fmp.enabled else "yfinance (FMP key not set)",
        "fresh_counts": fc, "hi": cc.get("HIGH", 0), "med": cc.get("MEDIUM", 0), "low": cc.get("LOW", 0),
        "market_risk_today": market_risk, "examined": len(records), "universe": len(tickers),
        "signals_rows": signals_mod.rows(rby, cfg)[1],
        "movers": moves, "backtest": bt,
        "bottlenecks": bottlenecks_mod.build_summary(bn_data, rby),
    }
    modes = cfg.get("modes") or {"balanced": {"label": "⚖️ متوازن", "rank": None, "allocation": None}}
    mode_files = {"balanced": "index.html", "aggressive": "aggressive.html", "conservative": "conservative.html"}
    modes_nav = [(k, (modes[k] or {}).get("label", k), mode_files.get(k, k + ".html")) for k in modes]

    # RESEARCH is objective (one ranking, mode-independent). The mode shapes ONLY the
    # PORTFOLIO allocation — aggressive/balanced/defensive change how your money is split,
    # not which stocks are objectively best (the user's explicit design).
    bal_w = (cfg.get("modes", {}) or {}).get("balanced", {}).get("rank")
    for rec in records:
        rec["rank_score"] = scoring.overall_rank(rec, cfg, bal_w)
    ranked_obj = sorted(records, key=lambda r: (r.get("rank_score") or 0), reverse=True)
    buckets_obj = make_buckets(ranked_obj)

    # ── «العقل العاقل»: استشعار وضع السوق من إشاراتنا، وترشيح الوضع الأنسب (إضافة لا بديل) ──
    # persist the FSM/desk memory ONLY on authoritative runs (cloud or live) — a Mac --from-cache
    # render must not pollute the trend/episode state the cloud owns.
    _persist_state = bool(args.cloud or args.live)
    try:
        base_meta["regime"] = regime_mod.detect(records, market_risk, cfg, persist=_persist_state)
    except Exception as e:
        print(f"  regime sense skipped: {e}")
    # ── «صوت العقل المحترف»: مذكّرة مكتبٍ تقرأ اللوح وتقول ما تغيّر/ما يهمّ — مربوطة بأرقام حقيقية ──
    try:
        base_meta["desk_note"] = desk_note_mod.build_desk_note(
            records, base_meta, holdings_eval, deltas, mem, cfg, persist=_persist_state)
    except Exception as e:
        print(f"  desk note skipped: {e}")

    for mkey, mdef in modes.items():
        mdef = mdef or {}
        mode_cfg = dict(cfg)
        port = dict(cfg.get("portfolio", {}) or {})
        if mdef.get("allocation"):
            port["allocation"] = mdef["allocation"]
        mode_cfg["portfolio"] = port
        portfolio_rows_m, _ = portfolio_mod.build_model(ranked_obj, mode_cfg)
        meta = dict(base_meta)
        meta.update({
            "holdings_eval": portfolio_mod.evaluate_holdings(records, mode_cfg, deltas),
            "active_mode": mkey, "active_mode_label": mdef.get("label", mkey),
            "active_mode_desc": mdef.get("desc", ""), "modes_nav": modes_nav,
        })
        html_doc = dashboard.build(records, buckets_obj, portfolio_rows_m, news_rows, political_rows, meta, mode_cfg)
        with open(os.path.join(out_dir, mode_files.get(mkey, mkey + ".html")), "w", encoding="utf-8") as f:
            f.write(html_doc)
        if mkey == "balanced":
            with open(os.path.join(out_dir, "dashboard.html"), "w", encoding="utf-8") as f:
                f.write(html_doc)        # back-compat default name

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
    print("\nTop 8 (best overall — holistic rank):")
    for i, r in enumerate(ranked[:8], 1):
        print(f"  {i}. {r['ticker']:6} rank={r.get('rank_score'):>5} conv={r.get('conviction_score')} | {r['action']:<18} | "
              f"halal={r.get('halal_status'):<7} | {r.get('data_freshness_status')}/{r.get('confidence')}")
    print("\n✅ done. This is research, not advice. Confirm halal on Zoya/Musaffa. No price is promised.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
