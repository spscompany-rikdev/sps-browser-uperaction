"""Memory saver / Energy saver controls (visible in the Quick panel).

Memory saver : the browser's existing 'tab sleep' (discard tabs that were not used for N minutes).
Energy saver : background tabs are FROZEN (no timers/scripts run) - saves battery; the tab wakes up the moment you open it.
Playing music/video tabs are never frozen or put to sleep."""
import os
from PyQt6.QtCore import QTimer
from PyQt6.QtWebEngineCore import QWebEnginePage

SLEEP_CHOICES = (5, 15, 30, 60)


def _pages(mw):
    for i in range(mw.tabs.count()):
        w = mw.tabs.widget(i)
        try:
            yield i, w, w.page()
        except Exception:
            continue


def sleeping_count(mw):
    n = 0
    for _, _, pg in _pages(mw):
        try:
            if getattr(pg, "_sps_sleeping", False) or pg.lifecycleState() != QWebEnginePage.LifecycleState.Active:
                n += 1
        except Exception:
            pass
    return n


def memory_mb():
    try:
        import psutil
        p = psutil.Process(os.getpid())
        total = p.memory_info().rss
        for c in p.children(recursive=True):
            try:
                total += c.memory_info().rss
            except Exception:
                pass
        return int(total / 1048576)
    except Exception:
        return None


def sleep_others_now(mw):
    cur, n = mw.tabs.currentIndex(), 0
    for i, w, pg in _pages(mw):
        if i == cur or pg is None:
            continue
        try:
            if pg.recentlyAudible():
                continue
            if pg.lifecycleState() == QWebEnginePage.LifecycleState.Active:
                pg.setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
                pg._sps_sleeping = True; n += 1
                mw.tabs.setTabToolTip(i, "Sleeping — click to wake")
        except Exception:
            pass
    return n


def energy_tick(mw):
    """Freeze background tabs, thaw the current one. Cheap: runs every few seconds, touches each tab once."""
    on = bool(mw.settings_data.get("energy_saver", False))
    cur = mw.tabs.currentIndex()
    for i, w, pg in _pages(mw):
        if pg is None or getattr(pg, "_sps_sleeping", False):
            continue
        try:
            st = pg.lifecycleState()
            if i == cur or not on:
                if st == QWebEnginePage.LifecycleState.Frozen:
                    pg.setLifecycleState(QWebEnginePage.LifecycleState.Active)
            elif st == QWebEnginePage.LifecycleState.Active and not pg.recentlyAudible():
                pg.setLifecycleState(QWebEnginePage.LifecycleState.Frozen)
        except Exception:
            pass


def install(mw):
    t = QTimer(mw); t.timeout.connect(lambda: energy_tick(mw)); t.start(4000)
    mw._sps_energy_timer = t
