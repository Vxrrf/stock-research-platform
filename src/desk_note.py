"""
desk_note.py — «صوت العقل المحترف»: مذكّرة مكتبٍ يكتبها البرنامج لحاله كل تشغيل، بلا أن
يُسأل، يقرأ اللوح كاملاً وعبر الزمن ويقول بصوتٍ أول-شخص هادئ ما تغيّر أو ما يهمّ فقط.

ليست شات بوت، ولا متنبّئ، ولا أمر شراء/بيع، ولا محرّك «دوبامين». كل سطر مربوط بحقلٍ ورقمٍ
حقيقي على السجلّات/الميتا/الدلتا/تقييم الحيازات — وإن غاب الرقم يسقط السطر (لا كلام إنشائي).
الصمت مخرَجٌ صالح: اليوم الهادئ سطرٌ واحد و«ولا حركة». القرار النهائي للمستخدم، والحلال يتأكّده بنفسه.

deterministic Python — بلا شبكة، بلا LLM. يعمل في السحابة والماك مقفل.
"""

import json
import os
from collections import Counter

from config_loader import state_dir
from schema import now_local

try:
    from regime import DISCLAIMER_AR, _RISK_RANK
except Exception:                                       # pragma: no cover
    DISCLAIMER_AR = "قراءة للحظة من إشاراتنا — ليست تنبؤاً؛ تُرشّح وضعاً والقرار لك."
    _RISK_RANK = {"low": 0, "medium": 1, "high": 2, "extreme": 3}

_RISK_AR = {"Low": "منخفضة", "Medium": "متوسطة", "High": "مرتفعة", "Extreme": "قصوى"}
_MODE_AR = {"conservative": "محافظ", "balanced": "متوازن", "aggressive": "هجومي"}

# عبارات ممنوعة (تهويل/أوامر/يقين) — أيّ سطر يحويها يُسقَط. مخصّصة عمداً (لا «بيع» المجرّدة).
_FORBIDDEN = ("اشترِ الآن", "اشتر الآن", "بِع الآن", "بيع الآن", "فرصة العمر", "مضمون",
              "أكيد يصعد", "أكيد يطلع", "لا تفوّت", "لا يفوّتك", "لا يفوتك",
              "راح ينفجر", "راح يطلع", "راح يضرب", "صاروخ")


def _params(cfg):
    dc = ((cfg or {}).get("desk_note", {}) or {})
    return {
        "crowd_move": dc.get("crowd_move", 0.10),
        "pe_move": dc.get("pe_move", 2),
        "concentration": dc.get("concentration", 0.40),
        "drawdown_flag": dc.get("drawdown_flag", -0.25),
        "max_lines": dc.get("max_lines", 6),
        "silver": [str(s).upper() for s in (dc.get("silver_tickers") or ["HL"])],
        "downgrade_cluster": dc.get("downgrade_cluster", 3),
    }


def _state_path(cfg):
    return os.path.join(state_dir(cfg), "desk_state.json")


def _load_state(cfg):
    try:
        with open(_state_path(cfg), encoding="utf-8") as f:
            s = json.load(f)
            return s if isinstance(s, dict) else None
    except Exception:
        return None


