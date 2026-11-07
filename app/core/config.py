from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, computed_field
from typing import Optional

class Settings(BaseSettings):
    """
    Application Configuration using Pydantic Settings.
    
    This class automatically loads environment variables.
    For example, a variable named 'PROJECT_NAME' in .env will populate the PROJECT_NAME field.
    This provides type safety and validation for configuration.
    """
    PROJECT_NAME: str = "Prime Auth"
    API_V1_STR: str = "/api/v1"
    
    # Security Configuration
    # WARNING: defaults are for development only. In production, these MUST be set via env vars.
    SECRET_KEY: str = "CHANGE_THIS_TO_A_SECURE_SECRET_KEY" 
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database Configuration
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "prime_auth"
    POSTGRES_PORT: int = 5432

    # Computed Field: dynamically constructs the Database URL from components
    # This allows us to construct complex connection strings from simple env vars.
    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg", # Using asyncpg driver for AsyncIO support
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
