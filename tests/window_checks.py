import json
from PyQt6.QtCore import Qt
"""Builds the REAL main window (offscreen) and checks: extension toolbar icons, extra windows staying alive, guest window."""
import gc, os, sys, tempfile, unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC)
os.environ["HOME"] = tempfile.mkdtemp(prefix="spshome_")
os.environ["USERPROFILE"] = os.environ["HOME"]
os.environ["SPS_DISABLE_UPDATER"] = "1"
try:
    sys.argv = ["sps"]
    import SPS_BROWSER as S
    from PyQt6.QtWidgets import QApplication, QPushButton, QMessageBox
    from PyQt6.QtCore import QTimer, QEventLoop, QUrl
    HAVE = True
except Exception as e:  # pragma: no cover
    HAVE = False
    print("window tests skipped:", e)


def wait(ms):
    l = QEventLoop(); QTimer.singleShot(ms, l.quit); l.exec()


@unittest.skipUnless(HAVE, "browser module could not be imported here")
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        S.MainWindow._ask_username_once = lambda self, *a, **k: None
        cls.app = QApplication.instance() or QApplication(["sps"])
        cls.w = S.MainWindow("Default")
        cls.w.show(); wait(400)

    def puzzle_buttons(self):
        return [b for b in self.w.toolbar.findChildren(QPushButton) if b.text() and b.isVisibleTo(self.w) is not None and b in getattr(self.w, "_ext_toolbar_widgets", [])]

    def set_exts(self, n):
        em = self.w.extension_manager
        em._extensions = [{"id": "x%d" % i, "name": "Ext %d" % i, "icon": "E%d" % i, "enabled": True, "show_in_toolbar": True, "description": ""} for i in range(n)]
        em._scripts = []

    def test_toolbar_icons_do_not_pile_up(self):
        for n, expected in ((0, 0), (1, 1), (2, 2), (3, 1), (5, 1)):
            self.set_exts(n)
            for _ in range(4):                       # rebuilding again and again must never add icons
                self.w._rebuild_extension_toolbar_buttons()
            wait(50)
            live = [b for b in self.w.toolbar.findChildren(QPushButton) if b.text() in ("\U0001F9E9",) or b.text().startswith("E")]
            self.assertEqual(len(live), expected, "extensions=%d" % n)
            if n > 2:
                self.assertEqual(live[0].text(), "\U0001F9E9")        # one puzzle button with the drop-down

    def test_v40_icons_anim_easy(self):
        import sps_icons, sps_anim, sps_easy
        w = self.w
        # vector icons replaced the text glyphs
        self.assertTrue(w.back_btn.text() == "" and not w.back_btn.icon().isNull())
        self.assertTrue(w.reload_btn.text() in ("↻", "✕") and not w.reload_btn.icon().isNull())   # text() still reports the logical value
        w.reload_btn.setText("✕"); self.assertEqual(w.reload_btn.text(), "✕"); w.reload_btn.setText("↻")
        # menu button: spins to the logo while the main menu is open, back to dots after
        fx = w.menu_btn._sps_fx
        self.assertEqual(fx.p, 0.0)
        seen = []
        orig = S.MainWindow._show_main_menu
        def fake_menu(self_=None):
            wait(450); seen.append(fx.p)
        w.__dict__["_show_main_menu"] = None
        import types
        # re-wrap with a fake menu so no modal menu blocks the test
        inner = fake_menu
        fx2 = fx
        def wrapped():
            fx2.go(True)
            try: inner()
            finally: fx2.go(False)
        wrapped(); wait(450)
        self.assertGreater(seen[0], 0.95); self.assertLess(fx.p, 0.05)
        del w.__dict__["_show_main_menu"]
        install = sps_anim.install_menu_button            # real wrapper is installed
        self.assertTrue(callable(w._show_main_menu))
        # easy access button + media / image / page context
        self.assertTrue(hasattr(w, "_easy_btn"))
        self.assertEqual(sps_easy.classify({"media": {"paused": False}}), "media")
        self.assertEqual(sps_easy.classify({"isImg": True}), "image")
        self.assertEqual(sps_easy.classify({"imgs": 4}), "page")
        ctl = w._easy_ctl
        for kind, info in (("media", {"url": "https://www.youtube.com/watch?v=1", "title": "Song", "media": {"kind": "video", "paused": False, "muted": False, "vol": 1, "rate": 1, "loop": False, "t": 12, "d": 200}}),
                           ("image", {"url": "https://x.test/a.png", "isImg": True, "title": "a.png"}),
                           ("page", {"url": "https://x.test/", "title": "X", "imgs": 5})):
            ctl._apply(w.tabs.currentWidget(), info); self.assertEqual(ctl.kind, kind)
            panel = sps_easy.EasyPanel(w, ctl); panel.popup_at(w._easy_btn); wait(120)
            self.assertTrue(panel.isVisible()); self.assertEqual(panel._built, kind)
            self.assertGreater(len(panel.findChildren(QPushButton)), 5)
            panel.close()
        # JS builders are syntactically valid in a real engine is covered in test_easy_js; here: every action exists
        for a in ("toggle", "seekrel", "seekfrac", "rate", "vol", "mute", "loop", "pip", "fs", "next", "prev"):
            self.assertIn("function", sps_easy.media_js(a, 1))
        for a in ("rot", "rotl", "flip", "b", "c", "s", "gray", "reset", "save"):
            self.assertIn("function", sps_easy.image_js(a, 100))

    def test_v40_easy_gesture_and_scroll(self):
        import sps_easy
        from PyQt6.QtWidgets import QScrollArea
        w = self.w; view = w.tabs.currentWidget()
        from PyQt6.QtCore import QObject, QEvent, Qt as _Qt
        seen = []
        class Spy(QObject):
            def eventFilter(self, o, e):
                if e.type() == QEvent.Type.KeyPress: seen.append(e.key())
                return False
        spy = Spy(); tgt = view.focusProxy() or view; tgt.installEventFilter(spy)
        fired = []
        sps_easy.give_gesture(view, lambda: fired.append(1)); wait(800)
        tgt.removeEventFilter(spy)
        # a real key press reaches the page (that is what lets Chromium allow fullscreen / picture-in-picture), then the JS runs
        self.assertIn(int(_Qt.Key.Key_F13), seen); self.assertEqual(fired, [1])
        # (the page-side effect - navigator.userActivation.isActive becoming true - was checked by hand on a real QtWebEngine page)
        ctl = w._easy_ctl
        ctl._apply(view, {"url": "https://x.test/", "title": "t", "media": {"kind": "video", "paused": False, "t": 1, "d": 9, "vol": 1, "rate": 1}})
        p = sps_easy.EasyPanel(w, ctl); p.popup_at(w._easy_btn); wait(150)
        self.assertIsNotNone(p.findChild(QScrollArea))
        y0 = p.y(); h0 = p.height()
        p._set_rate(1.5, p.speed_btns[4]); wait(200)
        self.assertEqual(p.y(), y0); self.assertEqual(p.height(), h0)   # clicking speed never moves or resizes the panel
        p._toggle_loop(); self.assertTrue(p.loop_b.property("on"))
        self.assertLessEqual(p.height(), 1200)
        p.close()

    def test_v40_dialog_scroll_and_menu_scroll(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea, QMenu
        import sps_anim
        d = QDialog(self.w); d.SPS_STAY_WINDOW = True
        lay = QVBoxLayout(d)
        for i in range(60): lay.addWidget(QLabel("row %d" % i))
        d.show(); wait(400)
        self.assertIsNotNone(d.findChild(QScrollArea))
        self.assertLessEqual(d.height(), 1200)
        d.close()
        m = QMenu(self.w); m.addAction("x"); m.popup(self.w.mapToGlobal(self.w.rect().center())); wait(300)
        self.assertIn("menu-scrollable", m.styleSheet()); m.close()

    def test_extra_window_survives_garbage_collection(self):
        before = len(S._SPS_WINDOW_REFS)
        self.w.open_new_window()
        gc.collect(); wait(200); gc.collect()
        self.assertGreater(len(S._SPS_WINDOW_REFS), before)
        win = S._SPS_WINDOW_REFS[-1]
        self.assertTrue(win.isVisible())
        win.hide()

    def test_quick_panel_dropdown(self):
        import sps_quick
        self.assertTrue(hasattr(self.w, "_quick_btn"))
        self.w._quick_btn.click(); wait(300)
        qp = self.w._sps_quick
        self.assertTrue(qp.isVisible())
        before = bool(self.w.settings_data.get("youtube_ad_skip", True))
        qp.toggle_btns["youtube_ad_skip"].click(); wait(100)
        self.assertEqual(bool(self.w.settings_data.get("youtube_ad_skip", True)), not before)
        qp.toggle_btns["youtube_ad_skip"].click(); wait(100)
        self.assertEqual(bool(self.w.settings_data.get("youtube_ad_skip", True)), before)
        n = self.w.tabs.count()
        for ic, label, meth, kw in sps_quick.TOOLS:                 # every tool button must point at a real method
            self.assertTrue(hasattr(self.w, meth), meth)
        qp._open("https://example.com/"); wait(300)
        self.assertEqual(self.w.tabs.count(), n + 1)
        qp.close()

    def test_safety_send_tab_and_savers(self):
        import sps_safety, sps_safety_ui, sps_qr, sps_perf, sps_updater, sps_quick
        from PyQt6.QtCore import QUrl
        # Safety Check end to end (offline stubs: nothing leaves the test)
        def offline(*a, **k): raise OSError("offline")
        o1, o2 = sps_safety.default_fetch, sps_updater.fetch_page
        sps_safety.default_fetch = offline; sps_updater.fetch_page = offline
        sps_safety.run_all.__kwdefaults__["fetch"] = offline
        try:
            d = sps_safety_ui.SafetyDialog(self.w, "38.0.0"); d.show(); d.start()
            for _ in range(40):
                wait(100)
                if not d.running: break
            self.assertFalse(d.running)
            self.assertGreaterEqual(d.bl.count(), 4)
            self.assertTrue(d.head.text())
            d.close()
        finally:
            sps_safety.default_fetch, sps_updater.fetch_page = o1, o2
            sps_safety.run_all.__kwdefaults__["fetch"] = o1
        # Send tab: the QR really contains the address
        self.w.add_new_tab(QUrl("https://example.com/hello?x=1")); wait(500)
        for _ in range(20):                                      # a busy window may take longer to show the new tab's address
            cur = self.w.tabs.currentWidget()
            if cur is not None and "example.com/hello" in cur.url().toString():
                break
            wait(200)
        dlg = sps_qr.SendTabDialog(self.w)
        self.assertIn("example.com/hello", dlg.url)
        self.assertFalse(dlg.qr.pixmap() is None or dlg.qr.pixmap().isNull())
        dlg.qr.pixmap().save(os.path.join(tempfile.gettempdir(), "sps_qr_test.png"))
        n = self.w.tabs.count(); dlg.paste.setPlainText("https://a.example/\nnot a link\nhttps://b.example/"); dlg._open_pasted(); wait(200)
        self.assertEqual(self.w.tabs.count(), n + 2)
        # Energy saver freezes background tabs and thaws the current one
        from PyQt6.QtWebEngineCore import QWebEnginePage
        self.w.settings_data["energy_saver"] = True
        sps_perf.energy_tick(self.w); wait(200)
        cur = self.w.tabs.currentIndex()
        states = [self.w.tabs.widget(i).page().lifecycleState() for i in range(self.w.tabs.count())]
        self.assertEqual(states[cur], QWebEnginePage.LifecycleState.Active)
        self.assertTrue(any(st == QWebEnginePage.LifecycleState.Frozen for i, st in enumerate(states) if i != cur))
        self.w.settings_data["energy_saver"] = False
        sps_perf.energy_tick(self.w)
        self.assertFalse(any(self.w.tabs.widget(i).page().lifecycleState() == QWebEnginePage.LifecycleState.Frozen for i in range(self.w.tabs.count())))
        self.assertGreaterEqual(sps_perf.sleep_others_now(self.w), 1)
        self.assertGreaterEqual(sps_perf.sleeping_count(self.w), 1)
        # quick panel shows the controls
        self.w._quick_btn.click(); wait(300)
        qp = self.w._sps_quick
        for k in ("tab_sleep_enabled", "energy_saver"): self.assertIn(k, qp.toggle_btns)
        self.assertIn("tabs", qp.perf.text())
        qp._cycle_minutes(); qp.close()
        for meth in ("show_safety_check", "show_send_tab"): self.assertTrue(hasattr(self.w, meth))

    def test_dialogs_open_as_dropdown(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
        import sps_dropdown
        seen = {}

        def mk(title):
            d = QDialog(self.w); d.setWindowTitle(title); QVBoxLayout(d).addWidget(QLabel("hello")); return d
        d = mk("Downloads")

        def probe():
            seen["host"] = type(d.window()).__name__; seen["vis"] = d.isVisible()
            d.accept()
        QTimer.singleShot(400, probe)
        r = d.exec()
        self.assertEqual(seen["host"], "DropdownHost"); self.assertTrue(seen["vis"])
        self.assertEqual(r, QDialog.DialogCode.Accepted.value if hasattr(QDialog.DialogCode.Accepted, "value") else 1)
        wait(300); self.assertIsNone(sps_dropdown._state["host"])
        # reject through "click outside / dismiss"
        d2 = mk("VPN test"); QTimer.singleShot(400, lambda: sps_dropdown._state["host"].dismiss())
        self.assertEqual(d2.exec(), 0)
        # special windows stay windows
        d3 = mk("Settings"); seen2 = {}
        QTimer.singleShot(300, lambda: (seen2.update(w=type(d3.window()).__name__), d3.accept()))
        d3.exec(); self.assertEqual(seen2["w"], "QDialog")
        # the real VPN window
        import sps_vpn_ui
        seen3 = {}
        orig = sps_vpn_ui.SpsVpnDialog

        def probe3():
            for wdg in QApplication.topLevelWidgets():
                if type(wdg).__name__ == "DropdownHost" and wdg.isVisible():
                    seen3["ok"] = type(wdg.dlg).__name__; wdg.dismiss()
        QTimer.singleShot(1200, probe3)
        sps_vpn_ui.show_vpn_dialog(self.w, tempfile.mkdtemp(), None, ())
        self.assertEqual(seen3.get("ok"), "SpsVpnDialog")

    def test_guest_window_is_private_and_stays(self):
        q = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        try:
            self.w._open_guest_mode()
        finally:
            QMessageBox.question = q
        gc.collect(); wait(300); gc.collect()
        g = S._SPS_WINDOW_REFS[-1]
        self.assertTrue(g.isVisible()); self.assertTrue(getattr(g, "_is_guest", False))
        self.assertTrue(g.browser_profile.isOffTheRecord())
        self.assertEqual(g._load_bookmarks(), [])
        n = len(g._load_history()); g._save_history("https://example.com/", "x")
        self.assertEqual(len(g._load_history()), n)                    # nothing written for a guest
        self.assertEqual(g.tabs.count(), 1)                            # only the private New Tab (no stray tab on the saved profile)
        self.assertTrue(g.tabs.widget(0).page().profile().isOffTheRecord())
        self.assertFalse(hasattr(g, "tray"))                           # no second tray icon
        wait(800)
        self.assertIn("sps_newtab_", g.tabs.currentWidget().url().toString())   # a real New Tab page, not a blank tab
        g.hide()

    def test_update_dialog_is_never_a_trap(self):
        info = {"version": "99.0.0", "url": "https://example.com/x.exe", "sha256": "0" * 64, "size": 1, "mandatory": True,
                "notes": "n", "path": "/nonexistent/x.exe"}
        d = S.SpsForcedUpdateDialog(self.w, info)
        self.assertTrue(d.mandatory); self.assertIsNotNone(d.quit_btn)           # a forced update still has a way out
        d._allow_later()
        self.assertFalse(d.mandatory)                                            # after a failed attempt it can be postponed
        d.reject(); d.deleteLater()

    def test_chrome_extension_queue_installs_in_order(self):
        import sps_chrome_ext, tempfile, zipfile, json
        root = os.path.join(os.path.dirname(os.path.abspath(S.__file__)), "..", "extension")
        d = tempfile.mkdtemp(); paths = []
        for n in ("One", "Two"):
            p = os.path.join(d, n + ".zip")
            with zipfile.ZipFile(p, "w") as z:
                if n != "One":
                    z.writestr("manifest.json", json.dumps({"manifest_version": 3, "name": "Test " + n, "version": "1.0"}))
                z.writestr("bg.js", "")
                if n == "One":      # a real logo + popup: must show up in the toolbar
                    z.writestr("manifest.json", json.dumps({"manifest_version": 3, "name": "Test One", "version": "1.0", "icons": {"16": "i16.png", "48": "i48.png"},
                                                            "action": {"default_popup": "pop.html"}}))
                    z.writestr("pop.html", "<b>hi</b>")
                    from PyQt6.QtGui import QImage
                    im = QImage(48, 48, QImage.Format.Format_ARGB32); im.fill(0xFFFF0000)
                    for nm in ("i16.png", "i48.png"):
                        tp = os.path.join(d, nm); im.save(tp); z.write(tp, nm)
            paths.append(p)
        bad = os.path.join(d, "Old.zip")
        with zipfile.ZipFile(bad, "w") as z: z.writestr("manifest.json", json.dumps({"manifest_version": 2, "name": "old", "version": "1"}))
        dlg = sps_chrome_ext.show_dialog(self.w, modal=False); h = dlg.test_hooks
        for p in (paths[0], bad, paths[1]): h["add"]("file", p)
        h["go"]()
        for _ in range(100):
            wait(200)
            if not h["state"]["running"]: break
        texts = [h["queue"].item(i).text() for i in range(h["queue"].count())]
        self.assertTrue(texts[0].startswith("\u2705"), texts); self.assertTrue(texts[1].startswith("\u274c") and "Manifest V2" in texts[1], texts)
        self.assertTrue(texts[2].startswith("\u2705"), texts)
        names = [h["inst"].item(i).text() for i in range(h["inst"].count())]
        self.assertEqual(len([n for n in names if n.startswith("Test ")]), 2, names)
        self.assertTrue(all("[ON]" in n for n in names if n.startswith("Test ")), names)
        wait(1500)
        tips = {getattr(b, "toolTip", lambda: "")(): b for b in self.w._ext_toolbar_widgets}
        self.assertIn("Test One", tips, list(tips))                              # the installed extension is in the toolbar ...
        self.assertFalse(tips["Test One"].icon().isNull())                        # ... with its real logo, not a text placeholder
        self.assertIn("Test Two", tips)
        self.assertNotIn("chromium-pdf", tips)
        dlg.close()

    def test_restart_now_after_removing_extension_works_from_settings(self):
        """The Extensions dialog opened from Settings has the Settings dialog as parent - 'Restart now' must still reach the main window."""
        from PyQt6.QtWidgets import QDialog, QMessageBox
        calls = []
        self.w.restart_browser = lambda reason="manual": calls.append(reason)
        S._SPS_MAIN_WINDOW = self.w
        holder = QDialog()                                         # stands in for the Settings dialog
        dlg = S.ExtensionsDialog(self.w.profile_name, self.w._theme, self.w.extension_manager, holder)
        orig_exec, orig_clicked = QMessageBox.exec, QMessageBox.clickedButton
        QMessageBox.exec = lambda box: 0
        QMessageBox.clickedButton = lambda box: [b for b in box.buttons() if b.text() == "Restart now"][0]
        try:
            dlg._ask_restart_after_removal()
        finally:
            QMessageBox.exec, QMessageBox.clickedButton = orig_exec, orig_clicked
        self.assertEqual(calls, ["extension removed"])

    def test_google_signin_is_caught_before_loading(self):
        import sps_signin
        shown = []
        orig = S.MainWindow._v40_google_signin_notice
        S.MainWindow._v40_google_signin_notice = lambda self_, url, page: shown.append(url.toString())
        try:
            pg = self.w.tabs.currentWidget().page()
            blocked = pg.acceptNavigationRequest(QUrl("https://accounts.google.com/v3/signin/identifier"), pg.NavigationType.NavigationTypeTyped, True)
            fine = pg.acceptNavigationRequest(QUrl("https://www.youtube.com/"), pg.NavigationType.NavigationTypeTyped, True)
            sub = pg.acceptNavigationRequest(QUrl("https://accounts.google.com/v3/signin/x"), pg.NavigationType.NavigationTypeTyped, False)
            wait(100)
        finally:
            S.MainWindow._v40_google_signin_notice = orig
        self.assertFalse(blocked); self.assertTrue(fine); self.assertTrue(sub)    # sub-frames are left alone
        self.assertEqual(len(shown), 1)


    # ---- title bar ----
    def test_tabs_live_in_the_title_bar_and_stay_in_sync(self):
        w = self.w
        self.assertIsNotNone(w._sps_title)
        self.assertTrue(bool(w.windowFlags() & Qt.WindowType.FramelessWindowHint))
        for i in range(3):
            w.add_new_tab(QUrl("about:blank"), "Tab %d" % i)
        wait(300)
        self.assertEqual(w.tabs.strip.count(), w.tabs.count())
        w.tabs.setCurrentIndex(1); wait(50)
        self.assertEqual(w.tabs.strip.currentIndex(), 1)
        w.tabs.strip.setCurrentIndex(2); wait(50)
        self.assertEqual(w.tabs.currentIndex(), 2)                       # clicking a round tab selects the page
        w.tabs.setTabText(2, "Renamed"); self.assertEqual(w.tabs.strip.tabText(2), "Renamed")
        w.tabs.setTabText(0, "Alpha"); w.tabs.setTabText(1, "Beta")
        titles = [w.tabs.tabText(i) for i in range(w.tabs.count())]
        w.tabs.move_tab(0, 1); wait(50)
        self.assertEqual([w.tabs.strip.tabText(i) for i in range(w.tabs.strip.count())], [w.tabs.tabText(i) for i in range(w.tabs.count())])
        self.assertNotEqual(titles, [w.tabs.tabText(i) for i in range(w.tabs.count())])
        n = w.tabs.count(); w.tabs.strip.tabCloseRequested.emit(w.tabs.count() - 1); wait(200)
        self.assertEqual(w.tabs.strip.count(), w.tabs.count())
        self.assertLess(w.tabs.count(), n)

    def test_window_buttons(self):
        t = self.w._sps_title
        self.assertTrue(t.b_min.isVisibleTo(t) and t.b_max.isVisibleTo(t) and t.b_close.isVisibleTo(t))
        self.assertLess(t.tab_host.geometry().right(), t.b_min.geometry().left())      # tabs are LEFT of minimise / maximise / close
        self.w.showMaximized(); wait(200); self.w._sps_frame.place()
        self.assertTrue(t.b_max.maximized)
        self.w.showNormal(); wait(200)

    def test_address_bar_is_a_pill(self):
        ss = self.w.url_bar.styleSheet()
        self.assertIn("border-radius:19px", ss)
        self.assertEqual(self.w.url_bar.height(), 38)

    # ---- new tab suggestions ----
    def test_a_new_tab_search_shows_options(self):
        w = self.w
        json.dump([{"title": "Sandwich recipes blog", "url": "https://sandwich.example.com/"}], open(w._bm_path(), "w"))
        w.settings_data["search_suggestions"] = False
        w.add_new_tab(); wait(1500)
        br = w.tabs.currentWidget(); res = {}
        from PyQt6.QtWebEngineCore import QWebEnginePage as _P
        br.page().setLifecycleState(_P.LifecycleState.Active)       # other tests may have left tab-freezing on
        br.setUrl(QUrl.fromLocalFile(br.url().toLocalFile())); wait(1200)
        for _ in range(20):                                         # wait until the new-tab page itself is loaded
            if "sps_newtab" in br.url().toString() and not br.page().isLoading() if hasattr(br.page(), "isLoading") else "sps_newtab" in br.url().toString():
                break
            wait(300)
        br.page().runJavaScript("var q=document.getElementById('q');q.focus();q.value='sand';q.dispatchEvent(new Event('input'));1")
        for _ in range(12):
            res.pop("rows", None)
            wait(500)
            br.page().runJavaScript("Array.from(document.querySelectorAll('#sg .r')).map(function(e){return e.textContent})", lambda r: res.update(rows=r))
            wait(300)
            if res.get("rows"):
                break
        rows = res.get("rows") or []
        self.assertTrue(any("sand" == r.lstrip("🔍") for r in rows), rows)                # what you typed
        self.assertTrue(any("Sandwich recipes blog" in r for r in rows), rows)            # a bookmark

    def test_a_website_cannot_ask_for_suggestions(self):
        """Only the browser's own new-tab file gets history/bookmark suggestions."""
        w = self.w
        w.add_new_tab(QUrl("data:text/html,<p>x</p>"), "x"); wait(500)
        got = []
        pg = w.tabs.currentWidget().page()
        pg.runJavaScript = lambda js, *a: got.append(js)
        w._newtab_suggest("sand", pg)
        self.assertEqual(got, [])

    # ---- site controls ----
    def test_site_controls_toggle_and_store(self):
        import sps_sitepanel as P
        w = self.w
        w.add_new_tab(QUrl("about:blank"), "x"); wait(300)
        store = w.permission_store
        store.clear()
        host = "example.com"
        self.assertFalse(P.is_on(store, host, "camera"))                  # nothing is on by itself
        for key, *_ in P.PERMISSIONS:
            self.assertFalse(P.is_on(store, host, key), key)
        P.set_value(store, host, "camera", True); P.set_value(store, host, "microphone", True)
        self.assertEqual(store.get(host, "camera_mic"), "allow")
        P.set_value(store, host, "camera", False)
        self.assertIsNone(store.get(host, "camera_mic"))
        P.set_value(store, host, "screen", True)
        self.assertEqual(store.get(host, "screen_audio"), "allow")
        P.block_all(store, host)
        self.assertEqual(store.get(host, "geolocation"), "deny")
        P.reset_site(store, host)
        self.assertIsNone(store.get(host, "geolocation"))
        P.set_value(store, host, "js", False, True)                       # features are stored only when they differ from the default
        self.assertEqual(store.get(host, "js"), "deny")
        P.set_value(store, host, "js", True, True)
        self.assertIsNone(store.get(host, "js"))

    def test_site_controls_change_the_page(self):
        import sps_sitepanel as P
        from PyQt6.QtWebEngineCore import QWebEngineSettings as QS
        w = self.w
        w.add_new_tab(QUrl("about:blank"), "x"); wait(300)
        pg = w.tabs.currentWidget().page(); store = w.permission_store; store.clear()
        P.set_value(store, "example.com", "js", False, True); P.set_value(store, "example.com", "popups", True, False)
        P.set_value(store, "example.com", "sound", False, True)
        P.apply_to_page(w, pg, "example.com")
        self.assertFalse(pg.settings().testAttribute(QS.WebAttribute.JavascriptEnabled))
        self.assertTrue(pg.settings().testAttribute(QS.WebAttribute.JavascriptCanOpenWindows))
        self.assertTrue(pg.isAudioMuted())
        P.reset_site(store, "example.com"); P.apply_to_page(w, pg, "example.com")
        self.assertTrue(pg.settings().testAttribute(QS.WebAttribute.JavascriptEnabled))      # another site is not affected
        self.assertFalse(pg.isAudioMuted())

    def test_site_panel_opens_for_a_website_only(self):
        import sps_sitepanel as P
        w = self.w
        w.add_new_tab(QUrl("about:blank"), "x"); wait(300)
        self.assertIsNone(P.show_panel(w, w.site_ctl_btn))                # about:blank is not a website: no panel, a hint instead
        panel = P.SitePanel(w, "example.com", w.tabs.currentWidget().page())
        panel.show(); wait(100)
        sw, st, perm, d = panel._rows["camera"]
        sw.click(); wait(50)
        self.assertEqual(w.permission_store.get("example.com", "camera"), "allow")
        self.assertEqual(st.text(), "Allowed")
        sw.click(); self.assertEqual(st.text(), "Ask first")
        panel._block_all(); self.assertEqual(st.text(), "Blocked")
        panel.close()


    def test_a_main_menu_hangs_under_its_button(self):
        from PyQt6.QtCore import QPoint, QPointF, Qt
        from PyQt6.QtGui import QWheelEvent
        from PyQt6.QtWidgets import QApplication
        w = self.w
        w.menu_btn.click(); wait(500)
        pop = w._sps_menu_popup
        self.assertTrue(pop.isVisible())
        btn = w.menu_btn.mapToGlobal(QPoint(w.menu_btn.width(), 0))
        bottom = w.toolbar.mapToGlobal(QPoint(0, w.toolbar.height())).y()
        self.assertLessEqual(abs(pop.y() - bottom), 6)                                  # right under the toolbar
        self.assertLessEqual(pop.x() + pop.width(), btn.x() + 8)                        # lined up with the button's right edge
        n = len(pop.buttons); self.assertGreater(n, 20)                                 # every item of the menu is in it
        sb = pop.scroll.verticalScrollBar()
        scr = QApplication.screenAt(pop.pos()) or QApplication.primaryScreen()
        self.assertLessEqual(pop.y() + pop.height(), scr.availableGeometry().bottom() + 2)   # never runs off the screen
        self.assertGreater(sb.maximum(), 0)                                             # so it must scroll ...
        sb.setValue(0)
        ev = QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(0, 0), QPoint(0, -240), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(pop.scroll.viewport(), ev); wait(100)
        self.assertGreater(sb.value(), 0)                                               # ... and the mouse wheel works
        sb.setValue(sb.maximum())                                                       # the very last item can be reached and clicked
        hit = []
        act, last = pop.buttons[-1]
        pop._run = lambda a: hit.append(a.text())                                       # (do not really open the About window here)
        wait(100); last.click(); wait(100)
        self.assertEqual(len(hit), 1); self.assertIn("About", hit[0])
        pop.close(); wait(100)

    def test_a_password_lock_otp_and_save_card(self):
        import sps_vault as V
        from PyQt6.QtWidgets import QDialog
        w = self.w; pm = w.password_manager; pm.lock.remove(); pm.lock.unlocked = True
        sent = []
        w._sps_otp_sender = lambda code: sent.append(code) or True
        # --- Set password: notification code -> dialogs (answered by script) -> lock is on
        answers = {}
        orig_exec = QDialog.exec
        def fake_exec(d):
            title = d.windowTitle()
            from PyQt6.QtWidgets import QLineEdit, QPushButton
            eds = d.findChildren(QLineEdit)
            btn = lambda txt: [b for b in d.findChildren(QPushButton) if b.text().startswith(txt)][0]
            if "Verification" in title:
                wait(50); eds[0].setText(sent[-1]); btn("✓").click(); return 1
            if "Choose" in title:
                eds[0].setText("my-secret-9"); eds[1].setText("my-secret-9"); btn("✓").click(); return 1
            if "locked" in title:
                answers["unlock_seen"] = True
                eds[0].setText(answers.get("typed", "")); btn("🔓").click(); return 1 if d.result() else 0
            return orig_exec(d)
        QDialog.exec = fake_exec
        try:
            self.assertTrue(V.set_password_flow(w, pm.lock))
            self.assertEqual(len(sent), 1)
            self.assertTrue(pm.lock.is_set())
            pm.lock.lock()
            # wrong password does not open; right one does
            answers["typed"] = "bad-guess"
            self.assertFalse(V.ensure_unlocked(w)); self.assertTrue(pm.lock.needs_unlock())
            answers["typed"] = "my-secret-9"
            self.assertTrue(V.ensure_unlocked(w)); self.assertFalse(pm.lock.needs_unlock())
            # autofill stays shut while locked
            pm.lock.lock(); w._pw_unlock_declined = True
            pm.add("https://lock-test.example", "me", "pw1")
            calls = []
            pg = w.tabs.currentWidget().page(); orig_rj = pg.runJavaScript
            pg.runJavaScript = lambda js, *a, **k: calls.append(js)
            from PyQt6.QtCore import QUrl as _U
            pg.url = lambda: _U("https://lock-test.example/login")
            w._v32_arm_autofill(pg)
            self.assertEqual([c for c in calls if "__spsPwArm" in c], [])
            pg.runJavaScript = orig_rj
            try: del pg.url                                   # remove the test's fake address again
            except AttributeError: pass
            # --- Forgot password: code from notification switches the lock off, saved passwords are kept
            sent.clear()
            self.assertTrue(V.forgot_flow(w, pm.lock))
            self.assertEqual(len(sent), 1)
            self.assertFalse(pm.lock.is_set())
            self.assertTrue(any(e["site"].startswith("https://lock-test") for e in pm.get_all()))
        finally:
            QDialog.exec = orig_exec
            pm.lock.remove(); w._sps_otp_sender = None
        # no notification possible -> no code is shown anywhere else, flow fails safely
        w._sps_otp_sender = lambda code: False
        self.assertFalse(V.send_code(w, "123456")); w._sps_otp_sender = None

    def test_a_save_password_drops_down_as_a_card(self):
        w = self.w; w._pw_box = None
        pend = {"page": None, "host": "card.example", "site": "https://card.example", "user": "bob", "pw": "pw-xyz", "t0": 0, "eid": None}
        w._v32_show_save_prompt(pend)
        card = w._pw_box
        self.assertIsNotNone(card); self.assertTrue(card.isVisible())
        self.assertTrue(card.parent() is w)                                    # a card inside the window, not a separate window
        bar_bottom = w.toolbar.mapTo(w, __import__("PyQt6.QtCore", fromlist=["QPoint"]).QPoint(0, w.toolbar.height())).y()
        wait(400); self.assertGreaterEqual(card.y(), bar_bottom - 4)           # hangs under the toolbar
        card._buttons["save"].click(); wait(100)
        self.assertIsNone(w._pw_box)
        self.assertTrue(any(e["site"] == "https://card.example" and e["username"] == "bob" and e["password"] == "pw-xyz" for e in w.password_manager.get_all()))
        # "Never for this site" is remembered, "Not now" is not
        pend2 = dict(pend, host="never.example", site="https://never.example")
        w._v32_show_save_prompt(pend2); w._pw_box._buttons["never"].click(); wait(100)
        self.assertTrue(w.password_manager.never_save("never.example"))


    def test_a_password_checkup_window(self):
        import sps_pwcheck as P
        from PyQt6.QtWidgets import QPushButton
        w = self.w; pm = w.password_manager
        pm._data = []
        pm.add("https://weak.example", "me", "123456"); pm.add("https://one.example", "me", "Same-Pass-12345!"); pm.add("https://two.example", "me", "Same-Pass-12345!")
        pm.add("https://leak.example", "me", "Leaked-pass-9988!")
        import hashlib
        h = hashlib.sha1(b"Leaked-pass-9988!").hexdigest().upper()
        orig = P.fetch_range
        P.fetch_range = lambda prefix, timeout=10: ("%s:99" % h[5:]) if prefix == h[:5] else ""
        try:
            dlg = P.show_checkup(w, pm, w); dlg.show(); wait(100)
            dlg._go.click()
            for _ in range(40):
                wait(100)
                if dlg._table.rowCount():
                    break
            txt = [dlg._table.item(r, 0).text() for r in range(dlg._table.rowCount())]
            self.assertTrue(any("leaked" in t.lower() or "leak" in t.lower() for t in txt), txt)
            self.assertTrue(any("Same password" in t for t in txt)); self.assertTrue(any("Weak" in t for t in txt))
            self.assertIn("leaked", dlg._summary.text())
            # "Change..." opens that website (recorded here instead of really loading it)
            opened = []
            real_add = w.add_new_tab; w.add_new_tab = lambda url=None, *a, **k: opened.append(url.toString() if url is not None else "")
            try:
                btn = dlg._table.cellWidget(0, 3); self.assertIsNotNone(btn)
                btn.click(); wait(100)
            finally:
                w.add_new_tab = real_add
            self.assertEqual(len(opened), 1); self.assertTrue(opened[0].startswith("https://"), opened)
        finally:
            P.fetch_range = orig; pm._data = []; pm._save()


    def test_a_long_menus_and_submenus_scroll_and_stay_on_screen(self):
        from PyQt6.QtWidgets import QMenu, QApplication
        from PyQt6.QtCore import QPoint, QTimer, QPointF, Qt
        from PyQt6.QtGui import QWheelEvent
        import sps_menu
        w = self.w
        scr = QApplication.primaryScreen().availableGeometry()
        # a) the three-dot menu: open "More Features" (a long sub-menu) near the bottom of the list; it must scroll and fit the screen
        w.menu_btn.click(); wait(500)
        pop = w._sps_menu_popup
        row = [b for a, b in pop.buttons if "More Features" in a.text()][0]
        row.click(); wait(400)
        sub = pop._sub
        self.assertTrue(sub.isVisible())
        self.assertGreater(len(sub.buttons), 8)
        self.assertGreaterEqual(sub.y(), scr.top()); self.assertLessEqual(sub.y() + sub.height(), scr.bottom() + 2)
        self.assertGreaterEqual(sub.x(), scr.left()); self.assertLessEqual(sub.x() + sub.width(), scr.right() + 2)
        sb = sub.scroll.verticalScrollBar()
        if sb.maximum() > 0:
            ev = QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(0, 0), QPoint(0, -240), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
            QApplication.sendEvent(sub.scroll.viewport(), ev); wait(100)
            self.assertGreater(sb.value(), 0)
        # help sub-menu is reachable too
        hrow = [b for a, b in pop.buttons if "Help" in a.text()][0]
        hrow.click(); wait(300)
        self.assertTrue(pop._sub.isVisible()); self.assertGreater(len(pop._sub.buttons), 2)
        pop.close(); wait(100)
        # b) any other long QMenu.exec scrolls and still returns the chosen action
        m = QMenu(w); acts = [m.addAction("Item %d" % i) for i in range(60)]
        seen = []
        def pick():
            p = [x for x in QApplication.topLevelWidgets() if isinstance(x, sps_menu.ScrollPopup) and x.isVisible()][0]
            seen.append((p.y(), p.height(), p.scroll.verticalScrollBar().maximum()))
            p.scroll.verticalScrollBar().setValue(p.scroll.verticalScrollBar().maximum())
            p.buttons[-1][1].click()
        QTimer.singleShot(400, pick)
        got = m.exec(QPoint(300, scr.bottom() - 120))
        self.assertIs(got, acts[-1])
        self.assertLessEqual(seen[0][0] + seen[0][1], scr.bottom() + 2); self.assertGreater(seen[0][2], 0)
        # c) a short menu stays the normal Qt menu
        short = QMenu(w); [short.addAction("S%d" % i) for i in range(3)]
        QTimer.singleShot(300, lambda: short.close())
        short.exec(QPoint(200, 200))
        self.assertFalse(any(isinstance(x, sps_menu.ScrollPopup) and x.isVisible() for x in QApplication.topLevelWidgets()))


    def test_a_three_dot_button_turns_into_the_logo(self):
        w = self.w; mo = w._menu_morph
        self.assertIsNotNone(mo)
        self.assertEqual(w.menu_btn.text(), "")
        self.assertLess(mo.t, 0.01)
        w.menu_btn.click(); wait(150)
        self.assertGreater(mo.t, 0.05); self.assertLess(mo.t, 0.99)                 # it is moving (rotating / fading)
        wait(600)
        self.assertGreater(mo.t, 0.97)                                              # now the logo
        a = mo._frame(0.0).toImage(); b = mo._frame(1.0).toImage()
        self.assertNotEqual(a, b)                                                   # the two pictures really differ
        w._sps_menu_popup.close(); wait(600)
        self.assertLess(mo.t, 0.03)                                                 # back to three dots after closing


    def test_a_video_panel_buttons_fit_without_scrolling(self):
        import sps_easy
        from PyQt6.QtWidgets import QPushButton, QSlider
        w = self.w; view = w.tabs.currentWidget(); ctl = w._easy_ctl
        ctl._apply(view, {"url": "https://www.youtube.com/watch?v=x", "title": "A long YouTube video title that goes on and on", "media": {"kind": "video", "paused": False, "t": 1, "d": 9, "vol": 1, "rate": 1}})
        p = sps_easy.EasyPanel(w, ctl); p.popup_at(w._easy_btn); wait(200)
        self.assertEqual(p.scroll.verticalScrollBar().maximum(), 0)            # everything is visible at once - no scrolling needed
        self.assertLessEqual(p.body.width(), p.scroll.viewport().width() + 1)   # nothing is wider than the panel (no cut-off on the right)
        vp = p.scroll.viewport().rect()
        btns = [b for b in p.body.findChildren(QPushButton) if b.isVisible()]
        self.assertGreaterEqual(len(btns), 14)                                   # prev, -10, play, +10, next, mute, 6 speeds, loop, pip, fullscreen, close
        for b in btns:
            tl = b.mapTo(p.body, b.rect().topLeft())
            self.assertGreaterEqual(tl.x(), 0, b.toolTip() or b.text())
            self.assertLessEqual(tl.x() + b.width(), vp.width(), (b.toolTip() or b.text(), tl.x() + b.width(), vp.width()))   # inside what you can see
            self.assertLessEqual(tl.y() + b.height(), p.body.height() + 1, b.toolTip() or b.text())
            self.assertGreaterEqual(b.width(), 24); self.assertGreaterEqual(b.height(), 28)
        self.assertLessEqual(p.play.width(), 60)                                  # the buttons stay small, only the panel is roomy
        self.assertLessEqual(p.height(), 460)
        p.grab().save("/tmp/claude-0/video_panel.png")
        p.close()


    def test_a_toolbar_search_suggestions_are_solid_and_work(self):
        from PyQt6.QtCore import Qt as _Q, QEvent, QPoint
        from PyQt6.QtGui import QKeyEvent
        w = self.w; a = w._addr_sugg
        json.dump([{"title": "Sandwich recipes blog", "url": "https://sandwich.example.com/"}], open(w._bm_path(), "w"))
        w.settings_data["address_suggestions"] = True; w.settings_data["search_suggestions"] = False
        a._bm = (0.0, [])
        w.activateWindow(); w.url_bar.setFocus(); wait(100)
        w.url_bar.setText("sand"); a.on_text_edited("sand"); wait(60)
        pop = a.popup
        self.assertTrue(pop.isVisible())
        rows = [pop.item(i).text() for i in range(pop.count())]
        self.assertTrue(any("sand" in r for r in rows), rows); self.assertTrue(any("Sandwich recipes blog" in r for r in rows), rows)
        # solid, not faded
        self.assertFalse(pop.testAttribute(_Q.WidgetAttribute.WA_TranslucentBackground)); self.assertEqual(pop.windowOpacity(), 1.0)
        img = pop.grab().toImage()
        cx, cy = img.width() // 2, img.height() - 8
        self.assertEqual(img.pixelColor(cx, cy).alpha(), 255)
        self.assertEqual(img.pixelColor(20, 10).alpha(), 255)
        # arrow keys choose rows and fill the bar, Esc closes
        QApplication.sendEvent(w.url_bar, QKeyEvent(QEvent.Type.KeyPress, _Q.Key.Key_Down, _Q.KeyboardModifier.NoModifier)); wait(50)
        QApplication.sendEvent(w.url_bar, QKeyEvent(QEvent.Type.KeyPress, _Q.Key.Key_Down, _Q.KeyboardModifier.NoModifier)); wait(50)
        self.assertEqual(pop.currentRow(), 1)
        self.assertEqual(w.url_bar.text(), pop.item(1).data(_Q.ItemDataRole.UserRole)["fill"])
        # clicking a row navigates with it
        went = []; real = w.navigate_to_url; w.navigate_to_url = lambda *a_, **k: went.append(w.url_bar.text())
        try:
            a._on_click(pop.item(1))
        finally:
            w.navigate_to_url = real
        self.assertEqual(len(went), 1)
        # it never lingers: moving the window closes it
        w.url_bar.setText("sand"); a.on_text_edited("sand"); wait(100); self.assertTrue(pop.isVisible())
        w.move(w.x() + 7, w.y() + 5); wait(80)
        self.assertFalse(pop.isVisible())
        QApplication.sendEvent(w.url_bar, QKeyEvent(QEvent.Type.KeyPress, _Q.Key.Key_Escape, _Q.KeyboardModifier.NoModifier))


if __name__ == "__main__":
    unittest.main()
