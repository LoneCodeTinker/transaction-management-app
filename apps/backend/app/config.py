import os
from pathlib import Path

def find_project_root(start_path: Path, marker: str = "projectroot") -> Path:
    current_path = start_path
    while current_path != current_path.parent:
        if (current_path / marker).exists():
            return current_path
        current_path = current_path.parent
    raise FileNotFoundError(f"{marker} not found")

BASE_DIR = Path(__file__).resolve().parent

DATA_ROOT = Path(
    os.getenv("DATA_ROOT")
    or find_project_root(BASE_DIR) / "data"
)

DB_PATH = DATA_ROOT / "db" / "orders_tracking.db"
LOG_PATH = DATA_ROOT / "logs" / "app.log"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DB_PATH}"
)