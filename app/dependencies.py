import uuid

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import decode_access_token, verify_webhook_hmac_signature
from app.database import get_db
from app.exceptions import ForbiddenException, UnauthorizedException
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

settings = get_settings()
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency to extract and validate the authenticated user from JWT Bearer token."""
    if not credentials or not credentials.credentials:
        raise UnauthorizedException(
            detail="Authentication token is missing.",
            code="AUTHENTICATION_REQUIRED",
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedException(
            detail="Token subject is missing.",
            code="TOKEN_INVALID",
        )

    try:
        user_id = uuid.UUID(sub)
    except ValueError as e:
        raise UnauthorizedException(
            detail="Token subject is not a valid UUID.",
            code="TOKEN_INVALID",
        ) from e

    user = await AuthService.get_by_id(db, user_id)
    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency requiring ADMIN role."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException(
            detail="Administrative privileges are required to perform this action.",
            code="ADMIN_PRIVILEGES_REQUIRED",
        )
    return current_user


async def verify_webhook_signature(
    request: Request,
    x_webhook_signature: str | None = Header(None, alias="X-Webhook-Signature"),
) -> None:
    """Validate webhook HMAC signature if secret is active and header is provided."""
    # If signature header is provided or if signature enforcement is configured:
    if x_webhook_signature:
        body = await request.body()
        is_valid = verify_webhook_hmac_signature(body, x_webhook_signature)
        if not is_valid:
            raise UnauthorizedException(
                detail="Invalid webhook HMAC signature.",
                code="INVALID_WEBHOOK_SIGNATURE",
            )
