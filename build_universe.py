# -*- coding: utf-8 -*-
"""
build_universe.py — يبني "كون" كبير من مصادر مجانية رسمية.

الخيارات:
  python3 build_universe.py            → S&P 1500 (500+400+600) ≈ 1500 شركة استثمارية
                                          (الأفضل: واسع + كله شركات حقيقية مغطّاة بمحللين)
  python3 build_universe.py --sec      → كل رموز SEC (~10 آلاف، فيها أسماء صغيرة كثيرة)
  python3 build_universe.py --all      → S&P 1500 + SEC مدموجين

يحفظ النتيجة في universe_data.txt — والنظام يستخدمها تلقائياً بدل القائمة المنتقاة.
كله مجاني، بدون مفتاح API.
"""

import sys
import io
import requests
import pandas as pd

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 mazer-system/1.0"

SP_PAGES = {
    "S&P 500": ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 0),
    "S&P 400": ("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", 0),
    "S&P 600": ("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", 0),
}


def _clean(sym):
    return str(sym).strip().upper().replace(".", "-")  # BRK.B → BRK-B (صيغة Yahoo)


def from_sp1500():
    tickers = set()
    for name, (url, _) in SP_PAGES.items():
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            r.raise_for_status()
            tables = pd.read_html(io.StringIO(r.text))
            found = 0
            for tbl in tables:
                cols = [str(c).lower() for c in tbl.columns]
                sym_col = None
                for cand in ("symbol", "ticker symbol", "ticker"):
                    for i, c in enumerate(cols):
                        if cand == c or cand in c:
                            sym_col = tbl.columns[i]
                            break
                    if sym_col is not None:
                        break
                if sym_col is not None:
                    for s in tbl[sym_col].dropna():
                        cs = _clean(s)
                        if cs and cs.replace("-", "").isalnum() and len(cs) <= 6:
                            tickers.add(cs)
                            found += 1
                    break
            print(f"  {name}: +{found}")
        except Exception as e:
            print(f"  {name}: فشل ({e})")
    return tickers


def from_sec():
    tickers = set()
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        data = r.json()
        for _, row in data.items():
            cs = _clean(row.get("ticker", ""))
            if cs and cs.replace("-", "").isalnum() and len(cs) <= 6:
                tickers.add(cs)
        print(f"  SEC: +{len(tickers)}")
    except Exception as e:
        print(f"  SEC: فشل ({e})")
    return tickers


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--sp1500"
    print(f"بناء الكون (الوضع: {mode}) ...")
    tickers = set()
    if mode in ("--sp1500", "--all") or mode == "--sp1500":
        tickers |= from_sp1500()
    if mode in ("--sec", "--all"):
        tickers |= from_sec()
    if not tickers:
        print("⚠️ ما قدرت أجيب أي رموز. تأكد من الاتصال.")
        return 1

    out = sorted(tickers)
    with open("universe_data.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"\n✅ حُفظ {len(out)} رمز في universe_data.txt")
    print("شغّل run.py عادي — النظام بيستخدم الكون الكبير تلقائياً.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
