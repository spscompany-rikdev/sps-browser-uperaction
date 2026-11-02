"""Real (executed) tests for the Android build: Shield logic on a JVM, the password-hook JS in Chromium, and wiring checks."""
import os, re, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JAVA = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "spscompany", "spsbrowser")
sys.path.insert(0, os.path.join(ROOT, "src"))


def _main():
    return open(os.path.join(JAVA, "MainActivity.java"), encoding="utf-8").read()


class CardsAndQuotesTests(unittest.TestCase):
    def test_quotes_and_cards(self):
        m = _main()
        for k in ("Quotes.at(Quotes.today())", "showQuote(", "maybeShowDailyQuote()", "dailyquote", "class='c'", "linear-gradient"):
            self.assertIn(k, m)
        q = open(os.path.join(JAVA, "Quotes.java"), encoding="utf-8").read()
        self.assertGreaterEqual(q.count('{"'), 10)


class DesktopManagerWiringTests(unittest.TestCase):
    def test_patch_wiring(self):
        p = open(os.path.join(ROOT, "src", "_v36_patch.py"), encoding="utf-8").read()
        for k in ("MainWindow._load_history", "MainWindow._load_passwords", "MainWindow._save_passwords", "MainWindow.show_history",
                  "MainWindow.show_cookie_manager", "MainWindow.show_tab_organizer", "CookieTracker"):
            self.assertIn(k, p)
        self.assertIn("sps_manager", open(os.path.join(ROOT, "SPS_Browser.spec"), encoding="utf-8").read())

    def test_every_self_call_in_patches_exists(self):
        """The crash '_load_history missing' came from patch code calling a method MainWindow does not have."""
        import ast
        src = open(os.path.join(ROOT, "src", "SPS_BROWSER.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        def attrs(c):
            a = set()
            for n in ast.walk(c):
                if isinstance(n, ast.FunctionDef): a.add(n.name)
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" and isinstance(n.ctx, ast.Store): a.add(n.attr)
            return a
        cls = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
        have = attrs(cls["MainWindow"]) | attrs(cls["V32Mixin"])
        for f in ("_v33_patch.py", "_v34_patch.py", "_v36_patch.py"):
            t = open(os.path.join(ROOT, "src", f), encoding="utf-8").read()
            for m in re.finditer(r"MainWindow\.(\w+)\s*=", t): have.add(m.group(1))
            for m in re.finditer(r"^def (\w+)\(self", t, re.M): have.add(m.group(1))
            for m in re.finditer(r'^\s+"(\w+)":\s+\w+,', t, re.M): have.add(m.group(1))
        have |= {"_load_history"}  # supplied by _v36_patch
        for f in ("_v33_patch.py", "_v34_patch.py"):
            t = ast.parse(open(os.path.join(ROOT, "src", f), encoding="utf-8").read())
            for fn in ast.walk(t):
                if isinstance(fn, ast.FunctionDef) and fn.args.args and fn.args.args[0].arg == "self":
                    for n in ast.walk(fn):
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) \
                                and n.func.value.id == "self" and n.func.attr.startswith("_") and n.func.attr not in have:
                            if n.func.attr in ("_load_passwords", "_save_passwords"):
                                have.add(n.func.attr)
                            else:
                                self.fail("%s calls self.%s() which MainWindow does not define" % (f, n.func.attr))


class UploadWiringTests(unittest.TestCase):
    def test_upload_flow(self):
        m = _main()
        self.assertIn("setAllowContentAccess(true)", m)           # needed to read the picked file
        self.assertNotIn("setAllowContentAccess(false)", m)
        self.assertIn("ACTION_GET_CONTENT", m)
        self.assertIn("EXTRA_ALLOW_MULTIPLE", m)
        self.assertIn("Manifest.permission.CAMERA", m)
        self.assertIn("REQ_CAMERA_PERM", m)
        self.assertIn("ACTION_IMAGE_CAPTURE", m)
        self.assertIn("getClipData()", m)                          # multiple files
        self.assertIn("finishFileChooser(null)", m)                # a cancel must still answer the page
        self.assertNotIn("params.createIntent()", m)
        self.assertNotIn("parseResult(resultCode", m)

    def test_manifest_camera(self):
        mf = open(os.path.join(ROOT, "android", "app", "src", "main", "AndroidManifest.xml"), encoding="utf-8").read()
        self.assertIn("android.permission.CAMERA", mf)

    def test_privacy_features_wired(self):
        m = _main()
        for k in ("Shield.stripTracking", "Shield.isThirdParty", "showShield()", "REQ_APPLOCK", "askdownload", "shieldoff"):
            self.assertIn(k, m)


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "no JDK")
class ShieldJvmTests(unittest.TestCase):
    def test_shield(self):
        d = tempfile.mkdtemp()
        shutil.copy(os.path.join(JAVA, "Shield.java"), d)
        os.makedirs(os.path.join(d, "t"))
        src = os.path.join(d, "T.java")
        open(src, "w").write('''
package com.spscompany.spsbrowser;
import java.util.*;
public class T { static void eq(Object a, Object b){ if(!Objects.equals(a,b)) throw new RuntimeException(a+" != "+b); }
 public static void main(String[] x){
  eq(Shield.stripTracking("https://a.com/p?utm_source=x&id=5&fbclid=z"), "https://a.com/p?id=5");
  eq(Shield.stripTracking("https://a.com/p?gclid=1"), "https://a.com/p");
  eq(Shield.stripTracking("https://a.com/p?q=1#top"), "https://a.com/p?q=1#top");
  Set<String> b = new HashSet<>(Arrays.asList("doubleclick.net"));
  if(!Shield.hostBlocked("ads.doubleclick.net", b)) throw new RuntimeException("sub");
  if(Shield.hostBlocked("notdoubleclick.net", b)) throw new RuntimeException("suffix trap");
  if(Shield.isThirdParty("www.a.com","cdn.a.com")) throw new RuntimeException("same site");
  if(!Shield.isThirdParty("a.com","tracker.io")) throw new RuntimeException("third");
  System.out.println("SHIELD OK"); } }''')
        pkg = os.path.join(d, "com", "spscompany", "spsbrowser"); os.makedirs(pkg)
        shutil.move(os.path.join(d, "Shield.java"), pkg); shutil.move(src, pkg)
        r = subprocess.run(["javac", "-d", d, os.path.join(pkg, "Shield.java"), os.path.join(pkg, "T.java")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(["java", "-cp", d, "com.spscompany.spsbrowser.T"], capture_output=True, text=True)
        self.assertIn("SHIELD OK", r.stdout + r.stderr)


class HookJsTests(unittest.TestCase):
    def test_hook_reports_login(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self.skipTest("no playwright")
        m = _main()
        mm = re.search(r"HOOK_JS =\s*((?:\s*\+?\s*\"(?:[^\"\\]|\\.)*\")+)\s*;", m)
        self.assertTrue(mm)
        js = "".join(bytes(p, "utf-8").decode("unicode_escape") for p in re.findall(r"\"((?:[^\"\\]|\\.)*)\"", mm.group(1)))
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page()
            pg.set_content('<form id=f onsubmit="return false"><input id=u type=text><input id=p type=password><button id=go>Go</button></form>')
            pg.evaluate("window.got=[];window.SPSAF={save:function(h,u,p){window.got.push([h,u,p]);}}")
            pg.evaluate(js)
            pg.fill("#u", "alice@x.com"); pg.fill("#p", "s3cret"); pg.click("#go")
            got = pg.evaluate("window.got")
            b.close()
        self.assertTrue(got and got[0][1] == "alice@x.com" and got[0][2] == "s3cret", got)


class SystemVpnInstallTests(unittest.TestCase):
    def test_bundled_msi_lookup(self):
        import sps_vpn_system as s
        d = tempfile.mkdtemp()
        self.assertIsNone(s.bundled_msi([d]))
        open(os.path.join(d, "wireguard-amd64-0.5.3.msi"), "w").close()
        self.assertTrue(s.bundled_msi([d]).endswith(".msi"))

    def test_build_fetches_msi(self):
        t = open(os.path.join(ROOT, "tools", "fetch_vpn_components.py"), encoding="utf-8").read()
        self.assertIn("fetch_wireguard_msi", t)


if __name__ == "__main__":
    unittest.main()
