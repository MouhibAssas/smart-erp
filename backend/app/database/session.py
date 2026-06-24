from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.base import Base
from app.config import settings


engine = create_engine(
    
    settings.DATABASE_URL,
    connect_args={},
    pool_pre_ping=True,      # checks connection health before using it
    pool_size=5,             # max 5 persistent connections
    max_overflow=10          # up to 10 extra connections under load
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,        # you control when to commit
    autoflush=False          # don't auto-sync before every query
)

def get_db():
    """FastAPI dependency — gives a DB session per request, closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()