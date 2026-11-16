"""Build the one-page test: python3 page.py [outdir]   (default ./dist)

Writes index.html, style.css (shared with product/static), app.js and the downloadable
preflight.py. Environment: SITE_URL, CONTACT_EMAIL, STRIPE_PAYMENT_LINK (button stays off without it).
"""
from __future__ import annotations

import html
import os
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preflight  # noqa: E402

e = html.escape
PRICE = "$9/month"

RULES = [
    ("Transport", "Streamable HTTP on one HTTPS endpoint. The legacy HTTP+SSE transport is refused.", "standards"),
    ("Protocol version", f"Nothing newer than MCP {preflight.LATEST}; newer spec releases are not supported yet.", "standards"),
    ("Static tools", "No list_tools, get_schema, execute_command or other dynamic dispatchers. Policy bans them.", "policy"),
    ("Safety annotations", "readOnlyHint or destructiveHint on every tool; destructiveHint: true on anything that deletes, pays or revokes.", "policy"),
    ("Descriptions and parameters", "Every tool and parameter typed and described; no multi-action tools; IDs as strings.", "standards"),
    ("Server instructions", "Present, because Google routes on them and snapshots them.", "standards"),
    ("Domain file", "/.well-known/google-connected-apps answers 200 with no redirect.", "prereq"),
    ("OAuth discovery", "Protected-resource and authorization-server metadata with the fields Google requires.", "oauth"),
]

JS = r"""
const $ = (s) => document.querySelector(s);
async function post(path, body) {
  const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  return [r.ok, await r.json().catch(() => ({error: 'The service did not answer. Use the CLI below.'}))];
}
$('#check').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const out = $('#result'); out.textContent = 'Checking…';
  const url = $('#check [name=url]').value;
  const [ok, d] = await post('/api/check', {url}).catch(() => [false, {error: 'The service did not answer. Use the CLI below.'}]);
  out.textContent = '';
  if (!ok) { const p = document.createElement('p'); p.className = 'note'; p.textContent = d.error; out.append(p); return; }
  const s = d.summary, h = document.createElement('p');
  h.innerHTML = '<strong></strong>'; h.firstChild.textContent = `${s.fail} failed, ${s.warn} warnings, ${s.pass} passed.`;
  out.append(h);
  for (const lvl of ['fail', 'warn', 'info', 'pass']) for (const f of d.findings.filter((f) => f.level === lvl)) {
    const row = document.createElement('div'); row.className = 'hit';
    const b = document.createElement('span'); b.className = 'badge ' + ({fail: 'retired', warn: 'retiring', info: 'deprecated', pass: 'active'})[lvl]; b.textContent = lvl;
    const t = document.createElement('strong'); t.textContent = ' ' + f.title;
    row.append(b, t);
    if (f.detail) { const p = document.createElement('div'); p.className = 'muted small'; p.textContent = f.detail; row.append(p); }
    if (f.ref && lvl !== 'pass') { const a = document.createElement('a'); a.className = 'small'; a.href = f.ref; a.textContent = "Google's rule"; row.append(a); }
    out.append(row);
  }
  $('#watch [name=url]').value = url;
});
$('#watch').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const f = ev.target, msg = $('#watch-msg');
  const [ok, d] = await post('/api/watch', {email: f.email.value, url: f.url.value, wants_paid: f.wants_paid.checked, website: f.website.value})
    .catch(() => [false, {error: 'The service did not answer. Try again later.'}]);
  msg.className = ok ? '' : 'note';
  msg.textContent = ok ? 'Check your inbox and confirm. Nothing is watched until you do.' : d.error;
});
"""


