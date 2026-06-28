# -*- coding: utf-8 -*-
"""
forward.py — النظرة المستقبلية (Forward Outlook).

A coverage-aware, None-safe forward-looking score (0–10) + confidence (HIGH/MED/LOW)
+ human drivers, LED by the DIRECTION analysts are moving estimates/targets
(run-over-run from our OWN watchlist memory — real, dated, never fabricated).

HONESTY CONTRACT (mirrors conviction.py):
  • a missing signal is SKIPPED from the weighted average, never coerced to 0
    (coercing to 0 both understates the score AND fakes precision).
  • sparse data lowers coverage → damps the score AND lowers the confidence flag.
  • first-sight tickers (no prior snapshot) → revision None → confidence forced LOW
    with the honest reason "الاتجاه غير متاح بعد".
  • this is a weighted EXPECTATION, labelled as such — not advice, not a prophecy.
"""

from datetime import datetime

DISCLAIMER_AR = ("نظرة مستقبلية = توقّع مرجّح من اتجاه تقديرات المحللين والنمو المتوقّع "
                 "والمحفّزات وعنق الزجاجة — ليست وعداً ولا نبوءة، والأرقام لحظة الفحص.")

# weights (revisions-first); sum = 100
WEIGHTS = {
    "revision": 35, "eps_growth": 20, "bottleneck": 12, "peg": 9,
    "upside": 9, "fair_value": 6, "why_catalyst": 5, "valuation_room": 4, "catalyst_near": 4,
}
_WTOTAL = float(sum(WEIGHTS.values()))
NOISE_FLOOR = 0.03          # ignore target moves below ±3% (yfinance/FMP re-key noise)
WHY_FRESH_DAYS = 120        # a catalyst note older than this is "stale"
MIN_ANALYSTS = 6            # thin coverage → confidence forced LOW
_CONF_FACTOR = {"HIGH": 1.0, "MED": 0.7, "LOW": 0.4}


def conf_factor(conf):
    return _CONF_FACTOR.get(conf, 0.4)


