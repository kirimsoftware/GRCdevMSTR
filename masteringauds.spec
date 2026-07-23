# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec untuk GRCmasteringStudio
# Build:  pyinstaller masteringauds.spec
# - macOS   -> dist/GRCmasteringStudio.app
# - Windows -> dist/GRCmasteringStudio/GRCmasteringStudio.exe

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

APP_NAME = 'GRCmasteringStudio'
IS_MAC = sys.platform == 'darwin'
IS_WIN = sys.platform.startswith('win')

# --- Data files (read-only resources) ---
datas = [
    ('templates', 'templates'),
    ('static/css', 'static/css'),
    ('static/js', 'static/js'),
    ('static/img', 'static/img'),
    ('presets', 'presets'),
]
if os.path.isdir('static/img'):
    datas.append(('static/img', 'static/img'))
datas += collect_data_files('librosa')
# imageio-ffmpeg menyimpan binary ffmpeg (arm64 mac / win64) sebagai data file
datas += collect_data_files('imageio_ffmpeg')

# --- Bundled ffmpeg (disiapkan oleh CI atau manual di folder vendor/) ---
binaries = []
ffmpeg_name = 'ffmpeg.exe' if IS_WIN else 'ffmpeg'
ffmpeg_path = os.path.join('vendor', ffmpeg_name)
if os.path.isfile(ffmpeg_path):
    binaries.append((ffmpeg_path, '.'))
else:
    print(f'[spec] PERINGATAN: {ffmpeg_path} tidak ditemukan — '
          'app akan bergantung pada ffmpeg sistem.')

hiddenimports = (
    collect_submodules('scipy.signal')
    + collect_submodules('soundfile')
    + collect_submodules('cryptography')
    + collect_submodules('webview')          # jendela native (pywebview)
    + ['pyloudnorm', 'imageio_ffmpeg',
       'cryptography.hazmat.bindings._rust',
       'cryptography.hazmat.primitives.asymmetric.ed25519',
       'engineio.async_drivers.threading',
       # dependensi runtime pywebview
       'proxy_tools', 'bottle', 'typing_extensions']
)

# Backend pywebview berbeda per OS; daftarkan yang relevan saja agar
# tidak menggagalkan build di platform lain.
if sys.platform == 'win32':
    hiddenimports += ['clr', 'pythonnet', 'webview.platforms.winforms',
                      'webview.platforms.edgechromium']
elif sys.platform == 'darwin':
    hiddenimports += ['webview.platforms.cocoa', 'objc', 'Foundation',
                      'AppKit', 'WebKit', 'Quartz']

a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PyQt5', 'PySide2', 'IPython'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,          # tanpa jendela terminal
    icon='vendor/icon.icns' if (IS_MAC and os.path.isfile('vendor/icon.icns'))
         else ('vendor/icon.ico' if (IS_WIN and os.path.isfile('vendor/icon.ico')) else None),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name=f'{APP_NAME}.app',
        icon='vendor/icon.icns' if os.path.isfile('vendor/icon.icns') else None,
        bundle_identifier='com.grc.masteringstudio',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
        },
    )
