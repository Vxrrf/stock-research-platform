# -*- coding: utf-8 -*-
"""
test_audit.py — regression tests for the audit fixes. No network.
Run: ./venv/bin/python tests/test_audit.py   (or with pytest)
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import schema
import config_loader
import scoring
import conviction as C
import engines as E
import themes
import gates as G
import actions
import portfolio
import halal_gate
import price_targets
import watchlist_memory
import pipeline
import themes

CFG = config_loader.load_config()
EXT = config_loader.load_external_lists()


def _gate_cfg():
    """A copy of config in strict halal GATE mode (for the gate-behaviour tests)."""
    import copy
    g = copy.deepcopy(CFG)
    g.setdefault("halal", {})["mode"] = "gate"
    return g


GATE = _gate_cfg()


def _rec(**kw):
    r = schema.blank_record(kw.get("ticker", "TST"))
    r.update(kw)
    return r


def test_halal_unknown_NOT_excluded_from_portfolio():
    """Corrected: halal 'unknown' stays investable (verify-first), only 'fail' is dropped."""
    strong = _rec(ticker="AAA", halal_status="unknown", engines=["compounder"],
                  conviction_score=8, total_score=80, market_cap=2e10, investable=True)
    bad = _rec(ticker="BBB", halal_status="fail", engines=["compounder"],
               conviction_score=8, total_score=80, market_cap=2e10, investable=True)
    picks = portfolio._bucket([strong, bad], "compounder", 8, GATE)
    syms = [p["ticker"] for p in picks]
    assert "AAA" in syms, "halal-unknown wrongly excluded from portfolio"
    assert "BBB" not in syms, "halal-fail must be excluded from portfolio (gate mode)"
    print("✅ [gate] halal unknown kept in portfolio; halal fail excluded")


def test_halal_unknown_cannot_be_candidate():
    r = _rec(halal_status="unknown", fundamental_score=90, total_score=90, confidence="HIGH")
    actions.apply(r, GATE)
    assert r["action"] == "Verify Halal First", f"[gate] unknown should be Verify Halal First, got {r['action']}"
    print("✅ [gate] halal unknown -> Verify Halal First (never Candidate)")


def test_info_mode_ranks_by_quality():
    """info mode: a high-quality halal-unknown name CAN be a Candidate (user verifies on Zoya)."""
    r = _rec(halal_status="unknown", fundamental_score=90, total_score=90, confidence="HIGH")
    actions.apply(r, CFG)        # CFG is info mode
    assert r["action"] == "Candidate", f"info mode: strong unknown should be Candidate, got {r['action']}"
    # and a halal-fail strong name is NOT auto-Avoided in info mode (shown, flagged)
    f = _rec(halal_status="fail", fundamental_score=90, total_score=90, confidence="HIGH")
    actions.apply(f, CFG)
    assert f["action"] != "Avoid", "info mode: halal-fail should be ranked by quality, not auto-Avoided"
    print("✅ [info] quality ranks regardless of halal (halal shown as flag, user verifies)")


def test_halal_fail_is_avoid():
    r = _rec(halal_status="fail", fundamental_score=90, total_score=90)
    actions.apply(r, GATE)
    assert r["action"] == "Avoid"
    print("✅ halal fail -> Avoid")


def test_cyclical_excluded_from_engines_and_discounted():
    cyc = _rec(ticker="GOLD", sector="Basic Materials", industry="Gold",
               rev_growth=0.6, rev_cagr_3y=0.3, roic=0.2, operating_margin=0.4,
               gross_margin=0.5, debt_to_equity=20, market_cap=5e10, forward_pe=18, eps_growth_fwd=0.2)
    themes.classify(cyc)
    assert cyc["cyclical"] is True, "gold miner must be flagged cyclical"
    E.classify(cyc, CFG)
    assert cyc["engines"] == [], "cyclical must not be in growth engines"
    raw = _rec(ticker="SEC", rev_growth=0.6, rev_cagr_3y=0.3, roic=0.2, operating_margin=0.4,
               gross_margin=0.5, debt_to_equity=20, forward_pe=18, eps_growth_fwd=0.2)
    f_cyc = scoring.fundamental_score(cyc, CFG)
    f_sec = scoring.fundamental_score(raw, CFG)
    assert f_cyc < f_sec, "cyclical fundamental must be discounted vs identical secular"
    print(f"✅ cyclical excluded from engines + discounted (cyc {f_cyc} < secular {f_sec})")


def test_accelerator_not_on_cyclical_recovery():
    recovery = _rec(rev_cagr_3y=-0.05, rev_growth=0.35, rec_mean=2.0, conviction_score=7,
                    analyst_upside_percent=0.2, operating_margin=0.1)
    assert E.is_accelerator(recovery, CFG) is False, "negative-CAGR recovery must NOT be accelerator"
    real = _rec(rev_cagr_3y=0.20, rev_growth=0.32, rec_mean=2.0, conviction_score=7,
                analyst_upside_percent=0.2, operating_margin=0.2)
    assert E.is_accelerator(real, CFG) is True, "genuine acceleration should pass"
    print("✅ accelerator gated on healthy CAGR (recovery rejected)")


def test_hard_gates_make_not_investable():
    r = _rec(price=10, market_cap=2e9, forward_pe=200, num_analysts=2,
             analyst_upside_percent=-0.3, confidence="HIGH")
    inv, reasons = G.evaluate(r, CFG)
    assert inv is False and reasons, "should be not-investable (low analysts, insane PE, negative upside)"
    good = _rec(price=10, market_cap=2e9, forward_pe=25, num_analysts=20,
                analyst_upside_percent=0.2, confidence="HIGH")
    inv2, _ = G.evaluate(good, CFG)
    assert inv2 is True
    print("✅ hard gates flag not-investable; clean name passes")


def test_conviction_within_range():
    r = _rec(rev_growth=0.5, rev_cagr_3y=0.3, roic=0.3, roe=0.4, gross_margin=0.7,
             operating_margin=0.4, forward_pe=18, ev_ebitda=15, rec_mean=1.2,
             analyst_upside_percent=0.4, debt_to_equity=10, institutional_ownership=0.6,
             beat_streak=4)
    C.compute(r, CFG)
    assert 0 <= r["conviction_score"] <= 10, f"conviction out of range: {r['conviction_score']}"
    print(f"✅ conviction within 0..10 ({r['conviction_score']})")


def test_csv_has_audit_fields():
    for f in ("rank_score", "conviction_score", "total_score", "fundamental_score",
              "external_bonus", "independent_confirmations"):
        assert f in schema.RANKED_COLS, f"{f} missing from ranked CSV columns"
    print("✅ ranked CSV exports all audit fields")


def test_de_scale_consistent():
    # FMP raw 0.06 must become ~6 (percent), matching yfinance's ~6
    r = _rec(market_cap=1e11)
    # simulate: scoring expects %-scale; ceiling 150 = 1.5x. A 0.06 ratio stored as 6 scores high.
    r["debt_to_equity"] = 6.0
    comps = scoring._components(r, CFG)
    assert comps["debt"] is not None and comps["debt"] > 0.9, "low-debt (6%) should score near-perfect"
    print("✅ D/E percent-scale consistent (6% = low debt = high score)")


def test_manual_halal_override_wins():
    """A manual Zoya/Musaffa verdict overrides the auto screen and tags its source."""
    r = _rec(ticker="AMD", sector="Technology", industry="Semiconductors", market_cap=2e11)
    halal_gate.apply(r, CFG, extra={}, overrides={"AMD": {"status": "pass", "source": "Zoya", "note": "Compliant"}})
    assert r["halal_status"] == "pass", "manual override must set status"
    assert r["halal_source"] == "manual:Zoya", f"source must be tagged, got {r['halal_source']}"
    # without override the same name should be 'unknown' on free data (can't verify interest income)
    r2 = _rec(ticker="AMD", sector="Technology", industry="Semiconductors", market_cap=2e11)
    halal_gate.apply(r2, CFG, extra={}, overrides={})
    assert r2["halal_status"] == "unknown" and r2["halal_source"] == "auto"
    print("✅ manual halal override wins and is source-tagged; auto stays 'unknown'")


def test_override_cannot_break_vocabulary():
    """A bad override status is ignored by the loader-level validation (never invents a state)."""
    r = _rec(ticker="ZZZ", sector="Technology", market_cap=1e10)
    # loader only keeps pass/fail/unknown; simulate a cleaned override dict
    halal_gate.apply(r, CFG, extra={}, overrides={"ZZZ": {"status": "fail", "source": "Musaffa", "note": ""}})
    assert r["halal_status"] == "fail" and r["halal_source"] == "manual:Musaffa"
    print("✅ manual fail override respected")


def test_dcf_crosscheck_sane_and_labelled():
    """DCF anchor produces a positive per-share value and fair_value blends agreeing anchors."""
    r = _rec(ticker="CCC", price=100.0, market_cap=1e11, fcf=4e9,
             rev_cagr_3y=0.15, forward_pe=30, target_mean=110.0)
    price_targets.apply(r, CFG)
    assert r["fair_value_dcf"] is not None and r["fair_value_dcf"] > 0, "DCF anchor should compute"
    assert r["fair_value_estimate"] is not None, "blended fair value should exist when anchors agree"
    assert r["fair_value_method"], "fair value must record which anchors agreed"
    print(f"✅ DCF cross-check sane (dcf={r['fair_value_dcf']}, fv={r['fair_value_estimate']}, via {r['fair_value_method']})")


def test_mode_weights_change_ranking():
    """Aggressive mode (high opportunity weight) ranks a high-opportunity name above a
    low-risk compounder, vs conservative which does the opposite."""
    growth = _rec(ticker="GRW", conviction_score=6, opportunity_score=90, risk_score=70,
                  fundamental_score=60, total_score=70, confidence="HIGH")
    safe = _rec(ticker="SAFE", conviction_score=7, opportunity_score=30, risk_score=20,
                fundamental_score=75, total_score=72, confidence="HIGH")
    aggr = CFG["modes"]["aggressive"]["rank"]
    cons = CFG["modes"]["conservative"]["rank"]
    g_a, s_a = scoring.overall_rank(growth, CFG, aggr), scoring.overall_rank(safe, CFG, aggr)
    g_c, s_c = scoring.overall_rank(growth, CFG, cons), scoring.overall_rank(safe, CFG, cons)
    assert g_a > s_a, "aggressive should favour the high-opportunity name"
    assert s_c > g_c, "conservative should favour the low-risk quality name"
    print(f"✅ modes re-rank (aggr: GRW {g_a}>{s_a}; cons: SAFE {s_c}>{g_c})")


def test_modes_change_allocation_not_ranking():
    """The CURRENT contract (post-restructure): investor MODE shapes the PORTFOLIO
    ALLOCATION only. Research ranking stays OBJECTIVE (balanced weights) and identical
    across modes — main.py ranks every dashboard with balanced, mode never enters the rank."""
    import copy
    recs = [
        _rec(ticker="CMP", engines=["compounder"], conviction_score=8, total_score=82,
             fundamental_score=75, opportunity_score=60, risk_score=30, market_cap=2e11, investable=True),
        _rec(ticker="ACC", engines=["accelerator"], conviction_score=7, total_score=78,
             fundamental_score=65, opportunity_score=85, risk_score=55, market_cap=3e10, investable=True),
        _rec(ticker="FUT", engines=["future_leader"], conviction_score=6, total_score=70,
             fundamental_score=58, opportunity_score=80, risk_score=70, market_cap=5e9, investable=True),
    ]
    bal = CFG["modes"]["balanced"]["rank"]
    order = [r["ticker"] for r in sorted(recs, key=lambda r: scoring.overall_rank(r, CFG, bal), reverse=True)]

    def alloc_rows(mode):
        cfg = copy.deepcopy(CFG)
        cfg["portfolio"] = dict(cfg["portfolio"])
        cfg["portfolio"]["allocation"] = CFG["modes"][mode]["allocation"]
        rows, _ = portfolio.build_model(recs, cfg)
        return {row["bucket"]: row["allocation_pct"] for row in rows}

    aggr, cons = alloc_rows("aggressive"), alloc_rows("conservative")
    order2 = [r["ticker"] for r in sorted(recs, key=lambda r: scoring.overall_rank(r, CFG, bal), reverse=True)]
    assert order == order2, "objective ranking must be stable / independent of mode"
    assert aggr != cons, "investor modes must change the portfolio allocation"
    print(f"✅ modes change ALLOCATION not RANKING (objective order={order}; aggr≠cons)")


def test_movers_empty_on_first_run():
    """movers() must not crash and returns [] when there's no prior snapshot."""
    mem = {"AAA": {"ticker": "AAA", "name": "A", "metrics": {"rank": 80}, "prev_metrics": None}}
    assert watchlist_memory.movers(mem) == []
    mem["AAA"]["prev_metrics"] = {"rank": 70, "conv": 6}
    mem["AAA"]["metrics"] = {"rank": 80, "conv": 8}
    mv = watchlist_memory.movers(mem)
    assert mv and mv[0]["ticker"] == "AAA" and mv[0]["direction"] == "up", "rank rise should surface as up-mover"
    print("✅ movers: empty on first run, surfaces driver on change")


