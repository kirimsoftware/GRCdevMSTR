# GRCmasteringStudio — Dokumentasi Project (untuk lanjut di akun / chat mana pun)

> **Cara pakai dokumen ini:** tempel seluruh isinya di awal chat baru, lalu bilang:
> **"Lanjutkan project GRCmasteringStudio, clone repo-ku dulu."**
> Claude akan `git clone` repo dan langsung punya semua konteks + kode terkini.

---

## 0. ATURAN WAJIB (jangan dilanggar)

1. **Jangan lakukan perubahan apa pun yang menurunkan kualitas yang sudah membaik.**
2. **Jangan menyentuh algoritma audio inti** kecuali ada alasan sangat kuat + persetujuan
   eksplisit user + verifikasi. File yang HARAM diubah sembarangan:
   `audio_engine/dynamics.py`, `audio_engine/adaptive.py`, `audio_engine/eq.py`,
   `audio_engine/stereo.py`, `audio_engine/lufs.py`, `static/js/preview.js`.
3. **Setiap perubahan diuji dulu** (jalankan server + playwright + tes numerik) sebelum
   dikirim. Kalau ragu apakah suatu perubahan mengubah hasil audio, **revert** daripada
   kirim tebakan.
4. **Claude tidak bisa mendengar audio** — hanya bisa ukur numerik. Untuk hal yang
   bergantung telinga (kualitas suara preview), user adalah penentu. Jangan memaksakan
   "perbaikan" berdasarkan angka kalau user bilang terdengar lebih buruk.
5. Semua percakapan dalam **Bahasa Indonesia**. UI aplikasi dalam **Bahasa Inggris**.

---

## 1. Apa ini

Aplikasi desktop **audio mastering** (Python/Flask backend + Web Audio frontend),
dipaket jadi `.app` (macOS) & `.exe` (Windows) via GitHub Actions + PyInstaller.

- **Repo GitHub:** **PRIVATE** (dulu publik di `kirimsoftware/GRCmasteringaudio`, sudah
  dipindah ke repo private untuk mengamankan source code).
- **Akun:** kirimsoftware
- Karena repo **private**, Claude **TIDAK bisa `git clone`** repo-nya (tidak punya akses).
  **Cara memberi kode ke Claude di chat baru:** download repo dari GitHub
  (Code → Download ZIP), lalu **upload ZIP itu ke chat**. Claude ekstrak & lanjut kerja.
  Alternatif: upload file-file yang relevan saja.
- User **bukan developer** — upload file lewat GitHub browser (Add file → Upload files
  atau Edit file), BUKAN git CLI.
- **Cara upload yg benar:** semua file berubah dalam **1 commit** → GitHub Actions build
  **per-commit (bukan per-file)**, jadi sekaligus = 1 build = hemat waktu. Untuk file di
  folder `.github/` (tersembunyi di Mac karena diawali titik), gunakan **Edit file**
  langsung di GitHub (buka file lama → pensil → timpa isi → commit), jangan drag-drop.
- **Lihat file tersembunyi di Mac Finder:** tekan `Cmd + Shift + .` (titik).

### Status build (per Juli 2026)
- ✅ Windows — berjalan sempurna (sedang diuji user).
- ✅ macOS Apple Silicon — berjalan sempurna.
- ⏳ macOS Intel — build sudah diperbaiki (kunci numba/llvmlite), perlu konfirmasi di
  Mac Intel fisik.

---

## 2. Arsitektur & cara kerja

### Backend (Python/Flask)
- `app.py` — server Flask + semua endpoint API.
- `audio_engine/` — mesin pemrosesan audio:
  - `masterer.py` — orkestrasi mastering (decode → adaptive → EQ → comp → stereo →
    dither → LUFS → limiter → write). **DIUBAH** (lihat §4): kini terima sample_rate &
    bit_depth dari settings.
  - `converter.py` — konversi format. **DIUBAH**: tambah dither 16-bit.
  - `dynamics.py` — multiband compressor + limiter. **ASLI, jangan sentuh.**
  - `adaptive.py` — analisa per-lagu (crest factor per band → threshold pintar).
    **ASLI, jangan sentuh.**
  - `eq.py`, `stereo.py`, `lufs.py`, `decoder.py`, `dither.py`, `analyzer.py` — **ASLI.**
- `licensing.py` — verifikasi lisensi Ed25519. File `static/license.key` = lisensi test,
  **JANGAN pernah upload ke repo publik.**
