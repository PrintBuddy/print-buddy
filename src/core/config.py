from pydantic import computed_field
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
    # Kept as a plain str (not list[str]): pydantic-settings tries to
    # JSON-decode any list-typed env var before field validators ever run,
    # which would reject a plain comma-separated string outright. Split via
    # CORS_ORIGINS_LIST below instead.
    CORS_ORIGINS: str = "http://localhost:5173"

    @computed_field()
    @property
    def CORS_ORIGINS_LIST(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

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

    # Lets the backend push Telegram messages directly (recharge-request
    # notifications created from the web app, where no bot conversation is
    # driving the send) using the same bot account the bot itself polls
    # with — Telegram routes the resulting button press to the bot
    # regardless of which process sent the original message. Optional: web-
    # originated recharge requests degrade to "no Telegram ping, web queue
    # only" if unset, rather than failing outright.
    TELEGRAM_BOT_TOKEN: str | None = None

    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str

    # Optional: error tracking. Left unset in dev/CI/test, where Sentry stays inactive.
    SENTRY_DSN: str | None = None

    # slowapi's rate-limit string for POST /auth/login (e.g. "5/minute").
    # Keyed by remote address (core/limiter.py) — every request in a
    # Docker-networked E2E run (Playwright's browser -> published port)
    # shares the same source address, so several specs logging in back to
    # back can trip the production limit within seconds. Overridable so
    # CI/E2E can raise it without weakening the real default.
    LOGIN_RATE_LIMIT: str = "5/minute"

    @computed_field()
    @property
    def DB_PATH(self) -> str:
        sub = "dev" if self.ENVIRONMENT == "development" else "prod"
        return f"{self.DB_NAME}-{sub}"

    @computed_field()
    @property
    def DB_URL(self) -> str:
        url = MultiHostUrl.build(
            scheme=self.DB_SCHEME,
            host=self.DB_HOSTNAME,
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            path=self.DB_PATH
        )

        return str(url)


settings = Settings()  # type: ignore
