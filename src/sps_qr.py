"""QR codes + 'Send tab' (no account, no server: the link travels inside the QR picture or as a share link)."""
from PyQt6.QtCore import Qt, QRectF, QUrl
from PyQt6.QtGui import QPixmap, QPainter, QColor, QGuiApplication
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QFileDialog, QMessageBox, QApplication)

MAX_QR_BYTES = 1800          # larger texts are not reliably scannable


def qr_matrix(text):
    import segno
    return [[bool(c) for c in row] for row in segno.make(text, error="m").matrix]


def qr_pixmap(text, size=280, border=4):
    m = qr_matrix(text)
    n = len(m) + 2 * border
    cell = max(2, size // n)
    px = QPixmap(cell * n, cell * n); px.fill(QColor("white"))
    p = QPainter(px); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("black"))
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                p.drawRect((x + border) * cell, (y + border) * cell, cell, cell)
    p.end()
    return px


def split_urls(text):
    out = []
    for line in (text or "").replace(",", "\n").splitlines():
        line = line.strip()
        if line.lower().startswith(("http://", "https://")):
            out.append(line)
    return out


class SendTabDialog(QDialog):
    def __init__(self, mw):
        super().__init__(mw)
        self.mw = mw
        self.setWindowTitle("Send tab")
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self); lay.setSpacing(8)
        w = mw.tabs.currentWidget()
        self.url = w.url().toString() if w is not None and hasattr(w, "url") else ""
        self.title = (mw.tabs.tabText(mw.tabs.currentIndex()) or "").replace("💤", "").strip()
        lay.addWidget(self._lbl("Scan this with your phone camera (or any QR app) to open the page there:"))
        self.qr = QLabel(); self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.qr)
        self.note = self._lbl(""); lay.addWidget(self.note)
        self._draw()
        row = QHBoxLayout()
        b = QPushButton("Copy link"); b.clicked.connect(self._copy); row.addWidget(b)
        b = QPushButton("Save QR picture…"); b.clicked.connect(self._save); row.addWidget(b)
        b = QPushButton("Copy all tabs"); b.clicked.connect(self._copy_all); row.addWidget(b)
        lay.addLayout(row)
        lay.addWidget(self._lbl("Received links or a list of tabs? Paste them here and open them:"))
        self.paste = QPlainTextEdit(); self.paste.setPlaceholderText("https://…\nhttps://…"); self.paste.setFixedHeight(70)
        lay.addWidget(self.paste)
        b = QPushButton("Open the pasted links in new tabs"); b.clicked.connect(self._open_pasted); lay.addWidget(b)

    @staticmethod
    def _lbl(t):
        l = QLabel(t); l.setWordWrap(True); return l

    def _draw(self):
        if not self.url.lower().startswith(("http://", "https://")):
            self.qr.setText("This tab has no web address to send."); return
        if len(self.url.encode("utf-8")) > MAX_QR_BYTES:
            self.qr.setText("The address is too long for a QR picture - use 'Copy link'."); return
        try:
            self.qr.setPixmap(qr_pixmap(self.url, 280))
            self.note.setText(self.title[:70] or self.url[:70])
        except Exception as e:
            self.qr.setText("QR could not be drawn (%s). Use 'Copy link'." % type(e).__name__)

    def _copy(self):
        QGuiApplication.clipboard().setText(self.url); self.note.setText("Link copied.")

    def _all_urls(self):
        urls = []
        for i in range(self.mw.tabs.count()):
            w = self.mw.tabs.widget(i)
            try:
                u = w.url().toString()
                if u.lower().startswith(("http://", "https://")):
                    urls.append(u)
            except Exception:
                pass
        return urls

    def _copy_all(self):
        urls = self._all_urls()
        QGuiApplication.clipboard().setText("\n".join(urls)); self.note.setText("%d tab link(s) copied - paste them on the other device." % len(urls))

    def _save(self):
        if self.qr.pixmap() is None or self.qr.pixmap().isNull():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save QR picture", "tab_qr.png", "PNG (*.png)")
        if path:
            self.qr.pixmap().save(path)

    def _open_pasted(self):
        urls = split_urls(self.paste.toPlainText())
        if not urls:
            QMessageBox.information(self, "Send tab", "No web links found in the text."); return
        for u in urls[:30]:
            self.mw.add_new_tab(QUrl(u))
        self.accept()


def show_send_tab(mw):
    SendTabDialog(mw).exec()
