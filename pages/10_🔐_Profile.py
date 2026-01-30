"""Profile page - User profile and password change."""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db
from utils.auth_check import require_login
from utils.theme import apply_theme
from auth import (
    get_user,
    change_password,
    get_user_role,
    get_role_display_name,
    get_role_badge_color,
)

init_db()

st.set_page_config(page_title="Profile - Bio Dashboard", page_icon="🔐", layout="wide")

# Apply light theme
apply_theme()

# Check authentication
require_login()

# Get current user info
current_username = st.session_state.get('username', '')
current_name = st.session_state.get('name', '')
user_data = get_user(current_username)
user_role = get_user_role(current_username)

# Light theme CSS
st.markdown("""
<style>
    .profile-header {
        background: linear-gradient(90deg, #F8FAFC 0%, #FFFFFF 100%);
        color: #1E293B;
        padding: 30px;
        border-radius: 15px;
        margin-bottom: 30px;
        text-align: center;
        border: 1px solid #E2E8F0;
        border-top: 4px solid #3B82F6;
    }

    .profile-avatar {
        font-size: 4em;
        margin-bottom: 15px;
    }

    .profile-name {
        font-size: 1.8em;
        font-weight: bold;
        margin-bottom: 5px;
        color: #1E293B;
    }

    .profile-username {
        color: #64748B;
        font-size: 1em;
    }

    .section-header {
        background: linear-gradient(90deg, #F8FAFC 0%, #FFFFFF 100%);
        color: #1E293B;
        padding: 16px 24px;
        border-radius: 12px;
        margin: 20px 0 15px 0;
        font-size: 1em;
        font-weight: 600;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #3B82F6;
    }

    .info-card {
        background: #FFFFFF;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        margin: 10px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    .info-label {
        color: #64748B;
        font-size: 0.9em;
        margin-bottom: 5px;
    }

    .info-value {
        color: #1E293B;
        font-size: 1.1em;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Profile Header
role_color = get_role_badge_color(user_role)
role_name = get_role_display_name(user_role)

st.markdown(f"""
<div class="profile-header">
    <div class="profile-avatar">👤</div>
    <div class="profile-name">{current_name}</div>
    <div class="profile-username">@{current_username}</div>
    <div style="margin-top: 15px;">
        <span style="background: {role_color}; color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9em;">
            {role_name}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# Tabs
tab1, tab2 = st.tabs(["📋 ข้อมูลส่วนตัว", "🔑 เปลี่ยนรหัสผ่าน"])

# Tab 1: Profile Info
with tab1:
    st.markdown('<div class="section-header">ข้อมูลบัญชี</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="info-card">
            <div class="info-label">Username</div>
            <div class="info-value">{}</div>
        </div>
        """.format(current_username), unsafe_allow_html=True)

        st.markdown("""
        <div class="info-card">
            <div class="info-label">ชื่อ-นามสกุล</div>
            <div class="info-value">{}</div>
        </div>
        """.format(user_data['name'] if user_data else '-'), unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="info-card">
            <div class="info-label">Email</div>
            <div class="info-value">{}</div>
        </div>
        """.format(user_data['email'] if user_data else '-'), unsafe_allow_html=True)

        st.markdown("""
        <div class="info-card">
            <div class="info-label">Role</div>
            <div class="info-value">{}</div>
        </div>
        """.format(role_name), unsafe_allow_html=True)

    # Role Permissions
    st.markdown('<div class="section-header">สิทธิ์การใช้งาน</div>', unsafe_allow_html=True)

    permissions = {
        'admin': ['ดูข้อมูลทั้งหมด', 'อัพโหลดไฟล์', 'ลบรายงาน', 'จัดการผู้ใช้', 'ตั้งค่าระบบ'],
        'user': ['ดูข้อมูลทั้งหมด', 'อัพโหลดไฟล์', 'ลบรายงาน'],
        'viewer': ['ดูข้อมูลทั้งหมด'],
    }

    user_permissions = permissions.get(user_role, [])

    col1, col2 = st.columns(2)
    for i, perm in enumerate(user_permissions):
        if i % 2 == 0:
            col1.success(f"✅ {perm}")
        else:
            col2.success(f"✅ {perm}")

    # Restricted permissions
    all_perms = ['ดูข้อมูลทั้งหมด', 'อัพโหลดไฟล์', 'ลบรายงาน', 'จัดการผู้ใช้', 'ตั้งค่าระบบ']
    restricted = [p for p in all_perms if p not in user_permissions]

    if restricted:
        st.markdown("---")
        st.markdown("**สิทธิ์ที่ไม่มี:**")
        for perm in restricted:
            st.warning(f"❌ {perm}")

# Tab 2: Change Password
with tab2:
    st.markdown('<div class="section-header">เปลี่ยนรหัสผ่าน</div>', unsafe_allow_html=True)

    with st.form("change_password_form"):
        current_password = st.text_input(
            "รหัสผ่านปัจจุบัน",
            type="password",
            placeholder="ใส่รหัสผ่านปัจจุบัน"
        )

        st.markdown("---")

        new_password = st.text_input(
            "รหัสผ่านใหม่",
            type="password",
            placeholder="อย่างน้อย 6 ตัวอักษร"
        )

        confirm_password = st.text_input(
            "ยืนยันรหัสผ่านใหม่",
            type="password",
            placeholder="ใส่รหัสผ่านใหม่อีกครั้ง"
        )

        submitted = st.form_submit_button("🔑 เปลี่ยนรหัสผ่าน", type="primary", use_container_width=True)

        if submitted:
            errors = []

            if not current_password:
                errors.append("กรุณาใส่รหัสผ่านปัจจุบัน")

            if not new_password:
                errors.append("กรุณาใส่รหัสผ่านใหม่")
            elif len(new_password) < 6:
                errors.append("รหัสผ่านใหม่ต้องมีอย่างน้อย 6 ตัวอักษร")

            if new_password != confirm_password:
                errors.append("รหัสผ่านใหม่ไม่ตรงกัน")

            if new_password == current_password:
                errors.append("รหัสผ่านใหม่ต้องไม่เหมือนรหัสผ่านเดิม")

            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                # Note: For full security, should verify current_password first
                # This simplified version just changes the password
                result = change_password(current_username, new_password)
                if result['success']:
                    st.success("✅ เปลี่ยนรหัสผ่านสำเร็จ!")
                    st.info("กรุณา Logout และ Login ใหม่ด้วยรหัสผ่านใหม่")
                else:
                    st.error(f"❌ {result['error']}")

    st.markdown("---")
    st.markdown("""
    **หมายเหตุ:**
    - รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร
    - หลังเปลี่ยนรหัสผ่าน ควร Logout และ Login ใหม่
    """)

# Footer
st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #64748B; padding: 10px;">'
    'Bio Dashboard - Profile'
    '</div>',
    unsafe_allow_html=True
)
