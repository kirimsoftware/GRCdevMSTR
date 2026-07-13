import os
import gc
import numpy as np
from .decoder import decode_audio, write_wav
from .eq import apply_parametric_eq
from .dynamics import multiband_compressor, brickwall_limiter, transient_shaper
from .stereo import stereo_width_processor, mid_side_processor, bass_mono_enforce
from .lufs import normalize_lufs, measure_lufs
from .dither import dither_and_shape
from .watermark import remove_watermark
from .cleanup import remove_temp_file
from config import (
    DEFAULT_SAMPLE_RATE, TRUE_PEAK_LIMIT,
    PLATFORM_TARGETS, GENRE_EQ_PRESETS, GENRE_COMPRESSOR_PRESETS,
)


def master_audio(
    audio,
    sr,
    genre='pop',
    platform='spotify',
    remove_wm=True,
    settings=None,
    progress_callback=None,
):
    settings = settings or {}
    step = 0

    # --- ADAPTIVE ANALYSIS: turunkan starting point dari materialnya ---
    # Nilai dari panel Pre-Master (eq_gains/compressor/input_gain_db) SELALU
    # menang; adaptive hanya mengisi yang tidak dikirim.
    input_gain_db = settings.get('input_gain_db')
    if settings.get('adaptive', True) and (
            not settings.get('eq_gains') or not settings.get('compressor')
            or input_gain_db is None):
        from .adaptive import derive_adaptive_settings
        adaptive = derive_adaptive_settings(audio, sr, genre)
        if not settings.get('eq_gains'):
            settings['eq_gains'] = adaptive['eq_gains']
        if not settings.get('compressor'):
            settings['compressor'] = adaptive['compressor']
        if input_gain_db is None:
            input_gain_db = adaptive['input_gain_db']
    try:
        input_gain_db = float(input_gain_db)
    except (TypeError, ValueError):
        input_gain_db = 0.0
    if abs(input_gain_db) > 0.5:
        audio = audio * (10 ** (input_gain_db / 20.0))
    if progress_callback:
        progress_callback(step, f'Gain staging {input_gain_db:+.1f} dB')

    if remove_wm:
        audio = remove_watermark(audio, sr)
        step += 10
        if progress_callback:
            progress_callback(step, 'Watermark removed')

    eq_preset = settings.get('eq_gains', None) or GENRE_EQ_PRESETS.get(genre, GENRE_EQ_PRESETS['pop'])
    audio = apply_parametric_eq(audio, sr, eq_preset, settings.get('eq_q', 1.4))
    step += 15
    if progress_callback:
        progress_callback(step, f'Genre EQ ({genre}) applied')

    comp_preset = settings.get('compressor', None) or _build_genre_compressor(genre)
    audio = multiband_compressor(audio, sr, comp_preset)
    step += 20
    if progress_callback:
        progress_callback(step, 'Multiband compression done')

    audio = transient_shaper(audio, sr, settings.get('attack_gain', 0.5), settings.get('sustain_gain', 0))
    step += 5
    if progress_callback:
        progress_callback(step, 'Transient shaped')

    audio = bass_mono_enforce(audio, sr)
    step += 5
    if progress_callback:
        progress_callback(step, 'Bass mono enforced')

    width = settings.get('stereo_width', 110)
    audio = stereo_width_processor(audio, sr, width)
    step += 5
    if progress_callback:
        progress_callback(step, 'Stereo enhanced')

    mid_gain = settings.get('mid_gain', 0)
    side_gain = settings.get('side_gain', 0.5)
    if mid_gain != 0 or side_gain != 0:
        audio = mid_side_processor(audio, sr, mid_gain, side_gain)
    step += 5
    if progress_callback:
        progress_callback(step, 'M/S processed')

    target_lufs = PLATFORM_TARGETS.get(platform, -14.0)
    audio = normalize_lufs(audio, sr, target_lufs)
    step += 10
    if progress_callback:
        progress_callback(step, f'LUFS normalized to {target_lufs}')

    _bd = 16 if str(settings.get('bit_depth', 24)) == '16' else 24
    audio = dither_and_shape(audio, sr, bit_depth=_bd)
    step += 15
    if progress_callback:
        progress_callback(step, f'Dithered & noise-shaped ({_bd}-bit)')

    # Limiter runs last so the true-peak ceiling holds even after dither noise.
    tp_ceiling = settings.get('true_peak', TRUE_PEAK_LIMIT)
    try:
        tp_ceiling = float(tp_ceiling)
    except (TypeError, ValueError):
        tp_ceiling = TRUE_PEAK_LIMIT
    tp_ceiling = max(-1.0, min(0.0, tp_ceiling))
    audio = brickwall_limiter(audio, sr, threshold_db=tp_ceiling)
    step += 10
    if progress_callback:
        progress_callback(step, 'Brickwall limiter applied')

    lufs_val = measure_lufs(audio, sr)
    tp_val = 20 * np.log10(np.max(np.abs(audio)) + 1e-10)
    if progress_callback:
        progress_callback(100, f'Done — LUFS: {lufs_val:.1f}, TP: {tp_val:.1f}')

    return audio, {'lufs': lufs_val, 'true_peak': tp_val, 'genre': genre, 'platform': platform}


def process_master(input_path, genre='pop', platform='spotify',
                   remove_wm=True, settings=None, progress_callback=None):
    settings = settings or {}
    # Sample rate & bit depth mengikuti pilihan user (default: 44.1kHz / 24-bit).
    from config import SAMPLE_RATES
    try:
        target_sr = int(settings.get('sample_rate', DEFAULT_SAMPLE_RATE))
    except (TypeError, ValueError):
        target_sr = DEFAULT_SAMPLE_RATE
    if target_sr not in SAMPLE_RATES:
        target_sr = DEFAULT_SAMPLE_RATE
    bit_depth = 16 if str(settings.get('bit_depth', 24)) == '16' else 24
    subtype = 'PCM_16' if bit_depth == 16 else 'PCM_24'

    audio, sr, decoded_path = decode_audio(input_path, target_sr)

    if progress_callback:
        progress_callback(5, 'Audio decoded')

    processed, stats = master_audio(audio, sr, genre, platform, remove_wm, settings, progress_callback)

    out_name = os.path.splitext(os.path.basename(input_path))[0] + f'_{platform}_mastered.wav'
    from config import OUTPUT_FOLDER
    output_dir = OUTPUT_FOLDER
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, out_name)
    write_wav(processed, output_path, sr, subtype)

    del audio, processed
    remove_temp_file(decoded_path)
    gc.collect()

    return output_path, stats


def _build_genre_compressor(genre):
    preset = GENRE_COMPRESSOR_PRESETS.get(genre, GENRE_COMPRESSOR_PRESETS['pop'])

    return [
        {
            'low': 20, 'high': 200,
            'threshold_db': preset['threshold'] + 2,
            'ratio': preset['ratio'],
            'attack_ms': preset['attack'],
            'release_ms': preset['release'],
            'makeup_db': 0,
        },
        {
            'low': 200, 'high': 3000,
            'threshold_db': preset['threshold'],
            'ratio': preset['ratio'],
            'attack_ms': preset['attack'] * 1.5,
            'release_ms': preset['release'],
            'makeup_db': 0,
        },
        {
            'low': 3000, 'high': 20000,
            'threshold_db': preset['threshold'] - 2,
            'ratio': preset['ratio'] * 0.7,
            'attack_ms': preset['attack'] * 2,
            'release_ms': preset['release'] * 0.8,
            'makeup_db': 0,
        },
    ]
