"""
discovery.py — «الصيّاد»: سطح اكتشافٍ حتميّ (deterministic Python، بلا LLM، بلا شبكة) يقرأ
الاتجاه run-over-run الذي تحسبه المنظومة وتهمله — ميل المحللين، سُلّم previous_rankings عبر
الجولات، وتجميع الإشارات لمستوى الثيمة/فئة الأصول — فيرى رأس المال يصحو في سلّةٍ قبل أن
يتصدّر أي اسمٍ الرانك. إضافةٌ تكمّل الرانك/الريجيم/الديسك-نوت، لا بديلٌ عنها: قيمته أنه
مبكّر (EARLY)، دوّار (ROTATION)، وتحت-رادار (UNDER-RADAR).

قرار المالك: «الصيّاد يطلّع الأفضل — لا يفلتر حلال/حرام، أنا أتأكّد قبل التنفيذ.» لذلك:
لا نستبعد على أساس الحلال إطلاقاً؛ نعرض الحالة الشرعية كعلمٍ محايد («تأكّد حلاله») ولا نؤكّد
حلال اسمٍ أبداً. كل صيدٍ مربوطٌ برقمٍ حقيقي ويحمل ضعفه الصريح. الصمت مخرَجٌ صالح.
"""

import json
import os

from config_loader import state_dir

try:
    import themes as _themes
    _PRIORITY = set(t.lower() for t in (getattr(_themes, "PRIORITY_THEMES", []) or []))
    _is_cyclical = getattr(_themes, "is_cyclical", None)
except Exception:                                       # pragma: no cover
    _PRIORITY, _is_cyclical = set(), None

try:
    from desk_note import _FORBIDDEN, _RISK_RANK
except Exception:                                       # pragma: no cover
    _FORBIDDEN = ("اشترِ الآن", "مضمون", "صاروخ", "لا تفوّت")
    _RISK_RANK = {"low": 0, "medium": 1, "high": 2, "extreme": 3}

try:
    from forward import DISCLAIMER_AR as _DISC
except Exception:                                       # pragma: no cover
    _DISC = "قراءة اتجاه من إشاراتنا — ليست توصية؛ القرار لك."

_HALAL_TAG = {"pass": "", "unknown": " تأكّد حلاله بنفسك", "fail": " ⚠ شرعياً غير متوافق بسجلّنا — راجِعه"}


def _params(cfg):
    d = ((cfg or {}).get("discovery", {}) or {})
    return {
        "min_breadth": d.get("min_breadth", 4),
        "waking_up_frac": d.get("waking_up_frac", 0.45),
        "crowd_calm": d.get("crowd_calm", 0.40),
        "rank_climb_min": d.get("rank_climb_min", 120),
        "backslide": d.get("backslide", 60),
        "not_yet_top": d.get("not_yet_top", 60),
        "noise_floor": d.get("noise_floor", 0.03),
        "upside_flip": d.get("upside_flip", 0.15),
        "min_analysts": d.get("min_analysts", 6),
        "max_catches": d.get("max_catches", 4),
        "conv_floor": d.get("conv_floor", 6),
    }


def _state_path(cfg):
    return os.path.join(state_dir(cfg), "discovery_state.json")


def _save_state(cfg, snap):
    try:
        with open(_state_path(cfg), "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"  discovery state save skipped: {e}")


def _theme(r):
    return (r.get("primary_theme") or r.get("sector") or "—")


def _rising(r):
    return any("يرفع" in str(d) for d in (r.get("forward_drivers") or []))


def _downgrading(r):
    return any("يخفّض" in str(d) for d in (r.get("forward_drivers") or []))


def _median(xs):
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    n = len(xs)
    return None if not n else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0)


def _eligible(r, holdings, desk):
    """البوّابة المشتركة — حلال-محايد (لا نستبعد على الحلال؛ المالك يتأكّد)."""
    t = r.get("ticker")
    return (not r.get("is_fund") and r.get("investable", True) and r.get("action") != "Avoid"
            and t not in holdings and t not in desk
            and not r.get("crowded_late") and not r.get("popular_not_cheap"))


def _trend_up(r, deltas, mem):
    t = r.get("ticker")
    e = (mem or {}).get(t) or {}
    return (_rising(r) or e.get("score_trend") == "up" or (deltas or {}).get(t, 0) >= 3)


def _trend_dn(r, deltas, mem):
    t = r.get("ticker")
    e = (mem or {}).get(t) or {}
    return (_downgrading(r) or e.get("score_trend") == "down" or (deltas or {}).get(t, 0) <= -3)


