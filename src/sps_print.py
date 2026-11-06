"""SPS Browser print window (Chrome-style): live preview, destination, pages, copies, layout, colour, paper size, margins, scale,
headers/footers, background graphics, two-sided - and "Selected area": drag a box on the page and print only that part."""
import json, os, tempfile, datetime

from PyQt6.QtCore import QObject, Qt, QTimer, QRect, QPoint, QMarginsF, QSizeF, QUrl, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QPageLayout, QPageSize, QPdfWriter, QPixmap, QCursor
from PyQt6.QtWidgets import (QDialog, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QComboBox, QSpinBox, QCheckBox, QLabel,
                             QPushButton, QLineEdit, QFileDialog, QMessageBox, QGroupBox, QApplication, QScrollArea)
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
    HAVE_PDF_VIEW = True
except Exception:                                                  # preview is a nice-to-have; printing still works
    HAVE_PDF_VIEW = False
try:
    from PyQt6.QtGui import QPageRanges
except Exception:
    try:
        from PyQt6.QtPrintSupport import QPageRanges
    except Exception:
        QPageRanges = None
try:
    from PyQt6.QtWebEngineCore import QWebEngineSettings
except Exception:
    QWebEngineSettings = None

PAPERS = [("A4", QPageSize.PageSizeId.A4), ("A3", QPageSize.PageSizeId.A3), ("A5", QPageSize.PageSizeId.A5),
          ("Letter", QPageSize.PageSizeId.Letter), ("Legal", QPageSize.PageSizeId.Legal), ("Tabloid", QPageSize.PageSizeId.Tabloid)]
PREFS_FILE = None
STYLE_ID = "sps-print-style"


