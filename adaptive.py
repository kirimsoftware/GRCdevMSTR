"""
Adaptive Analysis — menurunkan starting point EQ, kompresor multiband,
dan gain staging dari MATERIAL AUDIO ITU SENDIRI, bukan preset rata.

Prinsip:
1. Spektrum lagu diukur (10 band oktaf), dibandingkan dengan kurva target
   genre -> EQ correction per band (dibatasi agar tetap musikal).
2. Crest factor (peak vs RMS) per band frekuensi menentukan threshold &
   ratio kompresor: materi yang sudah padat dikompres ringan, materi
   dinamis diberi kontrol lebih.
3. Level RMS input dibawa ke gain staging sehat (~-18 dBFS) sebelum
   masuk rantai, sehingga kompresor bekerja di titik operasi yang benar.
"""
import numpy as np

EQ_BANDS = [64, 125, 250, 500, 1000, 2000, 4000, 8000, 12000, 16000]

# Kurva target per genre: dB relatif per band (rata-rata = 0).
# Berbasis kurva tonal balance yang lazim untuk rilisan komersial.
GENRE_TARGET_CURVES = {
    'pop':       [ 2.0,  2.5,  1.0,  0.0, -0.5,  0.0,  0.5,  1.0,  1.5,  1.0],
    'rock':      [ 1.0,  2.0,  1.5,  0.5,  0.0,  0.5,  1.0,  1.5,  1.0,  0.0],
    'edm':       [ 3.5,  4.0,  1.5, -0.5, -1.0, -0.5,  0.5,  1.5,  2.5,  2.0],
    'hiphop':    [ 4.0,  4.5,  2.0,  0.0, -1.0, -0.5,  0.0,  1.0,  1.5,  0.5],
    'jazz':      [ 0.5,  1.0,  0.5,  0.0,  0.0,  0.5,  0.5,  0.5,  0.5,  0.0],
    'classical': [ 0.0,  0.5,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.5,  0.5],
}

COMP_BANDS = [(20, 200), (200, 3000), (3000, 20000)]

MAX_EQ_CORRECTION = 3.0     # dB, batas koreksi per band agar tetap musikal
MATCH_STRENGTH = 0.45       # 0..1, seberapa agresif mengejar kurva target
TARGET_RMS_DB = -18.0       # gain staging input yang sehat


def _band_edges(center):
    return center / np.sqrt(2), center * np.sqrt(2)


