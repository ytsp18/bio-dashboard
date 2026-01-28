"""Authentication utilities for Bio Dashboard.

Uses database for user credentials instead of config.yaml to persist
user data across Streamlit Cloud deployments.

SECURITY: Cookie key is loaded from Streamlit secrets, not from config.yaml.
"""
import streamlit as st
import streamlit_authenticator as stauth
import secrets as py_secrets
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db
from .db_user_manager import get_all_users_for_auth


def get_cookie_config():
    """Get cookie configuration from Streamlit secrets (secure) or generate random key."""
    # Default values
    cookie_name = 'bio_dashboard_auth'
    expiry_days = 30

    # Try to get cookie_key from Streamlit secrets (SECURE)
    try:
        if hasattr(st, 'secrets') and 'cookie' in st.secrets:
            cookie_key = st.secrets['cookie'].get('key', None)
            cookie_name = st.secrets['cookie'].get('name', cookie_name)
            expiry_days = st.secrets['cookie'].get('expiry_days', expiry_days)
            if cookie_key:
                return {
                    'name': cookie_name,
                    'key': cookie_key,
                    'expiry_days': expiry_days
                }
    except Exception:
        pass

    # Fallback: Generate a random key per session (less ideal but secure)
    # This means users will need to re-login after app restarts
    if 'cookie_key' not in st.session_state:
        st.session_state['cookie_key'] = py_secrets.token_hex(32)

    return {
        'name': cookie_name,
        'key': st.session_state['cookie_key'],
        'expiry_days': expiry_days
    }


def get_authenticator():
    """Create and return authenticator instance using database credentials."""
    # Initialize database
    init_db()

    # Get users from database
    users = get_all_users_for_auth()

    # Build credentials structure for streamlit_authenticator
    credentials = {
        'usernames': users
    }

    # Load cookie settings from secrets (secure)
    cookie_config = get_cookie_config()

    # streamlit-authenticator v0.4.x API
    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name=cookie_config.get('name', 'bio_dashboard_auth'),
        cookie_key=cookie_config.get('key'),
        cookie_expiry_days=cookie_config.get('expiry_days', 30),
    )

    # Return authenticator and credentials (for compatibility)
    config = {
        'credentials': credentials,
        'cookie': cookie_config
    }

    return authenticator, config


def check_authentication():
    """
    Check if user is authenticated.
    Returns True if authenticated, False otherwise.
    Shows login form if not authenticated.
    """
    authenticator, config = get_authenticator()

    # Render login widget (v0.4.x API)
    try:
        # Try new API first (v0.4.x)
        authenticator.login()
    except TypeError:
        # Fallback to old API (v0.3.x)
        authenticator.login('main')

    # Check authentication status from session state
    if st.session_state.get('authentication_status'):
        # Store authenticator in session state
        st.session_state['authenticator'] = authenticator
        return True

    elif st.session_state.get('authentication_status') is False:
        st.error('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
        return False

    elif st.session_state.get('authentication_status') is None:
        st.warning('กรุณาใส่ชื่อผู้ใช้และรหัสผ่าน')
        return False


def logout_button():
    """Render logout button in sidebar."""
    if 'authenticator' in st.session_state:
        authenticator = st.session_state['authenticator']

        # Show current user
        if st.session_state.get('name'):
            st.sidebar.write(f"👤 {st.session_state['name']}")

        # Logout button (v0.4.x API)
        try:
            authenticator.logout(location='sidebar')
        except TypeError:
            # Fallback to old API
            authenticator.logout('Logout', 'sidebar')


def require_auth(func):
    """
    Decorator to require authentication for a function.
    Usage:
        @require_auth
        def main():
            # Your page code here
    """
    def wrapper(*args, **kwargs):
        if check_authentication():
            return func(*args, **kwargs)
    return wrapper
