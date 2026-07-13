import numpy as np
from scipy.signal import butter, sosfiltfilt
from config import BASS_MONO_FREQ


def stereo_width_processor(audio, sr, width_percent=100):
    if audio.ndim < 2 or audio.shape[1] < 2:
        return audio

    mid = (audio[:, 0] + audio[:, 1]) / 2
    side = (audio[:, 0] - audio[:, 1]) / 2

    factor = width_percent / 100.0 - 1.0
    side = side * (1.0 + factor)

    left = mid + side
    right = mid - side

    peak = max(np.max(np.abs(left)), np.max(np.abs(right)))
    if peak > 0.999:
        left /= peak / 0.999
        right /= peak / 0.999

    return np.column_stack([left, right])


def mid_side_processor(audio, sr, mid_gain_db=0, side_gain_db=0):
    if audio.ndim < 2 or audio.shape[1] < 2:
        return audio

    mid = (audio[:, 0] + audio[:, 1]) / 2
    side = (audio[:, 0] - audio[:, 1]) / 2

    mid = mid * (10 ** (mid_gain_db / 20.0))
    side = side * (10 ** (side_gain_db / 20.0))

    left = mid + side
    right = mid - side

    peak = max(np.max(np.abs(left)), np.max(np.abs(right)))
    if peak > 0.999:
        left /= peak / 0.999
        right /= peak / 0.999

    return np.column_stack([left, right])


def bass_mono_enforce(audio, sr, cutoff=BASS_MONO_FREQ):
    if audio.ndim < 2 or audio.shape[1] < 2:
        return audio

    left = audio[:, 0]
    right = audio[:, 1]

    nyq = sr / 2
    sos_low = butter(2, cutoff / nyq, btype='lowpass', output='sos')
    sos_high = butter(2, cutoff / nyq, btype='highpass', output='sos')

    left_low = sosfiltfilt(sos_low, left)
    right_low = sosfiltfilt(sos_low, right)
    left_high = sosfiltfilt(sos_high, left)
    right_high = sosfiltfilt(sos_high, right)

    mono_bass = (left_low + right_low) / 2

    left_out = mono_bass + left_high
    right_out = mono_bass + right_high

    return np.column_stack([left_out, right_out])


def phase_correlation_meter(audio, sr):
    if audio.ndim < 2 or audio.shape[1] < 2:
        return {'correlation': 1.0}

    left = audio[:, 0]
    right = audio[:, 1]

    corr = float(np.corrcoef(left, right)[0, 1])

    status = 'in_phase'
    if corr < -0.5:
        status = 'phase_issues'
    elif corr < 0:
        status = 'wide_phase'

    return {
        'correlation': corr,
        'status': status,
    }
