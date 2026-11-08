"""Easy access: one smart toolbar button (like Chrome's media / tools button).

* something is playing (YouTube, music ...)  -> media controls: play/pause, previous/next, +-10 s, seek bar, speed, volume, mute, loop,
  picture-in-picture, fullscreen, "go to that tab".  Works for a tab in the background too.
* a photo is open                            -> photo tools: zoom, rotate, flip, brightness/contrast/saturation, grayscale, save, copy address,
  search with Google Lens, print, open in a new tab.
* any other page (with pictures)             -> page tools + an "images on this page" gallery.
The button's icon follows the context (music note / video / photo / tune) and shows a coloured dot while media plays."""
import json
from PyQt6.QtCore import Qt, QObject, QTimer, QUrl, QPoint, QSize
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QVBoxLayout,
                             QGridLayout, QWidget)

import sps_icons

PROBE_JS = r"""(function(){try{
var ms=[].slice.call(document.querySelectorAll('video,audio'));
var m=ms.filter(function(x){return !x.paused&&!x.ended})[0]||ms.filter(function(x){return x.readyState>0&&x.duration>0})[0];
var ct=document.contentType||'';
var r={url:location.href,title:document.title,isImg:ct.indexOf('image/')==0,imgs:document.images.length};
if(m){var md=null;try{md=navigator.mediaSession&&navigator.mediaSession.metadata}catch(e){}
r.media={kind:m.tagName.toLowerCase(),paused:m.paused,muted:m.muted,vol:m.volume,rate:m.playbackRate,loop:m.loop,t:m.currentTime,
d:isFinite(m.duration)?m.duration:0,pip:!!document.pictureInPictureElement,
title:(md&&md.title)||'',artist:(md&&md.artist)||'',yt:/(^|\.)youtube\.com$/.test(location.hostname)};}
return JSON.stringify(r);}catch(e){return '{}'}})()"""

_PICK = ("var ms=[].slice.call(document.querySelectorAll('video,audio'));"
         "var m=ms.filter(function(x){return !x.paused&&!x.ended})[0]||ms.filter(function(x){return x.readyState>0&&x.duration>0})[0];if(!m)return;")


def media_js(action, val=None):
    v = json.dumps(val)
    body = {
        "toggle": "if(m.paused)m.play();else m.pause();",
        "seekrel": "m.currentTime=Math.max(0,Math.min(m.duration||1e9,m.currentTime+%s));" % v,
        "seekfrac": "if(m.duration)m.currentTime=m.duration*%s;" % v,
        "rate": "m.playbackRate=%s;" % v,
        "vol": "m.volume=%s;m.muted=false;" % v,
        "mute": "m.muted=!m.muted;",
        "loop": "m.loop=!m.loop;",
        "pip": "if(document.pictureInPictureElement)document.exitPictureInPicture();else if(m.requestPictureInPicture)m.requestPictureInPicture();",
        "fs": "if(document.fullscreenElement)document.exitFullscreen();else{var e=m.closest('#movie_player,.html5-video-player')||m;(e.requestFullscreen||m.webkitEnterFullscreen||function(){}).call(e);}",
        "next": "var b=document.querySelector('.ytp-next-button,.next-button,[aria-label=\"Next\"],[data-testid=\"control-button-skip-forward\"]');if(b)b.click();else m.currentTime=m.duration||m.currentTime;",
        "prev": "var b=document.querySelector('.ytp-prev-button,.previous-button,[aria-label=\"Previous\"],[data-testid=\"control-button-skip-back\"]');if(b&&b.offsetParent!==null&&!b.disabled)b.click();else m.currentTime=0;",
    }[action]
    return "(function(){" + _PICK + body + "})()"


