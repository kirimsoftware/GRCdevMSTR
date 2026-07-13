import os
import gc
import json
import uuid
import threading
from flask import Flask, render_template, request, jsonify, send_file
import urllib.parse
from werkzeug.utils import secure_filename
from config import UPLOAD_FOLDER, OUTPUT_FOLDER, FILE_RETENTION_HOURS
from audio_engine.converter import convert_mp3_to_wav, convert_audio_file, FORMATS
from audio_engine.mixer import process_mix
from audio_engine.masterer import process_master
from audio_engine.analyzer import analyze_audio
from licensing import get_hwid, verify_license, save_license, load_license
from audio_engine.decoder import decode_audio
from audio_engine.lufs import measure_lufs
from audio_engine.cleanup import cleanup_old_files

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024


PROGRESS = {}
RESULTS = {}
MAX_TRACKED_TASKS = 50


def _trim(store, keep=MAX_TRACKED_TASKS):
    # Bound memory: drop oldest entries (dicts keep insertion order in py3.7+)
    while len(store) > keep:
        store.pop(next(iter(store)))


def allowed_file(filename):
    ALLOWED = {'mp3', 'wav', 'flac', 'ogg', 'aiff', 'm4a'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


def progress_tracker(task_id):
    def callback(pct, msg):
        PROGRESS[task_id] = {'percent': pct, 'message': msg}
    return callback


def _log_error(task_id, exc):
    """Laporkan exception dari background thread ke UI + tulis ke file log."""
    import traceback
    err = f'{type(exc).__name__}: {exc}'
    RESULTS[task_id] = {'error': f'Processing failed — {err}'}
    PROGRESS[task_id] = {'percent': 100, 'message': f'Error: {err}'}
    try:
        log_dir = os.path.dirname(OUTPUT_FOLDER)
        with open(os.path.join(log_dir, 'error.log'), 'a') as f:
            f.write(f'\n[task {task_id}]\n{traceback.format_exc()}\n')
    except OSError:
        pass


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    _trim(PROGRESS)
    _trim(RESULTS)
    cleanup_old_files(FILE_RETENTION_HOURS)

    fname = secure_filename(file.filename)
    task_id = str(uuid.uuid4())[:8]
    ext = fname.rsplit('.', 1)[1].lower()
    saved_name = f'{task_id}.{ext}'
    filepath = os.path.join(UPLOAD_FOLDER, saved_name)
    file.save(filepath)

    return jsonify({
        'task_id': task_id,
        'filename': fname,
        'filepath': filepath,
    })


@app.route('/api/convert', methods=['POST'])
def convert():
    _gate = _license_gate()
    if _gate is not None:
        return _gate
    data = request.get_json() or {}
    filepath = data.get('filepath', '')
    task_id = data.get('task_id', '')
    sample_rate = data.get('sample_rate', 44100)
    remove_wm = data.get('remove_watermark', True)
    out_format = data.get('format', 'wav24')
    normalize = data.get('normalize', True)
    air_enhance = data.get('air_enhance', False)

    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

        # Reset state: hindari progress basi / hasil lama terbaca oleh polling
    PROGRESS[task_id] = {'percent': 0, 'message': 'Decoding & analyzing audio...'}
    RESULTS.pop(task_id, None)

    def run():
        try:
            cb = progress_tracker(task_id)
            out_path, stats = convert_audio_file(filepath, out_format, sample_rate,
                                                  normalize=normalize, remove_wm=remove_wm,
                                                  air_enhance=air_enhance,
                                                  progress_callback=cb)

            original_filename = data.get('filename', 'output')
            base_name = os.path.splitext(original_filename)[0]
            ext = FORMATS.get(out_format, '.wav')
            download_name = f"{base_name}_converted{ext}"
            encoded_name = urllib.parse.quote(download_name)
        
            RESULTS[task_id] = {
                'output_path': out_path,
                'output_url': f'/api/download?file={os.path.basename(out_path)}&name={encoded_name}',
                'stats': stats,
            }
            cb(100, 'Complete')
            gc.collect()

        except Exception as e:
            _log_error(task_id, e)

    thread = threading.Thread(target=run)
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'processing'})


