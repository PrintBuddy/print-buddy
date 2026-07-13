from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_core import MultiHostUrl


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="./.env",
        extra="ignore"
    )

    PROJECT_NAME: str
    VERSION: str
    ENVIRONMENT: str
    URL: str

    # Comma-separated list of allowed frontend origins for CORS, e.g.
    # "https://printbuddy.example.com,https://admin.printbuddy.example.com".
    # Defaults to Vite's local dev server so local development keeps working
    # without an explicit .env entry.
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXP_MIN: int
    PWD_RESET_SALT: str
    PWD_RESET_URL: str
    PWD_RESET_TIME_MIN: int

    DB_SCHEME: str
    DB_HOSTNAME: str
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    MAX_FILE_SIZE_MB: int
    UPLOAD_PATH: str

    PRINTER_MARKERS_DB: str

    TELEGRAM_SECRET: str

    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str
    
    @computed_field()
    @property
    def DB_PATH(self) -> str:
        sub = "dev" if self.ENVIRONMENT == "development" else "prod"
        return f"{self.DB_NAME}-{sub}"

    @computed_field()
    @property
    def DB_URL(self) -> str:
        url =  MultiHostUrl.build(
            scheme=self.DB_SCHEME,
            host=self.DB_HOSTNAME,
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            path=self.DB_PATH
        )

        return str(url)


settings = Settings() # type: ignore
