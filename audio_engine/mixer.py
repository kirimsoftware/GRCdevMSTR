import gc
from .decoder import decode_audio, write_wav
from .analyzer import analyze_audio
from .eq import apply_parametric_eq, auto_eq_correct
from .dynamics import multiband_compressor, transient_shaper
from .stereo import stereo_width_processor, mid_side_processor, bass_mono_enforce
from .lufs import normalize_lufs
from .cleanup import remove_temp_file
from config import HEADROOM_LUFS
import os


def intelligent_mix(audio, sr, settings=None, progress_callback=None):
    settings = settings or {}

    analysis = analyze_audio(audio, sr)
    if progress_callback:
        progress_callback(15, 'Analysis done')

    issues = analysis.get('issues', [])
    eq_gains = settings.get('eq_gains', {})
    audio = auto_eq_correct(audio, sr, issues)
    if progress_callback:
        progress_callback(25, 'Auto-EQ corrected')

    if eq_gains:
        audio = apply_parametric_eq(audio, sr, eq_gains, settings.get('eq_q', 1.4))
    if progress_callback:
        progress_callback(35, 'Custom EQ applied')

    comp_config = settings.get('compressor', None)
    if comp_config:
        audio = multiband_compressor(audio, sr, comp_config)
    else:
        audio = multiband_compressor(audio, sr)
    if progress_callback:
        progress_callback(50, 'Multiband compression done')

    attack_gain = settings.get('transient_attack', 0)
    sustain_gain = settings.get('transient_sustain', 0)
    if attack_gain != 0 or sustain_gain != 0:
        audio = transient_shaper(audio, sr, attack_gain, sustain_gain)
    if progress_callback:
        progress_callback(60, 'Transient shaping done')

    width = settings.get('stereo_width', 100)
    if width != 100:
        audio = stereo_width_processor(audio, sr, width)
    if progress_callback:
        progress_callback(70, 'Stereo width processed')

    bass_mono = settings.get('bass_mono', True)
    if bass_mono:
        audio = bass_mono_enforce(audio, sr)
    if progress_callback:
        progress_callback(80, 'Bass mono enforced')

    mid_gain = settings.get('mid_gain', 0)
    side_gain = settings.get('side_gain', 0)
    if mid_gain != 0 or side_gain != 0:
        audio = mid_side_processor(audio, sr, mid_gain, side_gain)
    if progress_callback:
        progress_callback(90, 'Mid/Side processed')

    target_lufs = settings.get('target_lufs', HEADROOM_LUFS)
    audio = normalize_lufs(audio, sr, target_lufs)
    if progress_callback:
        progress_callback(95, 'LUFS normalized')

    return audio


def process_mix(input_path, settings=None, progress_callback=None):
    audio, sr, decoded_path = decode_audio(input_path)

    if progress_callback:
        progress_callback(5, 'Audio decoded')

    processed = intelligent_mix(audio, sr, settings, progress_callback)

    out_name = os.path.splitext(os.path.basename(input_path))[0] + '_mixed.wav'
    from config import OUTPUT_FOLDER
    output_dir = OUTPUT_FOLDER
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, out_name)
    write_wav(processed, output_path, sr)

    del audio, processed
    remove_temp_file(decoded_path)
    gc.collect()

    return output_path
