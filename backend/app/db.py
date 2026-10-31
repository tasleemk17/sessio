from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL


def normalize_url(url: str) -> str:
    """Hosts hand out URLs that start with postgres:// or postgresql://, which SQLAlchemy reads as the old
    psycopg2 driver. This project ships psycopg 3, so the scheme is rewritten and the URL can be pasted as is."""
    for plain in ("postgres://", "postgresql://"):
        if url.startswith(plain):
            return "postgresql+psycopg://" + url[len(plain):]
    return url


_url = normalize_url(DATABASE_URL)
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}
engine = create_engine(_url, connect_args=_connect_args, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
