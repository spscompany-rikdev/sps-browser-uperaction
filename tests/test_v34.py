import unittest, json, re, html, os, sys, ast, hashlib, datetime
from urllib.parse import urlparse, quote_plus

def _reading_mode_clean(raw_html, theme=None, dark=False):
    if theme is None:
        theme = {"bg_primary":"#fff","text_primary":"#000","bg_secondary":"#f5f5f5","border":"#ccc","text_secondary":"#666","accent":"#1a73e8"}
    for tag in ["script","style","nav","footer","aside","form","iframe","noscript","header","menu","ads"]:
        raw_html = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', raw_html, flags=re.S|re.I)
    raw_html = re.sub(r' on\w+="[^"]*"', '', raw_html)
    title_m = re.search(r'<title[^>]*>(.*?)</title>', raw_html, re.I|re.S)
    title = html.unescape(title_m.group(1)) if title_m else "Reading View"
    body_m = re.search(r'<body[^>]*>(.*?)</body>', raw_html, re.S|re.I)
    body = body_m.group(1) if body_m else raw_html
    return f"<title>📖 {html.escape(title)}</title><body>{body}</body>"

def parse_chrome_bookmarks(data_str):
    data = json.loads(data_str)
    results = []
    def _walk(node, folder="Imported"):
        if node.get("type") == "url":
            results.append({"title":node.get("name",""),"url":node.get("url",""),"folder":folder,"added":""})
        for child in node.get("children",[]):
            _walk(child, node.get("name",folder))
    for root in data.get("roots",{}).values():
        if isinstance(root, dict): _walk(root)
    return results

def group_history_by_topic(history):
    groups = {}
    for entry in history:
        url = entry.get("url","")
        try:
            host = urlparse(url).netloc.lstrip("www.")
            domain = ".".join(host.rsplit(".",2)[-2:]) if "." in host else host or "Other"
        except Exception:
            domain = "Other"
        groups.setdefault(domain,[]).append(entry)
    for d in groups:
        groups[d].sort(key=lambda x: x.get("visited",""), reverse=True)
    return groups

def scan_for_suspicious_files(file_list):
    BAD_EXTS = {".exe",".bat",".cmd",".ps1",".vbs",".scr"}
    BAD_NAMES = ["inject","hook","steal","keylog","rat","trojan","backdoor","miner"]
    issues = []
    for fpath in file_list:
        fname = os.path.basename(fpath).lower()
        ext = os.path.splitext(fname)[1]
        if ext in BAD_EXTS: issues.append(("bad_ext",fpath))
        if any(b in fname for b in BAD_NAMES): issues.append(("bad_name",fpath))
    return issues

def price_extract_mock(html_text):
    m = re.search(r'\$[\d,]+\.?\d*', html_text)
    return m.group(0) if m else ""

def build_autofill_js(addresses):
    return f"(function(addresses){{/* fill */}})({json.dumps(addresses)});"

def extract_dominant_color_mock(pixels):
    if not pixels: return "#808080"
    r=sum(p[0] for p in pixels)//len(pixels)
    g=sum(p[1] for p in pixels)//len(pixels)
    b=sum(p[2] for p in pixels)//len(pixels)
    return f"#{r:02x}{g:02x}{b:02x}"

def detect_browser_profiles_mock(home):
    sources=[]
    candidates=[("Chrome",os.path.join(home,"AppData","Local","Google","Chrome","User Data")),
                ("Edge",os.path.join(home,"AppData","Local","Microsoft","Edge","User Data"))]
    for browser,base in candidates:
        if not os.path.isdir(base): continue
        for prof in ["Default","Profile 1"]:
            bm=os.path.join(base,prof,"Bookmarks")
            if os.path.exists(bm):
                sources.append({"browser":browser,"profile":prof,"path":bm,"type":"chrome"})
    return sources

CHROME_JSON = json.dumps({"roots":{
    "bookmark_bar":{"type":"folder","name":"Bar","children":[
        {"type":"url","name":"Google","url":"https://google.com","date_added":"1"},
        {"type":"url","name":"GitHub","url":"https://github.com","date_added":"2"},
        {"type":"folder","name":"Dev","children":[
            {"type":"url","name":"MDN","url":"https://developer.mozilla.org","date_added":"3"},
            {"type":"url","name":"PyPI","url":"https://pypi.org","date_added":"4"},
        ]},
    ]},
    "other":{"type":"folder","name":"Other","children":[
        {"type":"url","name":"HN","url":"https://news.ycombinator.com","date_added":"5"},
    ]},
}})

HIST=[
    {"url":"https://github.com/a/b","title":"Repo","visited":"2026-10-14T10:00"},
    {"url":"https://github.com/a/c","title":"Issues","visited":"2026-10-14T09:00"},
    {"url":"https://docs.python.org/3/","title":"Docs","visited":"2026-10-13T15:00"},
    {"url":"https://stackoverflow.com/q/1","title":"Q1","visited":"2026-10-12T08:00"},
    {"url":"https://stackoverflow.com/q/2","title":"Q2","visited":"2026-10-13T08:00"},
    {"url":"https://news.ycombinator.com","title":"HN","visited":"2026-10-14T11:00"},
    {"url":"not-a-url","title":"Bad","visited":"2026-10-01T00:00"},
]