@app.route('/api/mix', methods=['POST'])
def mix():
    data = request.get_json() or {}
    filepath = data.get('filepath', '')
    task_id = data.get('task_id', '')
    settings = data.get('settings', {})

    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    def run():
        try:
            cb = progress_tracker(task_id)
            out_path = process_mix(filepath, settings, progress_callback=cb)
        
            original_filename = data.get('filename', 'output')
            base_name = os.path.splitext(original_filename)[0]
            download_name = f"{base_name}_mix.wav"
            encoded_name = urllib.parse.quote(download_name)
        
            RESULTS[task_id] = {
                'output_path': out_path,
                'output_url': f'/api/download?file={os.path.basename(out_path)}&name={encoded_name}',
                'stats': {},
            }
            cb(100, 'Complete')
            gc.collect()

        except Exception as e:
            _log_error(task_id, e)

    thread = threading.Thread(target=run)
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'processing'})


@app.route('/api/master', methods=['POST'])
def master():
    _gate = _license_gate()
    if _gate is not None:
        return _gate
    data = request.get_json() or {}
    filepath = data.get('filepath', '')
    task_id = data.get('task_id', '')
    genre = data.get('genre', 'pop')
    platform = data.get('platform', 'spotify')
    settings = data.get('settings', {})
    remove_wm = data.get('remove_watermark', True)

    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

        # Reset state: hindari progress basi / hasil lama terbaca oleh polling
    PROGRESS[task_id] = {'percent': 0, 'message': 'Decoding & analyzing audio...'}
    RESULTS.pop(task_id, None)

    def run():
        try:
            cb = progress_tracker(task_id)
            out_path, stats = process_master(filepath, genre, platform, remove_wm, settings,
                                              progress_callback=cb)
                                          
            original_filename = data.get('filename', 'output')
            base_name = os.path.splitext(original_filename)[0]
            download_name = f"{base_name}_master.wav"
            encoded_name = urllib.parse.quote(download_name)
        
            RESULTS[task_id] = {
                'output_path': out_path,
                'output_url': f'/api/download?file={os.path.basename(out_path)}&name={encoded_name}',
                'stats': stats,
            }
            cb(100, 'Complete')
            gc.collect()

        except Exception as e:
            _log_error(task_id, e)

    thread = threading.Thread(target=run)
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'processing'})


@app.route('/api/progress/<task_id>')
def progress(task_id):
    return jsonify(PROGRESS.get(task_id, {'percent': 0, 'message': 'Waiting...'}))


@app.route('/api/result/<task_id>')
def result(task_id):
    result = RESULTS.get(task_id)
    if result:
        return jsonify(result)
    prog = PROGRESS.get(task_id)
    if prog is not None:
        # Task dikenal tapi hasil belum siap -> minta klien mencoba lagi
        return jsonify({'pending': True, 'percent': prog.get('percent', 0)}), 202
    return jsonify({'error': 'Task not found'}), 404


@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.get_json() or {}
    filepath = data.get('filepath', '')
    genre = data.get('genre', 'pop')

    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    audio, sr, _ = decode_audio(filepath)
    results = analyze_audio(audio, sr)
    lufs_val = measure_lufs(audio, sr)
    results['lufs'] = lufs_val
    # kurva spektrum terukur (untuk panel analyzer di bawah Master)
    from audio_engine.adaptive import _measured_curve, EQ_BANDS, fine_spectrum, tonal_zones
    curve = _measured_curve(audio, sr)
    results['curve'] = {str(f): round(float(v), 2) for f, v in zip(EQ_BANDS, curve)}
    results['spectrum'] = fine_spectrum(audio, sr)
    results['tonal_zones'] = tonal_zones(audio, sr, genre)
    del audio
    gc.collect()

    return jsonify(results)


@app.route('/api/adaptive', methods=['POST'])
def adaptive():
    """Analisis material -> starting point EQ/kompresor menuju target genre."""
    data = request.get_json() or {}
    filepath = data.get('filepath', '')
    genre = data.get('genre', 'pop')
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    from audio_engine.adaptive import derive_adaptive_settings
    audio, sr, _ = decode_audio(filepath)
    result = derive_adaptive_settings(audio, sr, genre)
    del audio
    gc.collect()
    return jsonify(result)


