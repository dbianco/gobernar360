"""API error type and the JSON shape every error response uses."""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def error_response(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
    **extra: object,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, **extra}},
        headers=headers,
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


def invalid_transition(message: str) -> ApiError:
    return ApiError(409, "invalid_transition", message)


def case_not_open() -> ApiError:
    return ApiError(409, "case_not_open", "The complaint is no longer open.")


def municipality_suspended() -> ApiError:
    return ApiError(403, "municipality_suspended", "This municipality is suspended.")


def future_month() -> ApiError:
    return ApiError(422, "future_month", "A month that has not started cannot be given a status.")


def meeting_closed() -> ApiError:
    return ApiError(409, "meeting_closed", "The meeting is closed: its minutes are frozen.")


def meeting_not_closed() -> ApiError:
    return ApiError(409, "meeting_not_closed", "The meeting has no minutes until it is closed.")


def meeting_already_open() -> ApiError:
    return ApiError(409, "meeting_already_open", "Close the open meeting before preparing another.")


def meeting_before_last() -> ApiError:
    return ApiError(422, "meeting_before_last", "A meeting cannot be dated before the last one.")


def agenda_changed() -> ApiError:
    return ApiError(409, "agenda_changed", "The proposed agenda changed. Load it again.")


def commitment_finished() -> ApiError:
    return ApiError(409, "commitment_finished", "The commitment is no longer open.")


def invalid_token() -> ApiError:
    return ApiError(410, "invalid_token", "The link is not valid: it expired or was already used.")


def too_many_requests() -> ApiError:
    return ApiError(429, "too_many_requests", "Too many requests. Try again later.")


def month_not_over() -> ApiError:
    return ApiError(422, "month_not_over", "Only a month that has ended can be closed.")


def not_aggregate() -> ApiError:
    return ApiError(
        422, "not_aggregate", "Only indicators declared aggregate in the catalogue are published."
    )


def dashboard_not_published() -> ApiError:
    return ApiError(422, "dashboard_not_published", "Publish the dashboard before its indicators.")


def personal_data() -> ApiError:
    return ApiError(
        422,
        "personal_data",
        "A comment of the report names a person or a document number of the registry.",
    )


def slug_taken() -> ApiError:
    return ApiError(409, "slug_taken", "Another municipality already uses this public address.")


def rate_limited(retry_after: int) -> ApiError:
    return ApiError(
        429,
        "rate_limited",
        "Too many requests; try again in a moment.",
        headers={"Retry-After": str(retry_after)},
    )


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
        return error_response(exc.status_code, exc.code, exc.message, headers=exc.headers, **extra)

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
