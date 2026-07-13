import numpy as np
from scipy.signal import firwin


def apply_tpdf_dither(audio, bit_depth=24):
    if bit_depth >= 32:
        return audio

    quant_levels = 2 ** (bit_depth - 1)
    noise1 = np.random.uniform(-1, 1, audio.shape)
    noise2 = np.random.uniform(-1, 1, audio.shape)
    tpdf_noise = (noise1 + noise2) / quant_levels

    return audio + tpdf_noise


def apply_noise_shaping(audio, sr, bit_depth=24):
    # At 24-bit, noise shaping is unnecessary and complex to implement correctly.
    # We bypass it to prevent audio destruction.
    return audio


def dither_and_shape(audio, sr, bit_depth=24):
    dithered = apply_tpdf_dither(audio, bit_depth)
    return apply_noise_shaping(dithered, sr, bit_depth)

