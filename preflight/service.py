"""Connected Preflight service: hosted check, watch signups, daily drift run.

    python3 service.py serve         # 127.0.0.1:8788, behind the web server that serves dist/
    python3 service.py run-watches   # daily: re-snapshot every confirmed watch, mail on drift
    python3 service.py stats

Reuses the mailer, public-address guard and rate limiter from product/sunset.

Environment: PREFLIGHT_DB (./preflight.db), PREFLIGHT_PORT (8788), PREFLIGHT_ADMIN_KEY,
SITE_URL, MAIL_FROM, SMTP_* and SUNSET_OUTBOX as in product/sunset/alerts.py.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import secrets
import sqlite3
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "product")]

import preflight  # noqa: E402
from sunset import alerts as mail  # noqa: E402  send_mail, check_webhook_url, EMAIL_RE, Rejected
from sunset.server import rate_ok  # noqa: E402

os.environ.setdefault("SITE_URL", "https://connectedpreflight.com")  # also used by the shared mailer
os.environ.setdefault("MAIL_FROM", "Connected Preflight <watch@connectedpreflight.com>")
MAX_BODY = 4096
FREE_WATCHES = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS checks(url_hash TEXT NOT NULL, at TEXT NOT NULL, fails INTEGER, warns INTEGER);
CREATE TABLE IF NOT EXISTS watches(
  id INTEGER PRIMARY KEY, email TEXT NOT NULL, url TEXT NOT NULL, token TEXT UNIQUE NOT NULL,
  confirmed INTEGER NOT NULL DEFAULT 0, wants_paid INTEGER NOT NULL DEFAULT 0,
  baseline TEXT NOT NULL, last_hash TEXT NOT NULL, created TEXT NOT NULL, UNIQUE(email, url));
"""
Rejected = mail.Rejected


def site() -> str:
    return os.environ.get("SITE_URL", "https://connectedpreflight.com").rstrip("/")


def connect(path: str | None = None) -> sqlite3.Connection:
    db = sqlite3.connect(path or os.environ.get("PREFLIGHT_DB", "preflight.db"))
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def guard(url: str) -> None:
    """Hosted checks only reach public https hosts, so the service cannot probe private networks."""
    try:
        mail.check_webhook_url(url)
    except Rejected:
        raise Rejected("Enter a public https:// MCP endpoint.")


def run_check(db, url: str, checker=preflight.check, guard=guard) -> dict:
    url = url.strip()
    guard(url)
    report = checker(url)
    # Only a hash of the URL is kept: enough to count distinct endpoints, nothing to leak.
    db.execute("INSERT INTO checks VALUES(?,?,?,?)",
               (hashlib.sha256(url.encode()).hexdigest(), now(),
                report["summary"]["fail"], report["summary"]["warn"]))
    db.commit()
    return report


def add_watch(db, email: str, url: str, wants_paid: bool = False, checker=preflight.check,
              guard=guard, mailer=None) -> dict:
    email, url = email.strip().lower(), url.strip()
    if not mail.EMAIL_RE.match(email):
        raise Rejected("Enter a valid email address.")
    guard(url)
    confirmed = db.execute("SELECT COUNT(*) FROM watches WHERE email=? AND confirmed=1 AND url<>?",
                           (email, url)).fetchone()[0]
    if confirmed >= FREE_WATCHES:
        raise Rejected("The free watch covers one endpoint. Tick the paid box and we will tell you when more are available.")
    snap = checker(url)["snapshot"]
    if not snap:
        raise Rejected("That endpoint did not return a tool list without authorization, so there is nothing to watch yet.")
    token = secrets.token_urlsafe(24)
    db.execute("INSERT INTO watches(email,url,token,wants_paid,baseline,last_hash,created) VALUES(?,?,?,?,?,?,?) "
               "ON CONFLICT(email,url) DO UPDATE SET wants_paid=excluded.wants_paid",
               (email, url, token, int(bool(wants_paid)), json.dumps(snap), snap["hash"], now()))
    db.commit()
    row = db.execute("SELECT token, confirmed FROM watches WHERE email=? AND url=?", (email, url)).fetchone()
    if not row["confirmed"]:
        (mailer or mail.send_mail)(
            email, "Confirm your Connected Preflight watch",
            f"Confirm the daily schema watch for {url}:\n\n{site()}/api/confirm?token={row['token']}\n\n"
            f"The baseline is today's schema ({snap['hash'][:12]}, {len(snap['tools'])} tools). You will get "
            "one email when the live schema differs from it. If you did not ask for this, ignore this "
            "message and nothing more will be sent.\n\nSent by an automated service. Not affiliated with Google.\n",
            row["token"])
    return {"ok": True, "confirmed": bool(row["confirmed"])}


def confirm(db, token: str) -> bool:
    cur = db.execute("UPDATE watches SET confirmed=1 WHERE token=?", (token,))
    db.commit()
    return cur.rowcount == 1


