// Preset Fine Tuning (EQ + Multiband Compressor).
// Disimpan di server (folder data user) agar persist antar buka-tutup aplikasi.
// Dipakai bersama oleh Master single & Album (keduanya memakai collectMixSettings).
(() => {
    const FTPresets = {
        init() {
            this.sel = document.getElementById('ftPresetSelect');
            if (!this.sel) return;
            document.getElementById('btnFtPresetSave')?.addEventListener('click', () => this.save());
            document.getElementById('btnFtPresetDelete')?.addEventListener('click', () => this.remove());
            this.sel.addEventListener('change', () => this.apply(this.sel.value));
            this.refresh();
        },

        async refresh(selectFile) {
            try {
                const data = await fetch('/api/userpresets').then(r => r.json());
                const presets = (data && data.presets) || [];
                this.sel.innerHTML = '<option value="">— Preset —</option>';
                for (const p of presets) {
                    const opt = document.createElement('option');
                    opt.value = p.file;
                    opt.textContent = p.name;
                    this.sel.appendChild(opt);
                }
                if (selectFile) this.sel.value = selectFile;
            } catch (e) {
                // preset opsional — diam saja
            }
        },

        async save() {
            const name = prompt('Save preset as:', '');
            if (name === null) return;
            const trimmed = (name || '').trim();
            if (!trimmed) { if (window.App) App.notify('Preset name required', 'error'); return; }
            if (typeof Uploader === 'undefined' || !Uploader.collectMixSettings) return;
            const settings = Uploader.collectMixSettings();
            try {
                const res = await fetch('/api/userpresets', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: trimmed, settings })
                }).then(r => r.json());
                if (res && res.ok) {
                    await this.refresh(res.file);
                    if (window.App) App.notify('Preset saved: ' + res.name, 'success');
                }
            } catch (e) {
                if (window.App) App.notify('Save failed: ' + e.message, 'error');
            }
        },

        async apply(file) {
            if (!file) return;
            try {
                const data = await fetch('/api/userpresets/' + encodeURIComponent(file)).then(r => r.json());
                const s = data && data.settings;
                if (!s) return;
                this.applySettings(s);
                if (window.App) App.notify('Preset loaded: ' + (data.name || ''), 'success');
            } catch (e) {
                if (window.App) App.notify('Load failed: ' + e.message, 'error');
            }
        },

        applySettings(s) {
            if (s.eq_gains && typeof Equalizer !== 'undefined' && Equalizer.setGains) {
                Equalizer.setGains(s.eq_gains);
            }
            const comp = Array.isArray(s.compressor) ? s.compressor : [];
            const map = [['Low', comp[0]], ['Mid', comp[1]], ['High', comp[2]]];
            for (const [band, c] of map) {
                if (!c) continue;
                this.setVal('comp' + band + 'Thresh', c.threshold_db);
                this.setVal('comp' + band + 'Ratio', c.ratio);
                this.setVal('comp' + band + 'Attack', c.attack_ms);
                this.setVal('comp' + band + 'Release', c.release_ms);
            }
        },

        setVal(id, v) {
            if (v === undefined || v === null) return;
            const el = document.getElementById(id);
            if (!el) return;
            el.value = v;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        },

        async remove() {
            const file = this.sel.value;
            if (!file) { if (window.App) App.notify('Select a preset to delete', 'error'); return; }
            const name = this.sel.options[this.sel.selectedIndex]?.textContent || file;
            if (!confirm('Delete preset "' + name + '"?')) return;
            try {
                await fetch('/api/userpresets/' + encodeURIComponent(file), { method: 'DELETE' });
                await this.refresh();
                if (window.App) App.notify('Preset deleted', 'success');
            } catch (e) {
                if (window.App) App.notify('Delete failed: ' + e.message, 'error');
            }
        },
    };

    window.FTPresets = FTPresets;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => FTPresets.init());
    } else {
        FTPresets.init();
    }
})();
