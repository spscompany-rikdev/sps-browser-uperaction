"""SvgPath (Material icons on Android) on a real JVM, the easy-access JS in a real browser engine, and wiring checks."""
import json, os, shutil, subprocess, tempfile, unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "android", "app", "src", "main")
JAVA = os.path.join(ROOT, "java", "com", "spscompany", "spsbrowser")
HAVE_JAVA = bool(shutil.which("javac") and shutil.which("java"))

T = r'''
import com.spscompany.spsbrowser.*;
public class T { public static void main(String[] a) throws Exception {
  for (String line : new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(a[0])), "UTF-8").split("\n")) {
    int i = line.indexOf('|'); if (i < 0 || !line.substring(i+1).startsWith("S ")) continue;
    float[][] ops = SvgP.parse(line.substring(i + 3));
    int bad = 0; for (float[] o : ops) for (float f : o) if (Float.isNaN(f) || Float.isInfinite(f) || Math.abs(f) > 60) bad++;
    System.out.println(line.substring(0, i) + " " + ops.length + " " + bad);
  }
  float[][] r = SvgP.parse("M0 0h10v10H0z"); System.out.println("rect " + r.length + " " + r[2][1] + "," + r[2][2] + " " + r[4][0]);
  float[][] arc = SvgP.parse("M0 0a5 5 0 0 1 10 0"); System.out.println("arc " + arc.length + " " + arc[arc.length-1][5] + "," + arc[arc.length-1][6]);
}}
'''


@unittest.skipUnless(HAVE_JAVA, "no JDK")
class SvgPathTests(unittest.TestCase):
    def test_all_material_icons_parse(self):
        d = tempfile.mkdtemp(); src = os.path.join(d, "src", "com", "spscompany", "spsbrowser"); os.makedirs(src)
        code = open(os.path.join(JAVA, "SvgPath.java"), encoding="utf-8").read().replace("final class SvgPath", "public final class SvgP").replace("SvgPath(", "SvgP(").replace("new SvgPath(", "new SvgP(")
        code = code.replace("static float[][] parse", "public static float[][] parse")
        open(os.path.join(src, "SvgP.java"), "w").write(code)
        open(os.path.join(d, "T.java"), "w").write(T)
        r = subprocess.run(["javac", "-d", d, os.path.join(src, "SvgP.java"), os.path.join(d, "T.java")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        out = subprocess.run(["java", "-cp", d, "T", os.path.join(ROOT, "assets", "icons.txt")], capture_output=True, text=True).stdout.splitlines()
        icons = [l.split() for l in out if not l.startswith(("rect", "arc"))]
        self.assertGreaterEqual(len(icons), 40)
        for name, n, bad in icons:
            self.assertGreater(int(n), 2, name); self.assertEqual(bad, "0", name)
        rect = [l for l in out if l.startswith("rect")][0].split()
        self.assertEqual(rect[1:], ["5", "10.0,10.0", "3.0"])               # M h v H z -> 5 ops, relative/absolute handled, z = CLOSE
        arc = [l for l in out if l.startswith("arc")][0].split()
        ex, ey = map(float, arc[2].split(","))
        self.assertAlmostEqual(ex, 10, 3); self.assertAlmostEqual(ey, 0, 3)  # arc ends exactly at its end point


class WiringTests(unittest.TestCase):
    def j(self, n): return open(os.path.join(JAVA, n), encoding="utf-8").read()

    def test_wiring(self):
        m = self.j("MainActivity.java")
        for needle in ("showEasyAccess", "spinMenuButton(true)", "spinMenuButton(false)", "easyIcon", "buildEasySheet", "easy.js"):
            self.assertIn(needle, m)
        self.assertIn("setOnShowListener", self.j("UI.java"))              # sheets slide up
        self.assertIn("SvgPath.parse", self.j("Ico.java"))
        for n in ("tune", "play", "pause", "volume", "pip", "rotate"):
            self.assertRegex(open(os.path.join(ROOT, "assets", "icons.txt")).read(), r"(?m)^%s\|S " % n)

    def test_easy_js_in_browser(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self.skipTest("no playwright")
        js = open(os.path.join(ROOT, "assets", "easy.js"), encoding="utf-8").read()
        html = "<title>t</title><video id=v src='data:video/mp4;base64,' muted></video><img src='data:image/gif;base64,R0lGODlhAQABAAAAACw='>"
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(); pg.set_content(html)
            pg.evaluate(js)
            info = json.loads(pg.evaluate("__spsEasy.probe()"))
            self.assertEqual(info["imgs"], 1); self.assertFalse(info["isImg"])
            pg.evaluate("document.getElementById('v').loop=false")
            pg.evaluate("__spsEasy.ctl('loop')"); pg.evaluate("__spsEasy.ctl('mute')")
            pg.evaluate("__spsEasy.img('rot')")
            self.assertIn("rotate(90deg)", pg.evaluate("document.images[0].style.transform"))
            pg.evaluate("__spsEasy.img('gray')")
            self.assertIn("grayscale(100%)", pg.evaluate("document.images[0].style.filter"))
            pg.evaluate("__spsEasy.gallery()"); self.assertFalse(pg.evaluate("!!document.getElementById('__sps_gal')") is None)
            b.close()


if __name__ == "__main__":
    unittest.main()


class FixTests(unittest.TestCase):
    """Regression guards for the problems found on real devices."""
    def test_capture_has_blank_detection(self):
        m = open(os.path.join(JAVA, "MainActivity.java"), encoding="utf-8").read()
        self.assertIn("looksBlank", m); self.assertIn("captureAreaNow", m)

    def test_installer_launches_app_as_normal_user(self):
        iss = open(os.path.join(os.path.dirname(__file__), "..", "installer", "SPS_Browser_Setup.iss"), encoding="utf-8").read()
        line = [l for l in iss.splitlines() if "postinstall" in l and l.startswith("Filename")][0]
        self.assertIn("runasoriginaluser", line)
        main = open(os.path.join(os.path.dirname(__file__), "..", "src", "main.py"), encoding="utf-8").read()
        self.assertIn("_drop_admin_rights", main)
        upd = open(os.path.join(os.path.dirname(__file__), "..", "src", "sps_updater.py"), encoding="utf-8").read()
        self.assertIn("_run_copy", upd); self.assertIn("last_error", upd)


class SpeedAndMediaFixTests(unittest.TestCase):
    def test_fast_paths_and_read_aloud(self):
        m = open(os.path.join(JAVA, "MainActivity.java"), encoding="utf-8").read()
        self.assertIn('endsWith("googlevideo.com")', m)
        self.assertIn("getMaxSpeechInputLength", m); self.assertIn("LANG_NOT_SUPPORTED", m)
        man = open(os.path.join(ROOT, "AndroidManifest.xml"), encoding="utf-8").read()
        self.assertIn("android.intent.action.TTS_SERVICE", man); self.assertIn("<queries>", man)
        d = open(os.path.join(os.path.dirname(__file__), "..", "src", "SPS_BROWSER.py"), encoding="utf-8").read()
        self.assertIn("_YT_FAST_HOSTS", d); self.assertIn("FAST PATH (YouTube start-up speed)", d)
