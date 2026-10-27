import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _get_fernet_key() -> bytes:
    """
    Derive or load the 32-byte urlsafe base64-encoded key for Fernet symmetric encryption.
    If FIELD_ENCRYPTION_KEY is provided in settings, use that; otherwise derive deterministically
    from SECRET_KEY so development environments run securely without manual key generation.
    """
    if getattr(settings, "FIELD_ENCRYPTION_KEY", None):
        key = settings.FIELD_ENCRYPTION_KEY.strip().encode()
        if len(key) == 44:  # standard base64 32-byte key length
            return key
    
    # Deterministic fallback derivation from SECRET_KEY
    derived = hashlib.sha256(b"safepath-field-encryption:" + settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(derived)


_fernet: Optional[Fernet] = None


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_get_fernet_key())
    return _fernet


def encrypt_field(plaintext: str) -> str:
    """
    Encrypt a plaintext string using AES-128-CBC with PKCS7 padding and HMAC-SHA256 integrity.
    Returns a urlsafe base64 string.
    """
    if not plaintext:
        return ""
    f = get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_field(ciphertext: str) -> str:
    """
    Decrypt a ciphertext string. If the value is not valid ciphertext (e.g. legacy plaintext
    during data migration), returns the input gracefully to avoid application crashes.
    """
    if not ciphertext:
        return ""
    # Check if value appears to be a Fernet token (starts with gAAAAA)
    if not ciphertext.startswith("gAAAAA"):
        return ciphertext
    
    try:
        f = get_fernet()
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        # Fallback if decryption fails or key mismatch
        return ciphertext


def mask_phone_number(phone: str) -> str:
    """
    Mask a phone number for administrative or public display.
    Example: '+919876543210' -> '+91 98*** **210' or '***-***-3210'
    """
    if not phone:
        return ""
    digits = [c for c in phone if c.isdigit()]
    if len(digits) < 6:
        return "***"
    
    # Keep first 3-4 chars (e.g. country code + prefix) and last 3-4 digits, mask middle
    if phone.startswith("+"):
        prefix = phone[:5]
        suffix = phone[-3:]
        return f"{prefix}*** ***{suffix}"
    elif len(phone) >= 10:
        return f"{phone[:3]}-***-**{phone[-2:]}"
    else:
        return f"***{phone[-4:]}"


def mask_email(email: str) -> str:
    """
    Mask an email address for administrative list display.
    Example: 'jane.doe@example.com' -> 'j***e@e***e.com'
    """
    if not email or "@" not in email:
        return "hidden@safepath.local"
    
    parts = email.strip().lower().split("@")
    user_part = parts[0]
    domain_part = parts[1]
    
    # Mask user part
    if len(user_part) <= 2:
        masked_user = user_part[0] + "***"
    else:
        masked_user = user_part[0] + "***" + user_part[-1]
    
    # Mask domain part
    domain_subparts = domain_part.split(".")
    if len(domain_subparts) >= 2:
        dom_name = domain_subparts[0]
        ext = ".".join(domain_subparts[1:])
        if len(dom_name) <= 2:
            masked_dom = dom_name[0] + "***"
        else:
            masked_dom = dom_name[0] + "***" + dom_name[-1]
        masked_domain = f"{masked_dom}.{ext}"
    else:
        masked_domain = "***"
    
    return f"{masked_user}@{masked_domain}"
