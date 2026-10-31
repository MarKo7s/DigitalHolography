# Ok so my philosophy here is that the python functions I have written are same name as the C function version but the digHolo part
# of the name has a underscore (_) after it to let me and anyone else going through the code to see the differences between Joels
# C lib and my python wrapper

import copy
import ctypes
from enum import IntEnum
import json
import logging
from pathlib import Path

from threading import Lock


log = logging.getLogger("digHolo")

import scipy.io
# import matplotlib.pyplot as plt
import numpy as np
# dh_dll as in header file for python... pretty clever I know (Daniel 2 seconds after writing this comment. Head slap you are a idiot )
# Ok so I found a lib called ctypesgen that can look at a header file and make a python wrapper that can also include all the error
# stuff so i have generated the python version of the header file with that. I need to test it to see how it goes.
from . import digholoHeader as dh_dll
from . import digholoResults as results
from . import digholoUtilities as utilities
from .digholoLogger import ConsoleLogger
from .digholoProperties import Properties
from .digholoStreamer import DigHoloFeeder

class digholoMetrics(IntEnum):
    # COUNT = dh_dll.DIGHOLO_METRIC_COUNT           # just len(digholoMetrics)
    IL = dh_dll.DIGHOLO_METRIC_IL                   # insertion loss
    MDL = dh_dll.DIGHOLO_METRIC_MDL                 # mode dependent loss (a.k.a matrix condition number)
    DIAG = dh_dll.DIGHOLO_METRIC_DIAG               # the total power along the diagonal of the transfer matrix
    SNRAVG = dh_dll.DIGHOLO_METRIC_SNRAVG           # the total power along the diagonal/total power off-diagonal
    DIAGBEST = dh_dll.DIGHOLO_METRIC_DIAGBEST       # the diagonal element with the most power
    DIAGWORST = dh_dll.DIGHOLO_METRIC_DIAGWORST     # the diagonal element with the worst power
    SNRBEST= dh_dll.DIGHOLO_METRIC_SNRBEST          # the diagonal/off-diagonal power of the best batch element
    SNRWORST= dh_dll.DIGHOLO_METRIC_SNRWORST        # the diagonal/off-diagonal power of the worst batch element
    SNRMG= dh_dll.DIGHOLO_METRIC_SNRMG              # degenerate mode group signal to noise

CONSOLE_FILENAME = "digHoloConsole.txt"