def image_js(action, val=None):
    v = json.dumps(val)
    pre = ("var i=document.images[0];if(!i)return;var S=window.__sps=window.__sps||{rot:0,fx:1,b:100,c:100,s:100,g:0};"
           "function ap(){i.style.transition='transform .25s ease,filter .2s';i.style.transform='rotate('+S.rot+'deg) scaleX('+S.fx+')';"
           "i.style.filter='brightness('+S.b+'%) contrast('+S.c+'%) saturate('+S.s+'%) grayscale('+S.g+'%)';}")
    body = {
        "rot": "S.rot=(S.rot+90)%360;ap();",
        "rotl": "S.rot=(S.rot+270)%360;ap();",
        "flip": "S.fx=-S.fx;ap();",
        "b": "S.b=%s;ap();" % v, "c": "S.c=%s;ap();" % v, "s": "S.s=%s;ap();" % v,
        "gray": "S.g=S.g?0:100;ap();",
        "reset": "S.rot=0;S.fx=1;S.b=100;S.c=100;S.s=100;S.g=0;ap();",
        "save": "var a=document.createElement('a');a.href=i.src;a.download='';document.body.appendChild(a);a.click();a.remove();",
    }[action]
    return "(function(){" + pre + body + "})()"


GALLERY_JS = r"""(function(){var o=document.getElementById('__sps_gal');if(o){o.remove();return;}
var seen={},L=[].slice.call(document.images).filter(function(i){return i.naturalWidth>=80&&i.naturalHeight>=80&&!seen[i.currentSrc||i.src]&&(seen[i.currentSrc||i.src]=1)});
o=document.createElement('div');o.id='__sps_gal';o.style.cssText='position:fixed;inset:0;z-index:2147483647;background:rgba(15,15,20,.92);overflow:auto;padding:24px;font:14px system-ui;color:#fff;animation:spsg .22s ease';
var st=document.createElement('style');st.textContent='@keyframes spsg{from{opacity:0;transform:scale(.98)}to{opacity:1;transform:none}}#__sps_gal img{transition:transform .15s}#__sps_gal img:hover{transform:scale(1.03)}';o.appendChild(st);
var h=document.createElement('div');h.style.cssText='display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;font-size:18px;font-weight:600';h.textContent='Images on this page ('+L.length+')';
var x=document.createElement('button');x.textContent='Close';x.style.cssText='border:0;border-radius:18px;padding:8px 18px;font-weight:600;cursor:pointer';x.onclick=function(){o.remove()};h.appendChild(x);o.appendChild(h);
var g=document.createElement('div');g.style.cssText='display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px';
L.forEach(function(i){var im=document.createElement('img');im.src=i.currentSrc||i.src;im.style.cssText='width:100%;height:150px;object-fit:cover;border-radius:12px;cursor:pointer;background:#222';im.onclick=function(){window.open(im.src,'_blank')};g.appendChild(im)});
o.appendChild(g);o.addEventListener('keydown',function(e){if(e.key=='Escape')o.remove()});document.documentElement.appendChild(o);})()"""


def fmt_time(s):
    s = int(max(0, s or 0)); h, r = divmod(s, 3600); m, sec = divmod(r, 60)
    return ("%d:%02d:%02d" % (h, m, sec)) if h else ("%d:%02d" % (m, sec))


def classify(info):
    """info = dict from PROBE_JS -> 'media' | 'image' | 'page'"""
    if info.get("media"):
        return "media"
    if info.get("isImg"):
        return "image"
    return "page"


def _theme(mw):
    t = dict(getattr(mw, "_theme", {}) or {})
    t.setdefault("bg_primary", "#ffffff"); t.setdefault("text_primary", "#202124"); t.setdefault("text_secondary", "#5f6368")
    t.setdefault("bg_secondary", "#f1f3f4"); t.setdefault("hover", "#e8eaed"); t.setdefault("border", "#dadce0")
    t["acc"] = mw.settings_data.get("accent_color") or t.get("accent", "#1a73e8")
    return t


