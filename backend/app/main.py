import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import SessionLocal, ping, prepare_database
from .demo_seed import ensure_demo_accounts as seed_demo_accounts
from .routers import applications, auth, notifications, users
from .routers import terms as terms_router
from .services import terms

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
    logger.info("Site URL: %s", settings.site_url)

    session = SessionLocal()
    try:
        seed_demo_accounts(session)
        terms.current_term(db=session)
    finally:
        session.close()
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
    app.include_router(terms_router.router, prefix="/api")
    app.include_router(applications.router, prefix="/api")
    app.include_router(notifications.router, prefix="/api")

    @app.get("/api/health", tags=["health"])
    def health():
        try:
            database = ping()
        except Exception as error:  # noqa: BLE001
            logger.warning("Health check could not reach the database: %s", error)
            database = False
        return {
            "status": "ok" if database else "degraded",
            "database": database,
            "authProvider": settings.auth_provider,
            "storageBackend": settings.storage_backend,
        }

    frontend = settings.resolved_frontend_dir
    if settings.serve_frontend and frontend.is_dir():
        # Only the website folders are published. The repository root is never
        # mounted, so backend sources, supabase/ and any .env file stay private.
        for folder in ("assets", "css", "js"):
            path = frontend / folder
            if path.is_dir():
                app.mount(f"/{folder}", StaticFiles(directory=str(path)), name=folder)

        templates = frontend / "template"
        if templates.is_dir():
            app.mount("/template", StaticFiles(directory=str(templates), html=True), name="template")

            @app.get("/", include_in_schema=False)
            @app.get("/index.html", include_in_schema=False)
            def landing_page():
                return FileResponse(frontend / "index.html")

        logger.info("Serving the frontend from %s", frontend)

    return app


app = create_app()
