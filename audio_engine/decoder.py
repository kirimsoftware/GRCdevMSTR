import subprocess
import os
import sys
import shutil
import numpy as np
import soundfile as sf
from config import TEMP_FOLDER, DEFAULT_SAMPLE_RATE


def _find_ffmpeg():
    """Cari ffmpeg: binary dari paket imageio-ffmpeg (mendukung mac arm64 &
    windows), lalu binary vendor yang dibundel PyInstaller, lalu PATH sistem."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        for name in ('ffmpeg.exe', 'ffmpeg'):
            cand = os.path.join(base, name)
            if os.path.isfile(cand):
                return cand
    return shutil.which('ffmpeg') or 'ffmpeg'


FFMPEG_BIN = _find_ffmpeg()


def decode_mp3(input_path, target_sr=DEFAULT_SAMPLE_RATE):
    output_path = os.path.join(TEMP_FOLDER, os.path.basename(input_path) + '_decoded.wav')

    cmd = [
        FFMPEG_BIN, '-y', '-i', input_path,
        '-ar', str(target_sr),
        '-ac', '2',
        '-c:a', 'pcm_s24le',
        '-af', 'aresample=resampler=soxr:precision=28',
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    audio, sr = sf.read(output_path)
    return audio, sr, output_path


def decode_audio(input_path, target_sr=DEFAULT_SAMPLE_RATE):
    ext = os.path.splitext(input_path)[1].lower()
    if ext in ['.mp3']:
        return decode_mp3(input_path, target_sr)
    elif ext in ['.wav', '.flac', '.ogg']:
        audio, sr = sf.read(input_path, always_2d=True)

        if audio.shape[1] == 1:
            audio = mono_to_stereo(audio)
        elif audio.shape[1] > 2:
            audio = audio[:, :2]

        if sr != target_sr:
            import librosa
            audio = librosa.resample(audio.T, orig_sr=sr, target_sr=target_sr).T
            sr = target_sr

        return audio, sr, input_path
    else:
        return decode_mp3(input_path, target_sr)


def mono_to_stereo(audio):
    if audio.ndim == 1:
        mono = audio
    else:
        mono = audio[:, 0]
    delay_samples = 23
    left = mono.copy()
    right = np.roll(mono, delay_samples)
    right[:delay_samples] = left[:delay_samples]
    right *= 0.98
    return np.column_stack([left, right])


def write_wav(audio, output_path, sr=DEFAULT_SAMPLE_RATE, subtype='PCM_24'):
    sf.write(output_path, audio, sr, subtype=subtype)
    return output_path


def create_spectral_attenuation(
    noise_profile, mix_factor=0.7, threshold_db=-40
):
    eps = 1e-10
    noise_mag = np.abs(noise_profile)
    noise_mag_db = 20 * np.log10(noise_mag + eps)
    attenuation_db = np.zeros_like(noise_mag_db)
    mask = noise_mag_db > threshold_db
    attenuation_db[mask] = -(noise_mag_db[mask] - threshold_db) * mix_factor
    attenuation_linear = 10 ** (attenuation_db / 20.0)
    return np.clip(attenuation_linear, 0.0, 1.0)


def chunk_processor(audio, sr, process_fn, chunk_duration=10, **kwargs):
    import gc
    chunk_samples = int(chunk_duration * sr)
    n_samples = len(audio)
    output = np.zeros_like(audio)

    for start in range(0, n_samples, chunk_samples):
        end = min(start + chunk_samples, n_samples)
        chunk = audio[start:end].copy()
        processed = process_fn(chunk, sr, **kwargs)
        output[start:end] = processed
        gc.collect()

    return output
