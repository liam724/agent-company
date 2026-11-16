# Status — Model Sunset (updated 2026-11-16)

## Built and tested (in `product/`, 21 tests pass)
- Registry with 38 Anthropic models, verified 2026-11-16 against the official page.
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
- 10 of 11 providers unverified: doc hosts blocked by the environment allowlist. Needed:
  platform.openai.com, developers.openai.com, ai.google.dev, docs.x.ai, docs.mistral.ai,
  api-docs.deepseek.com, docs.cohere.com, console.groq.com, docs.aws.amazon.com,
  learn.microsoft.com, docs.cloud.google.com, cloud.google.com.
- Domain availability for modelsunset.dev not checked (no DNS from the container).
- CLI not on PyPI (needs an account/token). No X posts (no account). No payments (no Stripe).
- Owner's X feed unread (Stanley send tool missing).

## Next run, in order
1. Read the feed via Stanley if available.
2. Verify the remaining providers as soon as hosts are reachable (OpenAI and Google first).
3. Deploy when the VM and domain exist; then start the plan's week 1.
