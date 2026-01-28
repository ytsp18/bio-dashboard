"""Upload page for importing Excel files."""
import streamlit as st
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session
from database.models import Report
from services.data_service import DataService
from services.excel_parser import ExcelParser
from utils.auth_check import require_login
from auth import can_upload, can_delete, get_user_role

# Initialize database
init_db()

st.set_page_config(page_title="Upload - Bio Dashboard", page_icon="📤", layout="wide")

# Check authentication
require_login()

# Check upload permission
if not can_upload():
    st.error("⛔ คุณไม่มีสิทธิ์อัพโหลดไฟล์ (Role: Viewer)")
    st.info("กรุณาติดต่อ Admin เพื่อขอสิทธิ์ User หรือ Admin")
    st.stop()

# Custom CSS
st.markdown("""
<style>
    .section-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 10px;
        margin: 20px 0 15px 0;
        font-size: 1.2em;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .upload-box {
        border: 2px dashed #3498db;
        border-radius: 15px;
        padding: 40px;
        text-align: center;
        background: #f8f9fa;
        margin: 20px 0;
    }

    .stat-card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        text-align: center;
        border-left: 4px solid #3498db;
    }

    .report-card {
        background: white;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border-left: 4px solid #2ecc71;
    }

    .info-text {
        color: #666;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown("""
<h1 style='text-align: center; color: #1e3c72; margin-bottom: 5px;'>
    📤 อัพโหลดไฟล์รายงาน
</h1>
<p style='text-align: center; color: #666; margin-bottom: 25px;'>
    นำเข้าไฟล์ Bio Unified Report เข้าสู่ระบบ
</p>
""", unsafe_allow_html=True)

# Upload section
st.markdown('<div class="section-header">📁 เลือกไฟล์</div>', unsafe_allow_html=True)

st.markdown("""
<div class="info-text">
    <p>รองรับไฟล์ <strong>Bio_unified_report_*.xlsx</strong> ทั้งรายวันและรายเดือน</p>
</div>
""", unsafe_allow_html=True)

# File uploader
uploaded_file = st.file_uploader(
    "เลือกไฟล์ Excel",
    type=['xlsx'],
    help="เลือกไฟล์ Bio_unified_report_*.xlsx",
    label_visibility="collapsed"
)

if uploaded_file is not None:
    st.success(f"✅ เลือกไฟล์: **{uploaded_file.name}**")

    # Preview section
    st.markdown('<div class="section-header">🔍 Preview ข้อมูล</div>', unsafe_allow_html=True)

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

    try:
        # Parse file for preview
        parser = ExcelParser(tmp_path)
        parser.load()

        # Show sheet info
        sheets = parser.get_sheet_names()

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("**📑 Sheets ที่พบ:**")
            st.caption(f"จำนวน {len(sheets)} sheets")
        with col2:
            with st.expander("ดู sheets ทั้งหมด"):
                for i, sheet in enumerate(sheets, 1):
                    st.text(f"{i}. {sheet}")

        # Show summary
        report_date = parser.extract_report_date()
        stats = parser.get_summary_stats()

        st.markdown("---")
        st.markdown("#### 📊 สรุปข้อมูลในไฟล์")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📅 วันที่รายงาน", str(report_date))
        with col2:
            st.metric("📊 จำนวนทั้งหมด", f"{stats['total_records']:,}")
        with col3:
            st.metric("✅ บัตรดี (G) - รวม", f"{stats['good_cards']:,}")
        with col4:
            st.metric("❌ บัตรเสีย (B)", f"{stats['bad_cards']:,}")

        # Show additional stats if available
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏢 บัตรดี - รับที่ศูนย์", f"{stats.get('good_pickup', 0):,}")
        with col2:
            st.metric("📦 บัตรดี - จัดส่ง", f"{stats.get('good_delivery', 0):,}")
        with col3:
            st.metric("🔢 Unique Serial (G)", f"{stats.get('unique_serial_g', 0):,}")

        # Preview data
        st.markdown("---")
        st.markdown("#### 📋 ตัวอย่างข้อมูล")

        all_data = parser.parse_all_data()
        if not all_data.empty:
            st.caption(f"แสดง 10 รายการแรก จากทั้งหมด {len(all_data):,} รายการ")
            st.dataframe(all_data.head(10), use_container_width=True, hide_index=True)
        else:
            # Try showing from good cards
            good_cards = parser.parse_good_cards()
            if not good_cards.empty:
                st.caption(f"แสดง 10 รายการแรก (บัตรดี) จากทั้งหมด {len(good_cards):,} รายการ")
                st.dataframe(good_cards.head(10), use_container_width=True, hide_index=True)
            else:
                st.warning("ไม่พบข้อมูลในไฟล์")

    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการอ่านไฟล์: {str(e)}")
        tmp_path = None

    # Import button
    if tmp_path:
        st.markdown("---")
        st.markdown('<div class="section-header">📥 นำเข้าข้อมูล</div>', unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📥 นำเข้าข้อมูลเข้าระบบ", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()

                try:
                    status_text.text("กำลังอ่านไฟล์...")
                    progress_bar.progress(20)

                    status_text.text("กำลังประมวลผลข้อมูล...")
                    progress_bar.progress(40)

                    result = DataService.import_excel(tmp_path, original_filename=uploaded_file.name)

                    progress_bar.progress(80)
                    status_text.text("กำลังบันทึกข้อมูล...")

                    progress_bar.progress(100)
                    status_text.empty()

                    st.success("✅ นำเข้าข้อมูลสำเร็จ!")

                    # Show import results
                    st.markdown("#### 📋 ผลการนำเข้า")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("""
                        <div style='background: #e8f5e9; padding: 15px; border-radius: 10px;'>
                        """, unsafe_allow_html=True)
                        st.markdown(f"""
                        **📁 ข้อมูลไฟล์**
                        - ชื่อไฟล์: `{result['filename']}`
                        - วันที่รายงาน: **{result['report_date']}**
                        - บัตรดี (G): **{result['total_good']:,}** ใบ
                        - บัตรเสีย (B): **{result['total_bad']:,}** ใบ
                        """)
                        st.markdown("</div>", unsafe_allow_html=True)

                    with col2:
                        st.markdown("""
                        <div style='background: #e3f2fd; padding: 15px; border-radius: 10px;'>
                        """, unsafe_allow_html=True)
                        st.markdown(f"""
                        **📊 รายการที่นำเข้า**
                        - ข้อมูลบัตร: **{result['cards_imported']:,}** รายการ
                        - บัตรเสีย: **{result['bad_cards_imported']:,}** รายการ
                        - บัตรจัดส่ง: **{result.get('delivery_imported', 0):,}** รายการ
                        - สถิติศูนย์: **{result['centers_imported']:,}** รายการ
                        - SLA เกิน: **{result['sla_anomalies_imported']:,}** รายการ
                        - ออกบัตรผิดศูนย์: **{result['wrong_center_imported']:,}** รายการ
                        """)
                        st.markdown("</div>", unsafe_allow_html=True)

                    st.balloons()

                except Exception as e:
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")

        # Cleanup temp file
        try:
            os.unlink(tmp_path)
        except:
            pass

# Show existing reports
st.markdown("---")
st.markdown('<div class="section-header">📋 รายงานที่มีในระบบ</div>', unsafe_allow_html=True)

session = get_session()
try:
    reports = session.query(Report).order_by(Report.report_date.desc()).all()

    if reports:
        import pandas as pd

        # Summary stats
        total_reports = len(reports)
        total_good = sum(r.total_good or 0 for r in reports)
        total_bad = sum(r.total_bad or 0 for r in reports)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📁 จำนวนรายงาน", f"{total_reports}")
        with col2:
            st.metric("✅ บัตรดีรวม", f"{total_good:,}")
        with col3:
            st.metric("❌ บัตรเสียรวม", f"{total_bad:,}")

        st.markdown("---")

        # Table of reports
        data = []
        for r in reports:
            data.append({
                'ID': r.id,
                'ชื่อไฟล์': r.filename[:50] + '...' if len(r.filename) > 50 else r.filename,
                'วันที่รายงาน': r.report_date,
                'วันที่อัพโหลด': r.upload_date.strftime('%Y-%m-%d %H:%M') if r.upload_date else '-',
                'บัตรดี': r.total_good or 0,
                'บัตรเสีย': r.total_bad or 0,
                'รวม': r.total_records or 0,
            })

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Management options
        st.markdown("---")
        st.markdown("#### 🛠️ จัดการรายงาน")

        tab1, tab2 = st.tabs(["แก้ไขชื่อไฟล์", "ลบรายงาน"])

        with tab1:
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                report_to_edit = st.selectbox(
                    "เลือกรายงาน",
                    options=[(r.id, r.filename) for r in reports],
                    format_func=lambda x: x[1],
                    key="edit_report"
                )
            with col2:
                new_filename = st.text_input(
                    "ชื่อไฟล์ใหม่",
                    value=report_to_edit[1] if report_to_edit else "",
                    key="new_filename"
                )
            with col3:
                st.write("")
                st.write("")
                if st.button("💾 บันทึก", type="primary", use_container_width=True):
                    if new_filename and new_filename != report_to_edit[1]:
                        try:
                            report = session.query(Report).filter(Report.id == report_to_edit[0]).first()
                            if report:
                                report.filename = new_filename
                                session.commit()
                                st.success(f"✅ เปลี่ยนชื่อเป็น {new_filename} สำเร็จ")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
                            session.rollback()

        with tab2:
            if not can_delete():
                st.warning("⚠️ คุณไม่มีสิทธิ์ลบรายงาน")
            else:
                col1, col2 = st.columns([3, 1])
                with col1:
                    report_to_delete = st.selectbox(
                        "เลือกรายงานที่ต้องการลบ",
                        options=[(r.id, r.filename) for r in reports],
                        format_func=lambda x: x[1],
                        key="delete_report"
                    )

                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ ลบรายงาน", type="secondary", use_container_width=True):
                        try:
                            report = session.query(Report).filter(Report.id == report_to_delete[0]).first()
                            if report:
                                session.delete(report)
                                session.commit()
                                st.success(f"✅ ลบรายงาน {report_to_delete[1]} สำเร็จ")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
                            session.rollback()

    else:
        st.markdown("""
        <div style='text-align: center; padding: 40px; background: #f8f9fa; border-radius: 15px;'>
            <h3>📭 ยังไม่มีรายงานในระบบ</h3>
            <p>อัพโหลดไฟล์ Bio Unified Report เพื่อเริ่มต้นใช้งาน</p>
        </div>
        """, unsafe_allow_html=True)

finally:
    session.close()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888; padding: 10px;'>
    <p>📊 Bio Unified Report Dashboard</p>
</div>
""", unsafe_allow_html=True)
