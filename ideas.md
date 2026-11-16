# Business ideas

One section per idea, strongest first. Sources: the owner's X feed read by Stanley on
2026-11-16 (99 timeline posts Nov 13-16, 99 bookmarks Jul 29-Nov 15; likes not visible) and
the open web. Feed themes, by frequency: AI-search optimisation (AEO), always-on background
agents, agentic video workflows, B2B buying-signal scraping. Evidence for the vetted ideas is
in `memory/notes/decision.md`.

## 1. Connected Preflight — check and watch an MCP server against Google's Connected Apps rules (ON HOLD 2026-11-16: absorbed by CI and code review)
- Feed source: @elliot_garreffa, Oct 30 (Google Connected Apps for MCPs); the always-on agent cluster.
- What it sells, and to whom: a free check of a public MCP endpoint against Google's published
  Connected Apps standards and policy; paid ($9/mo) daily watch that alerts when the live
  schema drifts from the snapshot Google took at registration. Buyers: teams submitting an
  MCP server to Google Connected Console.
- Why now: preview opened 2026-10-28. Google's docs say a schema change after registration
  "may cause the application to be disabled", and dynamic dispatchers are banned by policy.
- Competition read on their own pages: Manufact publish checks (ChatGPT/Claude only),
  MCPJam, sunpeak, FlareCanary, Apify ToolDiff, GenAI Magazine's offline checker. None
  tests a live endpoint against Google's rules.
- How the agent runs it alone: re-read Google's docs on a schedule, update rules, run watches.
- Cost to first revenue: domain (~$12) + VM + SMTP free tier.
- Risks: preview is a US waitlist with few admitted developers; Manufact could add a Google
  ruleset in a week; Google may ship its own linter.
- First seen: 2026-11-16

## Niche scorecard for the digest engine (owner-favoured direction, 2026-11-16)
A niche qualifies only if: readers make money from the information (operators, investors,
agency owners); 15+ active practitioner shows; no cross-show digest exists (read pages);
there is a public place to reach readers that allows posts; sponsors already buy ads in the
niche's shows. Candidates to score: multifamily operators, short-term-rental hosts,
e-commerce/Amazon sellers, home-service contractors, independent insurance or dental
practice owners, agency owners, managed IT service providers (MSPs). Rank survivors by
revenue per reader, using four numbers looked up per niche: price of existing paid info
(newsletters, memberships, masterminds); sponsor rates on the niche's shows/newsletters;
size of the decisions readers make; number of vendors with high-value contracts advertising
to them. Stay operational: no investment or health advice. Dropped: AEO (free newsletters and Otterly's sheet exist).

## Put to the owner on 2026-11-16 (none vetted to the binding rules yet)
- Niche stale-role shortlist: weekly pitch-ready list for one buyer type (e.g. fractional
  RevOps consultants), sold as a paid email, not as data.
- Vertical podcast digest (feed: @DallasAptGP): weekly brief of tactics from one trade's
  podcasts, paid newsletter.
- ChatGPT app rejection pre-check: proven pain on OpenAI's forum, but Manufact and Alpic are there.
- Programmatic calculator cluster (feed: @openseo, @arthuryuzbashev): slow, ad/affiliate revenue.
- Agent skills on lower-threshold marketplaces (Agensi, SkillHQ): unverified sales.

## 2. Stale Roles — list of long-open job postings from public ATS feeds (runner-up, gap NOT confirmed)
- Feed source: @freddiexpott, Nov 1 (pitching companies with jobs open 21+ days; 3 closes at $8.5k).
- What it sells: weekly list + CSV of roles open 21/45/90+ days by function, with alerts, to
  recruiters and agencies.
- Competition read: Mantiks shows "Job reposted - Active for 52 days" and sells alerts from
  EUR 99/mo; TheirStack has date filters, closed-job filter, CSV and email alerts ($49/mo API);
  Apify actors filter `openLongerThanDays` for $2-3 per 1,000; CSVFirst gives a free CSV of
  days-open per company. The data and the filter exist; only the packaging is open.
- Feasibility: Greenhouse, Lever and Ashby public job-board APIs answer without auth (tested).
- First seen: 2026-11-16

## 3. A paid Agent Skill on Capafy (runner-up, not vettable yet)
- Feed source: @Capafyai, Oct 21 (CloneCut: $289K in 30 days).
- Read on Capafy's GitHub docs: seller needs paid developer certification with KYC and a
  bank payout; search API exposes sales counts. Marketplace pages (capafy.ai) were not read
  before this run ended, so no gap is confirmed. Sales figures are uncorroborated.
- First seen: 2026-11-16

## Rejected on 2026-11-16
- Markdown-for-agents checker (feed: @CrowdReply_io on Ramp's markdown test): Cloudflare's
  isitagentready.com and at least five others check it free; monitoring sold at $19-99/mo by
  agent-ready tools; the underlying claim is disputed by Otterly and Profound tests.
- Connected Apps directory/tracker with alerts: free trackers exist for ChatGPT/Claude
  (ROAST, Sitter); Google publishes its own list; nobody pays for it.
- Podcast knowledge extraction (@DallasAptGP): needs paid LLM calls per customer from day one.
- Agent-first 3D engine, subagent session forking, terminal video editing: already built by
  the people posting, or not sellable inside $100.

## Old: Model Sunset — verified LLM model-retirement feed and alerts (KILLED 2026-11-16)
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

## Old: Paid Apify Actors / MCP tools portfolio (raw idea, not vetted)
- What it sells, and to whom: small pay-per-event scrapers/utilities to Apify users and agents.
- Why now: Apify moved the store to pay-per-event (rental ended 2026-10-01), 80% payout,
  marketplace handles billing and discovery. https://docs.apify.com/platform/actors/publishing/monetize
- How the agent runs it alone: build, publish, watch run stats, iterate. No domain needed.
- Cost to first revenue: $0, but the owner must pass Apify KYC.
- Risks: 3,329 actors were submitted to one challenge alone; one developer reported 5,407
  results and $0 because all users were on the free plan. Crowded, thin margins.
- First seen: 2026-11-16

## Old: Agent-readiness monitoring for websites (raw idea, not vetted)
- What it sells, and to whom: recurring checks that a site stays usable by AI agents
  (llms.txt, robots rules, MCP card, structured data) with change alerts, for SaaS marketers.
- Why now: lots of search interest in "agent ready" audits in 2026.
- Competition: Cloudflare, Frase, everydev and others give the one-off audit away free;
  Agent Ready sells a $19/mo plan; several Apify actors at $5-30 per 1,000 audits.
- Risks: the audit is commoditised and Cloudflare owns the top of the funnel; only the
  monitoring angle is open and buyers are marketers who expect support.
- First seen: 2026-11-16

## Rejected earlier
- AI-search visibility (GEO) tracker: dozens of funded tools from $25/mo to $6,000/mo, and
  it needs paid LLM API calls per customer from day one.
- Generic uptime monitoring: commodity, free tiers everywhere.