def _c01(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return 0.0 if x < 0 else (1.0 if x > 1.0 else x)


def _parse_date(s):
    s = str(s or "")
    if len(s) >= 10:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except Exception:
            pass
    try:
        return datetime.strptime(s[:7], "%Y-%m")
    except Exception:
        return None


def _age_days(as_of, run_date):
    a, b = _parse_date(as_of), _parse_date(run_date)
    if a is None or b is None:
        return None
    return (b - a).days


def _revision(rec, prev, noise_floor=NOISE_FLOOR):
    """Direction analysts are moving — the LEAD signal. Needs a prior snapshot with
    target_mean / rec_mean. Returns (value 0..1 or None, driver str or None)."""
    if not prev:
        return None, None
    legs, drv = [], None
    tm, ptm = rec.get("target_mean"), prev.get("target_mean")
    if tm and ptm and ptm > 0:
        chg = tm / ptm - 1.0
        if abs(chg) >= noise_floor:
            legs.append(_c01(0.5 + (chg / 0.10) * 0.5))     # +10%→1.0, -10%→0
            drv = ("المحللون يرفعون الأهداف %+.0f%%" if chg > 0 else "المحللون يخفّضون الأهداف %+.0f%%") % (chg * 100)
        else:
            legs.append(0.5)                                # flat → neutral, no phantom revision
    rm, prm = rec.get("rec_mean"), prev.get("rec_mean")
    if rm and prm and prm > 0:
        legs.append(_c01(0.5 + (prm - rm) / 0.6 * 0.5))     # rec_mean falling toward 1 (Strong Buy) is bullish
        if drv is None and abs(prm - rm) >= 0.1:
            drv = "تصنيف المحللين يتحسّن" if rm < prm else "تصنيف المحللين يضعف"
    if not legs:
        return None, None
    return sum(legs) / len(legs), drv


def _bottleneck_strength(rec):
    """Graded chokepoint strength (not the binary owner flag). None = lens didn't run."""
    tags = rec.get("bottlenecks")
    if tags is None:
        return None, None
    if not tags:
        return 0.1, None
    best, drv = 0.1, None
    _status_ar = {"acute": "مرحلة حادة", "building": "مرحلة تتشكّل", "easing": "تخفّ", "speculative": "مبكّرة"}
    for t in tags:
        role, status, prob = t.get("role"), t.get("status"), str(t.get("prob") or "")
        hi = prob == "high"
        s = 0.1
        if role == "chokepoint" and status == "acute" and hi:
            s = 1.0
        elif role == "chokepoint" and status == "building" and hi:
            s = 0.85
        elif role == "chokepoint" and (prob == "med" or status == "easing"):
            s = 0.6
        elif role in ("player", "supplier") and status in ("acute", "building") and hi:
            s = 0.45
        elif status in ("speculative", "early"):
            s = 0.25
        if s > best:
            best = s
            drv = "مالك عنق زجاجة (%s) — %s" % (t.get("chain") or "سلسلة", _status_ar.get(status, status or ""))
    return best, (drv if best >= 0.45 else None)


def _peg_eff(rec):
    """Effective PEG: prefer a sane positive pegRatio, else derive from forward_pe & growth."""
    peg = rec.get("peg")
    if peg and peg > 0:
        return peg
    fpe, g = rec.get("forward_pe"), rec.get("eps_growth_fwd")
    if fpe and fpe > 0 and g and g > 0:
        return fpe / (g * 100.0)
    return None


def _why_catalyst(rec, run_date, fresh_days=WHY_FRESH_DAYS):
    note = rec.get("why_note")
    if not note:
        return None, None, False
    cat = (note.get("catalyst") or "").strip()
    if not cat:
        return None, None, False
    age = _age_days(note.get("as_of"), run_date)
    stale = age is not None and age > fresh_days
    short = cat[:58] + ("…" if len(cat) > 58 else "")
    return (0.5 if stale else 1.0), ("محفّز قريب: " + short), stale


def forward_outlook(rec, cfg, prev_metrics=None):
    """Compute the forward outlook and attach it to rec. Pure, None-safe, no network."""
    rec.setdefault("forward_outlook_score", None)
    rec["forward_drivers"] = []
    if rec.get("is_fund"):                         # funds are a core hold, not a forecastable pick
        rec["forward_outlook_score"] = None
        rec["forward_outlook_confidence"] = None
        return rec

    cfgf = (cfg.get("forward") or {})
    min_an = int(cfgf.get("min_analysts", MIN_ANALYSTS))
    noise_floor = float(cfgf.get("noise_floor", NOISE_FLOOR))
    fresh_days = int(cfgf.get("why_note_fresh_days", WHY_FRESH_DAYS))
    run_date = rec.get("last_updated") or datetime.now().strftime("%Y-%m-%d")

    parts, drivers = [], []     # parts: (weight, value 0..1); drivers: (kind, text)
    W = WEIGHTS

    rev_v, rev_drv = _revision(rec, prev_metrics, noise_floor)
    has_revision = rev_v is not None
    if has_revision:
        parts.append((W["revision"], rev_v))
        if rev_drv:
            drivers.append(("rev", rev_drv))

    g = rec.get("eps_growth_fwd")
    has_eps = g is not None
    if has_eps:
        parts.append((W["eps_growth"], _c01(g / 0.25)))
        if g >= 0.15:
            drivers.append(("growth", "نمو أرباح متوقّع %+.0f%%" % (g * 100)))

    bs, bs_drv = _bottleneck_strength(rec)
    if bs is not None:
        parts.append((W["bottleneck"], bs))
        if bs_drv:
            drivers.append(("bottleneck", bs_drv))

    peg = _peg_eff(rec)
    if peg is not None:
        parts.append((W["peg"], _c01((3.0 - peg) / 2.0)))

    up = rec.get("analyst_upside_percent")
    has_up = up is not None
    if has_up:
        parts.append((W["upside"], _c01(up / 0.30)))
        if up >= 0.15:
            drivers.append(("upside", "صعود لمتوسط هدف المحللين %+.0f%%" % (up * 100)))

    fv, price, method = rec.get("fair_value_estimate"), rec.get("price"), (rec.get("fair_value_method") or "")
    if fv and price and price > 0 and method.startswith("تقاطُع"):   # honesty gate: real cross-check only
        parts.append((W["fair_value"], _c01((fv / price - 1.0) / 0.30)))

    wc_v, wc_drv, wc_stale = _why_catalyst(rec, run_date, fresh_days)
    has_cat = wc_v is not None
    if has_cat:
        parts.append((W["why_catalyst"], wc_v))
        if wc_drv:
            drivers.append(("catalyst", wc_drv + (" · ملاحظة قديمة" if wc_stale else "")))

    fpe = rec.get("forward_pe")
    if fpe is not None and fpe > 0:
        parts.append((W["valuation_room"], _c01(1.0 - (fpe - 20.0) / 60.0)))

    due = rec.get("days_until_earnings")
    if due is not None and due >= 0:                 # past dates (due<0) are dropped
        if due <= 14:
            v = 1.0
        elif due <= 45:
            v = 0.4 + (45 - due) / 31.0 * 0.6
        else:
            v = 0.2
        parts.append((W["catalyst_near"], v))
        drivers.append(("near", "نتائج خلال %d يوم — النظرة قد تتغيّر" % int(due)))

    if not parts:
        rec["forward_outlook_score"] = None
        rec["forward_outlook_confidence"] = "LOW"
        rec["forward_drivers"] = ["الاتجاه غير متاح بعد — لا بيانات مستقبلية كافية"]
        return rec

    w_present = sum(p[0] for p in parts)
    raw = sum(p[0] * p[1] for p in parts) / w_present
    coverage = w_present / _WTOTAL
    score10 = round(min(10.0, 10.0 * raw * (0.5 + 0.5 * coverage)), 1)
    rec["forward_outlook_score"] = score10
    rec["_forward_components"] = {"coverage": round(coverage, 2), "n_signals": len(parts), "has_revision": has_revision}

    nana = rec.get("num_analysts") or 0
    fresh = rec.get("data_freshness_status")
    only_narrative = not (has_revision or has_eps or has_up or has_cat)   # only theme/peg/valuation → weak
    # honesty contract: a confirmed DIRECTION (run-over-run revision) is required for any
    # confidence above LOW — first-sight names (no prior snapshot) stay LOW until we have history.
    if not has_revision:
        conf = "LOW"
    elif coverage >= 0.55:
        conf = "HIGH"
    elif coverage >= 0.40:
        conf = "MED"
    else:
        conf = "LOW"
    if nana < min_an or only_narrative:
        conf = "LOW"
    if fresh in ("STALE", "MISSING") and conf == "HIGH":
        conf = "MED"
    rec["forward_outlook_confidence"] = conf

    _order = {"catalyst": 0, "rev": 1, "growth": 2, "bottleneck": 3, "upside": 4, "near": 5}
    drivers.sort(key=lambda d: _order.get(d[0], 9))
    out = [d[1] for d in drivers[:3]]
    if not has_revision:                              # honest first-sight note leads
        out = (["الاتجاه غير متاح بعد — أول رصد للتقديرات"] + out)[:3]
    rec["forward_drivers"] = out
    return rec
