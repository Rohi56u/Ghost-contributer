from __future__ import annotations

import hmac
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.resources import files
from urllib.parse import urlsplit

from .errors import SafeStop


def handler_for(engine, token: str, port: int):
    origin = f"http://127.0.0.1:{port}"

    class Handler(BaseHTTPRequestHandler):
        server_version = "GhostLocal/0.2"

        def log_message(self, *args):
            pass  # Never log tokens, source, request bodies or repository paths.

        def send(self, status, content, mime="application/json"):
            raw = json.dumps(content).encode() if mime == "application/json" else content
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def safe_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{port}" and self.headers.get("Origin", origin) == origin

        def authorized(self):
            supplied = self.headers.get("Authorization", "")
            return self.safe_host() and hmac.compare_digest(supplied, "Bearer " + token)

        def do_GET(self):
            if not self.safe_host():
                return self.send(403, {"error": "Use the exact local dashboard address."})
            path = urlsplit(self.path).path
            if path == "/api/status":
                if not self.authorized():
                    return self.send(401, {"error": "Open the dashboard URL printed by ghost dashboard, including its token fragment."})
                try:
                    return self.send(200, engine.status())
                except SafeStop as exc:
                    return self.send(409, {"error": str(exc), "code": exc.code})
            assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path not in assets:
                return self.send(404, {"error": "Not found"})
            name, mime = assets[path]
            return self.send(200, files("ghost_contributor").joinpath("web", name).read_bytes(), mime)

        def do_POST(self):
            if not self.authorized():
                return self.send(403, {"error": "Local authentication required."})
            if self.path != "/api/action" or self.headers.get("Content-Type") != "application/json":
                return self.send(400, {"error": "Expected a JSON action."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 4096:
                    raise ValueError("length")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) - {"action", "id", "repo"}:
                    raise ValueError("body")
                action = body.get("action")
                if action == "run":
                    result = engine.run(body["repo"], dry_run=True)
                    result = {"status": result.get("status"), "id": result.get("id")}
                elif action == "approve":
                    p = engine.approve(body["id"], actor="dashboard")
                    result = {"status": p["status"], "sha": p.get("commit_sha")}
                elif action == "reject":
                    engine.reject(body["id"])
                    result = {"status": "rejected"}
                elif action in {"pause", "resume", "stop"}:
                    engine.state.set_flag("paused", action != "resume")
                    if action == "stop":
                        engine.state.set_flag("killed", True)
                    if action == "resume":
                        engine.state.set_flag("killed", False)
                    result = {"status": action}
                else:
                    raise ValueError("action")
                return self.send(200, result)
            except SafeStop as exc:
                return self.send(409, {"error": str(exc), "code": exc.code})
            except (ValueError, KeyError, TypeError):
                return self.send(400, {"error": "Invalid action payload."})
            except Exception:
                return self.send(500, {"error": "Operation stopped. Inspect local state; do not retry a commit blindly."})

    return Handler


def serve(engine, port: int = 8765):
    token = secrets.token_urlsafe(32)
    handler = handler_for(engine, token, port)
    # Deliberately single-threaded: one mutating operation at a time.
    with HTTPServer(("127.0.0.1", port), handler) as server:
        server.timeout = 1
        print(f"Local dashboard: http://127.0.0.1:{port}/#token={token}", flush=True)
        print("Keep this URL private. Ctrl+C closes the dashboard. No network push action is exposed here.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
