"""Upload page for importing QLog data files."""
import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session
from database.models import QLog, QLogUpload
from utils.auth_check import require_login
from utils.theme import apply_theme
from auth import can_upload, can_delete

init_db()

st.set_page_config(page_title="Upload QLog - Bio Dashboard", page_icon="⏱️", layout="wide")

apply_theme()
require_login()

if not can_upload():
    st.error("คุณไม่มีสิทธิ์อัพโหลดไฟล์ (Role: Viewer)")
    st.stop()

# Custom CSS
st.markdown("""
<style>
    .section-header {
        background: linear-gradient(90deg, #1A1F2E 0%, #252B3B 100%);
        color: #FAFAFA;
        padding: 16px 24px;
        border-radius: 12px;
        margin: 20px 0 15px 0;
        font-size: 1.1em;
        font-weight: 600;
        border: 1px solid #374151;
        border-left: 4px solid #10B981;
    }
    .info-box {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-left: 4px solid #10B981;
        padding: 16px 20px;
        border-radius: 8px;
        color: #6EE7B7;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown("""
<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #374151;">
    <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #10B981, #059669); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
        <span style="font-size: 24px;">⏱️</span>
    </div>
    <div>
        <h1 style="font-size: 1.75rem; font-weight: 700; color: #FAFAFA; margin: 0;">Upload ข้อมูล QLog</h1>
        <p style="font-size: 0.9rem; color: #9CA3AF; margin: 0;">นำเข้าข้อมูล Check-in จากระบบคิว</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    <strong>ข้อมูลที่ต้องการ:</strong> ไฟล์ CSV จากระบบ QLog<br>
    <strong>คอลัมน์หลัก:</strong> QLOG_ID, BRANCH_ID, QLOG_TIMEIN, APPOINTMENT_CODE, QLOG_STATUS
</div>
""", unsafe_allow_html=True)

# Column mapping
QLOG_COLUMNS = {
    'qlog_id': ['QLOG_ID', 'qlog_id'],
    'branch_code': ['BRANCH_ID', 'branch_id', 'branch_code'],
    'qlog_type': ['QLOG_TYPE', 'qlog_type'],
    'qlog_typename': ['QLOG_TYPENAME', 'qlog_typename'],
    'qlog_num': ['QLOG_NUM', 'qlog_num'],
    'qlog_counter': ['QLOG_COUNTER', 'qlog_counter'],
    'qlog_user': ['QLOG_USER', 'qlog_user'],
    'qlog_time_in': ['QLOG_TIMEIN', 'qlog_timein', 'qlog_time_in'],
    'qlog_date': ['QLOG_DATE', 'qlog_date', 'QLOG_DATEIN'],
    'qlog_time_call': ['QLOG_TIMECALL', 'qlog_timecall'],
    'qlog_time_end': ['QLOG_TIMEEND', 'qlog_timeend'],
    'wait_time_seconds': ['QLOG_COUNTWAIT', 'qlog_countwait'],
    'appointment_code': ['APPOINTMENT_CODE', 'appointment_code'],
    'appointment_time': ['APPOINTMENT_TIME', 'appointment_time'],
    'qlog_status': ['QLOG_STATUS', 'qlog_status'],
    'sla_status': ['SLA_STATUS', 'sla_status'],
    'sla_time_start': ['SLA_TIMESTART', 'sla_timestart'],
    'sla_time_end': ['SLA_TIMEEND', 'sla_timeend'],
}


def find_column(df, target_col):
    """Find matching column name in dataframe."""
    possible_names = QLOG_COLUMNS.get(target_col, [target_col])
    for col in df.columns:
        col_upper = col.upper().strip()
        for name in possible_names:
            if col_upper == name.upper():
                return col
    return None


def parse_date(val):
    """Parse date from various formats."""
    if pd.isna(val):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date() if hasattr(val, 'date') else val
    try:
        return pd.to_datetime(val).date()
    except:
        return None


def safe_int(val):
    """Safely convert to int."""
    if pd.isna(val):
        return None
    try:
        return int(float(val))
    except:
        return None


def safe_str(val):
    """Safely convert to string."""
    if pd.isna(val):
        return None
    return str(val).strip() if val else None


# Upload section
st.markdown('<div class="section-header">📁 เลือกไฟล์ QLog</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "เลือกไฟล์ CSV",
    type=['csv'],
    help="ไฟล์ qlog-*.csv จากระบบคิว",
    label_visibility="collapsed"
)

if uploaded_file is not None:
    st.success(f"เลือกไฟล์: **{uploaded_file.name}**")

    try:
        df = pd.read_csv(uploaded_file)

        st.markdown('<div class="section-header">🔍 Preview ข้อมูล</div>', unsafe_allow_html=True)

        st.markdown("**คอลัมน์ที่พบในไฟล์:**")
        st.caption(", ".join(df.columns.tolist()))

        # Auto-map columns
        col_mapping = {}
        for target_col in QLOG_COLUMNS.keys():
            found = find_column(df, target_col)
            col_mapping[target_col] = found

        # Show mapping status
        st.markdown("---")
        st.markdown("#### 🔗 การแมพคอลัมน์อัตโนมัติ")

        mapped_count = sum(1 for v in col_mapping.values() if v)
        st.info(f"พบคอลัมน์ที่ตรงกัน: {mapped_count}/{len(QLOG_COLUMNS)}")

        with st.expander("ดูการแมพคอลัมน์"):
            for target, found in col_mapping.items():
                if found:
                    st.text(f"✅ {target} → {found}")
                else:
                    st.text(f"❌ {target} → ไม่พบ")

        # Check required columns
        required = ['qlog_date', 'branch_code', 'appointment_code']
        missing = [c for c in required if not col_mapping.get(c)]

        if missing:
            st.warning(f"ไม่พบคอลัมน์ที่จำเป็น: {', '.join(missing)}")
        else:
            # Summary
            st.markdown("---")
            st.markdown("#### 📊 สรุปข้อมูล")

            total_records = len(df)

            # Parse dates
            date_col = col_mapping['qlog_date']
            df['_parsed_date'] = df[date_col].apply(parse_date)
            valid_dates = df['_parsed_date'].dropna()

            min_date = valid_dates.min() if len(valid_dates) > 0 else None
            max_date = valid_dates.max() if len(valid_dates) > 0 else None

            # Status counts
            status_col = col_mapping.get('qlog_status')
            if status_col:
                status_counts = df[status_col].value_counts()
                success_count = status_counts.get('S', 0)
                waiting_count = status_counts.get('W', 0)
            else:
                success_count = waiting_count = 0

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("จำนวน Records", f"{total_records:,}")
            with col2:
                st.metric("Served (S)", f"{success_count:,}")
            with col3:
                st.metric("Waiting (W)", f"{waiting_count:,}")
            with col4:
                st.metric("ช่วงวันที่", f"{min_date} - {max_date}" if min_date else "-")

            # Preview
            st.markdown("---")
            st.markdown("#### 📋 ตัวอย่างข้อมูล")
            st.dataframe(df.head(10), use_container_width=True, hide_index=True)

            # Import button
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📥 นำเข้าข้อมูล QLog", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        session = get_session()

                        status_text.text("กำลังสร้าง Upload record...")
                        progress_bar.progress(10)

                        upload = QLogUpload(
                            filename=uploaded_file.name,
                            date_from=min_date,
                            date_to=max_date,
                            total_records=total_records,
                            uploaded_by=st.session_state.get('username', 'unknown')
                        )
                        session.add(upload)
                        session.flush()

                        status_text.text("กำลังประมวลผลข้อมูล...")
                        progress_bar.progress(30)

                        qlogs = []
                        for idx, row in df.iterrows():
                            qlog = QLog(
                                upload_id=upload.id,
                                qlog_id=safe_str(row.get(col_mapping['qlog_id'])) if col_mapping.get('qlog_id') else None,
                                branch_code=safe_str(row.get(col_mapping['branch_code'])) if col_mapping.get('branch_code') else None,
                                qlog_type=safe_str(row.get(col_mapping['qlog_type'])) if col_mapping.get('qlog_type') else None,
                                qlog_typename=safe_str(row.get(col_mapping['qlog_typename'])) if col_mapping.get('qlog_typename') else None,
                                qlog_num=safe_int(row.get(col_mapping['qlog_num'])) if col_mapping.get('qlog_num') else None,
                                qlog_counter=safe_int(row.get(col_mapping['qlog_counter'])) if col_mapping.get('qlog_counter') else None,
                                qlog_user=safe_str(row.get(col_mapping['qlog_user'])) if col_mapping.get('qlog_user') else None,
                                qlog_date=parse_date(row.get(col_mapping['qlog_date'])) if col_mapping.get('qlog_date') else None,
                                qlog_time_in=safe_str(row.get(col_mapping['qlog_time_in'])) if col_mapping.get('qlog_time_in') else None,
                                qlog_time_call=safe_str(row.get(col_mapping['qlog_time_call'])) if col_mapping.get('qlog_time_call') else None,
                                qlog_time_end=safe_str(row.get(col_mapping['qlog_time_end'])) if col_mapping.get('qlog_time_end') else None,
                                wait_time_seconds=safe_int(row.get(col_mapping['wait_time_seconds'])) if col_mapping.get('wait_time_seconds') else None,
                                appointment_code=safe_str(row.get(col_mapping['appointment_code'])) if col_mapping.get('appointment_code') else None,
                                appointment_time=safe_str(row.get(col_mapping['appointment_time'])) if col_mapping.get('appointment_time') else None,
                                qlog_status=safe_str(row.get(col_mapping['qlog_status'])) if col_mapping.get('qlog_status') else None,
                                sla_status=safe_str(row.get(col_mapping['sla_status'])) if col_mapping.get('sla_status') else None,
                                sla_time_start=safe_str(row.get(col_mapping['sla_time_start'])) if col_mapping.get('sla_time_start') else None,
                                sla_time_end=safe_str(row.get(col_mapping['sla_time_end'])) if col_mapping.get('sla_time_end') else None,
                            )
                            qlogs.append(qlog)

                            if idx % 1000 == 0:
                                progress = 30 + int((idx / total_records) * 50)
                                progress_bar.progress(progress)
                                status_text.text(f"กำลังประมวลผล {idx:,}/{total_records:,}...")

                        status_text.text("กำลังบันทึกข้อมูล...")
                        progress_bar.progress(85)

                        session.bulk_save_objects(qlogs)
                        session.commit()

                        progress_bar.progress(100)
                        status_text.empty()

                        st.success("นำเข้าข้อมูล QLog สำเร็จ!")
                        st.markdown(f"""
                        **ผลการนำเข้า:**
                        - ไฟล์: `{uploaded_file.name}`
                        - จำนวน: **{total_records:,}** รายการ
                        - ช่วงวันที่: {min_date} ถึง {max_date}
                        """)
                        st.balloons()

                    except Exception as e:
                        progress_bar.empty()
                        status_text.empty()
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")
                        if 'session' in locals():
                            session.rollback()
                    finally:
                        if 'session' in locals():
                            session.close()

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {str(e)}")

# Show existing uploads
st.markdown("---")
st.markdown('<div class="section-header">📋 ข้อมูล QLog ที่มีในระบบ</div>', unsafe_allow_html=True)

session = get_session()
try:
    uploads = session.query(QLogUpload).order_by(QLogUpload.upload_date.desc()).all()

    if uploads:
        total_uploads = len(uploads)
        total_records = sum(u.total_records or 0 for u in uploads)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("จำนวนไฟล์", f"{total_uploads}")
        with col2:
            st.metric("QLog Records ทั้งหมด", f"{total_records:,}")

        st.markdown("---")

        data = []
        for u in uploads:
            data.append({
                'ID': u.id,
                'ชื่อไฟล์': u.filename[:40] + '...' if len(u.filename) > 40 else u.filename,
                'วันที่อัพโหลด': u.upload_date.strftime('%Y-%m-%d %H:%M') if u.upload_date else '-',
                'ช่วงวันที่': f"{u.date_from} - {u.date_to}" if u.date_from else '-',
                'จำนวน': u.total_records or 0,
            })

        df_uploads = pd.DataFrame(data)
        st.dataframe(df_uploads, use_container_width=True, hide_index=True)

        if can_delete():
            st.markdown("---")
            st.markdown("#### 🗑️ ลบข้อมูล QLog")

            col1, col2 = st.columns([3, 1])
            with col1:
                upload_to_delete = st.selectbox(
                    "เลือกไฟล์ที่ต้องการลบ",
                    options=[(u.id, u.filename) for u in uploads],
                    format_func=lambda x: x[1],
                    key="delete_qlog_upload"
                )

            with col2:
                st.write("")
                st.write("")
                if st.button("🗑️ ลบ", type="secondary", use_container_width=True, key="del_qlog"):
                    try:
                        upload_id = upload_to_delete[0]
                        upload = session.query(QLogUpload).filter(QLogUpload.id == upload_id).first()
                        if upload:
                            session.query(QLog).filter(QLog.upload_id == upload_id).delete()
                            session.delete(upload)
                            session.commit()
                            st.success(f"ลบข้อมูล {upload_to_delete[1]} สำเร็จ")
                            st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")
                        session.rollback()
    else:
        st.info("ยังไม่มีข้อมูล QLog ในระบบ - อัพโหลดไฟล์เพื่อเริ่มต้น")

finally:
    session.close()
