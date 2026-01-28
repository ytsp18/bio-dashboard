"""SQLAlchemy models for Bio Unified Report."""
from datetime import datetime, date, timezone, timedelta
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime,
    ForeignKey, Text, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Thailand timezone (UTC+7) for default timestamps
TH_TIMEZONE = timezone(timedelta(hours=7))


def now_th():
    """Get current datetime in Thailand timezone."""
    return datetime.now(TH_TIMEZONE)


class Report(Base):
    """Metadata for each uploaded report file."""
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    report_date = Column(Date, nullable=False)
    upload_date = Column(DateTime, default=now_th)
    total_good = Column(Integer, default=0)
    total_bad = Column(Integer, default=0)
    total_records = Column(Integer, default=0)

    # Relationships
    cards = relationship("Card", back_populates="report", cascade="all, delete-orphan")
    bad_cards = relationship("BadCard", back_populates="report", cascade="all, delete-orphan")
    center_stats = relationship("CenterStat", back_populates="report", cascade="all, delete-orphan")
    anomaly_slas = relationship("AnomalySLA", back_populates="report", cascade="all, delete-orphan")
    wrong_centers = relationship("WrongCenter", back_populates="report", cascade="all, delete-orphan")
    complete_diffs = relationship("CompleteDiff", back_populates="report", cascade="all, delete-orphan")
    delivery_cards = relationship("DeliveryCard", back_populates="report", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_reports_date', 'report_date'),
    )


class Card(Base):
    """All card records (from Sheet 13.ข้อมูลทั้งหมด)."""
    __tablename__ = 'cards'

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)

    # Core identifiers
    appointment_id = Column(String(50), index=True)
    form_id = Column(String(50))
    form_type = Column(String(20))
    branch_code = Column(String(20), index=True)
    branch_name = Column(String(255))
    card_id = Column(String(20), index=True)
    work_permit_no = Column(String(20))
    serial_number = Column(String(20), index=True)

    # Print info
    print_status = Column(String(10))  # G=Good, B=Bad
    reject_type = Column(String(255))
    operator = Column(String(50))
    print_date = Column(Date, index=True)

    # SLA info
    sla_start = Column(String(30))
    sla_stop = Column(String(30))
    sla_duration = Column(String(20))
    sla_minutes = Column(Float)
    sla_confirm_type = Column(String(20))

    # Queue info
    qlog_id = Column(String(50))
    qlog_branch = Column(String(20))
    qlog_date = Column(Date)
    qlog_queue_no = Column(Float)
    qlog_type = Column(String(10))
    qlog_time_in = Column(String(20))
    qlog_time_call = Column(String(20))
    wait_time_minutes = Column(Float)
    wait_time_hms = Column(String(20))
    qlog_sla_status = Column(String(10))

    # Appointment info
    appt_date = Column(Date)
    appt_branch = Column(String(20))
    appt_status = Column(String(20))

    # Flags
    wrong_date = Column(Boolean, default=False)
    wrong_branch = Column(Boolean, default=False)
    is_mobile_unit = Column(Boolean, default=False)
    is_ob_center = Column(Boolean, default=False)
    old_appointment = Column(Boolean, default=False)
    sla_over_12min = Column(Boolean, default=False)
    is_valid_sla_status = Column(Boolean, default=True)
    wait_over_1hour = Column(Boolean, default=False)
    emergency = Column(Boolean, default=False)

    # Region
    region = Column(String(50))

    # Relationship
    report = relationship("Report", back_populates="cards")

    __table_args__ = (
        Index('ix_cards_appointment', 'appointment_id'),
        Index('ix_cards_serial', 'serial_number'),
        Index('ix_cards_branch_date', 'branch_code', 'print_date'),
        # Composite index for Overview page queries (print_date + print_status)
        Index('ix_cards_date_status', 'print_date', 'print_status'),
        # Composite index for serial unique count with status
        Index('ix_cards_status_serial', 'print_status', 'serial_number'),
    )


class BadCard(Base):
    """Bad card records (from Sheet 3.รายการบัตรเสีย)."""
    __tablename__ = 'bad_cards'

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)

    appointment_id = Column(String(50), index=True)
    branch_code = Column(String(20))
    branch_name = Column(String(255))
    region = Column(String(50))
    card_id = Column(String(20))
    serial_number = Column(String(20))
    reject_reason = Column(Text)
    operator = Column(String(50))
    print_date = Column(Date)

    report = relationship("Report", back_populates="bad_cards")


