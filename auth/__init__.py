"""Authentication module for Bio Dashboard."""
from .authenticator import check_authentication, get_authenticator, logout_button
from .user_manager import (
    get_all_users,
    get_user,
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
    # User management
    'get_all_users',
    'get_user',
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