@app.route('/api/match_reference', methods=['POST'])
def match_reference():
    """EQ matching presisi: analisis source vs reference (file di-upload)
    dengan FFT resolusi tinggi di backend, bukan aproksimasi browser.
    Menerima multipart: 'reference' (file) + 'filepath' (source di server)."""
    source_fp = request.form.get('filepath', '')
    strength = request.form.get('strength', '')
    if not source_fp or not os.path.exists(source_fp):
        return jsonify({'error': 'Source file not found'}), 404
    if 'reference' not in request.files:
        return jsonify({'error': 'No reference file'}), 400
    ref_file = request.files['reference']
    if not ref_file or not allowed_file(ref_file.filename):
        return jsonify({'error': 'Invalid reference file type'}), 400

    # simpan reference sementara
    ref_ext = secure_filename(ref_file.filename).rsplit('.', 1)[1].lower()
    ref_path = os.path.join(UPLOAD_FOLDER, f'ref_{uuid.uuid4().hex[:8]}.{ref_ext}')
    ref_file.save(ref_path)
    try:
        from audio_engine.adaptive import match_reference_eq
        src_audio, src_sr, _ = decode_audio(source_fp)
        ref_audio, ref_sr, _ = decode_audio(ref_path)
        kwargs = {}
        try:
            if strength:
                kwargs['strength'] = float(strength)
        except ValueError:
            pass
        result = match_reference_eq(src_audio, src_sr, ref_audio, ref_sr, **kwargs)
        del src_audio, ref_audio
        gc.collect()
        return jsonify(result)
    finally:
        try:
            os.remove(ref_path)
        except OSError:
            pass


@app.route('/api/license/status')
def license_status():
    d, err = load_license()
    return jsonify({
        'hwid': get_hwid(),
        'licensed': d is not None,
        'mode': (d or {}).get('mode'),
        'exp': (d or {}).get('exp'),
        'name': (d or {}).get('name'),
        'message': err,
    })


@app.route('/api/license/activate', methods=['POST'])
def license_activate():
    data = request.get_json() or {}
    d, err = save_license(data.get('key', ''))
    if err:
        return jsonify({'error': err}), 400
    return jsonify({'ok': True, 'mode': d.get('mode'), 'exp': d.get('exp')})


def _license_gate():
    """Verifikasi ULANG signature+hwid+exp pada setiap pemrosesan."""
    d, err = load_license()
    if d is None:
        return jsonify({'error': 'License required: ' + (err or 'not activated')}), 403
    return None


@app.route('/api/album/zip', methods=['POST'])
def album_zip():
    """Gabungkan beberapa hasil master jadi satu ZIP untuk download album."""
    _gate = _license_gate()
    if _gate is not None:
        return _gate
    import zipfile, io
    data = request.get_json() or {}
    items = data.get('files', [])  # [{file, name}, ...]
    if not items:
        return jsonify({'error': 'No files'}), 400
    album_name = secure_filename(data.get('album', 'Album')) or 'Album'
    buf = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        used = set()
        for it in items:
            fn = secure_filename(it.get('file', ''))
            nm = it.get('name', fn) or fn
            src = os.path.join(OUTPUT_FOLDER, fn)
            if not os.path.exists(src):
                continue
            # hindari nama duplikat dalam zip
            arc = nm
            base, ext = os.path.splitext(arc)
            n = 1
            while arc in used:
                arc = f'{base} ({n}){ext}'; n += 1
            used.add(arc)
            zf.write(src, arc)
            added += 1
    if added == 0:
        # jangan kirim zip kosong — di sisi klien akan tampak "corrupted"
        return jsonify({'error': 'No output files found'}), 404
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f'{album_name}_mastered.zip',
                     mimetype='application/zip')


@app.route('/api/album/zip_save', methods=['POST'])
def album_zip_save():
    """Buat ZIP album dan SIMPAN LANGSUNG ke folder Downloads user.
    Andal di jendela desktop (webview tidak perlu meng-handle unduhan blob,
    yang sering menghasilkan file rusak)."""
    _gate = _license_gate()
    if _gate is not None:
        return _gate
    import zipfile
    data = request.get_json() or {}
    items = data.get('files', [])
    if not items:
        return jsonify({'error': 'No files'}), 400
    album_name = secure_filename(data.get('album', 'Album')) or 'Album'
    downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
    os.makedirs(downloads, exist_ok=True)
    dest = os.path.join(downloads, f'{album_name}_mastered.zip')
    base, ext = os.path.splitext(dest)
    n = 1
    while os.path.exists(dest):
        dest = f'{base} ({n}){ext}'; n += 1
    added = 0
    tmp = dest + '.part'
    try:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
            used = set()
            for it in items:
                fn = secure_filename(it.get('file', ''))
                nm = it.get('name', fn) or fn
                src = os.path.join(OUTPUT_FOLDER, fn)
                if not os.path.exists(src):
                    continue
                arc = nm
                b, e = os.path.splitext(arc)
                k = 1
                while arc in used:
                    arc = f'{b} ({k}){e}'; k += 1
                used.add(arc)
                zf.write(src, arc)
                added += 1
        if added == 0:
            os.remove(tmp)
            return jsonify({'error': 'No output files found'}), 404
        os.replace(tmp, dest)  # tulis atomik: zip tidak pernah setengah jadi
    except Exception as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return jsonify({'error': f'ZIP failed — {e}'}), 500
    return jsonify({'saved': added, 'zip': os.path.basename(dest), 'folder': downloads})


