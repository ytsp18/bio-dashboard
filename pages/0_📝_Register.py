"""Registration page - New user registration."""
import streamlit as st
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db
from auth import submit_registration, get_settings
from utils.theme import apply_theme

init_db()

st.set_page_config(page_title="Register - Bio Dashboard", page_icon="📝", layout="centered")

# Apply light theme
apply_theme()

# Custom CSS for Register page
st.markdown("""
<style>
    .register-header {
        text-align: center;
        padding: 20px;
        margin-bottom: 30px;
    }

    .register-header h1 {
        color: #2563EB;
        margin-bottom: 10px;
    }

    .register-header p {
        color: #64748B;
    }

    .form-container {
        background: #FFFFFF;
        padding: 30px;
        border-radius: 15px;
        border: 1px solid #E2E8F0;
        max-width: 500px;
        margin: 0 auto;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    .info-box {
        background: #EFF6FF;
        border-left: 4px solid #3B82F6;
        padding: 15px;
        border-radius: 5px;
        margin: 20px 0;
        color: #1E40AF;
    }

    .success-box {
        background: #ECFDF5;
        border-left: 4px solid #10B981;
        padding: 20px;
        border-radius: 5px;
        text-align: center;
        color: #065F46;
    }
</style>
""", unsafe_allow_html=True)

# Check if already logged in
if st.session_state.get('authentication_status'):
    st.info("คุณ login อยู่แล้ว")
    st.page_link("app.py", label="🏠 ไปที่หน้าหลัก", icon="🏠")
    st.stop()

# Check if registration is allowed
settings = get_settings()
if not settings.get('allow_registration', True):
    st.error("⛔ ระบบปิดการลงทะเบียนชั่วคราว")
    st.info("กรุณาติดต่อ Admin เพื่อขอ account")
    st.stop()

# Header
st.markdown("""
<div class="register-header">
    <h1>📝 สมัครสมาชิก</h1>
    <p>สร้างบัญชีใหม่เพื่อใช้งาน Bio Dashboard</p>
</div>
""", unsafe_allow_html=True)

# Check if form was submitted successfully
if 'registration_success' in st.session_state and st.session_state.registration_success:
    st.markdown("""
    <div class="success-box">
        <h3>✅ ส่งคำขอสมัครสำเร็จ!</h3>
        <p>กรุณารอ Admin อนุมัติการสมัคร</p>
        <p>คุณจะได้รับการแจ้งเตือนเมื่อบัญชีพร้อมใช้งาน</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔙 กลับไปหน้า Login"):
        st.session_state.registration_success = False
        st.rerun()
    st.stop()

# Registration form
with st.form("registration_form"):
    st.markdown("#### ข้อมูลส่วนตัว")

    username = st.text_input(
        "Username *",
        placeholder="เช่น john_doe (ตัวอักษรภาษาอังกฤษ ตัวเลข และ _ เท่านั้น)",
        help="ใช้สำหรับ login เข้าระบบ"
    )

    name = st.text_input(
        "ชื่อ-นามสกุล *",
        placeholder="เช่น สมชาย ใจดี",
        help="ชื่อที่จะแสดงในระบบ"
    )

    email = st.text_input(
        "Email *",
        placeholder="เช่น somchai@example.com",
        help="ใช้สำหรับติดต่อและกู้รหัสผ่าน"
    )

    st.markdown("---")
    st.markdown("#### รหัสผ่าน")

    password = st.text_input(
        "รหัสผ่าน *",
        type="password",
        placeholder="อย่างน้อย 6 ตัวอักษร",
        help="ต้องมีอย่างน้อย 6 ตัวอักษร"
    )

    password_confirm = st.text_input(
        "ยืนยันรหัสผ่าน *",
        type="password",
        placeholder="ใส่รหัสผ่านอีกครั้ง"
    )

    st.markdown("---")

    # Terms
    agree_terms = st.checkbox("ฉันยอมรับเงื่อนไขการใช้งาน", value=False)

    submitted = st.form_submit_button("📝 สมัครสมาชิก", type="primary", use_container_width=True)

    if submitted:
        # Validation
        errors = []

        if not username:
            errors.append("กรุณาใส่ Username")
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append("Username ใช้ได้เฉพาะตัวอักษรภาษาอังกฤษ ตัวเลข และ _ เท่านั้น")
        elif len(username) < 3:
            errors.append("Username ต้องมีอย่างน้อย 3 ตัวอักษร")

        if not name:
            errors.append("กรุณาใส่ชื่อ-นามสกุล")

        if not email:
            errors.append("กรุณาใส่ Email")
        elif not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errors.append("รูปแบบ Email ไม่ถูกต้อง")

        if not password:
            errors.append("กรุณาใส่รหัสผ่าน")
        elif len(password) < 6:
            errors.append("รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร")

        if password != password_confirm:
            errors.append("รหัสผ่านไม่ตรงกัน")

        if not agree_terms:
            errors.append("กรุณายอมรับเงื่อนไขการใช้งาน")

        if errors:
            for error in errors:
                st.error(f"❌ {error}")
        else:
            # Submit registration
            result = submit_registration(
                username=username.lower(),
                name=name,
                email=email,
                password=password
            )

            if result['success']:
                st.session_state.registration_success = True
                st.rerun()
            else:
                st.error(f"❌ {result['error']}")

# Info box
if settings.get('require_approval', True):
    st.markdown("""
    <div class="info-box">
        <strong>📌 หมายเหตุ:</strong><br>
        หลังจากสมัครสมาชิก คำขอของคุณจะถูกส่งไปยัง Admin เพื่อพิจารณาอนุมัติ<br>
        กรุณารอการอนุมัติก่อนใช้งาน
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="info-box">
        <strong>📌 หมายเหตุ:</strong><br>
        หลังจากสมัครสมาชิก คุณสามารถ login ใช้งานได้ทันที
    </div>
    """, unsafe_allow_html=True)

# Link to login
st.markdown("---")
st.markdown("**มีบัญชีอยู่แล้ว?**")
st.page_link("app.py", label="🔐 ไปที่หน้า Login", icon="🔐")
