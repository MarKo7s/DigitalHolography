# DigitalHolography

[digHolo](https://github.com/joelacarpenter/digHolo) is Joel Carpenter’s library for off-axis digital holography (Copyright 2021). The DLL, the C++ sources, and `digHolo.h` in this tree come from that repository. His copyright and permission notice stay in `digHolo.h`.

The Python wrapper around that DLL, including the ctypes header and the C++/DLL calling layer, was written by Daniel Dahl. This repository starts from that wrapper.

`pyDigHolo` is the engine module inside this repository. Settings live in `Properties`. Helpers, the logger, the feeder, result readers, config, and UI sit beside `DigHolo`.

## Install

Python 3.11 or newer.

```bash
pip install "pyDigHolo @ git+https://github.com/MarKo7s/DigitalHolography.git@v0.2.0"
```

Engine only. For the live viewport UI:

```bash
pip install "pyDigHolo[gui] @ git+https://github.com/MarKo7s/DigitalHolography.git@v0.2.0"
```

That install includes `digHolo.dll` from `pyDigHolo/digHolo_v1.0.0/bin/Win64`.

Editable checkout:

```bash
pip install -e .
pip install -e ".[gui]"
```

A conda environment with only Python and pip, and the scientific packages from pip:

```bash
conda env create -f environment.yml
```

On Windows, install PySide6 (and other Qt deps) via pip in that env — do not mix conda Qt with pip PySide6.

## Layout

`DigHolo` keeps the DLL handle, the frame pointer, coefficient unpacking, and a process lock used around batch + camera-viewport access. `Properties` holds the settings dictionary. `digholoResults` reads fields, coefficients, Fourier planes, and viewports. `digholoStreamer.DigHoloFeeder` feeds camera frames into `processBatch`. `pyDigHolo.ui.DigHoloViewport` is the multi-mode live viewport window. `pyDigHolo/config/appSettings.json` holds logger paths and related flags.

## Threading and buffers

digHolo does **not** own a private copy of every buffer you pass in. `digHoloSetBatch` points the engine at your float32 frame memory; viewport plotting also uses shared internal RGB / title buffers. Concurrent `processBatch` (e.g. from `DigHoloFeeder`) and `getViewPort` without synchronization can crash or return corrupt titles.

The wrapper therefore:

- Holds `_process_grab_lock` for `SetBatch` / `ProcessBatch` (and the matching path on frequency sweep).
- Locks camera-plane viewport reads (`getViewPort(1)`), which touch the live frame path.
- Offers `makeBufferCopy=True` on `processBatch` when the source array may be overwritten before the DLL finishes using it.

Keep feeder + UI on the same `DigHolo` instance and treat that lock as required for live streaming.

## Viewport UI

```python
from pyDigHolo.ui import DigHoloViewport

vp = DigHoloViewport(dh, refresh_rate_fps=20)
vp.show()
vp.start()
```

Checkboxes open floating plots (tiled from the top-left). Snap / float buttons group or separate them. Viewport file logs go under `%PROGRAMDATA%\LAB\algorithms\DigitalHolography\Viewport\` (see `appSettings.json`; `reset_logger` truncates on each new `DigHoloViewport`).

Camera averaging needs a ring buffer large enough for `get_tail(n)` (`n <= ring_buffer_size - 1`).

## Versioning

`pyproject.toml` is the only version source. `pyDigHolo.__version__` reads the installed package metadata.

## Releasing

1. Add a `## [X.Y.Z]` section at the top of `CHANGELOG.md`.
2. Set `version` in `pyproject.toml` to the same number.
3. Commit.
4. From the release branch: `python scripts/release.py --from-changelog --branch <branch>`.
