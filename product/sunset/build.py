"""Static site generator: python -m sunset.build [outdir]

Writes HTML pages, the JSON API, an Atom feed and ICS calendars. Standard library only.
Config comes from the environment: SITE_URL, CONTACT_EMAIL, STRIPE_PAYMENT_LINK, X_HANDLE.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import shutil
import sys
from html import escape as e

from . import events as ev
from . import registry

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
FREE_LIMIT = 3
PRICE = "$5/month"


def cfg():
    return {
        "site": os.environ.get("SITE_URL", "https://modelsunset.dev").rstrip("/"),
        "email": os.environ.get("CONTACT_EMAIL", ""),
        "pay": os.environ.get("STRIPE_PAYMENT_LINK", ""),
        "x": os.environ.get("X_HANDLE", ""),
    }


def page(c, title, desc, body, path="/"):
    x = f'<a href="https://x.com/{e(c["x"])}">X</a>' if c["x"] else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(c['site'] + path)}">
<link rel="alternate" type="application/atom+xml" title="Model Sunset events" href="/feed.xml">
<link rel="stylesheet" href="/style.css">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
</head><body>
<header><a class="brand" href="/"><span class="sun"></span>Model Sunset</a>
<nav><a href="/#upcoming">Retirements</a><a href="/alerts/">Alerts</a><a href="/developers/">API &amp; CLI</a><a href="/pricing/">Pricing</a><a href="/about/">About</a></nav></header>
<main>{body}</main>
<footer><p>Every date is read from the provider's own documentation and linked to it. Always confirm against the source before a migration.</p>
<p><a href="/feed.xml">Atom feed</a> <a href="/calendar.ics">Calendar</a> <a href="/api/v1/models.json">JSON</a> <a href="/about/">Operated by an AI agent</a> {x}</p></footer>
<script src="/check.js" defer></script>
</body></html>
"""


def badge(m):
    label = {"retiring": "retiring", "retired": "retired", "deprecated": "deprecated",
             "active": "active"}[m["status"]]
    return f'<span class="badge {label}">{label}</span>'


def when(m):
    if m["status"] == "retiring":
        d = m["days_left"]
        left = "tomorrow" if d == 1 else f"in {d} days"
        return f'<strong>{e(m["retires"])}</strong> <span class="muted">{left}</span>'
    if m["status"] == "retired":
        return e(m["retires"])
    if m.get("not_before"):
        return f'<span class="muted">not before {e(m["not_before"])}</span>'
    return '<span class="muted">no date published</span>'


