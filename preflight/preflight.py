#!/usr/bin/env python3
"""Connected Preflight: check a public MCP endpoint against Google's Connected Apps rules.

    python3 preflight.py https://api.example.com/mcp
    python3 preflight.py URL --header "Authorization: Bearer ..."   # servers that need auth
    python3 preflight.py URL --save snapshot.json                   # pin today's schema
    python3 preflight.py URL --against snapshot.json                # fail if it drifted

Standard library only. Each finding links the Google page the rule was read on (2026-11-16).
Not affiliated with Google. Passing does not mean Google will approve the app.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.1.0"
RULES_READ = "2026-11-16"
DOCS = "https://developers.google.com/connected-apps"
REF = {
    "standards": DOCS + "/mcp/server-optimization",
    "policy": DOCS + "/connected-apps-policy",
    "prereq": DOCS + "/gpc/prerequisites",
    "oauth": DOCS + "/mcp/oauth",
}
SUPPORTED = ("2025-03-26", "2025-06-18", "2025-11-25")  # Streamable HTTP onward, up to Google's ceiling
LATEST = SUPPORTED[-1]
MAX_BYTES = 2_000_000
BANNED = re.compile(
    r"^(list_tools|get_schema|discover_tools|execute_command|invoke_dynamic_tool|"
    r"(execute|run|invoke|call)_(any_)?(command|tool|dynamic_tool|action|function))$", re.I)
DESTRUCTIVE = re.compile(r"^(delete|remove|cancel|pay|purchase|buy|transfer|refund|revoke|destroy|drop)([_A-Z-]|$)")
ACTION_PARAMS = {"action", "operation", "op", "mode", "command"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def http(method: str, url: str, headers: dict | None = None, body: bytes | None = None,
         timeout: float = 15):
    """Returns (status, headers-dict-lowercased, body-bytes). Never follows redirects."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        r = urllib.request.build_opener(_NoRedirect).open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        r = e
    with r:
        ctype = r.headers.get("Content-Type", "")
        # An open GET event stream never ends; the headers are all we need from it.
        data = b"" if method == "GET" and "event-stream" in ctype else r.read(MAX_BYTES)
        return r.status, {k.lower(): v for k, v in r.headers.items()}, data


