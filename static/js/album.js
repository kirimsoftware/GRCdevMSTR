/* Album Mastering — proses hingga 15 lagu, adaptive per lagu,
   download per lagu + semua (ZIP). Reuse /api/upload + /api/master. */
const Album = {
    MAX: 15,
    tracks: [],   // {file, name, task_id, filepath, status, output_url, out_file, out_name, srcUrl}
    selected: -1, // index lagu yang sedang di-preview di player

    init() {
        const zone = document.getElementById('albumDropZone');
        const input = document.getElementById('albumFileInput');
        if (!zone || !input) return;

        zone.addEventListener('click', () => input.click());
        zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', e => {
            e.preventDefault(); zone.classList.remove('dragover');
            this.addFiles(e.dataTransfer.files);
        });
        input.addEventListener('change', () => this.addFiles(input.files));

        document.getElementById('btnAlbumMaster')?.addEventListener('click', () => this.masterAll());
        document.getElementById('btnAlbumDlWav')?.addEventListener('click', () => this.downloadAllWav());
        document.getElementById('btnAlbumDlZip')?.addEventListener('click', () => this.downloadAllZip());

        // Panel Pre-Master (Fine Tuning) dipakai bersama Master & Album:
        // dipindah ke tab yang aktif supaya ID unik tetap satu.
        this.hookTabSwitch();
    },

    hookTabSwitch() {
        if (typeof App === 'undefined' || !App.switchTab) return;
        const orig = App.switchTab.bind(App);
        App.switchTab = (tab) => { orig(tab); this.relocateFineTuning(tab); };
    },

    relocateFineTuning(tab) {
        const card = document.querySelector('.premaster-card');
        if (!card) return;
        if (tab === 'album') {
            const slot = document.getElementById('albumFineTuningSlot');
            if (slot && card.parentElement !== slot) slot.appendChild(card);
        } else if (tab === 'master') {
            const home = document.querySelector('.masterer-panel');
            if (home && card.parentElement !== home) home.prepend(card);
        }
    },

    addFiles(fileList) {
        const files = Array.from(fileList || []);
        for (const f of files) {
            if (this.tracks.length >= this.MAX) {
                App.notify(`Maksimum ${this.MAX} lagu`, 'error');
                break;
            }
            if (!f.type.startsWith('audio/') && !/\.(wav|mp3|flac|aiff?|m4a|ogg)$/i.test(f.name)) continue;
            this.tracks.push({ file: f, name: f.name, status: 'ready' });
        }
        this.render();
        this.updateCount();
    },

    removeTrack(i) {
        if (this.tracks[i] && this.tracks[i].status === 'processing') return;
        if (this.tracks[i] && this.tracks[i].srcUrl) URL.revokeObjectURL(this.tracks[i].srcUrl);
        this.tracks.splice(i, 1);
        if (this.selected === i) this.selected = -1;
        else if (this.selected > i) this.selected--;
        this.render();
        this.updateCount();
    },

    updateCount() {
        const c = document.getElementById('albumCount');
        if (c) c.textContent = `${this.tracks.length} / ${this.MAX} tracks`;
        const btn = document.getElementById('btnAlbumMaster');
        if (btn) btn.disabled = this.tracks.length === 0;
    },

    render() {
        const wrap = document.getElementById('albumTracks');
        const empty = document.getElementById('albumEmpty');
        if (!wrap) return;
        if (this.tracks.length === 0) {
            wrap.innerHTML = '<div class="album-empty" id="albumEmpty">Belum ada lagu. Tambahkan hingga 15 track untuk mulai.</div>';
            document.getElementById('albumActions').style.display = 'none';
            return;
        }
        wrap.innerHTML = this.tracks.map((t, i) => {
            const pct = t.percent || 0;
            let right = '';
            if (t.status === 'done') {
                right = `<span class="album-done-mark" title="Selesai">&#10003;</span><button class="btn btn-sm album-dl" data-i="${i}">&#8681; Save</button>`;
            } else if (t.status === 'processing') {
                right = `<span class="album-pct">${pct}%</span><span class="album-proc-label">PROCESSING</span>`;
            } else if (t.status === 'error') {
                right = `<span class="album-err" title="${this.esc(t.msg || '')}">Error</span><button class="btn btn-sm album-retry" data-i="${i}" title="Coba lagi">&#8635;</button>`;
            } else {
                right = `<button class="btn btn-sm album-rm" data-i="${i}">&times;</button>`;
            }
            const msgLine = t.status === 'processing'
                ? `<div class="album-track-msg">${this.esc(t.msg || 'Processing...')}</div>` : '';
            return `
            <div class="album-track ${t.status}${this.selected === i ? ' selected' : ''}">
                <div class="album-track-num">${i + 1}</div>
                <div class="album-track-info" data-i="${i}" title="Klik untuk preview A/B di player">
                    <div class="album-track-name">${this.esc(t.name)}</div>
                    <div class="album-track-bar${t.status === 'processing' && pct < 1 ? ' indeterminate' : ''}"><div class="album-track-fill" style="width:${pct}%"></div></div>
                    ${msgLine}
                </div>
                <div class="album-track-right">${right}</div>
            </div>`;
        }).join('');

        wrap.querySelectorAll('.album-rm').forEach(b =>
            b.addEventListener('click', e => { e.stopPropagation(); this.removeTrack(parseInt(b.dataset.i)); }));
        wrap.querySelectorAll('.album-retry').forEach(b =>
            b.addEventListener('click', e => { e.stopPropagation(); this.retryTrack(parseInt(b.dataset.i)); }));
        wrap.querySelectorAll('.album-dl').forEach(b =>
            b.addEventListener('click', e => { e.stopPropagation(); this.downloadOne(parseInt(b.dataset.i)); }));
        wrap.querySelectorAll('.album-track-info').forEach(el =>
            el.addEventListener('click', () => this.previewTrack(parseInt(el.dataset.i))));

        const doneCount = this.tracks.filter(t => t.status === 'done').length;
        document.getElementById('albumActions').style.display = doneCount > 0 ? '' : 'none';
    },

    esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; },

    /* Preview A/B per lagu: A = file asli (lokal), B = hasil master (jika sudah selesai).
       Player bawah + Live Preview panel Fine Tuning otomatis mengikuti lagu ini. */
    previewTrack(i) {
        const t = this.tracks[i];
        if (!t || typeof Player === 'undefined') return;
        this.selected = i;
        if (!t.srcUrl) t.srcUrl = URL.createObjectURL(t.file);

        // reset processed lama supaya tombol B tidak memutar lagu sebelumnya
        Player.processedUrl = null;
        Player.setOriginal(t.srcUrl, t.name);
        if (t.status === 'done' && t.output_url) {
            Player.setProcessed(t.output_url);   // langsung ke B (after)
        } else {
            Player.switchSource('original');      // hanya A tersedia
        }
        // Live Preview (panel Fine Tuning) memakai buffer baru saat play berikutnya
        if (typeof Preview !== 'undefined') Preview._bufUrl = null;
        this.render();
        App.notify(`Preview: ${t.name}${t.status === 'done' ? ' (A = asli, B = mastered)' : ' (A = asli — master dulu untuk B)'}`, 'success');
    },

    async masterAll() {
        const btn = document.getElementById('btnAlbumMaster');
        if (btn) btn.disabled = true;
        const genre = document.getElementById('albumGenre').value;
        const platform = document.getElementById('albumPlatform').value;
        const adaptive = document.getElementById('albumAdaptive').checked;
        const removeWm = document.getElementById('albumWatermark').checked;
        const useFineTune = document.getElementById('albumFineTune')?.checked;

        // Fine Tuning: nilai panel Pre-Master (EQ + compressor) dipakai untuk
        // semua lagu. Nilai panel menang; adaptive mengisi sisanya di backend.
        let ftSettings = {};
        if (useFineTune && typeof Uploader !== 'undefined' && Uploader.collectMixSettings) {
            ftSettings = Uploader.collectMixSettings();
            delete ftSettings.stereo_width;
        }
        // Sample rate & bit depth berlaku seragam untuk semua lagu album.
        ftSettings.sample_rate = parseInt(document.getElementById('albumSampleRate')?.value || '44100');
        ftSettings.bit_depth = document.getElementById('albumBitDepth')?.value || '24';

        for (let i = 0; i < this.tracks.length; i++) {
            const t = this.tracks[i];
            if (t.status === 'done') continue;
            try {
                await this.processTrack(t, i, genre, platform, adaptive, removeWm, ftSettings);
            } catch (e) {
                t.status = 'error'; this.render();
            }
        }
        if (btn) btn.disabled = false;
        App.notify('Album selesai di-master', 'success');
    },

    processTrack(t, i, genre, platform, adaptive, removeWm, ftSettings) {
        return new Promise(async (resolve, reject) => {
            try {
                t.status = 'processing'; t.percent = 0; t.msg = 'Uploading...'; this.render();

                // 1) upload
                const fd = new FormData();
                fd.append('file', t.file);
                const up = await fetch('/api/upload', { method: 'POST', body: fd }).then(r => r.json());
                if (!up.filepath) throw new Error('upload failed');
                t.task_id = up.task_id; t.filepath = up.filepath;

                // 2) master (adaptive per lagu + watermark removal sesuai toggle)
                await fetch('/api/master', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filepath: up.filepath, task_id: up.task_id, filename: t.name,
                        genre, platform, remove_watermark: removeWm,
                        settings: { ...(ftSettings || {}), adaptive: adaptive }
                    })
                });

                // 3) poll progress lagu ini — pakai loop await (bukan setInterval)
                //    supaya tidak ada request bertumpuk / race saat CPU sibuk.
                const sleep = ms => new Promise(r => setTimeout(r, ms));
                while (true) {
                    await sleep(500);
                    let p;
                    try {
                        p = await fetch(`/api/progress/${t.task_id}`).then(r => r.json());
                    } catch (e) { continue; /* server sibuk — coba lagi */ }
                    t.percent = p.percent || 0;
                    t.msg = p.message || '';
                    this.updateTrackBar(i);
                    if (t.percent >= 100) break;
                }

                // 4) ambil hasil — server bisa masih menulis file WAV beberapa saat
                //    setelah progress 100% (lagu panjang). Tunggu sampai siap,
                //    maksimal ~3 menit, JANGAN tandai done sebelum output_url ada.
                t.msg = 'Finalizing...'; this.updateTrackBar(i);
                let res = null;
                for (let attempt = 0; attempt < 360; attempt++) {
                    const r = await fetch(`/api/result/${t.task_id}`);
                    res = await r.json();
                    if (res && res.error) { t.status = 'error'; t.msg = res.error; this.render(); return reject(new Error(res.error)); }
                    if (res && res.output_url) break;
                    await new Promise(rr => setTimeout(rr, 500));
                }
                if (!res || !res.output_url) {
                    t.status = 'error'; t.msg = 'Result timeout';
                    this.render(); return reject(new Error('result timeout'));
                }

                t.output_url = res.output_url;
                const u = new URL(res.output_url, location.origin);
                const q = new URLSearchParams(u.search);
                t.out_file = q.get('file');
                t.out_name = q.get('name') || t.name;
                t.status = 'done'; t.msg = '';
                this.render();
                // kalau lagu ini sedang di-preview, langsung sediakan B (after)
                if (this.selected === i && typeof Player !== 'undefined') {
                    Player.setProcessed(t.output_url);
                }
                resolve();
            } catch (e) { t.status = 'error'; t.msg = String(e.message || e); this.render(); reject(e); }
        });
    },

    updateTrackBar(i) {
        const wrap = document.getElementById('albumTracks');
        if (!wrap) return;
        const row = wrap.children[i];
        if (!row) return;
        const t = this.tracks[i];
        const fill = row.querySelector('.album-track-fill');
        const pct = row.querySelector('.album-pct');
        const msg = row.querySelector('.album-track-msg');
        const bar = row.querySelector('.album-track-bar');
        if (fill) fill.style.width = (t.percent || 0) + '%';
        if (pct) pct.textContent = (t.percent || 0) + '%';
        if (msg) msg.textContent = t.msg || 'Processing...';
        // bar indeterminate saat persen masih 0 (decode/analisis awal)
        if (bar) bar.classList.toggle('indeterminate', (t.percent || 0) < 1);
    },

    async downloadOne(i) {
        const t = this.tracks[i];
        if (!t || t.status !== 'done') return;
        try {
            const res = await fetch(`/api/save?file=${encodeURIComponent(t.out_file)}&name=${encodeURIComponent(t.out_name)}`).then(r => r.json());
            if (res.saved) App.notify('Saved: ' + res.name, 'success');
            else throw new Error(res.error || 'save failed');
        } catch (e) {
            // fallback: buka download langsung
            window.location.href = t.output_url;
        }
    },

    /* Ulangi mastering satu lagu yang error */
    retryTrack(i) {
        const t = this.tracks[i];
        if (!t || t.status === 'processing') return;
        const genre = document.getElementById('albumGenre').value;
        const platform = document.getElementById('albumPlatform').value;
        const adaptive = document.getElementById('albumAdaptive').checked;
        const removeWm = document.getElementById('albumWatermark').checked;
        const useFineTune = document.getElementById('albumFineTune')?.checked;
        let ftSettings = {};
        if (useFineTune && typeof Uploader !== 'undefined' && Uploader.collectMixSettings) {
            ftSettings = Uploader.collectMixSettings();
            delete ftSettings.stereo_width;
        }
        ftSettings.sample_rate = parseInt(document.getElementById('albumSampleRate')?.value || '44100');
        ftSettings.bit_depth = document.getElementById('albumBitDepth')?.value || '24';
        this.processTrack(t, i, genre, platform, adaptive, removeWm, ftSettings)
            .catch(() => {});
    },

    _doneFiles() {
        return this.tracks.filter(t => t.status === 'done' && t.out_file)
            .map(t => ({ file: t.out_file, name: t.out_name }));
    },

    /* Opsi 1: simpan semua hasil sebagai file WAV terpisah di Downloads/<album>/ */
    async downloadAllWav() {
        const files = this._doneFiles();
        if (files.length === 0) { App.notify('Belum ada lagu selesai', 'error'); return; }
        const album = document.getElementById('albumName').value || 'Album';
        const btn = document.getElementById('btnAlbumDlWav');
        if (btn) btn.disabled = true;
        try {
            const res = await fetch('/api/album/save', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ album, files })
            }).then(r => r.json());
            if (res.saved) App.notify(`${res.saved} file WAV tersimpan di Downloads/${album}`, 'success');
            else throw new Error(res.error || 'save failed');
        } catch (e) {
            App.notify('Gagal menyimpan WAV: ' + (e.message || e), 'error');
        }
        if (btn) btn.disabled = false;
    },

    /* Opsi 2: ZIP — dibuat & disimpan langsung ke folder Downloads oleh server.
       (Bukan lewat blob browser, yang di jendela desktop sering korup.) */
    async downloadAllZip() {
        const files = this._doneFiles();
        if (files.length === 0) { App.notify('Belum ada lagu selesai', 'error'); return; }
        const album = document.getElementById('albumName').value || 'Album';
        const btn = document.getElementById('btnAlbumDlZip');
        if (btn) btn.disabled = true;
        try {
            const res = await fetch('/api/album/zip_save', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ album, files })
            }).then(r => r.json());
            if (res.zip) {
                App.notify(`ZIP tersimpan di Downloads: ${res.zip} (${res.saved} lagu)`, 'success');
                if (btn) btn.disabled = false;
                return;
            }
            throw new Error(res.error || 'zip failed');
        } catch (e) {
            // fallback (mode browser biasa): unduh zip via attachment
            try {
                const resp = await fetch('/api/album/zip', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ album, files })
                });
                if (!resp.ok) throw new Error('server error ' + resp.status);
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = `${album}_mastered.zip`;
                document.body.appendChild(a); a.click(); a.remove();
                URL.revokeObjectURL(url);
            } catch (e2) { App.notify('Download ZIP gagal: ' + (e2.message || e2), 'error'); }
        }
        if (btn) btn.disabled = false;
    },
};

