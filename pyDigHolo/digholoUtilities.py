import numpy as np


def interleave_complex64_to_float32(matrix: np.ndarray) -> np.ndarray:
    """Convert a complex64 matrix to a float32 array with interleaved [real, imag]"""
    interleaved = np.empty((matrix.shape[0], matrix.shape[1] * 2), dtype=np.float32)
    interleaved[:, 0::2] = matrix.real
    interleaved[:, 1::2] = matrix.imag
    return interleaved


def mode_group(mode_idx):
    # Solve n(n+1)/2 = total_modes → n = floor((-1 + sqrt(1 + 8 * total_modes)) / 2)
    return np.floor((-1 + np.sqrt(1 + 8 * mode_idx)) / 2).astype(int)


def mode_idx(mg):
    return mg * (mg + 1) // 2


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

    max_eff_mg = mode_group(max_eff_mode)
    first_mg_mode = mode_idx(max_eff_mg)
    first_next_mg_mode = mode_idx(max_eff_mg + 1)
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


def add_mg_strips(coefs_image: np.array, max_MG: int = 22, pol_count: int = 2, pol_gap: int = 10):
    """
    Adding mode group dot strips to coeffs rgb image for better readability.
    """
    new_array_length = coefs_image.shape[1] + max_MG * pol_count + pol_gap
    rgb_with_group_strips = np.zeros((coefs_image.shape[0], new_array_length, coefs_image.shape[2]),
                                     dtype=coefs_image.dtype)

    iter_idx = 0
    mode_index = 0
    for pol in range(pol_count):
        for mg in range(max_MG):
            spacing = 2
            rgb_with_group_strips[1::spacing, iter_idx, :] = 200
            iter_idx += 1
            print("skipping")
            for _ in range(mg + 1):
                rgb_with_group_strips[:, iter_idx, :] = coefs_image[:, mode_index, :]
                mode_index += 1
                iter_idx += 1
        iter_idx += pol_gap
    return rgb_with_group_strips