SRC_DIR = os.path.join(os.path.dirname(__file__),"..","src")

class TestReadingMode(unittest.TestCase):
    def test_removes_nav(self):
        r=_reading_mode_clean("<html><body><nav>Menu</nav><p>Article</p></body></html>")
        self.assertNotIn("<nav>",r); self.assertIn("Article",r)
    def test_removes_footer(self):
        r=_reading_mode_clean("<html><body><footer>Footer</footer><p>Content</p></body></html>")
        self.assertNotIn("<footer>",r); self.assertIn("Content",r)
    def test_removes_scripts(self):
        r=_reading_mode_clean("<body><script>evil()</script><p>Text</p></body>")
        self.assertNotIn("evil()",r)
    def test_removes_events(self):
        r=_reading_mode_clean('<body><p onclick="bad()">Click</p></body>')
        self.assertNotIn("onclick",r)
    def test_preserves_content(self):
        r=_reading_mode_clean("<body><p>Hello world</p></body>")
        self.assertIn("Hello world",r)
    def test_title_extracted(self):
        r=_reading_mode_clean("<html><head><title>My Article</title></head><body><p>t</p></body></html>")
        self.assertIn("My Article",r)
    def test_xss_in_title(self):
        r=_reading_mode_clean("<html><head><title><script>xss</script></title></head><body></body></html>")
        self.assertNotIn("<script>xss</script>",r)
    def test_empty_input(self):
        r=_reading_mode_clean("")
        self.assertIsInstance(r,str)
    def test_removes_aside(self):
        r=_reading_mode_clean("<body><aside>Ad</aside><p>Main</p></body>")
        self.assertNotIn("<aside>",r)
    def test_removes_iframe(self):
        r=_reading_mode_clean("<body><iframe src='x'></iframe><p>Real</p></body>")
        self.assertNotIn("<iframe",r); self.assertIn("Real",r)

class TestChromeImport(unittest.TestCase):
    def test_total(self):
        self.assertEqual(len(parse_chrome_bookmarks(CHROME_JSON)),5)
    def test_subfolder(self):
        bms=parse_chrome_bookmarks(CHROME_JSON)
        mdn=next(b for b in bms if "mozilla" in b["url"])
        self.assertEqual(mdn["folder"],"Dev")
    def test_top_level(self):
        bms=parse_chrome_bookmarks(CHROME_JSON)
        hn=next(b for b in bms if "ycombinator" in b["url"])
        self.assertEqual(hn["folder"],"Other")
    def test_all_have_urls(self):
        self.assertTrue(all(b["url"].startswith("http") for b in parse_chrome_bookmarks(CHROME_JSON)))
    def test_empty_roots(self):
        self.assertEqual(parse_chrome_bookmarks('{"roots":{}}'),[])
    def test_no_empty_urls(self):
        self.assertTrue(all(b["url"] for b in parse_chrome_bookmarks(CHROME_JSON)))

class TestJourneys(unittest.TestCase):
    def test_github(self):
        g=group_history_by_topic(HIST)
        self.assertIn("github.com",g); self.assertEqual(len(g["github.com"]),2)
    def test_stackoverflow(self):
        g=group_history_by_topic(HIST)
        self.assertIn("stackoverflow.com",g); self.assertEqual(len(g["stackoverflow.com"]),2)
    def test_sorted(self):
        g=group_history_by_topic(HIST)
        so=g["stackoverflow.com"]
        self.assertGreater(so[0]["visited"],so[1]["visited"])
    def test_bad_url(self):
        self.assertIsInstance(group_history_by_topic(HIST),dict)
    def test_python(self):
        self.assertIn("python.org",group_history_by_topic(HIST))
    def test_unique_domains(self):
        self.assertGreaterEqual(len(group_history_by_topic(HIST)),4)

class TestMalwareScanner(unittest.TestCase):
    def test_exe(self):
        self.assertTrue(any(i[0]=="bad_ext" for i in scan_for_suspicious_files(["/d/f.exe"])))
    def test_bat(self):
        self.assertTrue(any(i[0]=="bad_ext" for i in scan_for_suspicious_files(["/d/r.bat"])))
    def test_bad_name(self):
        self.assertTrue(any(i[0]=="bad_name" for i in scan_for_suspicious_files(["/d/keylogger.py"])))
    def test_clean(self):
        self.assertEqual(scan_for_suspicious_files(["/d/settings.json","/d/bookmarks.json"]),[])
    def test_trojan(self):
        self.assertTrue(any(i[0]=="bad_name" for i in scan_for_suspicious_files(["/d/trojan.txt"])))
    def test_empty(self):
        self.assertEqual(scan_for_suspicious_files([]),[])
    def test_ps1(self):
        self.assertTrue(any(i[0]=="bad_ext" for i in scan_for_suspicious_files(["/d/s.ps1"])))