def table(models, names, show_provider=True):
    rows = []
    for m in models:
        prov = f'<td><a href="/providers/{e(m["provider"])}/">{e(names[m["provider"]])}</a></td>' \
            if show_provider else ""
        rep = f'<code>{e(m["replacement"])}</code>' if m.get("replacement") else ""
        rows.append(f'<tr><td><a href="/models/{e(registry.path(m["key"]))}/"><code>{e(m["id"])}</code></a></td>'
                    f'{prov}<td>{badge(m)}</td><td>{when(m)}</td><td>{rep}</td></tr>')
    head = "<th>Provider</th>" if show_provider else ""
    return (f'<div class="scroll"><table><thead><tr><th>Model ID</th>{head}<th>Status</th>'
            f'<th>Retirement</th><th>Replacement</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def subscribe_form(preset=""):
    return f"""<form class="subscribe" method="post" action="/api/subscribe">
<label>Email <input type="email" name="email" required autocomplete="email" placeholder="you@company.com"></label>
<label>Models to watch <span class="muted">(comma-separated, e.g. anthropic/claude-sonnet-4-6)</span>
<input type="text" name="models" required value="{e(preset)}" list="model-keys" placeholder="provider/model-id"></label>
<input type="text" name="website" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">
<button type="submit">Email me before they retire</button>
<p class="muted small">Free for up to {FREE_LIMIT} models. We email you to confirm, then only when a watched model is deprecated, 60, 30, 7 and 1 days before retirement, and on the day. One-click unsubscribe.</p>
</form>"""


def build(out: pathlib.Path, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    c = cfg()
    reg = registry.load()
    models = registry.view(reg, today)
    names = {p["id"]: p["name"] for p in reg["providers"]}
    evs = ev.events(reg, today)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in STATIC.iterdir():
        shutil.copy(f, out / f.name)

    def write(rel, text):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    verified = [p for p in reg["providers"] if p.get("verified")]
    pending = [p for p in reg["providers"] if not p.get("verified")]
    retiring = [m for m in models if m["status"] == "retiring"]
    watch = [m for m in models if m["status"] in ("deprecated", "active")]
    retired = [m for m in models if m["status"] == "retired"]
    datalist = '<datalist id="model-keys">' + "".join(
        f'<option value="{e(m["key"])}">' for m in models if m["status"] != "retired") + "</datalist>"

    # ---- home
    cov = "".join(
        f'<li><a href="/providers/{e(p["id"])}/">{e(p["name"])}</a> '
        f'<span class="muted">verified {e(p["verified"])}</span></li>' for p in verified)
    cov += "".join(f'<li>{e(p["name"])} <span class="muted">pending verification</span></li>'
                   for p in pending)
    recent = "".join(f'<li><time>{e(x["date"])}</time> {e(x["text"])}</li>' for x in evs[:8])
    body = f"""
<section class="hero"><h1>Know before your model is retired.</h1>
<p class="lede">LLM providers retire models on 60 days' notice or less, and retired model IDs stop working.
Model Sunset tracks every published retirement date, links each one to the provider's own page, and warns you in time.</p>
<p class="muted">Updated {today.isoformat()}. {len(models)} models tracked across {len(verified)} verified provider{'s' if len(verified) != 1 else ''}; {len(retiring)} with a firm retirement date ahead.</p></section>

<section id="check"><h2>Check your code</h2>
<p>Paste code, config or a list of model IDs. Matching happens in your browser; nothing is uploaded.</p>
<textarea id="paste" rows="5" placeholder='model="claude-sonnet-4-5-20250929"' spellcheck="false"></textarea>
<div id="paste-result" aria-live="polite"></div></section>

<section id="upcoming"><h2>Retiring next</h2>
{table(retiring, names) if retiring else '<p>No firm retirement dates ahead.</p>'}
<h2>Deprecated or active</h2>
<p class="muted">"Not before" is the earliest date a provider has said a model could be retired. It is not a retirement date.</p>
{table(watch, names)}
<details><summary>Already retired ({len(retired)})</summary>{table(retired, names)}</details></section>

<section id="alerts"><h2>Get warned by email</h2>{subscribe_form()}{datalist}</section>

<section><h2>Coverage</h2><p>A provider is listed as verified only after its official page has been read and every date copied from it. We publish nothing from third-party trackers.</p>
<ul class="cov">{cov}</ul></section>

<section><h2>Recent events</h2><ul class="events">{recent}</ul>
<p><a href="/feed.xml">Subscribe to the Atom feed</a> or <a href="/calendar.ics">add the calendar</a>.</p></section>"""
    write("index.html", page(c, "Model Sunset: LLM model retirement dates and alerts",
                             "Verified retirement and deprecation dates for LLM API models, each linked to the provider's own page. Free alerts, JSON API, calendar and CLI.",
                             body))

    # ---- providers
    for p in verified:
        pm = [m for m in models if m["provider"] == p["id"]]
        note = f'<p class="note">{e(p["note"])}</p>' if p.get("note") else ""
        body = f"""<h1>{e(p["name"])} model retirement dates</h1>
<p>Source: <a href="{e(p["source_url"])}" rel="nofollow">{e(p["source_url"])}</a>. Last verified against the source on <strong>{e(p["verified"])}</strong>.</p>{note}
{table(pm, names, show_provider=False)}
<p>Machine-readable: <a href="/api/v1/providers/{e(p["id"])}.json">JSON</a> · <a href="/calendar/{e(p["id"])}.ics">calendar</a></p>
<h2>Watch all {e(p["name"])} models</h2>{subscribe_form(p["id"] + "/*")}{datalist}"""
        write(f"providers/{p['id']}/index.html",
              page(c, f"{p['name']} model deprecation and retirement dates",
                   f"Every published retirement date for {p['name']} models, verified {p['verified']} against the official documentation.",
                   body, f"/providers/{p['id']}/"))
        write(f"api/v1/providers/{p['id']}.json", json.dumps(
            {"generated": today.isoformat(), "provider": p, "models": pm}, indent=1))
        write(f"calendar/{p['id']}.ics", ics(pm, names, c, today))

    # ---- models
    provs = {p["id"]: p for p in reg["providers"]}
    for m in models:
        p = provs[m["provider"]]
        if m["status"] == "retiring":
            d = m["days_left"]
            head = f'{e(m["id"])} will be retired on {e(m["retires"])} ({"tomorrow" if d == 1 else f"in {d} days"}).'
        elif m["status"] == "retired":
            head = f'{e(m["id"])} was retired on {e(m["retires"])}.'
        elif m["status"] == "deprecated":
            head = f'{e(m["id"])} is deprecated. No retirement date has been published.'
        elif m.get("not_before"):
            head = f'{e(m["id"])} is active. {e(p["name"])} says it will not be retired before {e(m["not_before"])}.'
        else:
            head = f'{e(m["id"])} is active. No retirement date has been published.'
        facts = [("Provider", f'<a href="/providers/{e(p["id"])}/">{e(p["name"])}</a>'),
                 ("Status", badge(m)),
                 ("Deprecated on", e(m["deprecated"]) if m.get("deprecated") else "—"),
                 ("Retirement date", when(m)),
                 ("Recommended replacement", f'<code>{e(m["replacement"])}</code>' if m.get("replacement") else "—"),
                 ("Source", f'<a href="{e(p["source_url"])}" rel="nofollow">official page</a>, verified {e(p["verified"])}')]
        dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts)
        sub = "" if m["status"] == "retired" else \
            f'<h2>Get warned about this model</h2>{subscribe_form(m["key"])}'
        body = f"""<h1><code>{e(m["id"])}</code> retirement date</h1>
<p class="lede">{head}</p><dl class="facts">{dl}</dl>{sub}
<p><a href="/providers/{e(p["id"])}/">All {e(p["name"])} models</a></p>"""
        rel = registry.path(m["key"])
        write(f"models/{rel}/index.html",
              page(c, f"{m['id']} retirement date and deprecation status",
                   head.replace("&amp;", "&"), body, f"/models/{rel}/"))

    # ---- static-ish pages
    write("alerts/index.html", page(c, "Model retirement alerts by email — Model Sunset",
          "Email alerts before the LLM models you use are retired.",
          f"""<h1>Alerts</h1><p class="lede">Pick the models you depend on. You get an email when one is deprecated, then 60, 30, 7 and 1 days before it is retired, and on the day.</p>
{subscribe_form()}{datalist}
<h2>How it works</h2><ul><li>We send one confirmation email. Nothing else is sent until you click it.</li>
<li>Free covers {FREE_LIMIT} specific models. <a href="/pricing/">Pro</a> adds unlimited models, whole-provider watches such as <code>anthropic/*</code>, and webhooks.</li>
<li>We store your email address and your watch list, nothing more. Unsubscribing deletes both.</li></ul>""", "/alerts/"))

    buy = f'<a class="button" href="{e(c["pay"])}">Subscribe to Pro</a>' if c["pay"] else \
        '<p class="note">Pro is not on sale yet. Use the free tier now; your watch list carries over.</p>'
    write("pricing/index.html", page(c, "Pricing — Model Sunset", "Free registry, feeds, API and CLI. Pro alerts for teams.",
          f"""<h1>Pricing</h1><div class="plans"><div class="plan"><h2>Free</h2><p class="price">$0</p><ul>
<li>The full registry, with sources</li><li>JSON API, Atom feed, ICS calendars</li><li>CLI and CI scanner</li><li>Email alerts for up to {FREE_LIMIT} models</li></ul><a class="button ghost" href="/alerts/">Set up alerts</a></div>
<div class="plan"><h2>Pro</h2><p class="price">{PRICE}</p><ul><li>Unlimited watched models</li><li>Whole-provider watches (<code>openai/*</code>, <code>*</code>)</li>
<li>Webhook delivery (JSON; works with Slack incoming webhooks)</li><li>Cancel any time</li></ul>{buy}</div></div>""", "/pricing/"))

    site = c["site"]
    write("developers/index.html", page(c, "API, feeds and CLI — Model Sunset",
          "Free JSON API, Atom feed, ICS calendar and a CLI that fails your CI when your code references a retiring model.",
          f"""<h1>API, feeds and CLI</h1>
<h2>JSON</h2><p>Static files, rebuilt daily, no key, CORS open. Please cache for an hour.</p>
<pre><code>GET {site}/api/v1/models.json
GET {site}/api/v1/providers/anthropic.json
GET {site}/api/v1/events.json</code></pre>
<p>Each model has <code>provider</code>, <code>id</code>, <code>status</code> (<code>active</code>, <code>deprecated</code>, <code>retiring</code>, <code>retired</code>), <code>deprecated</code>, <code>retires</code>, <code>not_before</code>, <code>replacement</code> and <code>days_left</code>. <code>retires</code> is only ever a firm date from the provider.</p>
<h2>Feeds</h2><pre><code>{site}/feed.xml          Atom: deprecations, retirements, date changes
{site}/calendar.ics      every firm retirement date
{site}/calendar/anthropic.ics</code></pre>
<h2>CLI and CI</h2><p>Scans a directory for model IDs and fails when one is retired or retires soon. Python 3.9+, no dependencies.</p>
<pre><code>pipx run modelsunset scan . --fail-within 30</code></pre>
<p>GitHub Actions:</p>
<pre><code>- run: pipx run modelsunset scan . --fail-within 30</code></pre>
<p>The scanner reads the live registry, so it never goes stale between releases. Until the package is on PyPI, run it from <a href="/cli/modelsunset.py">a single file</a>: <code>python modelsunset.py scan .</code></p>""", "/developers/"))

    contact = f'<p>Contact: <a href="mailto:{e(c["email"])}">{e(c["email"])}</a></p>' if c["email"] else ""
    write("about/index.html", page(c, "About — Model Sunset", "How Model Sunset verifies dates, and who runs it.",
          f"""<h1>About</h1>
<h2>Operated by an AI agent</h2><p>Model Sunset is run day to day by an autonomous AI agent (Claude, made by Anthropic) on behalf of a human owner who is the legal entity behind it. The agent reads the provider pages, updates the registry, builds this site and writes the posts. We say so because you should know who you are trusting with a migration deadline.</p>
<h2>How dates are verified</h2><ul><li>Each provider's official deprecation page is re-read on a schedule and compared with the registry.</li>
<li>Dates are copied, never inferred. A provider we have not read yet is listed as pending, with no dates.</li>
<li>"Not sooner than" commitments are shown as earliest-possible dates and never counted down.</li>
<li>Each provider page shows the day it was last verified. Changes to a published date are recorded in the <a href="/feed.xml">feed</a>.</li></ul>
<h2>Limits</h2><p>Providers can change dates without notice, and cloud platforms often run on different schedules from the model maker. Check the linked source before you act. This site is not affiliated with any provider.</p>
<h2>Privacy</h2><p>No analytics scripts, no cookies. The alert service stores your email address and watch list until you unsubscribe.</p>{contact}""", "/about/"))
    write("manage/index.html", page(c, "Manage alerts — Model Sunset", "Change your watch list.",
          f"""<h1>Manage alerts</h1><p id="who" class="muted">Loading…</p>
<form id="manage" class="subscribe" hidden><label>Models to watch <span class="muted">(comma-separated)</span>
<input type="text" name="models" list="model-keys"></label>
<label id="hookrow" hidden>Webhook URL <span class="muted">(https; receives JSON with a Slack-compatible <code>text</code> field)</span>
<input type="text" name="webhook" placeholder="https://hooks.slack.com/services/..."></label>
<button type="submit">Save</button><p class="result muted" aria-live="polite"></p>
<p class="small"><a id="unsub" href="#">Unsubscribe and delete my data</a></p></form>{datalist}
<script src="/manage.js" defer></script>""", "/manage/"))
    for name, title, msg in (("confirmed", "You're subscribed", "Your alerts are on. You'll hear from us only when a watched model changes status or nears retirement."),
                             ("unsubscribed", "Unsubscribed", "Your email address and watch list have been deleted."),
                             ("check-email", "Check your email", "We sent a confirmation link. Alerts start once you click it.")):
        write(f"{name}/index.html", page(c, f"{title} — Model Sunset", msg,
                                         f"<h1>{title}</h1><p class='lede'>{msg}</p><p><a href='/'>Back to the registry</a></p>", f"/{name}/"))

    # ---- machine-readable
    write("api/v1/models.json", json.dumps(
        {"generated": today.isoformat(), "site": site, "providers": reg["providers"],
         "models": models}, indent=1))
    write("api/v1/events.json", json.dumps({"generated": today.isoformat(), "events": evs}, indent=1))
    write("feed.xml", atom(evs, c, today))
    write("calendar.ics", ics(models, names, c, today))
    write("cli/modelsunset.py", (ROOT / "sunset" / "scan.py").read_text())
    urls = ["/", "/alerts/", "/pricing/", "/developers/", "/about/"] + \
        [f"/providers/{p['id']}/" for p in verified] + \
        [f"/models/{registry.path(m['key'])}/" for m in models]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{e(site + u)}</loc></url>\n" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {site}/sitemap.xml\n")
    write("llms.txt", f"# Model Sunset\n\n> Verified retirement dates for LLM API models. Each date is copied from the provider's official page.\n\n"
          f"- [All models (JSON)]({site}/api/v1/models.json)\n- [Events (JSON)]({site}/api/v1/events.json)\n- [Atom feed]({site}/feed.xml)\n- [Calendar]({site}/calendar.ics)\n")
    return {"pages": len(urls), "models": len(models), "events": len(evs)}


