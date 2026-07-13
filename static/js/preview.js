/* Preview v2 — Live audition rantai Pre-Master via Web Audio API.
   - Crossover Linkwitz-Riley 24 dB/okt (jumlah band flat, tanpa phase-cancel)
   - Kompensasi auto-makeup DynamicsCompressor agar level & tonal jujur
   - Band EQ dinamis mengikuti UI (ujung = shelf, 12k/16k terdengar)
   - Monitor: IN (source) / OUT (processed) / REF (reference track)
   - Spectrum analyzer, meter per-band + GR, output meter */
(() => {
    window.Preview = {
        ctx: null, buffer: null, refBuffer: null, refGainVal: 1,
        src: null, refSrc: null, nodes: null,
        playing: false, monitor: 'out', raf: 0,
        // Trim global OUT agar loudness preview cocok dgn render Python.
        // Dikalibrasi empiris lintas beberapa setting compressor: selisih < 1 dB.
        // (render Python: makeup_db=0 + faktor 0.8; WebAudio: auto-makeup internal
        //  bikin OUT ~10 dB lebih keras, jadi ditrim ke 0.302 agar setara.)
        OUT_TRIM: 0.302,

        init() {
            document.getElementById('btnPreview')?.addEventListener('click', () => this.toggle());
            ['In', 'Out', 'Ref'].forEach(m => {
                document.getElementById('btnMon' + m)?.addEventListener('click', () => this.setMonitor(m.toLowerCase()));
            });
            document.getElementById('btnRefLoad')?.addEventListener('click', () =>
                document.getElementById('refFileInput')?.click());
            document.getElementById('refFileInput')?.addEventListener('change', e => this.loadRef(e.target.files[0]));

            document.addEventListener('input', e => {
                if (!this.playing || !this.nodes) return;
                const t = e.target;
                if (!t || t.type !== 'range') return;
                if (t.dataset && t.dataset.freq) this.applyEq();
                else if (/^comp(Low|Mid|High)/.test(t.id)) this.applyComp();
                else if (['masterStereoWidth', 'mixMidGain', 'mixSideGain'].includes(t.id)) this.applyStereo();
            });
        },

        eqBands() {
            const keys = (typeof Equalizer !== 'undefined' && Equalizer.gains)
                ? Object.keys(Equalizer.gains).map(Number) : [];
            const set = new Set(keys.concat([64, 125, 250, 500, 1000, 2000, 4000, 8000, 12000, 16000]));
            return [...set].sort((a, b) => a - b);
        },

        async load() {
            const url = (typeof Player !== 'undefined') && Player.originalUrl;
            if (!url) { App.notify('Upload audio first to preview', 'error'); return false; }
            if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
            if (this.ctx.state === 'suspended') await this.ctx.resume();
            if (!this.buffer || this._bufUrl !== url) {
                const resp = await fetch(url);
                this.buffer = await this.ctx.decodeAudioData(await resp.arrayBuffer());
                this._bufUrl = url;
            }
            return true;
        },

        // EQ matching: bandingkan tonal balance source vs reference.
        // Source dianalisis di server; reference (buffer lokal) di sini.
        async matchReferenceEq(sourceFilepath) {
            if (!this.refFileObj) throw new Error('no reference');
            // Analisis PRESISI di backend (FFT resolusi tinggi), bukan aproksimasi browser.
            const strength = (window.__matchStrength != null) ? window.__matchStrength : 0.6;
            const fd = new FormData();
            fd.append('reference', this.refFileObj);
            fd.append('filepath', sourceFilepath);
            fd.append('strength', String(strength));
            const r = await fetch('/api/match_reference', { method: 'POST', body: fd });
            const j = await r.json();
            if (j.error) throw new Error(j.error);
            // simpan kurva untuk kemungkinan tampil
            this._lastMatch = j;
            const gains = {};
            Object.entries(j.eq_gains || {}).forEach(([f, v]) => gains[f] = v);
            return gains;
        },

        _bufferCurve(buf) {
            // FFT sederhana per band via time-domain RMS pada band-pass kasar.
            // Cukup untuk matching tonal; pakai OfflineAudioContext + analyser.
            const BANDS = [64, 125, 250, 500, 1000, 2000, 4000, 8000, 12000, 16000];
            const data = buf.getChannelData(0);
            const N = 16384;
            const seg = data.subarray(0, Math.min(N, data.length));
            // DFT magnitudo (real) sederhana pada N titik
            const re = new Float32Array(N), im = new Float32Array(N);
            for (let i = 0; i < seg.length; i++) re[i] = seg[i] * (0.5 - 0.5*Math.cos(2*Math.PI*i/N));
            // gunakan FFT via AnalyserNode lebih murah: buat offline
            // (fallback: estimasi energi per band lewat goertzel di center freq)
            const sr = buf.sampleRate;
            const curve = BANDS.map(f => {
                // Goertzel pada center freq -> magnitudo
                const k = Math.round(N * f / sr);
                const wq = 2 * Math.PI * k / N;
                const cw = Math.cos(wq), coeff = 2 * cw;
                let s0 = 0, s1 = 0, s2 = 0;
                for (let i = 0; i < seg.length; i++) { s0 = re[i] + coeff*s1 - s2; s2 = s1; s1 = s0; }
                const mag = Math.sqrt(s1*s1 + s2*s2 - coeff*s1*s2);
                return 20 * Math.log10(mag + 1e-9);
            });
            const mean = curve.reduce((a,b)=>a+b,0) / curve.length;
            const rel = {};
            BANDS.forEach((f,i)=> rel[f] = curve[i] - mean);
            return rel;
        },

        async loadRef(file) {
            if (!file) return;
            this.refFileObj = file;   // simpan File asli untuk analisis backend presisi
            try {
                if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
                const buf = await file.arrayBuffer();
                this.refBuffer = await this.ctx.decodeAudioData(buf);
                // Loudness match kasar: samakan RMS referensi dengan source
                const rms = b => {
                    const d = b.getChannelData(0);
                    let s = 0, step = Math.max(1, Math.floor(d.length / 200000));
                    let n = 0;
                    for (let i = 0; i < d.length; i += step) { s += d[i] * d[i]; n++; }
                    return Math.sqrt(s / n) + 1e-9;
                };
                this.refGainVal = this.buffer ? Math.min(4, rms(this.buffer) / rms(this.refBuffer)) : 1;
                document.getElementById('btnMonRef')?.removeAttribute('disabled');
                const lbl = document.getElementById('refName');
                if (lbl) lbl.textContent = file.name;
                App.notify('Reference loaded: ' + file.name, 'success');
                // Reference juga masuk player A/B/R bawah + waveform-nya
                if (typeof Player !== 'undefined' && Player.setReference) {
                    Player.setReference(URL.createObjectURL(file), file.name);
                }
                if (this.playing) this.setMonitor('ref');
            } catch (e) {
                App.notify('Reference load failed: ' + e.message, 'error');
            }
        },

        // ---- Linkwitz-Riley 24 dB/okt: 2x Butterworth Q=0.7071 dirangkai ----
        lr4(type, freq) {
            const c = this.ctx;
            const a = c.createBiquadFilter(); a.type = type; a.frequency.value = freq; a.Q.value = 0.7071;
            const b = c.createBiquadFilter(); b.type = type; b.frequency.value = freq; b.Q.value = 0.7071;
            a.connect(b);
            return { in: a, out: b };
        },

        buildGraph() {
            const c = this.ctx;
            const n = {};
            n.input = c.createGain();

            // --- EQ dinamis: shelf di ujung, peaking di tengah ---
            const bands = this.eqBands();
            n.eqBandList = bands;
            n.eq = bands.map((f, i) => {
                const b = c.createBiquadFilter();
                if (i === 0) { b.type = 'lowshelf'; }
                else if (i === bands.length - 1) { b.type = 'highshelf'; }
                else { b.type = 'peaking'; b.Q.value = 1.3; }
                b.frequency.value = f; b.gain.value = 0;
                return b;
            });
            n.eq.reduce((a, b) => (a.connect(b), b), n.input);
            const eqOut = n.eq[n.eq.length - 1];

            // --- Crossover KOMPLEMENTER (subtraktif) — rekonstruksi flat sempurna ---
            // low  = LP(200)
            // mid  = LP(3000) - LP(200)
            // high = input     - LP(3000)
            // Jumlah low+mid+high == input persis (0 dB ripple), jadi sinyal TENGAH
            // (snare, vokal mono) tidak pernah ter-cancel / ter-boost di titik crossover.
            // Tiap band tetap punya .in (satu titik feed) & .out utk comp/makeup/analyser.
            const lpLow = this.lr4('lowpass', 200);
            const lpMid = this.lr4('lowpass', 3000);
            n._lpLow = lpLow; n._lpMid = lpMid;

            // low band
            const lowOut = c.createGain();
            lpLow.out.connect(lowOut);
            n.low = { in: lpLow.in, out: lowOut };

            // mid band = lpMid - lpLow
            const midOut = c.createGain();
            const midNegLow = c.createGain(); midNegLow.gain.value = -1;
            lpMid.out.connect(midOut);
            lpLow.out.connect(midNegLow); midNegLow.connect(midOut);
            n.mid = { in: lpMid.in, out: midOut, _feedFrom: 'shared' };

            // high band = input - lpMid
            const highOut = c.createGain();
            const highNegMid = c.createGain(); highNegMid.gain.value = -1;
            lpMid.out.connect(highNegMid); highNegMid.connect(highOut);
            n.high = { in: null, out: highOut, _feedFrom: 'input+lpMid' };

            n.comps = [0, 1, 2].map(() => c.createDynamicsCompressor());
            n.makeup = [0, 1, 2].map(() => c.createGain());     // kompensasi auto-makeup
            n.bandAnalysers = [0, 1, 2].map(() => { const a = c.createAnalyser(); a.fftSize = 512; return a; });
            n.sum = c.createGain();

            // Feed filter komplementer dari eqOut sekali saja:
            eqOut.connect(lpLow.in);
            eqOut.connect(lpMid.in);
            eqOut.connect(highOut);   // komponen 'input' untuk high = eqOut (dikurangi lpMid)

            // Rangkai tiap band -> comp -> makeup -> analyser -> sum
            [n.low, n.mid, n.high].forEach((b, i) => {
                b.out.connect(n.comps[i]);
                n.comps[i].connect(n.makeup[i]);
                n.makeup[i].connect(n.bandAnalysers[i]);
                n.bandAnalysers[i].connect(n.sum);
            });

            // --- Trim global agar loudness OUT preview == render Python ---
            n.outTrim = c.createGain();
            n.outTrim.gain.value = this.OUT_TRIM;
            n.sum.connect(n.outTrim);

            // --- Stereo width (M/S) ---
            n.split = c.createChannelSplitter(2);
            n.merge = c.createChannelMerger(2);
            n.mL1 = c.createGain(); n.mL2 = c.createGain();
            n.mR1 = c.createGain(); n.mR2 = c.createGain();
            n.outTrim.connect(n.split);
            n.split.connect(n.mL1, 0); n.split.connect(n.mL2, 1);
            n.split.connect(n.mR1, 0); n.split.connect(n.mR2, 1);
            n.mL1.connect(n.merge, 0, 0); n.mL2.connect(n.merge, 0, 0);
            n.mR1.connect(n.merge, 0, 1); n.mR2.connect(n.merge, 0, 1);

            // --- Monitor routing: dry (IN) vs wet (OUT) vs ref ---
            n.wet = c.createGain(); n.dry = c.createGain(); n.refGain = c.createGain();
            n.spec = c.createAnalyser(); n.spec.fftSize = 4096; n.spec.smoothingTimeConstant = 0.82;
            n.merge.connect(n.wet);
            n.input.connect(n.dry);            // sinyal source tanpa proses
            n.wet.connect(n.spec); n.dry.connect(n.spec); n.refGain.connect(n.spec);
            n.spec.connect(c.destination);

            this.nodes = n;
            this.applyEq(); this.applyComp(); this.applyStereo();
            this.setMonitor(this.monitor, true);
        },

        applyEq() {
            const n = this.nodes; if (!n) return;
            const gains = (typeof Equalizer !== 'undefined' && Equalizer.getGains) ? Equalizer.getGains() : {};
            n.eq.forEach((b, i) => {
                const f = n.eqBandList[i];
                const g = parseFloat(gains[f] ?? gains[String(f)] ?? 0);
                b.gain.setTargetAtTime(isFinite(g) ? g : 0, this.ctx.currentTime, 0.02);
            });
        },
        applyComp() {
            const n = this.nodes; if (!n) return;
            const v = id => parseFloat(document.getElementById(id)?.value);
            [['Low', 0], ['Mid', 1], ['High', 2]].forEach(([nm, i]) => {
                const cp = n.comps[i], t = this.ctx.currentTime;
                const thr = v(`comp${nm}Thresh`); const ratio = v(`comp${nm}Ratio`) || 2;
                cp.threshold.setTargetAtTime(isFinite(thr) ? thr : -20, t, 0.02);
                cp.ratio.setTargetAtTime(ratio, t, 0.02);
                cp.attack.setTargetAtTime((v(`comp${nm}Attack`) || 8) / 1000, t, 0.02);
                cp.release.setTargetAtTime((v(`comp${nm}Release`) || 60) / 1000, t, 0.02);
                cp.knee.value = 6;
                // Makeup dinetralkan ke UNITY (1.0). Auto-makeup internal WebAudio
                // + makeup tambahan dulu bikin preview OUT ~5.6 dB lebih keras
                // daripada hasil render Python (yang makeup_db=0 lalu dikali 0.8).
                // Level dicocokkan ke render lewat n.outTrim global di bawah.
                n.makeup[i].gain.setTargetAtTime(1.0, t, 0.02);
            });
            // Cocokkan loudness preview OUT dengan render Python (faktor 0.8 = -1.94 dB)
            if (n.outTrim) n.outTrim.gain.setTargetAtTime(this.OUT_TRIM, this.ctx.currentTime, 0.02);
        },
        applyStereo() {
            const n = this.nodes; if (!n) return;
            const wPct = parseFloat(document.getElementById('masterStereoWidth')?.value || '110');
            const sideDb = parseFloat(document.getElementById('mixSideGain')?.value || '0');
            const midDb = parseFloat(document.getElementById('mixMidGain')?.value || '0');
            const w = (wPct / 100) * Math.pow(10, sideDb / 20);
            const mid = Math.pow(10, midDb / 20);
            const a = (mid + w) / 2, b = (mid - w) / 2, t = this.ctx.currentTime;
            n.mL1.gain.setTargetAtTime(a, t, 0.02);
            n.mL2.gain.setTargetAtTime(b, t, 0.02);
            n.mR1.gain.setTargetAtTime(b, t, 0.02);
            n.mR2.gain.setTargetAtTime(a, t, 0.02);
        },

        setMonitor(mode, silent) {
            if (mode === 'ref' && !this.refBuffer) { App.notify('Load a reference track first', 'error'); return; }
            this.monitor = mode;
            ['in', 'out', 'ref'].forEach(m => {
                document.getElementById('btnMon' + m[0].toUpperCase() + m.slice(1))
                    ?.classList.toggle('active', m === mode);
            });
            const n = this.nodes; if (!n) return;
            const t = this.ctx.currentTime, T = 0.015;
            n.wet.gain.setTargetAtTime(mode === 'out' ? 1 : 0, t, T);
            n.dry.gain.setTargetAtTime(mode === 'in' ? 1 : 0, t, T);
            n.refGain.gain.setTargetAtTime(mode === 'ref' ? this.refGainVal : 0, t, T);
            if (mode === 'ref') this.ensureRefPlaying();
        },

        ensureRefPlaying() {
            if (this.refSrc || !this.playing || !this.refBuffer) return;
            this.refSrc = this.ctx.createBufferSource();
            this.refSrc.buffer = this.refBuffer; this.refSrc.loop = true;
            this.refSrc.connect(this.nodes.refGain);
            this.refSrc.start();
        },

        async toggle() {
            if (this.playing) { this.stop(); return; }
            try {
                if (!(await this.load())) return;
                if (typeof Player !== 'undefined' && Player.isPlaying) Player.togglePlay();
                this.buildGraph();
                this.src = this.ctx.createBufferSource();
                this.src.buffer = this.buffer; this.src.loop = true;
                this.src.connect(this.nodes.input);
                this.src.start();
                this.playing = true;
                if (this.monitor === 'ref') this.ensureRefPlaying();
                this.setBtn(true);
                this.loop();
            } catch (e) {
                App.notify('Preview failed: ' + e.message, 'error');
            }
        },

        stop() {
            try { this.src?.stop(); } catch (e) {}
            try { this.refSrc?.stop(); } catch (e) {}
            this.src = null; this.refSrc = null; this.playing = false;
            cancelAnimationFrame(this.raf);
            this.setBtn(false);
            this.clearVisuals();
        },

        setBtn(on) {
            const b = document.getElementById('btnPreview');
            if (b) { b.classList.toggle('active', on); b.innerHTML = on ? '&#9632; Stop Preview' : '&#9654; Live Preview'; }
        },

        loop() {
            if (!this.playing) return;
            this.drawSpectrum();
            this.drawBandMeters();
            this.drawOutputMeter();
            this.raf = requestAnimationFrame(() => this.loop());
        },

        drawSpectrum() {
            // umpan spektrum live ke Analyzer Panel (Spectrum bawah Master)
            if (typeof AnalyzerPanel !== 'undefined' && this.nodes) {
                const n = this.nodes.spec;
                const bins = new Uint8Array(n.frequencyBinCount);
                n.getByteFrequencyData(bins);
                const nyq = this.ctx.sampleRate / 2;
                const logBins = [];
                for (let i = 0; i < 96; i++) {
                    const f = 20 * Math.pow(1000, i / 95);
                    const bi = Math.min(bins.length - 1, Math.round(f / nyq * bins.length));
                    logBins.push((bins[bi] / 255) * 72 - 72);   // -> dB range
                }
                AnalyzerPanel.drawLiveSpectrum(logBins);
            }
            const canvas = document.getElementById('eqSpectrum');
            const n = this.nodes; if (!canvas || !n) return;
            const host = canvas.parentElement.getBoundingClientRect();
            canvas.width = host.width - 8; canvas.height = 200;
            const g = canvas.getContext('2d');
            g.clearRect(0, 0, canvas.width, canvas.height);
            const bins = new Uint8Array(n.spec.frequencyBinCount);
            n.spec.getByteFrequencyData(bins);
            const nyq = this.ctx.sampleRate / 2, fMin = 20, fMax = 20000;
            g.beginPath();
            for (let x = 0; x <= canvas.width; x += 2) {
                const f = fMin * Math.pow(fMax / fMin, x / canvas.width);
                const bin = Math.min(bins.length - 1, Math.round(f / nyq * bins.length));
                const y = canvas.height - (bins[bin] / 255) * canvas.height;
                x === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
            }
            g.lineTo(canvas.width, canvas.height); g.lineTo(0, canvas.height); g.closePath();
            const grad = g.createLinearGradient(0, 0, 0, canvas.height);
            grad.addColorStop(0, 'rgba(255, 32, 56, 0.5)');
            grad.addColorStop(1, 'rgba(255, 32, 56, 0.05)');
            g.fillStyle = grad; g.fill();
        },

        drawBandMeters() {
            const n = this.nodes; if (!n) return;
            ['meterLow', 'meterMid', 'meterHigh'].forEach((id, i) => {
                const el = document.getElementById(id); if (!el) return;
                const buf = new Float32Array(n.bandAnalysers[i].fftSize);
                n.bandAnalysers[i].getFloatTimeDomainData(buf);
                let s = 0; for (let k = 0; k < buf.length; k++) s += buf[k] * buf[k];
                const db = 20 * Math.log10(Math.sqrt(s / buf.length) + 1e-9);
                el.style.setProperty('--lvl', Math.max(0, Math.min(1, (db + 48) / 48)));
                const gr = n.comps[i].reduction || 0;
                const grEl = document.getElementById(id + 'Gr');
                if (grEl) grEl.textContent = gr < -0.5 ? gr.toFixed(1) + ' dB' : '—';
            });
        },

        drawOutputMeter() {
            const n = this.nodes; if (!n) return;
            const buf = new Float32Array(n.spec.fftSize);
            n.spec.getFloatTimeDomainData(buf);
            let peak = 0; for (let k = 0; k < buf.length; k++) peak = Math.max(peak, Math.abs(buf[k]));
            const db = 20 * Math.log10(peak + 1e-9);
            document.getElementById('outMeter')?.style.setProperty('--lvl', Math.max(0, Math.min(1, (db + 36) / 36)));
            const lbl = document.getElementById('outMeterDb');
            if (lbl) lbl.textContent = (db > -35 ? db.toFixed(1) : '-inf') + ' dB';
        },

        clearVisuals() {
            const c = document.getElementById('eqSpectrum');
            if (c) c.getContext('2d').clearRect(0, 0, c.width, c.height);
            ['meterLow', 'meterMid', 'meterHigh', 'outMeter'].forEach(id =>
                document.getElementById(id)?.style.setProperty('--lvl', 0));
        },
    };

    document.addEventListener('DOMContentLoaded', () => Preview.init());
})();
