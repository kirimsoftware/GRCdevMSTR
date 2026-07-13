/* License — layar aktivasi + status. Aktivasi offline dengan key
   bertanda tangan digital yang terikat Hardware ID mesin ini. */
(() => {
    window.License = {
        async init() {
            try {
                const s = await (await fetch('/api/license/status')).json();
                if (s.licensed) { this.hide(); return; }
                this.show(s);
            } catch (e) { /* backend belum siap; jangan blokir UI */ }
        },

        show(s) {
            const ov = document.getElementById('licenseOverlay');
            if (!ov) return;
            ov.style.display = 'flex';
            const hw = document.getElementById('licHwid');
            if (hw) hw.textContent = s.hwid || '----';

            // Bedakan: subscription habis vs belum pernah aktivasi
            const h2 = ov.querySelector('h2');
            const p = ov.querySelector('p');
            if (s.message && /expired/i.test(s.message)) {
                if (h2) h2.textContent = 'Subscription Expired';
                if (p) p.textContent = 'Your monthly license has expired. Send your Hardware ID to renew, then paste the new key below.';
                this.setStatus(s.message, 'err');
            } else if (s.message && /different machine/i.test(s.message)) {
                if (h2) h2.textContent = 'License Not Valid Here';
                if (p) p.textContent = 'The stored license belongs to another machine. Request a key for this Hardware ID.';
                this.setStatus(s.message, 'err');
            }
            document.getElementById('licCopy')?.addEventListener('click', () => {
                navigator.clipboard?.writeText(s.hwid || '');
                this.setStatus('Hardware ID copied', 'ok');
            });
            document.getElementById('licActivate')?.addEventListener('click', () => this.activate());
        },

        async activate() {
            const key = document.getElementById('licKey')?.value?.trim();
            if (!key) { this.setStatus('Paste your license key first', 'err'); return; }
            try {
                const r = await fetch('/api/license/activate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key }),
                });
                const j = await r.json();
                if (j.ok) {
                    this.setStatus('Activated — ' + j.mode + (j.exp ? ' (until ' + j.exp + ')' : ' license'), 'ok');
                    setTimeout(() => this.hide(), 900);
                } else {
                    this.setStatus(j.error || 'Activation failed', 'err');
                }
            } catch (e) {
                this.setStatus('Activation failed: ' + e.message, 'err');
            }
        },

        setStatus(msg, cls) {
            const el = document.getElementById('licStatus');
            if (el) { el.textContent = msg; el.className = 'license-status ' + cls; }
        },

        hide() {
            const ov = document.getElementById('licenseOverlay');
            if (ov) ov.style.display = 'none';
        },
    };
    document.addEventListener('DOMContentLoaded', () => License.init());
})();
