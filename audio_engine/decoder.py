import subprocess
import os
import sys
import shutil
import numpy as np
import soundfile as sf
from config import TEMP_FOLDER, DEFAULT_SAMPLE_RATE


def _user_ffmpeg_path():
    """Lokasi ffmpeg yang diunduh aplikasi (folder data user, selalu writable)."""
    from config import _user_data_dir
    d = os.path.join(_user_data_dir(), 'bin')
    name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    return os.path.join(d, name)


def _download_ffmpeg():
    """Unduh ffmpeg statis ke folder data user (sekali saja). Dipakai sebagai
    jalan terakhir kalau ffmpeg tak ter-bundle & tak ada di sistem.
    Return path bila berhasil, None bila gagal."""
    import urllib.request, platform, zipfile, tarfile, tempfile, stat as _stat
    dest = _user_ffmpeg_path()
    if os.path.isfile(dest) and os.access(dest, os.X_OK):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    sysname = platform.system().lower()
    machine = platform.machine().lower()
    # Sumber: build statis ffmpeg resmi & tepercaya per-OS.
    url = None
    if sysname == 'darwin':
        # evermeet menyediakan ffmpeg statis macOS (universal/x86_64).
        url = 'https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip'
    elif sysname == 'windows' or os.name == 'nt':
        url = ('https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/'
               'ffmpeg-master-latest-win64-gpl.zip')
    elif sysname == 'linux':
        arch = 'arm64' if 'aarch64' in machine or 'arm64' in machine else 'amd64'
        url = f'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-{arch}-static.tar.xz'
    if not url:
        return None

    try:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        req = urllib.request.Request(url, headers={'User-Agent': 'GRCmasteringStudio'})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp.name, 'wb') as f:
            shutil.copyfileobj(r, f)

        # Ekstrak binary ffmpeg dari arsip.
        extracted = None
        if tmp.name.endswith('.zip') or zipfile.is_zipfile(tmp.name):
            with zipfile.ZipFile(tmp.name) as z:
                for n in z.namelist():
                    base = os.path.basename(n)
                    if base in ('ffmpeg', 'ffmpeg.exe'):
                        with z.open(n) as src, open(dest, 'wb') as out:
                            shutil.copyfileobj(src, out)
                        extracted = dest
                        break
        else:
            with tarfile.open(tmp.name) as t:
                for m in t.getmembers():
                    if os.path.basename(m.name) == 'ffmpeg' and m.isfile():
                        src = t.extractfile(m)
                        with open(dest, 'wb') as out:
                            shutil.copyfileobj(src, out)
                        extracted = dest
                        break
        try:
            os.remove(tmp.name)
        except Exception:
            pass

        if extracted and os.path.isfile(extracted):
            os.chmod(extracted, os.stat(extracted).st_mode |
                     _stat.S_IXUSR | _stat.S_IXGRP | _stat.S_IXOTH)
            return extracted
    except Exception:
        return None
    return None


def _ensure_exec(path):
    """Pastikan file bisa dieksekusi (macOS/Linux sering kehilangan flag +x
    setelah dibundel PyInstaller)."""
    try:
        if path and os.path.isfile(path) and not os.access(path, os.X_OK):
            import stat
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass
    return path


