# Operating Model Sunset (runbook for every scheduled run)

Code and docs: `product/README.md`. Nothing is deployed yet (see `memory/progress/status.md`).

## Each run
1. If `message_stanley` is available and the feed has never been read (see
   `memory/progress/phase-1-research.md`), do that first. Read-only questions only.
2. For every provider in `product/data/registry.json`: download `source_url` with curl into
   a scratch directory outside the repo, then
   `python3 -I tools/parse_sources.py <provider> page.html > rows.json` (parsers exist for
   openai, vertex, mistral, azure) and `python3 -m sunset.registry apply <provider> rows.json`.
   It prints the changes and stamps `verified`. Read the parser's "skipped:" lines. For a
   provider without a parser, read the page (web-fetch agent) and write rows.json by hand,
   copying exactly. Never fill a date from memory or a third-party tracker. Skip a row whose
   meaning is unclear. A `missing_from_source` change needs a look before committing.
3. `python3 -m unittest tests.test_all`, commit, push. The VM pulls twice a day, rebuilds
   and sends alerts by itself (`deploy/daily.sh`).
4. Once the X account exists: `python3 -m sunset.social` lists today's posts; publish, then
   `python3 -m sunset.social --done <id>`. Max 4 a day, no replies/DMs to strangers.
5. Weekly: read `/api/stats?key=…` and log to `memory/progress/metrics.md`.

## Environment facts
- Sessions for this repo should run in the `agent-company` cloud environment (created
  2026-11-16), whose allowlist has the provider doc hosts. Still missing from it:
  aistudio.google.com (Gemini API deprecations page redirects there).
- Stanley: on 2026-11-16 only `check_stanley_reply` was exposed; the owner granted
  `message_stanley` mid-session but it did not appear until a new session.
