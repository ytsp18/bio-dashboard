"""Database-based user management for Bio Dashboard.

This module provides user management functions that store data in the database
instead of config.yaml, making user data persistent across deployments.
"""
from typing import Optional, List, Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from streamlit_authenticator.utilities import Hasher
except ImportError:
    from streamlit_authenticator import Hasher

from database.connection import get_session
from database.models import User, PendingRegistration, SystemSetting
from utils.timezone import now_th


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return Hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return Hasher.check(password, password_hash)


# ============== User Functions ==============

def get_all_users() -> List[Dict[str, Any]]:
    """Get all active users from database."""
    session = get_session()
    try:
        users = session.query(User).filter(User.is_active == True).all()
        return [
            {
                'username': u.username,
                'name': u.name,
                'email': u.email,
                'role': u.role,
            }
            for u in users
        ]
    finally:
        session.close()


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Get a specific user by username."""
    session = get_session()
    try:
        user = session.query(User).filter(
            User.username == username,
            User.is_active == True
        ).first()

        if user:
            return {
                'username': user.username,
                'name': user.name,
                'email': user.email,
                'role': user.role,
            }
        return None
    finally:
        session.close()


def get_user_for_auth(username: str) -> Optional[Dict[str, Any]]:
    """Get user with password hash for authentication."""
    session = get_session()
    try:
        user = session.query(User).filter(
            User.username == username,
            User.is_active == True
        ).first()

        if user:
            return {
                'username': user.username,
                'name': user.name,
                'email': user.email,
                'password': user.password_hash,
                'role': user.role,
            }
        return None
    finally:
        session.close()


def get_all_users_for_auth() -> Dict[str, Dict[str, Any]]:
    """Get all users in format suitable for streamlit_authenticator.

    Returns dict keyed by username AND email (as alias) so users can
    log in with either their username or email address.
    Each entry is a separate dict copy to avoid shared-reference issues.
    """
    session = get_session()
    try:
        users = session.query(User).filter(User.is_active == True).all()
        result = {}
        for u in users:
            user_data = {
                'name': u.name,
                'email': u.email,
                'password': u.password_hash,
                'role': u.role,
            }
            result[u.username] = user_data
            # Add email as alias key (separate copy)
            if u.email and u.email.lower() != u.username.lower():
                result[u.email.lower()] = {
                    'name': u.name,
                    'email': u.email,
                    'password': u.password_hash,
                    'role': u.role,
                }
        return result
    finally:
        session.close()


def lookup_username_by_email(email: str) -> Optional[str]:
    """Lookup username by email address. Returns username or None."""
    session = get_session()
    try:
        user = session.query(User.username).filter(
            User.email == email.lower(),
            User.is_active == True
        ).first()
        return user.username if user else None
    finally:
        session.close()


def create_user(username: str, name: str, email: str, password: str, role: str = 'viewer') -> Dict[str, Any]:
    """Create a new user."""
    session = get_session()
    try:
        # Check if username exists
        existing = session.query(User).filter(User.username == username).first()
        if existing:
            return {'success': False, 'error': 'Username already exists'}

        # Check if email exists
        existing_email = session.query(User).filter(User.email == email.lower()).first()
        if existing_email:
            return {'success': False, 'error': 'Email already exists'}

        # Hash password and create user
        hashed_password = hash_password(password)

        user = User(
            username=username.lower(),
            name=name,
            email=email.lower(),
            password_hash=hashed_password,
            role=role,
            is_active=True,
        )
        session.add(user)
        session.commit()

        return {'success': True}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def update_user(username: str, name: str = None, email: str = None, role: str = None) -> Dict[str, Any]:
    """Update user information (not password)."""
    session = get_session()
    try:
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return {'success': False, 'error': 'User not found'}

        if name:
            user.name = name

        if email:
            # Check if email is used by another user
            existing = session.query(User).filter(
                User.email == email.lower(),
                User.username != username
            ).first()
            if existing:
                return {'success': False, 'error': 'Email already used by another user'}
            user.email = email.lower()

        if role:
            user.role = role

        user.updated_at = now_th()
        session.commit()

        return {'success': True}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def change_password(username: str, new_password: str) -> Dict[str, Any]:
    """Change user password."""
    session = get_session()
    try:
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return {'success': False, 'error': 'User not found'}

        user.password_hash = hash_password(new_password)
        user.updated_at = now_th()
        session.commit()

        return {'success': True}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def delete_user(username: str) -> Dict[str, Any]:
    """Delete a user (soft delete by setting is_active=False)."""
    session = get_session()
    try:
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return {'success': False, 'error': 'User not found'}

        # Prevent deleting the last admin
        if user.role == 'admin':
            admin_count = session.query(User).filter(
                User.role == 'admin',
                User.is_active == True
            ).count()
            if admin_count <= 1:
                return {'success': False, 'error': 'Cannot delete the last admin user'}

        # Soft delete
        user.is_active = False
        user.updated_at = now_th()
        session.commit()

        return {'success': True}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def is_admin(username: str) -> bool:
    """Check if user is admin."""
    session = get_session()
    try:
        user = session.query(User).filter(
            User.username == username,
            User.is_active == True
        ).first()
        return user is not None and user.role == 'admin'
    finally:
        session.close()


# ============== Registration Functions ==============

def get_pending_registrations() -> List[Dict[str, Any]]:
    """Get all pending registrations."""
    session = get_session()
    try:
        pending = session.query(PendingRegistration).all()
        return [
            {
                'username': p.username,
                'name': p.name,
                'email': p.email,
                'requested_at': p.requested_at.strftime('%Y-%m-%d %H:%M:%S') if p.requested_at else '',
            }
            for p in pending
        ]
    finally:
        session.close()


def submit_registration(username: str, name: str, email: str, password: str) -> Dict[str, Any]:
    """Submit a new registration request."""
    session = get_session()
    try:
        # Check settings
        settings = get_settings()
        if not settings.get('allow_registration', True):
            return {'success': False, 'error': 'Registration is disabled'}

        username = username.lower()
        email = email.lower()

        # Check if username exists in users
        existing_user = session.query(User).filter(User.username == username).first()
        if existing_user:
            return {'success': False, 'error': 'Username already exists'}

        # Check if username exists in pending
        existing_pending = session.query(PendingRegistration).filter(
            PendingRegistration.username == username
        ).first()
        if existing_pending:
            return {'success': False, 'error': 'Registration already pending'}

        # Check if email exists in users
        existing_email = session.query(User).filter(User.email == email).first()
        if existing_email:
            return {'success': False, 'error': 'Email already registered'}

        # Check if email exists in pending
        existing_pending_email = session.query(PendingRegistration).filter(
            PendingRegistration.email == email
        ).first()
        if existing_pending_email:
            return {'success': False, 'error': 'Email already pending registration'}

        # Hash password
        hashed_password = hash_password(password)

        # Add to pending
        pending = PendingRegistration(
            username=username,
            name=name,
            email=email,
            password_hash=hashed_password,
            requested_at=now_th(),
        )
        session.add(pending)
        session.commit()

        # If no approval required, auto-approve
        if not settings.get('require_approval', True):
            session.close()
            return approve_registration(username)

        return {'success': True, 'message': 'Registration submitted. Please wait for admin approval.'}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def approve_registration(username: str) -> Dict[str, Any]:
    """Approve a pending registration."""
    session = get_session()
    try:
        pending = session.query(PendingRegistration).filter(
            PendingRegistration.username == username
        ).first()

        if not pending:
            return {'success': False, 'error': 'Registration not found'}

        # Get default role from settings
        settings = get_settings()
        default_role = settings.get('default_role', 'viewer')

        # Create user from pending
        user = User(
            username=pending.username,
            name=pending.name,
            email=pending.email,
            password_hash=pending.password_hash,
            role=default_role,
            is_active=True,
        )
        session.add(user)

        # Remove from pending
        session.delete(pending)
        session.commit()

        return {'success': True}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def reject_registration(username: str) -> Dict[str, Any]:
    """Reject a pending registration."""
    session = get_session()
    try:
        pending = session.query(PendingRegistration).filter(
            PendingRegistration.username == username
        ).first()

        if not pending:
            return {'success': False, 'error': 'Registration not found'}

        session.delete(pending)
        session.commit()

        return {'success': True}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


# ============== Settings Functions ==============

def get_settings() -> Dict[str, Any]:
    """Get system settings from database."""
    session = get_session()
    try:
        settings = {}

        # Default values
        defaults = {
            'allow_registration': 'true',
            'require_approval': 'true',
            'default_role': 'viewer',
        }

        for key, default_value in defaults.items():
            setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()
            if setting:
                # Convert string to appropriate type
                if setting.value in ('true', 'false'):
                    settings[key] = setting.value == 'true'
                else:
                    settings[key] = setting.value
            else:
                # Use default
                if default_value in ('true', 'false'):
                    settings[key] = default_value == 'true'
                else:
                    settings[key] = default_value

        return settings
    finally:
        session.close()


def update_settings(allow_registration: bool = None, require_approval: bool = None, default_role: str = None) -> Dict[str, Any]:
    """Update system settings."""
    session = get_session()
    try:
        if allow_registration is not None:
            _set_setting(session, 'allow_registration', 'true' if allow_registration else 'false')

        if require_approval is not None:
            _set_setting(session, 'require_approval', 'true' if require_approval else 'false')

        if default_role is not None:
            _set_setting(session, 'default_role', default_role)

        session.commit()
        return {'success': True}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def _set_setting(session, key: str, value: str):
    """Helper to set a setting value."""
    setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()
    if setting:
        setting.value = value
        setting.updated_at = now_th()
    else:
        setting = SystemSetting(key=key, value=value)
        session.add(setting)


# ============== Migration Function ==============

def migrate_users_from_config():
    """Migrate users from config.yaml to database (run once)."""
    import yaml
    from yaml.loader import SafeLoader

    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')

    if not os.path.exists(config_path):
        return {'success': False, 'error': 'Config file not found'}

    session = get_session()
    try:
        with open(config_path, encoding='utf-8') as file:
            config = yaml.load(file, Loader=SafeLoader)

        migrated = 0
        skipped = 0

        # Migrate users
        for username, data in config.get('credentials', {}).get('usernames', {}).items():
            existing = session.query(User).filter(User.username == username).first()
            if existing:
                skipped += 1
                continue

            user = User(
                username=username,
                name=data.get('name', username),
                email=data.get('email', f'{username}@local'),
                password_hash=data.get('password', ''),
                role=data.get('role', 'viewer'),
                is_active=True,
            )
            session.add(user)
            migrated += 1

        # Migrate pending registrations
        for username, data in config.get('pending_registrations', {}).items():
            existing = session.query(PendingRegistration).filter(
                PendingRegistration.username == username
            ).first()
            if existing:
                continue

            pending = PendingRegistration(
                username=username,
                name=data.get('name', username),
                email=data.get('email', f'{username}@local'),
                password_hash=data.get('password', ''),
            )
            session.add(pending)

        # Migrate settings
        settings = config.get('settings', {})
        if settings:
            for key, value in settings.items():
                if isinstance(value, bool):
                    value = 'true' if value else 'false'
                _set_setting(session, key, str(value))

        session.commit()

        return {'success': True, 'migrated': migrated, 'skipped': skipped}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()