- `config.py` — path lintas-platform (macOS `~/Library/Application Support/...`,
  Windows `LOCALAPPDATA`, dll). `DEFAULT_SAMPLE_RATE = 44100`, `SAMPLE_RATES` = daftar
  sample rate valid.

### Frontend (Web Audio + templates)
- `templates/` — `index.html` (shell + player A/B/R bawah), `masterer.html` (tab Master),
  `album.html` (tab Album), `converter.html` (tab Convert), `mixer.html`.
- `static/js/` — `uploader.js` (upload + master flow + chain labels), `album.js`
  (album mastering), `preview.js` (Web Audio realtime — **ASLI, disembunyikan**),
  `player.js` (player A/B/R), `equalizer.js`, `knob.js`, `analyzer_panel.js`, dll.
- `static/css/style.css` — semua styling. Tema **"Classic Futuristic Cyan"**.

### Cara Claude verifikasi (workflow tes lokal)
1. Clone repo ke `/home/claude/repo3`.
2. Install deps: `pip install -r requirements.txt --break-system-packages` (+ pynacl,
   playwright, flask).
3. Generate lisensi test in-memory (keypair sendiri, patch `licensing.PUBLIC_KEY_B64`,
   tulis token ke `LICENSE_PATH`) lalu jalankan Flask di thread.
4. Verifikasi UI pakai **playwright + Chromium headless** (screenshot ke /tmp, lalu view).
5. Verifikasi audio pakai **OfflineAudioContext** (numerik) atau proses Python langsung.
6. **PENTING:** app desktop di Mac pakai **WebKit** (bukan Chromium). Hindari
   `<input type=range>` native & tekstur foto → pakai **CSS murni + elemen kustom (div)**
   supaya render identik di semua engine.

---

## 3. Tema visual: "Classic Futuristic Cyan"
- Latar near-black + grid glow, aksen **cyan neon** (`--cy: #00e5ff`), LCD readout.
- Semua **CSS murni** (tak ada tekstur/gambar hardware) → identik WebKit & Chromium.
- Elemen merah (toggle aktif, bintang drop-zone) = merah tapi glow/menyala.
- Panel: 4 corner bracket cyan. Header judul box rata tengah.
- Variabel warna di blok `:root` tema (cari `--cy:` di style.css).

---

## 4. STATUS FINAL FITUR (semua sudah jadi & terverifikasi)

### Tab Master
- Upload lagu → **analisa adaptive otomatis** mengisi knob EQ & compressor dengan
  threshold pintar per-lagu (via `/api/adaptive` → `applyAdaptiveDefaults()`).
- **Alur "Master & Listen" (Preview = Master):** klik tombol **"★ Master & Listen"** →
  server render lagu penuh → hasil render **otomatis jadi OUT (B)** di player bawah
  (auto-switch) → bandingkan dengan IN (A) pakai telinga → belum cocok? ubah Fine Tuning
  → klik lagi → yakin? Download. **Preview = file yang di-download (akurat, bukan Web
  Audio).**
- Fine Tuning: Parametric EQ (10-band, fader kustom div+drag), Multiband Compressor
  (knob kustom), Image/Transient, Match Reference (tiru EQ lagu referensi — **dipakai
  user, jangan hapus**).
- **Sample Rate** dropdown: 44.1 / 48 / 88.2 / 96 kHz.
- **Bit Depth** dropdown: 24-bit / 16-bit (dithered). Label "TPDF Dither" di chain kanan
  ikut berubah sesuai pilihan (`chainDitherVal`).
- Toggle default: **Adaptive Analysis = ON**, **Watermark Removal = OFF**.
- **Live Preview LAMA disembunyikan** (tombol + monitor IN/OUT/REF + out-meter =
  `display:none`). Kode `preview.js` DIPERTAHANKAN karena Match Reference memakainya.
  A/B comparison sekarang via player bawah (A=IN, B=OUT, R=REF) yang akurat.

### Tab Album (max 15 lagu)
- Tiap lagu di-master adaptive sesuai mix-nya. Progress bar **beranimasi** per lagu
  (bar jalan + teks status "Decoding...", "Applying multiband compression...",
  "Finalizing..."; bar indeterminate saat 0%). Tombol **retry (↻)** per lagu kalau error.
- Preview A/B per lagu: klik judul lagu → player pindah ke lagu itu.
- **Fine Tuning tersedia** di Album (toggle "Use Fine Tuning").
- **Download 2 opsi:** "Download WAV" (tiap lagu file terpisah di `Downloads/<album>/`)
  dan "Download ZIP" (satu ZIP, dibuat & disimpan **server-side** ke Downloads via
  `/api/album/zip_save` — penulisan atomik, tidak korup). Fallback blob browser ada.
