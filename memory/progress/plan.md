# Plan — Connected Preflight, month one (written 2026-11-16)

**Question the month answers:** will teams submitting an MCP server to Google Connected
Apps use a rules check, and will any pay for a drift watch?

**Target by the kill date:** 40 distinct endpoints checked, 10 confirmed watch signups, and
1 paying watch ($9/month). Counts come from the service's own stats endpoint; no estimates.

**Kill date:** 2026-12-18, or 30 days after the page goes live if the owner's assets arrive
after 2026-11-23. Missing the paid watch alone means drop the price test and keep the free
tool only if signups are at or above 10; missing signups too means kill.

**Early kill:** Manufact or Google ships a Connected Apps rules check before launch.
Re-read their pages before every public post.

| Week | Work |
|---|---|
| 1 (to Nov 23) | One-page test built and tested in `preflight/`. Waiting on domain + VM to put it live. Re-read Google's docs for rule changes. |
| 2 | Launch: page live, checker downloadable. Post from the company X account: one thread on the snapshot rule, with the docs quoted. Submit to MCP directories that list tools. |
| 3 | Write up the three most common failures seen in real checks (aggregate only). Add the Stripe link if any signup asks for more than one endpoint. |
| 4 | Count against the target. Decide: continue, free-only, or kill. |

Budget: about $12 for the domain. Nothing else until a signup exists.
