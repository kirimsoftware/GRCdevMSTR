(() => {
    window.Player = {
        audioEl: null,
        currentSource: 'original',
        originalUrl: null,
        processedUrl: null,
        isPlaying: false,
        // cache waveform peaks per-URL supaya tidak decode ulang saat A/B
        peaksCache: {},

        init() {
            this.audioEl = new Audio();

            this.audioEl.addEventListener('timeupdate', () => this.updateTime());
            this.audioEl.addEventListener('ended', () => this.onEnded());
            this.audioEl.addEventListener('loadedmetadata', () => this.updateTime());

            document.getElementById('btnPlay')?.addEventListener('click', () => this.togglePlay());
            document.getElementById('btnAbOriginal')?.addEventListener('click', () => this.switchSource('original'));
            document.getElementById('btnAbProcessed')?.addEventListener('click', () => this.switchSource('processed'));
            document.getElementById('btnAbRef')?.addEventListener('click', () => this.switchSource('reference'));
            document.getElementById('playerVolume')?.addEventListener('input', e => {
                this.audioEl.volume = e.target.value / 100;
            });
            // klik waveform untuk seek
            const wf = document.getElementById('playerWaveform');
            wf?.addEventListener('click', e => {
                if (!this.audioEl.duration) return;
                const rect = wf.getBoundingClientRect();
                this.audioEl.currentTime = ((e.clientX - rect.left) / rect.width) * this.audioEl.duration;
            });

            this.animate();
        },

        setOriginal(url, filename) {
            this.originalUrl = url;
            if (filename) {
                const el = document.getElementById('playerFilename');
                if (el) el.textContent = filename;
            }
            this.decodeAndDrawPeaks(url);
            // otomatis muat original saat upload agar A langsung bisa diputar
            if (!this.processedUrl) this.switchSource('original');
        },

        setReference(url, name) {
            this.referenceUrl = url;
            document.getElementById('btnAbRef')?.removeAttribute('disabled');
            this.decodeAndDrawPeaks(url);
            if (name) App.notify('Reference in player: ' + name, 'success');
        },

        setProcessed(url) {
            this.processedUrl = url;
            this.decodeAndDrawPeaks(url);
            this.switchSource('processed');
        },

        switchSource(src) {
            const url = src === 'original' ? this.originalUrl
                : src === 'reference' ? this.referenceUrl
                : this.processedUrl;
            if (!url) return;

            const wasPlaying = this.isPlaying;
            const t = this.audioEl.currentTime || 0;
            this.currentSource = src;
            this.audioEl.src = url;
            this.audioEl.load();
            // pertahankan posih A/B agar perbandingan adil
            this.audioEl.addEventListener('loadedmetadata', () => {
                if (t && t < this.audioEl.duration) this.audioEl.currentTime = t;
            }, { once: true });

            document.getElementById('btnAbOriginal')?.classList.toggle('active', src === 'original');
            document.getElementById('btnAbProcessed')?.classList.toggle('active', src === 'processed');
            document.getElementById('btnAbRef')?.classList.toggle('active', src === 'reference');

            this.drawWaveform(url);

            if (wasPlaying) {
                this.audioEl.play().then(() => { this.isPlaying = true; this.updatePlayBtn(); }).catch(() => {});
            }
        },

        initMeters() {
            // Analisis playback: RMS, LUFS short-term (K-weighted approx), peak.
            if (this.meterCtx) { this.meterCtx.resume?.(); return; }
            try {
                const C = new (window.AudioContext || window.webkitAudioContext)();
                this.meterCtx = C;
                const src = C.createMediaElementSource(this.audioEl);
                this.an = C.createAnalyser(); this.an.fftSize = 2048;
                src.connect(this.an); this.an.connect(C.destination);
                // analyser FFT besar untuk spectrum + tonal balance live
                this.specAn = C.createAnalyser();
                this.specAn.fftSize = 8192;
                this.specAn.smoothingTimeConstant = 0.8;
                src.connect(this.specAn);
                // K-weighting: shelf +4dB @ ~1.5k + highpass 38Hz (aproksimasi ITU-R BS.1770)
                const hs = C.createBiquadFilter(); hs.type = 'highshelf'; hs.frequency.value = 1500; hs.gain.value = 4;
                const hp = C.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 38; hp.Q.value = 0.5;
                src.connect(hs); hs.connect(hp);
                this.kAn = C.createAnalyser(); this.kAn.fftSize = 2048;
                hp.connect(this.kAn);
                this.lufsWin = [];   // ring buffer mean-square 3 detik
            } catch (e) { /* meter opsional */ }
        },

        updateMeters() {
            if (!this.an || !this.isPlaying) return;
            const buf = new Float32Array(this.an.fftSize);
            this.an.getFloatTimeDomainData(buf);
            let sum = 0, peak = 0;
            for (let i = 0; i < buf.length; i++) { const v = buf[i]; sum += v*v; peak = Math.max(peak, Math.abs(v)); }
            const rmsDb = 10 * Math.log10(sum / buf.length + 1e-12);
            const el = id => document.getElementById(id);
            if (el('pmRms')) el('pmRms').textContent = rmsDb > -70 ? rmsDb.toFixed(1) : '-inf';
            el('pmPeak')?.style.setProperty('--lvl', Math.max(0, Math.min(1, (20*Math.log10(peak+1e-9) + 36) / 36)));

            const kbuf = new Float32Array(this.kAn.fftSize);
            this.kAn.getFloatTimeDomainData(kbuf);
            let ks = 0; for (let i = 0; i < kbuf.length; i++) ks += kbuf[i]*kbuf[i];
            const now = performance.now();
            this.lufsWin.push({ t: now, ms: ks / kbuf.length });
            while (this.lufsWin.length && now - this.lufsWin[0].t > 3000) this.lufsWin.shift();
            const mean = this.lufsWin.reduce((a, b) => a + b.ms, 0) / (this.lufsWin.length || 1);
            const lufs = -0.691 + 10 * Math.log10(mean + 1e-12);
            if (el('pmLufs')) el('pmLufs').textContent = lufs > -70 ? lufs.toFixed(1) : '-inf';

            // Live-drive Source Analyzer (spectrum + tonal balance) dari audio yang diputar
            if (this.specAn && typeof AnalyzerPanel !== 'undefined') {
                const sb = new Uint8Array(this.specAn.frequencyBinCount);
                this.specAn.getByteFrequencyData(sb);
                AnalyzerPanel.feedLive(sb, this.specAn.context.sampleRate);
            }
        },

        togglePlay() {
            if (!this.audioEl.src) return;
            if (typeof Preview !== 'undefined' && Preview.playing) Preview.stop();
            this.initMeters();
            if (this.isPlaying) {
                this.audioEl.pause();
                this.isPlaying = false;
            } else {
                this.audioEl.play().then(() => { this.isPlaying = true; this.updatePlayBtn(); }).catch(() => {});
                this.isPlaying = true;
            }
            this.updatePlayBtn();
        },

        updatePlayBtn() {
            const btn = document.getElementById('btnPlay');
            if (btn) btn.innerHTML = this.isPlaying ? '&#9646;&#9646;' : '&#9654;';
        },

        onEnded() {
            this.isPlaying = false;
            this.updatePlayBtn();
        },

        updateTime() {
            const cur = document.getElementById('playerCurrent');
            const dur = document.getElementById('playerDuration');
            if (cur) cur.textContent = App.formatTime(this.audioEl.currentTime || 0);
            if (dur) dur.textContent = App.formatTime(this.audioEl.duration || 0);
        },

        // --- Waveform ASLI: decode audio -> peaks ---
        async decodeAndDrawPeaks(url) {
            if (this.peaksCache[url]) { this.drawWaveform(url); return; }
            try {
                const resp = await fetch(url);
                const buf = await resp.arrayBuffer();
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const audioBuf = await ctx.decodeAudioData(buf);
                ctx.close();

                const raw = audioBuf.getChannelData(0);
                const barCount = 600;
                const block = Math.floor(raw.length / barCount);
                const peaks = [];
                for (let i = 0; i < barCount; i++) {
                    let max = 0;
                    for (let j = 0; j < block; j++) {
                        const v = Math.abs(raw[i * block + j] || 0);
                        if (v > max) max = v;
                    }
                    peaks.push(max);
                }
                const norm = Math.max(...peaks) || 1;
                this.peaksCache[url] = peaks.map(p => p / norm);
                this.drawWaveform(url);
            } catch (e) {
                // fallback: biarkan kosong, tak menghentikan playback
            }
        },

        drawWaveform(url) {
            const canvas = document.getElementById('waveformCanvas');
            if (!canvas) return;
            const peaks = this.peaksCache[url];
            const dpr = window.devicePixelRatio || 1;
            const w = canvas.parentElement.clientWidth;
            const h = canvas.parentElement.clientHeight || 56;
            canvas.width = w * dpr; canvas.height = h * dpr;
            canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
            const ctx = canvas.getContext('2d');
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            ctx.clearRect(0, 0, w, h);
            if (!peaks) return;

            const progress = this.audioEl.duration
                ? (this.audioEl.currentTime / this.audioEl.duration) : 0;
            const mid = h / 2;
            const played = this.currentSource === 'processed' ? '#ff2038'
                : this.currentSource === 'reference' ? '#e8b23c'
                : '#7ec8ff';
            const dim = this.currentSource === 'processed' ? 'rgba(255,32,56,0.28)'
                : this.currentSource === 'reference' ? 'rgba(232,178,60,0.28)'
                : 'rgba(126,200,255,0.25)';

            // Waveform terisi penuh (mirror atas-bawah) seperti referensi:
            // gambar outline lalu fill, dua warna sesuai progress.
            const drawFilled = (from, to, color) => {
                ctx.beginPath();
                ctx.moveTo(from, mid);
                for (let x = from; x <= to; x++) {
                    const p = peaks[Math.floor(x / w * peaks.length)] || 0;
                    ctx.lineTo(x, mid - p * (mid - 1));
                }
                for (let x = to; x >= from; x--) {
                    const p = peaks[Math.floor(x / w * peaks.length)] || 0;
                    ctx.lineTo(x, mid + p * (mid - 1));
                }
                ctx.closePath();
                ctx.fillStyle = color;
                ctx.fill();
            };
            const px = Math.round(progress * w);
            drawFilled(0, px, played);                 // bagian sudah diputar
            drawFilled(px, w, dim);                     // bagian belum diputar
            // garis playhead
            ctx.strokeStyle = 'rgba(255,255,255,0.5)';
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, h); ctx.stroke();
        },

        animate() {
            this.updateMeters();
            if (this.isPlaying) this.drawWaveform(
                this.currentSource === 'original' ? this.originalUrl
                : this.currentSource === 'reference' ? this.referenceUrl
                : this.processedUrl);
            requestAnimationFrame(() => this.animate());
        },
    };

    document.addEventListener('DOMContentLoaded', () => Player.init());
})();
