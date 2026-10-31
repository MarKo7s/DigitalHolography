"""DigHolo viewport controller: floating mode menu + independent plot windows.

Initial window size keeps the array aspect ratio and uses per-mode target
widths from ``VIEWPORT_DEFAULT_SIZE`` (edit that dict to tune). Snap tiles
open views in a plain QSplitter host — no QtAds reparenting (avoids crashes).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .digholoViewportViews import (
    VIEWPORT_DEFAULT_SIZE,
    VIEWPORT_MODES,
    DigHoloViewportView,
    display_size_for,
)
from .logHelper import get_logger

if TYPE_CHECKING:
    from ..digholoObject import DigHolo

_TITLE_PAD_H = 36
_BORDER_PAD = 16
_TILE_GAP = 8
_TILE_ORIGIN_X = 20
_TILE_ORIGIN_Y = 40


def _title_from_metadata(mode_name: str, metadata: list[str] | None) -> str:
    if not metadata or len(metadata) < 3:
        return mode_name
    unit_name, power_value, dimensions = metadata[0], metadata[1], metadata[2]
    return f"{mode_name} | {unit_name} : {power_value} | {dimensions}"


class _ViewportWindow(QMainWindow):
    """One floating RGB viewport; close unchecks the menu box via callback."""

    def __init__(
        self,
        idx: int,
        title: str,
        on_user_close,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.idx = idx
        self._on_user_close = on_user_close
        self._closing_from_menu = False
        self.view = DigHoloViewportView()
        self.setCentralWidget(self.view)
        self.setWindowTitle(title)
        tw = VIEWPORT_DEFAULT_SIZE.get(idx, 512)
        self.resize(tw + _BORDER_PAD, tw + _TITLE_PAD_H)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._closing_from_menu:
            self._on_user_close(self.idx)
        event.accept()


class _SnapHost(QMainWindow):
    """Snap tile host; user close unchecks every snapped mode."""

    def __init__(self, on_user_close, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_user_close = on_user_close
        self._closing_internal = False
        self.setWindowTitle("DigHolo Viewports")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._closing_internal:
            self._on_user_close()
        event.accept()


class DigHoloViewport(QWidget):
    """Floating mode menu that opens/closes independent viewport windows."""

    def __init__(
        self,
        dh: DigHolo,
        refresh_rate_fps: float = 20,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.dh = dh
        self._log = get_logger()
        fps = float(refresh_rate_fps) if refresh_rate_fps and refresh_rate_fps > 0 else 20.0
        fps = min(fps, 250.0)
        refresh_ms = max(int(round(1000.0 / fps)), 1)
        self.setWindowTitle("DigHolo Modes")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        self._checks: dict[int, QCheckBox] = {}
        self._windows: dict[int, _ViewportWindow] = {}
        self._syncing = False
        self._updating = False
        self._snapped = False
        self._snap_host: _SnapHost | None = None
        self._snap_splitter: QSplitter | None = None
        self._snap_idxs: list[int] = []

        self._vp_count = 0
        self._vp_t0 = time.perf_counter()
        self._viewport_fps = 0.0
        self._none_log_t: dict[int, float] = {}

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        mode_box = QGroupBox("Viewports")
        mode_layout = QVBoxLayout(mode_box)
        for idx, name in VIEWPORT_MODES.items():
            cb = QCheckBox(name)
            cb.toggled.connect(lambda checked, i=idx: self._on_mode_toggled(i, checked))
            mode_layout.addWidget(cb)
            self._checks[idx] = cb
        root.addWidget(mode_box)

        snap_btn = QPushButton("Snap all viewports together")
        snap_btn.setToolTip("Tile open viewports side-by-side in one window.")
        snap_btn.clicked.connect(self.snap_all_viewports)
        root.addWidget(snap_btn)

        float_btn = QPushButton("Float all again")
        float_btn.setToolTip("Return snapped viewports to independent floating windows.")
        float_btn.clicked.connect(self.float_all_viewports)
        root.addWidget(float_btn)

        self._fps_label = QLabel("fps: 0.0")
        root.addWidget(self._fps_label)

        self.resize(220, 340)

        self._timer = QTimer(self)
        self._timer.setInterval(refresh_ms)
        self._timer.timeout.connect(self._update)

    # --- public API ---------------------------------------------------------

    def start(self) -> None:
        if not self._timer.isActive():
            self._vp_count = 0
            self._vp_t0 = time.perf_counter()
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.stop()
        if self._snapped:
            self.float_all_viewports()
        for win in list(self._windows.values()):
            win._closing_from_menu = True
            win.close()
        self._windows.clear()
        if self._snap_host is not None:
            self._snap_host._closing_internal = True
            self._snap_host.close()
            self._snap_host = None
            self._snap_splitter = None
            self._snap_idxs = []
            self._snapped = False
        super().closeEvent(event)

    # --- menu / windows -----------------------------------------------------

    def _on_mode_toggled(self, idx: int, checked: bool) -> None:
        if self._syncing:
            return
        if checked:
            self._show_window(idx)
        else:
            self._hide_window(idx)

    def _on_window_user_close(self, idx: int) -> None:
        cb = self._checks.get(idx)
        if cb is None:
            return
        self._syncing = True
        try:
            cb.setChecked(False)
        finally:
            self._syncing = False
        win = self._windows.get(idx)
        if win is not None:
            win.hide()

    def _show_window(self, idx: int) -> None:
        if self._snapped:
            self.float_all_viewports()
        win = self._windows.get(idx)
        if win is None:
            win = _ViewportWindow(idx, VIEWPORT_MODES[idx], self._on_window_user_close)
            self._windows[idx] = win
        win.show()
        win.raise_()
        self._poll_one(idx)
        if win.view.frame_size() is not None:
            self._apply_window_size(win)
        self._layout_floating_windows()

    def _hide_window(self, idx: int) -> None:
        if self._snapped:
            self.float_all_viewports()
        win = self._windows.get(idx)
        if win is None:
            return
        win._closing_from_menu = True
        try:
            win.hide()
        finally:
            win._closing_from_menu = False
        self._layout_floating_windows()

    def _apply_window_size(self, win: _ViewportWindow) -> None:
        wh = win.view.frame_size()
        if wh is None:
            return
        arr_w, arr_h = wh
        cw, ch = display_size_for(win.idx, arr_w, arr_h)
        win.resize(cw + _BORDER_PAD, ch + _TITLE_PAD_H)

    def _layout_floating_windows(self) -> None:
        """Place open floating windows left-to-right from the top-left (mode order)."""
        if self._snapped:
            return
        open_wins = [
            self._windows[idx]
            for idx in VIEWPORT_MODES
            if idx in self._windows
            and self._checks[idx].isChecked()
            and self._windows[idx].isVisible()
        ]
        if not open_wins:
            return

        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            origin = screen.availableGeometry().topLeft()
            x0 = origin.x() + _TILE_ORIGIN_X
            y0 = origin.y() + _TILE_ORIGIN_Y
        else:
            x0, y0 = _TILE_ORIGIN_X, _TILE_ORIGIN_Y

        x = x0
        for win in open_wins:
            win.move(x, y0)
            x += win.width() + _TILE_GAP

    def _uncheck_idxs(self, idxs: list[int]) -> None:
        self._syncing = True
        try:
            for idx in idxs:
                cb = self._checks.get(idx)
                if cb is not None and cb.isChecked():
                    cb.setChecked(False)
        finally:
            self._syncing = False

    # --- snap / float -------------------------------------------------------

    def snap_all_viewports(self) -> None:
        open_idxs = [
            idx
            for idx in sorted(self._windows)
            if self._checks[idx].isChecked()
        ]
        if len(open_idxs) < 1:
            return
        if self._snapped:
            return

        was_running = self._timer.isActive()
        self._timer.stop()
        try:
            host = _SnapHost(self._on_snap_host_user_close)
            splitter = QSplitter(Qt.Orientation.Horizontal)
            sizes: list[int] = []
            max_h = 200

            for idx in open_idxs:
                win = self._windows[idx]
                win._closing_from_menu = True
                win.hide()
                win._closing_from_menu = False

                view = win.takeCentralWidget()
                if view is None or not isinstance(view, DigHoloViewportView):
                    view = win.view
                    view.setParent(None)
                win.view = view
                splitter.addWidget(view)

                wh = view.frame_size()
                if wh is not None:
                    cw, ch = display_size_for(idx, wh[0], wh[1])
                else:
                    cw = VIEWPORT_DEFAULT_SIZE.get(idx, 512)
                    ch = cw
                sizes.append(max(cw, 64))
                max_h = max(max_h, ch)

            host.setCentralWidget(splitter)
            if sizes:
                splitter.setSizes(sizes)

            total_w = sum(sizes) + 40
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                total_w = min(total_w, int(avail.width() * 0.95))
                max_h = min(max_h + _TITLE_PAD_H + 40, int(avail.height() * 0.9))
            host.resize(max(total_w, 400), max(max_h, 240))

            self._snap_host = host
            self._snap_splitter = splitter
            self._snap_idxs = list(open_idxs)
            self._snapped = True
            host.show()
            host.raise_()
            host.activateWindow()
        finally:
            if was_running:
                self._timer.start()

    def _on_snap_host_user_close(self) -> None:
        """User closed the snap window → restore views hidden and uncheck modes."""
        if not self._snapped:
            return
        idxs = list(self._snap_idxs)
        was_running = self._timer.isActive()
        self._timer.stop()
        try:
            for idx in idxs:
                win = self._windows.get(idx)
                if win is None:
                    continue
                view = win.view
                view.setParent(None)
                win.setCentralWidget(view)
                win.view = view
                win._closing_from_menu = True
                win.hide()
                win._closing_from_menu = False

            self._uncheck_idxs(idxs)
            self._snap_host = None
            self._snap_splitter = None
            self._snap_idxs = []
            self._snapped = False
            self._log.info("snap host closed by user; unchecked modes %s", idxs)
        finally:
            if was_running:
                self._timer.start()

    def float_all_viewports(self) -> None:
        if not self._snapped:
            return

        was_running = self._timer.isActive()
        self._timer.stop()
        try:
            for idx in list(self._snap_idxs):
                win = self._windows.get(idx)
                if win is None:
                    continue
                view = win.view
                view.setParent(None)
                win.setCentralWidget(view)
                win.view = view
                if self._checks[idx].isChecked():
                    if view.frame_size() is not None:
                        self._apply_window_size(win)
                    win.show()
                    win.raise_()

            host = self._snap_host
            self._snap_host = None
            self._snap_splitter = None
            self._snap_idxs = []
            self._snapped = False
            if host is not None:
                host._closing_internal = True
                host.hide()
                host.deleteLater()
            self._layout_floating_windows()
        finally:
            if was_running:
                self._timer.start()

    # --- polling ------------------------------------------------------------

    def _update(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            for idx in list(self._windows):
                if not self._checks[idx].isChecked():
                    continue
                self._poll_one(idx)
            self._vp_count += 1
            now = time.perf_counter()
            dt = now - self._vp_t0
            if dt >= 1.0:
                self._viewport_fps = self._vp_count / dt
                self._vp_count = 0
                self._vp_t0 = now
                self._fps_label.setText(f"fps: {self._viewport_fps:.1f}")
        finally:
            self._updating = False

    def _poll_one(self, idx: int) -> None:
        win = self._windows.get(idx)
        if win is None:
            return
        name = VIEWPORT_MODES[idx]
        try:
            result = self.dh.getViewPort(idx, forceProcessing=0)
        except Exception:
            self._log.exception(
                "getViewPort failed win=%s idx=%s mode=%s",
                win.windowTitle(),
                idx,
                name,
            )
            return
        if result is None:
            # Rate-limit: None can fire every poll tick (esp. camera metadata)
            now = time.perf_counter()
            last = self._none_log_t.get(idx, 0.0)
            if now - last >= 1.0:
                self._none_log_t[idx] = now
                self._log.error(
                    "getViewPort returned None win=%s idx=%s mode=%s "
                    "(no data or metadata parse failed in digHolo)",
                    win.windowTitle(),
                    idx,
                    name,
                )
            return
        rgb, metadata = result
        view = win.view
        size_changed = view.set_rgb(rgb)
        title = _title_from_metadata(name, metadata)
        win.setWindowTitle(title)
        if size_changed and win.isVisible() and not self._snapped:
            self._apply_window_size(win)
            self._layout_floating_windows()
