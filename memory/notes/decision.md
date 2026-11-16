# Decision log

## Current state (2026-11-16): no business chosen. Phase 1 must be redone.

Model Sunset was chosen and killed on the same day, before any launch or spend.

## Why Model Sunset was killed
The owner pointed out that modelsunset.com exists. Reading it and its neighbours showed the
market is already served, mostly for free:
- modelsunset.com (ALEX SMART TECH LLC): same name, same pitch. Official-source links,
  free 50-model alert watchlist, 90/30/7/1 reminders, local code scan, calendar, JSON feed.
  35 models, 3 providers, donation-supported.
- llmsunset.com: claims 2,186+ models, 21 providers, daily; free email/Slack/Teams alerts,
  webhook and read-only API (page is behind a bot check; this is from its search snippet).
- deprecations.info: free RSS/JSON feeds for 9 providers including Bedrock, Vertex, Azure.
- sunsetlint.com: paid GitHub App that finds retiring IDs by file and line, and already
  owns the "cloud platforms have their own dates" angle.
- Two GitHub projects named model-sunset, plus PyPI llm-model-deprecation, depdesk, llm-sunset.
Every differentiator in the original decision (alerts, feeds, source links, cloud clocks) is
already offered free by someone. A $5 tier has nothing to sell.

## What went wrong in phase 1 (do not repeat)
- I never searched for the product's own name or the obvious "X tracker / X alerts" queries
  with the alert feature in them; I wrote "none found offering alerts" from one search.
- I judged competitors from search snippets instead of reading their pages.
- I built for hours before a five-minute name check.
- The owner's X feed, the intended idea source, was unread.

## Rules for the next pick (binding)
1. Read the owner's feed via Stanley first. No pick without it unless the owner says so.
2. Before choosing: search the candidate's name, "<thing> tracker", "<thing> alerts",
   "<thing> API", "<thing> free", "<thing> github"; open and read the top five results.
3. Write down one gap, confirmed absent on each competitor's own page, that someone pays for
   today (name who, and what they pay). No confirmed gap, no pick.
4. Check the name: .com, GitHub, PyPI/npm, X handle.
5. Build nothing beyond a one-page test until 1-4 are written in this file.

## Old runners-up (not vetted to the standard above)
Paid Apify Actors / MCP tools; agent-readiness monitoring for websites. Treat as raw ideas.

## Salvage
`product/` stays in the repo: the registry/parsers, static generator, alert service and CLI
are generic and tested. Reuse the alert service and site generator if the next business
needs them. Nothing was deployed, published or bought.
