(() => {
    const App = {
        currentTab: 'master',
        state: {},

        init() {
            this.bindTabs();
            this.bindGlobalDragDrop();
        },

        bindTabs() {
            document.querySelectorAll('.nav-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const tab = btn.dataset.tab;
                    if (tab) this.switchTab(tab);
                });
            });
        },

        switchTab(tab) {
            this.currentTab = tab;
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            document.querySelector(`[data-tab="${tab}"]`)?.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById(`tab-${tab}`)?.classList.add('active');
        },

        bindGlobalDragDrop() {
            const overlay = document.getElementById('uploadOverlay');
            if (!overlay) return;

            let dragCounter = 0;
            document.addEventListener('dragenter', e => {
                e.preventDefault();
                dragCounter++;
                if (dragCounter === 1) overlay.classList.add('show');
            });
            document.addEventListener('dragleave', e => {
                e.preventDefault();
                dragCounter--;
                if (dragCounter === 0) overlay.classList.remove('show');
            });
            document.addEventListener('dragover', e => e.preventDefault());
            document.addEventListener('drop', e => {
                e.preventDefault();
                dragCounter = 0;
                overlay.classList.remove('show');
                const files = e.dataTransfer?.files;
                if (files?.length) this.handleGlobalDrop(files[0]);
            });
        },

        handleGlobalDrop(file) {
            switch (this.currentTab) {
                case 'convert':
                    if (typeof Uploader !== 'undefined') Uploader.handleFile(file, 'convert');
                    break;
                case 'mix':
                    if (typeof Uploader !== 'undefined') Uploader.handleFile(file, 'mix');
                    break;
                case 'master':
                    if (typeof Uploader !== 'undefined') Uploader.handleFile(file, 'master');
                    break;
            }
        },

        notify(msg, type = '') {
            const el = document.getElementById('notification');
            if (!el) return;
            el.textContent = msg;
            el.className = 'notification ' + type + ' show';
            clearTimeout(el._timeout);
            el._timeout = setTimeout(() => el.classList.remove('show'), 3000);
        },

        formatBytes(b) {
            if (b < 1024) return b + ' B';
            if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
            return (b / 1048576).toFixed(1) + ' MB';
        },

        formatTime(s) {
            const m = Math.floor(s / 60);
            const sec = Math.floor(s % 60);
            return `${m}:${sec.toString().padStart(2, '0')}`;
        }
    };

    window.App = App;
    document.addEventListener('DOMContentLoaded', () => App.init());
})();
