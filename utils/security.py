"""Security utilities for Bio Dashboard.

Provides:
- Login attempt limiting (brute force protection)
- Audit logging for important actions
"""
from datetime import datetime, timedelta
from typing import Optional
import json

import streamlit as st

from database.connection import get_session
from database.models import AuditLog, LoginAttempt, TH_TIMEZONE


# Configuration
MAX_LOGIN_ATTEMPTS = 5  # Max failed attempts before lockout
LOCKOUT_MINUTES = 15    # Lockout duration in minutes


def now_th():
    """Get current datetime in Thailand timezone."""
    return datetime.now(TH_TIMEZONE)


def get_client_ip() -> str:
    """Get client IP address (best effort in Streamlit)."""
    # Streamlit doesn't expose client IP directly
    # This is a placeholder - in production, use proxy headers
    return "unknown"


# ============== Login Attempt Limiting ==============

def check_login_allowed(username: str) -> tuple[bool, Optional[str]]:
    """
    Check if login is allowed for this username.
    Returns (allowed, message).
    """
    session = get_session()
    try:
        cutoff_time = now_th() - timedelta(minutes=LOCKOUT_MINUTES)

        # Count recent failed attempts
        failed_count = session.query(LoginAttempt).filter(
            LoginAttempt.username == username.lower(),
            LoginAttempt.timestamp > cutoff_time,
            LoginAttempt.success == False
        ).count()

        if failed_count >= MAX_LOGIN_ATTEMPTS:
            return False, f"บัญชีถูกล็อคชั่วคราว กรุณารอ {LOCKOUT_MINUTES} นาที"

        remaining = MAX_LOGIN_ATTEMPTS - failed_count
        if failed_count > 0:
            return True, f"เหลือโอกาสลองอีก {remaining} ครั้ง"

        return True, None
    finally:
        session.close()


def record_login_attempt(username: str, success: bool):
    """Record a login attempt."""
    session = get_session()
    try:
        attempt = LoginAttempt(
            username=username.lower(),
            ip_address=get_client_ip(),
            timestamp=now_th(),
            success=success
        )
        session.add(attempt)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def clear_login_attempts(username: str):
    """Clear failed login attempts after successful login."""
    session = get_session()
    try:
        cutoff_time = now_th() - timedelta(minutes=LOCKOUT_MINUTES)
        session.query(LoginAttempt).filter(
            LoginAttempt.username == username.lower(),
            LoginAttempt.timestamp > cutoff_time
        ).delete()
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


# ============== Audit Logging ==============

def log_audit(action: str, username: str = None, details: dict = None, success: bool = True):
    """
    Log an audit event.

    Actions:
        - login: User logged in
        - logout: User logged out
        - login_failed: Failed login attempt
        - upload: File uploaded
        - delete: Data deleted
        - user_created: New user created
        - user_deleted: User deleted
        - user_updated: User info updated
        - password_changed: Password changed
        - registration_approved: Registration approved
        - registration_rejected: Registration rejected
    """
    session = get_session()
    try:
        # Get username from session if not provided
        if username is None:
            username = st.session_state.get('username', 'anonymous')

        # Convert details to JSON string
        details_str = json.dumps(details, ensure_ascii=False) if details else None

        log_entry = AuditLog(
            timestamp=now_th(),
            username=username,
            action=action,
            details=details_str,
            ip_address=get_client_ip(),
            success=success
        )
        session.add(log_entry)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def get_recent_audit_logs(limit: int = 100, username: str = None, action: str = None):
    """Get recent audit logs with optional filters."""
    session = get_session()
    try:
        query = session.query(AuditLog).order_by(AuditLog.timestamp.desc())

        if username:
            query = query.filter(AuditLog.username == username)

        if action:
            query = query.filter(AuditLog.action == action)

        logs = query.limit(limit).all()

        return [
            {
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '',
                'username': log.username,
                'action': log.action,
                'details': json.loads(log.details) if log.details else None,
                'ip_address': log.ip_address,
                'success': log.success,
            }
            for log in logs
        ]
    finally:
        session.close()


def get_login_history(username: str = None, limit: int = 50):
    """Get login history."""
    return get_recent_audit_logs(
        limit=limit,
        username=username,
        action='login'
    )


# ============== Convenience Functions ==============

def audit_login(username: str, success: bool = True):
    """Log a login event."""
    if success:
        log_audit('login', username=username, success=True)
        clear_login_attempts(username)
    else:
        log_audit('login_failed', username=username, success=False)
        record_login_attempt(username, success=False)


def audit_logout(username: str = None):
    """Log a logout event."""
    log_audit('logout', username=username)


def audit_upload(filename: str, report_date: str = None):
    """Log a file upload event."""
    log_audit('upload', details={
        'filename': filename,
        'report_date': report_date
    })


def audit_delete(item_type: str, item_id: str = None, item_name: str = None):
    """Log a delete event."""
    log_audit('delete', details={
        'type': item_type,
        'id': item_id,
        'name': item_name
    })


def audit_user_action(action: str, target_username: str, details: dict = None):
    """Log a user management action."""
    log_audit(action, details={
        'target_user': target_username,
        **(details or {})
    })