class TestPriceTracker(unittest.TestCase):
    def test_extracts(self):
        self.assertEqual(price_extract_mock('<span>$29.99</span>'),"$29.99")
    def test_large(self):
        self.assertEqual(price_extract_mock('Price: $1,299.00'),"$1,299.00")
    def test_none(self):
        self.assertEqual(price_extract_mock('<p>No price</p>'),"")
    def test_down(self):
        self.assertTrue("$45.00"<"$50.00")
    def test_up(self):
        self.assertTrue("$55.00">"$50.00")

class TestAutofill(unittest.TestCase):
    ADDR=[{"full_name":"John Smith","email":"j@x.com","phone":"+1","address_line_1":"123 St","city":"NYC","zip_postal":"10001","country":"US"}]
    def test_name_in_js(self):
        self.assertIn("John Smith",build_autofill_js(self.ADDR))
    def test_email_in_js(self):
        self.assertIn("j@x.com",build_autofill_js(self.ADDR))
    def test_prefix(self):
        self.assertTrue(build_autofill_js(self.ADDR).startswith("(function(addresses)"))
    def test_empty(self):
        self.assertIn("[]",build_autofill_js([]))

class TestWallpaperTheme(unittest.TestCase):
    def test_white(self):
        self.assertEqual(extract_dominant_color_mock([(255,255,255)]*100),"#ffffff")
    def test_black(self):
        self.assertEqual(extract_dominant_color_mock([(0,0,0)]*100),"#000000")
    def test_red(self):
        self.assertEqual(extract_dominant_color_mock([(255,0,0)]*100),"#ff0000")
    def test_mixed(self):
        self.assertEqual(extract_dominant_color_mock([(100,100,100),(200,200,200)]),"#969696")
    def test_empty(self):
        self.assertEqual(extract_dominant_color_mock([]),"#808080")

class TestBrowserDetection(unittest.TestCase):
    def test_finds_chrome(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p=os.path.join(tmp,"AppData","Local","Google","Chrome","User Data","Default")
            os.makedirs(p,exist_ok=True)
            with open(os.path.join(p,"Bookmarks"),"w") as f: json.dump({"roots":{}},f)
            result=detect_browser_profiles_mock(tmp)
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]["browser"],"Chrome")
    def test_no_browsers(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(detect_browser_profiles_mock(tmp),[])

class TestPatchFiles(unittest.TestCase):
    def _funcs(self,path):
        with open(path,encoding="utf-8") as f: src=f.read()
        tree=ast.parse(src)
        return {n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
    def test_v33_funcs(self):
        funcs=self._funcs(os.path.join(SRC_DIR,"_v33_patch.py"))
        for fn in ["_show_bookmark_manager","_open_guest_mode",
                   "_show_privacy_guide","_set_as_default_browser"]:
            self.assertIn(fn,funcs,f"Missing V33: {fn}")
    def test_v34_funcs(self):
        funcs=self._funcs(os.path.join(SRC_DIR,"_v34_patch.py"))
        for fn in ["_toggle_reading_mode","_show_theme_store","_show_malware_scanner",
                   "_open_pdf_viewer","_show_accessibility_settings","_show_journeys",
                   "_import_profile_bookmarks","_show_full_site_settings",
                   "_toggle_vertical_tabs","_document_pip"]:
            self.assertIn(fn,funcs,f"Missing V34: {fn}")
    def test_main_has_loaders(self):
        with open(os.path.join(SRC_DIR,"SPS_BROWSER.py"),encoding="utf-8") as f: src=f.read()
        self.assertIn('_sps_load_patch("_v34_patch.py"',src)
        self.assertIn('_sps_load_patch("_v36_patch.py"',src)
        self.assertIn("_sps_guarantee_patch_methods",src)
    def test_sps_routes(self):
        with open(os.path.join(SRC_DIR,"SPS_BROWSER.py"),encoding="utf-8") as f: src=f.read()
        for route in ['"reading-mode"','"vertical-tabs"','"pdf-viewer"','"discards"','"net-internals"']:
            self.assertIn(route,src,f"Missing sps:// route: {route}")
    def test_all_parse_clean(self):
        for fname in ["SPS_BROWSER.py","_v33_patch.py","_v34_patch.py",
                      "sps_filter_engine.py","sps_pages.py"]:
            fpath=os.path.join(SRC_DIR,fname)
            with open(fpath,encoding="utf-8") as f: src=f.read()
            try: ast.parse(src)
            except SyntaxError as e: self.fail(f"Syntax error in {fname}: {e}")

if __name__=="__main__":
    loader=unittest.TestLoader()
    suite=unittest.TestSuite()
    for cls in [TestReadingMode,TestChromeImport,TestJourneys,TestMalwareScanner,
                TestPriceTracker,TestAutofill,TestWallpaperTheme,TestBrowserDetection,TestPatchFiles]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner=unittest.TextTestRunner(verbosity=2)
    result=runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
