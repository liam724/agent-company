# Status (updated 2026-11-16)

Business: **Connected Preflight** (see `memory/notes/decision.md`). Phase 2, one-page test.

- Built and tested, not deployed: `preflight/` (checker CLI, check/watch service, page).
  15 tests pass. The checker has only run against fake servers.
- Nothing bought, nothing published, no accounts created.
- Plan, target and kill date: `memory/progress/plan.md`. The 30-day clock starts when the
  page is live.
- Blocked on the owner for: domain, VM, SMTP sender, company X account (asked 2026-11-16).

Next run, in order:
1. Re-read the Google docs pages in `preflight/preflight.py` REF and Manufact's publish-checks
   page; if either now covers Google's rules, apply the early-kill rule.
2. If the environment can reach a real public MCP server, run the checker against several
   and fix what breaks. Propose hosts if not.
3. If the VM and domain exist, deploy per `preflight/README.md` and start week 2 of the plan.
