"""
GRCmasteringStudio Desktop Launcher
Menjalankan server Flask di background thread lalu membuka jendela aplikasi.
Dipakai sebagai entry point PyInstaller untuk build .app (macOS) / .exe (Windows).
"""
import os
import sys
import socket
import threading
import time
import urllib.request

# Saat frozen (PyInstaller), pastikan resource dir jadi working directory
if getattr(sys, 'frozen', False):
    RESOURCE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    os.chdir(RESOURCE_DIR)
    sys.path.insert(0, RESOURCE_DIR)

def _log_crash():
    """Tulis traceback startup ke lokasi yang mudah ditemukan + beri tahu user."""
    import traceback
    msg = traceback.format_exc()
    saved = None
    for path in (os.path.expanduser('~/Desktop/GRCmasteringStudio_error.log'),
                 os.path.expanduser('~/GRCmasteringStudio_error.log'),
                 '/tmp/GRCmasteringStudio_error.log'):
        try:
            with open(path, 'w') as f:
                f.write(msg)
            saved = path
            break
        except OSError:
            continue
    if sys.platform == 'darwin':
        try:
            import subprocess
            subprocess.run(['osascript', '-e',
                'display alert "GRCmasteringStudio failed to start" '
                f'message "Error log saved to: {saved or "unknown"}"'],
                timeout=10)
        except Exception:
            pass


try:
    from app import app  # noqa: E402
    from config import FILE_RETENTION_HOURS  # noqa: E402
    from audio_engine.cleanup import cleanup_old_files  # noqa: E402
except Exception:
    _log_crash()
    raise

APP_NAME = 'GRCmasteringStudio'
WINDOW_SIZE = (1200, 800)


def find_free_port(preferred=5000):
    """Pakai port 5000 jika kosong, kalau tidak cari port bebas."""
    for port in (preferred, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return s.getsockname()[1]
        except OSError:
            continue
    return preferred


def run_server(port):
    app.run(debug=False, host='127.0.0.1', port=port,
            threaded=True, use_reloader=False)


def wait_for_server(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    cleanup_old_files(FILE_RETENTION_HOURS)

    port = find_free_port()
    url = f'http://127.0.0.1:{port}'

    server = threading.Thread(target=run_server, args=(port,), daemon=True)
    server.start()

    if not wait_for_server(url):
        print('Server gagal start.')
        sys.exit(1)

    # Coba buka jendela native (pywebview); fallback ke browser default
    try:
        import webview
        try:
            webview.settings['ALLOW_DOWNLOADS'] = True  # izinkan unduhan file
        except Exception:
            pass
        webview.create_window(
            APP_NAME, url,
            width=WINDOW_SIZE[0], height=WINDOW_SIZE[1],
            min_size=(900, 600),
        )
        webview.start()  # blok sampai jendela ditutup
    except Exception:
        import webbrowser
        webbrowser.open(url)
        print(f'{APP_NAME} berjalan di {url}')
        print('Tutup aplikasi dengan menutup jendela terminal ini / Ctrl+C.')
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    try:
        main()
    except Exception:
        _log_crash()
        sys.exit(1)
