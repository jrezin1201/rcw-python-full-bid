"""
Application configuration management using Pydantic Settings.
All settings can be overridden via environment variables.
"""

from typing import Any, List

from pydantic import AnyHttpUrl, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "FastAPI SaaS Starter"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    API_KEY: str | None = None  # Optional API key for extraction service

    # Database
    DATABASE_URL: str | None = None  # Optional: Use this if set (e.g., sqlite:///./data/dev.db)
    POSTGRES_SERVER: str | None = None
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Get database URI - supports both SQLite and PostgreSQL."""
        # If DATABASE_URL is explicitly set, use it verbatim
        if self.DATABASE_URL:
            return self.DATABASE_URL

        # Otherwise, construct from POSTGRES_* variables
        if self.POSTGRES_SERVER and self.POSTGRES_USER and self.POSTGRES_PASSWORD and self.POSTGRES_DB:
            return (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        # Default to SQLite for local dev if nothing is configured
        return "sqlite:///./data/dev.db"

    @property
    def DATABASE_URI(self) -> str:
        """Alias for SQLAlchemy database URI (for compatibility)."""
        return self.SQLALCHEMY_DATABASE_URI

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.SQLALCHEMY_DATABASE_URI.startswith("sqlite")

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        """Construct Redis URL."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str] | str:
        """Parse CORS origins from string or list."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # First superuser (created on startup)
    DISABLE_BOOTSTRAP_USERS: bool = False  # Set to True to skip superuser creation
    FIRST_SUPERUSER_EMAIL: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "changethis"  # Max 72 bytes for bcrypt

    @field_validator("FIRST_SUPERUSER_PASSWORD", mode="after")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        """Validate password length for bcrypt (max 72 bytes)."""
        if v and len(v.encode('utf-8')) > 72:
            raise ValueError(
                f"FIRST_SUPERUSER_PASSWORD is too long ({len(v.encode('utf-8'))} bytes). "
                "Bcrypt has a maximum of 72 bytes. Please use a shorter password."
            )
        return v

    # File Storage
    FILE_STORAGE_PATH: str = "./data"  # Path for storing uploaded files and results


settings = Settings()  # type: ignore