class CenterStat(Base):
    """Center statistics (from Sheet 4.สรุปตามศูนย์)."""
    __tablename__ = 'center_stats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)

    branch_code = Column(String(20), index=True)
    branch_name = Column(String(255))
    good_count = Column(Integer, default=0)
    avg_sla = Column(Float)
    max_sla = Column(Float)

    report = relationship("Report", back_populates="center_stats")

    __table_args__ = (
        Index('ix_center_stats_branch', 'branch_code'),
    )


class AnomalySLA(Base):
    """SLA anomaly records (over 12 minutes)."""
    __tablename__ = 'anomaly_sla'

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)

    appointment_id = Column(String(50))
    branch_code = Column(String(20))
    branch_name = Column(String(255))
    serial_number = Column(String(20))
    sla_minutes = Column(Float)
    operator = Column(String(50))
    print_date = Column(Date)

    report = relationship("Report", back_populates="anomaly_slas")


class WrongCenter(Base):
    """Cards printed at wrong center."""
    __tablename__ = 'wrong_centers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)

    appointment_id = Column(String(50))
    expected_branch = Column(String(20))
    actual_branch = Column(String(20))
    serial_number = Column(String(20))
    status = Column(String(20))
    print_date = Column(Date)

    report = relationship("Report", back_populates="wrong_centers")


class CompleteDiff(Base):
    """Complete card differences - Appt ID with G > 1 (Sheet 22)."""
    __tablename__ = 'complete_diffs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)

    appointment_id = Column(String(50), index=True)
    g_count = Column(Integer)  # จำนวน G
    branch_code = Column(String(20))
    branch_name = Column(String(255))
    region = Column(String(50))
    card_id = Column(String(20))
    serial_number = Column(String(20), index=True)
    work_permit_no = Column(String(20))
    sla_minutes = Column(Float)
    operator = Column(String(50))
    print_date = Column(Date, index=True)

    report = relationship("Report", back_populates="complete_diffs")

    __table_args__ = (
        Index('ix_complete_diffs_appt', 'appointment_id'),
    )


class DeliveryCard(Base):
    """Delivery cards (from Sheet 7.บัตรจัดส่ง)."""
    __tablename__ = 'delivery_cards'

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)

    appointment_id = Column(String(50), index=True)
    serial_number = Column(String(20), index=True)
    print_status = Column(String(10))
    card_id = Column(String(20))
    work_permit_no = Column(String(20))

    report = relationship("Report", back_populates="delivery_cards")

    __table_args__ = (
        Index('ix_delivery_cards_serial', 'serial_number'),
    )


# ============== User Management Models ==============

class User(Base):
    """User accounts for authentication."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default='viewer')  # admin, user, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_th)
    updated_at = Column(DateTime, default=now_th, onupdate=now_th)

    __table_args__ = (
        Index('ix_users_username', 'username'),
        Index('ix_users_email', 'email'),
    )


class PendingRegistration(Base):
    """Pending user registrations awaiting approval."""
    __tablename__ = 'pending_registrations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    requested_at = Column(DateTime, default=now_th)


class SystemSetting(Base):
    """System settings stored in database."""
    __tablename__ = 'system_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(255))
    updated_at = Column(DateTime, default=now_th, onupdate=now_th)


class AuditLog(Base):
    """Audit log for tracking user actions."""
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=now_th, index=True)
    username = Column(String(50), index=True)
    action = Column(String(50), nullable=False)  # login, logout, upload, delete, etc.
    details = Column(Text)  # JSON or additional info
    ip_address = Column(String(50))
    success = Column(Boolean, default=True)

    __table_args__ = (
        Index('ix_audit_logs_user_time', 'username', 'timestamp'),
    )


class LoginAttempt(Base):
    """Track failed login attempts for brute force protection."""
    __tablename__ = 'login_attempts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), index=True)
    ip_address = Column(String(50), index=True)
    timestamp = Column(DateTime, default=now_th)
    success = Column(Boolean, default=False)

    __table_args__ = (
        Index('ix_login_attempts_ip_time', 'ip_address', 'timestamp'),
    )
