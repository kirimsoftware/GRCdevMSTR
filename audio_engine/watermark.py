import numpy as np
from scipy.signal import stft, istft, butter, sosfiltfilt
from scipy.ndimage import uniform_filter1d
import gc


def remove_watermark(audio, sr, strength=0.6, progress_callback=None):
    """Bungkus pengaman di sekeliling algoritma asli (repo dasar).

    Algoritma TIDAK diubah. Bungkus ini hanya memastikan master tidak pernah
    jadi senyap: bila hasil proses rusak (NaN/Inf), senyap, atau prosesnya
    gagal (mis. kehabisan memori pada lagu panjang), audio ASLI dikembalikan
    dan alasannya dicatat ke error.log untuk diagnosa.
    """
    try:
        processed = _remove_watermark_core(audio, sr, strength, progress_callback)
        return _sanity_check(audio, processed)
    except Exception as exc:
        _wm_log(f'dibatalkan ({type(exc).__name__}: {exc}); memakai audio asli')
        return audio


def _wm_log(msg):
    try:
        from config import OUTPUT_FOLDER
        import datetime, os as _os
        d = _os.path.dirname(OUTPUT_FOLDER)
        _os.makedirs(d, exist_ok=True)
        with open(_os.path.join(d, 'error.log'), 'a') as f:
            f.write(f'[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] watermark: {msg}\n')
    except Exception:
        pass


def _sanity_check(original, processed):
    o = np.asarray(original)
    p = np.asarray(processed)
    if p.shape != o.shape:
        _wm_log(f'bentuk berubah {o.shape}->{p.shape}; memakai audio asli')
        return original
    if not np.all(np.isfinite(p)):
        _wm_log(f'hasil mengandung {int(np.sum(~np.isfinite(p)))} nilai NaN/Inf; memakai audio asli')
        return original
    rms_o = float(np.sqrt(np.mean(o.astype(np.float64) ** 2)))
    rms_p = float(np.sqrt(np.mean(p.astype(np.float64) ** 2)))
    if rms_o > 1e-9 and rms_p < rms_o * 0.35:
        _wm_log(f'hasil terlalu pelan (RMS {rms_o:.5f} -> {rms_p:.5f}); memakai audio asli')
        return original
    return processed


def _remove_watermark_core(audio, sr, strength=0.6, progress_callback=None):
    if audio.ndim > 1:
        n_ch = audio.shape[1]
        processed = np.zeros_like(audio)
        for ch in range(n_ch):
            processed[:, ch] = _process_channel(audio[:, ch], sr, strength)
            if progress_callback:
                pct = 5 + int((ch + 1) / n_ch * 5)
                progress_callback(pct, f'Watermark ch {ch+1}/{n_ch}')
        return processed
    return _process_channel(audio, sr, strength)


def _process_channel(signal, sr, strength):
    signal = _spectral_subtraction(signal, sr, strength)
    signal = _ultrasonic_suppress(signal, sr, strength)
    signal = _synth_id_defense(signal, sr, strength)
    signal = _noise_gate(signal, sr)
    return signal