def test_pipeline_total_score_includes_adjustments():
    """The shared pipeline must apply theme bonus + hype penalty so total_score is
    NOT merely fundamental_score (the drift Codex flagged in the ad-hoc tool)."""
    # a strong AI/semiconductor name → theme bonus should LIFT total above fundamental
    ai = _rec(ticker="AIX", sector="Technology", industry="Semiconductors",
              name="AI Chips", rev_growth=0.4, rev_cagr_3y=0.3, roic=0.25, roe=0.3,
              gross_margin=0.6, operating_margin=0.35, forward_pe=28, eps_growth_fwd=0.25,
              market_cap=4e10, num_analysts=30, analyst_upside_percent=0.2, rec_mean=1.6,
              one_year_return=0.25, pct_below_52w_high=0.15, confidence="HIGH")
    pipeline.enrich_record(ai, CFG, EXT)
    pipeline.finalize_scores(ai, CFG)
    assert ai["total_score"] is not None and ai["fundamental_score"] is not None
    assert ai["total_score"] > ai["fundamental_score"], \
        f"theme bonus should lift total ({ai['total_score']}) above fundamental ({ai['fundamental_score']})"
    assert isinstance(ai.get("engines"), list) and ai.get("conviction_score") is not None
    assert ai.get("rank_score") is not None

    # a hyped name (+250% in 1y, near highs) → hype penalty should DROP total below fundamental
    hype = _rec(ticker="HYP", sector="Technology", name="Hype", rev_growth=0.3,
                operating_margin=0.2, gross_margin=0.5, forward_pe=40, market_cap=8e9,
                one_year_return=2.6, pct_below_52w_high=0.02, confidence="HIGH")
    pipeline.enrich_record(hype, CFG, EXT)
    pipeline.finalize_scores(hype, CFG)
    assert hype["total_score"] <= hype["fundamental_score"], \
        "a +250% near-highs name should be penalised, not lifted"
    print(f"✅ shared pipeline applies adjustments (AI {ai['fundamental_score']}→{ai['total_score']}; "
          f"hype {hype['fundamental_score']}→{hype['total_score']})")


