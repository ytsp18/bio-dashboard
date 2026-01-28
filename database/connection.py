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
    # PostgreSQL settings optimized for Streamlit Cloud
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # Check connection health
        pool_size=3,  # Smaller pool for serverless
        max_overflow=5,
        pool_recycle=300,  # Recycle connections every 5 minutes
        pool_timeout=30,  # Wait up to 30s for connection
        connect_args={
            "connect_timeout": 10,  # Connection timeout
            "options": "-c statement_timeout=30000"  # 30s query timeout
        }
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
    """Initialize database tables and run migrations."""
    from .models import Base
    from sqlalchemy import text, inspect

    Base.metadata.create_all(bind=engine)

    # Run migrations for existing tables (indexes won't be created by create_all)
    _run_migrations()

    print(f"Database initialized successfully! (Using: {'SQLite' if is_sqlite else 'PostgreSQL'})")


def _run_migrations():
    """Run database migrations for existing tables."""
    from sqlalchemy import text, inspect

    inspector = inspect(engine)

    # Check if users table exists
    if 'users' not in inspector.get_table_names():
        return

    # Get existing indexes on users table
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('users')}

    migrations = []

    # Add missing indexes
    if 'ix_users_username' not in existing_indexes:
        if is_sqlite:
            migrations.append("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)")
        else:
            migrations.append("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)")

    if 'ix_users_email' not in existing_indexes:
        if is_sqlite:
            migrations.append("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")
        else:
            migrations.append("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")

    # Execute migrations
    if migrations:
        with engine.connect() as conn:
            for sql in migrations:
                conn.execute(text(sql))
            conn.commit()
        print(f"Migrations applied: {len(migrations)} index(es) created")
