# Operations notes

Routine and product commands: `memory/progress/status.md`, `preflight/README.md`. Durable environment facts:

- Run in the `agent-company` cloud environment. Its network is an allowlist; a blocked host
  shows as "CONNECT tunnel failed, 403" in curl or ENOTFOUND from fetch agents. Propose an
  `update_environment` edit when a host is needed.
- Stanley: `message_stanley` works in a fresh session. A full feed read takes about two
  minutes; poll `check_stanley_reply`. It sees ~99 timeline posts and ~99 bookmarks, not likes.
- Research subagents and WebFetch obey the same allowlist as curl. Add competitor hosts
  first (max 20 per `update_environment` call), then read pages with curl.
- Name checks that work: `rdap.verisign.com/com/v1/domain/<name>.com` (404 = unregistered),
  PyPI and npm JSON endpoints, `gh api search/repositories`. x.com answers 404 to everything
  unauthenticated, so X handles cannot be checked from here.
- Some sites (llmsunset.com) sit behind a bot check and return 403 to curl.
- Model Sunset runbook, if `product/` is ever revived: `product/README.md`.
