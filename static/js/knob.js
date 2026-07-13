/* Knob — mengubah <input type="range" class="knob"> menjadi knob rotary analog.
   Interaksi: drag vertikal, scroll wheel, double-click = reset ke default.
   Input asli tetap hidup (hidden) dan memancarkan event 'input',
   jadi semua listener lama tetap bekerja. */
(() => {
    const SWEEP = 270;          // derajat putaran total (-135..+135)
    const START = -135;

    function build(input) {
        if (input.dataset.knobified) return;
        input.dataset.knobified = '1';

        const min = parseFloat(input.min || 0);
        const max = parseFloat(input.max || 100);
        const def = parseFloat(input.defaultValue);
        const suffix = input.dataset.suffix || '';
        const label = input.dataset.label || '';

        const wrap = document.createElement('div');
        wrap.className = 'knob-ctl' + (input.classList.contains('knob-lg') ? ' knob-ctl-lg' : '');
        wrap.innerHTML = `
            <div class="knob-dial">
                <div class="knob-ticks"></div>
                <div class="knob-cap"><div class="knob-pointer"></div></div>
            </div>
            <div class="knob-value"></div>
            <div class="knob-label"></div>`;
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);           // input ikut di dalam, disembunyikan via CSS
        wrap.querySelector('.knob-label').textContent = label;

        // tick marks statis
        const ticks = wrap.querySelector('.knob-ticks');
        for (let i = 0; i <= 10; i++) {
            const t = document.createElement('i');
            t.style.transform = `rotate(${START + (SWEEP * i / 10)}deg)`;
            ticks.appendChild(t);
        }

        const cap = wrap.querySelector('.knob-cap');
        const valEl = wrap.querySelector('.knob-value');

        function render() {
            const v = parseFloat(input.value);
            const pct = (v - min) / (max - min);
            cap.style.transform = `rotate(${START + pct * SWEEP}deg)`;   // hanya pointer wrapper yg berputar
            wrap.style.setProperty('--pct', pct);
            const txt = (input.step && parseFloat(input.step) < 1) ? v.toFixed(1) : Math.round(v);
            valEl.textContent = txt + suffix;
        }

        function setValue(v) {
            v = Math.min(max, Math.max(min, v));
            const step = parseFloat(input.step || 1);
            v = Math.round(v / step) * step;
            if (String(v) !== input.value) {
                input.value = v;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
            render();
        }

        // drag vertikal
        let startY = 0, startVal = 0;
        function onMove(e) {
            const y = (e.touches ? e.touches[0].clientY : e.clientY);
            const range = max - min;
            setValue(startVal + (startY - y) * (range / 150));   // 150px = full sweep
            e.preventDefault();
        }
        function onUp() {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onUp);
            wrap.classList.remove('active');
        }
        wrap.querySelector('.knob-dial').addEventListener('mousedown', e => {
            startY = e.clientY; startVal = parseFloat(input.value);
            wrap.classList.add('active');
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
            e.preventDefault();
        });
        wrap.querySelector('.knob-dial').addEventListener('touchstart', e => {
            startY = e.touches[0].clientY; startVal = parseFloat(input.value);
            wrap.classList.add('active');
            document.addEventListener('touchmove', onMove, { passive: false });
            document.addEventListener('touchend', onUp);
        }, { passive: true });

        // scroll & reset
        wrap.addEventListener('wheel', e => {
            e.preventDefault();
            const step = parseFloat(input.step || 1);
            setValue(parseFloat(input.value) + (e.deltaY < 0 ? step : -step));
        }, { passive: false });
        wrap.addEventListener('dblclick', () => setValue(def));

        input.addEventListener('input', render);
        render();
    }

    window.Knob = {
        init() { document.querySelectorAll('input[type="range"].knob').forEach(build); },
    };
    document.addEventListener('DOMContentLoaded', () => Knob.init());
})();
