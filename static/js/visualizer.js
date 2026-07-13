(() => {
    window.Visualizer = {
        init() {},

        drawSpectrum(canvas, freqs, spectrum) {
            if (!canvas || !freqs || !spectrum) return;

            const w = canvas.parentElement.clientWidth - 8;
            const h = 180;
            canvas.width = w;
            canvas.height = h;

            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, w, h);

            ctx.strokeStyle = '#252550';
            ctx.lineWidth = 0.5;
            for (let i = 0; i < 5; i++) {
                const y = (h / 5) * i;
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(w, y);
                ctx.stroke();
            }

            const maxVal = Math.max(...spectrum) || 1;
            const n = Math.min(spectrum.length, freqs.length);

            ctx.strokeStyle = '#ffd700';
            ctx.lineWidth = 1.5;
            ctx.beginPath();

            for (let i = 0; i < n; i++) {
                const x = (i / n) * w;
                const y = h - (spectrum[i] / maxVal) * h * 0.9;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();

            const grad = ctx.createLinearGradient(0, h, 0, 0);
            grad.addColorStop(0, 'rgba(255,215,0,0)');
            grad.addColorStop(1, 'rgba(255,215,0,0.08)');
            ctx.fillStyle = grad;
            ctx.lineTo(w, h);
            ctx.lineTo(0, h);
            ctx.fill();

            ctx.fillStyle = '#606080';
            ctx.font = '9px JetBrains Mono';
            const keyFreqs = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000];
            keyFreqs.forEach(f => {
                const idx = freqs.findIndex(fr => fr >= f);
                if (idx > 0) {
                    const x = (idx / n) * w;
                    ctx.fillText(f >= 1000 ? (f / 1000) + 'k' : f + 'Hz', x - 10, h - 4);
                }
            });
        },

        drawMinimalWaveform(canvas, audioEl) {
            if (!canvas || !audioEl) return;

            const w = canvas.parentElement.clientWidth;
            const h = 40;
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, w, h);

            ctx.strokeStyle = '#252550';
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(0, h / 2);
            ctx.lineTo(w, h / 2);
            ctx.stroke();

            const barCount = 120;
            const barWidth = w / barCount;
            for (let i = 0; i < barCount; i++) {
                const height = Math.abs(Math.sin(i * 0.15) * (h / 2 - 2));
                const alpha = 0.3 + Math.random() * 0.3;
                ctx.fillStyle = `rgba(255, 215, 0, ${alpha})`;
                ctx.fillRect(i * barWidth + 1, h / 2 - height, barWidth - 2, height * 2);
            }
        },
    };

    document.addEventListener('DOMContentLoaded', () => Visualizer.init());
})();
