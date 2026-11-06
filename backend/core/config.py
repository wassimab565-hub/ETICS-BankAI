from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ETICS-BankAI"
    app_env: str = "development"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "etics_db"
    db_user: str = "postgres"
    db_password: str

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    data_dir: str = "data"
    max_upload_mb: int = 20

    @property
    def database_url(self) -> str:
        pwd = quote_plus(self.db_password)
        return (
            f"postgresql://{self.db_user}:{pwd}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()