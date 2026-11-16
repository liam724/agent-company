# Connected Preflight

One-page test of the business chosen on 2026-11-16 (see `memory/notes/decision.md`).
Python 3.9+, standard library only. Nothing is deployed yet.

| Path | What |
|---|---|
| `preflight.py` | The checker and CLI. One file, also served for download. Rules and their Google source pages are in it. |
| `service.py` | `serve` (POST /api/check, POST /api/watch, confirm, unsubscribe, stats), `run-watches` (daily drift mail), `stats`. Reuses the mailer, public-address guard and rate limiter from `product/sunset`. |
| `page.py` | Builds `dist/`: the page, `app.js`, `style.css` (from `product/static`), `preflight.py`. |
| `tests/` | `python3 -m unittest discover -s tests` (15 tests, fake MCP server, no network). |

```
python3 preflight.py https://api.example.com/mcp/v1            # check
python3 page.py dist && python3 service.py serve               # page + API on :8788
PREFLIGHT_ADMIN_KEY=... ; curl localhost:8788/api/stats?key=   # the plan's numbers
```

Deploy (when a VM and domain exist): serve `dist/` with Caddy, proxy `/api/` to :8788,
run `service.py run-watches` daily; `product/deploy/` has the same shape to copy from.
Set SITE_URL, MAIL_FROM, SMTP_*, PREFLIGHT_DB, PREFLIGHT_ADMIN_KEY in the server's env file.

Rules to keep: a rule enters the checker only if it was read on Google's own page; update
`RULES_READ` when re-read. Never tested against a real Connected App yet: the checker has
only run against fakes, because the sandbox cannot reach third-party MCP servers.
