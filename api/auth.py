from __future__ import annotations

import os
import jwt
import datetime
import hashlib
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.getenv("JWT_SECRET", "sparksage-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password: str, hashed: str) -> bool:
    if "$" not in hashed:
        return False
    salt, expected = hashed.split("$", 1)
    actual = hashlib.sha256((salt + password).encode()).hexdigest()
    return secrets.compare_digest(actual, expected)


def create_token(user_id: str) -> tuple[str, str]:
    """Create a JWT token. Returns (token, expires_at iso string)."""
    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "sub": user_id,
        "exp": expires,
        "iat": datetime.datetime.now(datetime.timezone.utc),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires.isoformat()


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


bearer_scheme = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    """FastAPI dependency — validates Bearer token and returns payload."""
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return payload


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    """Alias for get_current_user — for backwards compatibility."""
    return get_current_user(credentials)