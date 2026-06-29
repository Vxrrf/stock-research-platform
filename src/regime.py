"""
regime.py — الطبقة «العاقلة»، نسخة v2 (آلة حالات بذاكرة واتجاه).

الفلسفة: «دافِع وأنت نازل، هاجِم عند الانعطاف». لا نقرأ *مستوى* الخطر وحده بل *اتجاهه*:
نُدخِل الدفاع حين يصعد الخطر، ونخرج منه — قفزاً مباشراً للهجوم — حين يبلغ الخطر ذروته ثم
يبدأ ينحسر فعلياً (مؤكَّداً عبر جولات) مع رخصٍ حقيقي في التقييم واتّساع فرص الجودة. لا توجد
«حالة دفاع نهائية»: ثلاثة أبواب خروج (بوّابة القاع، سقف زمني، عودة الهدوء) تضمن ألا يعلق أبداً.

تستشعر الحاضر ولا تتنبّأ بالغيب. تُرشّح وضعاً موجوداً (محافظ/متوازن/هجومي) لمستثمر DCA —
لا رافعة، لا all-in، لا أمر بيع/شراء آني. القرار النهائي للمستخدم (يقدر يتجاوز يدوياً).

المدخلات (نفس فلتر v1 — لا مصدر بيانات جديد): market_risk، crowded_late/popular_not_cheap،
forward_pe، action=="Candidate". الذاكرة في data/_state/regime_history.json تمنحنا الاتجاه.
"""

import json
import os

from config_loader import state_dir
from schema import now_utc, iso

_RISK_RANK = {"low": 0, "medium": 1, "high": 2, "extreme": 3}

DISCLAIMER_AR = ("قراءة للحظة الحالية من إشاراتنا — ليست تنبؤاً بالغيب. "
                 "تُرشّح وضعاً، والقرار يبقى لك.")

_MODE_FILE = {"conservative": "conservative.html", "balanced": "index.html",
              "aggressive": "aggressive.html"}
_MODE_AR = {"conservative": "محافظ", "balanced": "متوازن", "aggressive": "هجومي"}

_STATE_NAME = "regime_history.json"


def _params(cfg):
    rc = ((cfg or {}).get("regime", {}) or {})
    return {
        "confirm_runs": rc.get("confirm_runs", 2),
        "min_hold_runs": rc.get("min_hold_runs", 2),
        "max_defensive_runs": rc.get("max_defensive_runs", 16),
        "history_len": rc.get("history_len", 8),
        "crowd_enter": rc.get("crowd_enter", 0.50),
        "crowd_calm": rc.get("crowd_calm", 0.40),
        "pe_bubble": rc.get("pe_bubble", 34),
        "cand_attack": rc.get("cand_attack", 0.12),
        "cand_bottom": rc.get("cand_bottom", 0.10),
        "breadth_deep": rc.get("breadth_deep", 0.25),    # سهم بعيد ≥هذا عن قمّته = «متضرّر بعمق»
        "breadth_broad": rc.get("breadth_broad", 0.50),  # ≥هذا من الأسماء متضرّرة = هبوط واسع/انهيار عام
        "pe_cheap": rc.get("pe_cheap", 22),
        "peak_drop_frac": rc.get("peak_drop_frac", 0.85),
        "defense_relief_cand": rc.get("defense_relief_cand", 0.08),
    }


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def _state_path(cfg):
    return os.path.join(state_dir(cfg), _STATE_NAME)


def _load_state(cfg):
    try:
        with open(_state_path(cfg), encoding="utf-8") as f:
            st = json.load(f)
            return st if isinstance(st, dict) else {}
    except Exception:
        return {}                                   # missing/corrupt → cold-start, never drop the run


