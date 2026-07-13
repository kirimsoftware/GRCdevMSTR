"""
GRCmasteringStudio — Licensing
Lisensi offline berbasis tanda tangan digital Ed25519, terikat Hardware ID.

- Key digenerate pemilik dengan PRIVATE key (tool terpisah, JANGAN ada di app).
- App hanya memegang PUBLIC key: bisa MEMVERIFIKASI, mustahil MEMBUAT key.
- Payload berisi hwid + mode (lifetime/monthly) + exp; diverifikasi ULANG
  pada setiap render (bukan sekali di startup) agar sulit dilewati.
"""
import os
import re
import sys
import json
import base64
import hashlib
import datetime
import subprocess

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from config import OUTPUT_FOLDER

PUBLIC_KEY_B64 = 'XsipshG4Rrocnc0G2dhiiJK5/zw3Z/U2tjpipxnVBRg='
LICENSE_PATH = os.path.join(os.path.dirname(OUTPUT_FOLDER), 'license.key')


# ---------------- Hardware ID ----------------

def _raw_machine_id():
    try:
        if sys.platform == 'darwin':
            out = subprocess.check_output(
                ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
                stderr=subprocess.DEVNULL).decode()
            m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
            if m:
                return m.group(1)
        elif os.name == 'nt':
            out = subprocess.check_output(
                ['reg', 'query',
                 r'HKLM\SOFTWARE\Microsoft\Cryptography', '/v', 'MachineGuid'],
                stderr=subprocess.DEVNULL).decode(errors='ignore')
            return out.strip().split()[-1]
        else:
            with open('/etc/machine-id') as f:
                return f.read().strip()
    except Exception:
        pass
    import uuid
    return str(uuid.getnode())


def get_hwid():
    """Hardware ID stabil per mesin, format XXXX-XXXX-XXXX-XXXX."""
    h = hashlib.sha256(('GRC1|' + _raw_machine_id()).encode()).hexdigest().upper()[:16]
    return '-'.join(h[i:i + 4] for i in range(0, 16, 4))


# ---------------- Verifikasi ----------------

def _b64d(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def verify_license(token):
    """Verifikasi token. Mengembalikan (payload_dict, None) atau (None, error)."""
    try:
        token = (token or '').strip()
        p64, s64 = token.split('.')
        payload, sig = _b64d(p64), _b64d(s64)
        Ed25519PublicKey.from_public_bytes(
            base64.b64decode(PUBLIC_KEY_B64)).verify(sig, payload)
        d = json.loads(payload)
        if d.get('product') != 'GRCmasteringStudio':
            return None, 'Invalid license key'
        if d.get('hwid') != get_hwid():
            return None, 'This key is bound to a different machine'
        if d.get('mode') == 'monthly':
            exp = d.get('exp', '')
            if not exp or datetime.date.today().isoformat() > exp:
                return None, 'License expired — please renew'
        return d, None
    except Exception:
        return None, 'Invalid license key'


def save_license(token):
    d, err = verify_license(token)
    if err:
        return None, err
    os.makedirs(os.path.dirname(LICENSE_PATH), exist_ok=True)
    with open(LICENSE_PATH, 'w') as f:
        f.write(token.strip())
    return d, None


def load_license():
    """Baca + verifikasi ulang token tersimpan. Dipanggil di SETIAP render."""
    try:
        with open(LICENSE_PATH) as f:
            return verify_license(f.read())
    except OSError:
        return None, 'Not activated'
