import numpy as np
import librosa
import gc


def analyze_audio(audio, sr):
    results = {}

    results['duration'] = len(audio) / sr
    results['sample_rate'] = sr
    results['channels'] = audio.shape[1] if audio.ndim > 1 else 1

    results['frequency'] = _analyze_frequency(audio, sr)
    results['dynamics'] = _analyze_dynamics(audio, sr)
    results['stereo'] = _analyze_stereo(audio, sr)
    results['loudness'] = _measure_integrated_loudness(audio, sr)

    results['issues'] = _detect_issues(results)

    gc.collect()
    return results


def _analyze_frequency(audio, sr):
    if audio.ndim > 1:
        mono = np.mean(audio, axis=1)
    else:
        mono = audio

    n_fft = 4096
    hop_length = n_fft // 4
    stft = np.abs(librosa.stft(mono, n_fft=n_fft, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    avg_spectrum = np.mean(stft, axis=1)

    band_ranges = {
        'sub_bass': (20, 60),
        'bass': (60, 250),
        'low_mid': (250, 500),
        'mid': (500, 2000),
        'high_mid': (2000, 4000),
        'presence': (4000, 6000),
        'brilliance': (6000, 20000),
    }

    band_energies = {}
    for name, (lo, hi) in band_ranges.items():
        mask = (freqs >= lo) & (freqs < hi)
        band_energies[name] = float(np.mean(avg_spectrum[mask]))

    spec_centroid = float(librosa.feature.spectral_centroid(
        y=mono, sr=sr, n_fft=n_fft, hop_length=hop_length
    ).mean())

    return {
        'band_energies': band_energies,
        'spectral_centroid': spec_centroid,
        'freqs': freqs[:len(avg_spectrum)].tolist(),
        'spectrum': avg_spectrum.tolist(),
    }


def _analyze_dynamics(audio, sr):
    if audio.ndim > 1:
        mono = np.mean(audio, axis=1)
    else:
        mono = audio

    rms = librosa.feature.rms(y=mono, hop_length=512)[0]
    rms_db = 20 * np.log10(rms + 1e-10)

    peak_db = 20 * np.log10(np.max(np.abs(mono)) + 1e-10)
    rms_mean_db = float(np.mean(rms_db))
    crest_factor = float(peak_db - rms_mean_db)

    dynamic_range = float(np.percentile(rms_db, 95) - np.percentile(rms_db, 5))

    return {
        'peak_db': peak_db,
        'rms_db': rms_mean_db,
        'crest_factor': crest_factor,
        'dynamic_range': dynamic_range,
    }


def _analyze_stereo(audio, sr):
    if audio.ndim < 2 or audio.shape[1] < 2:
        return {'is_mono': True, 'correlation': 1.0, 'width_percent': 0}

    left = audio[:, 0]
    right = audio[:, 1]

    correlation = float(np.corrcoef(left, right)[0, 1])

    mid = (left + right) / 2
    side = (left - right) / 2
    mid_power = np.mean(mid ** 2)
    side_power = np.mean(side ** 2)
    width_percent = float(100 * side_power / (mid_power + side_power + 1e-10))

    n_fft = 4096
    hop_length = n_fft // 4
    spec_left = librosa.stft(left, n_fft=n_fft, hop_length=hop_length)
    spec_right = librosa.stft(right, n_fft=n_fft, hop_length=hop_length)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    phase_corr = np.zeros(len(freqs))
    for i, f in enumerate(freqs):
        x = spec_left[i] * np.conj(spec_right[i])
        phase_corr[i] = float(np.abs(np.mean(x)) / (np.mean(np.abs(spec_left[i])) * np.mean(np.abs(spec_right[i])) + 1e-10))

    return {
        'is_mono': False,
        'correlation': correlation,
        'width_percent': width_percent,
        'phase_correlation': phase_corr[:256].tolist(),
        'freqs': freqs[:256].tolist(),
    }


def _measure_integrated_loudness(audio, sr):
    from .lufs import measure_lufs
    return measure_lufs(audio, sr)


def _detect_issues(results):
    issues = []
    freq = results['frequency']
    dyn = results['dynamics']
    bands = freq['band_energies']
    total_energy = sum(bands.values()) + 1e-10

    if bands.get('low_mid', 0) / total_energy > 0.35:
        issues.append({'type': 'muddy', 'message': 'Muddy — consider cutting ~250-500Hz', 'severity': 'warning'})
    if bands.get('high_mid', 0) / total_energy > 0.3:
        issues.append({'type': 'harsh', 'message': 'Harsh — consider cutting ~2-4kHz', 'severity': 'warning'})
    if bands.get('bass', 0) / total_energy > 0.4:
        issues.append({'type': 'boomy', 'message': 'Boomy — consider cutting ~60-150Hz', 'severity': 'warning'})
    if bands.get('presence', 0) / total_energy < 0.05:
        issues.append({'type': 'dull', 'message': 'Dull — lacks presence around 4-8kHz', 'severity': 'info'})
    if bands.get('brilliance', 0) / total_energy < 0.03:
        issues.append({'type': 'lacking_air', 'message': 'Lacking air — little energy above 10kHz', 'severity': 'info'})
    if dyn.get('crest_factor', 0) < 6:
        issues.append({'type': 'overcompressed', 'message': 'Over-compressed — low crest factor', 'severity': 'warning'})
    if dyn.get('dynamic_range', 0) < 8:
        issues.append({'type': 'flat', 'message': 'Too flat/squashed — low dynamic range', 'severity': 'info'})

    return issues