document.addEventListener('DOMContentLoaded', () => Album.init());

/* ===== Convert: sample rate menyesuaikan format output (standar audio) ===== */
const ConvertFormatRules = {
    // format lossless: semua sample rate. MP3: maks 48 kHz (standar MP3).
    rates: {
        wav24: ['44100', '48000', '88200', '96000'],
        wav16: ['44100', '48000', '88200', '96000'],
        flac:  ['44100', '48000', '88200', '96000'],
        mp3_320: ['44100', '48000'],
        mp3_v0:  ['44100', '48000'],
    },
    init() {
        const fmt = document.getElementById('convertFormat');
        const sr = document.getElementById('convertSampleRate');
        if (!fmt || !sr) return;
        // simpan semua option asli
        this.allOptions = Array.from(sr.options).map(o => ({ value: o.value, text: o.textContent }));
        const apply = () => {
            const allowed = this.rates[fmt.value] || ['44100', '48000'];
            const prev = sr.value;
            sr.innerHTML = '';
            this.allOptions.forEach(o => {
                if (allowed.includes(o.value)) {
                    const opt = document.createElement('option');
                    opt.value = o.value; opt.textContent = o.text;
                    sr.appendChild(opt);
                }
            });
            // pertahankan pilihan jika masih valid, kalau tidak pilih yang tertinggi yg diizinkan
            if (allowed.includes(prev)) sr.value = prev;
            else sr.value = allowed[allowed.length - 1];
        };
        fmt.addEventListener('change', apply);
        apply();
    }
};
document.addEventListener('DOMContentLoaded', () => ConvertFormatRules.init());
