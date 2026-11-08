"""Password vault lock: pure logic (no Qt needed)."""
import os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import sps_vault as V


class VaultLockTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.lk = V.VaultLock(self.d)

    def test_set_verify_and_persist(self):
        self.assertFalse(self.lk.is_set()); self.assertFalse(self.lk.needs_unlock())
        self.lk.set_password("hello-123")
        self.assertTrue(self.lk.is_set()); self.assertFalse(self.lk.needs_unlock())     # just set -> open this session
        raw = open(os.path.join(self.d, "vault_lock.json")).read()
        self.assertNotIn("hello-123", raw)                                              # never stored in clear
        again = V.VaultLock(self.d)                                                     # next browser start
        self.assertTrue(again.needs_unlock())
        self.assertFalse(again.verify("wrong")); self.assertTrue(again.needs_unlock())
        self.assertTrue(again.verify("hello-123")); self.assertFalse(again.needs_unlock())
        again.lock(); self.assertTrue(again.needs_unlock())

    def test_short_password_refused(self):
        with self.assertRaises(ValueError):
            self.lk.set_password("abc")

    def test_guessing_is_slowed(self):
        self.lk.set_password("secret-pass")
        lk = V.VaultLock(self.d)
        for _ in range(5):
            self.assertFalse(lk.verify("nope"))
        self.assertGreater(lk.wait_seconds(), 0)
        self.assertFalse(lk.verify("secret-pass"))                                      # even the right one waits
        lk._wait_until = 0
        self.assertTrue(lk.verify("secret-pass"))

    def test_remove(self):
        self.lk.set_password("secret-pass"); lk = V.VaultLock(self.d)
        lk.remove()
        self.assertFalse(lk.is_set()); self.assertFalse(V.VaultLock(self.d).is_set())


class OtpTests(unittest.TestCase):
    def test_code_works_once(self):
        o = V.Otp(); c = o.new()
        self.assertRegex(c, r"^\d{6}$")
        self.assertEqual(o.check("000000" if c != "000000" else "111111"), "wrong")
        self.assertEqual(o.check(c), "ok")
        self.assertEqual(o.check(c), "expired")                                         # used up

    def test_five_wrong_tries_lock_the_code(self):
        o = V.Otp(); c = o.new(); bad = "000000" if c != "000000" else "111111"
        r = [o.check(bad) for _ in range(5)]
        self.assertEqual(r[-1], "locked")
        self.assertEqual(o.check(c), "locked")                                          # even the right code is dead now

    def test_expiry_and_resend_wait(self):
        o = V.Otp(); c = o.new()
        self.assertIsNone(o.new())                                                      # too fast
        o._exp = time.time() - 1
        self.assertEqual(o.check(c), "expired")
        o._sent = time.time() - 100
        self.assertIsNotNone(o.new())

    def test_codes_are_random(self):
        seen = set()
        for _ in range(30):
            o = V.Otp(); seen.add(o.new())
        self.assertGreater(len(seen), 25)


if __name__ == "__main__":
    unittest.main()


class NotifyTests(unittest.TestCase):
    """The code is sent with each system's own notifier (commands are faked here)."""
    class _MW: tray = None

    def _run(self, system, which_ok=True):
        import platform, shutil, subprocess
        calls = []
        class R: returncode = 0
        o = (platform.system, shutil.which, subprocess.run)
        platform.system = lambda: system
        shutil.which = lambda n: ("/usr/bin/" + n) if which_ok else None
        subprocess.run = lambda cmd, **k: (calls.append(cmd), R())[1]
        try:
            return V.send_code(self._MW(), "123456"), calls
        finally:
            platform.system, shutil.which, subprocess.run = o

    def test_linux(self):
        ok, calls = self._run("Linux")
        self.assertTrue(ok); self.assertIn("notify-send", calls[0][0]); self.assertTrue(any("123456" in a for a in calls[0]))

    def test_macos(self):
        ok, calls = self._run("Darwin")
        self.assertTrue(ok); self.assertIn("osascript", calls[0][0]); self.assertIn("123456", calls[0][2])

    def test_windows(self):
        ok, calls = self._run("Windows")
        self.assertTrue(ok); self.assertIn("powershell", calls[0][0]); self.assertIn("123456", calls[0][-1])

    def test_no_notifier_means_no_code_anywhere(self):
        ok, calls = self._run("Linux", which_ok=False)
        self.assertFalse(ok); self.assertEqual(calls, [])
