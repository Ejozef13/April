"""Optional KDE/Linux tray companion; owns only its server and microphone."""
import json
import socket
import signal
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QLockFile, QTimer, QUrl, Qt
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import (QApplication, QLabel, QMenu, QMessageBox,
                               QPushButton, QSystemTrayIcon, QVBoxLayout, QHBoxLayout, QWidget)
from PySide6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile,
                                    QWebEngineSettings, QWebEngineUrlRequestInterceptor)
from PySide6.QtWebEngineWidgets import QWebEngineView

from .desktop_audio import Microphone


class LocalOnly(QWebEngineUrlRequestInterceptor):
    def __init__(self, base, parent):
        super().__init__(parent)
        self.base = QUrl(base)

    def interceptRequest(self, info):
        url = info.requestUrl()
        local = (url.scheme() in {'http', 'ws'} and url.host() == self.base.host()
                 and url.port() == self.base.port())
        # Audio blobs never contain executable page content.
        info.block(not (local or url.scheme() in {'data', 'blob'}))


class Page(QWebEnginePage):
    def __init__(self, profile, base, parent):
        super().__init__(profile, parent)
        self.base = QUrl(base)

    def acceptNavigationRequest(self, url, kind, main_frame):
        local = (url.scheme() == self.base.scheme() and url.host() == self.base.host()
                 and url.port() == self.base.port() and url.path() == '/')
        if local:
            return True
        if main_frame and kind == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            if url.scheme() in {'https', 'http'} and not url.userName():
                QDesktopServices.openUrl(url)
        return False