def _spectrum_db(audio, sr, n_fft=8192):
    """Rata-rata magnitudo spektrum (dB) dengan windowing per segmen."""
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    hop = n_fft // 2
    n_seg = max(1, (len(mono) - n_fft) // hop)
    # sampling maks ~200 segmen agar cepat untuk lagu panjang
    idxs = np.linspace(0, max(0, len(mono) - n_fft), min(n_seg, 200)).astype(int)
    win = np.hanning(n_fft)
    acc = np.zeros(n_fft // 2 + 1)
    for i in idxs:
        seg = mono[i:i + n_fft]
        if len(seg) < n_fft:
            break
        acc += np.abs(np.fft.rfft(seg * win)) ** 2
    acc /= max(1, len(idxs))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    return freqs, 10 * np.log10(acc + 1e-12)


def _measured_curve(audio, sr):
    freqs, spec_db = _spectrum_db(audio, sr)
    curve = []
    for c in EQ_BANDS:
        lo, hi = _band_edges(c)
        mask = (freqs >= lo) & (freqs < hi)
        curve.append(float(spec_db[mask].mean()) if mask.any() else -60.0)
    curve = np.array(curve)
    # Kompensasi slope alami musik (~-4.5 dB/oktaf relatif 1kHz) supaya
    # bass yang secara natural dominan TIDAK dianggap "kelebihan" dan
    # treble yang natural rendah TIDAK dianggap "kurang". Tanpa ini,
    # koreksi EQ jadi ekstrem (bass dipangkas habis, treble diangkat tajam).
    tilt = np.array([np.log2(f / 1000.0) * 4.5 for f in EQ_BANDS])
    curve = curve + tilt
    return curve - curve.mean()          # normalisasi relatif


def _band_signal(audio, sr, lo, hi):
    """Isolasi band frekuensi via FFT masking (cukup akurat untuk metering)."""
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    # analisis pada potongan tengah maks 60 dtk agar cepat
    max_n = sr * 60
    if len(mono) > max_n:
        start = (len(mono) - max_n) // 2
        mono = mono[start:start + max_n]
    spec = np.fft.rfft(mono)
    freqs = np.fft.rfftfreq(len(mono), 1.0 / sr)
    spec[(freqs < lo) | (freqs >= hi)] = 0
    return np.fft.irfft(spec, len(mono))


def derive_adaptive_settings(audio, sr, genre='pop'):
    """Analisis material -> dict settings untuk rantai mastering."""
    target = np.array(GENRE_TARGET_CURVES.get(genre, GENRE_TARGET_CURVES['pop']))
    measured = _measured_curve(audio, sr)

    # --- EQ: koreksi menuju kurva target, dihaluskan antar band ---
    raw = (target - measured) * MATCH_STRENGTH
    smooth = np.convolve(raw, [0.25, 0.5, 0.25], mode='same')
    eq_gains = {str(f): float(np.clip(g, -MAX_EQ_CORRECTION, MAX_EQ_CORRECTION))
                for f, g in zip(EQ_BANDS, smooth)}

    # --- Kompresor: threshold & ratio dari crest factor per band ---
    compressor = []
    for lo, hi in COMP_BANDS:
        band = _band_signal(audio, sr, lo, hi)
        rms = np.sqrt(np.mean(band ** 2)) + 1e-12
        peak = np.max(np.abs(band)) + 1e-12
        rms_db = 20 * np.log10(rms)
        crest = 20 * np.log10(peak) - rms_db

        # Materi dinamis (crest tinggi) -> kontrol lebih; padat -> ringan.
        if crest > 16:
            ratio, thr_off = 3.5, 4.0
        elif crest > 12:
            ratio, thr_off = 2.5, 6.0
        else:
            ratio, thr_off = 1.8, 8.0

        attack = {200: 12, 3000: 8}.get(hi, 4)
        release = {200: 90, 3000: 60}.get(hi, 40)
        compressor.append({
            'low': lo, 'high': hi,
            'threshold_db': float(np.clip(rms_db + thr_off, -40, -3)),
            'ratio': ratio,
            'attack_ms': attack,
            'release_ms': release,
            'makeup_db': 0,
        })

    # --- Gain staging input (lembut) ---
    # Hanya koreksi jika level jauh dari sehat. Untuk materi normal, biarkan
    # netral (0 dB) supaya tidak menggeser titik kerja kompresor & tidak
    # berinteraksi buruk dengan LUFS normalize di akhir rantai.
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    rms_db = 20 * np.log10(np.sqrt(np.mean(mono ** 2)) + 1e-12)
    raw_stage = TARGET_RMS_DB - rms_db
    if abs(raw_stage) < 6.0:
        input_gain_db = 0.0                      # materi normal: jangan diutak-atik
    else:
        # koreksi sebagian saja, dibatasi lembut
        input_gain_db = float(np.clip(raw_stage * 0.5, -6.0, 6.0))

    return {
        'eq_gains': eq_gains,
        'compressor': compressor,
        'input_gain_db': input_gain_db,
        'analysis': {
            'measured_curve': {str(f): round(float(m), 2)
                               for f, m in zip(EQ_BANDS, measured)},
            'input_rms_db': round(rms_db, 2),
        },
    }


def match_reference_eq(source_audio, source_sr, ref_audio, ref_sr):
    """Bandingkan kurva spektrum source vs reference -> koreksi EQ agar
    source mendekati tonal balance reference. Ini 'EQ matching' klasik."""
    src_curve = _measured_curve(source_audio, source_sr)   # relatif (mean 0)
    ref_curve = _measured_curve(ref_audio, ref_sr)         # relatif (mean 0)
    # selisih: ke mana source harus bergerak agar seperti reference
    raw = (ref_curve - src_curve) * MATCH_STRENGTH
    smooth = np.convolve(raw, [0.25, 0.5, 0.25], mode='same')
    eq_gains = {str(f): float(np.clip(g, -MAX_EQ_CORRECTION, MAX_EQ_CORRECTION))
                for f, g in zip(EQ_BANDS, smooth)}
    return {
        'eq_gains': eq_gains,
        'source_curve': {str(f): round(float(v), 2) for f, v in zip(EQ_BANDS, src_curve)},
        'ref_curve': {str(f): round(float(v), 2) for f, v in zip(EQ_BANDS, ref_curve)},
    }


def fine_spectrum(audio, sr, n_bins=96):
    """Spektrum resolusi tinggi (log-spaced) untuk Spectrum Analyzer.
    Mengembalikan list dB per bin dari 20Hz..20kHz (dinormalisasi ke puncak)."""
    freqs, spec_db = _spectrum_db(audio, sr, n_fft=8192)
    f_edges = np.logspace(np.log10(20), np.log10(20000), n_bins + 1)
    out = []
    for i in range(n_bins):
        m = (freqs >= f_edges[i]) & (freqs < f_edges[i + 1])
        out.append(float(spec_db[m].mean()) if m.any() else -120.0)
    out = np.array(out)
    out = out - out.max()          # 0 dB = puncak
    return [round(float(v), 1) for v in out]


# Target Tonal Balance per genre (dBFS RMS per zona: low, low_mid, high_mid, high).
# CATATAN: ini "indicative targets" berbasis prinsip audio engineering yang
# mapan (bukan kurva referensi berlisensi dari database rilisan komersial).
# Berguna sebagai pemandu visual, bukan cetakan mutlak.
GENRE_TONAL_TARGETS = {
    # Frame flat (post-tilt). Nilai = (target_low, target_high) dBFS pada meter.
    # Karakter genre = pergeseran relatif antar zona.
    'edm':       {'low': (-27, -18), 'low_mid': (-30, -21), 'high_mid': (-31, -22), 'high': (-32, -22)},
    'hiphop':    {'low': (-26, -17), 'low_mid': (-30, -21), 'high_mid': (-31, -22), 'high': (-33, -23)},
    'pop':       {'low': (-29, -20), 'low_mid': (-29, -20), 'high_mid': (-30, -21), 'high': (-31, -21)},
    'rock':      {'low': (-30, -21), 'low_mid': (-28, -19), 'high_mid': (-29, -20), 'high': (-31, -22)},
    'jazz':      {'low': (-31, -22), 'low_mid': (-29, -20), 'high_mid': (-30, -21), 'high': (-32, -22)},
    'classical': {'low': (-32, -23), 'low_mid': (-30, -21), 'high_mid': (-31, -22), 'high': (-33, -23)},
}
_DEFAULT_TONAL = {'low': (-29, -20), 'low_mid': (-29, -20), 'high_mid': (-30, -21), 'high': (-31, -21)}


def tonal_zones(audio, sr, genre='pop'):
    """4 zona ala iZotope Tonal Balance: energi RMS (dBFS) + target range
    yang menyesuaikan genre (indicative, lihat GENRE_TONAL_TARGETS)."""
    from scipy.signal import butter, sosfilt
    zones = [('low', 20, 120), ('low_mid', 120, 1000),
             ('high_mid', 1000, 6000), ('high', 6000, 20000)]
    targets = GENRE_TONAL_TARGETS.get(genre, _DEFAULT_TONAL)
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    nyq = sr / 2
    out = []
    for name, lo, hi in zones:
        hi_c = min(hi, nyq * 0.99)
        try:
            sos = butter(4, [lo / nyq, hi_c / nyq], btype='band', output='sos')
            band = sosfilt(sos, mono)
            rms = np.sqrt(np.mean(band ** 2)) + 1e-12
            level = 20 * np.log10(rms)      # dBFS sejati
        except Exception:
            level = -60.0
        tlo, thi = targets[name]
        out.append({
            'zone': name, 'level': round(float(level), 1),
            'target_low': tlo, 'target_high': thi,
            'status': 'low' if level < tlo else ('high' if level > thi else 'ok'),
        })
    return out
