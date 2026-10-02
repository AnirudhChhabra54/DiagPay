from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.logging_config import logger


class AppException(Exception):
    def __init__(
        self,
        detail: str,
        code: str = "BAD_REQUEST",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        extra: dict[str, Any] | None = None,
    ):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        self.extra = extra or {}
        super().__init__(detail)


class NotFoundException(AppException):
    def __init__(self, detail: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(
            detail=detail,
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictException(AppException):
    def __init__(self, detail: str = "Resource conflict", code: str = "CONFLICT"):
        super().__init__(
            detail=detail,
            code=code,
            status_code=status.HTTP_409_CONFLICT,
        )


class UnauthorizedException(AppException):
    def __init__(
        self,
        detail: str = "Could not validate credentials",
        code: str = "UNAUTHORIZED",
    ):
        super().__init__(
            detail=detail,
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(AppException):
    def __init__(
        self,
        detail: str = "Permission denied",
        code: str = "FORBIDDEN",
    ):
        super().__init__(
            detail=detail,
            code=code,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ValidationException(AppException):
    def __init__(
        self,
        detail: str = "Request validation failed",
        code: str = "VALIDATION_ERROR",
        extra: dict[str, Any] | None = None,
    ):
        super().__init__(
            detail=detail,
            code=code,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            extra=extra,
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(
            "app_exception",
            path=request.url.path,
            method=request.method,
            code=exc.code,
            detail=exc.detail,
            status_code=exc.status_code,
        )
        content = {"detail": exc.detail, "code": exc.code}
        if exc.extra:
            content.update(exc.extra)
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        error_msgs = []
        for err in errors:
            loc = " -> ".join(str(loc_part) for loc_part in err.get("loc", []))
            msg = err.get("msg", "Invalid value")
            error_msgs.append(f"{loc}: {msg}")
        detail_msg = "; ".join(error_msgs) if error_msgs else "Validation error"

        logger.info(
            "validation_error",
            path=request.url.path,
            method=request.method,
            detail=detail_msg,
        )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": detail_msg,
                "code": "VALIDATION_ERROR",
                "errors": jsonable_encoder(errors),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_internal_error",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred. Please try again later.",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )
