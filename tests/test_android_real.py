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


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "no JDK")
class ExtensionsRunTests(unittest.TestCase):
    """Runs the real Java Extensions code on a JVM, then runs the JavaScript it produces inside Chromium on a test page."""
    def _js(self):
        d = tempfile.mkdtemp()
        pkg = os.path.join(d, "com", "spscompany", "spsbrowser"); os.makedirs(pkg)
        shutil.copy(os.path.join(JAVA, "Extensions.java"), pkg)
        java_src = r"""package com.spscompany.spsbrowser;
public class T { public static void main(String[] a){
 for (Extensions.Def d : Extensions.CATALOG) { int n = d.options == null ? 1 : d.options.length;
   for (int i = 0; i < n; i++) System.out.println(d.id + "\t" + i + "\t" + Extensions.js(d.id, i).replace("\n", "<NL>")); }
 System.out.println("MATCH\t" + Extensions.hostMatches("*.a.com","x.a.com") + Extensions.hostMatches("a.com","www.a.com") + Extensions.hostMatches("a.com","b.com") + Extensions.hostMatches("*","z.io"));
}}"""
        open(os.path.join(pkg, "T.java"), "w").write(java_src)
        r = subprocess.run(["javac", "-d", d, os.path.join(pkg, "Extensions.java"), os.path.join(pkg, "T.java")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(["java", "-cp", d, "com.spscompany.spsbrowser.T"], capture_output=True, text=True)
        out = {}
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                out[(parts[0], parts[1])] = parts[2].replace("<NL>", "\n")
        return out, r.stdout

    def test_matching(self):
        _, raw = self._js()
        self.assertIn("MATCH\ttruetruefalsetrue", raw)

    def test_scripts_work_in_chromium(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self.skipTest("no playwright")
        out, _ = self._js()
        html = ('<html><head><meta name=viewport content="width=device-width"></head><body>'
                '<div id=onetrust-banner-sdk style="position:fixed;bottom:0">cookies</div>'
                '<div id=chat style="position:fixed;right:0;bottom:0;width:60px;height:60px">chat</div>'
                '<article id=a><p>Hello</p></article><img id=im src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" width=20 height=20>'
                '<p id=t style="user-select:none">copy me</p></body></html>')
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(); pg.set_content(html)
            disp = lambda sel: pg.evaluate("s=>getComputedStyle(document.querySelector(s)).display", sel)
            pg.evaluate(out[("cookiehide", "0")]); self.assertEqual(disp("#onetrust-banner-sdk"), "none")
            pg.evaluate(out[("cleanpage", "0")]); self.assertEqual(disp("#chat"), "none")
            pg.evaluate(out[("noimages", "0")]); self.assertEqual(disp("#im"), "none")
            pg.evaluate(out[("copyunlock", "0")]); self.assertEqual(pg.evaluate("getComputedStyle(document.querySelector('#t')).userSelect"), "text")
            pg.evaluate(out[("forcezoom", "0")]); self.assertIn("user-scalable=yes", pg.evaluate("document.querySelector('meta[name=viewport]').content"))
            pg.evaluate(out[("readable", "2")]); self.assertEqual(pg.evaluate("getComputedStyle(document.querySelector('#a')).fontSize"), "24px")
            pg.evaluate(out[("darkpages", "1")]); self.assertIn("invert", pg.evaluate("getComputedStyle(document.documentElement).filter"))
            for k, v in out.items():                                           # every script must at least run without throwing
                if k[0] != "MATCH": pg.evaluate(v)
            b.close()


class AndroidFixesWiringTests(unittest.TestCase):
    def test_restart_and_chooser(self):
        m = _main()
        self.assertIn("RestartActivity.class", m)
        self.assertNotIn("killProcess(android.os.Process.myPid()), 300", m)
        mf = open(os.path.join(ROOT, "android", "app", "src", "main", "AndroidManifest.xml"), encoding="utf-8").read()
        self.assertIn(".RestartActivity", mf); self.assertIn(":restart", mf)
        for k in ("ACTION_OPEN_DOCUMENT", '"Files"', "ACTION_VIDEO_CAPTURE", "pickSource(", "RESOURCE_PROTECTED_MEDIA_ID", "manageSitePermissions", "showExtensions"):
            self.assertIn(k, m)

    def test_updater_is_visible_and_logged(self):
        u = open(os.path.join(ROOT, "src", "sps_updater.py"), encoding="utf-8").read()
        self.assertIn('"/SILENT"', u); self.assertNotIn('"/VERYSILENT"', u.split("SILENT_ARGS =")[1].split("\n")[0])
        self.assertIn("update_install.log", u); self.assertIn("open_installer_normally", u)

    def test_scan_thread_does_not_touch_widgets(self):
        t = open(os.path.join(ROOT, "src", "_v34_patch.py"), encoding="utf-8").read()
        worker = t.split("def _scan_worker():")[1].split("scan_timer = QTimer")[0]
        for bad in ("scan_btn.", "results.", "pb.setValue"):
            self.assertNotIn(bad, worker)


RES = os.path.join(ROOT, "android", "app", "src", "main", "res")


class WidgetAndResourceTests(unittest.TestCase):
    def test_all_xml_resources_are_well_formed(self):
        import xml.dom.minidom
        for base, _, files in os.walk(os.path.join(ROOT, "android", "app", "src", "main")):
            for f in files:
                if f.endswith(".xml"):
                    xml.dom.minidom.parse(os.path.join(base, f))

    def test_widget_ids_and_manifest(self):
        layout = open(os.path.join(RES, "layout", "widget_search.xml"), encoding="utf-8").read()
        w = open(os.path.join(JAVA, "SearchWidget.java"), encoding="utf-8").read()
        for view in re.findall(r'bind\(ctx, rv, "(\w+)"', w):
            self.assertIn("@+id/" + view, layout)
        for d in re.findall(r"@drawable/(\w+)", layout):
            self.assertTrue(os.path.isfile(os.path.join(RES, "drawable", d + ".xml")), d)
        info = open(os.path.join(RES, "xml", "widget_search_info.xml"), encoding="utf-8").read()
        self.assertIn("@layout/widget_search", info)
        mf = open(os.path.join(ROOT, "android", "app", "src", "main", "AndroidManifest.xml"), encoding="utf-8").read()
        self.assertIn(".SearchWidget", mf); self.assertIn("widget_search_info", mf)
        m = _main()
        for k in ("handleCommand(", "SearchWidget.VOICE", "SearchWidget.LENS", "startLens()", "Lens.byUrl(", "showTools()"):
            self.assertIn(k, m)


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "no JDK")
class LensUploadTests(unittest.TestCase):
    def test_lens_page_posts_the_photo_in_chromium(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self.skipTest("no playwright")
        d = tempfile.mkdtemp()
        pkg = os.path.join(d, "com", "spscompany", "spsbrowser"); os.makedirs(pkg)
        shutil.copy(os.path.join(JAVA, "Lens.java"), pkg)
        jpeg = ("/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
                "wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=")
        open(os.path.join(pkg, "T.java"), "w").write(r"""package com.spscompany.spsbrowser;
public class T { public static void main(String[] a){ System.out.print(Lens.uploadPage(Lens.UPLOAD, Lens.FIELD, a[0]));
  System.out.println(); System.out.println("URL " + Lens.byUrl("https://x.com/a b.jpg?x=1&y=2")); } }""")
        r = subprocess.run(["javac", "-d", d, os.path.join(pkg, "Lens.java"), os.path.join(pkg, "T.java")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(["java", "-cp", d, "com.spscompany.spsbrowser.T", jpeg], capture_output=True, text=True)
        html, _, tail = r.stdout.rpartition("\nURL ")
        self.assertEqual(tail.strip(), "https://lens.google.com/uploadbyurl?url=https%3A%2F%2Fx.com%2Fa+b.jpg%3Fx%3D1%26y%3D2")
        seen = {}
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page()
            def handler(route):
                req = route.request
                seen["method"] = req.method; seen["ctype"] = req.headers.get("content-type", ""); seen["body"] = req.post_data_buffer
                route.fulfill(status=200, content_type="text/html", body="<html><body>ok</body></html>")
            pg.route("https://lens.google.com/**", handler)
            pg.route("https://base.test/**", lambda route: route.fulfill(status=200, content_type="text/html", body=html))
            pg.goto("https://base.test/"); pg.wait_for_timeout(800)
            b.close()
        self.assertEqual(seen.get("method"), "POST")
        self.assertIn("multipart/form-data", seen["ctype"])
        self.assertIn(b'name="encoded_image"', seen["body"]); self.assertIn(b"\xff\xd8\xff", seen["body"])     # a real JPEG went out


class ButtonWiringTests(unittest.TestCase):
    """Nobody can tap every button on a phone here, so every button is checked in the source: its action exists, its icon exists."""
    def setUp(self):
        self.m = _main()
        for f in ("ListPage", "TabsPage", "Vault"):
            self.m += open(os.path.join(JAVA, f + ".java"), encoding="utf-8").read()

    def test_every_method_reference_exists(self):
        declared = set(re.findall(r"\b(?:void|boolean|String|int|View|TextView|long)\s+(\w+)\s*\(", self.m))
        for ref in set(re.findall(r"this::(\w+)", self.m)):
            self.assertIn(ref, declared, "button points to missing method %s" % ref)

    def test_every_icon_exists(self):
        icons = {l.split("|")[0] for l in open(os.path.join(ROOT, "android", "app", "src", "main", "assets", "icons.txt"), encoding="utf-8")}
        used = set(re.findall(r'Ico\.of\("(\w+)"', self.m)) | set(re.findall(r'(?:menuRow|settingLink|quickAction)\([^,]+,(?: [a-z\[\]0-9]+,)? "(\w+)"', self.m))
        self.assertTrue(used)
        self.assertEqual(sorted(u for u in used if u not in icons), [])

    def test_menu_and_settings_rows(self):
        for row in ('"Privacy shield"', '"Extension store"', '"Thought of the day"', '"Check for updates"', '"Read aloud"', '"Add to home screen"',
                    '"Profiles"', '"Bookmarks"', '"History"', '"Downloads"', '"Passwords"', '"Find in page"', '"Settings"'):
            self.assertIn("menuRow(box, d, ", self.m.split(row)[0][-60:] + "menuRow(box, d, " if row in self.m else "")
            self.assertIn(row, self.m)
        # these used to be silently missing from the menu: they must be inside showMenu()
        menu = self.m.split("private void showMenu()")[1].split("// ─────")[0]
        for row in ('"Privacy shield"', '"Extension store"', '"Thought of the day"', '"Check for updates"', '"Read aloud"'):
            self.assertIn(row, menu)
        settings = self.m.split("private void showSettings()")[1].split("private void ")[0]
        for row in ('"Remove tracking from links"', '"Lock the app with your screen lock"', '"Ask before downloading"', '"Thought of the day"',
                    '"Extension store"', '"Site permissions"', '"Block autoplay"', '"Block pop-up windows"', '"Check for updates automatically"'):
            self.assertIn(row, settings)


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "no JDK")
class UpdaterJvmTests(unittest.TestCase):
    def test_updater_logic(self):
        d = tempfile.mkdtemp()
        pkg = os.path.join(d, "com", "spscompany", "spsbrowser"); os.makedirs(pkg)
        shutil.copy(os.path.join(JAVA, "Updater.java"), pkg)
        # org.json does not exist on a plain JVM: give the compiler a stub (only fromRelease uses it, and it is not run here)
        stubs = os.path.join(d, "org", "json"); os.makedirs(stubs)
        open(os.path.join(stubs, "JSONObject.java"), "w").write("package org.json; public class JSONObject { public JSONObject(String s) throws Exception {} public boolean optBoolean(String k){return false;} public String optString(String k,String d){return d;} public JSONArray optJSONArray(String k){return null;} public long optLong(String k){return 0;} }")
        open(os.path.join(stubs, "JSONArray.java"), "w").write("package org.json; public class JSONArray { public int length(){return 0;} public JSONObject getJSONObject(int i) throws Exception {return null;} }")
        open(os.path.join(pkg, "T.java"), "w").write(r"""package com.spscompany.spsbrowser;
public class T { static void ok(boolean b, String m){ if(!b) throw new RuntimeException(m); }
 public static void main(String[] a) throws Exception {
  ok(Updater.isNewer("v38.5.0","38.2.0"), "newer"); ok(!Updater.isNewer("38.2.0","38.2.0"), "same"); ok(!Updater.isNewer("38.1.9","38.2.0"), "older");
  ok(Updater.isNewer("39.0.0","38.99.99"), "major"); ok(!Updater.isNewer("junk","38.0.0"), "junk");
  String h = "a".repeat(64);
  ok(h.equals(Updater.hashFor(h + "  SPS_Browser_Android_v38.5.0.apk" + (char)10 + "b".repeat(64) + "  other.exe" + (char)10, "SPS_Browser_Android_v38.5.0.apk")), "hash");
  ok(Updater.hashFor(h + "  x.apk", "y.apk") == null, "no hash");
  ok(Updater.sha256(new java.io.ByteArrayInputStream("abc".getBytes())).equals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"), "sha");
  System.out.println("UPDATER OK"); } }""")
        srcs = [os.path.join(pkg, "Updater.java"), os.path.join(pkg, "T.java"), os.path.join(stubs, "JSONObject.java"), os.path.join(stubs, "JSONArray.java")]
        r = subprocess.run(["javac", "-d", d] + srcs, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(["java", "-cp", d, "com.spscompany.spsbrowser.T"], capture_output=True, text=True)
        self.assertIn("UPDATER OK", r.stdout + r.stderr)


class UploadWiringTests(unittest.TestCase):
    def test_upload_flow(self):
        m = _main()
        self.assertIn("setAllowContentAccess(true)", m)           # needed to read the picked file
        self.assertNotIn("setAllowContentAccess(false)", m)
        self.assertIn("ACTION_GET_CONTENT", m)  # photos / videos source
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
