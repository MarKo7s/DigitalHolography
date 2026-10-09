import logging
import threading
from pathlib import Path

from . import digholoHeader as dh_dll

log = logging.getLogger("digHolo")
CONSOLE_FILENAME = "digHoloConsole.txt"


class ConsoleLogger:
    """
    Tried to link DigHolo console file to python logging
    does not work
    """
    def __init__(self, logger_name="DllLogger"):
        """
        dll: ctypes.CDLL instance
        filename: File where DLL console will be redirected
        logger_name: Name for Python logger
        """

        from importlib.resources import files
        file_path = str(files("modelabdrivers.digHolo").joinpath(f"{CONSOLE_FILENAME}"))
        log.debug(f"file_path of console: {file_path}")
        self.path = Path(file_path)
        self._stop_event = threading.Event()
        self._thread = None
        self._last_pos = 0
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

    def _watch_file(self):
        """Background thread: tails the file and logs new lines."""
        try:
            while not self._stop_event.is_set():
                log.debug("watch file cycle")
                if self.path.exists():
                    log.debug("path exists")

                    with self.path.open("r", encoding="utf-8", errors="ignore") as f:
                        if self.path.exists():
                            # Detect if file was replaced
                            stat = self.path.stat()
                            inode = (stat.st_ino, stat.st_size)
                            if inode != self._last_inode:
                                log.debug("Detected file change or recreation")
                                self._last_pos = 0
                                self._last_inode = inode

                            with self.path.open("r", encoding="utf-8", errors="ignore") as f:
                                f.seek(self._last_pos)
                                lines = f.readlines()
                                if lines:
                                    for line in lines:
                                        self.logger.info(f"[DLL] {line.strip()}")
                                    self._last_pos = f.tell()
                time.sleep(0.1)
        except Exception as e:
            log.exception("Exception in _watch_file thread: %s", e)

    def start(self):
        """Redirect DLL console output to file and start watcher."""
        self._thread = threading.Thread(target=self._watch_file, daemon=True)
        self._thread.start()

    def stop(self):
        """Restore DLL console and stop watcher."""
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        dh_dll.digHoloConsoleRestore()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
