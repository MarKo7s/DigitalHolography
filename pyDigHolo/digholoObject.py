# Ok so my philosophy here is that the python functions I have written are same name as the C function version but the digHolo part
# of the name has a underscore (_) after it to let me and anyone else going through the code to see the differences between Joels
# C lib and my python wrapper

import copy
import ctypes
from enum import IntEnum
import json
import logging


log = logging.getLogger("digHolo")

import scipy.io
# import matplotlib.pyplot as plt
import numpy as np
# dh_dll as in header file for python... pretty clever I know (Daniel 2 seconds after writing this comment. Head slap you are a idiot )
# Ok so I found a lib called ctypesgen that can look at a header file and make a python wrapper that can also include all the error
# stuff so i have generated the python version of the header file with that. I need to test it to see how it goes.
from . import digholoHeader as dh_dll

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
        return {
            "Wavelength": 1300e-9,
            "WavelengthCount": 1, # i am a little surprise at this but there is no built in function that set the wavelength count it is set when and if you have a array of wavelength to go over.
            "polCount": 2,
            "batchCount": 1,
            "AvgCount": 1,
            "PixelSize": 20e-6,
            "maxMG": 22,
            "FrameWidth": 256, # automatically set during autoalign
            "FrameHeight": 256, # automatically set during autoalign
            "fftWindowSizeX": 256,
            "fftWindowSizeY": 256,
            "FFTRadius": 0.4,
            "BeamCentreXPolH": 0,
            "BeamCentreXPolV": 0,
            "BeamCentreYPolH": 0,
            "BeamCentreYPolV": 0,
            "BasisWaistPolH": 1,
            "BasisWaistPolV": 1,
            "DefocusPolH": 0,
            "DefocusPolV": 0,
            "XTiltPolH": 0,
            "XTiltPolV": 0,
            "YTiltPolH": 0,
            "YTiltPolV": 0,
            "AutoAlignBeamCentre": 1,
            "AutoAlignDefocus": 1,
            "AutoAlignTilt": 1,
            "AutoAlignBasisWaist": 1,
            "AutoAlignFourierWindowRadius": 1,
            "goalIdx": digholoMetrics.IL,
            "basisType": 1,
            "resolutionMode": 1,  ## same resolution as FFT input or native one after aperture cropping
            "verbosity": 2,
        }

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
        self._properties = DigHolo.default_properties()  # default
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

        # Check for unknown keys
        unknown_keys = set(kwargs.keys()) - set(self._properties.keys())
        if unknown_keys:
            log.warning(f"Unknown digholoProperties keys: {unknown_keys}")
            for key in unknown_keys:
                kwargs.pop(key)
            # raise ValueError(f"Unknown digholoProperties keys: {unknown_keys}")

        self._properties.update(kwargs) # just internal update of dictionary

        # # just for TM?
        # goalIdx= self._properties["goalIdx"]
        # if goalIdx<0 or goalIdx>7:
        #     goalIdx =0
        #     print("Invaild goalIdx must be 0=>goalIdx<=7. goalIdx has been set to 0")
        # basisType = self._properties["basisType"]
        # if basisType<0 or basisType>2:
        #     basisType =0
        #     print("Invaild basisType must be 0=>basisType<=2. basisType has been set to 0")

        dh_dll.digHoloConfigSetAutoAlignGoalIdx(self._handleIdx, self._properties["goalIdx"])
        dh_dll.digHoloConfigSetBasisType(self._handleIdx, self._properties["basisType"])

        dh_dll.digHoloConfigSetFrameDimensions(self._handleIdx, self._properties["FrameWidth"], self._properties["FrameHeight"])

        dh_dll.digHoloConfigSetFramePixelSize(self._handleIdx, self._properties["PixelSize"])
        dh_dll.digHoloConfigSetBatchCount(self._handleIdx, self._properties["batchCount"])
        dh_dll.digHoloConfigSetBatchAvgCount(self._handleIdx, self._properties["AvgCount"])

        
        dh_dll.digHoloConfigSetWavelengthCentre(self._handleIdx, self._properties["Wavelength"])
        dh_dll.digHoloConfigSetPolCount(self._handleIdx, self._properties["polCount"])
           
        dh_dll.digHoloConfigSetBasisGroupCount(self._handleIdx, self._properties["maxMG"])
        

        dh_dll.digHoloConfigSetfftWindowSizeX(self._handleIdx, self._properties["fftWindowSizeX"])
        dh_dll.digHoloConfigSetfftWindowSizeY(self._handleIdx, self._properties["fftWindowSizeY"])
    
        dh_dll.digHoloConfigSetFourierWindowRadius(self._handleIdx, self._properties["FFTRadius"])
        dh_dll.digHoloConfigSetIFFTResolutionMode(self._handleIdx, self._properties["resolutionMode"])

        dh_dll.digHoloConfigSetBeamCentre(self._handleIdx, 0, 0, self._properties["BeamCentreXPolH"])
        dh_dll.digHoloConfigSetBeamCentre(self._handleIdx, 0, 1, self._properties["BeamCentreXPolV"])
        dh_dll.digHoloConfigSetBeamCentre(self._handleIdx, 1, 0, self._properties["BeamCentreYPolH"])
        dh_dll.digHoloConfigSetBeamCentre(self._handleIdx, 1, 1, self._properties["BeamCentreYPolV"])
        
        dh_dll.digHoloConfigSetBasisWaist(self._handleIdx, 0, self._properties["BasisWaistPolH"])
        dh_dll.digHoloConfigSetBasisWaist(self._handleIdx, 1, self._properties["BasisWaistPolV"])
        
        dh_dll.digHoloConfigSetDefocus(self._handleIdx, 0, self._properties["DefocusPolH"])
        dh_dll.digHoloConfigSetDefocus(self._handleIdx, 1, self._properties["DefocusPolV"])
        
        dh_dll.digHoloConfigSetTilt(self._handleIdx, 0, 0, self._properties["XTiltPolH"])
        dh_dll.digHoloConfigSetTilt(self._handleIdx, 0, 1, self._properties["XTiltPolV"])
        dh_dll.digHoloConfigSetTilt(self._handleIdx, 1, 0, self._properties["YTiltPolH"])
        dh_dll.digHoloConfigSetTilt(self._handleIdx, 1, 1, self._properties["YTiltPolV"])


        AutoAlignBeamCentre = int(self._properties["AutoAlignBeamCentre"])
        AutoAlignDefocus = int(self._properties["AutoAlignDefocus"])
        AutoAlignTilt = int(self._properties["AutoAlignTilt"])
        AutoAlignBasisWaist = int(self._properties["AutoAlignBasisWaist"])
        AutoAlignFourierWindowRadius = int(self._properties["AutoAlignFourierWindowRadius"])

        dh_dll.digHoloConfigSetAutoAlignBeamCentre(self._handleIdx, AutoAlignBeamCentre)
        dh_dll.digHoloConfigSetAutoAlignDefocus(self._handleIdx, AutoAlignDefocus)
        dh_dll.digHoloConfigSetAutoAlignTilt(self._handleIdx, AutoAlignTilt)
        dh_dll.digHoloConfigSetAutoAlignBasisWaist(self._handleIdx, AutoAlignBasisWaist)
        dh_dll.digHoloConfigSetAutoAlignFourierWindowRadius(self._handleIdx, AutoAlignFourierWindowRadius)

        dh_dll.digHoloConfigSetVerbosity(self._handleIdx, self._properties["verbosity"])


    def getProps(self, print_it=False):
        """
        Reads the current settings from the digHolo library into self._properties,
        then returns that dictionary.
        """

        # todo: update frame dimensions?

        self._properties["Wavelength"] = dh_dll.digHoloConfigGetWavelengthCentre(self._handleIdx)
        # self._properties["WavelengthOrdering"] = dh_dll.digHoloConfigGetWavelengthOrdering(self._handleIdx)

        self._properties["polCount"]   = int(dh_dll.digHoloConfigGetPolCount(self._handleIdx))
        self._properties["maxMG"]      = int(dh_dll.digHoloConfigGetBasisGroupCount(self._handleIdx))
        self._properties["batchCount"] = int(dh_dll.digHoloConfigGetBatchCount(self._handleIdx))
        self._properties["AvgCount"]   = int(dh_dll.digHoloConfigGetBatchAvgCount(self._handleIdx))

 
        self._properties["fftWindowSizeY"] = dh_dll.digHoloConfigGetfftWindowSizeY(self._handleIdx)
        self._properties["fftWindowSizeX"] = dh_dll.digHoloConfigGetfftWindowSizeX(self._handleIdx)

        self._properties["FFTRadius"]      = dh_dll.digHoloConfigGetFourierWindowRadius(self._handleIdx)
        self._properties["resolutionMode"] = dh_dll.digHoloConfigGetIFFTResolutionMode(self._handleIdx)
        
        self._properties["BeamCentreXPolH"] = dh_dll.digHoloConfigGetBeamCentre(self._handleIdx, 0, 0)
        self._properties["BeamCentreXPolV"] = dh_dll.digHoloConfigGetBeamCentre(self._handleIdx, 0, 1)
        self._properties["BeamCentreYPolH"] = dh_dll.digHoloConfigGetBeamCentre(self._handleIdx, 1, 0)
        self._properties["BeamCentreYPolV"] = dh_dll.digHoloConfigGetBeamCentre(self._handleIdx, 1, 1)
        
        self._properties["BasisWaistPolH"] = dh_dll.digHoloConfigGetBasisWaist(self._handleIdx, 0)
        self._properties["BasisWaistPolV"] = dh_dll.digHoloConfigGetBasisWaist(self._handleIdx, 1)
        
        self._properties["DefocusPolH"] = dh_dll.digHoloConfigGetDefocus(self._handleIdx, 0)
        self._properties["DefocusPolV"] = dh_dll.digHoloConfigGetDefocus(self._handleIdx, 1)

        self._properties["XTiltPolH"] = dh_dll.digHoloConfigGetTilt(self._handleIdx, 0, 0)
        self._properties["XTiltPolV"] = dh_dll.digHoloConfigGetTilt(self._handleIdx, 0, 1)
        
        self._properties["YTiltPolH"] = dh_dll.digHoloConfigGetTilt(self._handleIdx, 1, 0)
        self._properties["YTiltPolV"] = dh_dll.digHoloConfigGetTilt(self._handleIdx, 1, 1)

        self._properties["AutoAlignBeamCentre"]         = dh_dll.digHoloConfigGetAutoAlignBeamCentre(self._handleIdx)
        self._properties["AutoAlignDefocus"]            = dh_dll.digHoloConfigGetAutoAlignDefocus(self._handleIdx)
        self._properties["AutoAlignTilt"]               = dh_dll.digHoloConfigGetAutoAlignTilt(self._handleIdx)
        self._properties["AutoAlignBasisWaist"]         = dh_dll.digHoloConfigGetAutoAlignBasisWaist(self._handleIdx)
        self._properties["AutoAlignFourierWindowRadius"] = dh_dll.digHoloConfigGetAutoAlignFourierWindowRadius(self._handleIdx)

        self._properties["goalIdx"] = dh_dll.digHoloConfigGetAutoAlignGoalIdx(self._handleIdx)
        self._properties["basisType"] = dh_dll.digHoloConfigGetBasisType(self._handleIdx)

        if print_it:
            self.printProps(self._properties)

        return self._properties

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
        wavelengthCount = self._properties["WavelengthCount"]
        width = self._properties["FrameWidth"]
        height = self._properties["FrameHeight"]

        dh_dll.digHoloConfigSetRefCalibrationIntensity(self._handleIdx, calPtr, wavelengthCount, width, height)

    def setBatchCalibration(self, cal_array, polCount=1, batchCount=None):
        cal_array = np.atleast_2d(cal_array)   # shape (1, batchcount)
        if batchCount is None:
            batchCount = self._properties["BatchCount"]

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
        shape=frameBuffer.shape
        if len(shape)==2:
            self._properties["batchCount"]=1
            # self._properties["maxMG"]=1
            self._properties["FrameWidth"]=int(shape[1])
            self._properties["FrameHeight"]=int(shape[0])

        elif len(shape)==3:
            if not AvgCount:
                self._properties["batchCount"]=shape[0]
            else: 
                self._properties["batchCount"]=batchCount
                self._properties["AvgCount"]=AvgCount
            self._properties["FrameWidth"]=shape[2]
            self._properties["FrameHeight"]=shape[1]
        else:
            print("AutoAlign NOT run.\n The Camera frames that you have passed are not the correct dims. They should be [batchCount,CamHieght,CamWidth].")
            return

        self.setProps() # update changed properties

        frameBufferPtr = frameBuffer.ctypes.data_as(ctypes.POINTER(ctypes.c_float))        
        if AvgCount:
           dh_dll.digHoloSetBatchAvg(self._handleIdx, int(self._properties["batchCount"]), frameBufferPtr,
                                                            self._properties["AvgCount"], AvgMode)
        else:
            dh_dll.digHoloSetBatch(self._handleIdx,int(self._properties["batchCount"]),frameBufferPtr)



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

        wavelength_count = self._properties["WavelengthCount"] + 1
        metrics = np.array([
            np.ctypeslib.as_array(dh_dll.digHoloAutoAlignGetMetrics(self._handleIdx, i), shape=(wavelength_count,))
            for i in digholoMetrics
        ])

        self.setProps()  # why???
        self.save_properties_to_json("calib_data/dh_backup")

        return coefs, metrics

    # This is if you dont want digiholo to change any of its setting but you want to process some frames
    def processBatch(self, frameBuffer, CalculateMetrics=False, batchCount=1, AvgCount=0, AvgMode=dh_dll.DIGHOLO_AVGMODE_SEQUENTIAL):
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

        shape=frameBuffer.shape
        if self._properties["FrameWidth"] != shape[-1] or self._properties["FrameHeight"] != shape[-2]:
            raise ValueError(f"Buffer shape {shape} does not fit with digHoloFrame {self._properties['FrameHeight']}x{self._properties['FrameWidth']}")

        if len(shape)==2:
            if self._properties["batchCount"]!=1:
                raise ValueError(f"batchCount is not 1, but buffer shape is 2D")

        elif len(shape)==3:
            if AvgCount>1:
                self._properties["batchCount"]=batchCount
                self._properties["AvgCount"]=AvgCount
            else:
                self._properties["batchCount"]=shape[0]
        else:
            raise ValueError("Invalid shape")

        frameBufferPtr = frameBuffer.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        dh_dll.digHoloSetBatch(self._handleIdx, int(self._properties["batchCount"]), frameBufferPtr)
        if AvgCount>1:
           dh_dll.digHoloSetBatchAvg(self._handleIdx, int(self._properties["batchCount"]), frameBufferPtr,
                                        self._properties["AvgCount"], AvgMode)




        """
        Processes a batch of frames using the current settings, and returns a modal decomposition of the
        resulting fields.
        """
        # can be replaced by self.basisGetCoefs?
        batchCount_c = ctypes.c_int(int(self._properties["batchCount"]))
        polCount_c = ctypes.c_int(self._properties["polCount"])
        modeCount_c= ctypes.c_int()
        CoefptrOut = dh_dll.digHoloProcessBatch(self._handleIdx,ctypes.byref(batchCount_c),ctypes.byref(modeCount_c),ctypes.byref(polCount_c))


        coefs = np.ctypeslib.as_array(CoefptrOut, shape=(batchCount_c.value,2*modeCount_c.value*polCount_c.value))  # NOTE the 2 is to account for complex values
        coefs = coefs[:,0::2]+1j*coefs[:,1::2]
        
        if CalculateMetrics:
            self.autoAlignCalcMetrics()
            return coefs, self.basisGetMatric()

        return coefs


    def proccesBatchFrequencySweepLinear(self, frameBuffer, lambdaStart: float, lambdaStop: float, lambdaCount: int):
        shape = frameBuffer.shape
        if self._properties["FrameWidth"] != shape[-1] or self._properties["FrameHeight"] != shape[-2]:
            raise ValueError(
                f"Buffer shape {shape} does not fit with digHoloFrame {self._properties['FrameHeight']}x{self._properties['FrameWidth']}")
        if frameBuffer.ndim == 2:
            if self._properties["batchCount"] != 1:
                raise ValueError(f"batchCount is not 1, but buffer shape is 2D")
        elif frameBuffer.ndim == 3:
            self._properties["batchCount"] = shape[0]
        else:
            raise ValueError("Invalid shape")

        frameBufferPtr = frameBuffer.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        dh_dll.digHoloSetBatch(self._handleIdx, int(self._properties["batchCount"]), frameBufferPtr)


        # proccess batch
        batchCount_c = ctypes.c_int(int(self._properties["batchCount"]))
        polCount_c = ctypes.c_int(self._properties["polCount"])
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
            self._properties["Wavelength"] = wavelengths[0]
            self._properties["WavelengthCount"] = wavelengths.shape[0]
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
        """
        Retrieve the basis coefficients from the DLL and convert them to a complex NumPy array.

        The function uses the digHolo DLL to obtain holographic mode coefficients that are returned
        as interleaved real and imaginary float values (i.e., [Re0, Im0, Re1, Im1, ...]).

        It:
        - Calls the DLL to obtain a pointer to the raw coefficient data.
        - Wraps the pointer as a NumPy array with shape (batchCount, 2 * modeCount * polCount).
        - Splits the interleaved array into complex numbers using slicing.

        Returns:
            coefs (np.ndarray): A complex NumPy array of shape (batchCount, modeCount * polCount).
            batchCount (int): Number of batches.
            modeCount (int): Number of modes per polarization.
            polCount (int): Number of polarizations.
        """
        batchCount_c = ctypes.c_int()
        modeCount_c = ctypes.c_int()
        polCount_c = ctypes.c_int()

        CoefptrOut = dh_dll.digHoloBasisGetCoefs(self._handleIdx, ctypes.byref(batchCount_c), ctypes.byref(modeCount_c), ctypes.byref(polCount_c))
        coefs_raw = np.ctypeslib.as_array(CoefptrOut, shape=(batchCount_c.value,2*modeCount_c.value*polCount_c.value))

        # Split interleaved real/imag to complex: real = [::2], imag = [1::2]
        # 0::2 means: start at index 0, take every 2nd element → real part
        # 1::2 means: start at index 1, take every 2nd element → imaginary part
        coefs = coefs_raw[:,0::2] + 1j*coefs_raw[:,1::2]

        return coefs, batchCount_c.value, modeCount_c.value, polCount_c.value

    def autoAlignCalcMetrics(self):
        return dh_dll.digHoloAutoAlignCalcMetrics(self._handleIdx)

    def basisGetMatric(self):
        wavelength_count = self._properties["WavelengthCount"] + 1
        metrics = np.array([
            np.ctypeslib.as_array(
                dh_dll.digHoloAutoAlignGetMetrics(self._handleIdx, i),
                shape=(wavelength_count,)
            )
            for i in digholoMetrics
        ])
        return metrics

    def getFields16(self):
        batchCount_c = ctypes.c_int()
        polCount_c = ctypes.c_int()
        fieldWidth_ptr=ctypes.c_int()
        fieldHeight_ptr=ctypes.c_int()

        fieldR_ptr = ctypes.POINTER(ctypes.c_short)()
        fieldI_ptr = ctypes.POINTER(ctypes.c_short)()
        fieldScale_ptr = ctypes.POINTER(ctypes.c_float)()

        # x and y pointers (if you need the axis arrays too)
        x_ptr = ctypes.POINTER(ctypes.c_float)()
        y_ptr = ctypes.POINTER(ctypes.c_float)()



        dh_dll.digHoloGetFields16(self._handleIdx,
                                    ctypes.byref(batchCount_c),
                                    ctypes.byref(polCount_c),
                                    ctypes.byref(fieldR_ptr),
                                    ctypes.byref(fieldI_ptr),
                                    ctypes.byref(fieldScale_ptr),
                                    ctypes.byref(x_ptr),ctypes.byref(y_ptr),
                                    ctypes.byref(fieldWidth_ptr),ctypes.byref(fieldHeight_ptr))
        
        width= np.int32(fieldWidth_ptr)
        height= np.int32(fieldHeight_ptr)
        
        fieldR = np.ctypeslib.as_array(fieldR_ptr,shape=(batchCount_c.value*polCount_c.value,height,width))
        fieldI = np.ctypeslib.as_array(fieldI_ptr,shape=(batchCount_c.value*polCount_c.value,height,width)) 
        fieldScale = np.ctypeslib.as_array(fieldScale_ptr,shape=(polCount_c.value,batchCount_c.value)) 
        y = np.ctypeslib.as_array(y_ptr,shape=(1,height)) 
        x = np.ctypeslib.as_array(x_ptr,shape=(1,width)) 
        
        return fieldR, fieldI, fieldScale, x, y
    
    def getFields(self):
        """
        Retrieves the reconstructed field(s) from the library.
        Returns:
            fields: A numpy array of shape (batchCount, polCount, width, height)
                    containing complex-valued field data.
        """
        # Prepare pointers/variables to store outputs from the DLL
        batchCount_c = ((ctypes.c_int))()
        polCount_c   = ((ctypes.c_int))()
        w_c          = ((ctypes.c_int))()
        h_c          = ((ctypes.c_int))()

        # x and y pointers (if you need the axis arrays too)
        xPtr = (ctypes.POINTER(ctypes.c_float))()
        yPtr = (ctypes.POINTER(ctypes.c_float))()

        # Call digHoloGetFields
        ptrOut = dh_dll.digHoloGetFields(
            self._handleIdx,
            ctypes.byref(batchCount_c),
            ctypes.byref(polCount_c),
            ctypes.byref(xPtr),ctypes.byref(yPtr),
            ctypes.byref(w_c),ctypes.byref(h_c)
        )

        # Convert to Python ints
        batchCount = batchCount_c.value
        polCount   = polCount_c.value

        w          = w_c.value
        h          = h_c.value

        # Convert the returned pointer into a NumPy array.
        # The library packs real/imag in the last dimension => shape=(batchCount, polCount, w, 2*h).
        raw_fields = np.ctypeslib.as_array(ptrOut, shape=(batchCount, polCount, w, h*2))

        # Convert interleaved [Re,Im] into a single complex array
        fields = raw_fields[:, :, :, 0::2] + 1j * raw_fields[:, :, :, 1::2]

        return fields


    def basisGetFields(self):
        # Prepare pointers/variables to store outputs from the DLL
        batchCount_c = ((ctypes.c_int))()
        polCount_c   = ((ctypes.c_int))()
        w_c          = ((ctypes.c_int))()
        h_c          = ((ctypes.c_int))()

        # x and y pointers (if you need the axis arrays too)
        xPtr = (ctypes.POINTER(ctypes.c_float))()
        yPtr = (ctypes.POINTER(ctypes.c_float))()

        # Call digHoloGetFields
        ptrOut = dh_dll.digHoloBasisGetFields(
            self._handleIdx,
            ctypes.byref(batchCount_c),
            ctypes.byref(polCount_c),
            ctypes.byref(xPtr),ctypes.byref(yPtr),
            ctypes.byref(w_c),ctypes.byref(h_c)
        )

        # Convert to Python ints
        batchCount = batchCount_c.value
        polCount   = polCount_c.value

        w          = w_c.value
        h          = h_c.value

        # Convert the returned pointer into a NumPy array.
        # The library packs real/imag in the last dimension => shape=(batchCount, polCount, w, 2*h).
        raw_fields = np.ctypeslib.as_array(ptrOut, shape=(batchCount, polCount, w, h*2))

        # Convert interleaved [Re,Im] into a single complex array
        fields = raw_fields[:, :, :, 0::2] + 1j * raw_fields[:, :, :, 1::2]

        return fields

    def getViewPort(self, idx: int, forceProcessing=0):
        """
        Visualises internal buffers. Renders an RGB bitmap based on what type of plot you want to see (displayMode).
        • NONE 0
        • CAMERAPLANE 1
        • FOURIERPLANE 2
        • FOURIERPLANEDB 3
        • FOURIERWINDOW 4
        • FOURIERWINDOWABS 5
        • FIELDPLANE 6
        • FIELDPLANEABS 7
        • FIELDPLANEMODE 8
        • COUNT 9
        • NAMELENGTH 1024
        Args:
            idx: 0-9 or 1024 representing viewport mode
            forceProcessing: 0 if you dont want to process and to just take last buffer from last process
        :return:
            viewport: np.array of RGB bitmap
            windowString: list of strings which can
            serve as a window title containing basic information
        """
        if idx not in range(0, 10):
            raise ValueError(f"Viewport index {idx} is not valid")
        windowString = ((ctypes.c_char_p))()
        ViewPortHeight = ctypes.c_int(0)
        ViewPortWidth = ctypes.c_int(0)
        ViewPortPtr = dh_dll.digHoloGetViewport(int(self._handleIdx), idx, forceProcessing,
                                                  ctypes.byref(ViewPortWidth),
                                                  ctypes.byref(ViewPortHeight), ctypes.byref(windowString))
        ViewPortWidth = np.int32(ViewPortWidth)
        ViewPortHeight = np.int32(ViewPortHeight)
        try:
            viewport = np.ctypeslib.as_array(ViewPortPtr, shape=(ViewPortHeight, ViewPortWidth, 3))
            power_str, dimensions_str = str(windowString.value.decode('utf-8')).split('\t')
            unit_name, power_value_str = power_str.split(' : ')
            return viewport.copy(), [unit_name, power_value_str, dimensions_str]
        except:
            log.error(f"The most probably you have not run any frame processing yet")
            return None



    def getFourierPlaneFull(self):
        """
        Retrieves the full Fourier plane for each field.
        Returns:
            fourierPlanes: A numpy array of shape 
                        (batchCount, polCount, FourierHeight, ((FourierWidth//2)+1)*2)
                        containing complex-valued data for the full Fourier plane.
        """
        # Prepare pointers/variables
        batchCount_c = ctypes.c_int()
        polCount_c   = ctypes.c_int()
        FourierWidth_c  = ctypes.c_int()
        FourierHeight_c = ctypes.c_int()

        # Call digHoloGetFourierPlaneFull
        FourierPtrOut = dh_dll.digHoloGetFourierPlaneFull(
            self._handleIdx,
            ctypes.byref(batchCount_c),
            ctypes.byref(polCount_c),
            ctypes.byref(FourierWidth_c),
            ctypes.byref(FourierHeight_c)
        )

        # Convert to Python ints
        batchCount    = batchCount_c.value
        polCount      = polCount_c.value
        FourierWidth  = FourierWidth_c.value
        FourierHeight = FourierHeight_c.value

        # Convert pointer to NumPy array
        # The library returns real+imag in last dimension => shape=(..., 2).
        # Typically, shape = (batchCount, polCount, FourierHeight, ((FourierWidth//2)+1)*2).
        raw_fourier = np.ctypeslib.as_array(
            FourierPtrOut,
            shape=(batchCount, polCount, FourierHeight, ((FourierWidth // 2) + 1)*2)
        )

        # Convert interleaved [Re,Im] into complex
        fourierPlanes = raw_fourier[:, :, :, 0::2] + 1j * raw_fourier[:, :, :, 1::2]

        return fourierPlanes


    def getFourierPlaneWindow(self):
        """
        Retrieves the (windowed) Fourier plane for each field.
        Returns:
            fourierPlanesWin: A numpy array of shape 
                            (batchCount, polCount, FourierWidthWindow, FourierHeightWindow)
                            containing complex-valued data for the *windowed* Fourier plane.
        """
        # Prepare pointers/variables
        batchCount_c = ctypes.c_int()
        polCount_c   = ctypes.c_int()
        wWin_c       = ctypes.c_int()
        hWin_c       = ctypes.c_int()

        # Call digHoloGetFourierPlaneWindow
        FourierPtrOut_Win = dh_dll.digHoloGetFourierPlaneWindow(
            self._handleIdx,
            ctypes.byref(batchCount_c),
            ctypes.byref(polCount_c),
            ctypes.byref(wWin_c),
            ctypes.byref(hWin_c)
        )

        # Convert to Python ints
        batchCount = batchCount_c.value
        polCount   = polCount_c.value
        wWin       = wWin_c.value
        hWin       = hWin_c.value

        # Convert pointer to NumPy array
        # Real/imag data interleaved => shape=(batchCount, polCount, wWin, 2*hWin).
        raw_fourier_win = np.ctypeslib.as_array(
            FourierPtrOut_Win,
            shape=(batchCount, polCount, wWin, hWin*2)
        )
        fourierPlanesWin = raw_fourier_win[:, :, :, 0::2] + 1j * raw_fourier_win[:, :, :, 1::2]

        return fourierPlanesWin

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
        if ".json" not in path:
            path += ".json"
        self.getProps(print_it=print_it) # just update to be sure, there are last props from digiHolo
        with open(path, 'w') as f:
            json.dump(self._properties, f, indent=4)

    def load_properties_from_json(self, path, print_it=True):
        if ".json" not in path:
            path += ".json"
        with open(path, 'r') as f:
            properties = json.load(f)
        self.setProps(**properties)
        return self.getProps(print_it=print_it)

    @staticmethod
    def interleave_complex64_to_float32(matrix: np.ndarray) -> np.ndarray:
        """Convert a complex64 matrix to a float32 array with interleaved [real, imag]"""
        # assert matrix.dtype == np.complex64
        # flat = matrix
        interleaved = np.empty((matrix.shape[0], matrix.shape[1]* 2), dtype=np.float32)
        interleaved[:,0::2] = matrix.real
        interleaved[:,1::2] = matrix.imag
        return interleaved

    @staticmethod
    def mode_group(mode_idx):
        # Solve n(n+1)/2 = total_modes → n = floor((-1 + sqrt(1 + 8 * total_modes)) / 2)
        # return int((-1 + np.sqrt(1 + 8 * mode_idx)) // 2)
        return np.floor((-1 + np.sqrt(1 + 8 * mode_idx)) / 2).astype(int)

    @staticmethod
    def mode_idx(mg):
        return mg * (mg + 1) // 2

    @staticmethod
    def calc_crosstalk(pol_coeffs, return_in_db=False):
        """
        Coeffs can be shape (1, N), (N,) or shape (P, N) or (B, N) or shape (B, P, N) (batch).
        Args:
            pol_coeffs: complex coeffs of mode fields for one polarisation
        Returns:
            dict of params, each param is dim=1 if P=1/0 else dim=2 for both pols
        """
        pol_coeffs = np.squeeze(pol_coeffs)  # handles shape (1, N)
        batch1pol = (pol_coeffs.ndim == 2 and pol_coeffs.shape[0] > 2)
        only1pol = pol_coeffs.ndim == 1 or batch1pol

        if pol_coeffs.ndim < 3 or (pol_coeffs.ndim == 3 and pol_coeffs.shape[1] == 2):
            abs_norm_coeffs = np.abs(pol_coeffs) ** 2  # use factor of two?
            if pol_coeffs.ndim == 3 or batch1pol:
                # in case of multiple fields
                abs_norm_coeffs = np.mean(abs_norm_coeffs, axis=0)

            if only1pol:
                abs_norm_coeffs /= np.sum(abs_norm_coeffs)
            else:  # norm along both pols separately
                abs_norm_coeffs /= np.sum(abs_norm_coeffs, axis=1, keepdims=True)

        else:
            raise ValueError(f"Unexpected pol_coeffs shape: {pol_coeffs.shape}")

        max_eff_mode = np.argmax(abs_norm_coeffs, axis=-1)
        if only1pol:
            max_eff_mode_value = abs_norm_coeffs[max_eff_mode]
        else:
            max_eff_mode_value = abs_norm_coeffs[np.arange(abs_norm_coeffs.shape[0]), max_eff_mode]

        max_eff_mg = DigHolo.mode_group(max_eff_mode)
        first_mg_mode = DigHolo.mode_idx(max_eff_mg)
        first_next_mg_mode = DigHolo.mode_idx(max_eff_mg + 1)
        # max_eff_mg_value = np.sum(abs_norm_coeffs[first_mg_mode:first_mg_mode + max_eff_mode + 1])
        if only1pol:
            max_eff_mg_value = np.sum(abs_norm_coeffs[first_mg_mode:first_next_mg_mode])
        else:
            max_eff_mg_value = np.array([
                np.sum(abs_norm_coeffs[0, first_mg_mode[0]:first_next_mg_mode[0]]),
                np.sum(abs_norm_coeffs[1, first_mg_mode[1]:first_next_mg_mode[1]])
            ])

        if return_in_db:
            max_eff_mode_value = 10 * np.log10(max_eff_mode_value / (1 - max_eff_mode_value))
            max_eff_mg_value = 10 * np.log10(max_eff_mg_value / (1 - max_eff_mg_value))
        return max_eff_mode, max_eff_mode_value, max_eff_mg, max_eff_mg_value

    # @staticmethod
    # def calc_crosstalk(pol_coeffs, return_in_db=False):
    #     """
    #     Coeffs can be shape (1, N), (N,) or shape (P, N)
    #     Args:
    #         pol_coeffs: complex coeffs of mode fields for one polarisation
    #     Returns:
    #         dict of params
    #     """
    #     pol_coeffs = np.squeeze(pol_coeffs)  # handles shape (1, N)
    #
    #     if pol_coeffs.ndim < 3:
    #         abs_norm_coeffs = np.abs(pol_coeffs)**2  # use factor of two?
    #         abs_norm_coeffs /= np.sum(abs_norm_coeffs)
    #         if pol_coeffs.ndim == 2:
    #             # in case of multiple fields
    #             abs_norm_coeffs = np.mean(abs_norm_coeffs, axis=0)
    #     else:
    #         raise ValueError(f"Unexpected pol_coeffs shape: {pol_coeffs.shape}")
    #
    #     max_eff_mode = np.argmax(abs_norm_coeffs)
    #     max_eff_mode_value = abs_norm_coeffs[max_eff_mode]
    #
    #     max_eff_mg = DigHolo.mode_group(max_eff_mode)
    #     first_mg_mode = DigHolo.mode_idx(max_eff_mg)
    #     first_next_mg_mode = DigHolo.mode_idx(max_eff_mg + 1)
    #     # max_eff_mg_value = np.sum(abs_norm_coeffs[first_mg_mode:first_mg_mode + max_eff_mode + 1])
    #     max_eff_mg_value = np.sum(abs_norm_coeffs[first_mg_mode:first_next_mg_mode])
    #
    #     if return_in_db:
    #         max_eff_mode_value = 10*np.log10(max_eff_mode_value/(1-max_eff_mode_value))
    #         max_eff_mg_value = 10*np.log10(max_eff_mg_value/(1-max_eff_mg_value))
    #     return max_eff_mode, max_eff_mode_value, max_eff_mg, max_eff_mg_value

    @classmethod
    def add_mg_strips(self, coefs_image:np.array, max_MG:int=22, pol_count:int=2, pol_gap:int=10):
        """
        todo: mode where pol are above each other not left and right
        todo: separation styles, now just dots, adding group number texts above modegroup sectors

        Adding mode group dot strips to coeffs rgb image for better readability
        Args:
            coefs_image: RGB image of the coefficients
            max_MG: corresponding to mode count, use `mode_group` to get it
            pol_count: output of DigHolo dll 1 or 2
            pol_gap: gap in pixel between both pol images

        Returns:

        """
        new_array_length = coefs_image.shape[1] + max_MG * pol_count + pol_gap
        rgb_with_group_strips = np.zeros((coefs_image.shape[0], new_array_length, coefs_image.shape[2]),
                                         dtype=coefs_image.dtype)

        iter_idx = 0
        mode_idx = 0
        for pol in range(pol_count):
            for mg in range(max_MG):
                # generate mg pattern
                # array_size = rgb_ceoffs.shape[0]
                spacing = 2
                # tile_spacing = 4
                # pattern_length = (mg+1) * spacing + tile_spacing
                # pattern = np.zeros(pattern_length, dtype=np.uint8)
                # pattern[1:(mg+1) * spacing:spacing] = 200  # Set '1' every `spacing` steps
                # pattern_n = array_size // pattern_length
                # if pattern_n > 0:
                #     final_pattern = np.tile(pattern, pattern_n)[:, None]
                #     rgb_with_group_strips[:final_pattern.shape[0], iter_idx, :] = final_pattern
                # else:
                rgb_with_group_strips[1::spacing, iter_idx, :] = 200
                iter_idx += 1
                print("skipping")
                for _ in range(mg + 1):
                    rgb_with_group_strips[:, iter_idx, :] = coefs_image[:, mode_idx, :]
                    mode_idx += 1
                    iter_idx += 1
            iter_idx += pol_gap
        return rgb_with_group_strips


import threading
from time import sleep

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

from pathlib import Path

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
        # if dh_dll.digHoloConsoleRedirectToFile(str(self.filename).encode("utf-8")) != 0:
        #     raise RuntimeError("Failed to redirect DLL console output.")
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