def unsubscribe(db, token: str) -> bool:
    cur = db.execute("DELETE FROM watches WHERE token=?", (token,))
    db.commit()
    return cur.rowcount == 1


def run_watches(db, checker=preflight.check, guard=guard, mailer=None) -> dict:
    """One alert per new schema: mail when the hash differs from the last one seen."""
    sent = errors = 0
    for w in db.execute("SELECT * FROM watches WHERE confirmed=1").fetchall():
        try:
            guard(w["url"])
            snap = checker(w["url"])["snapshot"]
        except Exception:
            snap = None
        if not snap:
            errors += 1
            continue
        if snap["hash"] == w["last_hash"]:
            continue
        changes = preflight.diff(json.loads(w["baseline"]), snap)
        db.execute("UPDATE watches SET last_hash=? WHERE id=?", (snap["hash"], w["id"]))
        db.commit()
        if not changes:  # drifted and came back to the baseline
            continue
        (mailer or mail.send_mail)(
            w["email"], f"Schema drift on {urllib.parse.urlsplit(w['url']).hostname}",
            f"The live MCP schema at {w['url']} no longer matches the baseline you pinned.\n\n"
            + "\n".join("- " + c for c in changes) +
            "\n\nGoogle snapshots the tool list, arguments and server instructions at registration and says "
            "that changing the schema \"may break the integration and may cause the application to be "
            f"disabled\": {preflight.REF['standards']}\n\nIf the change is intended, ship it on a new versioned "
            f"endpoint and register a new app version, then start a new watch.\n\nStop this watch: "
            f"{site()}/api/unsubscribe?token={w['token']}\n", w["token"])
        sent += 1
    return {"alerts": sent, "unreachable": errors}


def stats(db) -> dict:
    one = lambda q: db.execute(q).fetchone()[0]
    return {"checks": one("SELECT COUNT(*) FROM checks"),
            "distinct_endpoints": one("SELECT COUNT(DISTINCT url_hash) FROM checks"),
            "watches_confirmed": one("SELECT COUNT(*) FROM watches WHERE confirmed=1"),
            "watches_pending": one("SELECT COUNT(*) FROM watches WHERE confirmed=0"),
            "want_paid": one("SELECT COUNT(*) FROM watches WHERE confirmed=1 AND wants_paid=1")}


class Handler(BaseHTTPRequestHandler):
    server_version = "ConnectedPreflight/1"

    def log_message(self, *a):
        pass

    def _send(self, code: int, obj) -> None:
        body = (obj if isinstance(obj, str) else json.dumps(obj)).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8" if isinstance(obj, str) else "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _ip(self) -> str:
        return (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[-1].strip()

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        db = connect()
        try:
            self._get(db, u, q)
        finally:
            db.close()

    def _get(self, db, u, q):
        if u.path == "/api/confirm":
            ok = confirm(db, q.get("token", ""))
            self._send(200 if ok else 404, "Watch confirmed. You will hear from us only if the schema changes."
                       if ok else "That link is not valid.")
        elif u.path == "/api/unsubscribe":
            unsubscribe(db, q.get("token", ""))
            self._send(200, "Watch removed. Your address has been deleted.")
        elif u.path == "/api/stats":
            key = os.environ.get("PREFLIGHT_ADMIN_KEY")
            if key and secrets.compare_digest(q.get("key", ""), key):
                self._send(200, stats(db))
            else:
                self._send(404, {"error": "not found"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        db = connect()
        try:
            self._post(db)
        finally:
            db.close()

    def _post(self, db):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/unsubscribe":  # one-click List-Unsubscribe
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
            unsubscribe(db, q.get("token", ""))
            return self._send(200, {"ok": True})
        if path not in ("/api/check", "/api/watch"):
            return self._send(404, {"error": "not found"})
        if not rate_ok(self._ip()):
            return self._send(429, {"error": "Too many requests from this address. Try again in an hour, or run the CLI."})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= MAX_BODY:
                raise ValueError
            data = json.loads(self.rfile.read(n))
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            return self._send(400, {"error": "Send a small JSON object."})
        try:
            if data.get("website"):  # honeypot field
                return self._send(200, {"ok": True})
            if path == "/api/check":
                report = run_check(db, str(data.get("url", "")))
                report.pop("snapshot", None)
                return self._send(200, report)
            self._send(200, add_watch(db, str(data.get("email", "")), str(data.get("url", "")),
                                      bool(data.get("wants_paid"))))
        except Rejected as e:
            self._send(400, {"error": str(e)})


def main(argv=None) -> int:
    cmd = (argv or sys.argv[1:] or ["serve"])[0]
    if cmd == "serve":
        ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PREFLIGHT_PORT", "8788"))), Handler).serve_forever()
    elif cmd == "run-watches":
        print(json.dumps(run_watches(connect())))
    elif cmd == "stats":
        print(json.dumps(stats(connect())))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
