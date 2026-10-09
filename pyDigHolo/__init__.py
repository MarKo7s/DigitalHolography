from importlib.metadata import PackageNotFoundError, version

from .digholoObject import DigHolo
from .digholoStreamer import DigHoloFeeder

try:
    __version__ = version("pyDigHolo")
except PackageNotFoundError:
    __version__ = "0.1.0"