def build_theme_map(records, deltas, mem, holdings, P):
    """يجمّع إشارات الاتجاه لمستوى الثيمة + ثلاث فئات أصول. الأعضاء = كل الأسهم القابلة (حلال-محايد)."""
    elig = [r for r in records if not r.get("is_fund") and r.get("investable", True)
            and r.get("action") != "Avoid"]
    by_theme = {}
    for r in elig:
        keys = set([_theme(r)] + [str(x) for x in (r.get("themes") or [])])
        for k in keys:
            by_theme.setdefault(k, []).append(r)
    out = {}
    for th, members in by_theme.items():
        n = len(members)
        if n < P["min_breadth"]:
            continue
        up = sum(1 for r in members if _trend_up(r, deltas, mem))
        dn = sum(1 for r in members if _trend_dn(r, deltas, mem))
        crowd = sum(1 for r in members if r.get("crowded_late") or r.get("popular_not_cheap"))
        crowd_share = crowd / n
        med_out = _median([r.get("forward_outlook_score") for r in members
                           if r.get("forward_outlook_confidence") in ("HIGH", "MED")])
        held = sum(1 for r in members if r.get("ticker") in holdings)
        net = (up - dn) / n
        if up / n >= P["waking_up_frac"] and up >= dn + 2 and crowd_share < P["crowd_calm"] and up >= 2 \
                and (med_out is None or med_out >= 6):
            state = "WAKING"
        elif crowd_share >= 0.55:
            state = "CROWDED"
        elif dn / n >= 0.40 and dn >= 3:
            state = "COOLING"
        else:
            state = "NEUTRAL"
        out[th] = {"n": n, "up": up, "dn": dn, "net": net, "crowd_share": crowd_share,
                   "med_out": med_out, "held": held, "state": state, "members": members,
                   "strength": ((up - dn) / n) * (1 - crowd_share)}
    return out


def _asset_class(r):
    if _is_cyclical and _is_cyclical(r):
        return "CYCLICAL"
    if r.get("cyclical"):
        return "CYCLICAL"
    blob = set([str(r.get("primary_theme") or "").lower()] + [str(x).lower() for x in (r.get("themes") or [])])
    if blob & _PRIORITY:
        return "SECULAR"
    return "DEFENSIVE"


def _rotation_line(records, deltas, mem, holdings, P):
    """سطر فئة الأصول: وين يميل صافي ميل المحللين (دوريّات/معادن مقابل نمو سكوني مقابل دفاعي)."""
    buckets = {"CYCLICAL": [], "SECULAR": [], "DEFENSIVE": []}
    for r in records:
        if r.get("is_fund") or not r.get("investable", True) or r.get("action") == "Avoid":
            continue
        buckets[_asset_class(r)].append(r)
    agg = {}
    for k, rs in buckets.items():
        n = len(rs) or 1
        up = sum(1 for r in rs if _trend_up(r, deltas, mem))
        dn = sum(1 for r in rs if _trend_dn(r, deltas, mem))
        agg[k] = {"n": len(rs), "net": (up - dn) / n}
    if not any(v["n"] for v in agg.values()):
        return None
    hot = max(agg, key=lambda k: agg[k]["net"])
    if agg[hot]["net"] < 0.20:
        return None
    ar = {"CYCLICAL": "الدوريّات/المعادن", "SECULAR": "النمو التقني السكوني", "DEFENSIVE": "الدفاعي"}
    tail = " (تحوّط/دورة سعر — حجم صغير)" if hot == "CYCLICAL" else ""
    return ("ميل رأس المال هالتشغيل نحو %s (صافي ميل المحللين +%d%%)%s — قراءة اتجاه لا توصية."
            % (ar[hot], round(agg[hot]["net"] * 100), tail))


# ───────────────────────── detectors ─────────────────────────

