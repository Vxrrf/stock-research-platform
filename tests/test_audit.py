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

CFG = config_loader.load_config()


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
    picks = portfolio._bucket([strong, bad], "compounder", 8, CFG)
    syms = [p["ticker"] for p in picks]
    assert "AAA" in syms, "halal-unknown wrongly excluded from portfolio"
    assert "BBB" not in syms, "halal-fail must be excluded from portfolio"
    print("✅ halal unknown kept in portfolio; halal fail excluded")


def test_halal_unknown_cannot_be_candidate():
    r = _rec(halal_status="unknown", fundamental_score=90, total_score=90, confidence="HIGH")
    actions.apply(r, CFG)
    assert r["action"] == "Verify Halal First", f"unknown should be Verify Halal First, got {r['action']}"
    print("✅ halal unknown -> Verify Halal First (never Candidate)")


def test_halal_fail_is_avoid():
    r = _rec(halal_status="fail", fundamental_score=90, total_score=90)
    actions.apply(r, CFG)
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