def atom(evs, c, today):
    site = c["site"]
    entries = "".join(
        f"<entry><id>tag:modelsunset,2026:{e(x['id'])}</id><title>{e(x['title'])}</title>"
        f"<updated>{x['date']}T00:00:00Z</updated>"
        f"<link href=\"{e(site)}/models/{e(registry.path(x['key']))}/\"/>"
        f"<summary>{e(x['text'])}</summary></entry>\n" for x in evs[:60])
    updated = evs[0]["date"] if evs else today.isoformat()
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
            f"<title>Model Sunset</title><id>{e(site)}/</id><link href=\"{e(site)}/\"/>"
            f"<link rel=\"self\" href=\"{e(site)}/feed.xml\"/><updated>{updated}T00:00:00Z</updated>"
            f"<author><name>Model Sunset</name></author>\n{entries}</feed>\n")


def ics(models, names, c, today):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Model Sunset//EN",
             "X-WR-CALNAME:Model Sunset", "REFRESH-INTERVAL;VALUE=DURATION:PT12H"]
    for m in models:
        if not m.get("retires"):
            continue
        day = dt.date.fromisoformat(m["retires"])
        if (today - day).days > 90:
            continue
        desc = f"{names[m['provider']]} retires {m['id']} on {m['retires']}."
        if m.get("replacement"):
            desc += f" Replacement: {m['replacement']}."
        lines += ["BEGIN:VEVENT", f"UID:{m['key']}@modelsunset",
                  f"DTSTAMP:{today:%Y%m%d}T000000Z",
                  f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
                  f"DTEND;VALUE=DATE:{day + dt.timedelta(days=1):%Y%m%d}",
                  f"SUMMARY:{_ics(m['id'])} retires ({_ics(names[m['provider']])})",
                  f"DESCRIPTION:{_ics(desc)}",
                  f"URL:{c['site']}/models/{registry.path(m['key'])}/", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"


def _ics(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    parts = []
    while len(line.encode()) > 74:
        cut = 74
        while len(line[:cut].encode()) > 74:
            cut -= 1
        parts.append(line[:cut])
        line = " " + line[cut:]
    parts.append(line)
    return "\r\n".join(parts)


if __name__ == "__main__":
    target = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dist")
    print(json.dumps(build(target)))
