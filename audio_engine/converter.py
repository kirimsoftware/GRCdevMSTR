import os
import gc
import subprocess
import numpy as np
import soundfile as sf
from .decoder import decode_audio, write_wav, FFMPEG_BIN
from .dither import dither_and_shape
from .lufs import normalize_lufs, measure_lufs
from .watermark import remove_watermark
from .dynamics import _limit
from .cleanup import remove_temp_file
from config import (DEFAULT_SAMPLE_RATE, TARGET_LUFS, TRUE_PEAK_LIMIT,
                    OUTPUT_FOLDER, TEMP_FOLDER)

# Format output yang didukung: kunci -> (ekstensi, deskripsi)
FORMATS = {
    'wav24':   '.wav',
    'wav16':   '.wav',
    'flac':    '.flac',
    'mp3_320': '.mp3',
    'mp3_v0':  '.mp3',
}


def convert_audio_file(
    input_path,
    out_format='wav24',
    target_sr=DEFAULT_SAMPLE_RATE,
    normalize=True,
    target_lufs=TARGET_LUFS,
    remove_wm=True,
    air_enhance=False,
    progress_callback=None,
):
    """Konversi universal: (mp3/wav/flac/ogg/m4a/aiff) -> wav16/wav24/flac/mp3."""
    if out_format not in FORMATS:
        out_format = 'wav24'

    audio, sr, decoded_path = decode_audio(input_path, target_sr)
    if progress_callback:
        progress_callback(20, 'Decoded audio')

    if remove_wm:
        audio = remove_watermark(audio, sr)
        if progress_callback:
            progress_callback(40, 'Watermark filtered')

    if air_enhance:
        # Opsional: perbaiki materi dull / lacking air (bukan proses standar)
        from .analyzer import analyze_audio
        from .eq import auto_eq_correct
        issues = [i for i in analyze_audio(audio, sr).get('issues', [])
                  if i.get('type') in ('dull', 'lacking_air')]
        if issues:
            audio = auto_eq_correct(audio, sr, issues)
        if progress_callback:
            progress_callback(48, 'Air enhanced' if issues else 'Air check: OK')

    if normalize:
        audio = normalize_lufs(audio, sr, target_lufs)
        if progress_callback:
            progress_callback(55, 'LUFS normalized')

    audio = _limit(audio, sr, TRUE_PEAK_LIMIT, release_ms=15)
    if progress_callback:
        progress_callback(70, 'True peak limited')

    lufs_val = measure_lufs(audio, sr)
    tp_val = 20 * np.log10(np.max(np.abs(audio)) + 1e-10)

    base = os.path.splitext(os.path.basename(input_path))[0]
    ext = FORMATS[out_format]
    out_name = f'{base}_converted{ext}'
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    output_path = os.path.join(OUTPUT_FOLDER, out_name)

    if out_format == 'wav24':
        write_wav(audio, output_path, target_sr, 'PCM_24')
    elif out_format == 'wav16':
        # Dither 16-bit WAJIB saat turun ke 16-bit: menyamarkan quantization
        # distortion jadi noise halus. Tanpa ini, bagian pelan bisa terdengar kasar.
        audio16 = dither_and_shape(audio, target_sr, bit_depth=16)
        write_wav(audio16, output_path, target_sr, 'PCM_16')
    elif out_format == 'flac':
        sf.write(output_path, audio, target_sr, subtype='PCM_24', format='FLAC')
    else:
        # MP3: tulis WAV sementara lalu encode via ffmpeg (libmp3lame)
        tmp_wav = os.path.join(TEMP_FOLDER, f'{base}_enc.wav')
        os.makedirs(TEMP_FOLDER, exist_ok=True)
        write_wav(audio, tmp_wav, target_sr, 'PCM_24')
        if out_format == 'mp3_320':
            enc = ['-codec:a', 'libmp3lame', '-b:a', '320k']
        else:  # mp3_v0 (VBR kualitas tertinggi)
            enc = ['-codec:a', 'libmp3lame', '-q:a', '0']
        cmd = [FFMPEG_BIN, '-y', '-i', tmp_wav] + enc + [output_path]
        subprocess.run(cmd, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        remove_temp_file(tmp_wav)

    if progress_callback:
        progress_callback(95, f'LUFS: {lufs_val:.1f}, TP: {tp_val:.1f} dBTP')

    del audio
    remove_temp_file(decoded_path)
    gc.collect()

    return output_path, {'lufs': lufs_val, 'true_peak': tp_val,
                         'sr': target_sr, 'format': out_format}


# --- Kompatibilitas mundur (dipakai kode lama) ---
def convert_mp3_to_wav(input_path, target_sr=DEFAULT_SAMPLE_RATE,
                       target_lufs=TARGET_LUFS, remove_wm=True,
                       progress_callback=None):
    return convert_audio_file(input_path, 'wav24', target_sr, True,
                              target_lufs, remove_wm, progress_callback)


def apply_true_peak_limiter(audio, sr, ceiling=TRUE_PEAK_LIMIT, lookahead_ms=5):
    return _limit(audio, sr, ceiling, release_ms=15)


def measure_true_peak(audio):
    return 20 * np.log10(np.max(np.abs(audio)) + 1e-10)
