"""
utils/security.py  –  API key encryption / decryption using Fernet (AES-128-CBC)

The secret key is derived from SECURITY_KEY env var (or auto-generated and saved).
"""

import os
import base64
import logging
from pathlib import Path

logger = logging.getLogger("security")

_KEY_FILE = ".security_key"


def _get_fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError("Install cryptography: pip install cryptography")

    key_env = os.getenv("SECURITY_KEY")
    if key_env:
        key = key_env.encode()
    elif Path(_KEY_FILE).exists():
        key = Path(_KEY_FILE).read_bytes().strip()
    else:
        key = Fernet.generate_key()
        Path(_KEY_FILE).write_bytes(key)
        logger.warning(
            f"Generated new encryption key → {_KEY_FILE}. "
            "Back this up or set SECURITY_KEY env var."
        )
    return Fernet(key)


def encrypt_key(plaintext: str) -> str:
    """Encrypt an API key string → base64 token."""
    try:
        f = _get_fernet()
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        # Fallback: store obfuscated (not secure, logs warning)
        logger.warning("Falling back to base64 obfuscation (install cryptography for real encryption)")
        return base64.b64encode(plaintext.encode()).decode()


def decrypt_key(token: str) -> str:
    """Decrypt a token back to plaintext API key."""
    try:
        f = _get_fernet()
        return f.decrypt(token.encode()).decode()
    except Exception:
        # Try base64 fallback
        try:
            return base64.b64decode(token.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return token   # return as-is if all else fails
