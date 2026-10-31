"""PyQtGraph view widgets for digHolo viewport RGB bitmaps."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QVBoxLayout, QWidget

# digHolo.h DIGHOLO_VIEWPORT_* (skip NONE=0; COUNT=9 is not a mode)
VIEWPORT_MODES: dict[int, str] = {
    1: "camera",
    2: "Fourier",
    3: "Fourier dB",
    4: "Fourier window",
    5: "Fourier window abs",
    6: "field",
    7: "field abs",
    8: "field from modes",
}

# Target *content* width in pixels for the floating window.
# Height is derived from the array aspect ratio: h = w * (arr_h / arr_w).
# Tune per mode — small arrays (field ~128px) need a larger target width than
# full camera frames so they open at a usable on-screen size.
VIEWPORT_DEFAULT_SIZE: dict[int, int] = {
    1: 640,  # camera
    2: 300,  # Fourier
    3: 300,  # Fourier dB
    4: 600,  # Fourier window
    5: 600,  # Fourier window abs
    6: 400,  # field
    7: 400,  # field abs
    8: 400,  # field from modes
}

_DEFAULT_TARGET_W = 512


def display_size_for(idx: int, arr_w: int, arr_h: int) -> tuple[int, int]:
    """Return (content_w, content_h) keeping array aspect, sized to VIEWPORT_DEFAULT_SIZE."""
    if arr_w <= 0 or arr_h <= 0:
        tw = VIEWPORT_DEFAULT_SIZE.get(idx, _DEFAULT_TARGET_W)
        return tw, tw
    target_w = VIEWPORT_DEFAULT_SIZE.get(idx, _DEFAULT_TARGET_W)
    content_w = max(int(target_w), 64)
    content_h = max(int(round(content_w * (arr_h / arr_w))), 64)
    return content_w, content_h


class DigHoloViewportView(QWidget):
    """RGB plot only (no histogram): ViewBox + ImageItem, aspect-locked."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._frame_wh: tuple[int, int] | None = None

        self._graphics = pg.GraphicsLayoutWidget()
        self._vb = self._graphics.addViewBox(lockAspect=True, enableMenu=False)
        self._vb.setAspectLocked(True)
        self._vb.invertY(True)
        self._vb.setMenuEnabled(False)
        self._item = pg.ImageItem(axisOrder="row-major")
        self._vb.addItem(self._item)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._graphics)

    def set_rgb(self, rgb: np.ndarray) -> bool:
        """Push an (H, W, 3) uint8 RGB bitmap. True if frame shape changed."""
        if rgb is None or rgb.size == 0:
            return False
        h, w = int(rgb.shape[0]), int(rgb.shape[1])
        size_changed = self._frame_wh != (w, h)
        self._frame_wh = (w, h)
        self._item.setImage(rgb, autoLevels=False)
        if size_changed:
            self._vb.setRange(
                xRange=(0.0, float(w)),
                yRange=(0.0, float(h)),
                padding=0.0,
            )
            self.updateGeometry()
        return size_changed

    def frame_size(self) -> tuple[int, int] | None:
        return self._frame_wh

    def sizeHint(self) -> QSize:  # noqa: N802
        if self._frame_wh is not None:
            w, h = self._frame_wh
            return QSize(max(w, 64), max(h, 64))
        return QSize(256, 256)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(64, 64)
