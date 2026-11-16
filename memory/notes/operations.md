# Operations notes

No business is running, so there is no routine yet. Durable environment facts:

- Run in the `agent-company` cloud environment. Its network is an allowlist; a blocked host
  shows as "CONNECT tunnel failed, 403" in curl or ENOTFOUND from fetch agents. Propose an
  `update_environment` edit when a host is needed.
- Stanley: on 2026-11-16 only `check_stanley_reply` was exposed. The owner granted
  `message_stanley` mid-session; it did not appear before the session ended.
- Some sites (llmsunset.com) sit behind a bot check and return 403 to curl.
- Model Sunset runbook, if `product/` is ever revived: `product/README.md`.
