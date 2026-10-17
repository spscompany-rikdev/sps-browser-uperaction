import os, sys, hashlib, json, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import sps_ed25519, sps_updater as U

SK = bytes(range(32)); PK = sps_ed25519.public_key(SK).hex()
DATA = b"MZ fake installer bytes" * 100

def block(version="37.0.0", data=DATA, url="https://example.com/s.exe", mandatory=True, sk=SK, tamper=None):
    info = {"version": version, "url": url, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "mandatory": mandatory}
    sig = sps_ed25519.sign(sk, U.canonical_message(info)).hex()
    if tamper: info.update(tamper)
    return ("SPS-UPDATE-BEGIN\nversion: %s\nurl: %s\nsha256: %s\nsize: %d\nmandatory: %s\nsignature: %s\nnotes: Fixes\nSPS-UPDATE-END"
            % (info["version"], info["url"], info["sha256"], info["size"], "yes" if info["mandatory"] else "no", sig))

class Resp:
    def __init__(s, data): s.data, s.history, s.url = data, [], "https://example.com/s.exe"
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def raise_for_status(s): pass
    def iter_content(s, n):
        for i in range(0, len(s.data), n): yield s.data[i:i+n]
class Sess:
    def __init__(s, data): s.data = data
    def get(s, url, **k): return Resp(s.data)

class T(unittest.TestCase):
    def test_rfc(self): self.assertTrue(sps_ed25519.self_test())
    def test_version(self):
        self.assertTrue(U.is_newer("36.0.1", "36.0.0")); self.assertFalse(U.is_newer("36.0.0", "36.0.0"))
        self.assertFalse(U.is_newer("35.9", "36.0.0")); self.assertIsNone(U.parse_version("abc"))
    def test_valid(self):
        i = U.best_valid_update("<p>hello</p>" + block(), "36.0.0", PK)
        self.assertEqual(i["version"], "37.0.0"); self.assertTrue(i["mandatory"])
    def test_google_sites_escaping(self):
        raw = block().replace("\n", "\\n").replace("/", "\\/")
        self.assertIsNotNone(U.best_valid_update('<script>x="' + raw + '"</script>', "36.0.0", PK))
    def test_html_wrapped(self):
        raw = "<div>" + block().replace("\n", "</div><div>") + "</div>"
        self.assertIsNotNone(U.best_valid_update(raw, "36.0.0", PK))
    def test_rejects(self):
        self.assertIsNone(U.best_valid_update(block(), "37.0.0", PK))                       # not newer
        self.assertIsNone(U.best_valid_update(block(), "36.0.0", sps_ed25519.public_key(bytes(32)).hex()))  # wrong key
        self.assertIsNone(U.best_valid_update(block(sk=bytes(32)), "36.0.0", PK))            # signed by someone else
        self.assertIsNone(U.best_valid_update(block(tamper={"url": "https://evil.com/x.exe"}), "36.0.0", PK))
        self.assertIsNone(U.best_valid_update(block(tamper={"sha256": "a" * 64}), "36.0.0", PK))
        self.assertIsNone(U.best_valid_update(block(tamper={"mandatory": False}), "36.0.0", PK))
        self.assertIsNone(U.best_valid_update(block(url="http://example.com/s.exe"), "36.0.0", PK))
        self.assertIsNone(U.best_valid_update(block(), "36.0.0", "0" * 64))                  # no key configured
    def test_newest_wins(self):
        i = U.best_valid_update(block("37.0.0") + "\n" + block("38.1.0") + "\n" + block("36.5.0"), "36.0.0", PK)
        self.assertEqual(i["version"], "38.1.0")
    def _updater(self, d, page, data=DATA, monkey=True):
        u = U.SpsUpdater("36.0.0", d, public_key_hex=PK)
        U.fetch_page = lambda url=None, timeout=20: page
        U._session = lambda: Sess(data)
        return u
    def test_stage_flow(self):
        with tempfile.TemporaryDirectory() as d:
            u = self._updater(d, block())
            k, info = u.check_and_stage(); self.assertEqual(k, "staged")
            self.assertEqual(u.check_and_stage()[0], "ready")
            self.assertEqual(U.SpsUpdater("36.0.0", d, public_key_hex=PK).staged_update()["version"], "37.0.0")
            self.assertIsNone(U.SpsUpdater("37.0.0", d, public_key_hex=PK).staged_update())  # already installed
            with open(info["path"], "ab") as f: f.write(b"x")                                # tampered on disk
            self.assertIsNone(u.staged_update())
    def test_bad_download_discarded(self):
        with tempfile.TemporaryDirectory() as d:
            u = self._updater(d, block(), data=b"E" * len(DATA))
            self.assertEqual(u.check_and_stage()[0], "error")
            self.assertEqual([f for f in os.listdir(os.path.join(d, "updates"))], [])
    def test_oversize_download(self):
        with tempfile.TemporaryDirectory() as d:
            u = self._updater(d, block(), data=DATA + b"extra")
            self.assertEqual(u.check_and_stage()[0], "error")
    def test_uptodate_and_lock(self):
        with tempfile.TemporaryDirectory() as d:
            u = self._updater(d, "nothing here"); self.assertEqual(u.check_and_stage()[0], "uptodate")
            open(u._lock_path, "w").close(); self.assertEqual(u.check_and_stage()[0], "busy")
    def test_no_launch_off_windows(self):
        with tempfile.TemporaryDirectory() as d:
            u = self._updater(d, block()); _, info = u.check_and_stage()
            if sys.platform != "win32": self.assertFalse(u.launch_installer(info))

if __name__ == "__main__": unittest.main()
