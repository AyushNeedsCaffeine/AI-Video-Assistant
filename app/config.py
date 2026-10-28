from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
VECTOR_DIR = BASE_DIR / "vector_db"
DOWNLOADS_DIR = BASE_DIR / "downloades"

STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"
ASSETS_DIR = BASE_DIR / "assets"

for directory in (DATA_DIR, UPLOAD_DIR, VECTOR_DIR, DOWNLOADS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