def prefs_path():
    global PREFS_FILE
    if PREFS_FILE:
        return PREFS_FILE
    base = os.environ.get("SPS_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".sps_browser")
    PREFS_FILE = os.path.join(base, "print_prefs.json")
    return PREFS_FILE


def load_prefs():
    try:
        with open(prefs_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_prefs(d):
    try:
        os.makedirs(os.path.dirname(prefs_path()), exist_ok=True)
        with open(prefs_path(), "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception:
        pass


def parse_ranges(text, max_pages=100000):
    """'1-3, 5, 8-' -> [(1,3),(5,5),(8,max)]; None when the text is not valid."""
    out = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                lo = int(a) if a else 1
                hi = int(b) if b else max_pages
            else:
                lo = hi = int(part)
        except ValueError:
            return None
        if lo < 1 or hi < lo:
            return None
        out.append((lo, hi))
    return out or None


def build_layout(paper_index, landscape, margin_mode, custom_mm):
    size = QPageSize(PAPERS[paper_index][1])
    orient = QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait
    mm = {"default": (10, 10, 10, 10), "none": (0, 0, 0, 0), "minimum": (4, 4, 4, 4)}.get(margin_mode, custom_mm)
    l, t, r, b = mm[3], mm[0], mm[1], mm[2]
    return QPageLayout(size, orient, QMarginsF(l, t, r, b), QPageLayout.Unit.Millimeter)


def print_css(scale_percent, header_footer, title, url):
    """Injected only for printing (@media print): the screen is never changed."""
    css = "@media print { html { zoom: %s; } }" % (max(10, min(400, int(scale_percent))) / 100.0)
    if header_footer:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        css += (" @page { @top-left { content: %s; font-size: 9pt; color: #555; }"
                " @top-right { content: %s; font-size: 9pt; color: #555; }"
                " @bottom-left { content: %s; font-size: 9pt; color: #555; }"
                " @bottom-right { content: counter(page) ' / ' counter(pages); font-size: 9pt; color: #555; } }") % (
                    json.dumps(title or ""), json.dumps(now), json.dumps(url or ""))
    return css


AREA_JS = r"""(function(){
 if(window.__spsAreaEl){window.__spsAreaEl.remove();}
 window.__spsArea=null;
 var o=document.createElement('div'); window.__spsAreaEl=o; o.id='__sps_area';
 o.style.cssText='position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:2147483647;cursor:crosshair;background:rgba(0,0,0,.30);user-select:none;touch-action:none;font:600 14px system-ui;color:#fff;';
 var hint=document.createElement('div'); hint.textContent='Drag a box around the part you want to print  (Esc = cancel)';
 hint.style.cssText='position:absolute;top:14px;left:0;right:0;text-align:center;text-shadow:0 1px 3px #000;pointer-events:none';
 var box=document.createElement('div'); box.style.cssText='position:absolute;display:none;border:2px solid #1a73e8;box-shadow:0 0 0 100000px rgba(0,0,0,.45);background:transparent;pointer-events:none';
 var lab=document.createElement('div'); lab.style.cssText='position:absolute;left:0;top:-22px;background:#1a73e8;color:#fff;font-size:12px;padding:2px 6px;border-radius:6px;white-space:nowrap';
 box.appendChild(lab); o.appendChild(hint); o.appendChild(box);
 var sx=0,sy=0,drag=false,r=null;
 function rect(x,y){return {x:Math.min(sx,x),y:Math.min(sy,y),w:Math.abs(x-sx),h:Math.abs(y-sy)};}
 function end(v){o.remove();window.__spsAreaEl=null;document.removeEventListener('keydown',key,true);window.__spsArea=v;}
 function key(e){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();end('cancel');}}
 o.addEventListener('mousedown',function(e){e.preventDefault();drag=true;sx=e.clientX;sy=e.clientY;hint.style.display='none';o.style.background='transparent';box.style.display='block';});
 o.addEventListener('mousemove',function(e){if(!drag)return;r=rect(e.clientX,e.clientY);box.style.left=r.x+'px';box.style.top=r.y+'px';box.style.width=r.w+'px';box.style.height=r.h+'px';lab.textContent=Math.round(r.w)+' x '+Math.round(r.h);});
 o.addEventListener('mouseup',function(e){if(!drag)return;drag=false;r=rect(e.clientX,e.clientY);
   if(r.w<8||r.h<8){box.style.display='none';hint.style.display='block';o.style.background='rgba(0,0,0,.30)';return;}
   end(r);});
 document.addEventListener('keydown',key,true);
 document.documentElement.appendChild(o);
})()"""


class AreaSelector(QObject):
    """Area selection drawn INSIDE the page (a DOM overlay) instead of a widget on top of the web view.
    A translucent widget over QWebEngineView froze some Windows machines (GPU compositor); the DOM overlay cannot.
    Drag a box; release = done (signal `chosen` with a QRect in view pixels); Esc = cancel."""
    chosen = pyqtSignal(QRect)
    cancelled = pyqtSignal()

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self._done = False
        self._ticks = 0
        self.timer = QTimer(self); self.timer.setInterval(120); self.timer.timeout.connect(self._poll)
        try:
            view.page().runJavaScript(AREA_JS)
        except Exception:
            QTimer.singleShot(0, self._cancel); return
        self.timer.start()

    def _finish(self):
        self._done = True; self.timer.stop()

    def _cancel(self):
        if not self._done:
            self._finish(); self.cancelled.emit()

    def _poll(self):
        self._ticks += 1
        if self._ticks > 1000:                        # ~2 minutes without an answer
            self.cancel_selection(); return
        try:
            self.view.page().runJavaScript("window.__spsArea===undefined?'none':JSON.stringify(window.__spsArea)", self._got)
        except Exception:
            self._cancel()

    def _got(self, res):
        if self._done or res in (None, "none", "null"):
            return
        if res == '"cancel"':
            self._cancel(); return
        try:
            import json
            d = json.loads(res)
            z = 1.0
            try: z = float(self.view.zoomFactor())
            except Exception: pass
            r = QRect(int(d["x"] * z), int(d["y"] * z), max(1, int(d["w"] * z)), max(1, int(d["h"] * z)))
        except Exception:
            self._cancel(); return
        self._finish(); self.chosen.emit(r)

    def cancel_selection(self):
        try:
            self.view.page().runJavaScript("(function(){var o=window.__spsAreaEl;if(o)o.remove();window.__spsAreaEl=null;window.__spsArea='cancel'})()")
        except Exception:
            pass
        self._cancel()

    def deleteLater(self):
        self._finish(); super().deleteLater()


class SpsPrintDialog(QDialog):
    def __init__(self, win, view, to_pdf=False, start_area=False):
        super().__init__(win)
        self.win, self.view = win, view
        self.page = view.page()
        self.setWindowTitle("Print")
        self.resize(1000, 680)
        self.prefs = load_prefs()
        self._tmp_pdf = None
        self._doc = None
        self._busy = False
        self._again = False
        self._pixmap = None                        # set when "Selected area" was used
        self._pages = 0
        self._selector = None

        root = QHBoxLayout(self)
        left = QVBoxLayout(); root.addLayout(left, 0)
        form = QFormLayout()

        self.dest = QComboBox(); self.dest.addItem("Save as PDF")
        self._printers = []
        try:
            default = QPrinterInfo.defaultPrinterName()
            for pi in QPrinterInfo.availablePrinters():
                self._printers.append(pi.printerName())
            self._printers.sort(key=lambda n: (n != default, n.lower()))
        except Exception:
            self._printers = []
        for n in self._printers:
            self.dest.addItem(n)
        if not to_pdf and self._printers:
            self.dest.setCurrentIndex(1)
        form.addRow("Destination", self.dest)

        self.area = QComboBox(); self.area.addItems(["Whole page", "Selected area (drag a box)"])
        form.addRow("Print", self.area)
        self.pick = QPushButton("Choose the area…"); self.pick.setEnabled(False)
        form.addRow("", self.pick)
        self.save_img = QPushButton("Save the area as a picture…"); self.save_img.setEnabled(False)
        self.copy_img = QPushButton("Copy the area"); self.copy_img.setEnabled(False)
        irow = QWidget(); il = QHBoxLayout(irow); il.setContentsMargins(0, 0, 0, 0); il.addWidget(self.save_img); il.addWidget(self.copy_img)
        form.addRow("", irow)

        self.pages_mode = QComboBox(); self.pages_mode.addItems(["All", "Custom"])
        self.pages_text = QLineEdit(); self.pages_text.setPlaceholderText("e.g. 1-3, 5"); self.pages_text.setEnabled(False)
        form.addRow("Pages", self.pages_mode); form.addRow("", self.pages_text)

        self.copies = QSpinBox(); self.copies.setRange(1, 99); self.copies.setValue(1)
        form.addRow("Copies", self.copies)

        self.orient = QComboBox(); self.orient.addItems(["Portrait", "Landscape"])
        self.orient.setCurrentIndex(int(self.prefs.get("landscape", 0)))
        form.addRow("Layout", self.orient)

        self.color = QComboBox(); self.color.addItems(["Color", "Black and white"])
        form.addRow("Color", self.color)

        self.paper = QComboBox(); self.paper.addItems([n for n, _ in PAPERS])
        self.paper.setCurrentIndex(min(len(PAPERS) - 1, int(self.prefs.get("paper", 0))))
        form.addRow("Paper size", self.paper)

        self.margins = QComboBox(); self.margins.addItems(["Default", "None", "Minimum", "Custom"])
        self.margins.setCurrentIndex(min(3, int(self.prefs.get("margins", 0))))
        form.addRow("Margins", self.margins)
        mrow = QWidget(); ml = QHBoxLayout(mrow); ml.setContentsMargins(0, 0, 0, 0)
        self.mm = []
        for lab in ("T", "R", "B", "L"):
            sp = QSpinBox(); sp.setRange(0, 60); sp.setValue(10); sp.setSuffix(" mm"); sp.setToolTip(
                {"T": "Top", "R": "Right", "B": "Bottom", "L": "Left"}[lab])
            ml.addWidget(QLabel(lab)); ml.addWidget(sp); self.mm.append(sp)
        self.mrow = mrow; mrow.setVisible(False); form.addRow("", mrow)

        self.scale = QSpinBox(); self.scale.setRange(25, 200); self.scale.setValue(int(self.prefs.get("scale", 100))); self.scale.setSuffix(" %")
        form.addRow("Scale", self.scale)

        self.duplex = QCheckBox("Two-sided (printer)"); form.addRow("", self.duplex)
        self.hf = QCheckBox("Headers and footers"); self.hf.setChecked(bool(self.prefs.get("hf", True))); form.addRow("", self.hf)
        self.bg = QCheckBox("Background graphics"); self.bg.setChecked(bool(self.prefs.get("bg", False))); form.addRow("", self.bg)
        left.addLayout(form)
        self.note = QLabel(""); self.note.setWordWrap(True); self.note.setStyleSheet("color:#888")
        left.addWidget(self.note); left.addStretch(1)

        brow = QHBoxLayout()
        self.go = QPushButton("Save" if to_pdf or not self._printers else "Print"); self.go.setDefault(True)
        cancel = QPushButton("Cancel")
        brow.addStretch(1); brow.addWidget(self.go); brow.addWidget(cancel)
        left.addLayout(brow)

        right = QVBoxLayout(); root.addLayout(right, 1)
        if HAVE_PDF_VIEW:
            self.pdf_view = QPdfView(self)
            self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            right.addWidget(self.pdf_view, 1)
        else:
            self.pdf_view = None
            right.addWidget(QLabel("Preview is not available on this computer. You can still print or save."), 1)
        self.status = QLabel("Preparing the preview…"); right.addWidget(self.status)

        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(350); self.timer.timeout.connect(self._render)
        for w in (self.orient, self.paper, self.margins, self.pages_mode, self.area, self.color):
            w.currentIndexChanged.connect(self._changed)
        for w in (self.scale, *self.mm):
            w.valueChanged.connect(self._changed)
        for w in (self.hf, self.bg):
            w.toggled.connect(self._changed)
        self.pages_text.textChanged.connect(self._changed)
        self.dest.currentIndexChanged.connect(self._dest_changed)
        self.pick.clicked.connect(self._choose_area)
        self.save_img.clicked.connect(self._save_picture)
        self.copy_img.clicked.connect(self._copy_picture)
        self.go.clicked.connect(self._do)
        cancel.clicked.connect(self.reject)
        self._dest_changed()
        self._changed()
        if start_area:
            self.area.setCurrentIndex(1)
            QTimer.singleShot(250, self._choose_area)

    # ── settings plumbing ──
    def _dest_changed(self):
        pdf = self.dest.currentIndex() == 0
        for w in (self.copies, self.duplex, self.color):
            w.setEnabled(not pdf)
        self.go.setText("Save" if pdf else "Print")
        self._changed()

    def _changed(self, *a):
        self.mrow.setVisible(self.margins.currentIndex() == 3)
        self.pages_text.setEnabled(self.pages_mode.currentIndex() == 1 and self.area.currentIndex() == 0)
        self.pages_mode.setEnabled(self.area.currentIndex() == 0)
        self.pick.setEnabled(self.area.currentIndex() == 1)
        have = self._pixmap is not None and not self._pixmap.isNull()
        self.save_img.setEnabled(have); self.copy_img.setEnabled(have)
        if self.area.currentIndex() == 1:
            self.note.setText("Selected area prints the box you drag, exactly as you see it on screen (as a picture).")
        else:
            self.note.setText("")
        self.timer.start()

    def _margin_mode(self):
        return ["default", "none", "minimum", "custom"][self.margins.currentIndex()]

    def _layout(self):
        return build_layout(self.paper.currentIndex(), self.orient.currentIndex() == 1, self._margin_mode(),
                            tuple(sp.value() for sp in self.mm))

    def _ranges(self):
        if self.pages_mode.currentIndex() == 0 or self.area.currentIndex() == 1:
            return None
        return parse_ranges(self.pages_text.text())

    # ── preview generation ──
    def _inject_css(self):
        title = self.view.title() if hasattr(self.view, "title") else ""
        css = print_css(self.scale.value(), self.hf.isChecked(), title, self.view.url().toString())
        js = ("(function(){var s=document.getElementById('%s');if(!s){s=document.createElement('style');s.id='%s';"
              "(document.head||document.documentElement).appendChild(s);}s.textContent=%s;})()") % (STYLE_ID, STYLE_ID, json.dumps(css))
        self.page.runJavaScript(js)

    def _remove_css(self):
        try:
            self.page.runJavaScript("var s=document.getElementById('%s');if(s)s.remove();" % STYLE_ID)
        except Exception:
            pass

    def _render(self):
        if self._busy:
            self._again = True
            return
        self._busy = True
        self.status.setText("Updating the preview…")
        try:
            if self.area.currentIndex() == 1:
                self._render_area()
            else:
                self._render_page()
        except Exception as e:
            self._busy = False
            self.status.setText("Preview failed: %s" % e)

    def _new_tmp(self):
        if self._tmp_pdf and os.path.exists(self._tmp_pdf):
            try:
                os.remove(self._tmp_pdf)
            except OSError:
                pass
        fd, path = tempfile.mkstemp(prefix="sps_print_", suffix=".pdf")
        os.close(fd)
        self._tmp_pdf = path
        return path

    def _render_page(self):
        if self.pages_mode.currentIndex() == 1 and self._ranges() is None:
            self._busy = False
            self.status.setText("Pages: type something like 1-3, 5")
            return
        if QWebEngineSettings is not None:
            try:
                self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.PrintElementBackgrounds, self.bg.isChecked())
            except Exception:
                pass
        self._inject_css()
        QTimer.singleShot(120, self._do_print_to_pdf)         # let the style apply

    def _do_print_to_pdf(self):
        layout = self._layout()
        rng = self._ranges()
        try:
            if rng and QPageRanges is not None:
                pr = QPageRanges()
                for lo, hi in rng:
                    pr.addRange(lo, min(hi, 100000))
                self.page.printToPdf(self._on_pdf, layout, pr)
            else:
                self.page.printToPdf(self._on_pdf, layout)
        except Exception as e:
            self._busy = False
            self.status.setText("Preview failed: %s" % e)

    def _on_pdf(self, data):
        try:
            b = bytes(data)
            if not b:
                self.status.setText("The page could not be prepared for printing.")
            else:
                path = self._new_tmp()
                with open(path, "wb") as f:
                    f.write(b)
                self._show_pdf(path)
        finally:
            self._busy = False
            if self._again:
                self._again = False
                self.timer.start()

    def _render_area(self):
        if self._pixmap is None:
            self._busy = False
            self.status.setText("Press “Choose the area…” and drag a box on the page.")
            return
        path = self._new_tmp()
        w = QPdfWriter(path)
        w.setPageLayout(self._layout())
        p = QPainter(w)
        self._paint_pixmap(p, w.width(), w.height())
        p.end()
        del w
        self._busy = False
        self._show_pdf(path)

    def _paint_pixmap(self, painter, width, height):
        pm = self._pixmap
        if pm is None or pm.isNull():
            return
        s = min(width / pm.width(), height / pm.height())
        s = s * (self.scale.value() / 100.0) if self.scale.value() < 100 else s
        tw, th = int(pm.width() * s), int(pm.height() * s)
        painter.drawPixmap(QRect(0, 0, tw, th), pm)

    def _show_pdf(self, path):
        if self.pdf_view is not None:
            doc = QPdfDocument(self)
            doc.load(path)
            self.pdf_view.setDocument(doc)
            self._doc = doc
            self._pages = doc.pageCount()
        self.status.setText("%s page%s" % (self._pages or "?", "" if self._pages == 1 else "s"))

    # ── selected area ──
    # The window must NOT be modal while the box is dragged (a modal window blocks the page, and hiding a window that is
    # inside exec() ends it - that was the "nothing happens after choosing the area" bug). So it is shown with show(), never exec().
    def _choose_area(self):
        if self._selector is not None:
            return
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.hide()
        try:
            self.win.raise_(); self.win.activateWindow()
        except Exception:
            pass
        self._selector = AreaSelector(self.view)
        self._selector.chosen.connect(self._area_chosen)
        self._selector.cancelled.connect(self._area_cancelled)

    def _back(self):
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.show(); self.raise_(); self.activateWindow()

    def _area_cancelled(self):
        if self._selector is not None:
            self._selector.deleteLater(); self._selector = None
        self._back()

    def _area_chosen(self, rect):
        if self._selector is not None:
            self._selector.deleteLater(); self._selector = None
        QTimer.singleShot(60, lambda: self._grab_area(rect))        # let the overlay disappear from the page first

    def _grab_area(self, rect):
        pm = self.view.grab(rect)
        if pm.isNull():
            pm = self.win.grab().copy(QRect(self.view.mapTo(self.win, rect.topLeft()), rect.size()))
        self._pixmap = pm
        self._back()
        self._changed()

    def _save_picture(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save the area as a picture", "selection.png", "PNG (*.png);;JPEG (*.jpg)")
        if path and self._pixmap is not None:
            if not self._pixmap.save(path):
                QMessageBox.warning(self, "Save", "The picture could not be saved.")

    def _copy_picture(self):
        if self._pixmap is not None:
            QApplication.clipboard().setPixmap(self._pixmap)
            self.status.setText("The area is copied - paste it anywhere.")

    # ── print / save ──
    def _do(self):
        try:
            self._save_prefs()
            if self.dest.currentIndex() == 0:
                self._save_pdf()
            else:
                self._print_to_printer(self._printers[self.dest.currentIndex() - 1])
        except Exception as e:
            QMessageBox.warning(self, "Print", "Could not finish: %s" % e)

    def _save_prefs(self):
        save_prefs({"landscape": self.orient.currentIndex(), "paper": self.paper.currentIndex(), "margins": self.margins.currentIndex(),
                    "scale": self.scale.value(), "hf": self.hf.isChecked(), "bg": self.bg.isChecked()})

    def _save_pdf(self):
        if not self._tmp_pdf or not os.path.exists(self._tmp_pdf):
            QMessageBox.information(self, "Save as PDF", "Please wait for the preview, then try again.")
            return
        name = (self.view.title() or "page").strip()
        for ch in '\\/:*?"<>|':
            name = name.replace(ch, "_")
        path, _ = QFileDialog.getSaveFileName(self, "Save as PDF", name[:80] + ".pdf", "PDF (*.pdf)")
        if not path:
            return
        with open(self._tmp_pdf, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        self.accept()

    def _print_to_printer(self, printer_name):
        info = None
        for pi in QPrinterInfo.availablePrinters():
            if pi.printerName() == printer_name:
                info = pi
        printer = QPrinter(info, QPrinter.PrinterMode.HighResolution) if info else QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageLayout(self._layout())
        printer.setCopyCount(self.copies.value())
        printer.setColorMode(QPrinter.ColorMode.GrayScale if self.color.currentIndex() == 1 else QPrinter.ColorMode.Color)
        if self.duplex.isChecked():
            printer.setDuplex(QPrinter.DuplexMode.DuplexLongSide)
        if self.area.currentIndex() == 1:
            if self._pixmap is None:
                QMessageBox.information(self, "Print", "Choose the area first.")
                return
            p = QPainter(printer)
            r = printer.pageRect(QPrinter.Unit.DevicePixel)
            self._paint_pixmap(p, int(r.width()), int(r.height()))
            p.end()
            self.accept()
            return
        rng = self._ranges()
        if rng:
            printer.setPrintRange(QPrinter.PrintRange.PageRange)
            printer.setFromTo(rng[0][0], rng[-1][1])
        self.status.setText("Sending to the printer…")
        self.go.setEnabled(False)
        def done(ok):
            self.go.setEnabled(True)
            if ok:
                self.accept()
            else:
                QMessageBox.warning(self, "Print", "The printer did not accept the job.")
        self._inject_css()
        QTimer.singleShot(150, lambda: self.page.print(printer, done))

    def done(self, r):
        self._remove_css()
        try:
            if self._tmp_pdf and os.path.exists(self._tmp_pdf):
                self._doc = None
                os.remove(self._tmp_pdf)
        except OSError:
            pass
        super().done(r)


def show_print_dialog(win, to_pdf=False, start_area=False):
    view = win.tabs.currentWidget()
    if view is None or not hasattr(view, "page"):
        QMessageBox.information(win, "Print", "Open a web page first.")
        return None
    old = getattr(win, "_sps_print_dlg", None)
    if old is not None:
        try:
            old.close()
        except Exception:
            pass
    dlg = SpsPrintDialog(win, view, to_pdf=to_pdf, start_area=start_area)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    dlg.setWindowModality(Qt.WindowModality.WindowModal)
    win._sps_print_dlg = dlg                 # keep a reference (a window without one is garbage collected)
    dlg.show()
    return dlg
