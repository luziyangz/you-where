"""
初始化 MySQL 表结构脚本。
用法：
    cd backend
    set DB_BACKEND=mysql
    python scripts/init_mysql_schema.py
"""

from pathlib import Path
import sys

# 兼容从 backend/scripts 直接执行，确保可导入 backend/common。
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.db import engine
from common.models import Base


def main() -> None:
    # 统一使用 SQLAlchemy 元数据建表，避免多入口脚本结构不一致。
    Base.metadata.create_all(bind=engine)
    print("MySQL schema initialized.")


if __name__ == "__main__":
    main()
