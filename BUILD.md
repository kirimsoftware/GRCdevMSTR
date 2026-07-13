# 📦 Build MASTERINGAUDS sebagai Aplikasi Desktop

MASTERINGAUDS dapat dipaketkan menjadi aplikasi desktop mandiri: **`.app` untuk macOS** dan **`.exe` untuk Windows**. Server Flask berjalan otomatis di background dan UI tampil dalam jendela aplikasi native — pengguna tidak perlu menginstal Python atau ffmpeg.

Ada dua cara build. Cara paling mudah adalah lewat GitHub Actions, karena PyInstaller **tidak bisa cross-compile**: file `.exe` hanya bisa dibuat di Windows dan `.app` hanya bisa dibuat di macOS. GitHub Actions menjalankan keduanya sekaligus di cloud secara gratis untuk repo publik.

## Cara 1 — Build Otomatis via GitHub Actions (disarankan)

1. Commit dan push semua file baru ini ke repo (`desktop.py`, `masteringauds.spec`, `.github/workflows/build-desktop.yml`, serta perubahan pada `config.py` dan `audio_engine/decoder.py`).
2. Buka tab **Actions** di GitHub. Workflow "Build Desktop Apps" akan berjalan otomatis setiap push ke `main`, atau bisa dijalankan manual lewat tombol **Run workflow**.
3. Setelah selesai (±10–20 menit), unduh hasilnya di bagian **Artifacts**: `MASTERINGAUDS-macos` (berisi `MASTERINGAUDS.app`) dan `MASTERINGAUDS-windows` (berisi folder dengan `MASTERINGAUDS.exe`).
4. Untuk membuat rilis resmi, push sebuah tag versi — file zip akan otomatis dilampirkan ke halaman Releases:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Cara 2 — Build Manual di Komputer Sendiri

Jalankan langkah ini **di macOS untuk menghasilkan .app**, atau **di Windows untuk menghasilkan .exe**.

```bash
# 1. Siapkan environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller pywebview

# 2. Siapkan ffmpeg statis di folder vendor/
#    macOS  : unduh dari https://evermeet.cx/ffmpeg/ lalu taruh sebagai vendor/ffmpeg
#    Windows: unduh dari https://www.gyan.dev/ffmpeg/builds/ lalu taruh vendor/ffmpeg.exe
#    (Jika dilewati, app tetap jalan tapi butuh ffmpeg terinstal di sistem pengguna.)

# 3. Build
pyinstaller masteringauds.spec --noconfirm
```

Hasil build ada di folder `dist/`: `MASTERINGAUDS.app` di macOS, atau folder `MASTERINGAUDS/` berisi `MASTERINGAUDS.exe` di Windows.

## Catatan Penting

**macOS Gatekeeper.** Karena app tidak ditandatangani dengan sertifikat Apple Developer, saat pertama dibuka macOS akan menolaknya. Solusinya: klik kanan → Open → Open, atau jalankan `xattr -cr /Applications/MASTERINGAUDS.app`. Untuk distribusi publik yang mulus, diperlukan code signing + notarization (butuh akun Apple Developer, $99/tahun).

**Windows SmartScreen.** Windows mungkin menampilkan peringatan "Windows protected your PC" untuk exe tanpa tanda tangan. Klik **More info → Run anyway**. Menghilangkan peringatan ini sepenuhnya memerlukan sertifikat code signing.

**Bentuk .exe.** Build Windows berupa folder berisi `MASTERINGAUDS.exe` beserta library-nya (mode *onedir*). Ini sengaja, karena mode satu-file tunggal sangat lambat saat startup untuk aplikasi dengan numpy/scipy/librosa dan lebih rawan gagal. Cukup zip foldernya untuk distribusi; pengguna tinggal ekstrak dan jalankan exe-nya.

**File kerja.** Saat berjalan sebagai app, file upload/output disimpan di folder data user (`~/Library/Application Support/MASTERINGAUDS` di macOS, `%LOCALAPPDATA%\MASTERINGAUDS` di Windows), bukan di dalam bundle aplikasi. File otomatis dibersihkan setelah 6 jam sesuai `FILE_RETENTION_HOURS`.

**Ikon aplikasi (opsional).** Taruh `vendor/icon.icns` (macOS) dan `vendor/icon.ico` (Windows) sebelum build; spec akan memakainya otomatis jika ada.

**Jendela aplikasi.** Launcher memakai `pywebview` untuk jendela native. Jika gagal di sistem pengguna, app otomatis fallback membuka UI di browser default.