def _find_ffmpeg():
    """Cari ffmpeg untuk decode MP3/M4A. Urutan:
    1) binary imageio-ffmpeg via API resmi
    2) binary imageio-ffmpeg dicari MANUAL di folder bundel (API sering gagal
       menunjuk path yang benar di dalam app terpaket PyInstaller)
    3) ffmpeg vendor yang dibundel di _MEIPASS
    4) ffmpeg sistem (PATH)
    """
    import glob

    # (1) API resmi imageio-ffmpeg
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return _ensure_exec(exe)
    except Exception:
        pass

    # (2) cari manual binary 'ffmpeg-*' di folder imageio_ffmpeg/binaries.
    #     Di app terpaket, modul ada tapi get_ffmpeg_exe bisa salah path.
    search_dirs = []
    try:
        import imageio_ffmpeg as _iff
        search_dirs.append(os.path.join(os.path.dirname(_iff.__file__), 'binaries'))
    except Exception:
        pass
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        search_dirs += [
            os.path.join(base, 'imageio_ffmpeg', 'binaries'),
            base,
            os.path.join(base, 'Frameworks'),
        ]
    for d in search_dirs:
        if not d or not os.path.isdir(d):
            continue
        for pat in ('ffmpeg-*', 'ffmpeg.exe', 'ffmpeg'):
            hits = sorted(glob.glob(os.path.join(d, pat)))
            for h in hits:
                if os.path.isfile(h):
                    return _ensure_exec(h)

    # (3) ffmpeg vendor dibundel
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        for name in ('ffmpeg.exe', 'ffmpeg'):
            cand = os.path.join(base, name)
            if os.path.isfile(cand):
                return _ensure_exec(cand)

    # (4) ffmpeg yang sudah diunduh aplikasi sebelumnya
    _u = _user_ffmpeg_path()
    if os.path.isfile(_u):
        return _ensure_exec(_u)

    # (5) ffmpeg sistem
    return shutil.which('ffmpeg') or 'ffmpeg'


FFMPEG_BIN = _find_ffmpeg()


def _resolve_ffmpeg(progress_callback=None):
    """Pastikan ada ffmpeg yang bisa dijalankan. Kalau FFMPEG_BIN tidak valid,
    coba unduh otomatis ke folder user. Return path ffmpeg atau raise error."""
    global FFMPEG_BIN
    # FFMPEG_BIN valid kalau berupa path file yang ada, atau nama di PATH.
    def _usable(p):
        if not p:
            return False
        if os.path.isfile(p):
            return True
        return shutil.which(p) is not None
    if _usable(FFMPEG_BIN):
        return FFMPEG_BIN
    # coba unduh
    if progress_callback:
        progress_callback(5, 'Menyiapkan ffmpeg (unduh sekali)...')
    got = _download_ffmpeg()
    if got and _usable(got):
        FFMPEG_BIN = got
        return got
    raise RuntimeError(
        'ffmpeg tidak tersedia dan gagal diunduh otomatis — tidak bisa membaca '
        'MP3/M4A. Periksa koneksi internet, atau pasang ffmpeg di sistem.')


def decode_mp3(input_path, target_sr=DEFAULT_SAMPLE_RATE, progress_callback=None):
    output_path = os.path.join(TEMP_FOLDER, os.path.basename(input_path) + '_decoded.wav')

    ffmpeg = _resolve_ffmpeg(progress_callback)
    cmd = [
        ffmpeg, '-y', '-i', input_path,
        '-ar', str(target_sr),
        '-ac', '2',
        '-c:a', 'pcm_s24le',
        '-af', 'aresample=resampler=soxr:precision=28',
        output_path
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=True)
    except FileNotFoundError:
        raise RuntimeError(
            'ffmpeg tidak ditemukan — tidak bisa membaca MP3/M4A. '
            'Pastikan ffmpeg ter-bundle (imageio-ffmpeg) atau terpasang di sistem.')
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b'').decode('utf-8', 'ignore')[-400:]
        raise RuntimeError(f'Gagal decode file audio (ffmpeg): {err.strip()}')

    if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
        raise RuntimeError('Decode menghasilkan file kosong — file sumber mungkin rusak.')

    audio, sr = sf.read(output_path, always_2d=True)
    # Pastikan selalu stereo (n, 2) agar tahap berikutnya konsisten.
    if audio.shape[1] == 1:
        audio = mono_to_stereo(audio)
    elif audio.shape[1] > 2:
        audio = audio[:, :2]
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


def _make_originator_ref(length=12):
    """Kode referensi acak unik per file (huruf/angka/simbol), mis. 'aaOxVBaS#3Kk'."""
    import random, string
    alphabet = string.ascii_letters + string.digits + '#@$%&+='
    return ''.join(random.choice(alphabet) for _ in range(length))


