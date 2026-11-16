# Model Sunset

Verified retirement dates for LLM API models, with alerts. Python 3.9+, standard library only.

| Path | What |
|---|---|
| `data/registry.json` | The registry: providers (with official source URL and last-verified date) and models. The only hand-maintained data. |
| `sunset/registry.py` | Load, validate, apply a fresh provider snapshot and record changes. |
| `sunset/build.py` | Static site: pages, JSON API, Atom, ICS, sitemap. |
| `sunset/alerts.py`, `sunset/server.py` | Email/webhook alerts: double opt-in, SQLite, Stripe webhook for Pro. |
| `sunset/scan.py` | The `modelsunset` CLI (also served as a single file at `/cli/modelsunset.py`). |
| `sunset/social.py` | Today's posts for the company X account. |
| `tools/parse_sources.py` | Turns a saved official page into rows for `registry apply` (openai, vertex, mistral, azure). |
| `deploy/` | Caddy, systemd units, installer, env template. |

```
python3 -m unittest tests.test_all      # tests
python3 -m sunset.dev                   # local preview on :8000, mail goes to ./outbox
python3 -m sunset.build dist            # build the site
python3 -m sunset.registry apply <provider> rows.json   # apply a freshly read official page
python3 -m sunset.scan scan . --registry dist/api/v1/models.json
```

## Data rules

1. A date enters the registry only if it was read on the provider's own page that day.
2. `retires` is a firm date. "Not sooner than" commitments go in `not_before`.
3. A row whose meaning is unclear on the source is left out, not interpreted.
4. A provider without a `verified` date cannot have models (validation fails).

`rows.json` for `apply` is a list of
`{"id", "state": active|deprecated|retired, "deprecated", "retires", "not_before", "replacement"}`.
