"""Auth: password hashing, JWT, credential encryption."""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet
from jose import jwt, JWTError
from passlib.context import CryptContext

from .config import get_settings

settings = get_settings()

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(pw: str) -> str:
    return _pwd.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _pwd.verify(pw, hashed)
    except Exception:
        return False


def create_access_token(sub: str, extra: Optional[dict] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": sub, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except JWTError:
        return None


# --- Credential encryption (envelope-ish; for production use a KMS, not local key) ---

def _fernet() -> Fernet:
    key = settings.credential_enc_key.strip()
    if not key:
        # Deterministic dev fallback derived from app_secret. NEVER use in production.
        digest = hashlib.sha256(settings.app_secret.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    return _fernet().decrypt(token.encode()).decode()
