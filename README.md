# MASTERINGAUDS 🎛️

**MASTERINGAUDS** adalah sebuah **Audio Mastering Suite** (Aplikasi Pemrosesan dan Mastering Audio) otomatis yang dapat diakses melalui antarmuka web dan Command Line Interface (CLI). Aplikasi ini dibangun untuk membantu musisi atau *audio engineer* dalam mengonversi, menganalisis, serta me-mastering trek audio agar memenuhi standar kualitas dan *loudness* (LUFS) platform streaming.

## 🛠️ Teknologi Utama
- **Backend:** Python dengan **Flask** (untuk Web Server & API).
- **Audio Processing Libraries:**
  - `numpy` & `scipy`: Komputasi matematis dan sinyal.
  - `librosa`: Analisis musik dan pemrosesan sinyal.
  - `soundfile` & `pydub`: I/O dan manipulasi format audio.
  - `pyloudnorm`: Pengukuran dan standardisasi kekerasan suara (LUFS).

## ✨ Fitur Utama
1. **Multi-Format Support:** Mendukung pemrosesan untuk ekstensi file `mp3`, `wav`, `flac`, `ogg`, `aiff`, dan `m4a`.
2. **Audio Conversion:** Mengonversi format audio (misalnya MP3 ke WAV) dengan opsi otomatis untuk mendeteksi dan menghapus frekuensi *watermark*.
3. **Automated Mixing:** Melakukan *mixing* audio berbasis pengaturan dan parameter spesifik.
4. **Smart Auto-Mastering:**
   - **Genre-Aware:** Menyesuaikan EQ dan Dynamics berdasarkan *genre* musik (Pop, Rock, EDM, dll).
   - **Platform-Ready:** Menyesuaikan target *Loudness* (LUFS) agar mematuhi standar platform *streaming* seperti Spotify.
5. **Audio Analysis:** Ekstraksi data audio dan pengukuran LUFS akurat.
6. **Background Task & Progress Tracking:** Pemrosesan audio intensif berjalan di *background thread* tanpa memblokir aplikasi, dilengkapi dengan pelacakan persentase *progress* secara *real-time*.
7. **Sistem Preset:** Mendukung *preset* kustom berbasis JSON untuk konfigurasi *mixing* dan *mastering*.

## 🚀 Cara Menjalankan

### Melalui Web UI
Jalankan perintah berikut di dalam environment Python Anda:
```bash
python app.py
```
Aplikasi akan berjalan secara lokal pada `http://localhost:5000`.

### Melalui Command Line Interface (CLI)
Anda juga bisa menggunakan alat ini tanpa Web UI melalui file CLI:
```bash
python cli.py --help
```
