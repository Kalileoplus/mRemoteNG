"""
Crittografia compatibile con mRemoteNG - AES-256-GCM + PBKDF2
"""
import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

DEFAULT_KDF_ITERATIONS = 1000
SALT_LENGTH = 16
NONCE_LENGTH = 12


def derive_key(password: str, salt: bytes, iterations: int = DEFAULT_KDF_ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=32,
        salt=salt,
        iterations=iterations,
        backend=default_backend()
    )
    return kdf.derive(password.encode('utf-8'))


def encrypt(plaintext: str, master_password: str = "") -> str:
    """Cifra una stringa con AES-256-GCM. Restituisce base64."""
    if not plaintext:
        return ""
    if not master_password:
        master_password = _get_machine_key()
    salt  = os.urandom(SALT_LENGTH)
    nonce = os.urandom(NONCE_LENGTH)
    key   = derive_key(master_password, salt)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    blob = salt + nonce + ct
    return base64.b64encode(blob).decode('ascii')


def decrypt(ciphertext: str, master_password: str = "") -> str:
    """Decifra una stringa cifrata con encrypt(). Restituisce plaintext."""
    if not ciphertext:
        return ""
    if not master_password:
        master_password = _get_machine_key()
    try:
        blob  = base64.b64decode(ciphertext)
        salt  = blob[:SALT_LENGTH]
        nonce = blob[SALT_LENGTH:SALT_LENGTH + NONCE_LENGTH]
        ct    = blob[SALT_LENGTH + NONCE_LENGTH:]
        key   = derive_key(master_password, salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode('utf-8')
    except Exception:
        # Potrebbe essere non cifrato (testo in chiaro da file legacy)
        return ciphertext


def _get_machine_key() -> str:
    """Chiave macchina derivata da valori locali (compatibile con mRemoteNG)."""
    import platform
    node = platform.node() or "mRemoteNGDefault"
    return hashlib.sha256(node.encode()).hexdigest()[:32]


def hash_string(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()
