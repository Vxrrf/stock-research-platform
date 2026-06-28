# -*- coding: utf-8 -*-
"""
run.py — المشغّل الرئيسي. شغّله بأمر واحد:

    python3 run.py

ويسوّي كل شي:
  ١) يفلتر الكون (المرحلة الأولى)
  ٢) يطلّع تقرير عربي بأسلوب المازر
  ٣) يجهّز ملف البحث العميق (dossier) للمرحلة الثانية
  ٤) يرسل إشعار تيليجرام (لو مفعّل)

كله مجاني، بدون أي اشتراك.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

from config import SETTINGS
from universe import get_universe
from screener import run_screen
from report_ar import build_report
from dossier import build_dossier, build_json
from notify import send_telegram


def _stamp():
    tz = timezone(timedelta(hours=SETTINGS["qatar_utc_offset"]))
    return datetime.now(tz).strftime("%Y%m%d_%H%M")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, SETTINGS["output_dir"])
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("  نظام المازر 2.0 — بدء الفرز")
    print("=" * 60)

    universe = get_universe()
    print(f"حجم الكون: {len(universe)} سهم\n")

    shortlist, stats = run_screen(universe, verbose=True)

    print(f"\n{'='*60}")
    print(f"  فُحص {stats['examined']} | نجا {stats['survivors']} | القائمة القصيرة {len(shortlist)}")
    print(f"{'='*60}\n")

    # التقارير
    report = build_report(shortlist, stats)
    dossier = build_dossier(shortlist, stats)
    js = build_json(shortlist, stats)

    stamp = _stamp()
    paths = {
        f"report_{stamp}.md": report,
        "report_latest.md": report,
        f"dossier_{stamp}.md": dossier,
        "dossier_latest.md": dossier,
        "candidates_latest.json": js,
    }
    for fname, content in paths.items():
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            f.write(content)

    print(f"📄 التقرير: {os.path.join(out_dir, 'report_latest.md')}")
    print(f"🔬 ملف البحث: {os.path.join(out_dir, 'dossier_latest.md')}")
    print(f"🗂️  JSON: {os.path.join(out_dir, 'candidates_latest.json')}")

    # إشعار
    if shortlist:
        top = shortlist[0]
        msg = (f"🎯 *المازر 2.0* — {len(shortlist)} مرشّح جديد\n\n"
               f"الأقوى: *{top['ticker']}* ({top['name']})\n"
               f"صعود متوقع: {(top['upside'] or 0):+.0%} | نقاط {top.get('score')}\n\n"
               f"افتح التقرير وكمّل البحث العميق مع كلود.")
    else:
        msg = "🎯 المازر 2.0: ما نجا أي سهم اليوم (المعايير صارمة). وسّع الكون أو خفّف معياراً."

    ok, info = send_telegram(msg)
    print(f"📲 إشعار: {info}")

    print("\n✅ خلصنا. التالي: افتح كلود واطلب البحث العميق على القائمة القصيرة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
