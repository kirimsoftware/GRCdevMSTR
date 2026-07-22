import os
import sys
import multiprocessing


def _user_data_dir():
    """Folder data milik user — selalu bisa ditulis, di luar bundle aplikasi."""
    if sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Application Support/GRCmasteringStudio')
    elif os.name == 'nt':
        return os.path.join(
            os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
            'GRCmasteringStudio')
    return os.path.expanduser('~/.grcmasteringstudio')


if getattr(sys, 'frozen', False):
    # Berjalan sebagai app terpaket (PyInstaller): resource read-only ada di
    # _MEIPASS, sedangkan file kerja (upload/output/temp) disimpan di folder
    # data milik user agar bundle .app/.exe tidak perlu ditulisi.
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    DATA_DIR = _user_data_dir()
    UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
    OUTPUT_FOLDER = os.path.join(DATA_DIR, 'outputs')
    TEMP_FOLDER = os.path.join(DATA_DIR, 'temp')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'static', 'outputs')
    TEMP_FOLDER = os.path.join(BASE_DIR, 'static', 'temp')


def _writable(folder):
    """True hanya jika folder benar-benar bisa DITULIS (bukan sekadar ada).

    Penting untuk macOS App Translocation: bundle read-only bisa saja sudah
    berisi foldernya (makedirs exist_ok lolos) tapi menulis file tetap gagal.
    """
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, '.write_test')
        with open(probe, 'w') as f:
            f.write('ok')
        os.remove(probe)
        return True
    except OSError:
        return False


def _ensure_work_dirs(upload, output, temp):
    """Pastikan ketiga folder kerja bisa ditulis; kalau tidak (mis. app jalan
    dari mount read-only karena App Translocation), alihkan SEMUA ke folder
    data user. Jangan pernah menulis ke dalam bundle aplikasi."""
    if all(_writable(f) for f in (upload, output, temp)):
        return upload, output, temp
    d = _user_data_dir()
    u = os.path.join(d, 'uploads')
    o = os.path.join(d, 'outputs')
    t = os.path.join(d, 'temp')
    os.makedirs(u, exist_ok=True)
    os.makedirs(o, exist_ok=True)
    os.makedirs(t, exist_ok=True)
    return u, o, t


UPLOAD_FOLDER, OUTPUT_FOLDER, TEMP_FOLDER = _ensure_work_dirs(
    UPLOAD_FOLDER, OUTPUT_FOLDER, TEMP_FOLDER)

MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'ogg', 'aiff', 'm4a'}

# Auto-cleanup: uploads/outputs older than this are purged on each upload & at startup
FILE_RETENTION_HOURS = 6

SAMPLE_RATES = [44100, 48000, 88200, 96000]
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_BIT_DEPTH = 24
DEFAULT_CHANNELS = 2

CHUNK_DURATION = 10  # seconds
MAX_WORKERS = min(4, multiprocessing.cpu_count())

TARGET_LUFS = -14.0
HEADROOM_LUFS = -18.0
TRUE_PEAK_LIMIT = -1.0

BASS_MONO_FREQ = 120  # Hz

EQ_BANDS = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]

CROSSOVER_LOW = 200   # Hz
CROSSOVER_HIGH = 3000  # Hz

PLATFORM_TARGETS = {
    'spotify': -14.0,
    'apple': -16.0,
    'youtube': -14.0,
    'tiktok': -14.0,
    'soundcloud': -10.0,
    'club': -8.0,
}

GENRES = ['pop', 'rock', 'edm', 'hiphop', 'jazz', 'classical']

GENRE_EQ_PRESETS = {
    'pop': {
        '32': 0, '64': 1.0, '125': 1.5, '250': 0.5, '500': -1.0,
        '1000': 1.0, '2000': 2.0, '4000': 1.5, '8000': 1.0, '16000': 0.5
    },
    'rock': {
        '32': 0, '64': 2.0, '125': 1.5, '250': 0, '500': -1.5,
        '1000': 1.0, '2000': 1.5, '4000': 1.0, '8000': 0.5, '16000': 0
    },
    'edm': {
        '32': 3.0, '64': 2.5, '125': 0.5, '250': -1.0, '500': -0.5,
        '1000': 0.5, '2000': 1.5, '4000': 2.0, '8000': 1.5, '16000': 1.0
    },
    'hiphop': {
        '32': 3.0, '64': 2.0, '125': 1.0, '250': 0, '500': -1.0,
        '1000': 0, '2000': 1.5, '4000': 1.0, '8000': 0.5, '16000': 0
    },
    'jazz': {
        '32': 1.0, '64': 0.5, '125': 0.5, '250': 1.0, '500': 0.5,
        '1000': 0, '2000': 0.5, '4000': 0.5, '8000': 0, '16000': 0
    },
    'classical': {
        '32': 0.5, '64': 0, '125': 0, '250': 0.5, '500': 0.5,
        '1000': 0, '2000': 0, '4000': 0.5, '8000': 0.5, '16000': 0.5
    }
}

GENRE_COMPRESSOR_PRESETS = {
    'pop': {'threshold': -18, 'ratio': 2.5, 'attack': 10, 'release': 80},
    'rock': {'threshold': -16, 'ratio': 3.0, 'attack': 5, 'release': 60},
    'edm': {'threshold': -20, 'ratio': 4.0, 'attack': 3, 'release': 50},
    'hiphop': {'threshold': -16, 'ratio': 3.5, 'attack': 8, 'release': 70},
    'jazz': {'threshold': -14, 'ratio': 2.0, 'attack': 15, 'release': 120},
    'classical': {'threshold': -12, 'ratio': 1.5, 'attack': 20, 'release': 150},
}