- Toggle default: **Adaptive = ON**, **Watermark Removal = OFF**, **Fine Tuning = ON**.

### Tab Convert
- Konversi format. Toggle default OFF. Sample rate menyesuaikan format (WAV/FLAC =
  44.1/48/88.2/96; MP3 = 44.1/48).
- **Dither 16-bit** kini diterapkan saat convert ke WAV 16-bit (dulu TIDAK ada — celah
  kualitas, sudah diperbaiki).
- Panel brand kanan: foto `static/img/brand_placeholder.jpg` **besar mengisi penuh**
  (`cover`, min-height 640px, TANPA border/frame). Credit "Created by @GitaRoni 2026".
  **Bug foto hilang setelah proses = SUDAH DIPERBAIKI** (dulu `showProgress` menyembunyikan
  brand & tak pernah mengembalikan).

**Urutan nav:** Master → Album → Convert.

---

## 5. BUG YANG SUDAH DIPERBAIKI (jangan diulang)

1. **Crash numpy di Mac lain:** `requirements.txt` → numpy==1.26.4 + scipy==1.13.1.
   Workflow: `MACOSX_DEPLOYMENT_TARGET: '11.0'` + force-reinstall numpy 1.26.4 + verifikasi
   versi saat build. (numpy 2.x crash di macOS lama: simbol Accelerate
   `_cblas_caxpy$NEWLAPACK$ILP64`.)
2. **Fader miring & knob aneh lintas-engine** → elemen kustom CSS (div).
3. **Tema hardware lama** (`!important` menumpuk) → dibuang, diganti tema cyan bersih.
4. **Album: tombol download hilang** → dulu frontend hanya tunggu 10 detik hasil render;
   lagu panjang belum selesai ditulis → download hilang. Kini tunggu s/d 3 menit &
   TIDAK menandai selesai sebelum output_url ada. Berlaku Master & Album.
5. **Album: ZIP corrupt** → dulu via blob browser (tak andal di WebView desktop). Kini
   ZIP dibuat & disimpan server-side (atomik). Guard: tolak ZIP kosong (404).
6. **Foto brand hilang setelah proses** → hapus baris yg menyembunyikan brandCard di
   `showProgress` (uploader.js).
7. **Label "TPDF Dither" tak ikut berubah** saat pilih 16-bit → beri id `chainDitherVal`
   + listener di uploader.js.
8. **Toggle Adaptive master cuma hiasan** → dulu payload hardcode `adaptive: true`. Kini
   baca `#masterAdaptive`.
9. **Build Intel GAGAL** (llvmlite compile from source) → kunci `numba==0.62.1` &
   `llvmlite==0.45.1` di requirements (punya wheel Intel+ARM cp312). Lihat §7.

### Catatan Live Preview (histori penting, agar tidak mengulang kesalahan)
Sepanjang pengembangan, `preview.js` (Web Audio realtime) sempat berkali-kali diubah
(crossover komplementer, netralkan makeup, OUT_TRIM) untuk mencocokkan suara OUT dengan
render Python. **SEMUA perubahan itu akhirnya di-REVERT ke asli** karena: (a) Web Audio
tak akan pernah 100% == render Python (mesin beda), (b) user bilang tetap terdengar
mundur. **Solusi final = alur "Master & Listen"** (preview pakai render server, bukan
Web Audio). Jadi: JANGAN coba lagi memperbaiki kualitas suara Live Preview via Web Audio.
Live Preview sudah disembunyikan; A/B pakai file render sungguhan.

---

## 6. Foto brand (trademark)
- File: `static/img/brand_placeholder.jpg` (foto studio, 1600×1200, ~420KB, progressive).
- User ganti dgn foto sendiri: upload ke GitHub (`static/img/`), timpa
  `brand_placeholder.jpg` (nama sama). Foto asli high-res sebaiknya di-resize ke ~1600px
  lebar + JPEG quality 88 progressive agar ringan tapi tajam.
- CSS pakai `cover` center → foto mengisi penuh (tepi bisa sedikit ter-crop, wajar).
- Credit: "Created by @GitaRoni 2026".

---

## 7. BUILD & KOMPATIBILITAS (penting untuk rilis)

### Workflow: `.github/workflows/build-desktop.yml`
Matrix 3 build (semua target minimum **macOS 11 Big Sur** via `MACOSX_DEPLOYMENT_TARGET`):
- `macos-latest` → label **macos-applesilicon** (arm64) — Mac M1/M2/M3/M4.
- `macos-15-intel` → label **macos-intel** (x86_64) — Mac Intel.
- `windows-latest` → label **windows** (x86_64) — Windows 10/11 64-bit.

