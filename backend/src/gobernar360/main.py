"""Application factory."""

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from gobernar360.core.config import get_settings
from gobernar360.core.errors import error_response, install_error_handlers
from gobernar360.dashboards import (
    cabinet,
    economic,
    environment,
    procedures,
    projects,
    registry,
    social,
)
from gobernar360.platform import (
    admin_router,
    auth_router,
    commitments_router,
    directory,
    notifications_router,
    operator_router,
    overview_router,
    settings_router,
    sso_router,
    status_router,
    subjects_router,
)

CSRF_HEADER = "x-requested-with"
CSRF_HEADER_VALUE = "gobernar360"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def register_dashboards() -> None:
    """Install every dashboard module. Also used by commands that run outside the API."""
    for module in (
        projects.module,
        environment.module,
        economic.module,
        social.module,
        procedures.module,
        cabinet.module,
    ):
        registry.register(module)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="gobernar360", docs_url="/api/docs", openapi_url="/api/openapi.json")
    install_error_handlers(app)

    @app.middleware("http")
    async def require_csrf_header(request: Request, call_next):
        # Browsers cannot add a custom header to a cross-site form post, so requiring
        # one on unsafe methods blocks cross-site request forgery with cookie sessions.
        if (
            request.method not in SAFE_METHODS
            and request.url.path.startswith("/api")
            and request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE
        ):
            return error_response(
                403, "csrf_header_missing", "The X-Requested-With header is required."
            )
        return await call_next(request)

    # Added last so it wraps every response, including the CSRF rejection.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    register_dashboards()

    api.include_router(auth_router.router)
    api.include_router(sso_router.router)
    api.include_router(notifications_router.router)
    api.include_router(operator_router.router)
    api.include_router(admin_router.router)
    api.include_router(settings_router.router)
    api.include_router(overview_router.router)
    api.include_router(status_router.router)
    api.include_router(subjects_router.router)
    api.include_router(directory.router)
    api.include_router(commitments_router.router)
    for module in registry.all_modules():
        api.include_router(module.router, prefix=f"/dashboards/{module.key}", tags=[module.key])
    app.include_router(api)
    return app
