import numpy as np
import pyloudnorm as pyln


def measure_lufs(audio, sr):
    if audio.ndim > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio
    meter = pyln.Meter(sr)
    return float(meter.integrated_loudness(audio_mono))


def normalize_lufs(audio, sr, target_lufs=-14.0):
    current_lufs = measure_lufs(audio, sr)
    if np.isinf(current_lufs) or abs(current_lufs - target_lufs) < 0.5:
        return audio
    gain_db = target_lufs - current_lufs
    gain_linear = 10 ** (gain_db / 20.0)
    audio = audio * gain_linear
    return audio


def measure_lufs_short_term(audio, sr, block_size=0.4):
    if audio.ndim > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio
    block_samples = int(block_size * sr)
    meter = pyln.Meter(sr)
    lufs_vals = []
    for start in range(0, len(audio_mono), block_samples):
        block = audio_mono[start:start + block_samples]
        if len(block) > sr * 0.1:
            lufs_vals.append(float(meter.integrated_loudness(block)))
    return lufs_vals


def measure_lufs_momentary(audio, sr):
    if audio.ndim > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio
    meter = pyln.Meter(sr)
    block_samples = int(0.1 * sr)
    lufs_vals = []
    for start in range(0, len(audio_mono), block_samples // 2):
        block = audio_mono[start:start + block_samples]
        if len(block) > sr * 0.05:
            lufs_vals.append(float(meter.integrated_loudness(block)))
    return lufs_vals
