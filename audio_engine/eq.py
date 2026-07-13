import numpy as np
from scipy.signal import butter, sosfiltfilt


def apply_parametric_eq(audio, sr, band_gains, q_factor=1.4):
    """band_gains: dict of {frequency_hz: gain_db}"""
    if audio.ndim > 1:
        processed = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            processed[:, ch] = _apply_eq_channel(audio[:, ch], sr, band_gains, q_factor)
        return processed
    return _apply_eq_channel(audio, sr, band_gains, q_factor)


def _apply_eq_channel(signal, sr, band_gains, q_factor):
    output = signal.copy()
    for freq, gain_db in sorted(band_gains.items(), key=lambda kv: int(kv[0])):
        freq = int(freq)
        gain_db = float(gain_db)
        if abs(gain_db) < 0.1 or freq >= sr / 2:
            continue

        w0 = freq / (sr / 2)
        bw = w0 / q_factor

        if gain_db > 0:
            sos = butter(2, [max(0.001, w0 - bw), min(0.999, w0 + bw)],
                         btype='bandpass', output='sos')
            gain_linear = 10 ** (gain_db / 20) - 1.0
            output = output + gain_linear * sosfiltfilt(sos, output)
        else:
            sos = butter(2, [max(0.001, w0 - bw), min(0.999, w0 + bw)],
                         btype='bandstop', output='sos')
            atten_linear = 1.0 - 10 ** (-abs(gain_db) / 20)
            output = output - atten_linear * sosfiltfilt(sos, output)

    return output


def auto_eq_correct(audio, sr, issues):
    gains = {}
    for issue in issues:
        itype = issue.get('type', '')
        if itype == 'muddy':
            gains['250'] = -2.0
            gains['500'] = -1.5
        elif itype == 'harsh':
            gains['2000'] = -2.0
            gains['4000'] = -1.5
        elif itype == 'boomy':
            gains['125'] = -2.5
            gains['250'] = -1.0
        elif itype == 'dull':
            gains['4000'] = 2.0
            gains['8000'] = 2.5
        elif itype == 'lacking_air':
            gains['8000'] = 2.0
            gains['16000'] = 2.0

    if gains:
        return apply_parametric_eq(audio, sr, gains)
    return audio


def apply_low_shelf(audio, sr, freq=80, gain_db=0, q=1.2):
    return apply_parametric_eq(audio, sr, {str(freq): gain_db}, q)


def apply_high_shelf(audio, sr, freq=10000, gain_db=0, q=1.2):
    return apply_parametric_eq(audio, sr, {str(freq): gain_db}, q)


def design_eq_filters(sr, band_frequencies, q=1.4):
    filters = []
    for f0 in band_frequencies:
        if f0 >= sr / 2:
            continue
        filters.append({
            'freq': f0,
            'q': q,
            'w0': f0 / (sr / 2),
        })
    return filters
