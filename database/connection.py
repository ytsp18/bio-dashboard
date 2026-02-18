"""Database connection management."""
import os
import re
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

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        if "already exists" in str(e):
            _log(f"Skipping existing objects during init: {e}")
        else:
            raise

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

    # ========== Cards table - partial index for slot cut query ==========
    if 'cards' in tables and not is_sqlite:
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('cards')}
        if 'ix_cards_wrong_appt' not in existing_indexes:
            migrations.append(
                "CREATE INDEX IF NOT EXISTS ix_cards_wrong_appt "
                "ON cards (appt_branch, appt_date) "
                "WHERE (wrong_date = true OR wrong_branch = true) AND print_status = 'G'"
            )
            _log("Queued index: ix_cards_wrong_appt (partial)")

    # ========== QLog table - add missing columns ==========
    if 'qlogs' in tables and not is_sqlite:
        existing_columns = {col['name'] for col in inspector.get_columns('qlogs')}
        qlog_new_columns = {
            'qlog_train_time': 'VARCHAR(20)',
            'qlog_typename': 'VARCHAR(50)',
            'qlog_counter': 'INTEGER',
        }
        for col_name, col_type in qlog_new_columns.items():
            if col_name not in existing_columns:
                migrations.append(f"ALTER TABLE qlogs ADD COLUMN {col_name} {col_type}")
                _log(f"Queued column add: qlogs.{col_name}")

    # ========== Fix VARCHAR column sizes for appointments ==========
    # This fixes StringDataRightTruncation errors for Thai text fields
    if 'appointments' in tables and not is_sqlite:
        # Define target sizes for each column (whitelist for security)
        appt_target_sizes = {
            'form_type': 255,      # Thai form type descriptions are long
            'card_id': 30,         # Card ID
            'work_permit_no': 30   # Work permit number
        }
        # Only allow columns in whitelist
        allowed_columns = set(appt_target_sizes.keys())

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'appointments'
                AND column_name IN ('form_type', 'card_id', 'work_permit_no')
            """))

            for row in result:
                col_name, current_size = row[0], row[1]
                # Security: Only process whitelisted column names
                if col_name not in allowed_columns:
                    continue
                target_size = appt_target_sizes.get(col_name, 50)
                if current_size and current_size < target_size:
                    # Safe: col_name is validated against whitelist
                    migrations.append(f"ALTER TABLE appointments ALTER COLUMN {col_name} TYPE VARCHAR({target_size})")
                    _log(f"Queued column resize: appointments.{col_name} to VARCHAR({target_size})")

    # ========== Fix VARCHAR column sizes for complete_diffs ==========
    # This fixes StringDataRightTruncation errors
    if 'complete_diffs' in tables and not is_sqlite:
        # Define target sizes for each column (whitelist for security)
        diff_target_sizes = {
            'operator': 100,      # For usernames or datetime strings
            'branch_code': 255,   # May contain branch_name due to Excel parsing
            'card_id': 50,        # May have longer IDs
            'serial_number': 50,  # May have longer serials
            'work_permit_no': 50  # May have longer permit numbers
        }
        # Only allow columns in whitelist
        allowed_diff_columns = set(diff_target_sizes.keys())

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'complete_diffs'
                AND column_name IN ('operator', 'branch_code', 'card_id', 'serial_number', 'work_permit_no')
            """))

            for row in result:
                col_name, current_size = row[0], row[1]
                # Security: Only process whitelisted column names
                if col_name not in allowed_diff_columns:
                    continue
                target_size = diff_target_sizes.get(col_name, 50)
                if current_size and current_size < target_size:
                    # Safe: col_name is validated against whitelist
                    migrations.append(f"ALTER TABLE complete_diffs ALTER COLUMN {col_name} TYPE VARCHAR({target_size})")

    # ========== Fix CASCADE DELETE for Foreign Keys ==========
    # This fixes the issue where deleting a report doesn't delete related records
    if not is_sqlite:
        # Tables that need CASCADE DELETE on report_id FK (whitelist for security)
        allowed_tables_with_fk = {
            'cards', 'bad_cards', 'center_stats', 'anomaly_sla',
            'wrong_centers', 'complete_diffs', 'delivery_cards'
        }

        with engine.connect() as conn:
            for table_name in allowed_tables_with_fk:
                if table_name not in tables:
                    continue

                # Security: table_name is from whitelist, safe to use
                # Use parameterized query for SELECT
                result = conn.execute(
                    text("""
                        SELECT tc.constraint_name, rc.delete_rule
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.referential_constraints rc
                            ON tc.constraint_name = rc.constraint_name
                        WHERE tc.table_name = :tbl_name
                        AND tc.constraint_type = 'FOREIGN KEY'
                    """),
                    {"tbl_name": table_name}
                )

                for row in result:
                    constraint_name, delete_rule = row[0], row[1]
                    if delete_rule != 'CASCADE':
                        # Security: Validate constraint_name format (alphanumeric + underscore only)
                        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', constraint_name):
                            _log(f"Skipping invalid constraint name: {constraint_name}")
                            continue
                        # Safe: table_name from whitelist, constraint_name validated
                        migrations.append(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}")
                        migrations.append(f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE")
                        _log(f"Queued CASCADE fix for {table_name}.{constraint_name}")

    # Execute migrations
    if migrations:
        with engine.connect() as conn:
            for sql in migrations:
                conn.execute(text(sql))
            conn.commit()
        _log(f"Migrations applied: {len(migrations)} change(s)")

    # Load branch master data from Excel if table is empty
    _load_branch_master_if_needed()


def _load_branch_master_if_needed():
    """Load branch master data from Excel file if table is empty."""
    from .models import BranchMaster
    import pandas as pd

    session = get_session()
    try:
        # Check if branch_master table has data
        count = session.query(BranchMaster).count()
        if count > 0:
            return  # Already has data

        # Find the Excel file
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        excel_path = os.path.join(base_dir, 'Data Master Branch.xlsx')

        if not os.path.exists(excel_path):
            _log(f"Branch master file not found: {excel_path}")
            return

        # Read Excel file
        df = pd.read_excel(excel_path, sheet_name=0)

        # Map columns
        records = []
        for _, row in df.iterrows():
            branch_code = str(row.get('branch_code', '')).strip()
            if not branch_code:
                continue

            max_cap = row.get('จำนวน max ที่จองได้ (คน)')
            if pd.notna(max_cap):
                max_cap = int(max_cap)
            else:
                max_cap = None

            records.append(BranchMaster(
                province_code=str(row.get('province_code', '')).strip() or None,
                branch_code=branch_code,
                branch_name=str(row.get('branch_name', '')).strip() or None,
                branch_name_en=str(row.get('branch_name_en', '')).strip() or None,
                branch_address=str(row.get('branch_address', '')).strip() or None,
                branch_address_en=str(row.get('branch_address_en', '')).strip() or None,
                max_capacity=max_cap,
            ))

        if records:
            session.add_all(records)
            session.commit()
            _log(f"Loaded {len(records)} branch master records from Excel")
    except Exception as e:
        session.rollback()
        _log(f"Error loading branch master: {e}")
    finally:
        session.close()


def get_branch_name_map():
    """Get cached branch_code -> branch_name mapping from BranchMaster."""
    from .models import BranchMaster

    session = get_session()
    try:
        branches = session.query(
            BranchMaster.branch_code,
            BranchMaster.branch_name
        ).all()
        return {b.branch_code: b.branch_name for b in branches if b.branch_code}
    finally:
        session.close()


@st.cache_data(ttl=3600)
def get_branch_name_map_cached():
    """Get cached branch_code -> branch_name mapping (cached for 1 hour)."""
    return get_branch_name_map()
