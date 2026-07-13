#!/usr/bin/env python3
"""
MASTERINGAUDS CLI — Command-line audio mastering tool
Usage:
    python cli.py convert input.mp3 [--sr 44100] [--no-wm]
    python cli.py mix input.mp3 [--preset pop|rock|edm|hiphop|jazz|classical]
    python cli.py master input.mp3 [--genre pop] [--platform spotify] [--no-wm]
    python cli.py analyze input.mp3
"""

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audio_engine.converter import convert_mp3_to_wav  # noqa: E402
from audio_engine.mixer import process_mix  # noqa: E402
from audio_engine.masterer import process_master  # noqa: E402
from audio_engine.analyzer import analyze_audio  # noqa: E402
from audio_engine.decoder import decode_audio  # noqa: E402
from audio_engine.lufs import measure_lufs  # noqa: E402
from config import PLATFORM_TARGETS, GENRES, SAMPLE_RATES  # noqa: E402


def progress_printer(pct, msg):
    bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
    sys.stdout.write(f'\r  [{bar}] {pct:3d}%  {msg}')
    sys.stdout.flush()
    if pct >= 100:
        print()


def cmd_convert(args):
    print(f'\n  Converting: {args.input}')
    print(f'  Sample Rate: {args.sr} Hz')
    print(f'  Watermark Removal: {not args.no_wm}\n')

    t0 = time.time()
    out_path, stats = convert_mp3_to_wav(
        args.input,
        target_sr=args.sr,
        remove_wm=not args.no_wm,
        progress_callback=progress_printer,
    )
    elapsed = time.time() - t0

    print(f'\n  Output : {out_path}')
    print(f'  LUFS    : {stats["lufs"]:.1f}')
    print(f'  True Peak: {stats["true_peak"]:.1f} dBTP')
    print(f'  Time   : {elapsed:.1f}s')
    print(f'  Sample Rate: {stats["sr"]} Hz\n')


def cmd_mix(args):
    print(f'\n  Mixing: {args.input}')

    settings = {}
    if args.preset:
        print(f'  Preset: {args.preset}')

    t0 = time.time()
    out_path = process_mix(args.input, settings, progress_callback=progress_printer)
    elapsed = time.time() - t0

    print(f'\n  Output: {out_path}')
    print(f'  Time  : {elapsed:.1f}s\n')


def cmd_master(args):
    print(f'\n  Mastering: {args.input}')
    print(f'  Genre   : {args.genre}')
    print(f'  Platform: {args.platform} ({PLATFORM_TARGETS.get(args.platform, -14)} LUFS)')
    print(f'  Watermark Removal: {not args.no_wm}\n')

    t0 = time.time()
    out_path, stats = process_master(
        args.input,
        genre=args.genre,
        platform=args.platform,
        remove_wm=not args.no_wm,
        progress_callback=progress_printer,
    )
    elapsed = time.time() - t0

    print(f'\n  Output : {out_path}')
    print(f'  LUFS    : {stats["lufs"]:.1f}')
    print(f'  True Peak: {stats["true_peak"]:.1f} dBTP')
    print(f'  Genre   : {stats["genre"]}')
    print(f'  Platform: {stats["platform"]}')
    print(f'  Time   : {elapsed:.1f}s\n')


def cmd_analyze(args):
    print(f'\n  Analyzing: {args.input}\n')

    audio, sr, _ = decode_audio(args.input)
    results = analyze_audio(audio, sr)
    lufs_val = measure_lufs(audio, sr)

    print(f'  Duration : {results["duration"]:.1f}s')
    print(f'  Sample Rate: {results["sample_rate"]} Hz')
    print(f'  Channels : {results["channels"]}')
    print(f'  LUFS     : {lufs_val:.1f}')
    print(f'  Peak     : {results["dynamics"]["peak_db"]:.1f} dB')
    print(f'  RMS      : {results["dynamics"]["rms_db"]:.1f} dB')
    print(f'  Crest Factor: {results["dynamics"]["crest_factor"]:.1f} dB')
    print(f'  Dynamic Range: {results["dynamics"]["dynamic_range"]:.1f} dB')
    print(f'  Stereo Width: {results["stereo"]["width_percent"]:.0f}%')
    print(f'  Correlation: {results["stereo"]["correlation"]:.3f}')

    if results.get('issues'):
        print('\n  Issues Detected:')
        for issue in results['issues']:
            icon = '⚠' if issue['severity'] == 'warning' else 'ℹ'
            print(f'    {icon} [{issue["type"]}] {issue["message"]}')

    print()


def main():
    parser = argparse.ArgumentParser(
        description='MASTERINGAUDS — Professional Audio Mastering Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python cli.py convert song.mp3
  python cli.py convert song.mp3 --sr 96000
  python cli.py mix song.wav --preset edm
  python cli.py master song.wav --genre edm --platform spotify
  python cli.py master song.wav --genre pop --platform apple --no-wm
  python cli.py analyze song.mp3
        '''
    )

    subparsers = parser.add_subparsers(dest='command', help='Command')

    p_convert = subparsers.add_parser('convert', help='Convert MP3 to mastered WAV')
    p_convert.add_argument('input', help='Input audio file')
    p_convert.add_argument('--sr', type=int, default=44100, choices=SAMPLE_RATES, help='Sample rate')
    p_convert.add_argument('--no-wm', action='store_true', help='Skip watermark removal')

    p_mix = subparsers.add_parser('mix', help='Intelligent mixing')
    p_mix.add_argument('input', help='Input audio file')
    p_mix.add_argument('--preset', choices=GENRES, help='Genre preset')

    p_master = subparsers.add_parser('master', help='Professional mastering')
    p_master.add_argument('input', help='Input audio file')
    p_master.add_argument('--genre', choices=GENRES, default='pop', help='Genre (default: pop)')
    p_master.add_argument('--platform', choices=list(PLATFORM_TARGETS.keys()), default='spotify', help='Platform target (default: spotify)')
    p_master.add_argument('--no-wm', action='store_true', help='Skip watermark removal')

    p_analyze = subparsers.add_parser('analyze', help='Analyze audio file')
    p_analyze.add_argument('input', help='Input audio file')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    print()
    print('  ╔══════════════════════════════════╗')
    print('  ║     MASTERINGAUDS — CLI v1.0     ║')
    print('  ╚══════════════════════════════════╝')

    if args.command == 'convert':
        cmd_convert(args)
    elif args.command == 'mix':
        cmd_mix(args)
    elif args.command == 'master':
        cmd_master(args)
    elif args.command == 'analyze':
        cmd_analyze(args)


if __name__ == '__main__':
    main()