def _det_theme_waking(tmap, deltas, mem, holdings, desk, P):
    out = []
    waking = sorted([(th, d) for th, d in tmap.items() if d["state"] == "WAKING"],
                    key=lambda x: x[1]["strength"], reverse=True)[:2]
    for th, d in waking:
        riders = [r for r in d["members"]
                  if _eligible(r, holdings, desk)
                  and r.get("action") in ("Candidate", "Returning", "Emerging Opportunity", "Research More")
                  and isinstance(r.get("conviction_score"), (int, float)) and r["conviction_score"] >= P["conv_floor"]
                  and ((deltas or {}).get(r.get("ticker"), 0) >= 3 or _rising(r))]
        riders.sort(key=lambda r: ((r.get("forward_outlook_score") or 0), (deltas or {}).get(r.get("ticker"), 0)),
                    reverse=True)
        if not riders:
            continue
        r = riders[0]
        wk = (r.get("weaknesses") or ["—"])[0]
        thesis = ("ثيمة «%s» تصحى بهدوء: المحللون يرفعون التقديرات في %d من %d اسماً (%d%%) والازدحام لسه %d%% فقط "
                  "— إشارة دوران مبكّرة قبل ما تكتظّ، مو توصية. أبرز راكبٍ مبكّر: %s (الترتيب +%d، قناعة %d/10، غير مزدحم). "
                  "نقطة ضعفه: %s.%s"
                  % (th, d["up"], d["n"], round(d["up"] / d["n"] * 100), round(d["crowd_share"] * 100),
                     r.get("ticker"), int((deltas or {}).get(r.get("ticker"), 0)), int(r["conviction_score"]),
                     wk, _HALAL_TAG.get(r.get("halal_status"), "")))
        out.append({"ticker": r.get("ticker"), "detector": "theme_waking", "theme": th,
                    "cyclical": _asset_class(r) == "CYCLICAL", "halal": r.get("halal_status"),
                    "score": d["strength"], "weight": 0.95, "thesis": thesis})
    return out


def _det_rank_climber(records, deltas, mem, holdings, desk, P):
    out = []
    for r in records:
        if not _eligible(r, holdings, desk):
            continue
        conv = r.get("conviction_score")
        if not (isinstance(conv, (int, float)) and conv >= P["conv_floor"]):
            continue
        if r.get("lifecycle_status") in ("Falling Conviction", "Fallen Angel") or _downgrading(r):
            continue
        if (deltas or {}).get(r.get("ticker"), 0) >= 5 and r.get("action") == "Candidate":
            continue                                    # this is the desk-note's quiet-climber
        e = (mem or {}).get(r.get("ticker")) or {}
        pr = e.get("previous_rankings") or []
        seen, ladder = set(), []
        for item in pr:                                 # dedup by date, keep rank
            try:
                dt, rk = item[0], int(item[1])
            except Exception:
                continue
            if dt in seen:
                continue
            seen.add(dt)
            ladder.append(rk)
        if len(ladder) < 3:
            continue
        span = ladder[0] - ladder[-1]                   # >0 = toward #1
        downs = sum(1 for a, b in zip(ladder, ladder[1:]) if b > a)
        worst_back = max([b - a for a, b in zip(ladder, ladder[1:])] + [0])
        cur_rank = ladder[-1]
        cur_s, disc_s = e.get("current_score"), e.get("discovery_score")
        if not (span >= P["rank_climb_min"] and downs <= 1 and worst_back <= P["backslide"]
                and cur_rank > P["not_yet_top"]
                and isinstance(cur_s, (int, float)) and isinstance(disc_s, (int, float)) and cur_s >= disc_s):
            continue
        wk = (r.get("weaknesses") or ["—"])[0]
        thesis = ("اسم يتسلّق بهدوء عبر %d جولات: %s تحسّن ترتيبه %d مركز (من #%d إلى #%d)، قناعته %d/10، وأعلى من نقطة "
                  "اكتشافه — لسه خارج الصدارة وغير مزدحم. مرشّح بحثٍ مبكّر قبل ما يكتظّ. نقطة ضعفه: %s.%s"
                  % (len(ladder), r.get("ticker"), span, ladder[0], cur_rank, int(conv), wk,
                     _HALAL_TAG.get(r.get("halal_status"), "")))
        out.append({"ticker": r.get("ticker"), "detector": "rank_climber", "theme": _theme(r),
                    "cyclical": _asset_class(r) == "CYCLICAL", "halal": r.get("halal_status"),
                    "score": span + (conv - 6) * 10 + (cur_s - disc_s), "weight": 0.92, "thesis": thesis})
    return out