def give_gesture(view, then=None):
    """Fullscreen and picture-in-picture only work after a REAL user input in the page. A click on our own panel is not one, so the
    page gets focus and a harmless key press (F13, which no site uses); `then` runs ~250 ms later, while the page's "user
    activation" is still valid (verified: navigator.userActivation.isActive becomes true)."""
    try:
        if not view.hasFocus():
            view.setFocus()
    except Exception:
        pass

    def send():
        try:
            from PyQt6.QtCore import QEvent
            from PyQt6.QtGui import QKeyEvent
            tgt = view.focusProxy() or view
            for et in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                QApplication.sendEvent(tgt, QKeyEvent(et, Qt.Key.Key_F13, Qt.KeyboardModifier.NoModifier))
        except Exception:
            pass
    QTimer.singleShot(150, send)
    if then is not None:
        QTimer.singleShot(380, then)


class Controller(QObject):
    """Polls the page that matters (a tab that is making sound, otherwise the current tab) and keeps the toolbar button in sync."""
    def __init__(self, mw, btn):
        super().__init__(btn)
        self.mw, self.btn = mw, btn
        self.info, self.kind, self.tab = {}, "page", None
        self._busy = False
        self.timer = QTimer(self); self.timer.setInterval(1500); self.timer.timeout.connect(self.probe)
        self.timer.start()
        QTimer.singleShot(600, self.probe)

    def _tabs(self):
        n = self.mw.tabs.count()
        return [self.mw.tabs.widget(i) for i in range(n)]

    def target(self):
        cur = self.mw.tabs.currentWidget()
        try:
            if cur is not None and cur.page().recentlyAudible():
                return cur
            for w in self._tabs():
                try:
                    if w is not cur and w.page().recentlyAudible():
                        return w
                except Exception:
                    pass
        except Exception:
            pass
        return cur

    def probe(self, cb=None):
        w = self.target()
        if w is None or self._busy:
            if cb: cb()
            return
        try:
            url = w.url().toString()
            if not url.startswith(("http", "file", "data", "blob")):
                self._apply(w, {}); cb and cb(); return
            self._busy = True
            def got(res, _w=w):
                self._busy = False
                try:
                    info = json.loads(res) if isinstance(res, str) else {}
                except Exception:
                    info = {}
                self._apply(_w, info); cb and cb()
            w.page().runJavaScript(PROBE_JS, got)
        except Exception:
            self._busy = False

    def _apply(self, w, info):
        self.tab, self.info, self.kind = w, info or {}, classify(info or {})
        self.refresh_button()

    def refresh_button(self):
        col = _theme(self.mw)["text_primary"]
        name = {"media": "music" if (self.info.get("media") or {}).get("kind") == "audio" else "video", "image": "image"}.get(self.kind, "tune")
        playing = self.kind == "media" and not self.info["media"].get("paused")
        key = (name, playing, col)
        if getattr(self, "_key", None) == key:
            return
        self._key = key
        self.btn.setIcon(sps_icons.icon(name, _theme(self.mw)["acc"] if playing else col, 21))
        self.btn.setProperty("playing", playing)
        self.btn.setToolTip({"media": "Easy access - media controls", "image": "Easy access - photo tools"}.get(self.kind, "Easy access - page tools"))
        self.btn.update()

    def run(self, js, tab=None, gesture=False):
        w = tab or self.tab or self.mw.tabs.currentWidget()
        if w is not None:
            try:
                if gesture:
                    give_gesture(w, lambda: w.page().runJavaScript(js))
                else:
                    w.page().runJavaScript(js)
            except Exception:
                pass


