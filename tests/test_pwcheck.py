import hashlib, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import sps_pwcheck as P


def fake_service(leaked):
    """Pretends to be the range service; records what was sent."""
    sent = []
    table = {}
    for pw, n in leaked.items():
        h = hashlib.sha1(pw.encode()).hexdigest().upper()
        table.setdefault(h[:5], []).append("%s:%d" % (h[5:], n))
    def fetch(prefix):
        sent.append(prefix)
        return "\r\n".join(table.get(prefix, []) + ["0000000000000000000000000000000000A:2"])
    return fetch, sent


E = lambda i, site, pw, user="u": {"id": i, "site": site, "username": user, "password": pw}


class PwCheckTests(unittest.TestCase):
    def test_known_hash(self):
        self.assertEqual(hashlib.sha1(b"password").hexdigest().upper()[:5], "5BAA6")

    def test_only_five_characters_leave_the_computer(self):
        fetch, sent = fake_service({"Tr0ub4dor&3": 7})
        self.assertEqual(P.pwned_count("Tr0ub4dor&3", fetch), 7)
        self.assertEqual(P.pwned_count("never-leaked-pass-91!", fetch), 0)
        self.assertTrue(all(len(x) == 5 for x in sent))
        self.assertNotIn("Tr0ub4dor&3", "".join(sent))

    def test_issues_reused_weak_leaked(self):
        entries = [E(1, "a.com", "Sup3r-long-unique-1!"), E(2, "b.com", "Sh4red-pass-xyz!"), E(3, "c.com", "Sh4red-pass-xyz!"),
                   E(4, "d.com", "123456"), E(5, "e.com", "Leaked-pass-9988!")]
        fetch, _ = fake_service({"Leaked-pass-9988!": 1234})
        r = P.check_all(entries, fetch)
        kinds = [(i["kind"], i["site"]) for i in r["issues"]]
        self.assertIn(("leaked", "e.com"), kinds)
        self.assertIn(("reused", "b.com"), kinds); self.assertIn(("reused", "c.com"), kinds)
        self.assertIn(("weak", "d.com"), kinds)
        self.assertNotIn("a.com", [s for _, s in kinds])
        self.assertEqual(kinds[0][0], "leaked")                                   # worst first
        self.assertFalse(r["offline"])

    def test_offline_still_reports_local_problems(self):
        def boom(prefix): raise OSError("no internet")
        r = P.check_all([E(1, "a.com", "123456"), E(2, "b.com", "x"), E(3, "c.com", "x")], boom)
        self.assertTrue(r["offline"])
        self.assertTrue(any(i["kind"] == "weak" for i in r["issues"])); self.assertTrue(any(i["kind"] == "reused" for i in r["issues"]))
        self.assertFalse(any(i["kind"] == "leaked" for i in r["issues"]))

    def test_same_password_is_looked_up_once(self):
        fetch, sent = fake_service({})
        P.check_all([E(1, "a", "Same-Pass-12345!"), E(2, "b", "Same-Pass-12345!")], fetch)
        self.assertEqual(len(sent), 1)

    def test_weakness(self):
        for w in ("password", "abc", "11111111", "abcdefgh", "aaaaaaaaaaaa"):
            self.assertTrue(P.weakness(w), w)
        self.assertEqual(P.weakness("Correct-horse-battery-7"), "")


if __name__ == "__main__":
    unittest.main()