**CATATAN RUNNER (bisa berubah, cek saat build):**
- `macos-13` (runner Intel lama) **sudah di-retire Desember 2025** — jangan pakai.
- `macos-15-intel` = runner Intel resmi pengganti, berlaku **s/d Agustus 2027**.
- `macos-latest` migrasi ke **macOS 26 mulai 15 Juni 2026** (tetap ARM, tetap aman).
- Kalau `macos-15-intel` suatu saat di-retire, cek pengganti Intel terbaru di
  https://github.com/actions/runner-images (mis. `macos-26-intel`).

### Kompatibilitas library (semua sudah dicek punya wheel Intel + ARM cp312)
- numpy 1.26.4, scipy 1.13.1 → wheel Intel (macosx_10_9_x86_64) & ARM ✓
- **numba 0.62.1 + llvmlite 0.45.1** (DIKUNCI) → wheel Intel (macosx_10_15) & ARM ✓.
  **WAJIB dikunci** — tanpa ini pip ambil numba terbaru yg compile llvmlite dari source
  (butuh LLVM/CMake) → build Intel gagal.
- cryptography 44.0.0 → universal2 (Intel+ARM) ✓
- imageio-ffmpeg → wheel Intel ✓; ffmpeg disediakan `imageio_ffmpeg.get_ffmpeg_exe()`
  otomatis sesuai arsitektur runner (makanya build Intel HARUS di runner Intel).
- librosa, soundfile, pyloudnorm, pydub → pure Python ✓

### codesign (Bug #2 diperbaiki)
Dulu `codesign --force --deep --sign -` (Apple tak sarankan `--deep`; bikin signature
tak konsisten pada bundle banyak .dylib). Kini: sign nested binary (.dylib/.so) dari
dalam ke luar dulu, lalu bundle utama, tanpa `--deep`.

### Cara download hasil build
GitHub repo → tab **Actions** → run terbaru (centang hijau) → scroll ke **Artifacts** →
download 3 file (applesilicon / intel / windows). Artifact ter-zip 2x (ekstrak 2 kali).
Artifact sementara (auto-hapus ~90 hari) — untuk rilis permanen pakai **Releases** (buat
tag versi, workflow otomatis melampirkan file).

### Batas yang jujur
Claude TIDAK bisa menjalankan build macOS / menjamin bebas bug runtime dari environment
tes. Konfirmasi akhir tiap arsitektur = **jalankan di device fisik** (Mac Intel / ARM /
Windows asli). Analisis statis bilang mulus, tapi runtime harus dites user.

### WebView (Windows)
`pywebview` pakai WebView bawaan OS: macOS = WKWebView (selalu ada), Windows = **WebView2**
(bawaan Win11; Win10 lama mungkin perlu install runtime). Ada fallback ke browser.

### Ide yang DITOLAK (jangan dikerjakan)
- "Audio setup / lock ke soundcard sample rate": **tidak mungkin di web app** (browser
  tak beri akses hardware audio) & **tidak perlu** (setting soundcard = monitoring, tak
  memengaruhi file render). Kualitas hasil ditentukan sample rate/bit depth **file render**
  + dither, yang sudah beres.

---

## 8. DAFTAR FILE YANG PERNAH DIUBAH (state final)

Upload semua ini (dalam 1 commit) untuk mendapat versi terkini:
```
.github/workflows/build-desktop.yml   (build 3-arch + codesign fix)
requirements.txt                      (kunci numba/llvmlite — fix build Intel)
app.py                                (endpoint album zip_save, dll)
audio_engine/masterer.py              (sample rate + bit depth + dither by setting)
audio_engine/converter.py             (dither 16-bit)
static/js/uploader.js                 (master flow, adaptive, chain labels, sr/bit payload)
static/js/album.js                    (animasi progress, retry, download WAV/ZIP)
static/css/style.css                  (tema cyan, brand foto besar, hint master, dll)
templates/masterer.html               (dropdown sr/bit, master&listen, IN/OUT hidden)
templates/album.html                  (toggle defaults, tombol download WAV/ZIP)
static/img/brand_placeholder.jpg      (foto studio high-res)
```

**JANGAN diubah (asli, jaga kualitas suara):**
`audio_engine/dynamics.py`, `adaptive.py`, `eq.py`, `stereo.py`, `lufs.py`,
`decoder.py`, `dither.py`, `static/js/preview.js`.