def _save_state(cfg, st):
    try:
        with open(_state_path(cfg), "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"  regime state save skipped: {e}")


def _metrics(records, market_risk, deep_thresh=0.25):
    invest = [r for r in records if not r.get("is_fund")
              and r.get("investable", True) and r.get("action") != "Avoid"]
    n = len(invest) or 1
    crowded = sum(1 for r in invest if r.get("crowded_late") or r.get("popular_not_cheap"))
    crowd_pct = crowded / n
    fpes = [r.get("forward_pe") for r in invest
            if isinstance(r.get("forward_pe"), (int, float)) and 0 < r.get("forward_pe") < 200]
    med_fpe = _median(fpes)
    cand_pct = sum(1 for r in invest if r.get("action") == "Candidate") / n
    risk_rank = _RISK_RANK.get(str(market_risk or "").strip().lower(), 0)
    # breadth of the damage: كم اسم بعيد ≥25% عن قمّته — اتساع الهبوط يميّز الانهيار العام
    # (capitulation حقيقية) عن تصحيحٍ ضيّق، ويقوّي إشارة «اشترِ وقت الخوف».
    deep = sum(1 for r in invest if isinstance(r.get("pct_below_52w_high"), (int, float))
               and r["pct_below_52w_high"] >= deep_thresh)
    cov = sum(1 for r in invest if isinstance(r.get("pct_below_52w_high"), (int, float)))
    breadth_down = (deep / cov) if cov else None
    return n, crowd_pct, med_fpe, cand_pct, risk_rank, breadth_down


def _stateless_decide(risk_rank, crowd_pct, med_fpe, cand_pct):
    """منطق المستوى (سلوك v1) — يُستخدم في بدء بارد قبل توفّر تاريخٍ كافٍ."""
    if risk_rank >= 3 or (risk_rank >= 2 and crowd_pct >= 0.40):
        return ("ضغط مرتفع — حذر دفاعي", "conservative",
                "مخاطر مرتفعة — مِل للحماية وتمهّل في الإضافة (بحجمٍ مدروس).")
    if crowd_pct >= 0.50 and (med_fpe is not None and med_fpe >= 34):
        return ("فقاعة محتملة — حذر", "conservative",
                "ازدحام وتقييمات مرتفعة — قلّل المطاردة ورجّح الجودة والحماية.")
    if risk_rank >= 2:
        return ("ضغط مرتفع — حذر دفاعي", "conservative",
                "مخاطر السوق مرتفعة — مِل للحماية حتى يتّضح الاتجاه.")
    if cand_pct >= 0.12 and crowd_pct < 0.40:
        return ("فرصة — وضع الهجوم", "aggressive",
                "فرص جودة كثيرة ومخاطر معقولة — مِل للنمو والصيد بحجمٍ مدروس.")
    return ("طبيعي — توازن", "balanced",
            "لا تطرّف واضح — التوازن الافتراضي يكفي.")


def detect(records, market_risk, cfg=None, persist=True):
    """يرجّع قراءة وضع السوق + الوضع الموصى به، بذاكرةٍ واتجاه. دفاعيّ ضدّ القيم الناقصة.
    persist=False (تشغيل الماك من الكاش) لا يكتب الحالة — السحابة وحدها تملك ذاكرة الـFSM."""
    cfg = cfg or {}
    P = _params(cfg)
    n, crowd_pct, med_fpe, cand_pct, risk_rank, breadth_down = _metrics(
        records, market_risk, P["breadth_deep"])
    broad_damage = isinstance(breadth_down, (int, float)) and breadth_down >= P["breadth_broad"]

    st = _load_state(cfg)
    hist = st.get("history") or []
    prev = hist[-1] if hist else None
    prev_risk = prev.get("risk_rank") if isinstance(prev, dict) else None
    cold = len(hist) < 1                              # نقص تاريخ فقط؛ med_fpe الناقص يُعالَج داخل الآلة

    # ── حالة محمَّلة ──
    peak = int(st.get("peak_risk_rank") or 0)
    peak_pe = st.get("peak_med_fpe")
    easing = int(st.get("easing_streak") or 0)
    defensive_runs = int(st.get("defensive_runs") or 0)
    calm_streak = int(st.get("calm_streak") or 0)
    episode = bool(st.get("episode_active"))
    relieved = bool(st.get("relieved"))              # خرجنا من الدفاع المطوّل عند هضبة عالية — لا نعود إلا بتصاعد
    cur_mode = st.get("current_mode")
    mode_since = int(st.get("mode_since_run") or 0)

    rising = (prev_risk is not None and risk_rank > prev_risk)

    # ── محاسبة النوبة/الاتجاه (تجري دائماً، حتى أثناء التسخين) ──
    if risk_rank > peak:
        peak = risk_rank
        easing = 0
        relieved = False                             # تصاعد جديد يُلغي «التهدئة»
        if risk_rank >= 2:
            episode = True
    if prev_risk is not None:
        easing = (easing + 1) if risk_rank <= prev_risk else 0
    if episode and med_fpe is not None:              # أعلى تقييم في النوبة = مستوى ما قبل الانهيار
        peak_pe = med_fpe if peak_pe is None else max(peak_pe, med_fpe)
    calm_streak = (calm_streak + 1) if risk_rank <= 1 else 0
    if episode and calm_streak >= P["confirm_runs"]:  # عودة الهدوء تُغلق النوبة وتُعيد التسليح
        episode, peak, peak_pe, relieved = False, 0, None, False

    cheap = (med_fpe is not None
             and (med_fpe <= P["pe_cheap"]
                  or (peak_pe and med_fpe <= P["peak_drop_frac"] * peak_pe)))

    # ── جدول القرار (أول تطابق يفوز). المبدأ: الدفاع للخطر *الصاعد/عند الذروة* فقط؛
    #     بمجرّد ما ينزل الخطر عن قمّته نترك الدفاع الكامل (هجوم لو رخص، وإلا توازن) → لا تعلّق أبداً ──
    safety = False
    is_bottom = False                                # علم ثابت (لا نعتمد على نصّ العرض العربي للـbypass)
    if cold:
        regime, mode, why = _stateless_decide(risk_rank, crowd_pct, med_fpe, cand_pct)
    elif risk_rank >= 3:                              # 1) override أمني فوري (Extreme)
        regime, mode = "تصعيد الأزمة — دفاع", "conservative"
        why = "ضغط أقصى — حماية فورية لرأس المال (بحجمٍ مدروس)."
        safety = True
        relieved = False
    elif (episode and peak >= 2 and risk_rank <= peak - 1
          and easing >= P["confirm_runs"] and cand_pct >= P["cand_bottom"] and cheap):  # 2) القاع/التعافي
        regime, mode = "القاع/التعافي — هجوم محسوب", "aggressive"
        is_bottom = True
        why = ("الخطر نزل عن قمّته وثبت نزوله، والتقييم رخص والفرص اتّسعت%s — "
               "مِل لمزيد من الجودة بحجمٍ مدروس (DCA)، لا دفعة واحدة."
               % (("، والهبوط واسع (%d%% بعيدة عن قممها) — قاعٌ عام لا تصحيح ضيّق"
                   % round(breadth_down * 100)) if broad_damage else ""))
    elif risk_rank >= 2 and risk_rank < peak and not rising:  # 3) ما بعد الذروة — حياد (مضادّ التعلّق)
        regime, mode = "ما بعد الذروة — حياد حذِر", "balanced"
        why = "الخطر بدأ ينزل عن قمّته لكن التقييم لم يرخص بعد — حياد حذِر، لا دفاع كامل ولا اندفاع."
    elif risk_rank >= 2:                              # 4) عند الذروة/صاعد — دفاع (مع تهدئة عند طول الهضبة)
        if rising:
            relieved = False
            regime, mode = "تصعيد الأزمة — دفاع", "conservative"
            why = "الخطر مرتفع وما زال يصعد — احمِ رأس المال وطارد أقل."
        elif relieved or (defensive_runs >= P["max_defensive_runs"] and risk_rank < 3):
            relieved = True                          # هضبة عالية طويلة بلا تصعيد → تهدئة وتبقى
            regime, mode = "تهدئة الدفاع — توازن", "balanced"
            why = "طال الدفاع والخطر توقّف عن التصعيد — توازن حذِر بدل التعلّق دفاعياً."
        else:
            regime, mode = "ضغط مرتفع — دفاع", "conservative"
            why = "الخطر مرتفع وعند ذروته — حافظ على الحماية حتى يبدأ ينحسر."
    elif (risk_rank <= 1 and crowd_pct >= P["crowd_enter"]
          and med_fpe is not None and med_fpe >= P["pe_bubble"]):  # 5) فقاعة/رغوة — تشذيب
        regime, mode = "فقاعة/رغوة — تشذيب", "conservative"
        why = "ازدحام وتقييمات مرتفعة في سوق هادئ — قلّل المطاردة ورجّح الجودة."
    elif risk_rank <= 1 and crowd_pct < P["crowd_calm"] and cand_pct >= P["cand_attack"]:  # 6) فرصة هادئة
        regime, mode = "فرصة هادئة — هجوم", "aggressive"
        why = "هدوء وفرص جودة وفيرة بلا ازدحام — مِل للنمو والصيد بحجمٍ مدروس."
    else:                                             # 7) طبيعي — توازن
        regime, mode = "طبيعي — توازن", "balanced"
        why = "لا تطرّف واضح — التوازن الافتراضي يكفي."

    # ── hysteresis: الحماية سريعة (دخول الدفاع فوري)؛ القاع المؤكَّد يتجاوز الـcooldown؛
    #     باقي التحوّلات الأنعم (خروج/هجوم هادئ/تشذيب) تحترم min_hold لمنع التذبذب ──
    bypass = safety or is_bottom                     # القاع المؤكَّد يتجاوز الـcooldown (علم ثابت)
    held = False
    if (not cold and cur_mode and mode != cur_mode
            and mode != "conservative"               # دخول الدفاع لا يُؤجَّل أبداً
            and mode_since < P["min_hold_runs"] and not bypass):
        mode = cur_mode
        held = True

    # ── عدّادات للجولة القادمة ──
    if mode != cur_mode:
        mode_since = 0
    else:
        mode_since += 1
    defensive_runs = (defensive_runs + 1) if mode == "conservative" else 0

    # ── إشارات شفّافة (بالاتجاه) ──
    signals = []
    if risk_rank >= 2:
        signals.append("مخاطر السوق %s" % ("قصوى" if risk_rank >= 3 else "مرتفعة"))
    if not cold and prev_risk is not None:
        if risk_rank > prev_risk:
            signals.append("الخطر يتصاعد")
        elif risk_rank < prev_risk:
            signals.append("الخطر يهدأ (انحسار %d جولة)" % easing)
    if crowd_pct >= P["crowd_calm"]:
        signals.append("ازدحام %d%%" % round(crowd_pct * 100))
    if med_fpe is not None and med_fpe >= P["pe_bubble"]:
        signals.append("تقييم مرتفع — وسيط P/E %d" % round(med_fpe))
    if med_fpe is not None and med_fpe <= P["pe_cheap"]:
        signals.append("تقييم رخيص — وسيط P/E %d" % round(med_fpe))
    if cand_pct >= P["cand_bottom"]:
        signals.append("فرص رخيصة %d%%" % round(cand_pct * 100))
    if broad_damage:
        signals.append("هبوط واسع — %d%% بعيدة عن قممها" % round(breadth_down * 100))
    if held:
        signals.append("تثبيت مؤقّت لمنع التذبذب")

    # ── الثقة ──
    if mode == "aggressive" and regime.startswith("القاع"):
        conf = "HIGH"
    elif risk_rank >= 3:
        conf = "HIGH"
    elif cold:
        conf = "MED" if len(signals) >= 2 else "LOW"
    else:
        strong = len([s for s in signals if s != "تثبيت مؤقّت لمنع التذبذب"])
        conf = "HIGH" if strong >= 3 else ("MED" if strong == 2 else "LOW")
        if mode == "balanced" and strong <= 1:
            conf = "HIGH"

    # ── حفظ الحالة ──
    ts = iso(now_utc())
    new_hist = (hist + [{
        "ts": ts, "risk_rank": risk_rank, "market_risk": market_risk,
        "crowd_pct": round(crowd_pct, 3),
        "med_fwd_pe": round(med_fpe, 1) if med_fpe is not None else None,
        "cand_pct": round(cand_pct, 3), "regime": regime, "recommended_mode": mode,
    }])[-P["history_len"]:]
    if persist:                                       # الماك من الكاش لا يلوّث ذاكرة الـFSM (السحابة تملكها)
        _save_state(cfg, {
            "schema": 1, "updated_utc": ts, "history": new_hist,
            "episode_active": episode, "peak_risk_rank": peak, "peak_med_fpe": peak_pe,
            "easing_streak": easing, "defensive_runs": defensive_runs, "calm_streak": calm_streak,
            "relieved": relieved, "current_mode": mode, "mode_since_run": mode_since,
        })

    return {
        "regime": regime,
        "recommended_mode": mode,
        "recommended_mode_ar": _MODE_AR.get(mode, mode),
        "recommended_file": _MODE_FILE.get(mode, "index.html"),
        "confidence": conf,
        "why": why,
        "signals": signals,
        "metrics": {
            "market_risk": market_risk,
            "crowd_pct": round(crowd_pct, 3),
            "med_fwd_pe": round(med_fpe, 1) if med_fpe is not None else None,
            "candidate_pct": round(cand_pct, 3),
            "breadth_down": round(breadth_down, 3) if isinstance(breadth_down, (int, float)) else None,
            "n": n,
            "risk_trend": ("rising" if rising else ("easing" if (prev_risk is not None and risk_rank < prev_risk) else "flat")),
            "episode_active": episode,
        },
        "disclaimer": DISCLAIMER_AR,
    }
