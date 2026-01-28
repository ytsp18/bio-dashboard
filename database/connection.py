"""Database connection management."""
import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

def get_database_url():
    """Get database URL from Streamlit secrets or environment variable."""
    # Try Streamlit secrets first (for Streamlit Cloud)
    try:
        if hasattr(st, 'secrets') and 'database' in st.secrets:
            return st.secrets['database']['url']
    except Exception:
        pass

    # Try environment variable
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url

    # Fallback to SQLite for local development
    DB_DIR = os.path.dirname(os.path.abspath(__file__))
    return f"sqlite:///{os.path.join(DB_DIR, 'bio_data.db')}"

# Get database URL
DATABASE_URL = get_database_url()

# Determine if using SQLite
is_sqlite = "sqlite" in DATABASE_URL

# Create engine with appropriate settings
if is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL settings
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # Check connection health
        pool_size=5,
        max_overflow=10
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_engine():
    """Get the database engine."""
    return engine


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Initialize database tables."""
    from .models import Base
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized successfully! (Using: {'SQLite' if is_sqlite else 'PostgreSQL'})")
