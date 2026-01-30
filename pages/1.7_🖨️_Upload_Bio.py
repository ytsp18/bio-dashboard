"""Upload page for importing Bio raw data files."""
import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session
from database.models import BioRecord, BioUpload
from utils.auth_check import require_login
from utils.theme import apply_theme
from auth import can_upload, can_delete

init_db()

st.set_page_config(page_title="Upload Bio - Bio Dashboard", page_icon="🖨️", layout="wide")

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
        border-left: 4px solid #3B82F6;
    }
    .info-box {
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-left: 4px solid #3B82F6;
        padding: 16px 20px;
        border-radius: 8px;
        color: #93C5FD;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown("""
<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #374151;">
    <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #3B82F6, #2563EB); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
        <span style="font-size: 24px;">🖨️</span>
    </div>
    <div>
        <h1 style="font-size: 1.75rem; font-weight: 700; color: #FAFAFA; margin: 0;">Upload ข้อมูล Bio</h1>
        <p style="font-size: 0.9rem; color: #9CA3AF; margin: 0;">นำเข้าข้อมูลการพิมพ์บัตรจากระบบ Bio</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    <strong>ไฟล์ที่รองรับ:</strong> Bio raw data (CSV/Excel)<br>
    <strong>ตัวอย่าง:</strong> ALL-OCT-2025-V1.csv, BIO_20251101-20251130.xlsx, 20260111_BIO.xlsx<br>
    <strong>คอลัมน์หลัก:</strong> Appointment ID, Serial Number, Print Status, Print Date, SLA Start/Stop
</div>
""", unsafe_allow_html=True)

# Column mapping
BIO_COLUMNS = {
    'appointment_id': ['Appointment ID', 'appointment_id', 'APPOINTMENT_ID'],
    'form_id': ['Form ID', 'form_id', 'FORM_ID'],
    'form_type': ['Form Type', 'form_type', 'FORM_TYPE'],
    'branch_code': ['Branch Code', 'branch_code', 'BRANCH_CODE'],
    'card_id': ['Card ID', 'card_id', 'CARD_ID'],
    'work_permit_no': ['Work Permit No', 'work_permit_no', 'WORK_PERMIT_NO'],
    'serial_number': ['Serial Number', 'serial_number', 'SERIAL_NUMBER'],
    'print_status': ['Print Status', 'print_status', 'PRINT_STATUS'],
    'reject_type': ['Reject Type', 'reject_type', 'REJECT_TYPE'],
    'operator': ['OS ID', 'os_id', 'OS_ID', 'Operator'],
    'print_date': ['Print Date', 'print_date', 'PRINT_DATE'],
    'sla_start': ['SLA Start', 'sla_start', 'SLA_START'],
    'sla_stop': ['SLA Stop', 'sla_stop', 'SLA_STOP'],
    'sla_duration': ['SLA Duration', 'sla_duration', 'SLA_DURATION'],
    'sla_confirm_type': ['SLA Confirm Type', 'sla_confirm_type'],
    'rate_service': ['Rate Service', 'rate_service'],
    'doe_id': ['DOE ID', 'doe_id'],
    'doe_comment': ['DOE Comment', 'doe_comment'],
    'emergency': ['Emergency', 'emergency'],
}


def find_column(df, target_col):
    """Find matching column name in dataframe."""
    possible_names = BIO_COLUMNS.get(target_col, [target_col])
    for col in df.columns:
        col_clean = str(col).strip()
        for name in possible_names:
            if col_clean.lower() == name.lower():
                return col
    return None


def parse_date(val):
    """Parse date from various formats."""
    if pd.isna(val):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date() if hasattr(val, 'date') else val
    try:
        # Try common formats
        val_str = str(val).strip()
        for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d']:
            try:
                return datetime.strptime(val_str[:10], fmt).date()
            except:
                continue
        return pd.to_datetime(val).date()
    except:
        return None


def parse_sla_duration(duration_str):
    """Convert SLA duration string to minutes."""
    if pd.isna(duration_str):
        return None
    try:
        duration_str = str(duration_str).strip()
        # Format: H:MM:SS or HH:MM:SS or 00:12:24
        match = re.match(r'(\d+):(\d+):(\d+)', duration_str)
        if match:
            hours, minutes, seconds = map(int, match.groups())
            return hours * 60 + minutes + seconds / 60
        return None
    except:
        return None


def safe_str(val):
    """Safely convert to string."""
    if pd.isna(val):
        return None
    return str(val).strip() if val else None


def safe_float(val):
    """Safely convert to float."""
    if pd.isna(val):
        return None
    try:
        return float(val)
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


# Upload section
st.markdown('<div class="section-header">📁 เลือกไฟล์ Bio</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "เลือกไฟล์ Excel หรือ CSV",
    type=['xlsx', 'xls', 'csv'],
    help="ไฟล์ Bio raw data",
    label_visibility="collapsed"
)

if uploaded_file is not None:
    st.success(f"เลือกไฟล์: **{uploaded_file.name}**")

    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            xls = pd.ExcelFile(uploaded_file)
            sheet_names = xls.sheet_names

            if len(sheet_names) > 1:
                selected_sheet = st.selectbox("เลือก Sheet", sheet_names)
                df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
            else:
                df = pd.read_excel(uploaded_file)

        st.markdown('<div class="section-header">🔍 Preview ข้อมูล</div>', unsafe_allow_html=True)

        st.markdown("**คอลัมน์ที่พบในไฟล์:**")
        st.caption(", ".join([str(c) for c in df.columns.tolist()]))

        # Auto-map columns
        col_mapping = {}
        for target_col in BIO_COLUMNS.keys():
            found = find_column(df, target_col)
            col_mapping[target_col] = found

        # Show mapping status
        st.markdown("---")
        st.markdown("#### 🔗 การแมพคอลัมน์อัตโนมัติ")

        mapped_count = sum(1 for v in col_mapping.values() if v)
        st.info(f"พบคอลัมน์ที่ตรงกัน: {mapped_count}/{len(BIO_COLUMNS)}")

        with st.expander("ดูการแมพคอลัมน์"):
            for target, found in col_mapping.items():
                if found:
                    st.text(f"✅ {target} → {found}")
                else:
                    st.text(f"❌ {target} → ไม่พบ")

        # Check required columns
        required = ['print_date', 'print_status', 'serial_number']
        missing = [c for c in required if not col_mapping.get(c)]

        if missing:
            st.warning(f"ไม่พบคอลัมน์ที่จำเป็น: {', '.join(missing)}")
        else:
            # Summary
            st.markdown("---")
            st.markdown("#### 📊 สรุปข้อมูล")

            total_records = len(df)

            # Parse dates
            date_col = col_mapping['print_date']
            df['_parsed_date'] = df[date_col].apply(parse_date)
            valid_dates = df['_parsed_date'].dropna()

            min_date = valid_dates.min() if len(valid_dates) > 0 else None
            max_date = valid_dates.max() if len(valid_dates) > 0 else None

            # Status counts
            status_col = col_mapping['print_status']
            status_counts = df[status_col].value_counts()
            good_count = status_counts.get('G', 0)
            bad_count = status_counts.get('B', 0)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("จำนวน Records", f"{total_records:,}")
            with col2:
                st.metric("บัตรดี (G)", f"{good_count:,}")
            with col3:
                st.metric("บัตรเสีย (B)", f"{bad_count:,}")
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
                if st.button("📥 นำเข้าข้อมูล Bio", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        session = get_session()

                        status_text.text("กำลังสร้าง Upload record...")
                        progress_bar.progress(10)

                        upload = BioUpload(
                            filename=uploaded_file.name,
                            date_from=min_date,
                            date_to=max_date,
                            total_records=total_records,
                            total_good=good_count,
                            total_bad=bad_count,
                            uploaded_by=st.session_state.get('username', 'unknown')
                        )
                        session.add(upload)
                        session.flush()

                        status_text.text("กำลังประมวลผลข้อมูล...")
                        progress_bar.progress(30)

                        bio_records = []
                        for idx, row in df.iterrows():
                            # Calculate SLA minutes
                            sla_duration = row.get(col_mapping['sla_duration']) if col_mapping.get('sla_duration') else None
                            sla_minutes = parse_sla_duration(sla_duration)

                            record = BioRecord(
                                upload_id=upload.id,
                                appointment_id=safe_str(row.get(col_mapping['appointment_id'])) if col_mapping.get('appointment_id') else None,
                                form_id=safe_str(row.get(col_mapping['form_id'])) if col_mapping.get('form_id') else None,
                                form_type=safe_str(row.get(col_mapping['form_type'])) if col_mapping.get('form_type') else None,
                                branch_code=safe_str(row.get(col_mapping['branch_code'])) if col_mapping.get('branch_code') else None,
                                card_id=safe_str(row.get(col_mapping['card_id'])) if col_mapping.get('card_id') else None,
                                work_permit_no=safe_str(row.get(col_mapping['work_permit_no'])) if col_mapping.get('work_permit_no') else None,
                                serial_number=safe_str(row.get(col_mapping['serial_number'])) if col_mapping.get('serial_number') else None,
                                print_status=safe_str(row.get(col_mapping['print_status'])) if col_mapping.get('print_status') else None,
                                reject_type=safe_str(row.get(col_mapping['reject_type'])) if col_mapping.get('reject_type') else None,
                                operator=safe_str(row.get(col_mapping['operator'])) if col_mapping.get('operator') else None,
                                print_date=parse_date(row.get(col_mapping['print_date'])) if col_mapping.get('print_date') else None,
                                sla_start=safe_str(row.get(col_mapping['sla_start'])) if col_mapping.get('sla_start') else None,
                                sla_stop=safe_str(row.get(col_mapping['sla_stop'])) if col_mapping.get('sla_stop') else None,
                                sla_duration=safe_str(sla_duration),
                                sla_minutes=sla_minutes,
                                sla_confirm_type=safe_str(row.get(col_mapping['sla_confirm_type'])) if col_mapping.get('sla_confirm_type') else None,
                                rate_service=safe_float(row.get(col_mapping['rate_service'])) if col_mapping.get('rate_service') else None,
                                doe_id=safe_str(row.get(col_mapping['doe_id'])) if col_mapping.get('doe_id') else None,
                                doe_comment=safe_str(row.get(col_mapping['doe_comment'])) if col_mapping.get('doe_comment') else None,
                                emergency=safe_int(row.get(col_mapping['emergency'])) if col_mapping.get('emergency') else None,
                            )
                            bio_records.append(record)

                            if idx % 1000 == 0:
                                progress = 30 + int((idx / total_records) * 50)
                                progress_bar.progress(progress)
                                status_text.text(f"กำลังประมวลผล {idx:,}/{total_records:,}...")

                        status_text.text("กำลังบันทึกข้อมูล...")
                        progress_bar.progress(85)

                        session.bulk_save_objects(bio_records)
                        session.commit()

                        progress_bar.progress(100)
                        status_text.empty()

                        st.success("นำเข้าข้อมูล Bio สำเร็จ!")
                        st.markdown(f"""
                        **ผลการนำเข้า:**
                        - ไฟล์: `{uploaded_file.name}`
                        - จำนวน: **{total_records:,}** รายการ
                        - บัตรดี (G): **{good_count:,}** | บัตรเสีย (B): **{bad_count:,}**
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
st.markdown('<div class="section-header">📋 ข้อมูล Bio ที่มีในระบบ</div>', unsafe_allow_html=True)

session = get_session()
try:
    uploads = session.query(BioUpload).order_by(BioUpload.upload_date.desc()).all()

    if uploads:
        total_uploads = len(uploads)
        total_records = sum(u.total_records or 0 for u in uploads)
        total_good = sum(u.total_good or 0 for u in uploads)
        total_bad = sum(u.total_bad or 0 for u in uploads)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("จำนวนไฟล์", f"{total_uploads}")
        with col2:
            st.metric("Records ทั้งหมด", f"{total_records:,}")
        with col3:
            st.metric("บัตรดี (G)", f"{total_good:,}")
        with col4:
            st.metric("บัตรเสีย (B)", f"{total_bad:,}")

        st.markdown("---")

        data = []
        for u in uploads:
            data.append({
                'ID': u.id,
                'ชื่อไฟล์': u.filename[:40] + '...' if len(u.filename) > 40 else u.filename,
                'วันที่อัพโหลด': u.upload_date.strftime('%Y-%m-%d %H:%M') if u.upload_date else '-',
                'ช่วงวันที่': f"{u.date_from} - {u.date_to}" if u.date_from else '-',
                'จำนวน': u.total_records or 0,
                'G': u.total_good or 0,
                'B': u.total_bad or 0,
            })

        df_uploads = pd.DataFrame(data)
        st.dataframe(df_uploads, use_container_width=True, hide_index=True)

        if can_delete():
            st.markdown("---")
            st.markdown("#### 🗑️ ลบข้อมูล Bio")

            col1, col2 = st.columns([3, 1])
            with col1:
                upload_to_delete = st.selectbox(
                    "เลือกไฟล์ที่ต้องการลบ",
                    options=[(u.id, u.filename) for u in uploads],
                    format_func=lambda x: x[1],
                    key="delete_bio_upload"
                )

            with col2:
                st.write("")
                st.write("")
                if st.button("🗑️ ลบ", type="secondary", use_container_width=True, key="del_bio"):
                    try:
                        upload_id = upload_to_delete[0]
                        upload = session.query(BioUpload).filter(BioUpload.id == upload_id).first()
                        if upload:
                            session.query(BioRecord).filter(BioRecord.upload_id == upload_id).delete()
                            session.delete(upload)
                            session.commit()
                            st.success(f"ลบข้อมูล {upload_to_delete[1]} สำเร็จ")
                            st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")
                        session.rollback()
    else:
        st.info("ยังไม่มีข้อมูล Bio ในระบบ - อัพโหลดไฟล์เพื่อเริ่มต้น")

finally:
    session.close()
