import datetime as dt
import hashlib, hmac, json, os, pathlib, tempfile, threading, time, unittest, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

from sunset import alerts, build, events, registry, scan, server

D = dt.date.fromisoformat


def reg():
    return {"schema": 1, "changes": [], "providers": [
        {"id": "acme", "name": "Acme", "kind": "first-party", "source_url": "https://acme.test/dep",
         "verified": "2026-11-01", "note": None},
        {"id": "todo", "name": "Todo", "kind": "cloud", "source_url": "https://todo.test", "verified": None, "note": None}],
        "models": [
        {"provider": "acme", "id": "a-1", "state": "retired", "deprecated": "2026-01-01", "retires": "2026-03-01", "not_before": None, "replacement": "a-3"},
        {"provider": "acme", "id": "a-2", "state": "deprecated", "deprecated": "2026-10-01", "retires": "2026-12-01", "not_before": None, "replacement": "a-3"},
        {"provider": "acme", "id": "a-2-5", "state": "deprecated", "deprecated": "2026-10-01", "retires": None, "not_before": None, "replacement": None},
        {"provider": "acme", "id": "a-3", "state": "active", "deprecated": None, "retires": None, "not_before": "2027-06-01", "replacement": None}]}


class Registry(unittest.TestCase):
    def test_real_registry_is_valid(self):
        r = registry.load()
        self.assertGreater(len(r["models"]), 30)

    def test_status_and_order(self):
        v = registry.view(reg(), D("2026-11-16"))
        self.assertEqual([(m["id"], m["status"]) for m in v],
                         [("a-2", "retiring"), ("a-2-5", "deprecated"), ("a-3", "active"), ("a-1", "retired")])
        self.assertEqual(v[0]["days_left"], 15)
        self.assertEqual(registry.status(reg()["models"][1], D("2026-12-01")), "retired")

    def test_not_before_is_never_a_retirement(self):
        m = reg()["models"][3]
        self.assertEqual(registry.status(m, D("2028-01-01")), "active")
        self.assertIsNone(registry.days_left(m, D("2028-01-01")))

    def test_rejects_unverified_and_bad_data(self):
        r = reg(); r["models"].append(dict(r["models"][0], provider="todo"))
        with self.assertRaises(ValueError): registry.validate(r)
        r = reg(); r["models"][1]["retires"] = "2026-13-01"
        with self.assertRaises(ValueError): registry.validate(r)
        r = reg(); r["models"][3]["retires"] = "2027-01-01"
        with self.assertRaises(ValueError): registry.validate(r)
        r = reg(); r["models"][1]["retires"] = "2026-09-01"
        with self.assertRaises(ValueError): registry.validate(r)

    def test_apply_snapshot_records_changes(self):
        r = reg()
        rows = [{"id": "a-2", "state": "deprecated", "deprecated": "2026-10-01", "retires": "2027-01-15", "replacement": "a-3"},
                {"id": "a-3", "state": "active", "not_before": "2027-06-01"},
                {"id": "a-4", "state": "active"}]
        ch = registry.apply_snapshot(r, "acme", rows, D("2026-11-20"))
        kinds = {(c["id"], c["field"]) for c in ch}
        self.assertEqual(kinds, {("a-2", "retires"), ("a-4", "added"), ("a-2-5", "missing_from_source")})
        self.assertEqual(len(r["models"]), 5)  # retired a-1 and unlisted a-2-5 are kept
        self.assertEqual(r["providers"][0]["verified"], "2026-11-20")
        moved = [e for e in events.events(r, D("2026-11-20")) if e["type"] == "date_changed"]
        self.assertIn("from 2026-12-01 to 2027-01-15", moved[0]["text"])


class Events(unittest.TestCase):
    def test_events_and_posts(self):
        ev = events.events(reg(), D("2026-11-16"))
        self.assertEqual([e["type"] for e in ev], ["deprecated", "deprecated", "retired", "deprecated"])
        self.assertEqual(events.posts(reg(), D("2026-11-16"), "https://s.test"), [])
        p = events.posts(reg(), D("2026-11-24"), "https://s.test")
        self.assertEqual(len(p), 1)
        self.assertIn("retires in 7 days", p[0]["text"])
        self.assertTrue(p[0]["text"].endswith("https://s.test/models/acme/a-2/"))
        day = events.posts(reg(), D("2026-12-01"), "https://s.test")
        self.assertEqual(len(day), 1); self.assertIn("retired a-2", day[0]["text"])
        self.assertLessEqual(len(events._fit("x" * 400, "https://s.test/")) - len("https://s.test/") + 23, 280)


