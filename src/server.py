# -*- coding: utf-8 -*-
"""
server.py — خادم محلي صغير يخلّي زر «حدّث الكل» يشتغل فعلاً.

    python src/server.py

يفتح المتصفح على http://localhost:8800
  • /            → الداشبورد
  • /planner     → مخطّط المحفظة
  • /update      → يحدّث أسهمك live (أسعار + نقاط + محرّكات + أضف/احتفظ/راجع) ~دقيقة
  • /update-full → يفحص السوق كامل (أبطأ)

ملاحظة صريحة: الزر يحدّث الأسعار والأخبار التلقائية وإعادة التقييم. أما البحث
العميق بعيوني (يوتيوب/ويب/تحليل) فهذا أنا لما تطلب — الخادم ما يقدر يكلّمني.
"""

import os
import sys
import json
import subprocess
import webbrowser
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "output")
PORT = int(os.environ.get("MAZER_PORT", "8800"))

_CT = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "application/javascript",
       ".csv": "text/csv; charset=utf-8", ".json": "application/json", ".md": "text/plain; charset=utf-8"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path):
        if not os.path.isfile(path):
            return self._send(404, "not found", "text/plain")
        ext = os.path.splitext(path)[1]
        with open(path, "rb") as f:
            self._send(200, f.read(), _CT.get(ext, "application/octet-stream"))

    def _run(self, mode):
        """Run the pipeline live, regenerate dashboard, return summary."""
        args = [sys.executable, os.path.join("src", "main.py")]
        if mode == "smart":
            # ONE-BUTTON update: full market scan + force-refresh your watchlist/holdings live.
            # First run of the day builds the cache (slower); after that it's fast.
            args += ["--smart"]
        try:
            r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=900)
            tail = "\n".join((r.stdout or "").strip().splitlines()[-12:])
            ok = r.returncode == 0
            self._send(200 if ok else 500, json.dumps(
                {"ok": ok, "mode": mode, "summary": tail, "err": (r.stderr or "")[-400:]},
                ensure_ascii=False))
        except subprocess.TimeoutExpired:
            self._send(504, json.dumps({"ok": False, "summary": "انتهى الوقت — جرّب فحص أصغر"}, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "summary": f"خطأ: {e}"}, ensure_ascii=False))

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self._file(os.path.join(OUT, "dashboard.html"))
        if p in ("/planner", "/planner.html"):
            return self._file(os.path.join(OUT, "planner.html"))
        if p in ("/update", "/update-full"):
            return self._run("smart")
        # serve any other output file (csv/report/etc.)
        return self._file(os.path.join(OUT, os.path.normpath(p.lstrip("/"))))


def main():
    os.makedirs(OUT, exist_ok=True)
    url = f"http://localhost:{PORT}/"
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"✅ الخادم شغّال: {url}")
    print("   • / الداشبورد · /planner المخطّط · زر «حدّث الكل» يشتغل من هنا")
    print("   • أوقفه بـ Ctrl+C")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nتوقّف الخادم.")
        srv.shutdown()


if __name__ == "__main__":
    main()
