from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

engine = create_engine(
    settings.DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DB_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from sqlalchemy import text

def init_db():
    from app import models
    Base.metadata.create_all(bind=engine)

    # Auto-migration for SQLite database
    with engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(servers);")).fetchall()
            existing_cols = [row[1] for row in result]
            if "sudo_password_encrypted" not in existing_cols:
                conn.execute(text("ALTER TABLE servers ADD COLUMN sudo_password_encrypted TEXT;"))
                conn.commit()
        except Exception:
            pass
