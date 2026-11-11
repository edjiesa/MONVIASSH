import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    APP_NAME: str = "Linux SSH Server Monitor"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "3000"))
    DATA_DIR: Path = DATA_DIR
    DB_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'monitor.db'}")
    SECRET_KEY_FILE: Path = DATA_DIR / "secret.key"
    DEFAULT_POLL_INTERVAL: int = int(os.getenv("DEFAULT_POLL_INTERVAL", "15"))
    SSH_TIMEOUT: int = int(os.getenv("SSH_TIMEOUT", "10"))
    METRIC_HISTORY_LIMIT: int = int(os.getenv("METRIC_HISTORY_LIMIT", "60")) # Keep last 60 records per server in DB

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