def _det_fallen_but_funded(records, deltas, mem, holdings, desk, P):
    out = []
    for r in records:
        if not _eligible(r, holdings, desk):
            continue
        below = r.get("pct_below_52w_high")
        fund = r.get("fundamental_score")
        conv = r.get("conviction_score")
        up = r.get("analyst_upside_percent")
        if not (isinstance(below, (int, float)) and below >= 0.30
                and isinstance(fund, (int, float)) and fund >= 55
                and isinstance(conv, (int, float)) and conv >= 6
                and isinstance(up, (int, float)) and up >= 0.20):
            continue
        de = r.get("debt_to_equity")
        e = (mem or {}).get(r.get("ticker")) or {}
        if (e.get("score_trend") == "down" or _downgrading(r)
                or r.get("lifecycle_status") == "Falling Conviction"
                or (isinstance(de, (int, float)) and de > 2.5)):
            continue                                    # value-trap guard
        wk = (r.get("weaknesses") or ["—"])[0]
        thesis = ("صيدٌ معاكس تحت الرادار: %s نازل %d%% عن قمّته لكن أساسه متين (جودة %d/100، قناعة %d/10) والمحللون "
                  "ما تخلّوا عنه — هدفهم أعلى من السعر بـ%d%%. رخيصٌ من الإهمال لا من الكسر. للبحث والتجميع المتدرّج، "
                  "ليست توصية. نقطة ضعفه: %s.%s"
                  % (r.get("ticker"), round(below * 100), int(fund), int(conv), round(up * 100), wk,
                     _HALAL_TAG.get(r.get("halal_status"), "")))
        out.append({"ticker": r.get("ticker"), "detector": "fallen_but_funded", "theme": _theme(r),
                    "cyclical": _asset_class(r) == "CYCLICAL", "halal": r.get("halal_status"),
                    "score": 0.5 * below + 0.3 * ((fund - 55) / 45.0) + 0.2 * min(up, 1.0),
                    "weight": 0.85, "thesis": thesis})
    return out


def _det_revision_inflection(records, deltas, mem, holdings, desk, P):
    out = []
    for r in records:
        if not _eligible(r, holdings, desk):
            continue
        e = (mem or {}).get(r.get("ticker")) or {}
        cur, prev = e.get("metrics") or {}, e.get("prev_metrics")
        if not prev:                                    # no fabricated trend
            continue
        below = r.get("pct_below_52w_high")
        fo = r.get("forward_outlook_score")
        conv = r.get("conviction_score")
        fund = r.get("fundamental_score")
        na = r.get("num_analysts") or 0
        up_now, up_prev = cur.get("upside"), prev.get("upside")
        tm, tmp = cur.get("target_mean"), prev.get("target_mean")
        rev_up = (isinstance(tm, (int, float)) and isinstance(tmp, (int, float)) and tmp > 0
                  and tm / tmp - 1 >= P["noise_floor"])
        if not rev_up:                                  # two-leg confirmation: needs target_mean leg
            continue
        if not (isinstance(up_now, (int, float)) and up_now >= P["upside_flip"]
                and isinstance(up_prev, (int, float)) and up_prev <= 0.05):   # real prior reading — no fabricated «من +0%»
            continue
        if not (isinstance(below, (int, float)) and 0.12 <= below <= 0.40
                and isinstance(fo, (int, float)) and fo >= 6
                and isinstance(conv, (int, float)) and conv >= 5.5
                and isinstance(fund, (int, float)) and fund >= 45
                and na >= P["min_analysts"] and not _downgrading(r)):
            continue
        wk = (r.get("weaknesses") or ["—"])[0]
        thesis = ("انعطاف مبكّر على %s: الصعود المتوقّع تحرّك إلى %+d%% من %+d%% بين الجولتين (المحللون يرفعون الأهداف، "
                  "%d محلل) وهو لسه نازل %d%% عن قمّته وغير مزدحم — التقدير يسبق السعر. قراءة اتجاه لا توصية. نقطة ضعفه: %s.%s"
                  % (r.get("ticker"), round(up_now * 100), round((up_prev or 0) * 100), int(na),
                     round(below * 100), wk, _HALAL_TAG.get(r.get("halal_status"), "")))
        conf = "MED" if (na >= P["min_analysts"] and r.get("data_freshness_status") == "FRESH") else "LOW"
        out.append({"ticker": r.get("ticker"), "detector": "revision_inflection", "theme": _theme(r),
                    "cyclical": _asset_class(r) == "CYCLICAL", "halal": r.get("halal_status"),
                    "score": (up_now - (up_prev or 0)) * (1 + below), "weight": 1.0,
                    "conf": conf, "thesis": thesis})
    return out


