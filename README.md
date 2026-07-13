# GRCmasteringStudio

**Professional audio mastering, made simple.** A desktop application that analyzes your
mix and masters it to release-ready standards — with full manual control when you want it.

Created by [@GitaRoni](https://github.com/kirimsoftware) · 2026

---

## What it does

Upload a track, and GRCmasteringStudio analyzes its actual content — dynamics, frequency
balance, stereo image — then applies a mastering chain tuned to *that specific mix*, not a
generic preset. What you hear in preview is exactly what you download: the preview **is**
the rendered master.

Not happy with the result? Adjust the fine-tuning controls and master again. Repeat until
it's right.

---

## Features

### 🎚️ Master
Single-track mastering with a full signal chain and adaptive analysis.

- **Adaptive Analysis** — measures crest factor per band and derives compressor
  thresholds and EQ curves from the material itself
- **Master & Listen workflow** — the rendered master loads straight into the player as
  **OUT (B)**; A/B it against the original **IN (A)** with your ears, on the real file
- **Parametric EQ** — 10-band, custom drag faders
- **Multiband Compressor** — low / mid / high, custom knobs
- **Image & Transients** — mid/side gain, attack/sustain shaping
- **Match Reference** — import a reference master and mirror its EQ curve
- **Output formats** — 44.1 / 48 / 88.2 / 96 kHz · 24-bit or 16-bit (TPDF dithered)
- **Platform targets** — Spotify, Apple Music, YouTube (LUFS-normalized)
- **Brickwall limiting** with true-peak ceiling control

### 💿 Album
Master a full album (up to 15 tracks) in one pass.

- Each track is analyzed and mastered **according to its own mix** (adaptive per track)
- Optional shared Fine Tuning across all tracks for a consistent album sound
- Live progress per track with status feedback and per-track retry
- Click any track to preview it in the player (A/B)
- **Download WAV** (individual files) or **Download ZIP** (whole album, written
  server-side for integrity)

### 🔄 Convert
Format conversion with mastering-grade handling.

- WAV 24-bit · WAV 16-bit · FLAC · MP3
- Sample rate follows the format (WAV/FLAC: 44.1–96 kHz · MP3: 44.1/48 kHz)
- **TPDF dither** applied when converting down to 16-bit — masks quantization
  distortion instead of truncating it
- Optional LUFS normalization, air enhancement, watermark removal

---

## Signal chain

```
Decode → Adaptive Analysis → Input Gain → Parametric EQ → Multiband Compressor
       → Mid/Side & Transients → Bass Mono → Stereo Enhance
       → TPDF Dither → LUFS Normalize → Brickwall Limiter → Write
```

Every stage is measurable and adjustable. Adaptive analysis only fills in what you
haven't set manually — **your Fine Tuning values always win.**

---

## Download

Prebuilt applications are available under **[Releases](../../releases)** and in
**[Actions](../../actions)** artifacts.

| Platform | File | Requirements |
|---|---|---|
| **macOS (Apple Silicon)** | `GRCmasteringStudio-macos-applesilicon.zip` | macOS 11 Big Sur or later · M1/M2/M3/M4 |
| **macOS (Intel)** | `GRCmasteringStudio-macos-intel.zip` | macOS 11 Big Sur or later · Intel |
| **Windows** | `GRCmasteringStudio-windows.zip` | Windows 10/11 (64-bit) |

**Which Mac do I have?**  → About This Mac → look at *Chip* / *Processor*.
"Apple M…" → Apple Silicon · "Intel Core…" → Intel.

> Windows may require the **WebView2 runtime** (preinstalled on Windows 11).

---

## Tech

- **Backend** — Python · Flask · NumPy · SciPy · librosa · soundfile · pyloudnorm
- **Frontend** — Web Audio API · custom CSS controls (no native inputs, so rendering is
  identical across WebKit and Chromium)
- **Desktop shell** — pywebview (WKWebView on macOS, WebView2 on Windows)
- **Packaging** — PyInstaller via GitHub Actions (macOS arm64 + x86_64, Windows x64)
- **Licensing** — offline Ed25519 signature verification, bound to hardware ID

---

## Development

```bash
pip install -r requirements.txt
python app.py          # dev server
python desktop.py      # desktop window
```

A valid license key is required for rendering. The application ships with the **public
key only** — it can verify licenses but cannot create them.

---

## License & ownership

Proprietary. All rights reserved.
This source code is private and not licensed for redistribution or derivative works.

**Created by @GitaRoni · 2026**
