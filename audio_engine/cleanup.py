import os
import time
from config import UPLOAD_FOLDER, OUTPUT_FOLDER, TEMP_FOLDER


def remove_temp_file(path):
    """Delete an intermediate decoded file, but only if it lives in TEMP_FOLDER.

    decode_audio() returns the original input path for wav/flac/ogg (which may be
    a user upload), so the TEMP_FOLDER guard prevents deleting source files.
    """
    if not path:
        return
    try:
        temp_root = os.path.abspath(TEMP_FOLDER)
        if os.path.abspath(os.path.dirname(path)) == temp_root and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def cleanup_old_files(max_age_hours=6, folders=(UPLOAD_FOLDER, OUTPUT_FOLDER, TEMP_FOLDER)):
    """Delete files older than max_age_hours from the given folders. Returns count removed."""
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for folder in folders:
        try:
            entries = os.listdir(folder)
        except OSError:
            continue
        for name in entries:
            fpath = os.path.join(folder, name)
            try:
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    removed += 1
            except OSError:
                pass
    return removed
