from functools import cached_property

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "CHANGE_THIS_TO_A_SECURE_SECRET_KEY"


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables (and `.env`).

    DATABASE_URL takes precedence. When it is not set, the URL is built
    from the individual POSTGRES_* variables.
    """

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "Prime Auth"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | test | production

    # Security
    SECRET_KEY: str = INSECURE_DEFAULT_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12

    # Rate limiting (slowapi syntax, e.g. "5/minute")
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT: str = "5/minute"
    REGISTER_RATE_LIMIT: str = "10/hour"

    # Database
    DATABASE_URL: str | None = None
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "prime_auth"
    POSTGRES_PORT: int = 5432
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    SQL_ECHO: bool = False

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.ENVIRONMENT == "production" and (
            self.SECRET_KEY == INSECURE_DEFAULT_SECRET or len(self.SECRET_KEY) < 32
        ):
            raise ValueError("SECRET_KEY must be set to a random value of at least 32 characters in production")
        return self

    @cached_property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