def _det_theme_cooling(tmap, holdings):
    """درء الدوران — يفلت حتى في الجوّ الدفاعي. يتكلّم فقط عن ثيمة تملك منها ≥2."""
    out = []
    for th, d in tmap.items():
        if d["state"] == "COOLING" and d["held"] >= 2:
            out.append("تنبيه دوران (لا نصيحة بيع): ثيمة «%s» تبرد — المحللون يخفّضون التقديرات في %d من %d اسماً (%d%%)، "
                       "وتملك منها %d. القصة الجماعية تضعف، تمهّل قبل تزيد في هالسلّة — القرار لك."
                       % (th, d["dn"], d["n"], round(d["dn"] / d["n"] * 100), d["held"]))
    return out[:1]


def discover(records, meta, holdings, deltas, mem, cfg=None, desk_tickers=None, persist=True):
    """يرجّع {'map':[...], 'catches':[...], 'lines':[...], 'disclaimer':...}. لا يرمي أبداً."""
    cfg = cfg or {}
    P = _params(cfg)
    holdings = set(holdings or [])
    desk = set(desk_tickers or [])
    rg = (meta or {}).get("regime") or {}
    mode = rg.get("recommended_mode")
    risk_rank = _RISK_RANK.get(str((rg.get("metrics") or {}).get("market_risk") or "").lower(), 0)
    defensive = (mode == "conservative") or (risk_rank >= 2)

    tmap = build_theme_map(records, deltas, mem, holdings, P)

    # ── map lines (الخريطة منفصلة عن سقف الصيدات) ──
    map_lines = []
    waking = sorted([(th, d) for th, d in tmap.items() if d["state"] == "WAKING"],
                    key=lambda x: x[1]["strength"], reverse=True)
    if waking:
        th, d = waking[0]
        map_lines.append("أقوى ثيمة تصحى: «%s» — تقديرات صاعدة في %d من %d (%d%%)، ازدحام %d%% فقط. وين يصحو رأس المال."
                         % (th, d["up"], d["n"], round(d["up"] / d["n"] * 100), round(d["crowd_share"] * 100)))
    rot = _rotation_line(records, deltas, mem, holdings, P)
    if rot:
        map_lines.append(rot)
    map_lines += _det_theme_cooling(tmap, holdings)      # guardrail — escapes defensive suppression

    # ── catches ──
    catches = []
    if not defensive:
        cand = (_det_theme_waking(tmap, deltas, mem, holdings, desk, P)
                + _det_revision_inflection(records, deltas, mem, holdings, desk, P)
                + _det_rank_climber(records, deltas, mem, holdings, desk, P)
                + _det_fallen_but_funded(records, deltas, mem, holdings, desk, P))
        # normalize strength within each detector, then final = weight * norm * conf_factor
        by_det = {}
        for c in cand:
            by_det.setdefault(c["detector"], []).append(c)
        conf_factor = {"HIGH": 1.0, "MED": 0.7, "LOW": 0.4}
        for det, lst in by_det.items():
            mx = max((c["score"] for c in lst), default=1.0) or 1.0
            mn = min((c["score"] for c in lst), default=0.0)
            rng = (mx - mn) or 1.0
            for c in lst:
                norm = 1.0 if mx == mn else (c["score"] - mn) / rng   # lone catch = full strength, not 0
                c["final"] = c["weight"] * norm * conf_factor.get(c.get("conf", "HIGH"), 1.0)
        cand.sort(key=lambda c: (c["final"], c["ticker"]), reverse=True)
        # dedup: one ticker, ≤1 per theme, ≤1 cyclical overall, hard cap
        seen_t, seen_theme, cyc_used = set(), set(), False
        for c in cand:
            t = c["ticker"]
            if t in seen_t or t in desk or t in holdings:
                continue
            if c["theme"] in seen_theme:
                continue
            if c["cyclical"] and cyc_used:
                continue
            if any(b in c["thesis"] for b in _FORBIDDEN):
                continue
            catches.append(c)
            seen_t.add(t)
            seen_theme.add(c["theme"])
            if c["cyclical"]:
                cyc_used = True
            if len(catches) >= P["max_catches"]:
                break

    # ── assemble display lines ──
    lines = list(map_lines)
    if catches:
        lines += [c["thesis"] for c in catches]
    elif not map_lines:
        lines.append("ما طلع صيدٌ يستاهل الإفراد هالتشغيل — السلالم ثابتة، وخريطة الدوران تتكوّن من الجاي.")

    if persist:
        _save_state(cfg, {"catches": [c["ticker"] for c in catches], "n_themes": len(tmap)})

    return {"map": map_lines,
            "catches": [{"ticker": c["ticker"], "detector": c["detector"], "thesis_ar": c["thesis"],
                         "halal": c.get("halal")} for c in catches],
            "lines": lines, "disclaimer": _DISC}
