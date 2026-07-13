/* Analyzer Panel — Tonal Balance (ala iZotope) + Spectrum (ala APU),
   bersebelahan di bawah kolom Master. */
(() => {
    window.AnalyzerPanel = {
        data: null, liveRaf: 0,

        async run(filepath) {
            this.lastFilepath = filepath;
            try {
                const genre = document.getElementById('masterGenre')?.value || 'pop';
                const r = await fetch('/api/analyze', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath, genre }),
                });
                const a = await r.json();
                if (a.error) return;
                this.data = a;
                this.render(a);
            } catch (e) { /* opsional */ }
        },

        render(a) {
            const card = document.getElementById('masterAnalyzerCard');
            if (card) card.style.display = 'block';
            this.drawTonal(a.tonal_zones || []);
            this.drawSpectrum(a.spectrum || []);
            this.drawMetrics(a);
            this.drawIssues(a.issues || []);
        },

        // ---- Tonal Balance: 4 zona dengan target range (gaya iZotope) ----
        // Live-drive dari player: bins = getByteFrequencyData (0..255)
        feedLive(bins, sampleRate) {
            const nyq = sampleRate / 2;
            const binHz = nyq / bins.length;

            // --- spectrum log 96 titik, dihaluskan (rata-rata dalam rentang bin) ---
            const N = 96;
            const logBins = [];
            for (let i = 0; i < N; i++) {
                const fLo = 20 * Math.pow(1000, (i - 0.5) / (N - 1));
                const fHi = 20 * Math.pow(1000, (i + 0.5) / (N - 1));
                let b0 = Math.max(0, Math.floor(fLo / nyq * bins.length));
                let b1 = Math.min(bins.length - 1, Math.ceil(fHi / nyq * bins.length));
                if (b1 < b0) b1 = b0;
                let sum = 0;
                for (let b = b0; b <= b1; b++) sum += bins[b];
                const avg = sum / (b1 - b0 + 1);
                logBins.push((avg / 255) * 66 - 66);   // -> dB (-66..0), rata-rata bukan puncak
            }
            this.drawSpectrum(this.data?.spectrum, logBins);

            // --- Tonal balance: level per zona dalam dBFS-konsisten ---
            // Magnitudo byte (0..255) -> perkiraan amplitudo linear -> dBFS.
            // Kalibrasi TETAP (tidak bergantung source) supaya reference & master
            // terbaca pada frame yang sama dengan target.
            const zoneDefs = [['low',20,120],['low_mid',120,1000],['high_mid',1000,6000],['high',6000,20000]];
            // Kompensasi slope (+3dB/oktaf tilt relatif 1kHz): musik alami turun
            // ~-4.5dB/okt sehingga low selalu tampak jauh lebih tinggi. Tilt ini
            // menormalkan agar materi seimbang terbaca RATA antar zona, seperti
            // tonal balance ber-referensi pink noise.
            const zoneCenterHz = { low: 70, low_mid: 350, high_mid: 2500, high: 11000 };
            const zonesOut = zoneDefs.map(([name, lo, hi]) => {
                let sum = 0, cnt = 0;
                const b0 = Math.floor(lo / binHz), b1 = Math.min(bins.length - 1, Math.ceil(hi / binHz));
                for (let b = b0; b <= b1; b++) {
                    const aDb = (bins[b] / 255) * 100 - 100;   // byte -> -100..0 dB
                    const lin = Math.pow(10, aDb / 20);
                    sum += lin * lin; cnt++;
                }
                const rms = Math.sqrt(sum / Math.max(1, cnt));
                let level = 20 * Math.log10(rms + 1e-9);
                level += Math.log2(zoneCenterHz[name] / 1000) * 4.5;   // tilt
                const st = (this.data?.tonal_zones || []).find(z => z.zone === name) || {};
                const tlo = st.target_low ?? -29, thi = st.target_high ?? -20;
                return { zone: name, level: level, target_low: tlo, target_high: thi,
                         status: level < tlo ? 'low' : (level > thi ? 'high' : 'ok'), live: true };
            });
            this.drawTonal(zonesOut);
            this.setLive(true);
        },

        setLive(on) {
            const d = document.getElementById('analyzerLive');
            if (d) d.classList.toggle('on', on);
            clearTimeout(this._liveTimer);
            if (on) this._liveTimer = setTimeout(() => this.setLive(false), 400);
        },

        drawTonal(zones) {
            const c = document.getElementById('tonalBalance');
            if (!c) return;
            // label genre target aktif
            const gen = document.getElementById('masterGenre')?.value || 'pop';
            const lbl = c.parentElement.querySelector('.section-label');
            if (lbl) lbl.innerHTML = 'Tonal Balance <span class="tb-genre">' + gen + ' target</span>';
            const w = c.parentElement.clientWidth - 4, h = 150;
            c.width = w; c.height = h;
            const g = c.getContext('2d');
            g.clearRect(0, 0, w, h);
            const labels = { low: 'Low', low_mid: 'Low-Mid', high_mid: 'High-Mid', high: 'High' };
            const n = zones.length || 4;
            const zw = w / n;
            const dbToY = db => h - ((db + 42) / 42) * (h - 24) - 4;   // -60..0 dBFS

            zones.forEach((z, i) => {
                const x = i * zw;
                // target range (band gelap)
                const yTop = dbToY(z.target_high), yBot = dbToY(z.target_low);
                g.fillStyle = 'rgba(80, 200, 220, 0.12)';
                g.fillRect(x + 4, yTop, zw - 8, yBot - yTop);
                g.strokeStyle = 'rgba(80, 200, 220, 0.35)';
                g.strokeRect(x + 4, yTop, zw - 8, yBot - yTop);

                // bar level aktual
                const yLvl = dbToY(z.level);
                const col = z.status === 'ok' ? '#3fd0c8'
                          : z.status === 'high' ? '#ff4053' : '#e8b23c';
                g.fillStyle = col;
                g.fillRect(x + 4, yLvl, zw - 8, h - 20 - yLvl);
                // garis level
                g.fillStyle = '#fff';
                g.fillRect(x + 4, yLvl - 1, zw - 8, 2);

                // label
                g.fillStyle = 'rgba(255,255,255,.6)'; g.font = '9px sans-serif';
                g.textAlign = 'center';
                g.fillText(labels[z.zone] || z.zone, x + zw / 2, h - 5);
                // pemisah zona
                if (i) { g.strokeStyle = 'rgba(255,255,255,.08)'; g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h - 16); g.stroke(); }
            });
            g.textAlign = 'left';
        },

        // ---- Spectrum: kurva log 20Hz..20kHz (gaya APU) ----
        drawSpectrum(spec, liveBins) {
            const c = document.getElementById('spectrumAnalyzer');
            if (!c) return;
            const w = c.parentElement.clientWidth - 4, h = 150;
            c.width = w; c.height = h;
            const g = c.getContext('2d');
            g.clearRect(0, 0, w, h);

            // grid garis frekuensi
            g.strokeStyle = 'rgba(255,255,255,.07)'; g.font = '8px monospace';
            g.fillStyle = 'rgba(255,255,255,.3)';
            [100, 1000, 10000].forEach(f => {
                const x = (Math.log10(f / 20) / Math.log10(20000 / 20)) * w;
                g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h - 12); g.stroke();
                g.fillText(f >= 1000 ? (f/1000) + 'k' : f, x + 2, h - 3);
            });

            const bins = liveBins || spec;
            if (!bins || !bins.length) return;
            const floor = -78, ceil = 6;   // headroom atas agar puncak tak mentok
            const span = ceil - floor;
            g.beginPath();
            bins.forEach((db, i) => {
                const x = (i / (bins.length - 1)) * w;
                const cl = Math.max(floor, Math.min(ceil, db));
                const y = (h - 12) - ((cl - floor) / span) * (h - 20);
                i === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
            });
            g.lineTo(w, h - 12); g.lineTo(0, h - 12); g.closePath();
            const grad = g.createLinearGradient(0, 0, 0, h);
            grad.addColorStop(0, 'rgba(90, 180, 230, 0.5)');
            grad.addColorStop(1, 'rgba(90, 180, 230, 0.05)');
            g.fillStyle = grad; g.fill();
            g.strokeStyle = '#6ab0e0'; g.lineWidth = 1.5;
            g.stroke();
        },

        // Live spectrum saat preview jalan (dipanggil Preview loop)
        drawLiveSpectrum(bins) {
            this.drawSpectrum(this.data?.spectrum, bins);
        },

        drawMetrics(a) {
            const el = document.getElementById('analyzerMetrics');
            if (!el) return;
            const m = [];
            if (a.lufs !== undefined) m.push(['Integrated LUFS', a.lufs.toFixed(1)]);
            if (a.crest_factor !== undefined) m.push(['Crest Factor', a.crest_factor.toFixed(1) + ' dB']);
            if (a.true_peak !== undefined) m.push(['True Peak', a.true_peak.toFixed(1) + ' dBTP']);
            if (a.dc_offset !== undefined) m.push(['DC Offset', a.dc_offset.toFixed(4)]);
            el.innerHTML = m.map(([k, v]) =>
                `<div class="metric"><span class="metric-k">${k}</span><span class="led-win">${v}</span></div>`).join('');
        },

        drawIssues(issues) {
            const el = document.getElementById('analyzerIssues');
            if (!el) return;
            el.innerHTML = issues.length
                ? issues.map(i => `<div class="issue"><span class="issue-dot"></span>${i.message || i}</div>`).join('')
                : '<div class="issue-ok">No major issues detected — clean source.</div>';
        },
    };
})();
