import ctypes
import logging

import numpy as np

log = logging.getLogger("digHolo")


def basisGetCoefs(dll, handle):
    """
    Retrieve the basis coefficients from the DLL and convert them to a complex NumPy array.
    """
    batchCount_c = ctypes.c_int()
    modeCount_c = ctypes.c_int()
    polCount_c = ctypes.c_int()

    CoefptrOut = dll.digHoloBasisGetCoefs(handle, ctypes.byref(batchCount_c), ctypes.byref(modeCount_c), ctypes.byref(polCount_c))
    coefs_raw = np.ctypeslib.as_array(CoefptrOut, shape=(batchCount_c.value, 2 * modeCount_c.value * polCount_c.value))
    coefs = coefs_raw[:, 0::2] + 1j * coefs_raw[:, 1::2]
    return coefs, batchCount_c.value, modeCount_c.value, polCount_c.value


def basisGetMatric(dll, handle, metric_length, metrics):
    return np.array([
        np.ctypeslib.as_array(
            dll.digHoloAutoAlignGetMetrics(handle, i),
            shape=(metric_length,)
        )
        for i in metrics
    ])


def getFields16(dll, handle):
    batchCount_c = ctypes.c_int()
    polCount_c = ctypes.c_int()
    fieldWidth_ptr = ctypes.c_int()
    fieldHeight_ptr = ctypes.c_int()

    fieldR_ptr = ctypes.POINTER(ctypes.c_short)()
    fieldI_ptr = ctypes.POINTER(ctypes.c_short)()
    fieldScale_ptr = ctypes.POINTER(ctypes.c_float)()

    x_ptr = ctypes.POINTER(ctypes.c_float)()
    y_ptr = ctypes.POINTER(ctypes.c_float)()

    dll.digHoloGetFields16(handle,
                           ctypes.byref(batchCount_c),
                           ctypes.byref(polCount_c),
                           ctypes.byref(fieldR_ptr),
                           ctypes.byref(fieldI_ptr),
                           ctypes.byref(fieldScale_ptr),
                           ctypes.byref(x_ptr), ctypes.byref(y_ptr),
                           ctypes.byref(fieldWidth_ptr), ctypes.byref(fieldHeight_ptr))

    width = np.int32(fieldWidth_ptr)
    height = np.int32(fieldHeight_ptr)

    fieldR = np.ctypeslib.as_array(fieldR_ptr, shape=(batchCount_c.value * polCount_c.value, height, width))
    fieldI = np.ctypeslib.as_array(fieldI_ptr, shape=(batchCount_c.value * polCount_c.value, height, width))
    fieldScale = np.ctypeslib.as_array(fieldScale_ptr, shape=(polCount_c.value, batchCount_c.value))
    y = np.ctypeslib.as_array(y_ptr, shape=(1, height))
    x = np.ctypeslib.as_array(x_ptr, shape=(1, width))

    return fieldR, fieldI, fieldScale, x, y


def _complex_fields(ptr_out, batch_count, pol_count, width, height):
    raw_fields = np.ctypeslib.as_array(ptr_out, shape=(batch_count, pol_count, width, height * 2))
    return raw_fields[:, :, :, 0::2] + 1j * raw_fields[:, :, :, 1::2]


def getFields(dll, handle):
    """
    Retrieves the reconstructed field(s) from the library.
    Returns:
        fields: A numpy array of shape (batchCount, polCount, width, height)
                containing complex-valued field data.
    """
    batchCount_c = ctypes.c_int()
    polCount_c = ctypes.c_int()
    w_c = ctypes.c_int()
    h_c = ctypes.c_int()
    xPtr = ctypes.POINTER(ctypes.c_float)()
    yPtr = ctypes.POINTER(ctypes.c_float)()

    ptrOut = dll.digHoloGetFields(
        handle,
        ctypes.byref(batchCount_c),
        ctypes.byref(polCount_c),
        ctypes.byref(xPtr), ctypes.byref(yPtr),
        ctypes.byref(w_c), ctypes.byref(h_c)
    )
    return _complex_fields(ptrOut, batchCount_c.value, polCount_c.value, w_c.value, h_c.value)


