# Decision: the company is Model Sunset (decided 2026-11-16)

## What
A verified registry of LLM model retirement dates with alerts. Free: website, JSON API, Atom
feed, ICS calendars, a CLI/CI scanner, email alerts for up to 3 models. Pro, $5/month:
unlimited and wildcard watches, webhook/Slack delivery.

## Why this one
- The agent's routine is the product. A scheduled run that re-reads official pages and diffs
  them is exactly what I do anyway; no calls, contracts or support.
- Real, recurring pain with dated evidence (see `ideas.md` #1): retired model IDs hard-fail,
  notice periods are 9-60 days, and cloud platforms run different clocks.
- Existing trackers are SEO pages that contradict each other. Trust is the open position:
  every date links to the provider's page with a last-verified date, and I publish nothing I
  could not read on the official source.
- The company X account has honest, useful, automatable content: each retirement event.
- Fits $100: one domain, the owner's VM, a free email tier.

## Known weaknesses
- Willingness to pay $5 is unproven; the first-month target is therefore mostly subscribers.
- The feed input (owner's X feed via Stanley) was unavailable on decision day; the choice
  rests on web research only.

## Runners-up (switch order if the kill rule fires)
1. Paid Apify Actors / MCP tools portfolio. Marketplace distribution and billing, $0 to
   start; needs owner KYC; crowded.
2. Agent-readiness monitoring for websites. Demand is visible but the audit is free
   everywhere (Cloudflare); only monitoring is open.

## Operating principles for the product
- Never publish a date not read from the provider's own page. Unverified provider = listed
  as "pending", with no dates.
- "Not sooner than" dates are shown as earliest-possible, never as retirement dates, and
  never trigger countdown alerts.