class Client:
    """Minimal MCP Streamable HTTP client."""

    def __init__(self, url: str, extra: dict | None = None, fetch=http):
        self.url, self.fetch, self.n = url, fetch, 0
        self.headers = {"Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "User-Agent": f"connected-preflight/{VERSION}", **(extra or {})}

    def rpc(self, method: str, params: dict | None = None, notify: bool = False):
        """Returns (status, content-type, message-or-None)."""
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            self.n += 1
            msg["id"] = self.n
        status, hdrs, data = self.fetch("POST", self.url, self.headers, json.dumps(msg).encode())
        if hdrs.get("mcp-session-id"):
            self.headers["Mcp-Session-Id"] = hdrs["mcp-session-id"]
        ctype = hdrs.get("content-type", "").split(";")[0].strip().lower()
        return status, ctype, (None if notify else _message(ctype, data, self.n)), hdrs


def _message(ctype: str, data: bytes, want_id: int):
    text = data.decode("utf-8", "replace")
    if ctype == "text/event-stream":
        for block in re.split(r"\r?\n\r?\n", text):
            payload = "\n".join(l[5:].lstrip() for l in block.splitlines() if l.startswith("data:"))
            try:
                m = json.loads(payload)
            except ValueError:
                continue
            if isinstance(m, dict) and m.get("id") == want_id:
                return m
        return None
    try:
        m = json.loads(text)
    except ValueError:
        return None
    return m if isinstance(m, dict) else None


def finding(fid: str, level: str, title: str, detail: str = "", ref: str = "") -> dict:
    return {"id": fid, "level": level, "title": title, "detail": detail, "ref": REF.get(ref, ref)}


def check(url: str, extra_headers: dict | None = None, fetch=http) -> dict:
    """Run every check. Returns {"url", "findings", "snapshot" (or None), "summary"}."""
    out: list[dict] = []
    add = lambda *a, **k: out.append(finding(*a, **k))
    u = urllib.parse.urlsplit(url)
    snapshot = None

    if u.scheme != "https" or not u.hostname:
        add("https", "fail", "Endpoint is not a public https:// URL",
            "Google requires the MCP server to be publicly reachable over HTTPS.", "prereq")
        return _report(url, out, None)
    add("https", "pass", "Endpoint uses HTTPS", ref="prereq")

    c = Client(url, extra_headers, fetch)
    try:
        status, ctype, msg, hdrs = c.rpc("initialize", {
            "protocolVersion": LATEST, "capabilities": {},
            "clientInfo": {"name": "connected-preflight", "version": VERSION}})
    except Exception as e:  # DNS, TLS, timeout
        add("reach", "fail", "Endpoint could not be reached", f"{type(e).__name__}: {e}", "prereq")
        return _report(url, out, None)

    authed = True
    if 300 <= status < 400:
        add("reach", "fail", f"Endpoint answers with a redirect ({status})",
            f"Register the final URL ({hdrs.get('location', 'see Location header')}). "
            "Google sends every JSON-RPC request to the single registered endpoint.", "standards")
    elif status in (401, 403):
        authed = False
        add("reach", "info", f"Endpoint requires authorization ({status})",
            "Tool checks were skipped. Re-run with --header \"Authorization: Bearer <token>\" "
            "to check tools. OAuth discovery is checked below.", "oauth")
    elif status != 200 or not msg or "result" not in msg:
        legacy = _legacy_sse(url, fetch)
        add("transport", "fail",
            "Server uses the legacy HTTP+SSE transport" if legacy else
            f"initialize did not return a JSON-RPC result (HTTP {status}, {ctype or 'no content type'})",
            "Google supports only Streamable HTTP (MCP 2025-03-26 and later): one endpoint that "
            "accepts POST and answers with application/json or text/event-stream.", "standards")
    else:
        add("transport", "pass", f"Streamable HTTP initialize succeeded ({ctype})", ref="standards")
        res = msg["result"]
        ver = str(res.get("protocolVersion", ""))
        if ver in SUPPORTED:
            add("version", "pass", f"Protocol version {ver} is supported", ref="standards")
        elif ver > LATEST:
            add("version", "fail", f"Protocol version {ver} is newer than Google supports",
                f"The platform supports the MCP specification up to {LATEST}.", "standards")
        else:
            add("version", "fail", f"Protocol version {ver or '(missing)'} is not supported",
                "The 2024-11-05 HTTP+SSE generation is not supported; use 2025-03-26 or later.",
                "standards")
        c.headers["MCP-Protocol-Version"] = ver if ver in SUPPORTED else LATEST
        instructions = res.get("instructions") or ""
        if instructions.strip():
            add("instructions", "pass", f"Server instructions present ({len(instructions)} characters)",
                ref="standards")
        else:
            add("instructions", "warn", "No server instructions",
                "Google ingests server instructions to decide when to route to your app, and "
                "snapshots them at registration.", "standards")
        try:
            c.rpc("notifications/initialized", notify=True)
        except Exception:
            pass
        tools, err = _list_tools(c)
        if err:
            add("tools", "fail", "tools/list failed", err, "standards")
        elif not tools:
            add("tools", "fail", "Server lists no tools",
                "A connected app must declare its callable tools.", "policy")
        else:
            add("tools", "pass", f"tools/list returned {len(tools)} tool(s)", ref="standards")
            _tool_checks(tools, add)
            snapshot = make_snapshot(ver, instructions, tools)

    _get_check(url, c, fetch, add)
    if re.search(r"/v\d+(/|$)", u.path):
        add("versioned-path", "pass", "Endpoint path is versioned", ref="standards")
    else:
        add("versioned-path", "info", "Endpoint path has no version segment (for example /mcp/v1)",
            "Schema changes are only allowed between app versions. A versioned path lets you "
            "ship a new schema on /v2 while the registered /v1 stays frozen.", "standards")
    _domain_check(u, fetch, add)
    if not authed:
        _oauth_checks(u, fetch, add)
    return _report(url, out, snapshot)


def _legacy_sse(url, fetch) -> bool:
    try:
        status, hdrs, _ = fetch("GET", url, {"Accept": "text/event-stream"}, None)
    except Exception:
        return False
    return status == 200 and "event-stream" in hdrs.get("content-type", "")


def _list_tools(c: Client):
    tools, cursor = [], None
    for _ in range(20):
        try:
            status, _, msg, _ = c.rpc("tools/list", {"cursor": cursor} if cursor else {})
        except Exception as e:
            return tools, f"{type(e).__name__}: {e}"
        if status != 200 or not msg or "result" not in msg:
            err = (msg or {}).get("error", {}).get("message", "")
            return tools, f"HTTP {status} {err}".strip()
        tools += [t for t in msg["result"].get("tools", []) if isinstance(t, dict)]
        cursor = msg["result"].get("nextCursor")
        if not cursor:
            break
    return tools, ""


def _names(items) -> str:
    items = list(items)
    return ", ".join(items[:8]) + (f" and {len(items) - 8} more" if len(items) > 8 else "")


def _tool_checks(tools: list[dict], add) -> None:
    name = lambda t: str(t.get("name", "?"))
    banned = [name(t) for t in tools if BANNED.match(name(t))]
    if banned:
        add("dynamic-tools", "fail", f"Dynamic discovery or dispatcher tool(s): {_names(banned)}",
            "Policy: connected apps must statically declare all callable operations and must not "
            "expose dynamic discovery functions or generic runtime dispatchers.", "policy")
    else:
        add("dynamic-tools", "pass", "No dynamic discovery or dispatcher tools", ref="policy")

    def hints(t):
        a = t.get("annotations")
        return a if isinstance(a, dict) else {}
    bare = [name(t) for t in tools if "readOnlyHint" not in hints(t) and "destructiveHint" not in hints(t)]
    if bare:
        add("annotations", "warn", f"{len(bare)} tool(s) without explicit safety annotations: {_names(bare)}",
            "Declare readOnlyHint or destructiveHint on every tool. Without them clients assume "
            "readOnlyHint: false and destructiveHint: true.", "standards")
    else:
        add("annotations", "pass", "Every tool declares readOnlyHint or destructiveHint", ref="standards")
    risky = [name(t) for t in tools if DESTRUCTIVE.match(name(t)) and hints(t).get("destructiveHint") is not True]
    if risky:
        add("destructive", "warn", f"Looks destructive but lacks destructiveHint: true: {_names(risky)}",
            "Policy: tools that delete data, move money or alter access must set destructiveHint: true "
            "or be marked as requiring confirmation in the Connected Console.", "policy")
    clash = [name(t) for t in tools if hints(t).get("readOnlyHint") is True and hints(t).get("destructiveHint") is True]
    if clash:
        add("annotation-clash", "warn", f"readOnlyHint and destructiveHint both true: {_names(clash)}",
            "A read-only tool cannot be destructive.", "standards")

    thin = [name(t) for t in tools if len(str(t.get("description") or "").strip()) < 40]
    if thin:
        add("descriptions", "warn", f"{len(thin)} tool(s) with a missing or very short description: {_names(thin)}",
            "The description is the only context the model has to pick your tool. Say what it does, "
            "when to use it, input formats and what it returns.", "standards")
    else:
        add("descriptions", "pass", "Every tool has a description of 40+ characters", ref="standards")
    vague = [name(t) for t in tools if re.search(r"best judge?ment", str(t.get("description") or ""), re.I)]
    if vague:
        add("discretion", "warn", f"Description leaves the choice to the model: {_names(vague)}",
            "Google: don't instruct the model to use its \"best judgment\".", "standards")

    multi, untyped, undescribed, int_ids = [], [], [], []
    for t in tools:
        schema = t.get("inputSchema") if isinstance(t.get("inputSchema"), dict) else {}
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for pname, p in props.items():
            if not isinstance(p, dict):
                continue
            label = f"{name(t)}.{pname}"
            if pname.lower() in ACTION_PARAMS and len(p.get("enum") or []) >= 3:
                multi.append(name(t))
            if not any(k in p for k in ("type", "anyOf", "oneOf", "allOf", "$ref", "enum", "const")):
                untyped.append(label)
            if not str(p.get("description") or "").strip():
                undescribed.append(label)
            if p.get("type") in ("integer", "number") and re.search(r"(^id$|_id$|[a-z]Id$)", pname):
                int_ids.append(label)
    if multi:
        add("multi-action", "warn", f"One tool, many actions: {_names(multi)}",
            "Google's standards show a single manage_x tool with an action parameter as the "
            "pattern to avoid. Split it into one tool per action.", "standards")
    if untyped:
        add("param-types", "warn", f"{len(untyped)} parameter(s) without a type: {_names(untyped)}",
            "Use strong, specific types and enums for fixed value sets.", "standards")
    if undescribed:
        add("param-docs", "warn", f"{len(undescribed)} parameter(s) without a description: {_names(undescribed)}",
            "Describe format, units and where the value comes from.", "standards")
    if int_ids:
        add("numeric-ids", "warn", f"Numeric ID parameter(s): {_names(int_ids)}",
            "Google: treat all numerical ID fields as strings; long IDs can be truncated.", "standards")
    if not (untyped or undescribed):
        add("params", "pass", "Every parameter has a type and a description", ref="standards")


def _get_check(url, c, fetch, add) -> None:
    try:
        status, hdrs, _ = fetch("GET", url, {**c.headers, "Accept": "text/event-stream"}, None)
    except Exception:
        return
    if status == 405 or (status == 200 and "event-stream" in hdrs.get("content-type", "")):
        add("get", "pass", f"GET on the endpoint is handled ({status})", ref="standards")
    elif status not in (401, 403):
        add("get", "info", f"GET on the endpoint returns {status}",
            "Google's client may try an optional GET stream. Return 405 if you do not support it.",
            "standards")


def _domain_check(u, fetch, add) -> None:
    target = f"https://{u.netloc}/.well-known/google-connected-apps"
    try:
        status, hdrs, data = fetch("GET", target, {"Accept": "application/json"}, None)
    except Exception as e:
        add("domain-file", "info", "Domain verification file could not be fetched", str(e), "prereq")
        return
    if 300 <= status < 400:
        add("domain-file", "fail", f"Domain verification path redirects ({status})",
            f"{target} must answer 200 directly, with no redirects.", "prereq")
    elif status == 200:
        try:
            json.loads(data.decode("utf-8", "replace"))
            add("domain-file", "pass", "Domain verification file is served as JSON with no redirect", ref="prereq")
        except ValueError:
            add("domain-file", "warn", "Domain verification path returns 200 but not JSON",
                "Serve the JSON challenge token file from the Connected Console as is.", "prereq")
    else:
        add("domain-file", "info", f"No domain verification file yet ({status})",
            f"Before registering you must serve the Console's JSON token at {target} "
            "with HTTP 200 and no redirects.", "prereq")


def _json_get(url, fetch):
    try:
        status, _, data = fetch("GET", url, {"Accept": "application/json"}, None)
        return json.loads(data.decode("utf-8", "replace")) if status == 200 else None
    except Exception:
        return None


def _oauth_checks(u, fetch, add) -> None:
    base = f"https://{u.netloc}"
    path = u.path.rstrip("/")
    prm = None
    for cand in ([f"{base}/.well-known/oauth-protected-resource{path}"] if path else []) + \
                [f"{base}/.well-known/oauth-protected-resource"]:
        prm = _json_get(cand, fetch)
        if isinstance(prm, dict):
            break
    servers = prm.get("authorization_servers") if isinstance(prm, dict) else None
    if not servers:
        add("oauth-resource", "fail", "No OAuth protected-resource metadata",
            "Serve /.well-known/oauth-protected-resource with an authorization_servers list so the "
            "client can discover how to authorize. On a provider-specific subdomain the metadata "
            "must match that exact subdomain.", "oauth")
        return
    add("oauth-resource", "pass", "OAuth protected-resource metadata found", ref="oauth")
    issuer = str(servers[0]).rstrip("/")
    iu = urllib.parse.urlsplit(issuer)
    if iu.scheme != "https":
        add("oauth-server", "fail", "Authorization server is not https", issuer, "oauth")
        return
    root = f"https://{iu.netloc}"
    meta = None
    for cand in (f"{root}/.well-known/oauth-authorization-server{iu.path}",
                 f"{root}/.well-known/openid-configuration{iu.path}",
                 f"{issuer}/.well-known/openid-configuration"):
        meta = _json_get(cand, fetch)
        if isinstance(meta, dict):
            break
    if not isinstance(meta, dict):
        add("oauth-server", "fail", "Authorization server metadata not found",
            "Google requires OAuth discovery (Authorization Server Metadata).", "oauth")
        return
    missing = [k for k in ("authorization_endpoint", "token_endpoint") if not isinstance(meta.get(k), str)]
    if "code" not in (meta.get("response_types_supported") or []):
        missing.append('response_types_supported containing "code"')
    if missing:
        add("oauth-server", "fail", "Authorization server metadata is incomplete",
            "Missing: " + ", ".join(missing), "oauth")
    else:
        add("oauth-server", "pass", "Authorization server metadata has the required fields", ref="oauth")
    if not meta.get("registration_endpoint"):
        add("oauth-dcr", "warn", "No registration_endpoint (Dynamic Client Registration)",
            "Without it you must enter a client ID and secret by hand in the console.", "oauth")
    if "S256" not in (meta.get("code_challenge_methods_supported") or []):
        add("oauth-pkce", "warn", "PKCE S256 is not advertised",
            "If you support PKCE, list code_challenge_methods_supported in the discovery JSON.", "oauth")


def _report(url: str, findings: list[dict], snapshot) -> dict:
    count = lambda lvl: sum(1 for f in findings if f["level"] == lvl)
    return {"url": url, "tool": f"connected-preflight {VERSION}", "rules_read": RULES_READ,
            "findings": findings, "snapshot": snapshot,
            "summary": {k: count(k) for k in ("fail", "warn", "pass", "info")}}


# ------------------------------------------------------------------ snapshots

def make_snapshot(version: str, instructions: str, tools: list[dict]) -> dict:
    """What Google says it snapshots at registration: tools, their arguments, server instructions."""
    slim = sorted(({"name": str(t.get("name", "")), "description": t.get("description") or "",
                    "inputSchema": t.get("inputSchema") or {}, "annotations": t.get("annotations") or {}}
                   for t in tools), key=lambda t: t["name"])
    snap = {"protocolVersion": version, "instructions": instructions, "tools": slim}
    snap["hash"] = hashlib.sha256(json.dumps(snap, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return snap


def diff(old: dict, new: dict) -> list[str]:
    """Human-readable changes from old to new. Empty list means no drift."""
    if old.get("hash") and old.get("hash") == new.get("hash"):
        return []
    changes = []
    a = {t["name"]: t for t in old.get("tools", [])}
    b = {t["name"]: t for t in new.get("tools", [])}
    changes += [f"Tool removed: {n}" for n in sorted(a.keys() - b.keys())]
    changes += [f"Tool added: {n}" for n in sorted(b.keys() - a.keys())]
    for n in sorted(a.keys() & b.keys()):
        for key, label in (("inputSchema", "arguments"), ("description", "description"),
                           ("annotations", "annotations")):
            if a[n].get(key) != b[n].get(key):
                changes.append(f"Tool {n}: {label} changed")
    if old.get("instructions") != new.get("instructions"):
        changes.append("Server instructions changed")
    if old.get("protocolVersion") != new.get("protocolVersion"):
        changes.append(f"Protocol version changed: {old.get('protocolVersion')} -> {new.get('protocolVersion')}")
    return changes


# ------------------------------------------------------------------------ CLI

MARK = {"fail": "FAIL", "warn": "WARN", "pass": " ok ", "info": "info"}


def render(report: dict) -> str:
    lines = [f"Connected Preflight {VERSION} - {report['url']}",
             f"Rules read from {DOCS} on {RULES_READ}", ""]
    for level in ("fail", "warn", "info", "pass"):
        for f in report["findings"]:
            if f["level"] != level:
                continue
            lines.append(f"[{MARK[level]}] {f['title']}")
            if f["detail"]:
                lines.append(f"       {f['detail']}")
            if f["ref"] and level != "pass":
                lines.append(f"       {f['ref']}")
    s = report["summary"]
    lines += ["", f"{s['fail']} failed, {s['warn']} warnings, {s['pass']} passed."]
    if report["snapshot"]:
        lines.append(f"Schema snapshot {report['snapshot']['hash'][:12]} "
                     f"({len(report['snapshot']['tools'])} tools).")
    lines.append("Passing these checks does not mean Google will approve the app.")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("--header", action="append", default=[], metavar="'Name: value'")
    ap.add_argument("--save", metavar="FILE", help="write the schema snapshot to FILE")
    ap.add_argument("--against", metavar="FILE", help="compare with a saved snapshot; exit 1 on drift")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    a = ap.parse_args(argv)
    headers = {}
    for h in a.header:
        k, sep, v = h.partition(":")
        if not sep:
            ap.error(f"bad --header {h!r}")
        headers[k.strip()] = v.strip()
    report = check(a.url, headers)
    print(json.dumps(report, indent=2) if a.json else render(report))
    code = 1 if report["summary"]["fail"] else 0
    snap = report["snapshot"]
    if a.against:
        if not snap:
            print("\nNo snapshot could be taken, so drift was not checked.", file=sys.stderr)
            return 2
        with open(a.against) as fh:
            changes = diff(json.load(fh), snap)
        if changes:
            print("\nDRIFT from the saved snapshot. Google snapshots the schema at registration; "
                  "a change may get the app disabled:", file=sys.stderr)
            for ch in changes:
                print("  - " + ch, file=sys.stderr)
            code = 1
        else:
            print("\nNo drift from the saved snapshot.")
    if a.save and snap:
        with open(a.save, "w") as fh:
            json.dump(snap, fh, indent=2, sort_keys=True)
        print(f"Snapshot written to {a.save}")
    return code


if __name__ == "__main__":
    sys.exit(main())