def basisGetFields(dll, handle):
    batchCount_c = ctypes.c_int()
    polCount_c = ctypes.c_int()
    w_c = ctypes.c_int()
    h_c = ctypes.c_int()
    xPtr = ctypes.POINTER(ctypes.c_float)()
    yPtr = ctypes.POINTER(ctypes.c_float)()

    ptrOut = dll.digHoloBasisGetFields(
        handle,
        ctypes.byref(batchCount_c),
        ctypes.byref(polCount_c),
        ctypes.byref(xPtr), ctypes.byref(yPtr),
        ctypes.byref(w_c), ctypes.byref(h_c)
    )
    return _complex_fields(ptrOut, batchCount_c.value, polCount_c.value, w_c.value, h_c.value)


def getViewPort(dll, handle, idx: int, forceProcessing=0):
    """
    Visualises internal buffers. Renders an RGB bitmap based on what type of plot you want to see.
    """
    if idx not in range(0, 10):
        raise ValueError(f"Viewport index {idx} is not valid")
    windowString = ctypes.c_char_p()
    ViewPortHeight = ctypes.c_int(0)
    ViewPortWidth = ctypes.c_int(0)
    ViewPortPtr = dll.digHoloGetViewport(int(handle), idx, forceProcessing,
                                         ctypes.byref(ViewPortWidth),
                                         ctypes.byref(ViewPortHeight), ctypes.byref(windowString))
    ViewPortWidth = np.int32(ViewPortWidth)
    ViewPortHeight = np.int32(ViewPortHeight)
    try:
        viewport = np.ctypeslib.as_array(ViewPortPtr, shape=(ViewPortHeight, ViewPortWidth, 3))
        power_str, dimensions_str = str(windowString.value.decode('utf-8')).split('\t')
        unit_name, power_value_str = power_str.split(' : ')
        return viewport.copy(), [unit_name, power_value_str, dimensions_str]
    except Exception:
        log.error("The most probably you have not run any frame processing yet")
        return None


def getFourierPlaneFull(dll, handle):
    """
    Retrieves the full Fourier plane for each field.
    """
    batchCount_c = ctypes.c_int()
    polCount_c = ctypes.c_int()
    FourierWidth_c = ctypes.c_int()
    FourierHeight_c = ctypes.c_int()

    FourierPtrOut = dll.digHoloGetFourierPlaneFull(
        handle,
        ctypes.byref(batchCount_c),
        ctypes.byref(polCount_c),
        ctypes.byref(FourierWidth_c),
        ctypes.byref(FourierHeight_c)
    )

    batchCount = batchCount_c.value
    polCount = polCount_c.value
    FourierWidth = FourierWidth_c.value
    FourierHeight = FourierHeight_c.value

    raw_fourier = np.ctypeslib.as_array(
        FourierPtrOut,
        shape=(batchCount, polCount, FourierHeight, ((FourierWidth // 2) + 1) * 2)
    )
    return raw_fourier[:, :, :, 0::2] + 1j * raw_fourier[:, :, :, 1::2]


def getFourierPlaneWindow(dll, handle):
    """
    Retrieves the windowed Fourier plane for each field.
    """
    batchCount_c = ctypes.c_int()
    polCount_c = ctypes.c_int()
    wWin_c = ctypes.c_int()
    hWin_c = ctypes.c_int()

    FourierPtrOut_Win = dll.digHoloGetFourierPlaneWindow(
        handle,
        ctypes.byref(batchCount_c),
        ctypes.byref(polCount_c),
        ctypes.byref(wWin_c),
        ctypes.byref(hWin_c)
    )

    raw_fourier_win = np.ctypeslib.as_array(
        FourierPtrOut_Win,
        shape=(batchCount_c.value, polCount_c.value, wWin_c.value, hWin_c.value * 2)
    )
    return raw_fourier_win[:, :, :, 0::2] + 1j * raw_fourier_win[:, :, :, 1::2]
