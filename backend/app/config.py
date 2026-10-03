from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Panpacific University Scholarship System API"
    environment: str = "development"
    auth_provider: str = "local"
    jwt_secret: str = "dev-secret-change-me-please-replace-0123456789"
    access_token_minutes: int = 480
    refresh_token_days: int = 14
    database_url: str = "sqlite:///./var/dev.db"

    university_email_domain: str = "@panpacificu.edu.ph"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_timeout: float = 15.0
    password_reset_redirect: str = ""
    frontend_url: str = "http://localhost:8000"

    storage_backend: str = "local"
    storage_bucket: str = "scholarship-documents"
    upload_dir: str = "./var/uploads"
    max_upload_mb: int = 5

    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    serve_frontend: bool = True
    frontend_dir: str = ".."

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in {"development", "dev", "local"}

    @property
    def uses_supabase_auth(self) -> bool:
        return self.auth_provider.strip().lower() == "supabase"

    @property
    def uses_supabase_storage(self) -> bool:
        return self.storage_backend.strip().lower() == "supabase"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def supabase_root(self) -> str:
        return self.supabase_url.rstrip("/")

    @property
    def supabase_auth_url(self) -> str:
        return f"{self.supabase_root}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_auth_url}/.well-known/jwks.json"

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        if url.startswith("sqlite") and ":///" in url:
            prefix, _, path = url.partition(":///")
            candidate = Path(path)
            if not candidate.is_absolute():
                candidate = (BACKEND_DIR / path.lstrip("./")).resolve()
            url = f"{prefix}:///{candidate}"
        return url

    @property
    def resolved_upload_dir(self) -> Path:
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = BACKEND_DIR / self.upload_dir.lstrip("./")
        return path.resolve()

    @property
    def resolved_frontend_dir(self) -> Path:
        path = Path(self.frontend_dir)
        if not path.is_absolute():
            path = BACKEND_DIR / self.frontend_dir
        return path.resolve()

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    def configuration_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.uses_supabase_auth:
            missing = [
                name
                for name, value in (
                    ("SUPABASE_URL", self.supabase_url),
                    ("SUPABASE_ANON_KEY", self.supabase_anon_key),
                    ("SUPABASE_SERVICE_KEY", self.supabase_service_key),
                )
                if not value
            ]
            if missing:
                warnings.append(f"AUTH_PROVIDER=supabase but missing: {', '.join(missing)}")
        if self.uses_supabase_storage:
            missing = [
                name
                for name, value in (
                    ("SUPABASE_URL", self.supabase_url),
                    ("SUPABASE_SERVICE_KEY", self.supabase_service_key),
                )
                if not value
            ]
            if missing:
                warnings.append(f"STORAGE_BACKEND=supabase but missing: {', '.join(missing)}")
        if not self.is_development and self.jwt_secret.startswith("dev-secret-change-me"):
            warnings.append("JWT_SECRET is still the development default")
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
