from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")
if _is_sqlite:
    Path("./data").mkdir(exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # aktifkan foreign key & cascade di SQLite
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
