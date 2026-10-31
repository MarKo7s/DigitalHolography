import threading
from time import perf_counter, sleep

import numpy as np

from .digholoUtilities import crop_frames_to_multiple_of_16, snap_hw_multiple_of_16

COPY_CAMERA_BUFFER_FRAMES = False

class DigHoloFeeder(threading.Thread):
    """
    Stream frames from any camera-like object into DigHolo.processBatch.

    Pass the camera object and the name of a method that returns the last N
    frames from a buffer (ndarray or (ndarray, ...)). digHolo needs H and W
    multiples of 16; the feeder snaps DigHolo FrameHeight/Width and crops
    grabs automatically. Dual-pol layouts should place H|V side-by-side
    (horizontal), not stacked vertically.
    """
    def __init__(self, dh_Object, cam_Object, cam_grab_ufunc_name:str, averaging = 1, startStream=True, refresh_rate_fps = None, callback=None):
        super().__init__()
        self._cam = cam_Object
        self._dh = dh_Object
        self._callback = callback
        
        if refresh_rate_fps is None or refresh_rate_fps <= 0:
            refresh_rate_fps = 240 #Default to 240 fps
        refresh_rate_fps = int(min(refresh_rate_fps, 240))
        self._loop_period = 1/refresh_rate_fps
        self._averaging = averaging

        #Deal with the camera grab function:
        if not isinstance(cam_grab_ufunc_name, str):
            raise ValueError(f"cam_grab_ufunc_name must be a string, got {type(cam_grab_ufunc_name)}")
        self._grab_ufunc = getattr(self._cam, cam_grab_ufunc_name) 
        if not callable(self._grab_ufunc):
            raise ValueError(f"cam_grab_ufunc_name must be a callable, got {type(self._grab_ufunc)}")

        props = self._dh.getProps()
        h16, w16 = snap_hw_multiple_of_16(props["FrameHeight"], props["FrameWidth"])
        if h16 != props["FrameHeight"] or w16 != props["FrameWidth"]:
            self._dh.setProps(FrameHeight=h16, FrameWidth=w16)
        self._frame_H = h16
        self._frame_W = w16
        self._dh_frame_H = h16
        self._dh_frame_W = w16

        #Thread control:
        self._kill_tread = False
        self.pause_event = threading.Event()

        self._loop_etime = 0
        self.processing_frame_rate = 0
        self.grabbing_frame_rate = 0

        #Results of the processing:
        self.coefs = None

        self._error_message = None

        if startStream:
            self.pause_event.set()

        self.start() #start the loop

    def _grab_frames(self):
        result = self._grab_ufunc(self._averaging)
        frames = result[0] if isinstance(result, tuple) else result
        frames = np.asarray(frames)
        if frames.ndim == 2:
            frames = frames[None, ...]
        # digHolo: H/W multiples of 16; keep configured ROI (top-left crop)
        frames = crop_frames_to_multiple_of_16(frames)
        return frames[:, : self._frame_H, : self._frame_W]

    def _update_frame_size_from_dh(self):
        self._dh_frame_W = self.dh.getProps()["FrameWidth"]
        self._dh_frame_H = self.dh.getProps()["FrameHeight"]
        self._frame_W = self.frames.shape[2]
        self._frame_H = self.frames.shape[1]

    def set_averaging(self, averaging:int):
        if averaging > 0:
            self._averaging = averaging
        else:
            print(f"Warning: averaging must be greater than 1, got {averaging}")

    def run(self):
            #!Grabbing loop
            while not self._kill_tread:
                try:
                    self.pause_event.wait()
                    _t0 = perf_counter()
                    frames = self._grab_frames()
                    #Check that frames are not crap

                    if not isinstance(frames, np.ndarray):
                        self._error_message = f"Frames are not a numpy array, got {type(frames)}"
                        sleep(self._loop_period or 0.1)
                        continue

                    #we can continue only if frames are a numpy array
                    _dim = frames.shape
                    # digholo takes 3D arrays with the first dimension being the number of frames
                    if len(_dim) == 2:
                        frames  = frames[None, :, :]

                    num_frames = frames.shape[0]

                    if num_frames != self._averaging:
                        print(f"Warning: number of frames {num_frames} does not match averaging {self._averaging}")

                    coefs = self._dh.processBatch(frames.astype(np.float32), batchCount=1, AvgCount=num_frames, CalculateMetrics=False, makeBufferCopy = COPY_CAMERA_BUFFER_FRAMES)
                    self.coefs = coefs

                    if self._callback:
                        self._callback(coefs)

                    self._loop_etime = perf_counter() - _t0
                    self.processing_frame_rate = 1 / self._loop_etime

                    _time_to_sleep = self._loop_period - self._loop_etime
                    if _time_to_sleep > 0:
                        sleep(_time_to_sleep)

                    self.grabbing_frame_rate = 1 / (self._loop_etime + _time_to_sleep)

                except Exception as e:
                    print(f"[DigHoloFeeder] Error: {e}")
                    self._error_message = e
                    sleep(1) #sleep for one second to avoid flooding the error message

    def get_processing_stats(self):
        """
        Returns:   Tuple of processing frame rate in fps and loop rate in fps (this the one asked by the user).
        The processing frame rate is the how many frames could potentially be processed per second.
        The loop rate is the actual frame rate at which the loop is running.
        """
        return self.processing_frame_rate, self.grabbing_frame_rate
    
    def get_coefs(self):
        return self.coefs

    def kill(self):
        if self.is_alive() and not self._kill_tread:
            self.pause_event.set()
            self._kill_tread = True
            self.join()
        else:
            raise RuntimeError("Thread is not alive")

    def pause(self):
        if self.is_alive() and not self._kill_tread:
            self.pause_event.set()

    def resume(self):
        if self.is_alive() and not self._kill_tread:
            self.pause_event.clear()

