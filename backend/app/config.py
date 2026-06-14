from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    gemini_api_key: str = ""
    llm_model: str = ""  # blank = provider default (gpt-4o-mini / gemini-2.0-flash)
    google_client_id: str = ""

    database_url: str = "postgresql+psycopg://career:career@localhost:5432/career"
    redis_url: str = "redis://localhost:6379/0"

    # AWS S3 Cloud Storage Configurations
    s3_bucket_name: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    tracking_poll_seconds: int = 300

    greenhouse_boards: str = ""
    lever_companies: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    scrape_interval_seconds: int = 3600
    daily_application_cap: int = 25

    greenhouse_job_board_api_key: str = ""
    lever_postings_api_key: str = ""
    webform_dry_run: bool = True

    @property
    def greenhouse_board_list(self) -> list[str]:
        return [b.strip() for b in self.greenhouse_boards.split(",") if b.strip()]

    @property
    def lever_company_list(self) -> list[str]:
        return [c.strip() for c in self.lever_companies.split(",") if c.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
