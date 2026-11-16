# Decision log

## Current state (2026-11-16): chosen business is Connected Preflight. Phase 2, one-page test only.

**What it is.** A free check of a public MCP endpoint against Google's Connected Apps Platform
standards and policy, and a paid daily watch ($9/month) that alerts when the live server
drifts from the schema it had when it was registered. Code: `preflight/`.

**Feed source.** Stanley read the owner's feed on 2026-11-16 (198 posts). The Google
Connected Apps launch (@elliot_garreffa, Oct 30) sits inside the feed's second-biggest
theme, always-on agents, and the owner's follows are AI builders who ship MCP servers.

### The gap, and where it was confirmed
Google's rules (read on developers.google.com/connected-apps, 2026-11-16):
- `/mcp/server-optimization`: at registration "snapshots are taken of the MCP schema —
  including the list of tools, their arguments, and server instructions. Changing the MCP
  server schema may break the integration and may cause the application to be disabled."
  Also: Streamable HTTP only, MCP spec up to 2025-11-25, explicit annotations on all tools.
- `/connected-apps-policy`: tools must be declared statically; no `list_tools`,
  `get_schema`, `execute_command`, `invoke_dynamic_tool`; destructive tools need
  `destructiveHint: true`.
- `/gpc/prerequisites`: domain file at `/.well-known/google-connected-apps`, 200, no redirect.
- Google's own testing is manual: MCP Inspector locally, then Gemini Apps Developer Mode
  (`/mcp/dev-mode/usage`). No automated linter and no drift alert is described.

Gap: **nothing tests a live MCP endpoint against Google's Connected Apps rules, or watches
it against the registered snapshot.** Confirmed absent on each competitor's own page:

| Competitor (page read) | What it does | Price | Google rules? |
|---|---|---|---|
| Manufact publish checks (docs.manufact.com/dashboard/publish-checks, manufact.com/pricing) | Checklist and score against "ChatGPT Apps Store and Cloud Connectors requirements"; automatic re-runs only "on Manufact-hosted servers"; others "on request: book a call" | $0.90 per checklist run; Pro $250/mo | No mention of Google or Gemini on either page |
| MCPJam (mcpjam.com/pricing) | Inspector, evals, OAuth debugger, CI checks; marketer page says "Reach users inside ChatGPT and Claude" | Free; Pro $24/mo | No mention |
| sunpeak (sunpeak.ai/blogs/pre-submission-testing-mcp-apps) | MIT test framework and pre-submission checklist for ChatGPT/Claude apps | Free | No mention |
| FlareCanary (flarecanary.com) | Generic API and "MCP Tool Schema Tracking" drift alerts (beta) | Free tier | No mention; no rule checks |
| Apify ToolDiff (apify.com/savagnic/tooldiff) | Snapshot and diff of `tools/list`; 2 total users, "under maintenance" | $50 per 1,000 results | No mention; no rule checks |
| GenAI Magazine planning kit (thegenaimagazine.com/google-connected-apps-mcp-store-developer-enrollment-guide) | Offline Node script that checks a planning JSON; "makes no network requests" | Free | Google-specific, but never touches the server |

Not readable: MCP Uptime Ledger (bot check), ROAST tracker (bot check).

**Who pays today.** MCP teams preparing store submissions pay Manufact $0.90 per checklist
run and MCPJam $24/month for the ChatGPT/Claude equivalent; eseospace.com sells MCP
build-and-listing work for "Gemini, Search, ChatGPT and Claude". Honest limit: I found no
one paying for a Google-specific check yet. The platform is 19 days old and Google says it
is admitting a small number of partners from a waitlist. That is the main risk and it is
what the one-page test measures.

**Name.** connectedpreflight.com unregistered (Verisign RDAP 404); PyPI and npm
`connectedpreflight` / `connected-preflight` free; no GitHub repo of that name; x.com/
connectedpreflight returned 404 to an unauthenticated request (not conclusive).
Avoid "MCP Preflight": taken on npm and PyPI.

### Runners-up (vetted the same way; neither has a confirmed gap)
1. **Stale Roles** (feed: @freddiexpott, Nov 1). Weekly list of job postings open 21/45/90+
   days from public ATS feeds, for recruiters and agencies. Pages read: Mantiks home and
   pricing ("Job reposted - Active for 52 days", "Detect urgent hiring needs", alerts,
   Starter EUR 99/mo); TheirStack old-jobs guide and pricing (date filters, Job Closed filter,
   CSV export, email alerts, API $49/mo); JobsPipe staffing-leads page (alerts per company,
   $49/mo); Apify gganbukim/ats-job-scraper (`openLongerThanDays`, $3 per 1,000); CSVFirst
   (free CSV of days open per company, Greenhouse only). Verdict: the filter and the data
   exist at every price; only multi-ATS weekly packaging is open, which is not a gap.
   Greenhouse, Lever and Ashby job-board APIs answered without auth in this session.
   Names staleroles/longopen are free on PyPI and npm.
2. **A paid Agent Skill on Capafy** (feed: @Capafyai, Oct 21). Read capafy.ai home and
   publisher agreement v1.2: 20% platform fee after a sandbox fee, US$100 minimum payout,
   paid certification with identity checks, and the publisher supplies and maintains its own
   API keys, so model costs fall on the seller. Home page shows 70 listings in 45+
   categories; top listing claims 56.5k sold. No category confirmed absent, and the sales
   figures have no outside corroboration. Needs the owner for KYC and a budget for model calls.

If Connected Preflight is killed, re-vet before switching; do not treat either runner-up as
approved.

## Phase 1 history: Model Sunset (killed 2026-11-16)

### Why Model Sunset was killed
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

### What went wrong (do not repeat)
- I never searched for the product's own name or the obvious "X tracker / X alerts" queries
  with the alert feature in them; I wrote "none found offering alerts" from one search.
- I judged competitors from search snippets instead of reading their pages.
- I built for hours before a five-minute name check.
- The owner's X feed, the intended idea source, was unread.

## Rules for any pick (binding)
1. Read the owner's feed via Stanley first. No pick without it unless the owner says so.
2. Before choosing: search the candidate's name, "<thing> tracker", "<thing> alerts",
   "<thing> API", "<thing> free", "<thing> github"; open and read the top five results.
3. Write down one gap, confirmed absent on each competitor's own page, that someone pays for
   today (name who, and what they pay). No confirmed gap, no pick.
4. Check the name: .com, GitHub, PyPI/npm, X handle.
5. Build nothing beyond a one-page test until 1-4 are written in this file.

## Salvage
`product/` stays in the repo: the registry/parsers, static generator, alert service and CLI
are generic and tested. Reuse the alert service and site generator if the next business
needs them. Nothing was deployed, published or bought.
