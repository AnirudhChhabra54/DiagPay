import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.exceptions import ConflictException, NotFoundException, UnauthorizedException
from app.logging_config import logger
from app.models.user import User, UserRole
from app.schemas.user import TokenResponse, UserLoginRequest, UserResponse, UserSignupRequest

settings = get_settings()


class AuthService:
    @staticmethod
    async def signup(db: AsyncSession, payload: UserSignupRequest) -> User:
        """Register a new user with Argon2 hashed password."""
        email_clean = payload.email.strip().lower()
        stmt = select(User).where(User.email == email_clean)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            logger.info("auth_signup_duplicate_email", email=email_clean)
            raise ConflictException(
                detail="A user with this email address already exists.",
                code="EMAIL_ALREADY_EXISTS",
            )

        hashed_pw = hash_password(payload.password)
        new_user = User(
            email=email_clean,
            password_hash=hashed_pw,
            full_name=payload.full_name.strip(),
            role=payload.role or UserRole.USER,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(
            "auth_signup_success",
            user_id=str(new_user.id),
            email=new_user.email,
            role=new_user.role.value,
        )
        return new_user

    @staticmethod
    async def login(db: AsyncSession, payload: UserLoginRequest) -> TokenResponse:
        """Verify user credentials and return a signed JWT token."""
        email_clean = payload.email.strip().lower()
        stmt = select(User).where(User.email == email_clean)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(payload.password, user.password_hash):
            logger.warning("auth_login_failed", email=email_clean)
            raise UnauthorizedException(
                detail="Incorrect email or password.",
                code="INVALID_CREDENTIALS",
            )

        token = create_access_token(subject=str(user.id), role=user.role.value)
        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

        logger.info("auth_login_success", user_id=str(user.id), role=user.role.value)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=expires_in,
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException(
                detail="User not found.",
                code="USER_NOT_FOUND",
            )
        return user