def _write_bext_chunk(wav_path, originator='Pro Tools',
                      originator_ref=None, description=''):
    """Sisipkan chunk BWF 'bext' (Broadcast Wave Format, EBU Tech 3285) ke file
    WAV yang sudah ada. Berisi Originator, OriginationDate/Time (waktu render),
    dan OriginatorReference acak 12 karakter. Ini standar yang dibaca DAW pro.

    Ditulis manual karena soundfile belum mendukung penulisan bext.
    """
    import struct, datetime, os

    now = datetime.datetime.now()
    if originator_ref is None:
        originator_ref = _make_originator_ref(12)

    def _fixed(s, n):
        b = s.encode('ascii', 'replace')[:n]
        return b + b'\x00' * (n - len(b))

    # Susun payload bext (minimal, tanpa CodingHistory panjang).
    bext = b''
    bext += _fixed(description, 256)                       # Description
    bext += _fixed(originator, 32)                         # Originator
    bext += _fixed(originator_ref, 32)                     # OriginatorReference
    bext += _fixed(now.strftime('%Y-%m-%d'), 10)          # OriginationDate YYYY-MM-DD
    bext += _fixed(now.strftime('%H:%M:%S'), 8)           # OriginationTime HH:MM:SS
    bext += struct.pack('<Q', 0)                           # TimeReference (0)
    bext += struct.pack('<H', 1)                           # Version = 1
    bext += b'\x00' * 64                                   # UMID
    bext += struct.pack('<hHHHH', 0, 0, 0, 0, 0)          # loudness fields (5x)
    bext += b'\x00' * 180                                  # Reserved
    # CodingHistory sengaja dikosongkan (tidak ditulis).

    # chunk harus genap; tambahkan pad byte bila ganjil
    if len(bext) % 2 == 1:
        bext += b'\x00'

    chunk = b'bext' + struct.pack('<I', len(bext)) + bext

    # INFO chunk berisi ISFT (Software) = 'Pro Tools' — ditulis manual
    # agar BERSIH tanpa tambahan '(libsndfile-...)'.
    def _info_sub(tag, text):
        b = text.encode('ascii', 'replace') + b'\x00'
        if len(b) % 2 == 1:
            b += b'\x00'
        return tag + struct.pack('<I', len(b)) + b
    info_body = b'INFO' + _info_sub(b'ISFT', 'Pro Tools')
    list_chunk = b'LIST' + struct.pack('<I', len(info_body)) + info_body

    extra = chunk + list_chunk

    # Baca WAV, sisipkan chunk tepat setelah header 'WAVE', perbarui ukuran RIFF.
    with open(wav_path, 'rb') as f:
        data = f.read()
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        return  # bukan WAV standar, lewati saja
    # sisipkan setelah 12 byte pertama (RIFF + size + WAVE)
    new_data = data[:12] + extra + data[12:]
    # perbarui ukuran RIFF (byte 4-8) = total - 8
    new_size = len(new_data) - 8
    new_data = new_data[:4] + struct.pack('<I', new_size) + new_data[8:]
    with open(wav_path, 'wb') as f:
        f.write(new_data)


def write_wav(audio, output_path, sr=DEFAULT_SAMPLE_RATE, subtype='PCM_24'):
    import numpy as _np
    data = _np.asarray(audio)
    channels = 1 if data.ndim == 1 else data.shape[1]
    # Tulis audio tanpa tag software soundfile (soundfile/libsndfile menambahkan
    # embel-embel '(libsndfile-x.y.z)' yang tidak diinginkan). Tag Software
    # ditulis manual & bersih di _write_bext_chunk (INFO chunk).
    try:
        with sf.SoundFile(output_path, 'w', samplerate=int(sr),
                          channels=channels, subtype=subtype) as f:
            f.write(data)
    except Exception:
        # fallback: penulisan biasa (jangan pernah gagal simpan)
        sf.write(output_path, data, int(sr), subtype=subtype)
    # Tambahkan chunk BWF 'bext' (Originator, tanggal/jam render, ref acak)
    # + INFO chunk 'ISFT' = Pro Tools (bersih tanpa libsndfile).
    try:
        _write_bext_chunk(output_path)
    except Exception:
        pass  # metadata opsional — jangan gagalkan penyimpanan
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
