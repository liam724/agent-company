"""Alert service HTTP API: python -m sunset.server

Runs on 127.0.0.1:8787 behind the web server, which serves the static site and proxies /api/.

Environment (besides those in alerts.py):
  SUNSET_PORT            listen port (default 8787)
  STRIPE_WEBHOOK_SECRET  signing secret for POST /api/stripe; the route is off without it
  SUNSET_ADMIN_KEY       key for GET /api/stats; the route is off without it
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import alerts, registry

MAX_BODY = 16_384
MAX_STRIPE_BODY = 512_000
RATE_LIMIT, RATE_WINDOW = 6, 3600
_hits: dict[str, list[float]] = {}
_lock = threading.Lock()


def rate_ok(ip: str, now: float | None = None) -> bool:
    now = now or time.time()
    with _lock:
        recent = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
        ok = len(recent) < RATE_LIMIT
        if ok:
            recent.append(now)
        _hits[ip] = recent
        if len(_hits) > 10_000:
            _hits.clear()
        return ok


def verify_stripe(payload: bytes, header: str, secret: str, now: float | None = None,
                  tolerance: int = 300) -> bool:
    """Stripe-Signature: t=<unix>,v1=<hex hmac-sha256 of "t.payload">[,v1=...]"""
    parts = [p.split("=", 1) for p in (header or "").split(",") if "=" in p]
    ts = next((v for k, v in parts if k == "t"), None)
    sigs = [v for k, v in parts if k == "v1"]
    if not ts or not ts.isdigit() or not sigs:
        return False
    if abs((now or time.time()) - int(ts)) > tolerance:
        return False
    want = hmac.new(secret.encode(), ts.encode() + b"." + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(want, s) for s in sigs)


def handle_stripe(db, event: dict, mailer=None) -> str:
    kind, obj = event.get("type"), event.get("data", {}).get("object", {})
    if kind == "checkout.session.completed":
        email = (obj.get("customer_details") or {}).get("email") or obj.get("customer_email")
        if not email:
            return "ignored: no email"
        token = alerts.set_plan(db, email, "pro", obj.get("customer"))
        (mailer or alerts.send_mail)(
            email, "Model Sunset Pro is active",
            "Thanks for subscribing to Model Sunset Pro.\n\nSet your watch list (whole providers "
            "like anthropic/* now work) and your webhook here:\n\n"
            f"{alerts.site()}/manage/?token={token}\n", token)
        return "upgraded"
    if kind == "customer.subscription.deleted":
        n = alerts.downgrade_customer(db, obj.get("customer") or "")
        return f"downgraded {n}"
    return "ignored"


class Handler(BaseHTTPRequestHandler):
    server_version = "ModelSunset"
    mailer = None  # tests replace this

    def log_message(self, fmt, *args):  # no request logs: they would hold tokens and IPs
        pass

    # -- helpers
    def _ip(self):
        return (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[-1].strip()

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, path):
        self.send_response(303)
        self.send_header("Location", path)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _body(self, limit=MAX_BODY):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > limit:
            return None
        return self.rfile.read(n)

    def _params(self, raw: bytes) -> tuple[dict, bool]:
        """Returns (fields, wants_json)."""
        if "json" in (self.headers.get("Content-Type") or ""):
            try:
                data = json.loads(raw or b"{}")
            except ValueError:
                data = None
            return (data if isinstance(data, dict) else {}), True
        form = urllib.parse.parse_qs(raw.decode("utf-8", "replace"))
        return {k: v[0] for k, v in form.items()}, False

    # -- routes
    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        db = alerts.connect()
        try:
            if url.path == "/api/health":
                return self._json(200, {"ok": True})
            if url.path == "/api/confirm":
                return self._redirect("/confirmed/" if alerts.confirm(db, q.get("token", ""))
                                      else "/alerts/")
            if url.path == "/api/unsubscribe":
                alerts.unsubscribe(db, q.get("token", ""))
                return self._redirect("/unsubscribed/")
            if url.path == "/api/me":
                data = alerts.me(db, q.get("token", ""))
                return self._json(200, data) if data else self._json(404, {"error": "That link is no longer valid."})
            if url.path == "/api/stats":
                key = os.environ.get("SUNSET_ADMIN_KEY")
                if key and hmac.compare_digest(key, q.get("key", "")):
                    return self._json(200, alerts.stats(db))
                return self._json(404, {"error": "not found"})
            self._json(404, {"error": "not found"})
        finally:
            db.close()

    def do_POST(self):
        url = urllib.parse.urlsplit(self.path)
        db = alerts.connect()
        try:
            if url.path == "/api/stripe":
                return self._stripe(db)
            raw = self._body()
            if raw is None:
                return self._json(413, {"error": "Request too large."})
            fields, wants_json = self._params(raw)
            if url.path == "/api/unsubscribe":  # RFC 8058 one-click
                q = urllib.parse.parse_qs(url.query)
                alerts.unsubscribe(db, (q.get("token") or [fields.get("token", "")])[0])
                return self._json(200, {"message": "Unsubscribed."})
            if url.path == "/api/subscribe":
                return self._subscribe(db, fields, wants_json)
            if url.path == "/api/manage":
                try:
                    data = alerts.manage(db, str(fields.get("token", "")), fields.get("models"),
                                         fields.get("webhook"), registry.load())
                except alerts.Rejected as exc:
                    return self._json(400, {"error": str(exc)})
                return self._json(200, dict(data, message="Saved."))
            self._json(404, {"error": "not found"})
        finally:
            db.close()

    def _subscribe(self, db, fields, wants_json):
        ok_msg = "Check your email for a confirmation link. Alerts start once you click it."
        if fields.get("website"):  # honeypot: bots fill every field
            return self._json(200, {"message": ok_msg}) if wants_json else self._redirect("/check-email/")
        if not rate_ok(self._ip()):
            return self._json(429, {"error": "Too many requests from your network. Try again in an hour."})
        try:
            kwargs = {"mailer": self.mailer} if self.mailer else {}
            alerts.subscribe(db, str(fields.get("email", "")), fields.get("models"),
                             registry.load(), **kwargs)
        except alerts.Rejected as exc:
            return self._json(400, {"error": str(exc)})
        except Exception:
            return self._json(502, {"error": "We couldn't send the confirmation email. Please try again later."})
        return self._json(200, {"message": ok_msg}) if wants_json else self._redirect("/check-email/")

    def _stripe(self, db):
        secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        raw = self._body(MAX_STRIPE_BODY)
        if not secret or raw is None:
            return self._json(404, {"error": "not found"})
        if not verify_stripe(raw, self.headers.get("Stripe-Signature", ""), secret):
            return self._json(400, {"error": "bad signature"})
        try:
            event = json.loads(raw)
        except ValueError:
            return self._json(400, {"error": "bad json"})
        kwargs = {"mailer": self.mailer} if self.mailer else {}
        self._json(200, {"result": handle_stripe(db, event, **kwargs)})


def main():
    port = int(os.environ.get("SUNSET_PORT", "8787"))
    registry.load()  # fail at start, not on first request
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
