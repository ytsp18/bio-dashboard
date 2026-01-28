"""Role-based permissions for Bio Dashboard.

Roles:
    - admin: Full access to everything including Admin Panel
    - user: Can use all features + upload files, but no Admin Panel access
    - viewer: View only, cannot upload files
"""
import streamlit as st
from .db_user_manager import get_user


@st.cache_data(ttl=60)  # Cache user data for 60 seconds
def _get_cached_user(username: str):
    """Get user from database with caching."""
    return get_user(username)


# Permission definitions
PERMISSIONS = {
    'admin': {
        'view_dashboard': True,
        'view_reports': True,
        'view_search': True,
        'view_analytics': True,
        'view_raw_data': True,
        'upload_files': True,
        'delete_reports': True,
        'admin_panel': True,
        'manage_users': True,
    },
    'user': {
        'view_dashboard': True,
        'view_reports': True,
        'view_search': True,
        'view_analytics': True,
        'view_raw_data': True,
        'upload_files': True,
        'delete_reports': True,
        'admin_panel': False,
        'manage_users': False,
    },
    'viewer': {
        'view_dashboard': True,
        'view_reports': True,
        'view_search': True,
        'view_analytics': True,
        'view_raw_data': True,
        'upload_files': False,
        'delete_reports': False,
        'admin_panel': False,
        'manage_users': False,
    },
}


def get_user_role(username: str = None) -> str:
    """Get user role from database (cached)."""
    if username is None:
        username = st.session_state.get('username', '')

    if not username:
        return 'viewer'

    # Use cached version to avoid repeated DB queries
    user = _get_cached_user(username)
    if user:
        return user.get('role', 'viewer')
    return 'viewer'


def has_permission(permission: str, username: str = None) -> bool:
    """Check if user has a specific permission."""
    role = get_user_role(username)
    return PERMISSIONS.get(role, {}).get(permission, False)


def can_upload(username: str = None) -> bool:
    """Check if user can upload files."""
    return has_permission('upload_files', username)


def can_delete(username: str = None) -> bool:
    """Check if user can delete reports."""
    return has_permission('delete_reports', username)


def can_access_admin(username: str = None) -> bool:
    """Check if user can access admin panel."""
    return has_permission('admin_panel', username)


def require_permission(permission: str):
    """
    Decorator/function to require a specific permission.
    Stops execution if permission is not granted.
    """
    if not has_permission(permission):
        role = get_user_role()
        st.error(f"⛔ คุณไม่มีสิทธิ์ดำเนินการนี้ (Role: {role})")
        st.info("กรุณาติดต่อ Admin เพื่อขอสิทธิ์เพิ่มเติม")
        st.stop()


def require_upload_permission():
    """Require upload permission, stops if not allowed."""
    require_permission('upload_files')


def get_role_display_name(role: str) -> str:
    """Get display name for role."""
    names = {
        'admin': 'Admin (ผู้ดูแลระบบ)',
        'user': 'User (ผู้ใช้งาน)',
        'viewer': 'Viewer (ผู้ชม)',
    }
    return names.get(role, role)


def get_role_badge_color(role: str) -> str:
    """Get badge color for role."""
    colors = {
        'admin': '#9333ea',  # Purple
        'user': '#3b82f6',   # Blue
        'viewer': '#6b7280', # Gray
    }
    return colors.get(role, '#6b7280')


def show_role_badge(role: str = None):
    """Display role badge in sidebar."""
    if role is None:
        role = get_user_role()

    color = get_role_badge_color(role)
    display_name = get_role_display_name(role)

    st.sidebar.markdown(
        f'<span style="background: {color}; color: white; padding: 3px 10px; '
        f'border-radius: 15px; font-size: 0.8em;">{display_name}</span>',
        unsafe_allow_html=True
    )