class EasyPanel(QFrame):
    def __init__(self, mw, ctl):
        super().__init__(mw, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.mw, self.ctl = mw, ctl
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        t = _theme(mw); self.t = t
        outer = QVBoxLayout(self); outer.setContentsMargins(14, 14, 14, 18)
        self.box = QFrame(); self.box.setObjectName("ep"); outer.addWidget(self.box)
        sh = QGraphicsDropShadowEffect(self); sh.setBlurRadius(28); sh.setOffset(0, 6); sh.setColor(QColor(0, 0, 0, 90)); self.box.setGraphicsEffect(sh)
        self.setStyleSheet(
            "#ep{background:%(bg_primary)s;border:1px solid %(border)s;border-radius:18px;}"
            "QLabel{color:%(text_primary)s;background:transparent;} QLabel#h{font-size:16px;font-weight:700;} QLabel#s{color:%(text_secondary)s;font-size:12px;font-weight:600;}"
            "QPushButton{background:%(bg_secondary)s;color:%(text_primary)s;border:none;border-radius:10px;padding:6px 8px;font-weight:600;font-size:13px;}"
            "QPushButton:hover{background:%(hover)s;} QPushButton[on='true']{background:%(acc)s;color:white;}"
            "QPushButton#round{border-radius:22px;padding:0;} QPushButton#big{background:%(acc)s;border-radius:28px;padding:0;}"
            "QPushButton#big:hover{background:%(acc)s;}"
            "QSlider::groove:horizontal{height:5px;background:%(hover)s;border-radius:2px;} QSlider::sub-page:horizontal{background:%(acc)s;border-radius:2px;}"
            "QSlider::handle:horizontal{background:%(acc)s;width:14px;height:14px;margin:-5px 0;border-radius:7px;}" % t)
        from PyQt6.QtWidgets import QScrollArea
        bl = QVBoxLayout(self.box); bl.setContentsMargins(0, 6, 0, 6)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}QScrollBar:vertical{width:8px;background:transparent;margin:2px;}"
                                  "QScrollBar::handle:vertical{background:rgba(128,128,128,110);border-radius:4px;min-height:30px;}"
                                  "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        # NOTE: a bare "background:transparent;" here (no selector) is inherited by EVERY child button and wiped their colours -
        # that is why play/pause and the active speed button were invisible. Style only the body itself.
        self.body = QWidget(); self.body.setObjectName("epbody"); self.body.setStyleSheet("QWidget#epbody{background:transparent;}")
        self.scroll.setWidget(self.body); bl.addWidget(self.scroll)
        self.lay = QVBoxLayout(self.body); self.lay.setContentsMargins(14, 6, 14, 6); self.lay.setSpacing(8)
        self.setFixedWidth(440)
        self._built = None
        self.rebuild()
        self.tick = QTimer(self); self.tick.setInterval(1000); self.tick.timeout.connect(lambda: ctl.probe(self._sync)); self.tick.start()

    # ---- helpers ----
    def _clear(self):
        while self.lay.count():
            it = self.lay.takeAt(0); w = it.widget()
            if w is not None:
                w.setParent(None); w.deleteLater()
            elif it.layout() is not None:
                self._drop(it.layout())

    def _drop(self, lay):
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None); w.deleteLater()
            elif it.layout() is not None:
                self._drop(it.layout())

    def _btn(self, icon, tip, fn, name=None, color=None, size=22, w=44, h=44, text=None):
        b = QPushButton(text or ""); b.setToolTip(tip); b.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            b.setIcon(sps_icons.icon(icon, color or self.t["text_primary"], size)); b.setIconSize(QSize(size, size))
        if name: b.setObjectName(name)
        if w and h and not text: b.setFixedSize(w, h)
        b.clicked.connect(lambda *_: fn()); return b

    def _head(self, icon, title, sub):
        row = QHBoxLayout(); ic = QLabel(); ic.setPixmap(sps_icons.pixmap(icon, self.t["acc"], 24)); ic.setFixedWidth(30)
        col = QVBoxLayout(); col.setSpacing(0)
        a = QLabel(title[:46] or "SPS Browser"); a.setObjectName("h"); b = QLabel(sub[:56]); b.setObjectName("s")
        for lab in (a, b):                                    # a long title is cut short, it never widens the panel
            lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred); lab.setMinimumWidth(0)
        a.setToolTip(title)
        col.addWidget(a); col.addWidget(b); row.addWidget(ic); row.addLayout(col, 1)
        x = self._btn("close", "Close", self.close, size=16, w=30, h=30); row.addWidget(x); self.lay.addLayout(row)
        return a, b

    def _grid(self, items, cols=3):
        g = QGridLayout(); g.setSpacing(5)
        for i, (ic, label, fn) in enumerate(items):
            b = QPushButton("  " + label); b.setIcon(sps_icons.icon(ic, self.t["text_primary"], 18)); b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(lambda *_, f=fn: (f(), None)); g.addWidget(b, i // cols, i % cols)
        self.lay.addLayout(g)

    # ---- builders ----
    def rebuild(self):
        self._clear()
        kind, info = self.ctl.kind, self.ctl.info
        self._built = kind
        {"media": self._media, "image": self._image}.get(kind, self._page)(info)
        self.fit()

    def fit(self):
        """Height = content, but never taller than the screen; the top edge never moves (the content scrolls instead)."""
        try:
            scr = QApplication.primaryScreen().availableGeometry()
            want = self.body.sizeHint().height() + 12 + 44
            h = max(160, min(want, scr.height() - 90))
            top = self.y() if self.isVisible() else None
            self.setFixedHeight(h)
            if top is not None:
                self.move(self.x(), min(top, scr.bottom() - h - 8))
        except Exception:
            pass

    def _sync(self):
        if self.ctl.kind != self._built:
            self.rebuild(); return
        if self._built == "media":
            m = self.ctl.info.get("media") or {}
            if hasattr(self, "play") and not getattr(self, "_dragging", False):
                self.play.setIcon(sps_icons.icon("play" if m.get("paused") else "pause", "#ffffff", 30))
                d = m.get("d") or 0
                self.seek.blockSignals(True); self.seek.setValue(int(1000 * (m.get("t", 0) / d)) if d else 0); self.seek.blockSignals(False)
                self.tl.setText("%s / %s" % (fmt_time(m.get("t")), fmt_time(d)))
                self.mute_b.setIcon(sps_icons.icon("mute" if m.get("muted") else "volume", self.t["text_primary"], 20))
                self.loop_b.setProperty("on", bool(m.get("loop"))); self.loop_b.style().unpolish(self.loop_b); self.loop_b.style().polish(self.loop_b)

    def _media(self, info):
        m = info.get("media") or {}
        title = m.get("title") or info.get("title") or "Playing"
        host = QUrl(info.get("url", "")).host()
        self._head("music" if m.get("kind") == "audio" else "video", title, (m.get("artist") + " · " if m.get("artist") else "") + host)
        self.seek = QSlider(Qt.Orientation.Horizontal); self.seek.setRange(0, 1000)
        self.seek.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        def rel():
            self._dragging = False; self.ctl.run(media_js("seekfrac", self.seek.value() / 1000.0))
        self.seek.sliderReleased.connect(rel); self.lay.addWidget(self.seek)
        self.tl = QLabel("0:00 / 0:00"); self.tl.setObjectName("s"); self.lay.addWidget(self.tl)
        r = QHBoxLayout(); r.addStretch()
        r.addWidget(self._btn("prev", "Previous", lambda: self.ctl.run(media_js("prev")), "round"))
        r.addWidget(self._btn("back10", "Back 10 seconds", lambda: self.ctl.run(media_js("seekrel", -10)), "round"))
        self.play = self._btn("play", "Play / pause", lambda: (self.ctl.run(media_js("toggle")), QTimer.singleShot(250, self.ctl.probe)), "big", "#ffffff", 26, 56, 56)
        r.addWidget(self.play)
        r.addWidget(self._btn("fwd10", "Forward 10 seconds", lambda: self.ctl.run(media_js("seekrel", 10)), "round"))
        r.addWidget(self._btn("next", "Next", lambda: self.ctl.run(media_js("next")), "round")); r.addStretch(); self.lay.addLayout(r)
        v = QHBoxLayout(); self.mute_b = self._btn("volume", "Mute / unmute", lambda: self.ctl.run(media_js("mute")), size=18, w=32, h=32); v.addWidget(self.mute_b)
        vs = QSlider(Qt.Orientation.Horizontal); vs.setRange(0, 100); vs.setValue(int(100 * (m.get("vol", 1) or 0)))
        vs.valueChanged.connect(lambda x: self.ctl.run(media_js("vol", x / 100.0))); v.addWidget(vs); self.lay.addLayout(v)
        s = QLabel("SPEED"); s.setObjectName("s"); self.lay.addWidget(s)
        sp = QHBoxLayout(); sp.setSpacing(4)
        for rate in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
            b = QPushButton(("%g×" % rate)); b.setMinimumHeight(32); b.setMaximumHeight(34); b.setMinimumWidth(0); b.setStyleSheet("padding:4px 2px;"); b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed); b.setProperty("on", abs((m.get("rate") or 1) - rate) < 0.01); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda *_, r_=rate, b_=b: self._set_rate(r_, b_)); sp.addWidget(b)
        self.lay.addLayout(sp)
        self.speed_btns = []
        for i in range(sp.count()):
            self.speed_btns.append(sp.itemAt(i).widget())
        self.loop_b = QPushButton("  Loop"); self.loop_b.setIcon(sps_icons.icon("repeat", self.t["text_primary"], 18)); self.loop_b.setProperty("on", bool(m.get("loop")))
        self.loop_b.clicked.connect(lambda *_: self._toggle_loop())
        pip = QPushButton("  PiP"); pip.setIcon(sps_icons.icon("pip", self.t["text_primary"], 18)); pip.clicked.connect(lambda *_: (self.close(), self.ctl.run(media_js("pip"), gesture=True)))
        fs = QPushButton(" Full screen"); fs.setIcon(sps_icons.icon("fullscreen", self.t["text_primary"], 18)); fs.clicked.connect(lambda *_: (self.close(), self.ctl.run(media_js("fs"), gesture=True)))
        g = QHBoxLayout(); g.setSpacing(4)
        for x in (self.loop_b, pip, fs):
            x.setMinimumWidth(0); x.setMinimumHeight(32); x.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed); x.setIconSize(QSize(16, 16)); g.addWidget(x)
        self.lay.addLayout(g)
        cur = self.mw.tabs.currentWidget()
        if self.ctl.tab is not None and self.ctl.tab is not cur:
            go = QPushButton("  Go to this tab"); go.setIcon(sps_icons.icon("open", self.t["text_primary"], 18))
            go.clicked.connect(lambda *_: (self.close(), self.mw.tabs.setCurrentWidget(self.ctl.tab))); self.lay.addWidget(go)
        self._sync()

    def _set_rate(self, rate, btn):
        self.ctl.run(media_js("rate", rate))
        for x in getattr(self, "speed_btns", []):
            x.setProperty("on", x is btn); x.style().unpolish(x); x.style().polish(x)

    def _toggle_loop(self):
        self.ctl.run(media_js("loop"))
        on = not bool(self.loop_b.property("on")); self.loop_b.setProperty("on", on)
        self.loop_b.style().unpolish(self.loop_b); self.loop_b.style().polish(self.loop_b)

    def rebuild_soon(self):
        self.ctl.probe(lambda: self.rebuild() if self.isVisible() else None)

    def _image(self, info):
        self._head("image", info.get("title") or "Photo", "Photo tools · " + QUrl(info.get("url", "")).host())
        run = self.ctl.run; mw = self.mw
        self._grid([("zoom_in", "Zoom in", lambda: mw.zoom_in()), ("zoom_out", "Zoom out", lambda: mw.zoom_out()),
                    ("reload", "Reset", lambda: run(image_js("reset"))),
                    ("rotate", "Rotate", lambda: run(image_js("rot"))), ("flip", "Flip", lambda: run(image_js("flip"))),
                    ("brightness", "Grayscale", lambda: run(image_js("gray")))])
        for lab, key in (("BRIGHTNESS", "b"), ("CONTRAST", "c"), ("COLOUR", "s")):
            l = QLabel(lab); l.setObjectName("s"); self.lay.addWidget(l)
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(20, 200); sl.setValue(100)
            sl.valueChanged.connect(lambda x, k=key: run(image_js(k, x))); self.lay.addWidget(sl)
        url = info.get("url", "")
        self._grid([("download", "Save", lambda: (run(image_js("save")), self.close())), ("copy", "Copy link", lambda: QGuiApplication.clipboard().setText(url)),
                    ("search", "Google Lens", lambda: (self.close(), mw.add_new_tab(QUrl("https://lens.google.com/uploadbyurl?url=" + QUrl.toPercentEncoding(url).data().decode())))),
                    ("print", "Print", lambda: (self.close(), mw.print_page())), ("open", "New tab", lambda: (self.close(), mw.add_new_tab(QUrl(url)))),
                    ("star", "Bookmark", lambda: mw.add_bookmark_current())])

    def _page(self, info):
        self._head("tune", info.get("title") or "Page tools", QUrl(info.get("url", "")).host() or "Easy access")
        mw = self.mw; c = lambda name: (lambda: (self.close(), getattr(mw, name)()) if hasattr(mw, name) else None)
        items = [("star", "Bookmark", c("add_bookmark_current")), ("print", "Print", c("print_page")), ("camera", "Screenshot", c("take_screenshot")),
                 ("reader", "Reader", c("toggle_reader_mode")), ("translate", "Translate", c("translate_page")), ("zoom_in", "Zoom in", lambda: mw.zoom_in()),
                 ("zoom_out", "Zoom out", lambda: mw.zoom_out()), ("code", "Source", c("view_source")), ("qr", "Page QR", c("show_send_tab")),
                 ("copy", "Copy link", lambda: QGuiApplication.clipboard().setText(info.get("url", ""))),
                 ("download", "Save page", c("save_page")), ("bolt", "Quick panel", c("show_quick_panel"))]
        self._grid(items)
        n = info.get("imgs", 0)
        if n:
            s = QLabel("PICTURES"); s.setObjectName("s"); self.lay.addWidget(s)
            b = QPushButton("  View all %d images on this page" % n); b.setIcon(sps_icons.icon("grid", self.t["text_primary"], 18))
            b.clicked.connect(lambda *_: (self.close(), self.ctl.run(GALLERY_JS))); self.lay.addWidget(b)

    def popup_at(self, anchor):
        self.fit()
        pos = anchor.mapToGlobal(QPoint(anchor.width() - self.width() + 14, anchor.height() + 2))
        scr = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if scr is not None:
            pos.setX(max(scr.left() + 4, min(pos.x(), scr.right() - self.width() - 4)))
        self.move(pos); self.show()


