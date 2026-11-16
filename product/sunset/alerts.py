"""Alert subscriptions and delivery. SQLite + standard library only.

Environment:
  SUNSET_DB        path of the SQLite file (default ./alerts.db)
  SITE_URL         public site URL used in links
  SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASS, MAIL_FROM   outgoing mail
  SUNSET_OUTBOX    directory to write .eml files to when SMTP_HOST is unset (dev / dry run)
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import ipaddress
import json
import os
import pathlib
import re
import secrets
import smtplib
import socket
import sqlite3
import urllib.parse
import urllib.request
from email.message import EmailMessage

from . import registry

FREE_LIMIT = 3
PRO_LIMIT = 500
LEADS = (60, 30, 7, 1, 0)
GRACE_DAYS = 3  # still send the "retired" notice if a daily run was missed
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?\.[A-Za-z]{2,}$")
SELECTOR_RE = re.compile(r"^[A-Za-z0-9*][A-Za-z0-9._:@/*-]{0,199}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers(
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, token TEXT UNIQUE NOT NULL,
  confirmed INTEGER NOT NULL DEFAULT 0, plan TEXT NOT NULL DEFAULT 'free',
  webhook TEXT, stripe_customer TEXT, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS watches(
  sub_id INTEGER NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
  selector TEXT NOT NULL, PRIMARY KEY(sub_id, selector));
CREATE TABLE IF NOT EXISTS sent(
  sub_id INTEGER NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
  key TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY(sub_id, key));
"""


class Rejected(ValueError):
    """A request the user can fix; the message is shown to them."""


def site() -> str:
    return os.environ.get("SITE_URL", "https://modelsunset.dev").rstrip("/")


