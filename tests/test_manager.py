"""Executes the SPS Manager window (offscreen) with real files: select, bulk delete, move, tabs and cookies."""
import datetime, json, os, sys, tempfile, unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtCore import Qt
    import sps_manager
    HAVE = True
except Exception:  # pragma: no cover
    HAVE = False


@unittest.skipUnless(HAVE, "PyQt6 not installed")
class ManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["sps-test"])

    def setUp(self):
        self.d = tempfile.mkdtemp()
        now = datetime.datetime.now()
        hist = [{"url": "https://a.com/%d" % i, "title": "A page %d" % i, "time": str(now - datetime.timedelta(days=i))} for i in range(6)]
        hist.append({"url": "https://b.org/x", "title": "Other", "time": str(now)})
        json.dump(hist, open(os.path.join(self.d, "history.json"), "w"))
        json.dump([{"title": "One", "url": "https://one.io", "folder": "General"}, {"title": "Two", "url": "https://two.io", "folder": "General"},
                   {"title": "Three", "url": "https://three.io", "folder": "Work"}], open(os.path.join(self.d, "bookmarks.json"), "w"))
        self.opened, self.actions, self.saved = [], [], []
        tabs = [{"id": i, "title": "T%d" % i, "url": "https://site%d.com/" % (i % 2), "private": False, "muted": False, "pinned": False,
                 "sleeping": False, "active": i == 0} for i in range(4)]
        tabs.append(dict(tabs[1], id=9, active=False))                       # a duplicate of tab 1
        outer = self

        class H(sps_manager.Hooks):
            history_path = os.path.join(outer.d, "history.json")
            bookmarks_path = os.path.join(outer.d, "bookmarks.json")
            cookie_store = None

            @staticmethod
            def save_bookmarks(b):
                outer.saved.append(b); json.dump(b, open(os.path.join(outer.d, "bookmarks.json"), "w"))

            @staticmethod
            def open_url(u, p=False): outer.opened.append((u, p))

            @staticmethod
            def tabs(): return tabs

            @staticmethod
            def tab_action(a, ids): outer.actions.append((a, list(ids)))
        self.H = H
        self._q = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

    def tearDown(self):
        QMessageBox.question = self._q

    def test_history_multi_select_delete(self):
        m = sps_manager.SpsManager(self.H)
        p = m.pages["history"]
        self.assertEqual(p.tree.topLevelItemCount(), 7)
        p.tree.selectAll()
        self.assertEqual(len(p.selected()), 7)
        p.tree.clearSelection()
        for i in (0, 2, 3):
            p.tree.topLevelItem(i).setSelected(True)
        p.on_delete()
        self.assertEqual(len(json.load(open(self.H.history_path))), 4)
        self.assertEqual(p.tree.topLevelItemCount(), 4)

    def test_history_filters_and_open(self):
        m = sps_manager.SpsManager(self.H)
        p = m.pages["history"]
        p.search.setText("other"); self.assertEqual(p.tree.topLevelItemCount(), 1)
        p.search.setText("")
        p.range.setCurrentIndex(p.range.findData("today")); self.assertEqual(p.tree.topLevelItemCount(), 2)
        p.tree.selectAll(); p.on_open(True)
        self.assertEqual(len(self.opened), 2); self.assertTrue(all(pr for _, pr in self.opened))

    def test_history_to_bookmarks(self):
        m = sps_manager.SpsManager(self.H)
        p = m.pages["history"]; p.tree.selectAll(); p.on_bookmark()
        self.assertEqual(len(json.load(open(self.H.bookmarks_path))), 3 + 7)
        p.on_bookmark()                                                      # no duplicates the second time
        self.assertEqual(len(json.load(open(self.H.bookmarks_path))), 10)

    def test_bookmarks_move_and_delete(self):
        m = sps_manager.SpsManager(self.H, "bookmarks")
        p = m.pages["bookmarks"]
        p.folder.setCurrentIndex(p.folder.findData("General")); self.assertEqual(p.tree.topLevelItemCount(), 2)
        p.tree.selectAll()
        sps_manager.QInputDialog.getItem = staticmethod(lambda *a, **k: ("Reading", True))
        p.on_move()
        self.assertEqual({b["folder"] for b in json.load(open(self.H.bookmarks_path))}, {"Reading", "Work"})
        p.folder.setCurrentIndex(0); p.tree.selectAll(); p.on_delete()
        self.assertEqual(json.load(open(self.H.bookmarks_path)), [])

    def test_tabs_bulk(self):
        m = sps_manager.SpsManager(self.H, "tabs")
        p = m.pages["tabs"]
        self.assertEqual(p.tree.topLevelItemCount(), 5)
        p.tree.topLevelItem(1).setSelected(True); p.tree.topLevelItem(2).setSelected(True)
        p.act("close")
        self.assertEqual(self.actions[-1], ("close", [1, 2]))
        p.close_dups()
        self.assertEqual(self.actions[-1], ("close", [2, 3, 9]))   # same address as the active tab / tab 1
        p.group.setCurrentIndex(1)                                           # grouped by site
        self.assertEqual(p.tree.topLevelItemCount(), 2)
        p.tree.selectAll(); self.assertEqual(sorted(p.ids()), [0, 1, 2, 3, 9])

    def test_cookies_page_without_store(self):
        m = sps_manager.SpsManager(self.H, "cookies")
        self.assertIn("not available", m.pages["cookies"].sub.text())

    def test_cookies_with_real_store(self):
        try:
            from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
            from PyQt6.QtCore import QTimer, QEventLoop, QUrl
        except Exception:
            self.skipTest("no QtWebEngine")
        import http.server, threading

        class Hd(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.send_header("Set-Cookie", "srv=1; Path=/; Max-Age=86400"); self.send_header("Content-Type", "text/html")
                self.end_headers(); self.wfile.write(b"hi")
            def log_message(self, *a): pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), Hd); threading.Thread(target=srv.serve_forever, daemon=True).start()

        def wait(ms):
            l = QEventLoop(); QTimer.singleShot(ms, l.quit); l.exec()
        prof = QWebEngineProfile("sps-test-%d" % os.getpid())
        prof.setPersistentStoragePath(tempfile.mkdtemp())
        prof.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        tracker = sps_manager.CookieTracker(prof.cookieStore())           # created before pages load, like in the browser
        wait(800)                                                           # the store is ready shortly after start
        pg = QWebEnginePage(prof); pg.load(QUrl("http://127.0.0.1:%d/" % srv.server_port)); wait(2000)
        H = type("H2", (self.H,), {"cookie_store": prof.cookieStore(), "cookie_tracker": tracker})
        m = sps_manager.SpsManager(H, "cookies")
        p = m.pages["cookies"]; p.render()
        self.assertTrue(any(k[2] == "srv" for k in tracker.cookies), tracker.cookies)
        self.assertEqual(p.tree.topLevelItemCount(), 1)
        p.tree.selectAll(); p.on_delete(); wait(600)
        self.assertFalse(tracker.cookies)
        srv.shutdown(); del m, pg


if __name__ == "__main__":
    unittest.main()
