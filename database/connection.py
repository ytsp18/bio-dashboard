"""Database connection management."""
import os
import time
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

# Track if migrations have been run this session
_migrations_done = False

# Simple logging with Thailand timezone (avoid circular import)
def _log(msg):
    from datetime import datetime, timezone, timedelta
    th_tz = timezone(timedelta(hours=7))
    th_time = datetime.now(th_tz).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{th_time}] [DB] {msg}")


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


@st.cache_resource
def warm_up_connection():
    """Warm up database connection pool (runs once per app session)."""
    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(__import__('sqlalchemy').text("SELECT 1"))
        duration = (time.perf_counter() - start) * 1000
        _log(f"Connection warm-up: {duration:.0f}ms")
        return True
    except Exception as e:
        _log(f"Connection warm-up failed: {e}")
        return False


# Warm up connection on module load
warm_up_connection()


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
    """Initialize database tables and run migrations (runs only once per app session)."""
    global _migrations_done

    # Skip if already done
    if _migrations_done:
        return

    start = time.perf_counter()
    from .models import Base

    Base.metadata.create_all(bind=engine)

    # Run migrations for existing tables (indexes won't be created by create_all)
    _run_migrations()

    _migrations_done = True
    duration = (time.perf_counter() - start) * 1000
    _log(f"Database initialized in {duration:.0f}ms (Using: {'SQLite' if is_sqlite else 'PostgreSQL'})")


def _run_migrations():
    """Run database migrations for existing tables."""
    from sqlalchemy import text, inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    migrations = []

    # ========== Users table indexes ==========
    if 'users' in tables:
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('users')}

        if 'ix_users_username' not in existing_indexes:
            migrations.append("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)")

        if 'ix_users_email' not in existing_indexes:
            migrations.append("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")

    # ========== Cards table indexes (for Overview page performance) ==========
    if 'cards' in tables:
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('cards')}

        # Composite index for date range + status queries
        if 'ix_cards_date_status' not in existing_indexes:
            migrations.append("CREATE INDEX IF NOT EXISTS ix_cards_date_status ON cards (print_date, print_status)")

        # Composite index for status + serial (unique serial count)
        if 'ix_cards_status_serial' not in existing_indexes:
            migrations.append("CREATE INDEX IF NOT EXISTS ix_cards_status_serial ON cards (print_status, serial_number)")

    # ========== Fix operator column size (VARCHAR(20) -> VARCHAR(50)) ==========
    # This fixes StringDataRightTruncation error when operator username > 20 chars
    if 'complete_diffs' in tables and not is_sqlite:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'complete_diffs' AND column_name = 'operator'
            """))
            row = result.fetchone()
            if row and row[0] and row[0] < 50:
                migrations.append("ALTER TABLE complete_diffs ALTER COLUMN operator TYPE VARCHAR(50)")

    # Execute migrations
    if migrations:
        with engine.connect() as conn:
            for sql in migrations:
                conn.execute(text(sql))
            conn.commit()
        _log(f"Migrations applied: {len(migrations)} index(es) created")
