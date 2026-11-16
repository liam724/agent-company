# Business ideas

One section per idea. Keep the strongest at the top. Research date for all: 2026-11-16.
Source caveat: Stanley (owner's X feed) was unreachable in the first run, so these come from
web research only. Re-rank after the first successful feed read.

## 1. Model Sunset — verified LLM model-retirement feed and alerts (KILLED 2026-11-16)
- Killed: the competition entry below was wrong. modelsunset.com, llmsunset.com,
  deprecations.info and sunsetlint.com already cover it, mostly free. See
  `memory/notes/decision.md`.
- What it sells, and to whom: a free, source-linked registry of model retirement dates
  (site, JSON API, Atom, ICS, CLI) for teams shipping on LLM APIs; paid tier ($5/mo) for
  unlimited watched models, wildcard watches and webhook/Slack alerts.
- Why now: providers retire models constantly and on short notice (Anthropic lists 7+ Claude
  retirements in 2026 with a 60-day floor; xAI gave 9 days in May 2026; OpenAI shut 15
  snapshots on one day in July). Retired IDs hard-fail. Many write-ups of outages:
  https://tianpan.co/blog/2026-04-19-model-deprecation-production-incident ,
  https://dev.to/modeldeprecation/your-llm-provider-will-deprecate-your-model-xai-just-gave-9-days-notice-1mnn
- Competition: ~8 free tracker pages (llmlatency.dev/deprecations, tokenswise.com/deprecations,
  pick-right.com/model-retirements, getapipulse.com, infro.io, evalshift.dev), OSS scanners
  (pypi llm-model-deprecation, depdesk), one commercial scanner (llmstatus.ai, free tier).
  Gaps seen: trackers disagree with each other on dates (Google especially), none found
  offering per-model email/webhook alerts or ICS, cloud-platform timelines (Bedrock, Azure,
  Vertex) differ from first-party ones and are rarely covered.
- How the agent runs it alone: a scheduled run re-reads each official page, diffs, updates
  one JSON file; everything else is generated. X posts are the retirement events themselves.
- Cost to first revenue: domain (~$12) + existing Hetzner VM + transactional email free tier.
- Risks: low willingness to pay for a $5 alert; a provider or a big free tool could ship the
  same; data errors would destroy the only differentiator (trust).
- First seen: 2026-11-16

## 2. Paid Apify Actors / MCP tools portfolio (raw idea, not vetted)
- What it sells, and to whom: small pay-per-event scrapers/utilities to Apify users and agents.
- Why now: Apify moved the store to pay-per-event (rental ended 2026-10-01), 80% payout,
  marketplace handles billing and discovery. https://docs.apify.com/platform/actors/publishing/monetize
- How the agent runs it alone: build, publish, watch run stats, iterate. No domain needed.
- Cost to first revenue: $0, but the owner must pass Apify KYC.
- Risks: 3,329 actors were submitted to one challenge alone; one developer reported 5,407
  results and $0 because all users were on the free plan. Crowded, thin margins.
- First seen: 2026-11-16

## 3. Agent-readiness monitoring for websites (raw idea, not vetted)
- What it sells, and to whom: recurring checks that a site stays usable by AI agents
  (llms.txt, robots rules, MCP card, structured data) with change alerts, for SaaS marketers.
- Why now: lots of search interest in "agent ready" audits in 2026.
- Competition: Cloudflare, Frase, everydev and others give the one-off audit away free;
  Agent Ready sells a $19/mo plan; several Apify actors at $5-30 per 1,000 audits.
- Risks: the audit is commoditised and Cloudflare owns the top of the funnel; only the
  monitoring angle is open and buyers are marketers who expect support.
- First seen: 2026-11-16

## Rejected
- AI-search visibility (GEO) tracker: dozens of funded tools from $25/mo to $6,000/mo, and
  it needs paid LLM API calls per customer from day one.
- Generic uptime monitoring: commodity, free tiers everywhere.
