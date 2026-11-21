"""Tiny dependency-free HTTP server: JSON API + static frontend.

Run:  python3 server.py            (http://localhost:8000)
      PORT=9000 python3 server.py
"""
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from recommender import Recommender

ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.normpath(os.path.join(ROOT, "..", "frontend"))
engine = Recommender()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json"):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/meta":
            return self._send(200, engine.meta())
        if path == "/api/knowledge":
            return self._send(200, engine.knowledge_view())
        if path == "/api/health":
            return self._send(200, {"status": "ok"})
        if path.startswith("/api/"):
            return self._send(404, {"error": "Not found"})
        return self._static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/recommend":
            return self._send(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            return self._send(200, engine.recommend(req))
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            return self._send(400, {"error": str(e)})

    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(FRONTEND, rel))
        if not full.startswith(FRONTEND + os.sep) or not os.path.isfile(full):
            return self._send(404, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            return self._send(200, f.read(), ctype)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("Knowledge-based recommender running at http://localhost:%d" % port)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