class Companion(QWidget):
    def __init__(self, config, base, *, microphone=True, hidden=False):
        super().__init__()
        self.config, self.base = config, base
        self.enabled = config.mode != 'simulation'
        self.activating = False
        self.last_state = None
        self.error_pending = False
        self.poll_pending = False
        self.was_busy = False
        self.setWindowTitle('APRIL · companion')
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.resize(config.widget_width, config.widget_height)
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(max(area.left(), area.right() - config.widget_width - 24),
                      max(area.top(), area.bottom() - config.widget_height - 24))
        icon = QIcon(str(Path(__file__).parent / 'web/tray.svg'))
        self.setWindowIcon(icon)
        self.setStyleSheet('QWidget{background:#172523;color:#e5eee7} QPushButton{padding:7px;border:1px solid #58774d;border-radius:6px} QLabel{padding:4px}')
        self.status = QLabel('Connecting to April…')
        self.status.setWordWrap(True)
        self.view = QWebEngineView()
        self.profile = QWebEngineProfile(self)  # unnamed: off-the-record, no disk history
        self.interceptor = LocalOnly(base, self.profile)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        self.page = Page(self.profile, base, self.view)
        self.view.setPage(self.page)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, False)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.page.permissionRequested.connect(lambda permission: permission.deny())
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        for label, callback in [('Record', self.activate), ('Dismiss', self.dismiss),
                                ('Open full app', lambda: QDesktopServices.openUrl(QUrl(base)))]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(self.status)
        layout.addWidget(self.view)
        self.worker = Microphone(config)
        self.worker.wake.connect(self.activate)
        self.worker.audio.connect(self.deliver_audio)
        self.worker.level.connect(lambda rms, epoch:
            self.js('window.aprilDesktop?.level(' + str(rms) + ',' + str(epoch) + ')'))
        self.worker.empty.connect(self.empty_recording)
        self.worker.failed.connect(self.mic_error)
        self.tray = QSystemTrayIcon(icon, self)
        menu = QMenu()
        self.menu = menu
        for label, callback in [('Show April', self.reveal), ('Record', self.activate)]:
            action = menu.addAction(label)
            action.triggered.connect(callback)
        self.pause_action = QAction('Pause microphone', self, checkable=True)
        self.pause_action.setChecked(not self.enabled)
        self.pause_action.toggled.connect(self.pause)
        menu.addAction(self.pause_action)
        menu.addAction('Retry microphone', self.retry)
        menu.addAction('Dismiss', self.dismiss)
        menu.addSeparator()
        menu.addAction('Quit April', lambda: QApplication.instance().exit(0))
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.reveal() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.setToolTip('APRIL · connecting')
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        else:
            hidden = False  # Never hide the only way to quit/restore the app.
        self.view.load(QUrl(base + '/?widget=1'))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_after_reply)
        if microphone and config.mode != 'simulation':
            self.worker.start()
        if not hidden:
            self.show()

    def js(self, expression, callback=None):
        self.page.runJavaScript(expression, callback or (lambda value: None))

    def poll(self):
        if self.poll_pending:
            return
        self.poll_pending = True
        self.js('JSON.stringify(window.aprilDesktop ? window.aprilDesktop.snapshot() : null)', self.snapshot)

    def snapshot(self, value):
        self.poll_pending = False
        try:
            value = json.loads(value) if isinstance(value, str) else value
        except (ValueError, TypeError):
            return
        if not isinstance(value, dict):
            return
        state, connected = value.get('state'), value.get('connected')
        self.worker.ready(bool(self.enabled and connected and state in {'idle', 'error'} and not self.activating))
        if not connected:
            self.worker.cancel()
            self.status.setText('Disconnected · microphone paused. Quit and restart April.')
        if state != self.last_state:
            if state in {'transcribing', 'thinking', 'speaking'}:
                self.was_busy = True
            if state == 'idle' and self.was_busy:
                self.worker.cancel()  # Cooldown starts after playback, not before inference.
                self.was_busy = False
                if self.config.widget_hide_seconds:
                    self.hide_timer.start(int(self.config.widget_hide_seconds * 1000))
            if state == 'error':
                self.worker.cancel()
                self.reveal()
            self.last_state = state
        if not self.error_pending and connected:
            self.status.setText('SIMULATION · no microphone or wake detection' if self.config.mode == 'simulation'
                                else ('Microphone paused' if not self.enabled else
                                      ('Listening for your command…' if state == 'listening' else
                                       'Wake listener active · local microphone' if state in {'idle', 'error'}
                                       else 'Wake listener paused during response')))
        self.tray.setToolTip('APRIL · ' + self.status.text()[:100])
        request = value.get('request')
        if request == 'record':
            self.activate()
        elif request == 'finish':
            self.worker.finish()
        elif request == 'cancel':
            self.worker.cancel()

    def activate(self):
        if self.activating:
            return
        self.reveal()
        if self.config.mode == 'simulation':
            self.js('window.aprilDesktop?.demo()')
            return
        if not self.enabled:
            self.status.setText('Microphone paused. Resume it from the tray before recording.')
            return
        self.activating = True
        self.worker.ready(False)
        def begin(epoch):
            self.activating = False
            if isinstance(epoch, (int, float)) and not isinstance(epoch, bool) and epoch >= 0:
                self.worker.capture(int(epoch))
        self.js('window.aprilDesktop ? window.aprilDesktop.begin() : -1', begin)

    def deliver_audio(self, encoded, epoch):
        self.js('window.aprilDesktop?.audio(' + json.dumps(encoded) + ',' + str(epoch) + ')')

    def empty_recording(self, epoch):
        self.js('window.aprilDesktop?.empty(' + str(epoch) + ')')

    def mic_error(self, message):
        self.worker.cancel()
        self.error_pending = True
        self.status.setText(message)
        self.js('window.aprilDesktop?.cancel()')
        self.reveal()

    def retry(self):
        self.error_pending = False
        self.worker.retry()

    def pause(self, paused):
        self.enabled = not paused
        self.worker.cancel()
        self.js('window.aprilDesktop?.cancel()')
        if not paused:
            self.retry()

    def reveal(self):
        self.hide_timer.stop()
        self.show()
        self.raise_()
        self.activateWindow()  # Wayland may decline focus; tray/manual fallback remains.

    def dismiss(self):
        self.hide_timer.stop()
        self.worker.cancel()
        self.js('window.aprilDesktop?.cancel()')
        if self.tray.isVisible():
            self.hide()
        else:
            self.showMinimized()

    def hide_after_reply(self):
        if self.last_state == 'idle' and self.tray.isVisible():
            self.hide()

    def closeEvent(self, event):
        event.ignore()
        self.dismiss()

    def shutdown(self):
        self.timer.stop()
        self.worker.cancel()
        self.worker.stop()
        if not self.worker.wait(5000):
            # Never terminate an audio thread while it owns a device.
            self.worker.wait()
        self.tray.hide()

    def dispose(self):
        self.shutdown()
        self.page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.profile.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def main(config, *, hidden=False):
    """Start a dedicated loopback server; never kill/reuse an unrelated process."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    Path('artifacts').mkdir(exist_ok=True)
    lock = QLockFile(str(Path('artifacts/widget.lock').absolute()))
    if not lock.tryLock(0):
        raise SystemExit('April widget is already running. Use its tray icon.')
    family = socket.AF_INET6 if ':' in config.host else socket.AF_INET
    try:
        with socket.socket(family) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((config.host, config.port))
    except OSError:
        raise SystemExit('APRIL port is already in use. Stop your existing APRIL instance, then start the widget.')
    server = subprocess.Popen([sys.executable, '-m', 'april.server'])
    host = '[' + config.host + ']' if ':' in config.host else config.host
    base = f'http://{host}:{config.port}'
    window = None
    interrupted = False
    def quit_from_signal(signum, frame):
        nonlocal interrupted
        # Never call Qt from Python's asynchronous signal callback: it can
        # interrupt Qt while it owns an internal lock. The watchdog quits from
        # a normal GUI callback instead.
        interrupted = True
    previous_handlers = {signum: signal.signal(signum, quit_from_signal)
                         for signum in (signal.SIGINT, signal.SIGTERM)}
    try:
        # Bounded startup; do not show an error page before Uvicorn is listening.
        import httpx
        import time
        for attempt in range(50):
            if interrupted:
                raise SystemExit(0)
            if server.poll() is not None:
                raise SystemExit('APRIL backend exited during widget startup. Check terminal output.')
            try:
                response = httpx.get(base + '/health', timeout=.2, trust_env=False)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        else:
            raise SystemExit('APRIL backend did not become ready within the startup deadline.')
        if interrupted:
            raise SystemExit(0)
        window = Companion(config, base, hidden=hidden)
        # Keep shutdown handling installed after Qt/Chromium initialization.
        for signum in previous_handlers:
            signal.signal(signum, quit_from_signal)
        def exited():
            if interrupted:
                app.exit(0)
                return
            if server.poll() is not None:
                window.worker.cancel()
                window.status.setText('APRIL backend stopped. Quit and restart the widget.')
                window.reveal()
        watchdog = QTimer()
        watchdog.timeout.connect(exited)
        watchdog.start(1000)
        app.aboutToQuit.connect(window.shutdown)
        if interrupted:
            return 0
        return app.exec()
    finally:
        if window:
            window.dispose()
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        lock.unlock()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
