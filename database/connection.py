from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> dict:
    """Check that PostgreSQL is reachable with the configured credentials."""
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
    except Exception as exc:
        return {"database": "unreachable", "error": type(exc).__name__}
    return {"database": "up", "name": settings.db_name, "version": version}