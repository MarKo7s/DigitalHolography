# Changelog

## [0.2.0]

Threading-safe batch/viewport sync, live DigHolo viewport UI, and unified app settings.

- Synchronized `processBatch` / `getViewPort` with a process lock so the feeder thread and UI cannot race inside digHolo. digHolo holds pointers into the caller frame buffer (and shared viewport plot buffers); use `makeBufferCopy=True` when the source buffer may change, and keep viewport-1 reads under the same lock as batch processing.
- `DigHoloFeeder` camera streaming loop with averaging, refresh-rate capping, and optional frame-buffer copy.
- PySide6 / pyqtgraph DigHolo viewport UI (`pyDigHolo.ui`): floating mode menu, per-mode tiled windows, snap/float layout, FPS readout, and file logging under ProgramData.
- `pyDigHolo/config/appSettings.json` for logger paths and `reset_logger`.
- Optional `[gui]` extras: PySide6, pyqtgraph, PySide6-QtAds.

## [0.1.0]

First packaged snapshot of the pyDigHolo engine.

- Settings live in `Properties`, with `DigHolo` reading and writing that dictionary through the class.
- Helpers, the console logger, the frame feeder, and the DLL result readers sit beside `DigHolo`.
- The Win64 `digHolo.dll` is installed with the package.