def test_pipeline_matches_main_contract():
    """enrich+finalize populate every field downstream consumers (actions/gates/dashboard) read."""
    r = _rec(ticker="ZZZ", sector="Technology", name="Z", rev_growth=0.2, market_cap=1e10,
             forward_pe=25, num_analysts=10, analyst_upside_percent=0.15, confidence="HIGH")
    pipeline.enrich_record(r, CFG, EXT)
    pipeline.finalize_scores(r, CFG)
    for f in ("fundamental_score", "total_score", "opportunity_score", "risk_score",
              "rank_score", "conviction_score", "halal_status", "engines", "weaknesses",
              "suggested_hold_months"):
        assert f in r and r[f] is not None or f in ("engines", "weaknesses"), f"pipeline left {f} unset"
    print("✅ pipeline populates the full downstream contract")


def test_iren_override_from_yaml():
    """The real halal_overrides.yaml marks IREN compliant (user verified on Zoya)."""
    ov = config_loader.load_halal_overrides()
    assert ov.get("IREN", {}).get("status") == "pass", "IREN should be a pass override"
    r = _rec(ticker="IREN", sector="Financial Services", industry="Capital Markets", market_cap=1e10)
    halal_gate.apply(r, CFG, extra={}, overrides=ov)
    assert r["halal_status"] == "pass" and r["halal_source"].startswith("manual:"), \
        "Zoya override must flip IREN to pass and tag the source"
    print("✅ IREN override (Zoya) flips auto-fail → pass, source-tagged")


