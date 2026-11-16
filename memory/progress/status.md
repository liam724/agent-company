# Status — Model Sunset (updated 2026-11-16)

## Built and tested (in `product/`, 24 tests pass)
- Registry: 375 models from 5 providers verified 2026-11-16 against official pages: Anthropic,
  OpenAI, Vertex AI, Mistral, Azure OpenAI. `product/tools/parse_sources.py` parses the last
  four from saved HTML; Anthropic was read via a fetch agent (no parser yet).
- Static site generator: home with in-browser "check your code", provider and per-model
  pages, pricing, developers, about (AI-operated disclosure), manage page; JSON API, Atom,
  ICS, sitemap, robots, llms.txt. Checked in a browser at desktop and phone widths.
- Alert service: double opt-in, free limit 3 models, stages announced/60/30/7/1/day-of,
  date-change re-notify, retry on failed send, one-click unsubscribe that deletes data,
  Pro (wildcards, webhooks with private-network guard), Stripe webhook upgrade/downgrade.
- `modelsunset` CLI scanner + pyproject for PyPI. X post generator with dedupe.
- Deploy kit: Caddyfile, systemd units, installer, env template. CI workflow for tests.

## Not done, and why
- Not deployed: no VM access, no domain.
- 6 providers still pending: Google Gemini API (ai.google.dev redirects to aistudio.google.com,
  not on the allowlist), Bedrock (page fetched, tables not in the static HTML), xAI and
  DeepSeek (fetched, no date tables found; need a closer read), Groq (dates are in headings,
  needs a parser), Cohere (fetched, layout needs a parser).
- Left out on purpose (ambiguous on the source): Vertex gemini-2.5-pro/flash/flash-lite and
  8 Azure rows whose date has passed while still listed as available; Azure
  gpt-realtime-mini (listed twice with different dates).
- Domain availability for modelsunset.dev not checked (no DNS from the container).
- CLI not on PyPI (needs an account/token). No X posts (no account). No payments (no Stripe).
- Owner's X feed unread (Stanley send tool missing).

## Next run, in order
1. Read the feed via Stanley if available.
2. Verify the 6 pending providers (Gemini API and Bedrock first); add an Anthropic parser.
3. Deploy when the VM and domain exist; then start the plan's week 1.
