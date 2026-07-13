import numpy as np
from scipy.signal import butter, sosfiltfilt, resample_poly

try:
    from numba import njit
except Exception:  # pragma: no cover - numba ships with librosa, fallback just in case
    def njit(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]
        def _deco(fn):
            return fn
        return _deco


@njit(cache=True)
def _gain_envelope(target_gr, release_coeff):
    """Per-sample limiter gain-reduction envelope.

    Instant attack, exponential release toward unity. Because target_gr already
    includes the current sample's required reduction, gr[i] >= target_gr[i] for
    every sample, which mathematically guarantees the output never exceeds the
    ceiling (no block-interpolation overshoot).
    """
    n = target_gr.shape[0]
    gr = np.empty(n, dtype=np.float64)
    g = 1.0
    for i in range(n):
        t = target_gr[i]
        released = 1.0 + (g - 1.0) * release_coeff
        g = t if t > released else released
        gr[i] = g
    return gr


def _limit(audio, sr, threshold_db, release_ms=15, oversample=4):
    """True-peak-aware brickwall limiter that strictly holds the ceiling.

    Inter-sample peaks are detected by oversampling the signal before computing
    the required gain reduction, so the result respects the ceiling in dBTP, not
    just at sample points.
    """
    ceiling = 10 ** (threshold_db / 20.0)
    release_coeff = float(np.exp(-1.0 / (sr * release_ms / 1000.0)))
    output = np.zeros_like(audio)

    for ch in range(audio.shape[1]):
        x = audio[:, ch]
        n = len(x)
        if n == 0:
            continue

        if oversample > 1:
            up = np.abs(resample_poly(x, oversample, 1))
            up = up[:n * oversample]
            if len(up) < n * oversample:
                up = np.pad(up, (0, n * oversample - len(up)))
            true_peak = up.reshape(n, oversample).max(axis=1)
        else:
            true_peak = np.abs(x)

        # Never under-attenuate the actual sample value
        true_peak = np.maximum(true_peak, np.abs(x))
        target_gr = np.maximum(1.0, true_peak / ceiling)

        gr = _gain_envelope(target_gr.astype(np.float64), release_coeff)
        output[:, ch] = x / gr

    return output


def multiband_compressor(audio, sr, configs=None):
    """configs: list of {'low': cutoff, 'high': cutoff, 'threshold_db': x, 'ratio': y, ...}"""
    if configs is None:
        configs = [
            {'low': 20, 'high': 200, 'threshold_db': -18, 'ratio': 3.0,
             'attack_ms': 10, 'release_ms': 80, 'makeup_db': 0},
            {'low': 200, 'high': 3000, 'threshold_db': -20, 'ratio': 2.5,
             'attack_ms': 8, 'release_ms': 60, 'makeup_db': 0},
            {'low': 3000, 'high': 20000, 'threshold_db': -22, 'ratio': 2.0,
             'attack_ms': 5, 'release_ms': 40, 'makeup_db': 0},
        ]

    processed = np.zeros_like(audio)
    for ch in range(audio.shape[1]):
        signal = audio[:, ch]
        output = np.zeros_like(signal)

        for band in configs:
            band_signal = _bandpass_filter(signal, sr, band['low'], band['high'])
            compressed = _compressor(
                band_signal, sr,
                band['threshold_db'], band['ratio'],
                band['attack_ms'], band['release_ms'],
                band.get('makeup_db', 0)
            )
            output += compressed

        processed[:, ch] = output * 0.8

    return processed


def _bandpass_filter(signal, sr, low, high):
    nyq = sr / 2
    low_norm = max(low / nyq, 0.001)
    high_norm = min(high / nyq, 0.999)
    if high_norm <= low_norm:
        return signal.copy()
    sos = butter(2, [low_norm, high_norm], btype='bandpass', output='sos')
    return sosfiltfilt(sos, signal)


def _compressor(signal, sr, threshold_db, ratio, attack_ms, release_ms, makeup_db):
    threshold_linear = 10 ** (threshold_db / 20)
    attack_coeff = np.exp(-1.0 / (sr * attack_ms / 1000))
    release_coeff = np.exp(-1.0 / (sr * release_ms / 1000))
    makeup_linear = 10 ** (makeup_db / 20)

    envelope = np.abs(signal)
    
    # Fast block-based envelope follower
    block_size = 128
    num_blocks = int(np.ceil(len(envelope) / block_size))
    
    padded_env = np.pad(envelope, (0, num_blocks * block_size - len(envelope)))
    blocks = padded_env.reshape(num_blocks, block_size)
    block_peaks = np.max(blocks, axis=1)
    
    smooth_env = np.zeros(num_blocks)
    env_val = 0.0
    
    for i in range(num_blocks):
        target = block_peaks[i]
        if target > env_val:
            env_val = target + (env_val - target) * (attack_coeff ** block_size)
        else:
            env_val = target + (env_val - target) * (release_coeff ** block_size)
        smooth_env[i] = env_val
        
    x_points = np.arange(num_blocks) * block_size + block_size // 2
    x_target = np.arange(len(envelope))
    smooth_env_full = np.interp(x_target, x_points, smooth_env)

    gain_reduction = np.ones_like(signal)
    over_mask = smooth_env_full > threshold_linear
    gain_reduction[over_mask] = (threshold_linear / smooth_env_full[over_mask]) ** (1.0 - 1.0 / ratio)

    return signal * gain_reduction * makeup_linear


def brickwall_limiter(audio, sr, threshold_db=-1.0, lookahead_ms=5, release_ms=15):
    # lookahead_ms kept for API compatibility; the per-sample envelope uses
    # instant attack and already accounts for the current sample, so no
    # block-interpolation overshoot is possible.
    return _limit(audio, sr, threshold_db, release_ms=release_ms)


def transient_shaper(audio, sr, attack_gain=0, sustain_gain=0, window_ms=10):
    window = int(window_ms * sr / 1000)
    if window < 2:
        window = 2

    attack_linear = 10 ** (attack_gain / 20.0)
    sustain_linear = 10 ** (sustain_gain / 20.0)

    output = np.zeros_like(audio)
    for ch in range(audio.shape[1]):
        signal = audio[:, ch]
        env = np.abs(signal)

        smoothed = np.convolve(env, np.ones(window) / window, mode='same')
        smoothed[smoothed < 1e-10] = 1e-10

        transient_mask = np.minimum(env / smoothed, 1.0)
        sustain_mask = 1.0 - transient_mask

        shaped = signal * (transient_mask * attack_linear + sustain_mask * sustain_linear)
        output[:, ch] = shaped

    return output