def connect(path: str | None = None) -> sqlite3.Connection:
    db = sqlite3.connect(path or os.environ.get("SUNSET_DB", "alerts.db"), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    return db


# ---------------------------------------------------------------- subscriptions

def parse_selectors(raw) -> list[str]:
    items = raw if isinstance(raw, list) else re.split(r"[,\s]+", str(raw or ""))
    out = []
    for s in items:
        s = str(s).strip()
        if s and s not in out:
            out.append(s)
    return out


def check_selectors(selectors: list[str], reg: dict, plan: str) -> None:
    if not selectors:
        raise Rejected("Add at least one model to watch, like anthropic/claude-sonnet-4-6.")
    keys = {registry.key(m) for m in reg["models"]}
    providers = {p["id"] for p in reg["providers"]}
    for s in selectors:
        if not SELECTOR_RE.match(s):
            raise Rejected(f"'{s[:60]}' is not a valid model. Use provider/model-id.")
        if "*" in s:
            if plan != "pro":
                raise Rejected("Whole-provider watches like anthropic/* are a Pro feature. "
                               "List specific models, or see the pricing page.")
            if s != "*" and s.split("/")[0] not in providers | {"*"}:
                raise Rejected(f"Unknown provider in '{s}'.")
        elif s not in keys:
            raise Rejected(f"We don't track '{s}' yet. Check the spelling against the registry; "
                           "IDs look like anthropic/claude-sonnet-4-6.")
    limit = PRO_LIMIT if plan == "pro" else FREE_LIMIT
    if len(selectors) > limit:
        raise Rejected(f"The free plan covers {FREE_LIMIT} models. Remove some, or see the pricing page."
                       if plan != "pro" else f"At most {PRO_LIMIT} watches.")


def subscribe(db, email: str, raw_selectors, reg: dict, mailer=None) -> dict:
    """Create or extend a subscription. Sends the confirmation mail when still unconfirmed."""
    email = (email or "").strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise Rejected("That email address doesn't look right.")
    selectors = parse_selectors(raw_selectors)
    row = db.execute("SELECT * FROM subscribers WHERE email=?", (email,)).fetchone()
    plan = row["plan"] if row else "free"
    existing = [r["selector"] for r in db.execute(
        "SELECT selector FROM watches WHERE sub_id=?", (row["id"],))] if row else []
    merged = existing + [s for s in selectors if s not in existing]
    check_selectors(merged, reg, plan)
    if not row:
        token = secrets.token_urlsafe(24)
        cur = db.execute("INSERT INTO subscribers(email, token, created) VALUES(?,?,?)",
                         (email, token, dt.datetime.now(dt.timezone.utc).isoformat()))
        sub_id, confirmed = cur.lastrowid, 0
    else:
        sub_id, token, confirmed = row["id"], row["token"], row["confirmed"]
    db.executemany("INSERT OR IGNORE INTO watches VALUES(?,?)", [(sub_id, s) for s in merged])
    db.commit()
    if not confirmed:
        link = f"{site()}/api/confirm?token={token}"
        body = (f"Confirm your Model Sunset alerts for:\n\n  " + "\n  ".join(merged) +
                f"\n\nConfirm: {link}\n\nIf you didn't ask for this, ignore this email and "
                "nothing more will be sent.\n")
        (mailer or send_mail)(email, "Confirm your Model Sunset alerts", body, token)
    return {"token": token, "confirmed": bool(confirmed), "watches": merged}


def confirm(db, token: str) -> bool:
    cur = db.execute("UPDATE subscribers SET confirmed=1 WHERE token=?", (token,))
    db.commit()
    return cur.rowcount == 1


def unsubscribe(db, token: str) -> bool:
    cur = db.execute("DELETE FROM subscribers WHERE token=?", (token,))
    db.commit()
    return cur.rowcount == 1


def me(db, token: str) -> dict | None:
    row = db.execute("SELECT * FROM subscribers WHERE token=?", (token,)).fetchone()
    if not row:
        return None
    return {"email": row["email"], "plan": row["plan"], "confirmed": bool(row["confirmed"]),
            "webhook": row["webhook"],
            "watches": [r["selector"] for r in db.execute(
                "SELECT selector FROM watches WHERE sub_id=? ORDER BY selector", (row["id"],))]}


def manage(db, token: str, raw_selectors, webhook: str | None, reg: dict) -> dict:
    row = db.execute("SELECT * FROM subscribers WHERE token=?", (token,)).fetchone()
    if not row:
        raise Rejected("That link is no longer valid.")
    selectors = parse_selectors(raw_selectors)
    check_selectors(selectors, reg, row["plan"])
    webhook = (webhook or "").strip() or None
    if webhook:
        if row["plan"] != "pro":
            raise Rejected("Webhooks are a Pro feature.")
        check_webhook_url(webhook)
    db.execute("DELETE FROM watches WHERE sub_id=?", (row["id"],))
    db.executemany("INSERT INTO watches VALUES(?,?)", [(row["id"], s) for s in selectors])
    db.execute("UPDATE subscribers SET webhook=? WHERE id=?", (webhook, row["id"]))
    db.commit()
    return me(db, token)


def set_plan(db, email: str, plan: str, stripe_customer: str | None = None) -> str:
    """Called from the payment webhook. Creates a confirmed subscriber if needed. Returns token."""
    email = email.strip().lower()
    row = db.execute("SELECT * FROM subscribers WHERE email=?", (email,)).fetchone()
    if row:
        db.execute("UPDATE subscribers SET plan=?, confirmed=1, "
                   "stripe_customer=COALESCE(?, stripe_customer) WHERE id=?",
                   (plan, stripe_customer, row["id"]))
        token = row["token"]
    else:
        token = secrets.token_urlsafe(24)
        db.execute("INSERT INTO subscribers(email, token, confirmed, plan, stripe_customer, created)"
                   " VALUES(?,?,1,?,?,?)", (email, token, plan, stripe_customer,
                                            dt.datetime.now(dt.timezone.utc).isoformat()))
    db.commit()
    return token


def downgrade_customer(db, stripe_customer: str) -> int:
    """Subscription ended: back to free. Wildcards and extra watches stop matching; webhook off."""
    rows = db.execute("SELECT id FROM subscribers WHERE stripe_customer=?", (stripe_customer,)).fetchall()
    for r in rows:
        db.execute("UPDATE subscribers SET plan='free', webhook=NULL WHERE id=?", (r["id"],))
    db.commit()
    return len(rows)


def stats(db) -> dict:
    one = lambda q: db.execute(q).fetchone()[0]
    return {"confirmed": one("SELECT COUNT(*) FROM subscribers WHERE confirmed=1"),
            "unconfirmed": one("SELECT COUNT(*) FROM subscribers WHERE confirmed=0"),
            "pro": one("SELECT COUNT(*) FROM subscribers WHERE plan='pro'"),
            "watches": one("SELECT COUNT(*) FROM watches"),
            "notifications_sent": one("SELECT COUNT(*) FROM sent")}


# ---------------------------------------------------------------- notifications

def stage(m: dict):
    """Which notice a model is due right now: (stage_key, subject, sentence) or None."""
    if m["status"] == "deprecated":
        return ("deprecated", f"{m['id']} has been deprecated",
                f"{m['id']} is deprecated. No retirement date has been published yet; "
                "we'll tell you when one is.")
    if m["status"] == "retiring":
        d = m["days_left"]
        due = [lead for lead in LEADS if d <= lead]
        if not due:
            return (f"{m['retires']}|announced", f"{m['id']} will be retired on {m['retires']}",
                    f"{m['id']} is scheduled for retirement on {m['retires']}, {d} days from now.")
        when = "tomorrow" if d == 1 else f"in {d} days"
        return (f"{m['retires']}|{min(due)}", f"{m['id']} retires {when}",
                f"{m['id']} will be retired {when}, on {m['retires']}.")
    if m["status"] == "retired" and -GRACE_DAYS <= m["days_left"] <= 0:
        return (f"{m['retires']}|0", f"{m['id']} has been retired",
                f"{m['id']} was retired on {m['retires']}. Requests using this model ID "
                "will fail or be served by a different model.")
    return None


def effective_watches(sub: sqlite3.Row, selectors: list[str]) -> list[str]:
    """What a subscriber's plan actually covers (matters after a downgrade)."""
    if sub["plan"] == "pro":
        return selectors
    return [s for s in sorted(selectors) if "*" not in s][:FREE_LIMIT]


def pending(db, reg: dict, today: dt.date) -> list[dict]:
    """Notifications that should go out now and have not been sent."""
    models = registry.view(reg, today)
    provs = {p["id"]: p for p in reg["providers"]}
    out = []
    for sub in db.execute("SELECT * FROM subscribers WHERE confirmed=1").fetchall():
        selectors = [r["selector"] for r in db.execute(
            "SELECT selector FROM watches WHERE sub_id=?", (sub["id"],))]
        selectors = effective_watches(sub, selectors)
        sent = {r["key"] for r in db.execute("SELECT key FROM sent WHERE sub_id=?", (sub["id"],))}
        for m in models:
            if not any(fnmatch.fnmatchcase(m["key"], s) for s in selectors):
                continue
            st = stage(m)
            if not st:
                continue
            key = f"{m['key']}|{st[0]}"
            if key in sent:
                continue
            out.append({"sub": sub, "model": m, "provider": provs[m["provider"]], "key": key,
                        "subject": st[1], "sentence": st[2]})
    return out


def notify(db, reg: dict, today: dt.date, mailer=None, poster=None) -> dict:
    """Send everything pending. A failed delivery is retried on the next run."""
    mailer, poster = mailer or send_mail, poster or post_webhook
    counts = {"email": 0, "webhook": 0, "failed": 0}
    for n in pending(db, reg, today):
        sub, m, p = n["sub"], n["model"], n["provider"]
        page = f"{site()}/models/{registry.path(m['key'])}/"
        lines = [n["sentence"], ""]
        if m.get("replacement"):
            lines.append(f"Recommended replacement: {m['replacement']}")
        lines += [f"Provider: {p['name']}", f"Official source: {p['source_url']}",
                  f"(verified {p['verified']})", f"Details: {page}", "",
                  "Dates can change. Check the official source before you migrate.", "",
                  f"Manage your watch list: {site()}/manage/?token={sub['token']}",
                  f"Unsubscribe: {site()}/api/unsubscribe?token={sub['token']}"]
        try:
            mailer(sub["email"], n["subject"], "\n".join(lines) + "\n", sub["token"])
            counts["email"] += 1
            if sub["webhook"] and sub["plan"] == "pro":
                try:
                    poster(sub["webhook"], {
                        "text": f"{n['sentence']} {page}", "event": n["key"].rsplit("|", 1)[-1],
                        "provider": m["provider"], "model": m["id"], "status": m["status"],
                        "retires": m.get("retires"), "days_left": m.get("days_left"),
                        "replacement": m.get("replacement"), "source": p["source_url"]})
                    counts["webhook"] += 1
                except Exception:
                    counts["failed"] += 1  # the email went out; do not resend it for a bad hook
        except Exception:
            counts["failed"] += 1
            continue
        db.execute("INSERT OR IGNORE INTO sent VALUES(?,?,?)",
                   (sub["id"], n["key"], dt.datetime.now(dt.timezone.utc).isoformat()))
        db.commit()
    return counts


# ---------------------------------------------------------------- delivery

def send_mail(to: str, subject: str, body: str, token: str) -> None:
    msg = EmailMessage()
    msg["From"] = os.environ.get("MAIL_FROM", "Model Sunset <alerts@modelsunset.dev>")
    msg["To"] = to
    msg["Subject"] = subject
    msg["List-Unsubscribe"] = f"<{site()}/api/unsubscribe?token={token}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["Auto-Submitted"] = "auto-generated"
    # Keep long links on one unencoded line when the body is plain ASCII.
    msg.set_content(body, cte="7bit" if body.isascii() else None)
    host = os.environ.get("SMTP_HOST")
    if not host:
        outbox = pathlib.Path(os.environ.get("SUNSET_OUTBOX", "outbox"))
        outbox.mkdir(parents=True, exist_ok=True)
        (outbox / f"{dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}-{secrets.token_hex(3)}.eml"
         ).write_bytes(bytes(msg))
        return
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=30) as s:
        s.starttls()
        if os.environ.get("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
        s.send_message(msg)


def check_webhook_url(url: str) -> None:
    """Only public https endpoints: the server must not be usable to probe private networks."""
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or not u.hostname or len(url) > 500 or u.username:
        raise Rejected("The webhook must be an https:// URL.")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or 443, proto=socket.IPPROTO_TCP)
    except OSError:
        raise Rejected("The webhook host could not be resolved.")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise Rejected("The webhook must point to a public address.")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def post_webhook(url: str, payload: dict) -> None:
    check_webhook_url(url)  # re-checked at send time; DNS can change after it was saved
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "ModelSunset-Webhook/1"})
    urllib.request.build_opener(_NoRedirect).open(req, timeout=10).close()


def main(argv=None):
    """python -m sunset.alerts notify | stats"""
    import sys
    argv = argv or sys.argv[1:]
    db = connect()
    if argv[:1] == ["notify"]:
        print(json.dumps(notify(db, registry.load(), dt.date.today())))
    elif argv[:1] == ["stats"]:
        print(json.dumps(stats(db)))
    else:
        sys.exit(main.__doc__)


if __name__ == "__main__":
    main()
