import threading
from time import sleep

import numpy as np


class DigHoloFeeder(threading.Thread):
    """
    Each iteration take frame and process it.
    So digholo internal viewport buffer is updated for viewports and current values
    """
    def __init__(self, cam, dh, cam_rows_range=(0, 256), callback=None, stop_event=None, loop_period=0.1, startStream=True):
        super().__init__()
        self._cam = cam
        self._dh = dh
        self._rows_range = cam_rows_range
        self._callback = callback
        self._loop_period = loop_period

        self.stop_event = stop_event or threading.Event()

        if startStream:
            self.start()

    def run(self):
        try:
            self._dh.setProps(batchCount=1)
            while not self.stop_event.is_set():
                raw_calib_frame, times, counts = self._cam.grabTail(1)
                calib_frame = raw_calib_frame[self._rows_range[0], :self._rows_range[1], :]
                coefs = self._dh.processBatch(calib_frame.astype(np.float32), CalculateMetrics=False)

                if self._callback:
                    self._callback(coefs)
                sleep(self._loop_period)
        except Exception as e:
            print(f"[CalibrationThread] Error: {e}")

    def stop(self):
        self.stop_event.set()
