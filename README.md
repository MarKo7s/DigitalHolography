# DigitalHolography

[digHolo](https://github.com/joelacarpenter/digHolo) is Joel Carpenter’s library for off-axis digital holography (Copyright 2021). The DLL, the C++ sources, and `digHolo.h` in this tree come from that repository. His copyright and permission notice stay in `digHolo.h`.

The Python wrapper around that DLL, including the ctypes header and the C++/DLL calling layer, was written by Daniel Dahl. This repository starts from that wrapper.

`pyDigHolo` is the engine module inside this repository. The current work is a refactor of that engine: settings live in `Properties`, and the helpers, the logger, the feeder, and the result readers sit beside `DigHolo`.

Next is connecting cameras through `DigHoloFeeder` in `pyDigHolo/digholoStreamer.py` and adding widgets.

## Install

Python 3.11 or newer.

```bash
pip install "pyDigHolo @ git+https://github.com/MarKo7s/DigitalHolography.git@v0.1.0"
```

That install includes `digHolo.dll` from `pyDigHolo/digHolo_v1.0.0/bin/Win64`.

Editable checkout:

```bash
pip install -e .
```

A conda environment with only Python and pip, and the scientific packages from pip:

```bash
conda env create -f environment.yml
```

## Layout

`DigHolo` keeps the DLL handle, the frame pointer, and coefficient unpacking. `Properties` holds the settings dictionary. `digholoResults` reads fields, coefficients, Fourier planes, and viewports. `digholoStreamer.DigHoloFeeder` feeds camera frames into `processBatch`.

## Versioning

`pyproject.toml` is the only version source. `pyDigHolo.__version__` reads the installed package metadata.

## Releasing

1. Add a `## [X.Y.Z]` section at the top of `CHANGELOG.md`.
2. Set `version` in `pyproject.toml` to the same number.
3. Commit.
4. From the release branch: `python scripts/release.py --from-changelog --branch <branch>`.
