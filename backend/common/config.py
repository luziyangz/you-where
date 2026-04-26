import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


class Settings:
    """应用配置集合。"""

    # 数据库后端开关：统一改造后默认使用 mysql。
    DB_BACKEND: str = os.getenv("DB_BACKEND", "mysql").strip().lower()

    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "youzainaye")
    MYSQL_POOL_SIZE: int = int(os.getenv("MYSQL_POOL_SIZE", "10"))
    MYSQL_MAX_OVERFLOW: int = int(os.getenv("MYSQL_MAX_OVERFLOW", "20"))

    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "data/app.db")

    WECHAT_APP_ID: str = os.getenv("WECHAT_APP_ID", "")
    WECHAT_APP_SECRET: str = os.getenv("WECHAT_APP_SECRET", "")
    WECHAT_REMINDER_TEMPLATE_ID: str = os.getenv("WECHAT_REMINDER_TEMPLATE_ID", "")
    ENABLE_TEST_USERS: bool = os.getenv(
        "ENABLE_TEST_USERS",
        "1" if os.getenv("DB_BACKEND", "mysql").strip().lower() == "sqlite" else "0",
    ).strip().lower() in {"1", "true", "yes", "on"}

    @property
    def mysql_url(self) -> str:
        # 使用 PyMySQL 驱动连接 MySQL。
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.SQLITE_DB_PATH}"

    @property
    def database_url(self) -> str:
        if self.DB_BACKEND == "mysql":
            return self.mysql_url
        return self.sqlite_url


settings = Settings()

