#!/usr/bin/env python3
"""Grab DigHoloViewport modes panel for README (docs/images/gui.png)."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DEFAULT = REPO_ROOT / "docs" / "images" / "gui.png"


def build_window():
    from pyDigHolo import DigHolo
    from pyDigHolo.ui import DigHoloViewport

    dh = DigHolo(consoleRedirectToFile=False)
    gui = DigHoloViewport(dh, refresh_rate_fps=10)
    gui.show()
    gui.start()

    def teardown() -> None:
        gui.stop()
        gui.close()

    return gui, teardown


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture DigHoloViewport for README.")
    parser.add_argument("-o", "--output", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--wait-ms", type=int, default=1500)
    parser.add_argument("--offscreen", action="store_true")
    args = parser.parse_args()

    if args.offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import pyqtgraph as pg
    from PySide6.QtWidgets import QApplication

    pg.setConfigOptions(useOpenGL=False, antialias=True)

    app = QApplication.instance() or QApplication(sys.argv)
    window, teardown = build_window()
    window.resize(240, 380)
    window.show()
    window.raise_()
    window.activateWindow()

    deadline = time.perf_counter() + max(args.wait_ms, 200) / 1000.0
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pix = window.grab()
    if pix.isNull() or pix.width() < 10:
        teardown()
        raise SystemExit("grab() returned an empty pixmap")
    if not pix.save(str(args.output), "PNG"):
        teardown()
        raise SystemExit(f"Failed to write {args.output}")

    teardown()
    print(f"Wrote {args.output}")
    app.quit()


if __name__ == "__main__":
    main()
