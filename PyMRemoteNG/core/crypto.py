"""
Crittografia compatibile con mRemoteNG - AES-256-GCM + PBKDF2
"""
import logging
import os
import base64
import hashlib
import secrets
from typing import Optional
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

DEFAULT_KDF_ITERATIONS = 1000   # legacy — usato solo per decifrare vecchi blob
_V2_ITERATIONS         = 100_000
_V2_PREFIX             = "v2:"
SALT_LENGTH  = 16
NONCE_LENGTH = 12

# Prefisso che indica chiave protetta con Windows DPAPI
_DPAPI_MAGIC = b"NX1:"

_DEVICE_KEY_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "Nexus", "device_key.bin"
)


def derive_key(password: str, salt: bytes,
               iterations: int = DEFAULT_KDF_ITERATIONS) -> bytes:
    """PBKDF2-SHA1 legacy — usato solo per decifrare blob esistenti."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=32,
        salt=salt,
        iterations=iterations,
        backend=default_backend()
    )
    return kdf.derive(password.encode('utf-8'))


def _derive_key_v2(password: str, salt: bytes) -> bytes:
    """PBKDF2-SHA256 con 100K iterazioni (formato v2)."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_V2_ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(password.encode('utf-8'))


def encrypt(plaintext: str, master_password: str = "") -> str:
    """Cifra con AES-256-GCM + PBKDF2-SHA256/100K (formato v2). Restituisce base64 con prefisso v2:."""
    if not plaintext:
        return ""
    if not master_password:
        master_password = _get_device_key()
    salt   = os.urandom(SALT_LENGTH)
    nonce  = os.urandom(NONCE_LENGTH)
    key    = _derive_key_v2(master_password, salt)
    aesgcm = AESGCM(key)
    ct     = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    blob   = salt + nonce + ct
    return _V2_PREFIX + base64.b64encode(blob).decode('ascii')


def decrypt(ciphertext: str, master_password: str = "") -> str:
    """Decifra una stringa cifrata con encrypt(). Restituisce plaintext."""
    if not ciphertext:
        return ""
    if master_password:
        return _try_decrypt(ciphertext, master_password) or ciphertext

    result = _try_decrypt(ciphertext, _get_device_key())
    if result is not None:
        return result

    # Fallback: chiave macchina legacy (dati cifrati con versioni precedenti)
    result = _try_decrypt(ciphertext, _get_machine_key())
    if result is not None:
        logging.warning("Dato decifrato con chiave macchina legacy — ri-cifrare con device key.")
        return result

    return ciphertext


