from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DB_PATH = Path("/app/data/netwatch.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def init_db():
    from app.models import Device, Event  # noqa: F401 — registers models
    Base.metadata.create_all(bind=engine)
    # Lightweight migrations for columns added after initial release
    with engine.connect() as conn:
        existing = [row[1] for row in conn.execute(
            __import__('sqlalchemy').text("PRAGMA table_info(devices)")
        )]
        if "known_ips" not in existing:
            conn.execute(__import__('sqlalchemy').text(
                "ALTER TABLE devices ADD COLUMN known_ips TEXT DEFAULT '[]'"
            ))
            conn.commit()
        if "note" not in existing:
            conn.execute(__import__('sqlalchemy').text(
                "ALTER TABLE devices ADD COLUMN note TEXT DEFAULT ''"
            ))
            conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
