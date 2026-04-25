from pathlib import Path
import os

# Environment-aware path configuration
BASE_DIR = Path(__file__).resolve().parents[3]

DATA_ROOT = Path(
    os.getenv("DATA_ROOT", BASE_DIR / "data")
)

DB_PATH = DATA_ROOT / "db" / "orders_tracking.db"

# SQLite database file with environment override support
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DB_PATH}"
)

print(f"""paths:
- BASE_DIR: {BASE_DIR}
- DATA_ROOT: {DATA_ROOT}
- DB_PATH: {DB_PATH}
- DATABASE_URL: {DATABASE_URL}
""")