def build(out: pathlib.Path) -> pathlib.Path:
    site = os.environ.get("SITE_URL", "https://connectedpreflight.com").rstrip("/")
    contact = os.environ.get("CONTACT_EMAIL", "")
    pay = os.environ.get("STRIPE_PAYMENT_LINK", "")
    rules = "".join(
        f'<li><strong>{e(t)}.</strong> {e(d)} <a class="small" href="{e(preflight.REF[r])}">source</a></li>'
        for t, d, r in RULES)
    paid = (f'<p><a class="button" href="{e(pay)}">Start Team</a></p>' if pay else
            '<p class="muted small">Not on sale yet. Tick the box in the watch form and you will get one email when it is.</p>')
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connected Preflight — check your MCP server against Google's Connected Apps rules</title>
<meta name="description" content="Free check of a live MCP endpoint against Google's published Connected Apps standards and policy, and a daily watch that warns you when the schema drifts from what you registered.">
<link rel="canonical" href="{e(site)}/">
<link rel="stylesheet" href="/style.css">
</head><body>
<header><a class="brand" href="/"><span class="sun"></span>Connected Preflight</a>
<nav><a href="#rules">Rules</a><a href="#watch-h">Watch</a><a href="#cli">CLI</a><a href="#about">About</a></nav></header>
<main>
<section>
<h1>Will Google accept your MCP server, and will it stay accepted?</h1>
<p class="lede">Google's Connected Apps Platform snapshots your tool list, arguments and server instructions when you register. Its documentation says a later schema change <q>may break the integration and may cause the application to be disabled</q>. Connected Preflight tests a live endpoint against Google's published rules, then watches it for drift.</p>
<form id="check" class="subscribe">
<label>MCP endpoint <input type="text" name="url" placeholder="https://api.example.com/mcp/v1" required></label>
<button>Run the check</button>
<p class="muted small">Public https endpoints only. We store a hash of the URL to count checks, not the URL or the result.</p>
</form>
<div id="result" aria-live="polite"></div>
</section>
<section><h2 id="rules">What is checked</h2>
<p class="muted">Each rule was read on Google's developer site on {e(preflight.RULES_READ)} and every finding links to its page.</p>
<ul class="cov">{rules}</ul></section>
<section><h2 id="watch-h">Watch for drift</h2>
<p>We pin today's schema as the baseline, re-read the endpoint daily, and email you once when the tool list, arguments or server instructions differ.</p>
<form id="watch" class="subscribe">
<label>MCP endpoint <input type="text" name="url" required></label>
<label>Email <input type="email" name="email" required></label>
<label class="hp">Website <input type="text" name="website" tabindex="-1" autocomplete="off"></label>
<label style="font-weight:400;display:flex;gap:8px;align-items:center"><input type="checkbox" name="wants_paid"> I would pay {PRICE} for 10 endpoints, hourly checks and a webhook</label>
<button>Start the free watch</button>
<p id="watch-msg" class="small"></p>
</form>
<div class="plans" style="margin-top:16px">
<div class="plan"><h2>Free</h2><p class="price">$0</p><p>One endpoint, checked daily, email alert. Unlimited one-off checks and the CLI.</p></div>
<div class="plan"><h2>Team</h2><p class="price">{PRICE}</p><p>Ten endpoints, hourly checks, webhook alerts.</p>{paid}</div>
</div></section>
<section><h2 id="cli">Run it yourself</h2>
<p>One Python file, standard library only. It also works on servers behind authorization and in CI.</p>
<pre>curl -O {e(site)}/preflight.py
python3 preflight.py https://api.example.com/mcp/v1 --save registered.json
python3 preflight.py https://api.example.com/mcp/v1 --against registered.json   # exit 1 on drift</pre></section>
<section><h2 id="about">About</h2>
<p>Connected Preflight is an independent tool and is not affiliated with or endorsed by Google. It checks only what can be tested from outside: it cannot see your Connected Console settings, and passing does not mean Google will approve your app. It is built and operated by an AI agent on behalf of its owner.{f' Contact: <a href="mailto:{e(contact)}">{e(contact)}</a>.' if contact else ''}</p></section>
</main>
<footer><p>Rules source: <a href="{e(preflight.DOCS)}">developers.google.com/connected-apps</a>. Google and Gemini are trademarks of Google LLC.</p></footer>
<script src="/app.js" defer></script>
</body></html>
"""
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(body)
    (out / "app.js").write_text(JS.strip() + "\n")
    shutil.copy(HERE.parent / "product" / "static" / "style.css", out / "style.css")
    shutil.copy(HERE / "preflight.py", out / "preflight.py")
    return out


if __name__ == "__main__":
    print(build(pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "dist")))
