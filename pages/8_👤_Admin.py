"""Admin Panel - User Management."""
import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db
from utils.auth_check import require_login
from auth import (
    is_admin,
    get_all_users,
    create_user,
    update_user,
    change_password,
    delete_user,
    get_pending_registrations,
    approve_registration,
    reject_registration,
    get_settings,
    update_settings,
)

init_db()

st.set_page_config(page_title="Admin - Bio Dashboard", page_icon="👤", layout="wide")

# Check authentication
require_login()

# Check if user is admin
current_user = st.session_state.get('username', '')
if not is_admin(current_user):
    st.error("⛔ คุณไม่มีสิทธิ์เข้าถึงหน้านี้ (ต้องเป็น Admin เท่านั้น)")
    st.stop()

# Dark theme CSS
st.markdown("""
<style>
    .admin-header {
        background: linear-gradient(90deg, #6c3483 0%, #9b59b6 100%);
        color: white;
        padding: 15px 25px;
        border-radius: 10px;
        margin-bottom: 20px;
        text-align: center;
    }

    .section-header {
        background: linear-gradient(90deg, #21262d 0%, #161b22 100%);
        color: #c9d1d9;
        padding: 12px 20px;
        border-radius: 8px;
        margin: 20px 0 15px 0;
        font-size: 1em;
        font-weight: 600;
        border-left: 4px solid #58a6ff;
    }

    .user-card {
        background: #161b22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363d;
        margin: 10px 0;
    }

    .pending-badge {
        background: #f59e0b;
        color: black;
        padding: 3px 10px;
        border-radius: 15px;
        font-size: 0.8em;
        font-weight: bold;
    }

    .admin-badge {
        background: #9333ea;
        color: white;
        padding: 3px 10px;
        border-radius: 15px;
        font-size: 0.8em;
    }

    .user-badge {
        background: #3b82f6;
        color: white;
        padding: 3px 10px;
        border-radius: 15px;
        font-size: 0.8em;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="admin-header"><h2>👤 Admin Panel - จัดการผู้ใช้</h2></div>', unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📋 รายชื่อผู้ใช้", "➕ เพิ่มผู้ใช้ใหม่", "📝 คำขอสมัคร", "⚙️ ตั้งค่า"])

# ============== Tab 1: User List ==============
with tab1:
    st.markdown('<div class="section-header">รายชื่อผู้ใช้ทั้งหมด</div>', unsafe_allow_html=True)

    users = get_all_users()

    if users:
        # Summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("ผู้ใช้ทั้งหมด", len(users))
        with col2:
            admin_count = sum(1 for u in users if u['role'] == 'admin')
            st.metric("Admin", admin_count)
        with col3:
            user_count = sum(1 for u in users if u['role'] == 'user')
            st.metric("User", user_count)

        st.markdown("---")

        # User table
        df = pd.DataFrame(users)
        df = df[['username', 'name', 'email', 'role']]
        df.columns = ['Username', 'ชื่อ', 'Email', 'Role']

        st.dataframe(df, use_container_width=True, hide_index=True)

        # Edit/Delete section
        st.markdown("---")
        st.markdown("#### แก้ไข/ลบผู้ใช้")

        col1, col2 = st.columns(2)

        with col1:
            selected_user = st.selectbox(
                "เลือกผู้ใช้",
                options=[u['username'] for u in users],
                format_func=lambda x: f"{x} ({next((u['name'] for u in users if u['username'] == x), '')})"
            )

        if selected_user:
            user_data = next((u for u in users if u['username'] == selected_user), None)

            if user_data:
                st.markdown(f"**ผู้ใช้ที่เลือก:** {user_data['name']} (`{selected_user}`)")

                with st.expander("📝 แก้ไขข้อมูล", expanded=False):
                    new_name = st.text_input("ชื่อใหม่", value=user_data['name'], key="edit_name")
                    new_email = st.text_input("Email ใหม่", value=user_data['email'], key="edit_email")

                    role_options = ['admin', 'user', 'viewer']
                    role_index = role_options.index(user_data['role']) if user_data['role'] in role_options else 2
                    new_role = st.selectbox(
                        "Role",
                        options=role_options,
                        index=role_index,
                        format_func=lambda x: {'admin': 'Admin (จัดการระบบ)', 'user': 'User (อัพโหลดได้)', 'viewer': 'Viewer (ดูอย่างเดียว)'}.get(x, x),
                        key="edit_role"
                    )

                    if st.button("💾 บันทึกการแก้ไข", type="primary"):
                        result = update_user(selected_user, name=new_name, email=new_email, role=new_role)
                        if result['success']:
                            st.success("✅ อัพเดทข้อมูลสำเร็จ")
                            st.rerun()
                        else:
                            st.error(f"❌ {result['error']}")

                with st.expander("🔑 เปลี่ยนรหัสผ่าน", expanded=False):
                    new_password = st.text_input("รหัสผ่านใหม่", type="password", key="new_pass")
                    confirm_password = st.text_input("ยืนยันรหัสผ่าน", type="password", key="confirm_pass")

                    if st.button("🔑 เปลี่ยนรหัสผ่าน"):
                        if not new_password:
                            st.error("กรุณาใส่รหัสผ่านใหม่")
                        elif new_password != confirm_password:
                            st.error("รหัสผ่านไม่ตรงกัน")
                        elif len(new_password) < 6:
                            st.error("รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร")
                        else:
                            result = change_password(selected_user, new_password)
                            if result['success']:
                                st.success("✅ เปลี่ยนรหัสผ่านสำเร็จ")
                            else:
                                st.error(f"❌ {result['error']}")

                with st.expander("🗑️ ลบผู้ใช้", expanded=False):
                    st.warning(f"⚠️ คุณกำลังจะลบผู้ใช้ **{selected_user}** การดำเนินการนี้ไม่สามารถย้อนกลับได้!")

                    if selected_user == current_user:
                        st.error("ไม่สามารถลบตัวเองได้")
                    else:
                        confirm_delete = st.checkbox(f"ยืนยันการลบ {selected_user}", key="confirm_delete")
                        if st.button("🗑️ ลบผู้ใช้", type="secondary", disabled=not confirm_delete):
                            result = delete_user(selected_user)
                            if result['success']:
                                st.success("✅ ลบผู้ใช้สำเร็จ")
                                st.rerun()
                            else:
                                st.error(f"❌ {result['error']}")

    else:
        st.info("ไม่มีผู้ใช้ในระบบ")

# ============== Tab 2: Add New User ==============
with tab2:
    st.markdown('<div class="section-header">เพิ่มผู้ใช้ใหม่</div>', unsafe_allow_html=True)

    with st.form("add_user_form"):
        col1, col2 = st.columns(2)

        with col1:
            new_username = st.text_input("Username *", placeholder="เช่น john_doe")
            new_user_name = st.text_input("ชื่อ-นามสกุล *", placeholder="เช่น John Doe")
            new_user_email = st.text_input("Email *", placeholder="เช่น john@example.com")

        with col2:
            new_user_password = st.text_input("รหัสผ่าน *", type="password")
            new_user_password_confirm = st.text_input("ยืนยันรหัสผ่าน *", type="password")
            new_user_role = st.selectbox(
                "Role",
                options=['viewer', 'user', 'admin'],
                format_func=lambda x: {'admin': 'Admin (จัดการระบบ)', 'user': 'User (อัพโหลดได้)', 'viewer': 'Viewer (ดูอย่างเดียว)'}.get(x, x)
            )

        submitted = st.form_submit_button("➕ เพิ่มผู้ใช้", type="primary", use_container_width=True)

        if submitted:
            # Validation
            if not all([new_username, new_user_name, new_user_email, new_user_password]):
                st.error("กรุณากรอกข้อมูลให้ครบทุกช่อง")
            elif new_user_password != new_user_password_confirm:
                st.error("รหัสผ่านไม่ตรงกัน")
            elif len(new_user_password) < 6:
                st.error("รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร")
            elif ' ' in new_username:
                st.error("Username ไม่สามารถมีช่องว่างได้")
            else:
                result = create_user(
                    username=new_username.lower(),
                    name=new_user_name,
                    email=new_user_email,
                    password=new_user_password,
                    role=new_user_role
                )
                if result['success']:
                    st.success(f"✅ สร้างผู้ใช้ **{new_username}** สำเร็จ")
                    st.balloons()
                else:
                    st.error(f"❌ {result['error']}")

# ============== Tab 3: Pending Registrations ==============
with tab3:
    st.markdown('<div class="section-header">คำขอสมัครสมาชิกที่รอการอนุมัติ</div>', unsafe_allow_html=True)

    pending = get_pending_registrations()

    if pending:
        st.info(f"📋 มี **{len(pending)}** คำขอที่รอการอนุมัติ")

        for reg in pending:
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

                with col1:
                    st.write(f"**Username:** {reg['username']}")
                    st.write(f"**ชื่อ:** {reg['name']}")

                with col2:
                    st.write(f"**Email:** {reg['email']}")
                    st.write(f"**วันที่ขอ:** {reg['requested_at']}")

                with col3:
                    if st.button("✅ อนุมัติ", key=f"approve_{reg['username']}", type="primary"):
                        result = approve_registration(reg['username'])
                        if result['success']:
                            st.success(f"อนุมัติ {reg['username']} แล้ว")
                            st.rerun()
                        else:
                            st.error(result['error'])

                with col4:
                    if st.button("❌ ปฏิเสธ", key=f"reject_{reg['username']}"):
                        result = reject_registration(reg['username'])
                        if result['success']:
                            st.warning(f"ปฏิเสธ {reg['username']} แล้ว")
                            st.rerun()
                        else:
                            st.error(result['error'])

                st.markdown("---")
    else:
        st.success("✅ ไม่มีคำขอที่รอการอนุมัติ")

# ============== Tab 4: Settings ==============
with tab4:
    st.markdown('<div class="section-header">ตั้งค่าระบบ</div>', unsafe_allow_html=True)

    settings = get_settings()

    col1, col2 = st.columns(2)

    with col1:
        allow_reg = st.toggle(
            "เปิดให้สมัครสมาชิก",
            value=settings.get('allow_registration', True),
            help="อนุญาตให้ผู้ใช้ใหม่สมัครสมาชิกได้"
        )

    with col2:
        require_approve = st.toggle(
            "ต้องรอ Admin อนุมัติ",
            value=settings.get('require_approval', True),
            help="ผู้สมัครใหม่ต้องรอ Admin อนุมัติก่อนใช้งาน"
        )

    if st.button("💾 บันทึกการตั้งค่า", type="primary"):
        result = update_settings(
            allow_registration=allow_reg,
            require_approval=require_approve
        )
        if result['success']:
            st.success("✅ บันทึกการตั้งค่าสำเร็จ")
        else:
            st.error("❌ เกิดข้อผิดพลาด")

    st.markdown("---")

    # System info
    st.markdown("#### ข้อมูลระบบ")

    users = get_all_users()
    pending = get_pending_registrations()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("ผู้ใช้ทั้งหมด", len(users))
    with col2:
        st.metric("รอการอนุมัติ", len(pending))
    with col3:
        st.metric("Admin", sum(1 for u in users if u['role'] == 'admin'))

# Footer
st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #6e7681; padding: 10px;">'
    'Bio Dashboard - Admin Panel'
    '</div>',
    unsafe_allow_html=True
)