@app.route('/api/album/save', methods=['POST'])
def album_save():
    """Simpan semua hasil album ke folder Downloads/<album> — untuk desktop."""
    _gate = _license_gate()
    if _gate is not None:
        return _gate
    import shutil
    data = request.get_json() or {}
    items = data.get('files', [])
    album_name = secure_filename(data.get('album', 'Album')) or 'Album'
    if not items:
        return jsonify({'error': 'No files'}), 400
    downloads = os.path.join(os.path.expanduser('~'), 'Downloads', album_name)
    os.makedirs(downloads, exist_ok=True)
    saved = 0
    for it in items:
        fn = secure_filename(it.get('file', ''))
        nm = secure_filename(it.get('name', fn)) or fn
        src = os.path.join(OUTPUT_FOLDER, fn)
        if not os.path.exists(src):
            continue
        dest = os.path.join(downloads, nm)
        base, ext = os.path.splitext(dest)
        n = 1
        while os.path.exists(dest):
            dest = f'{base} ({n}){ext}'; n += 1
        shutil.copy2(src, dest)
        saved += 1
    return jsonify({'saved': saved, 'folder': downloads})


@app.route('/api/download')
def download():
    filename = request.args.get('file', '')
    download_name = request.args.get('name', filename)
    filepath = os.path.join(OUTPUT_FOLDER, secure_filename(filename))
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    # play=1 -> stream inline (untuk player A/B); default -> paksa download
    as_attachment = request.args.get('play') != '1'
    return send_file(filepath, as_attachment=as_attachment, download_name=download_name)


@app.route('/api/original')
def original():
    """Serve file upload asli untuk A/B compare & waveform 'before'."""
    task_id = secure_filename(request.args.get('task_id', ''))
    if task_id:
        for name in os.listdir(UPLOAD_FOLDER):
            if name.startswith(task_id + '.'):
                return send_file(os.path.join(UPLOAD_FOLDER, name))
    return jsonify({'error': 'Original not found'}), 404


@app.route('/api/save')
def save_to_downloads():
    """Salin hasil ke folder Downloads user — andal di jendela desktop."""
    import shutil
    filename = request.args.get('file', '')
    save_name = secure_filename(request.args.get('name', filename)) or 'output.wav'
    src = os.path.join(OUTPUT_FOLDER, secure_filename(filename))
    if not os.path.exists(src):
        return jsonify({'error': 'File not found'}), 404
    downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
    os.makedirs(downloads, exist_ok=True)
    dest = os.path.join(downloads, save_name)
    # hindari menimpa: tambahkan (1), (2), ... jika sudah ada
    base, ext = os.path.splitext(dest)
    n = 1
    while os.path.exists(dest):
        dest = f'{base} ({n}){ext}'
        n += 1
    shutil.copy2(src, dest)
    return jsonify({'saved': dest, 'name': os.path.basename(dest)})


@app.route('/api/presets/<preset_type>/<preset_name>')
def get_preset(preset_type, preset_name):
    preset_dir = os.path.join(os.path.dirname(__file__), 'presets')
    filepath = os.path.join(preset_dir, f'{preset_type}_{preset_name}.json')
    if not os.path.exists(filepath):
        return jsonify({'error': 'Preset not found'}), 404
    with open(filepath) as f:
        return jsonify(json.load(f))


if __name__ == '__main__':
    cleanup_old_files(FILE_RETENTION_HOURS)
    print('=' * 50)
    print('  GRCmasteringStudio — Audio Mastering Suite')
    print('  http://localhost:5000')
    print('=' * 50)
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
