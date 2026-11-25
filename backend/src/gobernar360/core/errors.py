"""API error type and the JSON shape every error response uses."""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: list[dict] | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


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


def already_registered() -> ApiError:
    return ApiError(409, "already_registered", "This person is already registered here.")


def dni_exists() -> ApiError:
    return ApiError(409, "dni_exists", "Another person already has this document number.")


def household_has_head() -> ApiError:
    return ApiError(409, "household_has_head", "This household already has a head.")


def in_another_household() -> ApiError:
    return ApiError(409, "in_another_household", "This person belongs to another household.")


def in_use(message: str = "The resource is referenced by other records.") -> ApiError:
    return ApiError(409, "in_use", message)


def invalid_reference(message: str) -> ApiError:
    return ApiError(422, "invalid_reference", message)


def validation_error(message: str) -> ApiError:
    return ApiError(422, "validation_error", message)


def future_month() -> ApiError:
    return ApiError(422, "future_month", "A month that has not started cannot be given a status.")


def invalid_token() -> ApiError:
    return ApiError(410, "invalid_token", "The link is not valid: it expired or was already used.")


def too_many_requests() -> ApiError:
    return ApiError(429, "too_many_requests", "Too many requests. Try again later.")


def invalid_location(message: str) -> ApiError:
    return ApiError(422, "invalid_location", message)


def map_api_key_required() -> ApiError:
    return ApiError(422, "map_api_key_required", "This map needs a key from its provider.")


def invalid_area(message: str) -> ApiError:
    return ApiError(422, "invalid_area", message)


def invalid_boundary(message: str) -> ApiError:
    return ApiError(422, "invalid_boundary", message)


def zone_not_closed() -> ApiError:
    return ApiError(
        422, "zone_not_closed", "The boundary is not closed: its last corner must be its first one."
    )


def zone_self_intersects(reason: str) -> ApiError:
    return ApiError(422, "zone_self_intersects", f"The boundary crosses itself: {reason}.")


def zone_name_exists() -> ApiError:
    return ApiError(409, "zone_name_exists", "Another zone already has this name.")


def zone_changed() -> ApiError:
    return ApiError(
        409, "zone_changed", "Somebody else changed the boundary of this zone in the meantime."
    )


def zone_file_invalid(details: list[dict]) -> ApiError:
    return ApiError(
        422, "zone_file_invalid", "The file was not imported: some zones have problems.", details
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        extra = {} if exc.details is None else {"details": exc.details}
        return error_response(exc.status_code, exc.code, exc.message, **extra)

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
