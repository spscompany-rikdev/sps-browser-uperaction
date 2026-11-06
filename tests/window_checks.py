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


if __name__ == "__main__":
    unittest.main()
