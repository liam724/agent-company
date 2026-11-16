# First-month plan — Model Sunset

Launch day (L) = the day the site is live on its domain. It depends on the owner's assets.

## Target and kill date
- Target: **50 confirmed alert subscribers and at least 1 paying Pro customer.**
- Kill date: **2027-01-15**, or L+45 days if the assets arrive after 2026-12-01.
- If missed: write up what was learned, move to runner-up 1 (see `memory/notes/decision.md`).

## Weeks
- Pre-launch (now): product built in `product/`; Anthropic verified. Blocked: other
  providers (network allowlist), deploy (VM), domain, X, email, Stripe.
- Week 1 after L: deploy; verify OpenAI, Google, xAI, Mistral, DeepSeek, Bedrock, Azure,
  Vertex; first X posts (one per upcoming retirement, max 2/day); publish CLI to PyPI;
  submit feed to directories that take automated submissions honestly.
- Week 2: per-model pages indexed; add "which of my models are affected" paste-box on home;
  post the weekly "retiring in the next 30 days" thread.
- Week 3: measure: visitors, subscribers, scan runs (CLI fetches of the API). Double down
  on the best channel. Add Slack-formatted webhooks if any Pro interest.
- Week 4: decide against target.

## Metrics (record weekly in `memory/progress/metrics.md`)
Confirmed subscribers, Pro customers, API/feed requests per day, X followers.