def install(mw):
    """Adds the easy-access button just left of the quick-panel/menu buttons."""
    if getattr(mw, "_easy_btn", None) is not None:
        return
    btn = QPushButton(); btn.setFixedSize(36, 36); btn.setToolTip("Easy access")
    btn.setStyleSheet("QPushButton{background:transparent;border:none;border-radius:18px;}QPushButton:hover{background:rgba(128,128,128,60);}")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setIcon(sps_icons.icon("tune", _theme(mw)["text_primary"], 21)); btn.setIconSize(QSize(21, 21))
    ref = getattr(mw, "_quick_btn", None) or mw.menu_btn
    before = next((a for a in mw.toolbar.actions() if mw.toolbar.widgetForAction(a) is ref), None)
    mw._easy_action = mw.toolbar.insertWidget(before, btn) if before is not None else mw.toolbar.addWidget(btn)
    mw._easy_btn = btn
    ctl = Controller(mw, btn); mw._easy_ctl = ctl
    def open_panel():
        old = getattr(mw, "_easy_panel", None)
        if old is not None:
            try: old.close()
            except Exception: pass
        def go():
            p = EasyPanel(mw, ctl); mw._easy_panel = p; p.popup_at(btn)
        ctl.probe(go)
    btn.clicked.connect(lambda *_: open_panel())
    try:
        from PyQt6.QtGui import QShortcut, QKeySequence
        mw._easy_sc = QShortcut(QKeySequence("Ctrl+Shift+E"), mw, activated=open_panel)
    except Exception:
        pass
