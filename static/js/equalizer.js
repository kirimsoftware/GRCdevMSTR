(() => {
    window.Equalizer = {
        bands: [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000],
        gains: {},
        canvas: null,
        ctx: null,
        dragging: -1,

        init() {
            this.canvas = document.getElementById('eqCanvas');
            if (!this.canvas) return;
            this.ctx = this.canvas.getContext('2d');
            this.resizeCanvas();

            this.bands.forEach(f => { this.gains[f] = 0; });
            this.createSliders();
            this.draw();

            this.canvas.addEventListener('mousedown', e => this.onMouseDown(e));
            this.canvas.addEventListener('mousemove', e => this.onMouseMove(e));
            this.canvas.addEventListener('mouseup', () => this.dragging = -1);
            this.canvas.addEventListener('mouseleave', () => this.dragging = -1);
            window.addEventListener('resize', () => { this.resizeCanvas(); this.draw(); });

            document.getElementById('btnEqReset')?.addEventListener('click', () => this.reset());
            document.getElementById('btnEqAuto')?.addEventListener('click', () => this.autoCorrect());

            this.bindMixSliders();
        },

        resizeCanvas() {
            if (!this.canvas) return;
            const rect = this.canvas.parentElement.getBoundingClientRect();
            this.canvas.width = rect.width - 8;
            this.canvas.height = 200;
        },

        createSliders() {
            const container = document.getElementById('eqSliders');
            if (!container) return;
            container.innerHTML = '';

            const displayBands = [64, 125, 250, 500, 1000, 2000, 4000, 8000, 12000, 16000];
            const MIN = -12, MAX = 12;
            displayBands.forEach(f => {
                const group = document.createElement('div');
                group.className = 'eq-slider-group';
                const label = document.createElement('label');
                label.textContent = f >= 1000 ? (f / 1000).toFixed(0) + 'k' : f + 'Hz';

                // ==== FADER KUSTOM (div+drag) — identik di semua engine ====
                const fader = document.createElement('div');
                fader.className = 'fader-custom';
                fader.dataset.freq = f;
                fader.dataset.min = MIN;
                fader.dataset.max = MAX;
                fader.innerHTML =
                    '<div class="fader-track"></div>' +
                    '<div class="fader-cap"></div>';
                const cap = fader.querySelector('.fader-cap');

                const span = document.createElement('span');
                span.textContent = '0dB';

                // nilai internal
                let value = 0;
                const self = this;
                function setPos(v) {
                    v = Math.max(MIN, Math.min(MAX, v));
                    v = Math.round(v / 0.5) * 0.5;
                    value = v;
                    const pct = (v - MIN) / (MAX - MIN);       // 0 bawah .. 1 atas
                    cap.style.bottom = 'calc(' + (pct * 100) + '% - 11px)';
                    span.textContent = v > 0 ? '+' + v.toFixed(1) : v.toFixed(1);
                    self.gains[f] = v;
                    self.draw();
                }
                fader._setValue = setPos;    // supaya reset/match bisa panggil

                function pointerToValue(clientY) {
                    const rect = fader.getBoundingClientRect();
                    const pct = 1 - (clientY - rect.top) / rect.height;  // atas=1
                    return MIN + pct * (MAX - MIN);
                }
                let dragging = false;
                function down(e) {
                    dragging = true;
                    const y = e.touches ? e.touches[0].clientY : e.clientY;
                    setPos(pointerToValue(y));
                    e.preventDefault();
                }
                function move(e) {
                    if (!dragging) return;
                    const y = e.touches ? e.touches[0].clientY : e.clientY;
                    setPos(pointerToValue(y));
                }
                function up() { dragging = false; }
                fader.addEventListener('mousedown', down);
                window.addEventListener('mousemove', move);
                window.addEventListener('mouseup', up);
                fader.addEventListener('touchstart', down, { passive: false });
                window.addEventListener('touchmove', move, { passive: false });
                window.addEventListener('touchend', up);
                // klik ganda = reset ke 0
                fader.addEventListener('dblclick', () => setPos(0));

                setPos(0);
                group.appendChild(label);
                group.appendChild(fader);
                group.appendChild(span);
                container.appendChild(group);
            });
        },

        bindMixSliders() {
            const bindRange = (id, displayId, suffix = '') => {
                const input = document.getElementById(id);
                const display = document.getElementById(displayId);
                if (!input || !display) return;
                input.addEventListener('input', () => {
                    display.textContent = input.value + suffix;
                });
            };

            bindRange('mixStereoWidth', 'mixStereoWidthVal', '%');
            bindRange('mixMidGain', 'mixMidGainVal', ' dB');
            bindRange('mixSideGain', 'mixSideGainVal', ' dB');
            bindRange('mixAttack', 'mixAttackVal', ' dB');
            bindRange('mixSustain', 'mixSustainVal', ' dB');
            bindRange('masterStereoWidth', 'masterStereoWidthVal', '%');
            bindRange('compLowThresh', 'compLowThreshVal', 'dB');
            bindRange('compLowRatio', 'compLowRatioVal', ':1');
            bindRange('compLowAttack', 'compLowAttackVal', 'ms');
            bindRange('compLowRelease', 'compLowReleaseVal', 'ms');
            bindRange('compMidThresh', 'compMidThreshVal', 'dB');
            bindRange('compMidRatio', 'compMidRatioVal', ':1');
            bindRange('compMidAttack', 'compMidAttackVal', 'ms');
            bindRange('compMidRelease', 'compMidReleaseVal', 'ms');
            bindRange('compHighThresh', 'compHighThreshVal', 'dB');
            bindRange('compHighRatio', 'compHighRatioVal', ':1');
            bindRange('compHighAttack', 'compHighAttackVal', 'ms');
            bindRange('compHighRelease', 'compHighReleaseVal', 'ms');
        },

        draw() {
            if (!this.ctx || !this.canvas) return;
            const w = this.canvas.width;
            const h = this.canvas.height;
            const ctx = this.ctx;

            ctx.clearRect(0, 0, w, h);

            ctx.strokeStyle = '#252550';
            ctx.lineWidth = 1;
            for (let db = -12; db <= 12; db += 6) {
                const y = h / 2 - (db / 12) * (h / 2.2);
                ctx.beginPath();
                ctx.moveTo(30, y);
                ctx.lineTo(w - 10, y);
                ctx.stroke();
                ctx.fillStyle = '#606080';
                ctx.font = '9px JetBrains Mono';
                ctx.fillText(db + 'dB', 2, y + 3);
            }

            const points = [];
            const bands = Object.keys(this.gains).map(Number).sort((a, b) => a - b);
            const minFreq = Math.log10(bands[0]);
            const maxFreq = Math.log10(bands[bands.length - 1]);

            bands.forEach(f => {
                const x = 30 + ((Math.log10(f) - minFreq) / (maxFreq - minFreq)) * (w - 40);
                const y = h / 2 - (this.gains[f] / 12) * (h / 2.2);
                points.push({ x, y, f });
            });

            if (points.length > 0) {
                for (let i = 1; i < points.length; i++) {
                    const cp1x = (points[i].x + points[i - 1].x) / 2;
                    const cp1y = points[i - 1].y;
                    const cp2x = (points[i].x + points[i - 1].x) / 2;
                    const cp2y = points[i].y;

                    ctx.strokeStyle = '#ffd700';
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(points[i - 1].x, points[i - 1].y);
                    ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, points[i].x, points[i].y);
                    ctx.stroke();

                    const grad = ctx.createLinearGradient(0, h / 2, 0, points[0].y);
                    grad.addColorStop(0, 'rgba(255,215,0,0)');
                    grad.addColorStop(1, 'rgba(255,215,0,0.15)');
                    ctx.fillStyle = grad;
                    ctx.lineTo(points[i].x, h / 2);
                }
            }

            points.forEach(p => {
                ctx.fillStyle = '#ffd700';
                ctx.beginPath();
                ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = '#0a0a1a';
                ctx.lineWidth = 1.5;
                ctx.stroke();
            });
        },

        onMouseDown(e) {
            const rect = this.canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            const bands = Object.keys(this.gains).map(Number).sort((a, b) => a - b);
            const minFreq = Math.log10(bands[0]);
            const maxFreq = Math.log10(bands[bands.length - 1]);
            const w = this.canvas.width;
            const h = this.canvas.height;

            for (let i = 0; i < bands.length; i++) {
                const x = 30 + ((Math.log10(bands[i]) - minFreq) / (maxFreq - minFreq)) * (w - 40);
                const y = h / 2 - (this.gains[bands[i]] / 12) * (h / 2.2);
                const dist = Math.sqrt((mx - x) ** 2 + (my - y) ** 2);
                if (dist < 12) {
                    this.dragging = i;
                    this.updateGain(i, my, h);
                    return;
                }
            }
        },

        onMouseMove(e) {
            if (this.dragging < 0) return;
            const rect = this.canvas.getBoundingClientRect();
            const my = e.clientY - rect.top;
            this.updateGain(this.dragging, my, this.canvas.height);
        },

        updateGain(index, my, h) {
            const bands = Object.keys(this.gains).map(Number).sort((a, b) => a - b);
            const freq = bands[index];
            const gain = Math.round(((h / 2 - my) / (h / 2.2)) * 12 * 2) / 2;
            const clamped = Math.max(-12, Math.min(12, gain));
            this.gains[freq] = clamped;
            this.draw();
            this.updateSlider(freq, clamped);
        },

        updateSlider(freq, value) {
            const fader = document.querySelector(`#eqSliders .fader-custom[data-freq="${freq}"]`);
            if (fader && fader._setValue) fader._setValue(value);
        },

        reset() {
            Object.keys(this.gains).forEach(f => { this.gains[f] = 0; });
            document.querySelectorAll('#eqSliders .fader-custom').forEach(fd => {
                if (fd._setValue) fd._setValue(0);
            });
            this.draw();
        },

        autoCorrect() {
            const corrections = {
                250: -2, 500: -1.5,
                2000: -1.5, 4000: -1,
                8000: 1.5, 16000: 1,
                125: -1.5,
            };
            Object.keys(corrections).forEach(f => {
                this.gains[parseInt(f)] = corrections[f];
            });
            this.draw();
            Object.keys(corrections).forEach(f => {
                this.updateSlider(parseInt(f), corrections[f]);
            });
        },

        setGains(newGains) {
            Object.entries(newGains || {}).forEach(([f, v]) => {
                const key = parseInt(f);
                const val = parseFloat(v);
                if (!isFinite(val)) return;
                this.gains[key] = val;
                const fader = document.querySelector(`#eqSliders .fader-custom[data-freq="${key}"]`);
                if (fader && fader._setValue) fader._setValue(val);
            });
            this.draw();
        },

        getGains() {
            return { ...this.gains };
        },

        updateFromAnalysis(data) {
            const issues = data.issues || [];
            const autoFixes = {};
            issues.forEach(issue => {
                switch (issue.type) {
                    case 'muddy': autoFixes[250] = -2; autoFixes[500] = -1.5; break;
                    case 'harsh': autoFixes[2000] = -2; autoFixes[4000] = -1; break;
                    case 'boomy': autoFixes[125] = -2; break;
                    case 'dull': autoFixes[4000] = 2; autoFixes[8000] = 2; break;
                    case 'lacking_air': autoFixes[8000] = 2; autoFixes[16000] = 2; break;
                }
            });
            Object.keys(autoFixes).forEach(f => {
                this.gains[parseInt(f)] = autoFixes[f];
                this.updateSlider(parseInt(f), autoFixes[f]);
            });
            this.draw();
            App.notify('Auto-EQ corrections applied based on analysis', 'success');
        },
    };

    document.addEventListener('DOMContentLoaded', () => Equalizer.init());
})();
