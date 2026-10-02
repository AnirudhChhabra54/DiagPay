import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings
from app.exceptions import UnauthorizedException
from app.logging_config import logger

settings = get_settings()
ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2 hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception as e:
        logger.warning("password_verification_error", error=str(e))
        return False


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token containing subject (user_id), role, and expiration."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(subject),
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    encoded_jwt = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedException(
            detail="Token has expired. Please log in again.",
            code="TOKEN_EXPIRED",
        ) from e
    except jwt.InvalidTokenError as e:
        raise UnauthorizedException(
            detail=f"Invalid authentication token: {str(e)}",
            code="TOKEN_INVALID",
        ) from e


def verify_webhook_hmac_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Verify webhook payload using HMAC-SHA256 signature."""
    if not signature_header:
        return False
    computed_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    # constant-time comparison
    return hmac.compare_digest(computed_signature, signature_header)


def compute_webhook_signature(raw_body: bytes) -> str:
    """Helper to compute webhook HMAC-SHA256 signature for clients/testing."""
    return hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
