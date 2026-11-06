import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import sps_signin as g


class SignInDetect(unittest.TestCase):
    def test_signin_pages_are_caught(self):
        for u in ("https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fwww.youtube.com",
                  "https://accounts.google.com/v3/signin/identifier?flowName=GlifWebSignIn",
                  "https://accounts.google.com/signin/v2/identifier",
                  "https://accounts.google.com/signin",
                  "https://accounts.google.com/AccountChooser?continue=x",
                  "https://accounts.google.com/o/oauth2/v2/auth?client_id=1&response_type=code",
                  "HTTPS://Accounts.Google.com/SignIn/rejected"):
            self.assertTrue(g.is_google_signin(u), u)

    def test_other_pages_are_not(self):
        for u in ("https://www.youtube.com/", "https://www.google.com/search?q=accounts.google.com/signin",
                  "https://accounts.google.com/Logout", "https://myaccount.google.com/",
                  "https://accounts.google.com.evil.example/signin", "ftp://accounts.google.com/signin", "", "not a url"):
            self.assertFalse(g.is_google_signin(u), u)

    def test_texts(self):
        self.assertEqual(g.MESSAGE, "Google blocks sign-in here. Open it in your default browser, or continue without signing in.")
        self.assertIn("You don't need to sign in to watch YouTube", g.HINT)
        for t in (g.TITLE, g.MESSAGE, g.HINT, g.BTN_OPEN, g.BTN_SKIP, g.BTN_TRY):
            self.assertTrue(t.isascii() or "🌐" in t or "▶" in t)


if __name__ == "__main__":
    unittest.main()
