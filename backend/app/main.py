import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import ping, prepare_database
from .routers import applications, auth, notifications, terms, users

logger = logging.getLogger("sams")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    prepare_database()
    for warning in settings.configuration_warnings():
        logger.warning("Configuration: %s", warning)
    logger.info("Auth provider: %s", settings.auth_provider)
    logger.info("Storage backend: %s", settings.storage_backend)
    logger.info("Database: %s", settings.resolved_database_url.split("@")[-1])
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["Content-Disposition"],
        )

    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(terms.router, prefix="/api")
    app.include_router(applications.router, prefix="/api")
    app.include_router(notifications.router, prefix="/api")

    @app.get("/api/health", tags=["health"])
    def health():
        return {
            "status": "ok",
            "database": ping(),
            "authProvider": settings.auth_provider,
            "storageBackend": settings.storage_backend,
        }

    frontend = settings.resolved_frontend_dir
    if settings.serve_frontend and frontend.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend), html=True), name="frontend")
        logger.info("Serving the frontend from %s", frontend)

    return app


app = create_app()