def _spectral_subtraction(signal, sr, strength):
    nperseg = 8192
    noverlap = nperseg // 2

    f, t, Zxx = stft(signal, sr, nperseg=nperseg, noverlap=noverlap)
    magnitude = np.abs(Zxx)
    phase = np.angle(Zxx)

    n_freq, n_time = magnitude.shape
    smooth_win = max(3, min(11, n_time // 32))
    if smooth_win % 2 == 0:
        smooth_win += 1
    mag_smooth = uniform_filter1d(magnitude, size=smooth_win, axis=1)

    noise_floor = np.percentile(mag_smooth, 5, axis=1, keepdims=True)

    freq_win = max(3, min(15, n_freq // 16))
    if freq_win % 2 == 0:
        freq_win += 1
    noise_floor = uniform_filter1d(noise_floor.ravel(), size=freq_win).reshape(-1, 1)

    snr = (mag_smooth + 1e-10) / (noise_floor + 1e-10)

    # Frequency-weighted aggression: subtract harder in high freqs where AI
    # watermarks (SynthID pilot tones, Suno artifacts) concentrate.
    freq_bins = np.linspace(0, sr / 2, n_freq)
    hf_weight = np.clip((freq_bins - 6000) / 10000, 0.0, 1.0)  # 0 below 6k, 1 at 16k+
    hf_boost = 1.0 + hf_weight * strength * 0.8

    beta = 1.0 - strength * 0.15
    thresh_val = 3.0 - strength * 1.5

    k = 2.0 * hf_boost[:, np.newaxis]
    thresh = thresh_val + hf_weight[:, np.newaxis] * strength * 0.5
    gain = beta + (1.0 - beta) * (1.0 / (1.0 + np.exp(-k * (snr - thresh))))

    g_freq = max(1, min(5, n_freq // 64))
    g_time = max(1, min(11, n_time // 32))
    gain = uniform_filter1d(gain, size=g_freq, axis=0)
    gain = uniform_filter1d(gain, size=g_time, axis=1)

    Zxx_clean = magnitude * gain * np.exp(1j * phase)
    _, cleaned = istft(Zxx_clean, sr, nperseg=nperseg, noverlap=noverlap)

    gc.collect()
    return cleaned[:len(signal)]


def _ultrasonic_suppress(signal, sr, strength):
    """Strip AI pilot tones typically embedded in the 16–22 kHz band.

    Musical content above ~17 kHz is minimal for most material; watermarks live there.
    We apply a steep lowpass at 17.5 kHz scaled by strength — full cut at strength=1.
    """
    nyq = sr / 2
    cutoff = 17500.0
    if cutoff >= nyq * 0.98:
        return signal

    sos = butter(6, cutoff / nyq, btype='lowpass', output='sos')
    filtered = sosfiltfilt(sos, signal)

    # Blend original ↔ filtered by strength so low-strength preserves air.
    mix = np.clip(strength, 0.0, 1.0)
    return signal * (1.0 - mix) + filtered * mix


def _synth_id_defense(signal, sr, strength):
    """Perturb the STFT phase across the full spectrum to break SynthID-style
    perceptual watermarks that encode identity in phase relationships.

    The perturbation is small (well below JND) but consistent enough to
    disrupt phase-based fingerprint decoders.
    """
    if strength <= 0:
        return signal

    nperseg = 4096
    noverlap = nperseg * 3 // 4

    f, t, Zxx = stft(signal, sr, nperseg=nperseg, noverlap=noverlap)
    mag = np.abs(Zxx)
    phase = np.angle(Zxx)

    n_freq, n_time = mag.shape
    rng = np.random.RandomState(int(sr) ^ n_time)

    # Frequency-dependent jitter — heavier at high freqs, lighter at low freqs
    # (bass phase carries stereo image; don't disturb it).
    freq_bins = np.linspace(0, sr / 2, n_freq)
    freq_weight = np.clip((freq_bins - 800) / 12000, 0.05, 1.0)

    jitter_amp = strength * 0.35 * freq_weight[:, np.newaxis]
    phase_jitter = rng.uniform(-np.pi, np.pi, (n_freq, n_time)) * jitter_amp

    # Smooth the jitter in time so it doesn't produce audible warbling.
    smooth_t = max(3, n_time // 24)
    if smooth_t % 2 == 0:
        smooth_t += 1
    phase_jitter = uniform_filter1d(phase_jitter, size=smooth_t, axis=1)

    Zxx_pert = mag * np.exp(1j * (phase + phase_jitter))
    _, out = istft(Zxx_pert, sr, nperseg=nperseg, noverlap=noverlap)

    gc.collect()
    return out[:len(signal)]


def _noise_gate(signal, sr, threshold_db=-45):
    sq = signal ** 2

    win = int(sr * 0.05)
    win = max(3, min(win, len(signal) // 16))
    power_env = uniform_filter1d(sq, size=win)
    amp_env = np.sqrt(np.maximum(power_env, 1e-20))

    threshold_amp = 10 ** (threshold_db / 20.0)
    thresh_lower = threshold_amp * 0.5

    mask = np.clip((amp_env - thresh_lower) / (threshold_amp - thresh_lower + 1e-10), 0.0, 1.0)

    mask_win = max(3, min(int(sr * 0.03), len(mask) // 8))
    mask_smooth = uniform_filter1d(mask, size=mask_win)

    return signal * mask_smooth
