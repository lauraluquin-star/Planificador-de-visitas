from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'app.db'}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
