"""Authentication utilities for Bio Dashboard."""
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os

# Path to config file
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')


def load_config():
    """Load authentication config from YAML file."""
    with open(CONFIG_PATH) as file:
        config = yaml.load(file, Loader=SafeLoader)
    return config


def save_config(config):
    """Save authentication config to YAML file."""
    with open(CONFIG_PATH, 'w') as file:
        yaml.dump(config, file, default_flow_style=False, allow_unicode=True)


def get_authenticator():
    """Create and return authenticator instance."""
    config = load_config()

    # streamlit-authenticator v0.4.x API
    authenticator = stauth.Authenticate(
        credentials=config['credentials'],
        cookie_name=config['cookie']['name'],
        cookie_key=config['cookie']['key'],
        cookie_expiry_days=config['cookie']['expiry_days'],
    )

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