def _try_decrypt(ciphertext: str, password: str) -> Optional[str]:
    """
    Tenta la decifratura AES-GCM.
    Distingue tag di autenticazione invalido (manomissione) da altri errori.
    """
    try:
        if ciphertext.startswith(_V2_PREFIX):
            raw    = base64.b64decode(ciphertext[len(_V2_PREFIX):])
            key_fn = _derive_key_v2
        else:
            raw    = base64.b64decode(ciphertext)
            key_fn = lambda pw, salt: derive_key(pw, salt)  # noqa: E731
        salt   = raw[:SALT_LENGTH]
        nonce  = raw[SALT_LENGTH:SALT_LENGTH + NONCE_LENGTH]
        ct     = raw[SALT_LENGTH + NONCE_LENGTH:]
        key    = key_fn(password, salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode('utf-8')
    except InvalidTag:
        # Tag GCM non valido = possibile manomissione del ciphertext
        logging.warning("SECURITY: AES-GCM authentication tag non valido — possibile manomissione dati.")
        return None
    except UnicodeDecodeError:
        logging.warning("Decifratura: dato autentico ma non decodificabile come UTF-8.")
        return None
    except Exception:
        return None


# ── Windows DPAPI — lega la device key al profilo utente ─────────────────────

def _dpapi_protect(data: bytes) -> bytes:
    """Cifra data con Windows DPAPI (bound al profilo utente corrente)."""
    try:
        import ctypes
        from ctypes import wintypes

        class _BLOB(ctypes.Structure):
            _fields_ = [('cbData', wintypes.DWORD),
                        ('pbData', ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        in_blob = _BLOB(len(data),
                        ctypes.cast(ctypes.c_char_p(data),
                                    ctypes.POINTER(ctypes.c_char)))
        out_blob = _BLOB()
        if crypt32.CryptProtectData(
            ctypes.byref(in_blob), None, None, None, None, 0,
            ctypes.byref(out_blob)
        ):
            result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return _DPAPI_MAGIC + result
    except Exception as e:
        logging.error(f"DPAPI protect fallito: {e}")
    return data  # fallback: nessuna protezione aggiuntiva


def _dpapi_unprotect(raw: bytes) -> Optional[bytes]:
    """
    Decifra una chiave: usa DPAPI se il magic è presente, altrimenti raw.
    Restituisce None in caso di errore.
    """
    if not raw.startswith(_DPAPI_MAGIC):
        return raw if len(raw) >= 32 else None  # formato legacy (32 byte raw)

    blob = raw[len(_DPAPI_MAGIC):]
    try:
        import ctypes
        from ctypes import wintypes

        class _BLOB(ctypes.Structure):
            _fields_ = [('cbData', wintypes.DWORD),
                        ('pbData', ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        in_blob = _BLOB(len(blob),
                        ctypes.cast(ctypes.c_char_p(blob),
                                    ctypes.POINTER(ctypes.c_char)))
        out_blob = _BLOB()
        if crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0,
            ctypes.byref(out_blob)
        ):
            result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return result
    except Exception as e:
        logging.error(f"DPAPI unprotect fallito: {e}")
    return None


# ── Device key ────────────────────────────────────────────────────────────────

def _get_device_key() -> str:
    """
    Chiave device: generata casualmente al primo avvio, salvata su file protetto.
    Su Windows viene ulteriormente protetta con DPAPI (bound al profilo utente).
    V6-01 fix: apri direttamente senza os.path.exists (elimina TOCTOU).
    """
    try:
        with open(_DEVICE_KEY_PATH, "rb") as f:
            raw = f.read()
        _restrict_file_permissions(_DEVICE_KEY_PATH)
        key_bytes = _dpapi_unprotect(raw)
        if key_bytes and len(key_bytes) >= 32:
            return key_bytes[:32].hex()
    except FileNotFoundError:
        pass  # Prima esecuzione: genera nuova chiave
    except Exception as e:
        logging.error(f"Lettura device key fallita: {e}")

    key_bytes = secrets.token_bytes(32)
    try:
        os.makedirs(os.path.dirname(_DEVICE_KEY_PATH), exist_ok=True)
        protected = _dpapi_protect(key_bytes) if os.name == 'nt' else key_bytes
        with open(_DEVICE_KEY_PATH, "wb") as f:
            f.write(protected)
        _restrict_file_permissions(_DEVICE_KEY_PATH)
    except Exception as e:
        logging.error(f"Salvataggio device key fallito: {e}")
    return key_bytes.hex()


def _restrict_file_permissions(path: str) -> None:
    """
    Limita i permessi del file al solo utente corrente.
    V6-09 fix: logga esplicitamente i fallimenti.
    """
    if os.name == 'nt':
        try:
            import subprocess as _sp
            username = os.environ.get('USERNAME', '')
            if not username:
                logging.warning("_restrict_file_permissions: USERNAME non disponibile.")
                return
            result = _sp.run(
                ['icacls', path, '/inheritance:r', '/grant:r', f'{username}:(F)'],
                capture_output=True, timeout=5
            )
            if result.returncode != 0:
                logging.error(
                    f"icacls fallito (rc={result.returncode}) su {path}: "
                    f"{result.stderr.decode(errors='replace').strip()}"
                )
        except Exception as e:
            logging.error(f"_restrict_file_permissions Windows fallito: {e}")
    else:
        try:
            os.chmod(path, 0o600)
        except Exception as e:
            logging.error(f"chmod 0o600 fallito su {path}: {e}")


def _get_machine_key() -> str:
    """Chiave legacy: derivata dal nome macchina. Usata solo come fallback per dati esistenti."""
    import platform
    node = platform.node() or "mRemoteNGDefault"
    return hashlib.sha256(node.encode()).hexdigest()[:32]


def hash_string(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()
