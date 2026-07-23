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
    signal = _spectral_subtraction_chunked(signal, sr, strength)
    signal = _noise_gate(signal, sr, threshold_db=-45)
    return signal


def _spectral_subtraction_chunked(signal, sr, strength, chunk_sec=45.0):
    """Spectral subtraction per potongan agar MEMORI KONSTAN.

    BUG FIX (lagu jadi senyap): STFT sekaligus untuk lagu panjang membuat
    matriks raksasa (lagu ~4 menit: >0.6GB per kanal sebelum salinan internal
    scipy). Di mesin yang memorinya terpakai, alokasi ini gagal -> hasil nol
    -> master senyap (LUFS -inf). Lagu 3:23 lolos, 3:49 tidak: persis di
    ambang. Dengan chunking, pemakaian memori tidak lagi tergantung durasi.

    Potongan diproses dengan overlap dan disambung memakai crossfade linear
    supaya tidak ada diskontinuitas yang terdengar di titik sambung.
    """
    n = len(signal)
    chunk = int(sr * chunk_sec)
    if n <= chunk:
        return _spectral_subtraction(signal, sr, strength)

    overlap = int(sr * 2.0)          # 2 detik tumpang-tindih untuk crossfade
    out = np.zeros(n, dtype=signal.dtype)
    fade = np.linspace(0.0, 1.0, overlap, dtype=np.float64)

    start = 0
    prev_end = 0
    while start < n:
        end = min(start + chunk, n)
        seg_start = max(0, start - overlap) if start > 0 else 0
        seg = signal[seg_start:end]
        proc = _spectral_subtraction(seg, sr, strength)

        if start == 0:
            out[0:end] = proc[0:end]
        else:
            head = start - seg_start           # panjang bagian overlap di proc
            xf = min(overlap, head, end - start if end > start else 0)
            if xf > 0:
                f = fade[:xf] if xf == overlap else np.linspace(0.0, 1.0, xf)
                a = out[start:start + xf]              # ekor potongan sebelumnya
                b = proc[head:head + xf]               # kepala potongan ini
                out[start:start + xf] = a * (1.0 - f) + b * f
                out[start + xf:end] = proc[head + xf:head + (end - start)]
            else:
                out[start:end] = proc[head:head + (end - start)]
        prev_end = end
        if end >= n:
            break
        start = end
        del seg, proc
        gc.collect()
    return out


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

    # BUG FIX (lagu senyap): threshold TIDAK boleh absolut. Lagu yang di-export
    # pelan (umum pada materi AI) bisa seluruhnya berada di bawah -45dB absolut,
    # sehingga gate menutup SEMUANYA -> output senyap. Buat threshold RELATIF
    # terhadap level lagu: ukur puncak envelope, lalu tempatkan gate jauh di
    # bawahnya. Dengan begini gate hanya menyingkirkan bagian yg benar-benar
    # hening relatif thd lagu, bukan menggate lagu pelan secara keseluruhan.
    ref = np.percentile(amp_env, 95)  # "level lagu" (puncak wajar, tahan outlier)
    if ref < 1e-6:
        return signal  # benar-benar senyap/near-zero: jangan sentuh
    rel_floor_db = -45.0          # bagian >45dB di bawah level lagu dianggap silence
    threshold_amp = ref * (10 ** (rel_floor_db / 20.0))
    thresh_lower = threshold_amp * 0.5  # -6dB knee

    # Create soft mask
    mask = np.clip((amp_env - thresh_lower) / (threshold_amp - thresh_lower + 1e-10), 0.0, 1.0)

    # Smooth the mask (Attack/Release ~50ms).
    # PERF FIX: gaussian sigma=sr*0.05 (=2205 @44.1k) = kernel ~17.000 tap ->
    # puluhan detik per menit audio (aplikasi tampak STUCK). Cascade 3x box
    # filter memberi smoothing ~identik gaussian (central limit) tapi O(n).
    w = max(3, int(sr * 0.10))
    mask_smooth = mask
    for _ in range(3):
        mask_smooth = scipy.ndimage.uniform_filter1d(mask_smooth, size=w)

    return signal * mask_smooth


def _smooth_noise_profile(noise_floor, window_size=5):
    from scipy.ndimage import uniform_filter1d
    return uniform_filter1d(noise_floor.astype(float), window_size, axis=0, mode='nearest')