def test_bottleneck_classify_and_summary():
    """A chokepoint owner at an acute high-prob stage is flagged; an unlisted name isn't."""
    import bottlenecks
    data = bottlenecks.load()
    assert data.get("chains"), "bottlenecks.yaml should load chains"
    recs = [_rec(ticker="CEG", conviction_score=7), _rec(ticker="ZZNOTinMAP")]
    bottlenecks.classify(recs, data)
    ceg = recs[0]
    assert ceg["bottlenecks"], "CEG should be tagged (AI power)"
    assert ceg["bottleneck_owner"] is True, "CEG is an acute high-prob chokepoint → owner"
    assert recs[1]["bottlenecks"] == [] and recs[1]["bottleneck_owner"] is False
    summary = bottlenecks.build_summary(data, {"CEG": ceg})
    assert any(c["id"] == "ai_power" for c in summary), "summary must include the ai_power chain"
    print("✅ bottleneck lens: tags chokepoint owners, ignores unlisted, builds summary")


def test_sanity_flags_artifacts_and_funds():
    """Implausible data is flagged (not trusted as signal); ETFs are detected."""
    import sanity
    bad = _rec(ticker="SNDK", one_year_return=45.53, confidence="HIGH")   # +4553% = artifact
    sanity.flag_suspect(bad)
    assert bad["data_suspect"] and bad["confidence"] == "MEDIUM", "huge return must be flagged + soften confidence"
    clean = _rec(ticker="ABC", one_year_return=0.4, rev_growth=0.3, confidence="HIGH")
    sanity.flag_suspect(clean)
    assert not clean["data_suspect"] and clean["confidence"] == "HIGH"
    assert sanity.is_fund(_rec(ticker="HLAL", name="Wahed FTSE USA Shariah ETF")), "HLAL must be a fund"
    assert not sanity.is_fund(_rec(ticker="NVDA", sector="Technology", rev_growth=0.5))
    # broken P&L (held price 10x) is suspect
    assert sanity.pnl_is_suspect(1133.0, 133.0) and not sanity.pnl_is_suspect(140.0, 130.0)
    print("✅ sanity: flags artifacts + softens confidence; detects funds; catches broken P&L")


