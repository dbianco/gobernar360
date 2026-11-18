"""API error type and the JSON shape every error response uses."""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(status_code: int, code: str, message: str, **extra: object) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message, **extra}}
    )


def not_authenticated() -> ApiError:
    return ApiError(401, "not_authenticated", "Authentication is required.")


def forbidden(message: str = "You do not have access to this resource.") -> ApiError:
    return ApiError(403, "forbidden", message)


def not_found(message: str = "Resource not found.") -> ApiError:
    return ApiError(404, "not_found", message)


def conflict(message: str) -> ApiError:
    return ApiError(409, "conflict", message)


def in_use(message: str = "The resource is referenced by other records.") -> ApiError:
    return ApiError(409, "in_use", message)


def invalid_reference(message: str) -> ApiError:
    return ApiError(422, "invalid_reference", message)


def validation_error(message: str) -> ApiError:
    return ApiError(422, "validation_error", message)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in error["loc"][1:]), "message": error["msg"]}
            for error in exc.errors()
        ]
        return error_response(
            422, "validation_error", "The request is not valid.", details=jsonable_encoder(details)
        )
