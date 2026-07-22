(() => {
    window.Uploader = {
        files: {},
        pollIntervals: {},

        init() {
            this.bindTabUpload('convert', 'fileInput', 'dropZone', 'fileInfo', 'fileName', 'fileSize', 'btnRemoveFile', 'btnConvert');
            this.bindTabUpload('mix', 'mixFileInput', 'mixDropZone', 'mixFileInfo', 'mixFileName', 'mixFileSize', 'btnMixRemoveFile', 'btnMix');
            this.bindTabUpload('master', 'masterFileInput', 'masterDropZone', 'masterFileInfo', 'masterFileName', 'masterFileSize', 'btnMasterRemoveFile', 'btnMaster');

            this.bindChainBadges();
            this.bindEqButtons();

            document.getElementById('btnConvert')?.addEventListener('click', () => this.startConvert());
            document.getElementById('btnMix')?.addEventListener('click', () => this.startMix());
            document.getElementById('btnMaster')?.addEventListener('click', () => this.startMaster());
        },

        bindTabUpload(tab, inputId, zoneId, infoId, nameId, sizeId, removeId, btnId) {
            const input = document.getElementById(inputId);
            const zone = document.getElementById(zoneId);
            if (!input || !zone) return;

            zone.addEventListener('click', () => input.click());
            zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
            zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
            zone.addEventListener('drop', e => {
                e.preventDefault();
                zone.classList.remove('drag-over');
                if (e.dataTransfer.files.length) this.handleFile(e.dataTransfer.files[0], tab);
            });
            input.addEventListener('change', () => {
                if (input.files.length) this.handleFile(input.files[0], tab);
            });

            const removeBtn = document.getElementById(removeId);
            if (removeBtn) {
                removeBtn.addEventListener('click', () => this.removeFile(tab));
            }
        },

        async handleFile(file, tab) {
            const config = this.getTabConfig(tab);
            const formData = new FormData();
            formData.append('file', file);

            try {
                const r = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await r.json();
                if (data.error) throw new Error(data.error);

                this.files[tab] = { ...data, file };
                this.showFileInfo(tab, file, data);
                this.enableButton(tab);
                this.runAnalysis(tab, data.filepath);

                // Muat audio asli ke player untuk A/B (before) + waveform asli
                if (typeof Player !== 'undefined') {
                    Player.setOriginal(`/api/original?task_id=${encodeURIComponent(data.task_id)}`, data.filename);
                }

                // Analisis adaptif -> isi starting point Pre-Master (EQ + comp)
                if (tab === 'master') this.applyAdaptiveDefaults();
                if (tab === 'master' && typeof AnalyzerPanel !== 'undefined') AnalyzerPanel.run(data.filepath);

                App.notify('File uploaded: ' + file.name, 'success');
            } catch (e) {
                App.notify('Upload failed: ' + e.message, 'error');
            }
        },

        removeFile(tab) {
            delete this.files[tab];
            const config = this.getTabConfig(tab);
            if (config.infoEl) config.infoEl.style.display = 'none';
            if (config.zoneEl) config.zoneEl.style.display = '';
            if (config.inputEl) config.inputEl.value = '';

            const btn = document.getElementById(config.btnId);
            if (btn) btn.disabled = true;
        },

        showFileInfo(tab, file, data) {
            const config = this.getTabConfig(tab);
            if (config.zoneEl) config.zoneEl.style.display = 'none';
            if (config.infoEl) config.infoEl.style.display = 'flex';
            if (config.nameEl) config.nameEl.textContent = data.filename;
            if (config.sizeEl) config.sizeEl.textContent = App.formatBytes(file.size);
        },

        enableButton(tab) {
            const config = this.getTabConfig(tab);
            const btn = document.getElementById(config.btnId);
            if (btn) btn.disabled = false;
        },

        getTabConfig(tab) {
            const configs = {
                convert: { inputId: 'fileInput', zoneEl: document.getElementById('dropZone'), infoEl: document.getElementById('fileInfo'), nameEl: document.getElementById('fileName'), sizeEl: document.getElementById('fileSize'), inputEl: document.getElementById('fileInput'), btnId: 'btnConvert', progressCard: 'progressCard', progressBar: 'progressBar', progressPct: 'progressPercent', progressMsg: 'progressMessage', resultCard: 'resultCard', resultStats: 'resultStats', btnDownload: 'btnDownload' },
                mix: { inputId: 'mixFileInput', zoneEl: document.getElementById('mixDropZone'), infoEl: document.getElementById('mixFileInfo'), nameEl: document.getElementById('mixFileName'), sizeEl: document.getElementById('mixFileSize'), inputEl: document.getElementById('mixFileInput'), btnId: 'btnMix', progressCard: 'mixProgressCard', progressBar: 'mixProgressBar', progressPct: 'mixProgressPercent', progressMsg: 'mixProgressMessage', resultCard: 'mixResultCard', resultStats: null, btnDownload: 'btnMixDownload' },
                master: { inputId: 'masterFileInput', zoneEl: document.getElementById('masterDropZone'), infoEl: document.getElementById('masterFileInfo'), nameEl: document.getElementById('masterFileName'), sizeEl: document.getElementById('masterFileSize'), inputEl: document.getElementById('masterFileInput'), btnId: 'btnMaster', progressCard: 'masterProgressCard', progressBar: 'masterProgressBar', progressPct: 'masterProgressPercent', progressMsg: 'masterProgressMessage', resultCard: 'masterResultCard', resultStats: 'masterResultStats', btnDownload: 'btnMasterDownload' },
            };
            return configs[tab] || {};
        },

        async runAnalysis(tab, filepath) {
            try {
                const r = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath }),
                });
                const data = await r.json();
                if (tab === 'convert') this.showConvertAnalysis(data);
                if (tab === 'mix') this.showMixAnalysis(data);
                if (tab === 'master') this.showMasterAnalysis(data);
            } catch (e) {
                console.warn('Analysis failed:', e);
            }
        },

        showConvertAnalysis(data) {
            const card = document.getElementById('analysisCard');
            if (!card) return;
            card.style.display = '';

            const grid = document.getElementById('statsGrid');
            if (!grid) return;
            const stats = [
                ['LUFS', data.lufs?.toFixed(1) + ' LUFS' || 'N/A'],
                ['Duration', App.formatTime(data.duration || 0)],
                ['Channels', data.channels === 1 ? 'Mono' : 'Stereo'],
                ['Crest Factor', data.dynamics?.crest_factor?.toFixed(1) + ' dB' || 'N/A'],
                ['Dyn Range', data.dynamics?.dynamic_range?.toFixed(1) + ' dB' || 'N/A'],
            ];
            grid.innerHTML = stats.map(([l, v]) =>
                `<div class="stat-item"><div class="stat-label">${l}</div><div class="stat-val">${v}</div></div>`
            ).join('');

            if (data.issues?.length) {
                const issues = data.issues.map(i =>
                    `<div class="stat-item" style="border-color:${i.severity==='warning'?'var(--warning)':'var(--info)'}"><div class="stat-label">${i.type}</div><div class="stat-val" style="font-size:11px">${i.message}</div></div>`
                ).join('');
                grid.innerHTML += issues;
            }

            if (typeof Visualizer !== 'undefined') {
                const canvas = document.getElementById('spectrumCanvas');
                if (canvas && data.frequency?.freqs && data.frequency?.spectrum) {
                    Visualizer.drawSpectrum(canvas, data.frequency.freqs, data.frequency.spectrum);
                }
            }
        },

        showMixAnalysis(data) {
            if (typeof Visualizer !== 'undefined' && typeof Equalizer !== 'undefined') {
                Equalizer.updateFromAnalysis(data);
            }
        },

        showMasterAnalysis(data) {},

        startConvert() {
            const file = this.files['convert'];
            if (!file) return;
            const config = this.getTabConfig('convert');
            this.showProgress(config);
            this.disableButton('convert');

            const sr = parseInt(document.getElementById('convertSampleRate')?.value || '44100');
            const removeWm = document.getElementById('convertRemoveWm')?.checked ?? true;

            fetch('/api/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filepath: file.filepath, task_id: file.task_id, filename: file.filename,
                    sample_rate: sr, remove_watermark: removeWm,
                    format: document.getElementById('convertFormat')?.value || 'wav24',
                    normalize: document.getElementById('convertNormalize')?.checked ?? true,
                    air_enhance: document.getElementById('convertAirEnhance')?.checked ?? false,
                }),
            }).then(r => r.json()).then(data => {
                if (data && data.error) { App.notify(data.error, 'error'); return; }
                this.pollProgress(file.task_id, 'convert');
            }).catch(e => App.notify('Error: ' + e.message, 'error'));
        },

        startMix() {
            const file = this.files['mix'];
            if (!file) return;
            const config = this.getTabConfig('mix');
            this.showProgress(config);
            this.disableButton('mix');

            const settings = this.collectMixSettings();

            fetch('/api/mix', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filepath: file.filepath, task_id: file.task_id, filename: file.filename, settings }),
            }).then(r => r.json()).then(data => {
                this.pollProgress(file.task_id, 'mix');
            }).catch(e => App.notify('Error: ' + e.message, 'error'));
        },

        startMaster() {
            const file = this.files['master'];
            if (!file) return;
            if (typeof Preview !== 'undefined' && Preview.playing) Preview.stop();
            const config = this.getTabConfig('master');
            this.showProgress(config);
            this.disableButton('master');

            const genre = document.getElementById('masterGenre')?.value || 'pop';
            const platform = document.getElementById('masterPlatform')?.value || 'spotify';
            const stereoWidth = parseInt(document.getElementById('masterStereoWidth')?.value || '110');
            const truePeak = parseFloat(document.getElementById('masterTruePeak')?.value ?? '-1.0');
            const removeWm = document.getElementById('masterRemoveWm')?.checked ?? true;

            // Pre-Master fine tuning: hanya dikirim jika diaktifkan;
            // jika tidak, EQ & kompresor mengikuti preset genre otomatis.
            // Panel Pre-Master = kebenaran: apa yang terdengar di preview
            // adalah persis yang dirender. Nilai panel SELALU dikirim.
            const ft = this.collectMixSettings();
            delete ft.stereo_width;   // stereo width dikontrol knob master
            let settings = {
                ...ft,
                stereo_width: stereoWidth,
                true_peak: truePeak,
                adaptive: document.getElementById('masterAdaptive')?.checked ?? true,
                input_gain_db: this.adaptiveInfo?.input_gain_db,
                sample_rate: parseInt(document.getElementById('masterSampleRate')?.value || '44100'),
                bit_depth: document.getElementById('masterBitDepth')?.value || '24',
            };

            fetch('/api/master', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filepath: file.filepath, task_id: file.task_id, filename: file.filename, genre, platform, remove_watermark: removeWm, settings }),
            }).then(r => r.json()).then(data => {
                if (data && data.error) { App.notify(data.error, 'error'); return; }
                this.pollProgress(file.task_id, 'master');
            }).catch(e => App.notify('Error: ' + e.message, 'error'));
        },

        async applyAdaptiveDefaults() {
            const file = this.files['master'];
            if (!file) return;
            const genre = document.getElementById('masterGenre')?.value || 'pop';
            try {
                const r = await fetch('/api/adaptive', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath: file.filepath, genre }),
                });
                const a = await r.json();
                if (a.error) return;
                this.adaptiveInfo = a;
                if (typeof Equalizer !== 'undefined' && Equalizer.setGains) Equalizer.setGains(a.eq_gains);
                const names = ['Low', 'Mid', 'High'];
                (a.compressor || []).forEach((band, i) => {
                    const set = (id, val) => {
                        const el = document.getElementById(id);
                        if (!el || !isFinite(val)) return;
                        el.value = val;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    };
                    set(`comp${names[i]}Thresh`, band.threshold_db);
                    set(`comp${names[i]}Ratio`, band.ratio);
                    set(`comp${names[i]}Attack`, band.attack_ms);
                    set(`comp${names[i]}Release`, band.release_ms);
                });
                App.notify(`Adaptive analysis applied (${genre} target)`, 'success');
            } catch (e) { /* analisis gagal tidak menghalangi alur */ }
        },

        bindEqButtons() {
            document.getElementById('btnEqMatchRef')?.addEventListener('click', async () => {
                if (typeof Preview === 'undefined' || !Preview.refFileObj) {
                    App.notify('Load a reference track first (⊕ Ref in Pre-Master)', 'error');
                    return;
                }
                const file = this.files['master'];
                if (!file) { App.notify('Upload audio first', 'error'); return; }
                const btn = document.getElementById('btnEqMatchRef');
                const orig = btn ? btn.textContent : '';
                if (btn) { btn.disabled = true; btn.textContent = 'Matching…'; }
                try {
                    const gains = await Preview.matchReferenceEq(file.filepath);
                    if (gains && typeof Equalizer !== 'undefined' && Equalizer.setGains) {
                        Equalizer.setGains(gains);
                        if (Preview.playing) Preview.applyEq();
                        App.notify('EQ matched to reference (precise)', 'success');
                    }
                } catch (e) {
                    App.notify('Match failed: ' + e.message, 'error');
                } finally {
                    if (btn) { btn.disabled = false; btn.textContent = orig; }
                }
            });
        },

        bindChainBadges() {
            const lufsMap = { spotify: '-14 LUFS', apple: '-16 LUFS', youtube: '-14 LUFS', tiktok: '-14 LUFS', soundcloud: '-10 LUFS', club: '-8 LUFS' };
            const setTxt = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };

            const tp = document.getElementById('masterTruePeak');
            const upTp = () => setTxt('chainBrickwallVal', (parseFloat(tp.value) === 0 ? '0' : tp.value) + ' dBTP');
            tp?.addEventListener('change', upTp); if (tp) upTp();

            document.getElementById('masterGenre')?.addEventListener('change', () => {
                this.applyAdaptiveDefaults();
                const f = this.files['master'];
                if (f && typeof AnalyzerPanel !== 'undefined') AnalyzerPanel.run(f.filepath);
            });

            const pf = document.getElementById('masterPlatform');
            const upPf = () => setTxt('chainLufsVal', lufsMap[pf.value] || '-14 LUFS');
            pf?.addEventListener('change', upPf); if (pf) upPf();

            const sw = document.getElementById('masterStereoWidth');
            const upSw = () => setTxt('chainStereoVal', sw.value + '%');
            sw?.addEventListener('input', upSw); if (sw) upSw();

            // Bit Depth -> perbarui label "TPDF Dither" di chain visual kanan
            const bd = document.getElementById('masterBitDepth');
            const upBd = () => setTxt('chainDitherVal', (bd?.value || '24') + '-bit');
            bd?.addEventListener('change', upBd); if (bd) upBd();

            const ad = document.getElementById('masterAdaptive');
            const upMode = () => {
                const mode = ad?.checked ? 'Adaptive' : 'Manual';
                setTxt('chainEqVal', mode);
                setTxt('chainCompVal', mode);
            };
            ad?.addEventListener('change', upMode);
            upMode();
        },

        collectMixSettings() {
            return {
                eq_gains: typeof Equalizer !== 'undefined' ? Equalizer.getGains() : {},
                eq_q: 1.4,
                compressor: [
                    {
                        low: 20, high: 200,
                        threshold_db: parseFloat(document.getElementById('compLowThresh')?.value || '-18'),
                        ratio: parseFloat(document.getElementById('compLowRatio')?.value || '3'),
                        attack_ms: parseInt(document.getElementById('compLowAttack')?.value || '10'),
                        release_ms: parseInt(document.getElementById('compLowRelease')?.value || '80'),
                        makeup_db: 0,
                    },
                    {
                        low: 200, high: 3000,
                        threshold_db: parseFloat(document.getElementById('compMidThresh')?.value || '-20'),
                        ratio: parseFloat(document.getElementById('compMidRatio')?.value || '2.5'),
                        attack_ms: parseInt(document.getElementById('compMidAttack')?.value || '8'),
                        release_ms: parseInt(document.getElementById('compMidRelease')?.value || '60'),
                        makeup_db: 0,
                    },
                    {
                        low: 3000, high: 20000,
                        threshold_db: parseFloat(document.getElementById('compHighThresh')?.value || '-22'),
                        ratio: parseFloat(document.getElementById('compHighRatio')?.value || '2'),
                        attack_ms: parseInt(document.getElementById('compHighAttack')?.value || '5'),
                        release_ms: parseInt(document.getElementById('compHighRelease')?.value || '40'),
                        makeup_db: 0,
                    },
                ],
                stereo_width: parseInt(document.getElementById('mixStereoWidth')?.value || '100'),
                bass_mono: document.getElementById('mixBassMono')?.checked ?? true,
                mid_gain: parseFloat(document.getElementById('mixMidGain')?.value || '0'),
                side_gain: parseFloat(document.getElementById('mixSideGain')?.value || '0'),
                transient_attack: parseFloat(document.getElementById('mixAttack')?.value || '0'),
                transient_sustain: parseFloat(document.getElementById('mixSustain')?.value || '0'),
            };
        },

        showProgress(config) {
            const card = document.getElementById(config.progressCard);
            if (card) card.style.display = '';
            const resultCard = document.getElementById(config.resultCard);
            if (resultCard) resultCard.style.display = 'none';
            // brand card (foto @GitaRoni) dibiarkan tetap tampil — progress muncul
            // di bawahnya. Dulu foto disembunyikan lalu tak pernah dikembalikan,
            // sehingga foto "hilang" setelah proses pertama.
        },

        disableButton(tab) {
            const config = this.getTabConfig(tab);
            const btn = document.getElementById(config.btnId);
            if (btn) btn.disabled = true;
        },

        pollProgress(taskId, tab) {
            const config = this.getTabConfig(tab);
            const interval = setInterval(async () => {
                try {
                    const r = await fetch(`/api/progress/${taskId}`);
                    const p = await r.json();
                    const bar = document.getElementById(config.progressBar);
                    // animasi indeterminate saat proses awal (decode/analisis) belum lapor persen
                    bar?.parentElement?.classList.toggle('indeterminate', (p.percent || 0) < 1);
                    const pct = document.getElementById(config.progressPct);
                    const msg = document.getElementById(config.progressMsg);
                    if (bar) bar.style.width = p.percent + '%';
                    if (pct) pct.textContent = p.percent + '%';
                    if (msg) msg.textContent = p.message;

                    this.updateChainSteps(tab, p.percent);

                    if (p.percent >= 100) {
                        clearInterval(interval);
                        this.fetchResult(taskId, tab);
                    }
                } catch (e) {}
            }, 500);
            this.pollIntervals[taskId] = interval;
        },

        updateChainSteps(tab, pct) {
            if (tab !== 'master') return;
            const steps = [
                { name: 'watermark', threshold: 10 },
                { name: 'eq', threshold: 25 },
                { name: 'comp', threshold: 45 },
                { name: 'transient', threshold: 50 },
                { name: 'bassmono', threshold: 55 },
                { name: 'lufs', threshold: 65 },
                { name: 'limiter', threshold: 80 },
                { name: 'dither', threshold: 95 },
            ];
            document.querySelectorAll('.chain-step').forEach(el => el.classList.remove('active', 'done'));
            steps.forEach(s => {
                const el = document.querySelector(`[data-chain="${s.name}"]`);
                if (!el) return;
                if (pct >= s.threshold + 5) el.classList.add('done');
                else if (pct >= s.threshold) el.classList.add('active');
            });
        },

        async fetchResult(taskId, tab, attempt = 0) {
            try {
                const r = await fetch(`/api/result/${taskId}`);
                // Parse aman: WebKit melempar "The string did not match the
                // expected pattern" bila payload bukan JSON valid (mis. NaN).
                // Baca sbg teks dulu supaya kalau invalid, isinya bisa
                // ditampilkan di pesan error (diagnosa sekali lihat).
                const raw = await r.text();
                let data;
                try { data = JSON.parse(raw); }
                catch (pe) { throw new Error('invalid result payload: ' + raw.slice(0, 140)); }
                if (data.pending) {
                    // hasil belum tertulis — coba lagi (maks ~10 detik)
                    if (attempt < 20) setTimeout(() => this.fetchResult(taskId, tab, attempt + 1), 500);
                    else App.notify('Result timeout — please try again', 'error');
                    return;
                }
                if (data.error) { App.notify(data.error, 'error'); return; }

                const config = this.getTabConfig(tab);
                const resultCard = document.getElementById(config.resultCard);
                if (resultCard) resultCard.style.display = '';

                const btn = document.getElementById(config.btnId);
                if (btn) btn.disabled = false;

                const dl = document.getElementById(config.btnDownload);
                if (dl) {
                    dl.href = '#';
                    dl.onclick = async (ev) => {
                        ev.preventDefault();
                        try {
                            // simpan langsung ke folder Downloads lewat backend —
                            // andal di jendela desktop (webview tak perlu handle unduhan)
                            const u = new URL(data.output_url, location.origin);
                            const q = new URLSearchParams(u.search);
                            const res = await fetch(`/api/save?file=${encodeURIComponent(q.get('file'))}&name=${encodeURIComponent(q.get('name') || '')}`);
                            const j = await res.json();
                            if (j.saved) {
                                App.notify('Saved to Downloads: ' + j.name, 'success');
                            } else {
                                throw new Error(j.error || 'Save failed');
                            }
                        } catch (e) {
                            App.notify('Save failed: ' + e.message, 'error');
                        }
                    };
                }

                if (config.resultStats && data.stats) {
                    const s = document.getElementById(config.resultStats);
                    if (s) {
                        const stats = data.stats;
                        s.innerHTML = `
                            <div class="result-stat"><div class="stat-value">${stats.lufs?.toFixed(1) || 'N/A'}</div><div class="stat-label">LUFS</div></div>
                            <div class="result-stat"><div class="stat-value">${stats.true_peak?.toFixed(1) || 'N/A'}</div><div class="stat-label">True Peak</div></div>
                            <div class="result-stat"><div class="stat-value">${stats.genre || tab}</div><div class="stat-label">Preset</div></div>
                        `;
                    }
                }

                App.notify('Processing complete!', 'success');

                if (typeof Player !== 'undefined') {
                    // pakai play=1 agar di-stream inline (bukan diunduh) untuk A/B
                    Player.setProcessed(data.output_url + '&play=1');
                }
            } catch (e) {
                App.notify('Result fetch failed: ' + e.message, 'error');
            }
        },
    };

    document.addEventListener('DOMContentLoaded', () => Uploader.init());
})();
