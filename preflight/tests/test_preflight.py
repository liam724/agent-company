"""python3 -m unittest discover -s tests   (from preflight/)"""
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import page  # noqa: E402
import preflight  # noqa: E402
import service  # noqa: E402

GOOD_TOOLS = [
    {"name": "search_orders", "description": "Search the signed-in user's orders by status. Returns up to 20 orders, newest first.",
     "inputSchema": {"type": "object", "properties": {
         "status": {"type": "string", "enum": ["open", "shipped"], "description": "Order status to filter by."}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "cancel_order", "description": "Cancel one order. 'order_id' must come from search_orders. Returns the new status.",
     "inputSchema": {"type": "object", "properties": {
         "order_id": {"type": "string", "description": "Order UUID from search_orders."}}, "required": ["order_id"]},
     "annotations": {"destructiveHint": True}},
]


class Fake:
    """A fake fetch() standing in for an MCP server and its well-known files."""

    def __init__(self, tools=GOOD_TOOLS, version="2025-11-25", instructions="Order support for Acme.",
                 sse=False, auth=False, init_status=200, get_status=405, wellknown=None):
        self.__dict__.update(locals())
        self.wellknown = wellknown or {}

    def __call__(self, method, url, headers=None, body=None, timeout=15):
        path = url.split("/", 3)[3] if url.count("/") > 2 else ""
        if "/.well-known/" in url:
            for suffix, (status, payload) in self.wellknown.items():
                if url.endswith(suffix):
                    return status, {"content-type": "application/json"}, json.dumps(payload).encode()
            return 404, {}, b""
        if method == "GET":
            return self.get_status, {"content-type": "text/event-stream" if self.get_status == 200 else ""}, b""
        if self.auth:
            return 401, {}, b""
        if self.init_status != 200:
            return self.init_status, {"location": "https://x.example/new"}, b""
        msg = json.loads(body)
        if "id" not in msg:
            return 202, {}, b""
        if msg["method"] == "initialize":
            result = {"protocolVersion": self.version, "capabilities": {"tools": {}},
                      "serverInfo": {"name": "fake", "version": "1"}}
            if self.instructions:
                result["instructions"] = self.instructions
        else:
            result = {"tools": self.tools}
        reply = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        if self.sse:
            return 200, {"content-type": "text/event-stream"}, f"event: message\ndata: {json.dumps(reply)}\n\n".encode()
        return 200, {"content-type": "application/json", "mcp-session-id": "s1"}, json.dumps(reply).encode()


URL = "https://mcp.example.com/mcp/v1"


def levels(report):
    return {f["id"]: f["level"] for f in report["findings"]}


class CheckTests(unittest.TestCase):
    def test_clean_server_passes(self):
        r = preflight.check(URL, fetch=Fake())
        self.assertEqual(r["summary"]["fail"], 0, r["findings"])
        self.assertEqual(r["summary"]["warn"], 0, r["findings"])
        self.assertEqual(len(r["snapshot"]["tools"]), 2)
        self.assertEqual(levels(r)["domain-file"], "info")

    def test_sse_framed_response_is_parsed(self):
        r = preflight.check(URL, fetch=Fake(sse=True))
        self.assertEqual(levels(r)["transport"], "pass")
        self.assertTrue(r["snapshot"])

    def test_not_https(self):
        r = preflight.check("http://mcp.example.com/mcp", fetch=Fake())
        self.assertEqual(levels(r), {"https": "fail"})

    def test_version_too_new_and_too_old(self):
        self.assertEqual(levels(preflight.check(URL, fetch=Fake(version="2026-06-30")))["version"], "fail")
        self.assertEqual(levels(preflight.check(URL, fetch=Fake(version="2024-11-05")))["version"], "fail")

    def test_legacy_sse_and_redirect(self):
        r = preflight.check(URL, fetch=Fake(init_status=404, get_status=200))
        self.assertIn("legacy", [f for f in r["findings"] if f["id"] == "transport"][0]["title"])
        self.assertEqual(levels(preflight.check(URL, fetch=Fake(init_status=308)))["reach"], "fail")

    def test_bad_tools_are_flagged(self):
        bad = [
            {"name": "execute_command", "description": "Runs it."},
            {"name": "delete_user", "description": "Deletes.", "inputSchema": {"type": "object", "properties": {
                "user_id": {"type": "integer"}}}},
            {"name": "manage_user", "description": "Use your best judgment to manage users in the system somehow.",
             "inputSchema": {"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["create", "update", "delete"], "description": "What to do."},
                 "blob": {}}}, "annotations": {"readOnlyHint": True, "destructiveHint": True}},
        ]
        lv = levels(preflight.check("https://mcp.example.com/mcp", fetch=Fake(tools=bad, instructions="")))
        self.assertEqual(lv["dynamic-tools"], "fail")
        for k in ("annotations", "destructive", "annotation-clash", "descriptions", "discretion", "multi-action",
                  "param-types", "param-docs", "numeric-ids", "instructions"):
            self.assertEqual(lv[k], "warn", k)
        self.assertEqual(lv["versioned-path"], "info")

    def test_auth_required_checks_oauth(self):
        lv = levels(preflight.check(URL, fetch=Fake(auth=True)))
        self.assertEqual(lv["reach"], "info")
        self.assertEqual(lv["oauth-resource"], "fail")
        wk = {"/.well-known/oauth-protected-resource/mcp/v1": (200, {"authorization_servers": ["https://auth.example.com"]}),
              "/.well-known/oauth-authorization-server": (200, {
                  "authorization_endpoint": "https://auth.example.com/a", "token_endpoint": "https://auth.example.com/t",
                  "response_types_supported": ["code"], "code_challenge_methods_supported": ["S256"]})}
        r = preflight.check(URL, fetch=Fake(auth=True, wellknown=wk))
        lv = levels(r)
        self.assertEqual((lv["oauth-resource"], lv["oauth-server"], lv["oauth-dcr"]), ("pass", "pass", "warn"))
        self.assertIsNone(r["snapshot"])

    def test_domain_file(self):
        ok = {"/.well-known/google-connected-apps": (200, {"token": "abc"})}
        self.assertEqual(levels(preflight.check(URL, fetch=Fake(wellknown=ok)))["domain-file"], "pass")
        moved = {"/.well-known/google-connected-apps": (301, {})}
        self.assertEqual(levels(preflight.check(URL, fetch=Fake(wellknown=moved)))["domain-file"], "fail")

    def test_diff(self):
        a = preflight.check(URL, fetch=Fake())["snapshot"]
        self.assertEqual(preflight.diff(a, preflight.check(URL, fetch=Fake())["snapshot"]), [])
        tools = json.loads(json.dumps(GOOD_TOOLS))
        tools[0]["inputSchema"]["properties"]["limit"] = {"type": "integer", "description": "Max rows."}
        tools.append({"name": "new_tool", "description": "x"})
        del tools[1]
        b = preflight.check(URL, fetch=Fake(tools=tools, instructions="Changed."))["snapshot"]
        self.assertEqual(preflight.diff(a, b), ["Tool removed: cancel_order", "Tool added: new_tool",
                                               "Tool search_orders: arguments changed", "Server instructions changed"])

    def test_cli_drift_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            snap = pathlib.Path(d) / "s.json"
            real = preflight.http
            try:
                preflight.http = Fake()
                preflight.check.__defaults__ = (None, preflight.http)
                self.assertEqual(preflight.main([URL, "--save", str(snap)]), 0)
                self.assertEqual(preflight.main([URL, "--against", str(snap)]), 0)
                preflight.check.__defaults__ = (None, Fake(instructions="Different."))
                self.assertEqual(preflight.main([URL, "--against", str(snap)]), 1)
            finally:
                preflight.http = real
                preflight.check.__defaults__ = (None, real)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = service.connect(":memory:")
        self.mails = []
        self.mailer = lambda to, subject, body, token: self.mails.append((to, subject, body, token))
        self.ok = lambda url: None
        self.checker = lambda url: preflight.check(url, fetch=Fake())
        self.addCleanup(self.db.close)

    def test_guard_rejects_private_and_http(self):
        for url in ("http://example.com/mcp", "https://127.0.0.1/mcp", "https://localhost/mcp", "ftp://x"):
            with self.assertRaises(service.Rejected):
                service.guard(url)

    def test_check_counts_distinct_endpoints_without_storing_urls(self):
        for url in (URL, URL, "https://other.example.com/mcp"):
            service.run_check(self.db, url, checker=self.checker, guard=self.ok)
        s = service.stats(self.db)
        self.assertEqual((s["checks"], s["distinct_endpoints"]), (3, 2))
        self.assertNotIn("example.com", json.dumps([tuple(r) for r in self.db.execute("SELECT * FROM checks")]))

    def test_watch_lifecycle(self):
        with self.assertRaises(service.Rejected):
            service.add_watch(self.db, "nope", URL, checker=self.checker, guard=self.ok, mailer=self.mailer)
        service.add_watch(self.db, "Dev@Example.com", URL, True, checker=self.checker, guard=self.ok, mailer=self.mailer)
        self.assertEqual(len(self.mails), 1)
        token = self.mails[0][3]
        self.assertIn(token, self.mails[0][2])
        self.assertEqual(service.run_watches(self.db, checker=self.checker, guard=self.ok, mailer=self.mailer)["alerts"], 0)
        self.assertTrue(service.confirm(self.db, token))
        self.assertEqual(service.stats(self.db)["want_paid"], 1)
        with self.assertRaises(service.Rejected):  # free plan: one endpoint
            service.add_watch(self.db, "dev@example.com", "https://b.example.com/mcp", checker=self.checker,
                              guard=self.ok, mailer=self.mailer)
        same = service.run_watches(self.db, checker=self.checker, guard=self.ok, mailer=self.mailer)
        self.assertEqual(same, {"alerts": 0, "unreachable": 0})
        drifted = lambda url: preflight.check(url, fetch=Fake(instructions="New words."))
        self.assertEqual(service.run_watches(self.db, checker=drifted, guard=self.ok, mailer=self.mailer)["alerts"], 1)
        self.assertIn("Server instructions changed", self.mails[-1][2])
        # the same drift is not mailed twice
        self.assertEqual(service.run_watches(self.db, checker=drifted, guard=self.ok, mailer=self.mailer)["alerts"], 0)
        self.assertTrue(service.unsubscribe(self.db, token))
        self.assertEqual(service.stats(self.db)["watches_confirmed"], 0)

    def test_watch_needs_a_readable_tool_list(self):
        locked = lambda url: preflight.check(url, fetch=Fake(auth=True))
        with self.assertRaises(service.Rejected):
            service.add_watch(self.db, "a@example.com", URL, checker=locked, guard=self.ok, mailer=self.mailer)


class PageTests(unittest.TestCase):
    def test_build(self):
        with tempfile.TemporaryDirectory() as d:
            out = page.build(pathlib.Path(d))
            html = (out / "index.html").read_text()
            self.assertIn("not affiliated with or endorsed by Google", html)
            self.assertIn("operated by an AI agent", html)
            self.assertNotIn("Start Team", html)  # no payment link configured
            for f in ("style.css", "app.js", "preflight.py"):
                self.assertTrue((out / f).stat().st_size > 100, f)


if __name__ == "__main__":
    unittest.main()
