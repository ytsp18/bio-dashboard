"""User management utilities for Bio Dashboard."""
import yaml
from yaml.loader import SafeLoader
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from streamlit_authenticator.utilities import Hasher
except ImportError:
    from streamlit_authenticator import Hasher

from utils.timezone import now_th

# Path to config file
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')


def load_config():
    """Load config from YAML file."""
    with open(CONFIG_PATH, encoding='utf-8') as file:
        config = yaml.load(file, Loader=SafeLoader)
    return config


def save_config(config):
    """Save config to YAML file."""
    with open(CONFIG_PATH, 'w', encoding='utf-8') as file:
        yaml.dump(config, file, default_flow_style=False, allow_unicode=True)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return Hasher.hash(password)


def get_all_users():
    """Get all users from config."""
    config = load_config()
    users = []
    for username, data in config['credentials']['usernames'].items():
        users.append({
            'username': username,
            'name': data.get('name', ''),
            'email': data.get('email', ''),
            'role': data.get('role', 'user'),
        })
    return users


def get_user(username: str):
    """Get a specific user."""
    config = load_config()
    if username in config['credentials']['usernames']:
        user_data = config['credentials']['usernames'][username]
        return {
            'username': username,
            'name': user_data.get('name', ''),
            'email': user_data.get('email', ''),
            'role': user_data.get('role', 'user'),
        }
    return None


def create_user(username: str, name: str, email: str, password: str, role: str = 'user') -> dict:
    """Create a new user."""
    config = load_config()

    # Check if username exists
    if username in config['credentials']['usernames']:
        return {'success': False, 'error': 'Username already exists'}

    # Check if email exists
    for uname, data in config['credentials']['usernames'].items():
        if data.get('email', '').lower() == email.lower():
            return {'success': False, 'error': 'Email already exists'}

    # Hash password
    hashed_password = hash_password(password)

    # Add user
    config['credentials']['usernames'][username] = {
        'name': name,
        'email': email,
        'password': hashed_password,
        'role': role,
    }

    save_config(config)
    return {'success': True}


def update_user(username: str, name: str = None, email: str = None, role: str = None) -> dict:
    """Update user information (not password)."""
    config = load_config()

    if username not in config['credentials']['usernames']:
        return {'success': False, 'error': 'User not found'}

    user = config['credentials']['usernames'][username]

    if name:
        user['name'] = name
    if email:
        # Check if email is used by another user
        for uname, data in config['credentials']['usernames'].items():
            if uname != username and data.get('email', '').lower() == email.lower():
                return {'success': False, 'error': 'Email already used by another user'}
        user['email'] = email
    if role:
        user['role'] = role

    save_config(config)
    return {'success': True}


def change_password(username: str, new_password: str) -> dict:
    """Change user password."""
    config = load_config()

    if username not in config['credentials']['usernames']:
        return {'success': False, 'error': 'User not found'}

    # Hash new password
    hashed_password = hash_password(new_password)
    config['credentials']['usernames'][username]['password'] = hashed_password

    save_config(config)
    return {'success': True}


def delete_user(username: str) -> dict:
    """Delete a user."""
    config = load_config()

    if username not in config['credentials']['usernames']:
        return {'success': False, 'error': 'User not found'}

    # Prevent deleting the last admin
    user_role = config['credentials']['usernames'][username].get('role', 'user')
    if user_role == 'admin':
        admin_count = sum(1 for u, d in config['credentials']['usernames'].items()
                        if d.get('role') == 'admin')
        if admin_count <= 1:
            return {'success': False, 'error': 'Cannot delete the last admin user'}

    del config['credentials']['usernames'][username]
    save_config(config)
    return {'success': True}


def is_admin(username: str) -> bool:
    """Check if user is admin."""
    config = load_config()
    if username in config['credentials']['usernames']:
        return config['credentials']['usernames'][username].get('role') == 'admin'
    return False


# ============== Registration Functions ==============

def get_pending_registrations():
    """Get all pending registrations."""
    config = load_config()
    pending = config.get('pending_registrations', {})
    return [
        {
            'username': username,
            'name': data.get('name', ''),
            'email': data.get('email', ''),
            'requested_at': data.get('requested_at', ''),
        }
        for username, data in pending.items()
    ]


def submit_registration(username: str, name: str, email: str, password: str) -> dict:
    """Submit a new registration request."""
    config = load_config()

    # Check settings
    if not config.get('settings', {}).get('allow_registration', True):
        return {'success': False, 'error': 'Registration is disabled'}

    # Check if username exists
    if username in config['credentials']['usernames']:
        return {'success': False, 'error': 'Username already exists'}

    # Check pending registrations
    pending = config.get('pending_registrations', {})
    if username in pending:
        return {'success': False, 'error': 'Registration already pending'}

    # Check if email exists
    for uname, data in config['credentials']['usernames'].items():
        if data.get('email', '').lower() == email.lower():
            return {'success': False, 'error': 'Email already registered'}

    for uname, data in pending.items():
        if data.get('email', '').lower() == email.lower():
            return {'success': False, 'error': 'Email already pending registration'}

    # Hash password
    hashed_password = hash_password(password)

    # Add to pending
    if 'pending_registrations' not in config:
        config['pending_registrations'] = {}

    config['pending_registrations'][username] = {
        'name': name,
        'email': email,
        'password': hashed_password,
        'requested_at': now_th().strftime('%Y-%m-%d %H:%M:%S'),
    }

    save_config(config)

    # If no approval required, auto-approve
    if not config.get('settings', {}).get('require_approval', True):
        return approve_registration(username)

    return {'success': True, 'message': 'Registration submitted. Please wait for admin approval.'}


def approve_registration(username: str) -> dict:
    """Approve a pending registration."""
    config = load_config()

    pending = config.get('pending_registrations', {})
    if username not in pending:
        return {'success': False, 'error': 'Registration not found'}

    # Move from pending to users
    user_data = pending[username]
    config['credentials']['usernames'][username] = {
        'name': user_data['name'],
        'email': user_data['email'],
        'password': user_data['password'],
        'role': 'user',
    }

    # Remove from pending
    del config['pending_registrations'][username]

    save_config(config)
    return {'success': True}


def reject_registration(username: str) -> dict:
    """Reject a pending registration."""
    config = load_config()

    pending = config.get('pending_registrations', {})
    if username not in pending:
        return {'success': False, 'error': 'Registration not found'}

    del config['pending_registrations'][username]
    save_config(config)
    return {'success': True}


def get_settings():
    """Get system settings."""
    config = load_config()
    return config.get('settings', {
        'allow_registration': True,
        'require_approval': True,
    })


def update_settings(allow_registration: bool = None, require_approval: bool = None) -> dict:
    """Update system settings."""
    config = load_config()

    if 'settings' not in config:
        config['settings'] = {}

    if allow_registration is not None:
        config['settings']['allow_registration'] = allow_registration
    if require_approval is not None:
        config['settings']['require_approval'] = require_approval

    save_config(config)
    return {'success': True}