**JANGAN di-upload ke repo publik:** `static/license.key` (lisensi test).

---

## 9. Endpoint API utama (referensi)
- `POST /api/upload` — upload file → {task_id, filepath}
- `POST /api/master` — render master (terima genre, platform, remove_wm, settings termasuk
  sample_rate & bit_depth) → jalan async, progress via task_id
- `GET  /api/progress/<task_id>` — {percent, message}
- `GET  /api/result/<task_id>` — {output_url} (atau pending / error)
- `GET  /api/download?file=..&name=..` — unduh/putar hasil
- `POST /api/adaptive` — analisa lagu → {eq_gains, compressor, input_gain_db}
- `POST /api/album/save` — simpan tiap lagu WAV ke Downloads/<album>/
- `POST /api/album/zip_save` — buat ZIP server-side ke Downloads (atomik)
- `POST /api/album/zip` — ZIP via attachment (fallback browser)
- `POST /api/convert` — konversi format
- `GET  /api/license/status` — status lisensi

---

## 10. Ide/pekerjaan berikutnya (belum dikerjakan, opsional)
- Konfirmasi build Intel sukses di Mac Intel fisik (setelah fix numba/llvmlite).
- Pertimbangkan halaman **Releases** untuk distribusi permanen (bukan Artifacts).
- (Jika perlu Windows lama) sediakan installer WebView2 / instruksi.
- Peringatan "Node.js 20 deprecated" di Actions = warning saja, bukan error; bisa
  di-update belakangan (actions/checkout, setup-python, upload-artifact ke versi terbaru).

---

## 11. CARA PRIVATE REPO & HAPUS REPO PUBLIK LAMA

### A. Buat repo PRIVATE baru (rekomendasi: paling aman)
1. GitHub → pojok kanan atas **+** → **New repository**
2. Owner: `kirimsoftware`. Repository name: mis. `GRCmasteringStudio` (boleh nama baru).
3. **Pilih: Private** ⚠️ (jangan Public)
4. **JANGAN** centang "Add a README" / .gitignore / license (biar kosong).
5. Klik **Create repository**.
6. Di repo kosong itu: **uploading an existing file** → drag semua isi dari
   `GRCmasteringStudio-REPO-LENGKAP.zip` (ekstrak dulu) → Commit.
   - **PENTING:** folder `.github` tersembunyi di Mac. Tekan `Cmd + Shift + .` di Finder
     agar terlihat, lalu ikut di-drag. Kalau tetap sulit: buat file manual di GitHub
     (Add file → Create new file → ketik `.github/workflows/build-desktop.yml` → paste isi).
7. Cek tab **Actions** → build jalan → 3 artifact keluar.

### B. Ubah repo LAMA jadi private (alternatif, kalau mau pertahankan history)
1. Buka repo `kirimsoftware/GRCmasteringaudio` → **Settings**
2. Scroll paling bawah → **Danger Zone** → **Change repository visibility**
3. **Change to private** → ketik nama repo untuk konfirmasi → konfirmasi.
> ⚠️ Catatan: mengubah ke private TIDAK menghapus fork/clone yang mungkin sudah dibuat
> orang lain saat masih publik, dan cache Google bisa tetap ada sementara.

### C. HAPUS repo publik lama (setelah repo private siap & terbukti jalan)
1. **PASTIKAN DULU** repo private baru sudah berisi semua file & build sukses.
2. Buka repo lama `kirimsoftware/GRCmasteringaudio` → **Settings**
3. Scroll paling bawah → **Danger Zone** → **Delete this repository**
4. GitHub minta ketik nama lengkap repo (`kirimsoftware/GRCmasteringaudio`) → konfirmasi.
> ⚠️ **PERMANEN & TIDAK BISA DIBATALKAN.** Semua Actions history & artifact ikut hilang.
> Download dulu artifact/rilis yang masih kamu butuhkan sebelum menghapus.

### D. Setelah repo private — hal yang berubah
- **Claude tidak bisa clone** repo private. Beri kode ke Claude via **upload ZIP** ke chat.
- GitHub Actions **tetap jalan** di repo private (ada kuota menit gratis; untuk akun
  personal Free biasanya cukup, cek Settings → Billing kalau build sering).
- Artifact & Releases tetap berfungsi, tapi hanya bisa diakses oleh kamu/kolaborator.
- Untuk membagikan aplikasi ke user tanpa membuka source: pakai **Releases** dan bagikan
  file `.zip` hasil build-nya saja (bukan link repo).
