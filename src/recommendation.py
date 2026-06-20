# -*- coding: utf-8 -*-
"""
recommendation.py — per-stock research report (spec §15, 13 sections).

This is RESEARCH output, never a buy signal. It never promises a price.
"""


def _pct(x, plus=True):
    if x is None:
        return "—"
    return f"{x:+.1%}" if plus else f"{x:.1%}"


def _money(x):
    return f"${x:,.2f}" if isinstance(x, (int, float)) else "—"


def _cap(x):
    if not isinstance(x, (int, float)):
        return "—"
    return f"${x/1e9:.1f}B" if x >= 1e9 else f"${x/1e6:.0f}M"


def _num(x, d=1):
    return f"{x:.{d}f}" if isinstance(x, (int, float)) else "—"


HALAL_LABEL = {
    "pass": "✅ pass (passes the approximate Sharia screen)",
    "unknown": "⚠️ unknown — Verify Halal First (do not act until confirmed)",
    "fail": "🔴 fail (fails the Sharia screen — Avoid)",
}


def _growth_drivers(rec):
    drivers = []
    if rec.get("primary_theme"):
        drivers.append(f"theme exposure: {', '.join(rec.get('themes') or [])}")
    if (rec.get("ai_exposure_score") or 0) >= 6:
        drivers.append(f"meaningful AI exposure (score {rec['ai_exposure_score']}/10)")
    if rec.get("rev_growth") is not None and rec["rev_growth"] > 0.15:
        drivers.append(f"revenue growing {_pct(rec['rev_growth'])} yoy")
    if rec.get("rev_cagr_3y") is not None and rec["rev_cagr_3y"] > 0.12:
        drivers.append(f"durable 3Y revenue CAGR {_pct(rec['rev_cagr_3y'])}")
    if rec.get("eps_growth_fwd") is not None and rec["eps_growth_fwd"] > 0.10:
        drivers.append(f"expected EPS growth {_pct(rec['eps_growth_fwd'])}")
    if rec.get("fcf_margin") is not None and rec["fcf_margin"] > 0.10:
        drivers.append(f"strong free-cash-flow margin {_pct(rec['fcf_margin'], plus=False)}")
    return drivers or ["growth drivers unclear from the quantitative data — needs deep research"]


def build(rec, cfg):
    L = []
    L.append(f"## {rec.get('name')} ({rec['ticker']}) — {rec.get('action')}")
    L.append(f"> total {_num(rec.get('total_score'))}/100 · fundamental {_num(rec.get('fundamental_score'))} · "
             f"opportunity {_num(rec.get('opportunity_score'))} · risk {_num(rec.get('risk_score'))} · "
             f"confidence {rec.get('confidence')} · data {rec.get('data_freshness_status')}")
    L.append("")
    # 1
    L.append(f"**1) Name & business:** {rec.get('name')} — {rec.get('sector') or '—'} / {rec.get('industry') or '—'}, "
             f"market cap {_cap(rec.get('market_cap'))}.")
    # 2
    L.append(f"**2) Analyst opinion:** {rec.get('rec_key') or '—'}"
             + (f" (mean {_num(rec.get('rec_mean'),2)}/5, {int(rec['num_analysts'])} analysts)" if rec.get('num_analysts') else ""))
    # 3
    L.append(f"**3) Current price & target:** {_money(rec.get('price'))} now · mean target {_money(rec.get('target_mean'))} "
             f"(range {_money(rec.get('target_low'))}–{_money(rec.get('target_high'))})")
    # 4
    L.append(f"**4) Expected upside:** {_pct(rec.get('analyst_upside_percent'))} to mean target.")
    # 5
    summ = (rec.get("summary") or "").strip()
    L.append(f"**5) Company overview:** {summ[:320] + '…' if summ else 'no description available.'}")
    # 6
    L.append(f"**6) Growth drivers:** " + "; ".join(_growth_drivers(rec)) + ".")
    # 7
    sent = rec.get("_news_sentiment")
    if sent is None:
        news = "no recent headline signal captured."
    elif sent > 0.15:
        news = f"recent news skews positive (sentiment {sent:+.2f}) — light tailwind."
    elif sent < -0.15:
        news = f"recent news skews negative (sentiment {sent:+.2f}) — watch for a catalyst risk."
    else:
        news = f"recent news roughly neutral (sentiment {sent:+.2f})."
    L.append(f"**7) Recent news & impact:** {news} (news affects the score by ≤5%, applied: {_num(rec.get('news_impact_score'),2)} pts)")
    # 8
    risks = list(rec.get("weaknesses") or [])
    if rec.get("risk_score") is not None:
        risks.insert(0, f"composite risk score {_num(rec['risk_score'])}/100")
    L.append(f"**8) Risks:** " + "; ".join(risks) + ".")
    # 9
    L.append(f"**9) Halal status:** {HALAL_LABEL.get(rec.get('halal_status'), '—')}")
    for r in (rec.get("halal_reasons") or [])[:2]:
        L.append(f"   - {r}")
    # 10
    flags = []
    if rec.get("crowded_late"):
        flags.append("CROWDED / LATE (near highs after a big run)")
    if rec.get("popular_not_cheap"):
        flags.append("POPULAR, NOT CHEAP (late-entry risk)")
    L.append(f"**10) Crowding / late-entry:** {'; '.join(flags) if flags else 'no crowding flag.'}")
    # 11
    L.append(f"**11) Suggested holding period:** {rec.get('suggested_holding_period') or '—'} "
             "(short 0–6m · medium 6–18m · long 18m+).")
    # 12
    L.append("**12) Exit conditions** (conditions, not dated sells):")
    for c in (rec.get("exit_conditions") or [])[:5]:
        L.append(f"   - {c}")
    # 13
    L.append(f"**13) Final action:** **{rec.get('action')}** — {rec.get('action_reason')}")
    L.append("")
    L.append("---")
    return "\n".join(L)


def build_report(records, cfg, market_risk="—"):
    from schema import now_local
    off = (cfg.get("run", {}) or {}).get("qatar_utc_offset", 3)
    now = now_local(off)
    app_name = (cfg.get("app", {}) or {}).get("name", "مرصد الأسهم")
    H = [
        f"# 📊 {app_name} — تقرير البحث",
        f"**Generated:** {now.strftime('%Y-%m-%d %H:%M')} (Qatar) · **Market risk today:** {market_risk}",
        "",
        "> Research only — not advice, not a buy signal, never a promised price. "
        "Halal status is approximate; confirm on Zoya/Musaffa. Final decision and responsibility are yours.",
        "",
        "---",
        "",
    ]
    if not records:
        H.append("_No qualifying names this run._")
        return "\n".join(H)
    for rec in records:
        H.append(build(rec, cfg))
        H.append("")
    return "\n".join(H)