def _save_state(cfg, snap):
    try:
        with open(_state_path(cfg), "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"  desk_note state save skipped: {e}")


def _theme(rec):
    return rec.get("primary_theme") or rec.get("sector") or "—"


def _downgrading(rec):
    return any("يخفّض" in str(d) for d in (rec.get("forward_drivers") or []))


def _held_rows(holdings_eval):
    """صفوف الحيازات القابلة للتقييم (نستبعد الصناديق و«لا بيانات»)."""
    out = []
    for h in (holdings_eval or []):
        v = str(h.get("verdict") or "")
        if "صندوق" in v or "لا بيانات" in v:
            continue
        out.append(h)
    return out


def build_desk_note(records, meta, holdings_eval, deltas, mem, cfg=None, persist=True):
    """يرجّع {'lines': [...], 'disclaimer': ...} — مرتّبة ومحدودة ومفلترة. لا يرمي أبداً.
    persist=False (الماك من الكاش) لا يكتب لقطة اللوح — السحابة وحدها تملك ذاكرة الاتجاه."""
    cfg = cfg or {}
    P = _params(cfg)
    rg = (meta or {}).get("regime") or {}
    m = rg.get("metrics") or {}
    by_t = {r.get("ticker"): r for r in records if r.get("ticker")}
    deltas = deltas or {}
    held = _held_rows(holdings_eval)
    held_syms = {h.get("ticker") for h in held}

    mode = rg.get("recommended_mode") or "balanced"
    conf = rg.get("confidence")
    risk_now = m.get("market_risk")
    risk_rank_now = _RISK_RANK.get(str(risk_now or "").lower(), 0)
    crowd_now = m.get("crowd_pct")
    pe_now = m.get("med_fwd_pe")
    cand_now = m.get("candidate_pct")
    defensive_tape = (mode == "conservative") or (risk_rank_now >= 2)

    prev = _load_state(cfg)

    # ── أعلى ثيمة في حيازاتك (بالعدّ، لا الوزن — لا نختلق نسبة وزنٍ ما نملكها) ──
    held_recs = [by_t[s] for s in held_syms if s in by_t]
    theme_clause = ""
    top_theme = None
    if held_recs:
        tc = Counter(_theme(r) for r in held_recs)
        top_theme, top_n = tc.most_common(1)[0]
        share = top_n / max(1, len(held_recs))
        # «أسهمك» لا «حيازاتك» — نعدّ الأسهم فقط (الصناديق الأساسية كـHLAL مستبعَدة من عدّ الثيمة)
        theme_clause = " وأغلب أسهمك في «%s» (%d من %d)" % (top_theme, top_n, len(held_recs))

    lines = []

    # ── 1) الافتتاحية — سطرٌ واحد دائماً ──
    if not prev:
        lead = ("أول تشغيل عندي — ما عندي مقارنة بالسابق بعد. القراءة الحالية: «%s» ومخاطر %s%s. "
                "اتجاه التصاعد/التراجع بيتوفّر من التشغيل الجاي."
                % (rg.get("regime", "—"), _RISK_AR.get(str(risk_now), str(risk_now or "—")), theme_clause))
    else:
        prev_mode = prev.get("regime_mode")
        prev_riskrank = _RISK_RANK.get(str(prev.get("market_risk") or "").lower(), 0)
        prev_crowd = prev.get("crowd_pct")
        prev_pe = prev.get("med_fwd_pe")
        moved = (prev_mode != mode
                 or abs(risk_rank_now - prev_riskrank) >= 1
                 or (isinstance(crowd_now, (int, float)) and isinstance(prev_crowd, (int, float))
                     and abs(crowd_now - prev_crowd) >= P["crowd_move"])
                 or (isinstance(pe_now, (int, float)) and isinstance(prev_pe, (int, float))
                     and abs(pe_now - prev_pe) >= P["pe_move"]))
        if moved:
            rdir = ("ترتفع" if risk_rank_now > prev_riskrank
                    else ("تهدأ" if risk_rank_now < prev_riskrank else "ثابتة"))
            lead = ("المشهد يتحرّك هالتشغيل: كنت أقرأه «%s» وصار «%s» — مخاطر السوق %s من %s إلى %s%s. "
                    "مو ذعر، ترتيب." % (prev.get("regime_label", prev_mode or "—"), rg.get("regime", "—"),
                                        rdir, _RISK_AR.get(str(prev.get("market_risk")), str(prev.get("market_risk") or "—")),
                                        _RISK_AR.get(str(risk_now), str(risk_now or "—")), theme_clause))
        else:
            lead = ("اللوح ثابت من آخر تشغيل: «%s» ومخاطر %s%s. ما تغيّر شي جوهري يستدعي حركة."
                    % (rg.get("regime", "—"), _RISK_AR.get(str(risk_now), str(risk_now or "—")), theme_clause))
    lines.append(lead)

    cand = []   # (tier, strength, text, theme, ticker)

    # ── 2) اللي يقلقني — تدهور هذا التشغيل على كتابك ──
    for h in held:
        t = h.get("ticker")
        v = str(h.get("verdict") or "")
        conv = h.get("conviction")
        d = deltas.get(t, 0)
        if "🔴" in v and isinstance(d, (int, float)) and d < 0 and isinstance(conv, (int, float)):
            cand.append((0, abs(d), "اللي يقلقني في كتابك: %s — القناعة %d/10 وخسر %d نقطة من آخر فحص. "
                         "مو نصيحة بيع، بس الأطروحة تضعف — راجع ليش تملكه قبل تزيد فيه."
                         % (t, conv, abs(int(d))), _theme(by_t.get(t, {})), t))

    for h in held:
        t = h.get("ticker")
        rec = by_t.get(t)
        if rec and _downgrading(rec):
            cand.append((0, 5, "تنبيه على %s اللي تملكه: المحللون يخفّضون أهدافهم من آخر فحص — "
                         "أصدق إشارة مبكّرة إن القصة تبرد. لسه مو كارثة، بس راقبها." % t,
                         _theme(rec), t))

    # regime step-up (تشدّد الإطار)
    if prev and prev.get("regime_mode") and mode == "conservative" and prev["regime_mode"] != "conservative":
        cand.append((0, 6, "الإطار العام تشدّد: النظام انتقل من «%s» لـ«محافظ» — هالتشغيل احمِ رأس المال أكثر، "
                     "طارد أقل، وخلّ الكاش ذخيرة. مو خوف، ترتيب." % _MODE_AR.get(prev["regime_mode"], prev["regime_mode"]),
                     None, None))

    # downgrade cluster (عرض السوق)
    dn = [r for r in records if _downgrading(r) and not r.get("is_fund")]
    if len(dn) >= P["downgrade_cluster"]:
        tcl = Counter(_theme(r) for r in dn).most_common(1)[0][0]
        cand.append((1, len(dn), "إشارة هادئة تستاهل الانتباه: %d أسماء هالتشغيل المحللون يخفّضون أهدافها، "
                     "أغلبها في «%s». واحد ضوضاء، عدّة بنفس الثيمة = أتمهّل قبل أزيد فيها." % (len(dn), tcl),
                     tcl, None))

    # concentration (بالعدّ)
    if held_recs and top_theme:
        same = [r for r in held_recs if _theme(r) == top_theme]
        share = len(same) / max(1, len(held_recs))
        cut = [r for r in same if _downgrading(r) or deltas.get(r.get("ticker"), 0) < 0]
        if share >= P["concentration"] and len(cut) >= 2:
            cand.append((0, int(share * 100), "اللي يقلقني مو سهم — تركيزك: أغلب حيازاتك في «%s»، واثنين منها "
                         "(%s) بدأ المحللون/الترتيب يميل ضدّهم. القصة قوية بس بيضك في سلّة وحدة — "
                         "أي إضافة جديدة أفضّلها خارج هالثيمة." % (top_theme, "، ".join(c.get("ticker") for c in cut[:2])),
                         top_theme, None))

    # ── 3) الدرء النفسي — لا تبيع الجوهرة ──
    for h in held:
        t = h.get("ticker")
        rec = by_t.get(t) or {}
        pnl = h.get("pnl")
        conv = h.get("conviction")
        if (isinstance(pnl, (int, float)) and pnl <= P["drawdown_flag"]
                and isinstance(conv, (int, float)) and conv >= 6
                and rec.get("score_trend") != "down" and not h.get("pnl_suspect")):
            cand.append((0, int(abs(pnl) * 100),
                         "أرى %s عندك نازل %d%% من شرائك، وأعرف إنه يضغط نفسياً — بس الأساس ما تغيّر: "
                         "القناعة لسه %d/10 والتقديرات ما انخفضت. الستوب المحسوب لك في بطاقة السهم — مو وصلناه "
                         "بالبيع الغريزي. والتركيب يكافئ الصبر: أغلب المكسب يجي بالسنين الأخيرة، وهبوطٌ مؤقّت "
                         "لاسمٍ أساسه سليم جزءٌ من الرحلة لا نهايتها. موضع تماسُك مو هروب، والقرار لك."
                         % (t, round(abs(pnl) * 100), conv), _theme(rec), t))

    # ── الأساس مقابل السعر: في الهبوط، القوي النازل = فرصة تجميع؛ الضعيف النازل = ابتعد ──
    sw_strong, sw_weak = [], []
    for r in records:
        if r.get("is_fund"):
            continue
        below = r.get("pct_below_52w_high")
        if not (isinstance(below, (int, float)) and below >= 0.20):   # فقط الأسماء النازلة فعلاً
            continue
        lc, fund, conv = r.get("lifecycle_status"), r.get("fundamental_score"), r.get("conviction_score")
        if (lc == "Fallen Angel" and isinstance(fund, (int, float)) and fund >= 50
                and isinstance(conv, (int, float)) and conv >= 6
                and r.get("halal_status") != "fail" and not _downgrading(r)):
            sw_strong.append(r)
        elif lc == "Falling Conviction" or (isinstance(fund, (int, float)) and fund < 40) or _downgrading(r):
            sw_weak.append(r)
    sw_strong.sort(key=lambda r: (r.get("conviction_score") or 0), reverse=True)
    sw_weak.sort(key=lambda r: (r.get("fundamental_score") if isinstance(r.get("fundamental_score"), (int, float)) else 99))
    if sw_strong:
        s = sw_strong[0]
        sb = round((s.get("pct_below_52w_high") or 0) * 100)
        owned = s.get("ticker") in held_syms
        opp = "تشبّث به وزِد بثقة" if owned else "فرصة بحثٍ وتجميع — وتأكّد حلاله بنفسك"
        wk = (s.get("weaknesses") or ["—"])[0]
        fundv = ("%d" % round(s["fundamental_score"])) if isinstance(s.get("fundamental_score"), (int, float)) else "—"
        wclause = ""
        if sw_weak:
            wclause = " بالمقابل %s نازلٌ وأساسه يضعف — أتجنّبه، نزوله له سبب." % sw_weak[0].get("ticker")
        cand.append((0, sb, "افرز القوي من الضعيف في الهبوط: %s نازل %d%% لكن أساسه متين (جودة %s، قناعة %d/10) — %s. "
                     "نقطة ضعفه: %s.%s" % (s.get("ticker"), sb, fundv, int(s.get("conviction_score") or 0), opp, wk, wclause),
                     _theme(s), s.get("ticker")))

    # ── 4) الميل (لو القرار قراري) ──
    if mode == "conservative" and conf != "LOW":
        cl = ("الازدحام %d%% ووسيط P/E الآجل %d" % (round((crowd_now or 0) * 100), round(pe_now))
              if isinstance(pe_now, (int, float)) else "الزحام والتقييم مرتفعان")
        cand.append((0, 50, "لو القرار قراري هالتشغيل، أميل للدفاع: %s — مو وقت المطاردة، "
                     "وقت أنتقي الجودة الرخيصة وأخلّي الكاش جاهز. القرار يبقى لك." % cl, None, None))
    elif mode == "aggressive":
        cl = ("فرص الجودة الرخيصة اتّسعت لـ%d%% من الأسماء" % round((cand_now or 0) * 100)
              if isinstance(cand_now, (int, float)) else "فرص الجودة اتّسعت")
        cand.append((1, 40, "أميل شوي للهجوم: %s والمخاطر والزحام معقولين — الجوّ يسمح بصيدٍ مدروس "
                     "بحجمٍ صغير ومتدرّج (DCA)، مو دفعة وحدة. الفرصة ما تستاهل تكسر انضباطك." % cl, None, None))

    # ── 5) فكرة تحت الرادار (≤1، وتُمنَع في الجوّ الدفاعي/المرتفع المخاطر) ──
    ideas = []
    if not defensive_tape:
        # quiet climber: مرشّح غير مملوك، ترتيبه صاعد، غير مزدحم، قناعة كافية
        climbers = [r for r in records if not r.get("is_fund")
                    and r.get("ticker") not in held_syms
                    and r.get("action") == "Candidate"
                    and r.get("halal_status") != "fail"            # لا نطرح اسماً محرّماً كفكرة أبداً
                    and not r.get("crowded_late") and not r.get("popular_not_cheap")
                    and isinstance(r.get("conviction_score"), (int, float)) and r["conviction_score"] >= 6
                    and deltas.get(r.get("ticker"), 0) >= 5]
        climbers.sort(key=lambda r: deltas.get(r.get("ticker"), 0), reverse=True)
        if climbers:
            r = climbers[0]
            wk = (r.get("weaknesses") or ["—"])[0]
            ideas.append((1, deltas.get(r.get("ticker"), 0),
                          "اسم يصعد بهدوء ما يكون على رادارك: %s — ترتيبه طالع (+%d)، قناعة %d/10، ومو مزدحم. "
                          "نقطة ضعفه الصريحة: %s. مرشّح للبحث فقط قبل ما يكتظ — وتأكّد حلاله بنفسك."
                          % (r.get("ticker"), int(deltas.get(r.get("ticker"), 0)), int(r["conviction_score"]), wk),
                          _theme(r), r.get("ticker")))
        # silver rotation: مزدوج البوّابة (الذهب يشتغل + اسم فضة مؤهّل فعلاً)
        gold_working = any((by_t.get(s, {}).get("score_trend") == "up"
                            or (by_t.get(s, {}).get("forward_outlook_score") or 0) >= 7)
                           for s in held_syms if "gold" in str(by_t.get(s, {}).get("primary_theme") or "").lower()
                           or "ذهب" in str(by_t.get(s, {}).get("primary_theme") or ""))
        silver = [by_t[s] for s in P["silver"] if s in by_t
                  and by_t[s].get("investable", True)
                  and by_t[s].get("halal_status") != "fail"        # لا نطرح فضّة محرّمة كفكرة
                  and isinstance(by_t[s].get("conviction_score"), (int, float))
                  and by_t[s]["conviction_score"] >= 5]
        if gold_working and silver:
            r = silver[0]
            ideas.append((1, 3, "فكرة دوران أصول تحت الرادار: تحوّطك ذهب وهو يشتغل — والفضة تتحرّك معاه بزخمٍ أعلى وتأخّر. "
                          "%s طلع في الفحص بقناعة %d/10. الفضة أعنف صعوداً وهبوطاً، فحجمٌ صغير لو فتحتها — تحوّط لا نمو، "
                          "وتأكّد حلالها بنفسك. مو توصية شراء." % (r.get("ticker"), int(r["conviction_score"])),
                          "silver", r.get("ticker")))
    if ideas:
        ideas.sort(key=lambda x: x[1], reverse=True)
        cand.append((1, ideas[0][1] - 0.5, ideas[0][2], ideas[0][3], ideas[0][4]))   # واحدة فقط، وزنها أقل قليلاً

    # ── 6) اللي أراقبه الجاي — أقرب محفّز ──
    soon = []
    for h in held:
        du = h.get("days_until_earnings")
        if isinstance(du, (int, float)) and 0 <= du <= 7:
            soon.append((du, h.get("ticker"), True))
    if not soon:
        for r in records:
            du = r.get("days_until_earnings")
            if (isinstance(du, (int, float)) and 0 <= du <= 14
                    and r.get("action") == "Candidate" and r.get("ticker") not in held_syms):
                soon.append((du, r.get("ticker"), False))
    if soon:
        soon.sort(key=lambda x: x[0])
        du, t, owned = soon[0]
        cand.append((2, 1, "اللي أراقبه الأيام الجاية: %s يعلن نتائجه خلال %d يوم — النظرة قد تتغيّر بعدها. "
                     "لا تبني قرار كبير قبلها؛ خلّ التقرير يتكلّم الأول." % (t, int(du)), None, t))

    # ── التجميع: ترتيب + دمج الثيمة/الرمز + سقف + منع الإيمان الفارغ ──
    cand.sort(key=lambda x: (x[0], -x[1]))
    seen_themes, seen_tickers, picked, idea_used = set(), set(), [], False
    for tier, _st, text, theme, ticker in cand:
        is_idea = (theme == "silver") or text.startswith("اسم يصعد")
        if is_idea and (idea_used or defensive_tape):
            continue
        if ticker and ticker in seen_tickers:
            continue
        if theme and theme not in (None, "silver") and theme in seen_themes:
            continue
        if any(b in text for b in _FORBIDDEN):
            continue
        picked.append(text)
        if ticker:
            seen_tickers.add(ticker)
        if theme and theme not in (None, "silver"):
            seen_themes.add(theme)
        if is_idea:
            idea_used = True
        if len(picked) >= P["max_lines"] - 1:        # نترك مكاناً للافتتاحية
            break

    # يوم هادئ: لو ما طلع غير الافتتاحية
    if not picked and mode == "balanced":
        picked.append("يوم هادئ — والهدوء بحدّ ذاته معلومة. لا تطرّف في المخاطر ولا الازدحام ولا التقييم، "
                      "وحيازاتك ماشية. أفضل حركة الحين: ولا حركة — كمّل DCA وخلّك ماشي. أراك التشغيل الجاي.")

    # ── حفظ لقطة اللوح لهذا التشغيل (للاتجاه القادم) — السحابة وحدها تكتب ──
    if persist:
        _save_state(cfg, {
            "run_date": now_local().strftime("%Y-%m-%d %H:%M"),
            "regime_mode": mode, "regime_label": rg.get("regime"),
            "market_risk": risk_now,
            "crowd_pct": crowd_now, "med_fwd_pe": pe_now, "candidate_pct": cand_now,
        })

    return {"lines": [lead] + picked, "disclaimer": DISCLAIMER_AR}
