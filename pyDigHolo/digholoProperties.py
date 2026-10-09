"""This is just a inteface for the digHolo properties dictionary """
import ctypes
import logging

from . import digholoHeader as dh_dll

log = logging.getLogger("digHolo")


class Properties:
    """digHolo settings. The live key/value store is ``_data``."""

    def __init__(self):
        self._data = self.defaults()

    @staticmethod
    def defaults():
        return {
            "Wavelength": 1300e-9,
            "WavelengthCount": 1,  # no built-in setter; written when a wavelength array is applied
            "polCount": 2,
            "batchCount": 1,
            "AvgCount": 1,
            "PixelSize": 20e-6,
            "maxMG": 22,
            "FrameWidth": 256,  # automatically set during autoalign
            "FrameHeight": 256,  # automatically set during autoalign
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
            "goalIdx": dh_dll.DIGHOLO_METRIC_IL,
            "basisType": 1,
            "resolutionMode": 1,  # same resolution as FFT input or native one after aperture cropping
            "verbosity": 2,
        }

    def as_dict(self):
        return self._data

    def get_batch_count(self):
        return int(self._data["batchCount"])

    def get_avg_count(self):
        return int(self._data["AvgCount"])

    def get_batch_and_pol_counts(self):
        return (
            ctypes.c_int(int(self._data["batchCount"])),
            ctypes.c_int(int(self._data["polCount"])),
        )

    def get_calibration_frame(self):
        return (
            self._data["WavelengthCount"],
            self._data["FrameWidth"],
            self._data["FrameHeight"],
        )

    def get_metric_length(self):
        return self._data["WavelengthCount"] + 1

    def set_wavelength_axis(self, wavelength, count):
        self._data["Wavelength"] = wavelength
        self._data["WavelengthCount"] = count

    def update(self, **kwargs):
        unknown_keys = set(kwargs.keys()) - set(self._data.keys())
        if unknown_keys:
            log.warning(f"Unknown digholoProperties keys: {unknown_keys}")
            for key in unknown_keys:
                kwargs.pop(key)
        self._data.update(kwargs)

    def apply(self, dll, handle):
        props = self._data
        dll.digHoloConfigSetAutoAlignGoalIdx(handle, props["goalIdx"])
        dll.digHoloConfigSetBasisType(handle, props["basisType"])

        dll.digHoloConfigSetFrameDimensions(handle, props["FrameWidth"], props["FrameHeight"])

        dll.digHoloConfigSetFramePixelSize(handle, props["PixelSize"])
        dll.digHoloConfigSetBatchCount(handle, props["batchCount"])
        dll.digHoloConfigSetBatchAvgCount(handle, props["AvgCount"])

        dll.digHoloConfigSetWavelengthCentre(handle, props["Wavelength"])
        dll.digHoloConfigSetPolCount(handle, props["polCount"])

        dll.digHoloConfigSetBasisGroupCount(handle, props["maxMG"])

        dll.digHoloConfigSetfftWindowSizeX(handle, props["fftWindowSizeX"])
        dll.digHoloConfigSetfftWindowSizeY(handle, props["fftWindowSizeY"])

        dll.digHoloConfigSetFourierWindowRadius(handle, props["FFTRadius"])
        dll.digHoloConfigSetIFFTResolutionMode(handle, props["resolutionMode"])

        dll.digHoloConfigSetBeamCentre(handle, 0, 0, props["BeamCentreXPolH"])
        dll.digHoloConfigSetBeamCentre(handle, 0, 1, props["BeamCentreXPolV"])
        dll.digHoloConfigSetBeamCentre(handle, 1, 0, props["BeamCentreYPolH"])
        dll.digHoloConfigSetBeamCentre(handle, 1, 1, props["BeamCentreYPolV"])

        dll.digHoloConfigSetBasisWaist(handle, 0, props["BasisWaistPolH"])
        dll.digHoloConfigSetBasisWaist(handle, 1, props["BasisWaistPolV"])

        dll.digHoloConfigSetDefocus(handle, 0, props["DefocusPolH"])
        dll.digHoloConfigSetDefocus(handle, 1, props["DefocusPolV"])

        dll.digHoloConfigSetTilt(handle, 0, 0, props["XTiltPolH"])
        dll.digHoloConfigSetTilt(handle, 0, 1, props["XTiltPolV"])
        dll.digHoloConfigSetTilt(handle, 1, 0, props["YTiltPolH"])
        dll.digHoloConfigSetTilt(handle, 1, 1, props["YTiltPolV"])

        dll.digHoloConfigSetAutoAlignBeamCentre(handle, int(props["AutoAlignBeamCentre"]))
        dll.digHoloConfigSetAutoAlignDefocus(handle, int(props["AutoAlignDefocus"]))
        dll.digHoloConfigSetAutoAlignTilt(handle, int(props["AutoAlignTilt"]))
        dll.digHoloConfigSetAutoAlignBasisWaist(handle, int(props["AutoAlignBasisWaist"]))
        dll.digHoloConfigSetAutoAlignFourierWindowRadius(handle, int(props["AutoAlignFourierWindowRadius"]))

        dll.digHoloConfigSetVerbosity(handle, props["verbosity"])

    def apply_batch_counts(self, dll, handle):
        dll.digHoloConfigSetBatchCount(handle, self._data["batchCount"])
        dll.digHoloConfigSetBatchAvgCount(handle, self._data["AvgCount"])

    def read(self, dll, handle):
        """Read DLL settings into the dictionary.

        FrameWidth, FrameHeight, PixelSize, WavelengthCount, and verbosity are left
        as last written. The DLL getters used here do not return them.
        """
        props = self._data
        props["Wavelength"] = dll.digHoloConfigGetWavelengthCentre(handle)

        props["polCount"] = int(dll.digHoloConfigGetPolCount(handle))
        props["maxMG"] = int(dll.digHoloConfigGetBasisGroupCount(handle))
        props["batchCount"] = int(dll.digHoloConfigGetBatchCount(handle))
        props["AvgCount"] = int(dll.digHoloConfigGetBatchAvgCount(handle))

        props["fftWindowSizeY"] = dll.digHoloConfigGetfftWindowSizeY(handle)
        props["fftWindowSizeX"] = dll.digHoloConfigGetfftWindowSizeX(handle)

        props["FFTRadius"] = dll.digHoloConfigGetFourierWindowRadius(handle)
        props["resolutionMode"] = dll.digHoloConfigGetIFFTResolutionMode(handle)

        props["BeamCentreXPolH"] = dll.digHoloConfigGetBeamCentre(handle, 0, 0)
        props["BeamCentreXPolV"] = dll.digHoloConfigGetBeamCentre(handle, 0, 1)
        props["BeamCentreYPolH"] = dll.digHoloConfigGetBeamCentre(handle, 1, 0)
        props["BeamCentreYPolV"] = dll.digHoloConfigGetBeamCentre(handle, 1, 1)

        props["BasisWaistPolH"] = dll.digHoloConfigGetBasisWaist(handle, 0)
        props["BasisWaistPolV"] = dll.digHoloConfigGetBasisWaist(handle, 1)

        props["DefocusPolH"] = dll.digHoloConfigGetDefocus(handle, 0)
        props["DefocusPolV"] = dll.digHoloConfigGetDefocus(handle, 1)

        props["XTiltPolH"] = dll.digHoloConfigGetTilt(handle, 0, 0)
        props["XTiltPolV"] = dll.digHoloConfigGetTilt(handle, 0, 1)

        props["YTiltPolH"] = dll.digHoloConfigGetTilt(handle, 1, 0)
        props["YTiltPolV"] = dll.digHoloConfigGetTilt(handle, 1, 1)

        props["AutoAlignBeamCentre"] = dll.digHoloConfigGetAutoAlignBeamCentre(handle)
        props["AutoAlignDefocus"] = dll.digHoloConfigGetAutoAlignDefocus(handle)
        props["AutoAlignTilt"] = dll.digHoloConfigGetAutoAlignTilt(handle)
        props["AutoAlignBasisWaist"] = dll.digHoloConfigGetAutoAlignBasisWaist(handle)
        props["AutoAlignFourierWindowRadius"] = dll.digHoloConfigGetAutoAlignFourierWindowRadius(handle)

        props["goalIdx"] = dll.digHoloConfigGetAutoAlignGoalIdx(handle)
        props["basisType"] = dll.digHoloConfigGetBasisType(handle)
        return props

    def adopt_frame_shape(self, shape, batch_count=1, avg_count=0):
        """Update width, height, and batch count from an autoAlign buffer.

        Returns False when the rank is not 2 or 3.
        """
        if len(shape) == 2:
            self._data["batchCount"] = 1
            self._data["FrameWidth"] = int(shape[1])
            self._data["FrameHeight"] = int(shape[0])
            return True
        if len(shape) == 3:
            if not avg_count:
                self._data["batchCount"] = shape[0]
            else:
                self._data["batchCount"] = batch_count
                self._data["AvgCount"] = avg_count
            self._data["FrameWidth"] = shape[2]
            self._data["FrameHeight"] = shape[1]
            return True
        print(
            "AutoAlign NOT run.\n The Camera frames that you have passed are not the correct dims. "
            "They should be [batchCount,CamHieght,CamWidth]."
        )
        return False

    def check_batch_shape(self, shape, batch_count=1, avg_count=0):
        """Reject a buffer that does not match the configured frame, then set the batch count."""
        if self._data["FrameWidth"] != shape[-1] or self._data["FrameHeight"] != shape[-2]:
            raise ValueError(
                f"Buffer shape {shape} does not fit with digHoloFrame "
                f"{self._data['FrameHeight']}x{self._data['FrameWidth']}"
            )
        if len(shape) == 2:
            if self._data["batchCount"] != 1:
                raise ValueError("batchCount is not 1, but buffer shape is 2D")
        elif len(shape) == 3:
            if avg_count > 1:
                self._data["batchCount"] = batch_count
                self._data["AvgCount"] = avg_count
            else:
                self._data["batchCount"] = shape[0]
        else:
            raise ValueError("Invalid shape")