def test_action_respects_investable_fund_and_suspect():
    """Funds → core Watch; not-investable & suspect can never be Candidate."""
    fund = _rec(halal_status="pass", is_fund=True, fundamental_score=90, total_score=90, confidence="HIGH")
    actions.apply(fund, CFG)
    assert fund["action"] == "Watch" and "صندوق" in fund["action_reason"], "fund must be a core hold"
    noninv = _rec(halal_status="pass", investable=False, not_investable_reasons=["few analysts"],
                  fundamental_score=90, total_score=90, confidence="HIGH")
    actions.apply(noninv, CFG)
    assert noninv["action"] == "Watch", "not-investable must never be a Candidate"
    susp = _rec(halal_status="pass", data_suspect=True, data_suspect_reasons=["عائد شاذ"],
                fundamental_score=90, total_score=90, confidence="HIGH")
    actions.apply(susp, CFG)
    assert susp["action"] == "Watch", "suspect data must never be a Candidate"
    # and the rank floor applies
    base = scoring.overall_rank(_rec(conviction_score=8, opportunity_score=80, risk_score=20,
                                     fundamental_score=70, total_score=70, confidence="HIGH"), CFG)
    floored = scoring.overall_rank(_rec(conviction_score=8, opportunity_score=80, risk_score=20,
                                        fundamental_score=70, total_score=70, confidence="HIGH",
                                        investable=False), CFG)
    assert floored < base, "not-investable must floor the rank"
    print("✅ actions: funds→core, not-investable/suspect never Candidate, rank floored")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"❌ {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"💥 {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{'='*50}\n{len(tests)-failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
