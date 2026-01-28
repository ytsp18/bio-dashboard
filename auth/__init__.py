"""Authentication module for Bio Dashboard.

User management functions now use database storage (Supabase) instead of
config.yaml to persist user data across Streamlit Cloud deployments.
"""
from .authenticator import check_authentication, get_authenticator, logout_button
from .db_user_manager import (
    get_all_users,
    get_user,
    get_user_for_auth,
    get_all_users_for_auth,
    create_user,
    update_user,
    change_password,
    delete_user,
    is_admin,
    get_pending_registrations,
    submit_registration,
    approve_registration,
    reject_registration,
    get_settings,
    update_settings,
    migrate_users_from_config,
)
from .permissions import (
    get_user_role,
    has_permission,
    can_upload,
    can_delete,
    can_access_admin,
    require_permission,
    require_upload_permission,
    get_role_display_name,
    get_role_badge_color,
    show_role_badge,
)

__all__ = [
    # Authentication
    'check_authentication',
    'get_authenticator',
    'logout_button',
    # User management (database-based)
    'get_all_users',
    'get_user',
    'get_user_for_auth',
    'get_all_users_for_auth',
    'create_user',
    'update_user',
    'change_password',
    'delete_user',
    'is_admin',
    'get_pending_registrations',
    'submit_registration',
    'approve_registration',
    'reject_registration',
    'get_settings',
    'update_settings',
    'migrate_users_from_config',
    # Permissions
    'get_user_role',
    'has_permission',
    'can_upload',
    'can_delete',
    'can_access_admin',
    'require_permission',
    'require_upload_permission',
    'get_role_display_name',
    'get_role_badge_color',
    'show_role_badge',
]