class Scan(unittest.TestCase):
    def test_scan_boundaries_and_exit(self):
        models = reg()["models"]
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "app.py").write_text('m = "a-2"\nold = "a-1"\nn = "a-2-5"\nx = "data-2"\ny="a-3."\n')
            (p / "node_modules").mkdir(); (p / "node_modules" / "x.js").write_text('"a-1"')
            (p / "bin.dat").write_bytes(b"\0a-1")
            hits = scan.scan([d], models, D("2026-11-16"))
            self.assertEqual([(h["line"], h["id"], h["status"]) for h in hits],
                             [(1, "a-2", "retiring"), (2, "a-1", "retired"), (3, "a-2-5", "deprecated"), (5, "a-3", "active")])
            self.assertTrue(scan.failing(hits[1], 0)); self.assertFalse(scan.failing(hits[0], 14))
            self.assertTrue(scan.failing(hits[0], 15)); self.assertFalse(scan.failing(hits[2], 999))
            regfile = p / "models.json"; regfile.write_text(json.dumps({"models": models}))
            self.assertEqual(scan.main(["scan", str(p / "app.py"), "--registry", str(regfile)]), 1)
            (p / "ok.py").write_text('"a-3"')
            self.assertEqual(scan.main(["scan", str(p / "ok.py"), "--registry", str(regfile)]), 0)
            self.assertEqual(scan.main(["scan", d, "--registry", str(p / "missing.json")]), 2)


