import numpy as np
from scipy.signal import butter, sosfiltfilt, stft, istft
import gc


def remove_watermark(audio, sr, strength=0.6):
    if audio.ndim > 1:
        processed = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            processed[:, ch] = _process_channel(audio[:, ch], sr, strength)
        return processed
    else:
        return _process_channel(audio, sr, strength)


def _process_channel(signal, sr, strength):
    signal = _adaptive_notch_filter(signal, sr, strength)
    signal = _spectral_subtraction(signal, sr, strength)
    signal = _noise_gate(signal, sr, threshold_db=-45)
    return signal


def _adaptive_notch_filter(signal, sr, strength):
    # Bypassed: High-Q notch filters cause severe metallic ringing (alien artifacts)
    return signal


def _spectral_subtraction(signal, sr, strength):
    nperseg = 4096
    noverlap = 3072  # 75% overlap for artifact-free reconstruction

    # MEM FIX: proses di float32/complex64 (bukan float64/complex128).
    # Lagu 4 menit stereo di complex128 bisa >1GB per kanal (STFT + magnitude
    # + phase + salinan) -> MemoryError di Mac yg memorinya terpakai. float32
    # memotong setengah; presisinya setara >24-bit, jauh di atas ambang dengar.
    in_dtype = signal.dtype
    signal32 = np.asarray(signal, dtype=np.float32)

    f, t, Zxx = stft(signal32, sr, nperseg=nperseg, noverlap=noverlap)
    magnitude = np.abs(Zxx)
    phase = np.angle(Zxx)

    import scipy.ndimage
    
    # Smooth magnitude over time to prevent jitter
    mag_smooth = scipy.ndimage.gaussian_filter1d(magnitude, sigma=2, axis=1)

    # Estimate noise floor: 5th percentile over time
    noise_floor = np.percentile(mag_smooth, 5, axis=1, keepdims=True)
    
    # Smooth noise floor over frequency so it doesn't have sharp peaks
    noise_floor = scipy.ndimage.gaussian_filter1d(noise_floor, sigma=4, axis=0)

    # Calculate SNR
    snr = (mag_smooth + 1e-10) / (noise_floor + 1e-10)
    
    # Extremely soft transition mask (Logistic function)
    thresh = 3.0 - (1.5 * strength)
    beta = 1.0 - (0.6 * strength) # Floor: max -8dB reduction to strictly prevent gating artifacts
    
    # k controls the steepness. Lower k = softer transition.
    k = 2.0
    gain = beta + (1.0 - beta) * (1.0 / (1.0 + np.exp(-k * (snr - thresh))))
    
    # MASSIVE smoothing of the gain mask in BOTH frequency and time!
    # This blurs the mask so much that isolated "alien" bins cannot exist.
    gain = scipy.ndimage.gaussian_filter(gain, sigma=(4.0, 8.0))

    Zxx_clean = magnitude * gain * np.exp(1j * phase).astype(np.complex64)
    _, cleaned = istft(Zxx_clean, sr, nperseg=nperseg, noverlap=noverlap)

    gc.collect()
    return cleaned[:len(signal)].astype(in_dtype, copy=False)


def _noise_gate(signal, sr, threshold_db=-45):
    # Vectorized zero-phase envelope extraction
    sq = signal ** 2
    
    import scipy.ndimage
    # Power envelope (50ms window)
    window_samples = int(sr * 0.05)
    power_env = scipy.ndimage.uniform_filter1d(sq, size=window_samples)
    amp_env = np.sqrt(power_env)
    
    # Calculate threshold (linear)
    threshold_amp = 10 ** (threshold_db / 20.0)
    thresh_lower = threshold_amp * 0.5  # -6dB knee
    
    # Create soft mask
    mask = np.clip((amp_env - thresh_lower) / (threshold_amp - thresh_lower + 1e-10), 0.0, 1.0)
    
    # Smooth the mask (Attack/Release ~50ms).
    # PERF FIX: gaussian_filter1d dgn sigma=sr*0.05 (=2205 @44.1k) butuh kernel
    # ~17.000 tap -> puluhan detik per menit audio (aplikasi tampak STUCK).
    # Ganti dgn cascade 3x box filter: hasil smoothing ~identik gaussian
    # (central limit theorem, sigma_eq = w/2 = sr*0.05 — sama spt sebelumnya)
    # tapi O(n), selesai < 1 detik. Karakter attack/release tidak berubah.
    w = max(3, int(sr * 0.10))
    mask_smooth = mask
    for _ in range(3):
        mask_smooth = scipy.ndimage.uniform_filter1d(mask_smooth, size=w)
    
    return signal * mask_smooth


def _smooth_noise_profile(noise_floor, window_size=5):
    from scipy.ndimage import uniform_filter1d
    return uniform_filter1d(noise_floor.astype(float), window_size, axis=0, mode='nearest')
