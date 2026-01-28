"""Bio Unified Report Dashboard - Main Application."""
import streamlit as st
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import init_db
from auth import check_authentication, logout_button, migrate_users_from_config
from utils.logger import log_info, log_error

# Initialize database on startup
init_db()


# Migrate users from config.yaml to database (run once)
@st.cache_resource
def run_user_migration():
    """Migrate users from config.yaml to database if needed."""
    try:
        result = migrate_users_from_config()
        if result.get('success'):
            migrated = result.get('migrated', 0)
            if migrated > 0:
                log_info(f"Migrated {migrated} users from config.yaml to database")
        return True
    except Exception as e:
        log_error(f"Migration error (non-fatal): {e}")
        return True  # Return True anyway to not block app startup


# Run migration on startup
run_user_migration()

# Warm up database connection on first load
@st.cache_resource
def warm_up_connection():
    """Warm up database connection pool."""
    from database.connection import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True

# Call on startup (cached, so only runs once per session)
warm_up_connection()


# Cached functions for better performance
@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_quick_stats():
    """Get cached quick statistics."""
    from database.connection import get_session
    from database.models import Report, Card

    session = get_session()
    try:
        report_count = session.query(Report).count()
        card_count = session.query(Card).count()
        good_count = session.query(Card).filter(Card.print_status == 'G').count()
        bad_count = session.query(Card).filter(Card.print_status == 'B').count()

        recent_reports = session.query(Report).order_by(Report.report_date.desc()).limit(5).all()
        recent_data = [(r.filename, str(r.report_date), r.total_good, r.total_bad) for r in recent_reports]

        return {
            'report_count': report_count,
            'card_count': card_count,
            'good_count': good_count,
            'bad_count': bad_count,
            'recent_reports': recent_data
        }
    finally:
        session.close()

# Page configuration
st.set_page_config(
    page_title="Bio Unified Report Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .stMetric {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Check authentication
if not check_authentication():
    st.stop()

# Show logout button in sidebar
logout_button()

# Main content
st.markdown('<p class="main-header">📊 Bio Unified Report Dashboard</p>', unsafe_allow_html=True)

st.markdown("""
ยินดีต้อนรับสู่ระบบ Dashboard สำหรับดูและวิเคราะห์ข้อมูล Bio Unified Report

### เมนูหลัก
ใช้เมนูด้านซ้ายเพื่อเข้าถึงฟังก์ชันต่างๆ:

- **📤 Upload** - อัพโหลดไฟล์ Excel รายงาน
- **📈 Overview** - ดูภาพรวมข้อมูลตามช่วงเวลา
- **🔍 Search** - ค้นหา Appointment ID, Card ID, Serial Number
- **🏢 By Center** - ดูสถิติตามศูนย์บริการ
- **⚠️ Anomaly** - ดูรายงานผิดปกติ
- **📋 Raw Data** - ดูข้อมูลดิบทั้งหมด

### วิธีใช้งาน
1. **อัพโหลดข้อมูล** - ไปที่หน้า Upload เพื่อนำเข้าไฟล์ Excel
2. **ดูภาพรวม** - ไปที่หน้า Overview เพื่อดูสรุปข้อมูล
3. **ค้นหา** - ใช้หน้า Search เพื่อค้นหารายการเฉพาะ
""")

# Show quick stats if data exists (with caching)
stats = get_quick_stats()

if stats['report_count'] > 0:
    st.markdown("---")
    st.subheader("📊 สถิติเบื้องต้น")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("จำนวนรายงาน", f"{stats['report_count']:,}")

    with col2:
        st.metric("จำนวนบัตรทั้งหมด", f"{stats['card_count']:,}")

    with col3:
        printed_count = stats['good_count'] + stats['bad_count']
        good_rate = stats['good_count'] / printed_count * 100 if printed_count > 0 else 0
        st.metric("อัตราบัตรดี", f"{good_rate:.1f}%", help="คำนวณจากบัตรที่พิมพ์แล้วเท่านั้น (G+B)")

    # Recent reports
    st.subheader("📅 รายงานล่าสุด")
    if stats['recent_reports']:
        for filename, report_date, total_good, total_bad in stats['recent_reports']:
            st.text(f"• {filename} ({report_date}) - บัตรดี: {total_good:,}, บัตรเสีย: {total_bad:,}")
else:
    st.info("💡 ยังไม่มีข้อมูล กรุณาไปที่หน้า **Upload** เพื่ออัพโหลดไฟล์รายงาน")
