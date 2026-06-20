# -*- coding: utf-8 -*-
"""
notify.py — إشعار تيليجرام (اختياري).

التفعيل:
  1) في تيليجرام: كلّم @BotFather → /newbot → خذ التوكن.
  2) كلّم @userinfobot → خذ chat_id حقك.
  3) حطهم في config.py (TELEGRAM) وحوّل enabled=True.
بدونها: النظام يكتب التقرير كملف عادي ويشتغل تمام.
"""

import urllib.request
import urllib.parse
import json

from config import TELEGRAM


def send_telegram(text):
    if not TELEGRAM.get("enabled"):
        return False, "تيليجرام غير مفعّل (التقرير محفوظ كملف)"
    token = TELEGRAM.get("bot_token", "")
    chat_id = TELEGRAM.get("chat_id", "")
    if not token or not chat_id:
        return False, "ينقص bot_token أو chat_id"

    # تيليجرام يحد الرسالة بـ 4096 حرف
    chunk = text[:4000]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": chunk,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.loads(r.read().decode())
            return bool(res.get("ok")), "أُرسل ✅" if res.get("ok") else str(res)
    except Exception as e:
        return False, f"فشل الإرسال: {e}"
