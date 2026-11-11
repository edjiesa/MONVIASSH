import base64
import os
from cryptography.fernet import Fernet
from app.config import settings

def _get_or_create_key() -> bytes:
    key_file = settings.SECRET_KEY_FILE
    if key_file.exists():
        return key_file.read_bytes().strip()
    
    # Generate new Fernet key and save to disk
    key = Fernet.generate_key()
    key_file.write_bytes(key)
    return key

_fernet = None

def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = _get_or_create_key()
        _fernet = Fernet(key)
    return _fernet

def encrypt_secret(plain_text: str | None) -> str | None:
    if not plain_text:
        return None
    f = get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")

def decrypt_secret(cipher_text: str | None) -> str | None:
    if not cipher_text:
        return None
    try:
        f = get_fernet()
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        # In case key changed or corrupted
        return None