class DigHolo:
    dll = dh_dll
    metricsenum = digholoMetrics
    @staticmethod
    def default_properties():
        return Properties.defaults()

    def __init__(self, consoleRedirectToFile=True, **kwargs):
        """
        Initializes the digholoObject with optional properties.
        To make it easier TM methods and properties were removed
        Args:
            consoleRedirectToFile:
            **kwargs:

        Accepted kwargs (default_properties):

            Wavelength: float (default 1300e-9)
            WavelengthCount: int (default 1)
            polCount: int (default 2)
            batchCount: int (default 1)
            AvgCount: int (default 1)
            PixelSize: float (default 20e-6)
            maxMG: int (default 22)
            fftWindowSizeX: int (default 256)
            fftWindowSizeY: int (default 256)
            FFTRadius: float (default 0.4)
            BeamCentreXPolH: int (default 0)
            BeamCentreXPolV: int (default 0)
            BeamCentreYPolH: int (default 0)
            BeamCentreYPolV: int (default 0)
            BasisWaistPolH: float (default 1)
            BasisWaistPolV: float (default 1)
            DefocusPolH: float (default 0)
            DefocusPolV: float (default 0)
            XTiltPolH: float (default 0)
            XTiltPolV: float (default 0)
            YTiltPolH: float (default 0)
            YTiltPolV: float (default 0)
            AutoAlignBeamCentre: int (default 1)
            AutoAlignDefocus: int (default 1)
            AutoAlignTilt: int (default 1)
            AutoAlignBasisWaist: int (default 1)
            AutoAlignFourierWindowRadius: float (default 1)
            goalIdx: int (default 0)
            basisType: int (default 1)
            resolutionMode: int (default 1)
            verbosity: int (default 2)
        """
        self._handleIdx = dh_dll.digHoloCreate()
        self._thread_feeder = None
        self.props = Properties()
        self._properties = self.props.as_dict()
        self._batch_frame_buffer_ptr = None
        self._process_grab_lock = Lock()
        self.setProps(**kwargs)  # update self._properties and digholo.dll setProps

        if consoleRedirectToFile:
            charPtr = ctypes.c_char_p(CONSOLE_FILENAME.encode('utf-8'))
            dh_dll.digHoloConsoleRedirectToFile(charPtr)

    def __del__(self):
        """Destructor to destory the digital holograph object."""
        error=dh_dll.digHoloDestroy(self._handleIdx)
        if error==0:
            print("DigHolo has been destroyed")
        else:
            print("problems destroying DigHolo Error code: ", error)
            

    def setProps(self, **kwargs):
        """
        Validates and updates holography properties.

        Raises:
            ValueError: If any keys in kwargs are not valid properties.
        """

        self.props.update(**kwargs)
        self.props.apply(dh_dll, self._handleIdx)


    def getProps(self, print_it=False):
        """
        Reads the current settings from the digHolo library into self._properties,
        then returns that dictionary.
        """

        self.props.read(dh_dll, self._handleIdx)

        if print_it:
            self.printProps(self.props.as_dict())

        return self.props.as_dict()

    def printProps(self, props=None):
        if not props:
            self.getProps(print_it=True)
            return  # getprops print automatically
        print(f"{'Property':<30} Value")
        print("-" * 40)
        for prop_name, value in props.items():
            print(f"{prop_name:<30} {value}")


    def setRefCalibrationIntensity(self, cal):
        calPtr = cal.ctypes.data_as(ctypes.POINTER(ctypes.c_ushort))
        wavelengthCount, width, height = self.props.get_calibration_frame()

        dh_dll.digHoloConfigSetRefCalibrationIntensity(self._handleIdx, calPtr, wavelengthCount, width, height)

    def setBatchCalibration(self, cal_array, polCount=1, batchCount=None):
        cal_array = np.atleast_2d(cal_array)   # shape (1, batchcount)
        if batchCount is None:
            batchCount = self.props.get_batch_count()

        if cal_array.shape != (polCount, batchCount):
            raise ValueError("Invalid shape for batch calibration, has to be polCount x batchCount")


        #todo: using unified staticmethod interleave complex to float

        # Ensure complex numbers are split into float32 pairs
        if np.iscomplexobj(cal_array):
            float_view = np.column_stack([cal_array.real, cal_array.imag]).astype(np.float32)
        else:
            float_view = np.asarray(cal_array, dtype=np.float32)

            # if it was already float, reshape to match complex-as-2-float convention
            if float_view.ndim == 2:
                float_view = float_view[..., np.newaxis]  # (polCount, batchCount, 1)
            if float_view.shape[-1] == 1:
                float_view = np.concatenate([float_view, np.zeros_like(float_view)], axis=-1)

        # Make contiguous and flatten
        float_view = np.ascontiguousarray(float_view, dtype=np.float32)
        flat_array = float_view.ravel()
        cal_ptr = flat_array.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        dh_dll.digHoloConfigSetBatchCalibration(self._handleIdx, cal_ptr, polCount, batchCount)

    def setBatchCalibrationEnabled(self, enabled=True):
        dh_dll.digHoloConfigSetBatchCalibrationEnabled(self._handleIdx, enabled)

    def getBatchCalibrationEnabled(self):
        return dh_dll.digHoloConfigGetBatchCalibrationEnabled(self._handleIdx)

    def setAutoAlignPolIndependence(self, independence=True):
        self.dll.digHoloConfigSetAutoAlignPolIndependence(self._handleIdx, independence)
        return self.getAutoAlignPolIndependence()

    def getAutoAlignPolIndependence(self):
        return self.dll.digHoloConfigGetAutoAlignPolIndependence(self._handleIdx)

    def autoAlign(self, frameBuffer, batchCount=1, AvgCount=0, AvgMode=dh_dll.DIGHOLO_AVGMODE_SEQUENTIAL):
        """
        Runs the AutoAlign routine that searches for optimal settings [e.g. tilt, defocus, beam centre,
        waist] with respect to the specified goalIdx [e.g. IL, MDL, SNR etc].
        The AutoAlign routine has two parts. A first section which attempts to rapidly estimate
        the parameters (tilt, defocus, beam centre, waist) from scratch, followed by a fine
        alignment tweaking stage. The alignment mode specifies whether to run both stages, or
        just 1 of the stages of auto-alignment.
        Alignment routine assumes that polarisation components are mostly on opposite sides of
        the frame along the x-axis (width), which is typically the widest axis of a camera.
        See digHoloConfigSetAutoAlignMode() for types of AutoAlignment routines. See
        digHoloConfigSetAutoAlignGoalIdx() for types of AutoAlignment goal parameters for
        optimisation.
        Args:
            frameBuffer:
            AverageBatch:
            batchCount:
            AvgCount:
            AvgMode:

        Returns:

        """
        if not self.props.adopt_frame_shape(frameBuffer.shape, batchCount, AvgCount):
            return

        self.props.apply(dh_dll, self._handleIdx)

        frameBufferPtr = frameBuffer.ctypes.data_as(ctypes.POINTER(ctypes.c_float))        
        if AvgCount:
           dh_dll.digHoloSetBatchAvg(self._handleIdx, self.props.get_batch_count(), frameBufferPtr,
                                                            self.props.get_avg_count(), AvgMode)
        else:
            dh_dll.digHoloSetBatch(self._handleIdx, self.props.get_batch_count(), frameBufferPtr)



        dh_dll.digHoloAutoAlign(self._handleIdx)

        # self.processBatch(
        #     frameBuffer,
        #     CalculateMetrics=True,
        #     batchCount=batchCount,
        #     AvgCount=AvgCount,
        #     AvgMode=AvgMode
        # )

        self.getProps()
        # self.SaveBatchFile("Batch", frameBuffer, False)
        
        # Get the Coef matrix and metrics  
        coefs, *_ = self.basisGetCoefs()

        # for metric in digholoMetrics:
        #     metrics_ptr = dh_dll.digHoloAutoAlignGetMetrics(self._handleIdx, metricIdx)
        #     metrics[metricIdx,:] = np.ctypeslib.as_array(metrics_ptr, shape=(int(self._properties["WavelengthCount"])+1,))

        wavelength_count = self.props.get_metric_length()
        metrics = np.array([
            np.ctypeslib.as_array(dh_dll.digHoloAutoAlignGetMetrics(self._handleIdx, i), shape=(wavelength_count,))
            for i in digholoMetrics
        ])

        self.setProps()  # why???
        self.save_properties_to_json("calib_data/dh_backup")

        return coefs, metrics

    # This is if you dont want digiholo to change any of its setting but you want to process some frames
    def processBatch(self, frameBuffer, CalculateMetrics=False, batchCount=1, AvgCount=0, AvgMode=dh_dll.DIGHOLO_AVGMODE_SEQUENTIAL, makeBufferCopy = False):
        """
        Setting the parameters for processing a batch of batchCount frames stored in a float32 frameBuffer the first entry.
        'digHoloSetBatch*()' called before calling digHoloProcessBatch().

        Args:
            frameBuffer:
            CalculateMetrics:
            AverageBatch:
            batchCount:
            AvgCount:
            AvgMode:

        Returns:

        """

        frameBuffer = self._prepare_frame_buffer(frameBuffer)
        self.props.check_batch_shape(frameBuffer.shape, batchCount, AvgCount)
        self.props.apply_batch_counts(dh_dll, self._handleIdx)
        with self._process_grab_lock:
            self._batch_frame_buffer_ptr = frameBuffer.copy() if makeBufferCopy else frameBuffer #Keep pointing to the original frame buffer or copy it
            frameBufferPtr = self._batch_frame_buffer_ptr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            dh_dll.digHoloSetBatch(self._handleIdx, self.props.get_batch_count(), frameBufferPtr)
            if AvgCount>1:
                dh_dll.digHoloSetBatchAvg(self._handleIdx, self.props.get_batch_count(), frameBufferPtr,
                                            self.props.get_avg_count(), AvgMode)
            """
            Processes a batch of frames using the current settings, and returns a modal decomposition of the
            resulting fields.
            """
            # can be replaced by self.basisGetCoefs?
            batchCount_c, polCount_c = self.props.get_batch_and_pol_counts()
            modeCount_c= ctypes.c_int()
            CoefptrOut = dh_dll.digHoloProcessBatch(self._handleIdx,ctypes.byref(batchCount_c),ctypes.byref(modeCount_c),ctypes.byref(polCount_c))


        coefs = np.ctypeslib.as_array(CoefptrOut, shape=(batchCount_c.value,2*modeCount_c.value*polCount_c.value))  # NOTE the 2 is to account for complex values
        coefs = coefs[:,0::2]+1j*coefs[:,1::2]
        
        if CalculateMetrics:
            self.autoAlignCalcMetrics()
            return coefs, self.basisGetMatric()

        return coefs


    def _prepare_frame_buffer(self, frameBuffer):
        """Contiguous float32 crop so H/W are multiples of 16; sync FrameHeight/Width."""
        frameBuffer = np.asarray(frameBuffer)
        cropped = utilities.crop_frames_to_multiple_of_16(frameBuffer)
        h, w = int(cropped.shape[-2]), int(cropped.shape[-1])
        props = self.props.as_dict()
        if props["FrameHeight"] != h or props["FrameWidth"] != w:
            self.setProps(FrameHeight=h, FrameWidth=w)
        if cropped is not frameBuffer and not cropped.flags["C_CONTIGUOUS"]:
            cropped = np.ascontiguousarray(cropped)
        return cropped

    def proccesBatchFrequencySweepLinear(self, frameBuffer, lambdaStart: float, lambdaStop: float, lambdaCount: int, makeBufferCopy = False):
        frameBuffer = self._prepare_frame_buffer(frameBuffer)
        self.props.check_batch_shape(frameBuffer.shape)
        self.props.apply_batch_counts(dh_dll, self._handleIdx)

        with self._process_grab_lock:
            self._batch_frame_buffer_ptr = frameBuffer.copy() if makeBufferCopy else frameBuffer #Keep pointing to the original frame buffer or copy it
            frameBufferPtr = self._batch_frame_buffer_ptr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            dh_dll.digHoloSetBatch(self._handleIdx, self.props.get_batch_count(), frameBufferPtr)


            # proccess batch
            batchCount_c, polCount_c = self.props.get_batch_and_pol_counts()
            modeCount_c = ctypes.c_int()
            CoefptrOut = dh_dll.digHoloProcessBatchFrequencySweepLinear(self._handleIdx,
                                                                ctypes.byref(batchCount_c),ctypes.byref(modeCount_c),ctypes.byref(polCount_c),
                                                                lambdaStart, lambdaStop, lambdaCount
                                                                )
        self.updateWavelenghts()
        coefs = np.ctypeslib.as_array(CoefptrOut, shape=(batchCount_c.value, 2 * modeCount_c.value * polCount_c.value))  # NOTE the 2 is to account for complex values
        coefs = coefs[:, 0::2] + 1j * coefs[:, 1::2]
        return coefs, batchCount_c.value, modeCount_c.value, polCount_c.value

    def setWavelengthOrdering(
            self,
            inoutIdx: dh_dll.DIGHOLO_WAVELENGTHORDER_INPUT | dh_dll.DIGHOLO_WAVELENGTHORDER_OUTPUT,
            ordering: dh_dll.DIGHOLO_WAVELENGTHORDER_FAST | dh_dll.DIGHOLO_WAVELENGTHORDER_SLOW
    ):
        """
        Sets the ordering of wavelength data (Fast vs. slow) for the input frame source, or the
        output fields and coefficients.

        Specifies how data corresponding to wavelength sweeps are organised in memory.
        The user can input frames where adjacent frames in memory are at different wavelengths, or
        the same wavelength. The user can also specify how to arrange the fields and output mode
        basis coefficients.
        For example, the user may want to experimentally capture frames where an input is kept
        constant, and the wavelength of the source is swept (Input = ORDER_FAST), however the
        output reconstructed fields may be desired such that transfer matrices for each wavelength are
        output in continuous blocks of memory (Output = ORDER_SLOW).
        Named 'fast' and 'slow' because the wavelength axis is either the fast changing axis, or the
        slowly changing axis in the data.

        DIGHOLO_WAVELENGTHORDER_INPUT 0
        Input. The ordering of the input frames.

        DIGHOLO_WAVELENGTHORDER_OUTPUT 1
        Output. The ordering of the output fields and modal coefficients.

        DIGHOLO_WAVELENGTHORDER_FAST 0
        Wavelength is the fast changing axis. Data corresponding to different wavelengths is
        adjacent in memory and changes from one element to the next.

        DIGHOLO_WAVELENGTHORDER_SLOW 1
        Wavelength is the slow changing axis. Data corresponding to the same wavelength is
        adjacent in memory. All data for a particular wavelength is continous in memory

        Args:
            inoutIdx:
            ordering:

        Returns:

        """
        return dh_dll.digHoloConfigSetWavelengthOrdering(self._handleIdx, inoutIdx, ordering)

    def getWavelengthOrdering(self, inoutIdx: dh_dll.DIGHOLO_WAVELENGTHORDER_INPUT | dh_dll.DIGHOLO_WAVELENGTHORDER_OUTPUT):
        return dh_dll.digHoloConfigGetWavelengthOrdering(self._handleIdx, inoutIdx)

    def setWavelengthsLinearFrequency(self, wavelengthStart: float, wavelengthStop: float, wavelengthCount: int):
        """
        Sets a wavelength axis that is linear in frequency between wavelengthStart and
        wavelengthStop of length wavelengthCount
        Args:
            wavelengthStart:
            wavelengthStop:
            wavelengthCount:

        Returns:
            errorCode
        """
        dh_dll.digHoloConfigSetWavelengthsLinearFrequency(self._handleIdx, wavelengthStart, wavelengthStop, wavelengthCount)
        return self.updateWavelenghts()

    def setWavelength(self, wavelength):
        self.setProps(Wavelength=wavelength)
        self.setWavelengths([wavelength]) # if sweep before update list

    def setWavelengths(self, wavelengths):
        if isinstance(wavelengths, list):
            wavelengths = np.asarray(wavelengths, dtype=np.float32)
        wavelengthsPtr = wavelengths.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        dh_dll.digHoloConfigSetWavelengths(self._handleIdx, wavelengthsPtr, wavelengths.size)
        return self.updateWavelenghts()

    def getWavelengths(self):
        """
        Returns an array corresponding to the current wavelength axis.
        Note:
            This may only be updated after digital holography processing has been performed
        """
        wavelengthCount_c = ctypes.c_int()
        wavelengths_raw = dh_dll.digHoloConfigGetWavelengths(self._handleIdx, ctypes.byref(wavelengthCount_c))
        wavelengths_out = np.ctypeslib.as_array(wavelengths_raw, shape=(wavelengthCount_c.value,)).copy()
        return self.updateWavelenghts(wavelengths_out)

    def updateWavelenghts(self, wavelengths=None):
        if wavelengths is None:
            return self.getWavelengths()
        else:
            self.props.set_wavelength_axis(wavelengths[0], wavelengths.shape[0])
            return wavelengths

    
    def configSetBasisTypeCustom(self, transformMatrix):
        # self._properties["basisType"] = 2  # 2 - custom
        self.setProps(basisType=self.dll.DIGHOLO_BASISTYPE_CUSTOM)  # int 2
        TransformMatrix_dims = transformMatrix.shape
        modeCountIn=TransformMatrix_dims[0]
        modeCountOut=TransformMatrix_dims[1]

        transformMatrix_as_float = self.interleave_complex64_to_float32(transformMatrix)

        transformMatrixPtr = transformMatrix_as_float.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        error=dh_dll.digHoloConfigSetBasisTypeCustom (self._handleIdx,  modeCountIn, modeCountOut,transformMatrixPtr)
        print("return",  error)
        return transformMatrix_as_float
        
    def basisGetCoefs(self):
        """Retrieve the basis coefficients from the DLL as a complex NumPy array."""
        return results.basisGetCoefs(dh_dll, self._handleIdx)

    def autoAlignCalcMetrics(self):
        return dh_dll.digHoloAutoAlignCalcMetrics(self._handleIdx)

    def basisGetMatric(self):
        return results.basisGetMatric(dh_dll, self._handleIdx, self.props.get_metric_length(), digholoMetrics)

    def getFields16(self):
        return results.getFields16(dh_dll, self._handleIdx)
    
    def getFields(self):
        """Reconstructed fields, shape (batchCount, polCount, width, height), complex."""
        return results.getFields(dh_dll, self._handleIdx)


    def basisGetFields(self):
        return results.basisGetFields(dh_dll, self._handleIdx)

    def getViewPort(self, idx: int, forceProcessing=0):
        """RGB bitmap of an internal buffer. idx 0-9 selects the viewport."""
        if idx == 0:
            print("Allowed viewports are: 1-9")
            return None
        #! Protect viewport 1 since it does not copy the frame and some thread could be setting a new processbatch and other trying to read the viewport
        #! No need for lock with the other viewports since they copy the frame and it is handled by C++
        if idx == 1:
            with self._process_grab_lock:
                return results.getViewPort(dh_dll, self._handleIdx, idx, forceProcessing)
        else:
            return results.getViewPort(dh_dll, self._handleIdx, idx, forceProcessing)



    def getFourierPlaneFull(self):
        """Full Fourier plane for each field, complex."""
        return results.getFourierPlaneFull(dh_dll, self._handleIdx)


    def getFourierPlaneWindow(self):
        """Windowed Fourier plane for each field, complex."""
        return results.getFourierPlaneWindow(dh_dll, self._handleIdx)

    def startThread(self, cam, loop_period=0.05, cam_rows_range=(0, 256)):
        if self._thread_feeder is None:
            self._thread_feeder = DigHoloFeeder(cam, self, cam_rows_range=cam_rows_range, loop_period=loop_period)
        else:
            self._thread_feeder.stop()
            self._thread_feeder = DigHoloFeeder(cam, self, cam_rows_range=cam_rows_range, loop_period=loop_period)

    def stopThread(self):
        if self._thread_feeder is not None:
            self._thread_feeder.stop()
            self._thread_feeder = None

    def save_properties_to_json(self, path, print_it=False):
        # Check fitst Path exist otherwise create it
        path = Path(path)
        if path.suffix != ".json":
            path = path.with_suffix(".json")
        path.parent.mkdir(parents=True, exist_ok=True)

        self.getProps(print_it=print_it) # just update to be sure, there are last props from digiHolo
        with open(str(path), 'w') as f:
            json.dump(self.props.as_dict(), f, indent=4)

    def load_properties_from_json(self, path, print_it=True):
        if ".json" not in path:
            path += ".json"
        with open(path, 'r') as f:
            properties = json.load(f)
        self.setProps(**properties)
        return self.getProps(print_it=print_it)


    @staticmethod
    def interleave_complex64_to_float32(matrix):
        return utilities.interleave_complex64_to_float32(matrix)

    @staticmethod
    def mode_group(mode_idx):
        return utilities.mode_group(mode_idx)

    @staticmethod
    def mode_idx(mg):
        return utilities.mode_idx(mg)

    @staticmethod
    def calc_crosstalk(pol_coeffs, return_in_db=False):
        return utilities.calc_crosstalk(pol_coeffs, return_in_db)

    @staticmethod
    def add_mg_strips(coefs_image, max_MG=22, pol_count=2, pol_gap=10):
        return utilities.add_mg_strips(coefs_image, max_MG, pol_count, pol_gap)