class Alerts(unittest.TestCase):
    def setUp(self):
        self.db = alerts.connect(":memory:")
        self.mail = []
        self.mailer = lambda to, subj, body, token: self.mail.append((to, subj, body))

    def sub(self, email="A@x.io", models="acme/a-2", confirm=True):
        r = alerts.subscribe(self.db, email, models, reg(), self.mailer)
        if confirm: alerts.confirm(self.db, r["token"])
        return r

    def test_double_opt_in(self):
        r = self.sub(confirm=False)
        self.assertEqual(len(self.mail), 1); self.assertIn("/api/confirm?token=" + r["token"], self.mail[0][2])
        self.assertEqual(alerts.notify(self.db, reg(), D("2026-11-16"), self.mailer)["email"], 0)
        self.assertTrue(alerts.confirm(self.db, r["token"])); self.assertFalse(alerts.confirm(self.db, "nope"))
        self.assertEqual(alerts.notify(self.db, reg(), D("2026-11-16"), self.mailer)["email"], 1)

    def test_validation_and_limits(self):
        for email, models in (("bad", "acme/a-2"), ("a@x.io", ""), ("a@x.io", "acme/nope"),
                              ("a@x.io", "acme/*"), ("a@x.io", "acme/a-1,acme/a-2,acme/a-2-5,acme/a-3")):
            with self.assertRaises(alerts.Rejected): alerts.subscribe(self.db, email, models, reg(), self.mailer)
        self.sub(models="acme/a-1, acme/a-2")
        self.sub(models="acme/a-2 acme/a-3")  # merge, dedupe -> 3
        with self.assertRaises(alerts.Rejected): self.sub(models="acme/a-2-5")
        self.assertEqual(alerts.stats(self.db)["watches"], 3)
        self.assertEqual(alerts.stats(self.db)["confirmed"], 1)

    def test_stages_fire_once_each(self):
        self.sub(); self.mail.clear()
        subjects = []
        day = D("2026-09-25")
        r = reg()
        while day <= D("2026-12-06"):
            alerts.notify(self.db, r, day, self.mailer); day += dt.timedelta(days=1)
        subjects = [m[1] for m in self.mail]
        self.assertEqual(subjects, ["a-2 will be retired on 2026-12-01", "a-2 retires in 60 days", "a-2 retires in 30 days",
                                    "a-2 retires in 7 days", "a-2 retires tomorrow", "a-2 has been retired"])
        self.assertIn("https://acme.test/dep", self.mail[0][2]); self.assertIn("unsubscribe?token=", self.mail[0][2])

    def test_late_subscriber_gets_one_current_notice_and_missed_runs_recover(self):
        self.sub(); self.mail.clear()
        alerts.notify(self.db, reg(), D("2026-11-16"), self.mailer)
        self.assertEqual([m[1] for m in self.mail], ["a-2 retires in 15 days"])
        alerts.notify(self.db, reg(), D("2026-12-03"), self.mailer)  # runs missed for 2 weeks
        self.assertEqual(self.mail[-1][1], "a-2 has been retired"); self.assertEqual(len(self.mail), 2)
        self.sub(email="late@x.io", models="acme/a-1"); self.mail.clear()
        self.assertEqual(alerts.notify(self.db, reg(), D("2026-12-03"), self.mailer)["email"], 0)  # long retired

    def test_date_change_renotifies_and_failed_send_retries(self):
        self.sub(); alerts.notify(self.db, reg(), D("2026-11-16"), self.mailer); self.mail.clear()
        r = reg(); r["models"][1]["retires"] = "2026-12-20"
        alerts.notify(self.db, r, D("2026-11-17"), self.mailer)
        self.assertEqual([m[1] for m in self.mail], ["a-2 retires in 33 days"])
        def boom(*a): raise OSError("smtp down")
        self.assertEqual(alerts.notify(self.db, r, D("2026-11-21"), boom)["failed"], 1)
        self.assertEqual(alerts.notify(self.db, r, D("2026-11-21"), self.mailer)["email"], 1)

    def test_pro_wildcards_webhook_and_downgrade(self):
        r = self.sub()
        alerts.set_plan(self.db, "a@x.io", "pro", "cus_1")
        posts = []
        orig = alerts.check_webhook_url; alerts.check_webhook_url = lambda u: None
        try:
            me = alerts.manage(self.db, r["token"], "acme/*", "https://hooks.test/x", reg())
        finally:
            alerts.check_webhook_url = orig
        self.assertEqual(me["watches"], ["acme/*"])
        c = alerts.notify(self.db, reg(), D("2026-11-16"), self.mailer, lambda u, p: posts.append(p))
        self.assertEqual((c["email"], c["webhook"]), (2, 2))  # a-2 retiring + a-2-5 deprecated
        self.assertEqual(posts[0]["model"], "a-2"); self.assertIn("text", posts[0])
        self.assertEqual(alerts.downgrade_customer(self.db, "cus_1"), 1)
        self.assertEqual(alerts.notify(self.db, reg(), D("2026-11-25"), self.mailer)["email"], 0)  # wildcard no longer covered
        with self.assertRaises(alerts.Rejected): alerts.manage(self.db, r["token"], "acme/a-2", "https://hooks.test/x", reg())

    def test_webhook_url_guard(self):
        for bad in ("http://example.com/x", "https://127.0.0.1/x", "https://localhost/x", "https://10.0.0.5/x",
                    "https://169.254.169.254/latest", "https://u:p@example.com/", "ftp://x"):
            with self.assertRaises(alerts.Rejected, msg=bad): alerts.check_webhook_url(bad)

    def test_unsubscribe_deletes_everything(self):
        r = self.sub(); alerts.notify(self.db, reg(), D("2026-11-16"), self.mailer)
        self.assertTrue(alerts.unsubscribe(self.db, r["token"]))
        s = alerts.stats(self.db)
        self.assertEqual((s["confirmed"], s["watches"], s["notifications_sent"]), (0, 0, 0))

    def test_outbox_mail_has_unsubscribe_headers(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["SUNSET_OUTBOX"] = d; os.environ.pop("SMTP_HOST", None)
            alerts.send_mail("a@x.io", "s", "b", "tok")
            eml = next(pathlib.Path(d).iterdir()).read_text()
            self.assertIn("List-Unsubscribe-Post: List-Unsubscribe=One-Click", eml); self.assertIn("token=tok", eml)
            del os.environ["SUNSET_OUTBOX"]


class Stripe(unittest.TestCase):
    def test_signature(self):
        body, secret, now = b'{"a":1}', "whsec_x", 1_800_000_000
        sig = hmac.new(secret.encode(), f"{now}.".encode() + body, hashlib.sha256).hexdigest()
        self.assertTrue(server.verify_stripe(body, f"t={now},v1={sig}", secret, now + 10))
        self.assertFalse(server.verify_stripe(body, f"t={now},v1={sig}", secret, now + 1000))
        self.assertFalse(server.verify_stripe(body + b" ", f"t={now},v1={sig}", secret, now))
        self.assertFalse(server.verify_stripe(body, f"t={now},v1={sig}", "other", now))
        self.assertFalse(server.verify_stripe(body, "", secret, now))

    def test_upgrade_and_cancel(self):
        db = alerts.connect(":memory:"); mail = []
        m = lambda *a: mail.append(a)
        out = server.handle_stripe(db, {"type": "checkout.session.completed", "data": {"object": {
            "customer": "cus_9", "customer_details": {"email": "New@x.io"}}}}, m)
        self.assertEqual(out, "upgraded"); self.assertEqual(alerts.stats(db)["pro"], 1); self.assertIn("/manage/?token=", mail[0][2])
        self.assertEqual(server.handle_stripe(db, {"type": "customer.subscription.deleted", "data": {"object": {"customer": "cus_9"}}}, m), "downgraded 1")
        self.assertEqual(alerts.stats(db)["pro"], 0)
        self.assertEqual(server.handle_stripe(db, {"type": "invoice.paid", "data": {"object": {}}}, m), "ignored")


class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SUNSET_DB"] = os.path.join(cls.tmp.name, "t.db")
        os.environ["SUNSET_ADMIN_KEY"] = "k"; os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_t"
        cls.mail = []
        server.Handler.mailer = staticmethod(lambda to, s, b, t: cls.mail.append((to, s, b, t)))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); server.Handler.mailer = None; cls.tmp.cleanup()
        for k in ("SUNSET_DB", "SUNSET_ADMIN_KEY", "STRIPE_WEBHOOK_SECRET"): os.environ.pop(k)

    def call(self, path, data=None, headers=None, raw=None):
        body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        req = urllib.request.Request(self.base + path, data=body, headers=headers or ({"Content-Type": "application/json"} if data is not None else {}))
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k): return None
        try:
            r = urllib.request.build_opener(NoRedirect).open(req)
            return r.status, json.loads(r.read() or b"{}"), r.headers
        except urllib.error.HTTPError as e:
            txt = e.read()
            return e.code, (json.loads(txt) if txt else {}), e.headers

    def test_flow(self):
        server._hits.clear()
        self.assertEqual(self.call("/api/health")[0], 200)
        self.assertEqual(self.call("/api/subscribe", {"email": "nope", "models": "x"})[0], 400)
        n = len(self.mail)
        self.assertEqual(self.call("/api/subscribe", {"email": "bot@x.io", "models": "anthropic/claude-sonnet-4-6", "website": "spam"})[0], 200)
        self.assertEqual(len(self.mail), n)  # honeypot: nothing stored or sent
        code, body, _ = self.call("/api/subscribe", {"email": "h@x.io", "models": "anthropic/claude-sonnet-4-6"})
        self.assertEqual(code, 200); token = self.mail[-1][3]
        code, _, h = self.call("/api/subscribe", raw=b"email=f%40x.io&models=anthropic%2Fclaude-opus-4-6", headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual((code, h["Location"]), (303, "/check-email/"))
        code, _, h = self.call(f"/api/confirm?token={token}"); self.assertEqual((code, h["Location"]), (303, "/confirmed/"))
        self.assertEqual(self.call(f"/api/me?token={token}")[1]["watches"], ["anthropic/claude-sonnet-4-6"])
        self.assertEqual(self.call("/api/me?token=bad")[0], 404)
        code, body, _ = self.call("/api/manage", {"token": token, "models": "anthropic/claude-opus-4-6", "webhook": ""})
        self.assertEqual(body["watches"], ["anthropic/claude-opus-4-6"])
        self.assertEqual(self.call("/api/manage", {"token": token, "models": "anthropic/*"})[0], 400)
        self.assertEqual(self.call("/api/stats?key=k")[1]["confirmed"], 1)
        self.assertEqual(self.call("/api/stats?key=wrong")[0], 404)
        self.assertEqual(self.call("/api/subscribe", raw=b"x" * 20000, headers={"Content-Type": "application/json"})[0], 413)
        ev = json.dumps({"type": "checkout.session.completed", "data": {"object": {"customer": "c", "customer_details": {"email": "h@x.io"}}}}).encode()
        ts = str(int(time.time())); sig = hmac.new(b"whsec_t", ts.encode() + b"." + ev, hashlib.sha256).hexdigest()
        self.assertEqual(self.call("/api/stripe", raw=ev, headers={"Stripe-Signature": "t=1,v1=bad"})[0], 400)
        self.assertEqual(self.call("/api/stripe", raw=ev, headers={"Stripe-Signature": f"t={ts},v1={sig}"})[1]["result"], "upgraded")
        self.assertEqual(self.call(f"/api/me?token={token}")[1]["plan"], "pro")
        self.assertEqual(self.call(f"/api/unsubscribe?token={token}", raw=b"List-Unsubscribe=One-Click", headers={"Content-Type": "application/x-www-form-urlencoded"})[0], 200)
        self.assertEqual(self.call(f"/api/me?token={token}")[0], 404)

    def test_rate_limit(self):
        server._hits.clear()
        codes = [self.call("/api/subscribe", {"email": "nope", "models": "x"})[0] for _ in range(8)]
        self.assertEqual(codes[:6], [400] * 6); self.assertEqual(codes[6:], [429, 429])
        server._hits.clear()


class Parsers(unittest.TestCase):
    def run_parser(self, name, html, today="2026-11-16"):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ps", pathlib.Path(__file__).parent.parent / "tools/parse_sources.py")
        ps = importlib.util.module_from_spec(spec); spec.loader.exec_module(ps)
        t = ps.Tables(); t.feed(html)
        return {r["id"]: r for r in ps.PARSERS[name](t.tables, D(today))}

    def test_openai(self):
        r = self.run_parser("openai", """<h2>Upcoming</h2><table><tr><th>Shutdown date</th><th>Affected model</th><th>Status</th><th>Recommended replacement</th><th>Notice date</th></tr>
<tr><td>Dec 11, 2026</td><td>GPT-9 (<code>gpt-9</code>, gpt-9-2025-08-07)</td><td>Deprecated</td><td>gpt-10</td><td>Jun 11, 2026</td></tr>
<tr><td>Soon</td><td>gpt-x-1</td><td>Deprecated</td><td>y</td><td>Jun 11, 2026</td></tr></table>
<h2>Past</h2><table><tr><th>Shutdown date</th><th>Affected model or feature</th><th>Listed replacement</th><th>Notice date</th></tr>
<tr><td>Sep 24, 2026</td><td>Videos API</td><td>None</td><td>Mar 24, 2026</td></tr>
<tr><td>Jan 4, 2024</td><td>ada-code-001 Historical price $4.00 / 1M tokens</td><td>emb-3</td><td>Jul 6, 2023</td></tr>
<tr><td>Jan 4, 2020</td><td>gpt-9</td><td>old</td><td>Jul 6, 2019</td></tr></table>""")
        self.assertEqual(set(r), {"gpt-9", "gpt-9-2025-08-07", "ada-code-001"})
        self.assertEqual((r["gpt-9"]["state"], r["gpt-9"]["retires"], r["gpt-9"]["deprecated"], r["gpt-9"]["replacement"]), ("deprecated", "2026-12-11", "2026-06-11", "gpt-10"))
        self.assertEqual(r["ada-code-001"]["state"], "retired")

    def test_vertex_soft_dates_and_ambiguous_rows(self):
        head = "<tr><th>Model ID</th><th>Release date</th><th>Retirement date</th><th>Replacement model ID</th></tr>"
        r = self.run_parser("vertex", f"""<h2>Gemini models</h2><table>{head}
<tr><td>g-4</td><td>x</td><td>October 13, 2027 or later</td><td></td></tr><tr><td>g-emb</td><td>x</td><td>No sooner than May 20, 2028</td><td></td></tr>
<tr><td>g-new</td><td>x</td><td>No retirement date announced</td><td></td></tr><tr><td>g-3</td><td>x</td><td>January 28, 2027</td><td>g-4</td></tr>
<tr><td>g-2</td><td>x</td><td>October 20, 2026</td><td>g-4</td></tr></table>
<summary>The following table lists the retired models</summary><table>{head}<tr><td>g-1@001*</td><td>x</td><td>June 1, 2026</td><td>g-3</td></tr></table>""")
        self.assertEqual(set(r), {"g-4", "g-emb", "g-new", "g-3", "g-1@001"})  # g-2: past date but still listed -> left out
        self.assertEqual((r["g-4"]["retires"], r["g-4"]["not_before"]), (None, "2027-10-13"))
        self.assertEqual(r["g-emb"]["not_before"], "2028-05-20")
        self.assertEqual((r["g-3"]["retires"], r["g-1@001"]["state"]), ("2027-01-28", "retired"))

    def test_mistral_and_azure(self):
        r = self.run_parser("mistral", """<h2>Deprecated &amp; retired models</h2><table>
<tr><td>M Large</td><td>25.12</td><td>m-large-2512</td><td><span>10/31/2026</span><span>4/30/2027</span></td><td>M Large 4</td></tr>
<tr><td>M Odd</td><td>1</td><td>m-odd</td><td>10/31/2026</td><td></td></tr></table>""")
        self.assertEqual(list(r), ["m-large-2512"]); self.assertEqual((r["m-large-2512"]["deprecated"], r["m-large-2512"]["retires"]), ("2026-10-31", "2027-04-30"))
        r = self.run_parser("azure", """<h2>Azure OpenAI</h2><table><tr><th>Model</th><th>Version</th><th>Lifecycle</th><th>Retirement date</th><th>Replacement</th></tr>
<tr><td>g</td><td>1</td><td>GA</td><td>2027-04-14<sup>3</sup></td><td>—</td></tr><tr><td>g</td><td>0</td><td>Retired</td><td>2026-06-29</td><td>g2</td></tr>
<tr><td>late</td><td>1</td><td>GA</td><td>2026-10-15</td><td>—</td></tr><tr><td>dup</td><td>1</td><td>GA</td><td>2027-01-01</td><td>—</td></tr><tr><td>dup</td><td>1</td><td>GA</td><td>2027-02-01</td><td>—</td></tr></table>
<h2>Cohere</h2><table><tr><th>Model</th><th>Version</th><th>Lifecycle</th><th>Retirement date</th><th>Replacement</th></tr><tr><td>c</td><td>1</td><td>GA</td><td>2027-04-14</td><td>—</td></tr></table>""")
        self.assertEqual(set(r), {"g@1", "g@0"}); self.assertEqual((r["g@1"]["retires"], r["g@1"]["replacement"], r["g@0"]["state"]), ("2027-04-14", None, "retired"))


class Build(unittest.TestCase):
    def test_build_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "dist"
            info = build.build(out, D("2026-11-16"))
            self.assertGreater(info["pages"], 40)
            home = (out / "index.html").read_text()
            self.assertIn("claude-sonnet-4-5-20250929", home); self.assertIn("in 14 days", home)
            self.assertIn("pending verification", home)
            api = json.loads((out / "api/v1/models.json").read_text())
            s45 = next(m for m in api["models"] if m["id"] == "claude-sonnet-4-5-20250929")
            self.assertEqual((s45["status"], s45["days_left"], s45["retires"]), ("retiring", 14, "2026-11-30"))
            self.assertTrue(all(m["retires"] is None for m in api["models"] if m["not_before"]))
            self.assertEqual(scan.scan([str(out / "models/anthropic/claude-opus-4-1-20250805")], api["models"], D("2026-11-16"))[0]["status"], "retired")
            ics = (out / "calendar.ics").read_bytes().decode()
            self.assertIn("\r\n", ics)
            self.assertIn("DTSTART;VALUE=DATE:20261130", ics); self.assertNotIn("20271109", ics)
            self.assertTrue(all(len(l.encode()) <= 75 for l in ics.split("\r\n")))
            import xml.dom.minidom
            xml.dom.minidom.parse(str(out / "feed.xml")); xml.dom.minidom.parse(str(out / "sitemap.xml"))
            for f in ("providers/anthropic/index.html", "models/anthropic/claude-2.1/index.html", "manage/index.html",
                      "cli/modelsunset.py", "calendar/anthropic.ics", "robots.txt", "llms.txt", "style.css"):
                self.assertTrue((out / f).exists(), f)
            self.assertFalse((out / "providers/groq").exists())  # unverified providers get no page


if __name__ == "__main__":
    unittest.main()
