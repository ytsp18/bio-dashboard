"""Upload page for importing Appointment data files."""
import streamlit as st
import sys
import os
import tempfile
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session
from database.models import Appointment, AppointmentUpload
from utils.auth_check import require_login
from utils.theme import apply_theme
from auth import can_upload, can_delete

# Initialize database
init_db()

st.set_page_config(page_title="Upload Appointment - Bio Dashboard", page_icon="📅", layout="wide")

apply_theme()
require_login()

# Check upload permission
if not can_upload():
    st.error("คุณไม่มีสิทธิ์อัพโหลดไฟล์ (Role: Viewer)")
    st.info("กรุณาติดต่อ Admin เพื่อขอสิทธิ์ User หรือ Admin")
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
        border-left: 4px solid #F59E0B;
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
    <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #F59E0B, #D97706); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
        <span style="font-size: 24px;">📅</span>
    </div>
    <div>
        <h1 style="font-size: 1.75rem; font-weight: 700; color: #FAFAFA; margin: 0;">Upload ข้อมูลนัดหมาย</h1>
        <p style="font-size: 0.9rem; color: #9CA3AF; margin: 0;">นำเข้าข้อมูล Appointment สำหรับคำนวณ No-show</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Info box
st.markdown("""
<div class="info-box">
    <strong>ข้อมูลที่ต้องการ:</strong><br>
    ไฟล์ Excel/CSV ที่มีข้อมูลนัดหมายทั้งหมด (รวมคนที่ไม่มาด้วย)<br>
    <strong>คอลัมน์ที่จำเป็น:</strong> Appointment ID, วันนัด (Appt Date), รหัสศูนย์ (Branch Code)
</div>
""", unsafe_allow_html=True)

# Expected columns mapping
EXPECTED_COLUMNS = {
    'appointment_id': ['appointment_id', 'appt_id', 'รหัสนัดหมาย', 'เลขนัดหมาย'],
    'appt_date': ['appt_date', 'appointment_date', 'วันนัด', 'วันที่นัด', 'วันนัดหมาย'],
    'appt_time': ['appt_time', 'appointment_time', 'เวลานัด', 'เวลานัดหมาย'],
    'branch_code': ['branch_code', 'center_code', 'รหัสศูนย์', 'ศูนย์'],
    'branch_name': ['branch_name', 'center_name', 'ชื่อศูนย์'],
    'form_id': ['form_id', 'รหัสฟอร์ม'],
    'form_type': ['form_type', 'ประเภทฟอร์ม'],
    'card_id': ['card_id', 'เลขบัตร', 'รหัสบัตร'],
    'work_permit_no': ['work_permit_no', 'เลขใบอนุญาต'],
    'appt_status': ['appt_status', 'status', 'สถานะ', 'สถานะนัดหมาย'],
}


def find_column(df, target_col):
    """Find matching column name in dataframe."""
    possible_names = EXPECTED_COLUMNS.get(target_col, [target_col])
    for col in df.columns:
        col_lower = col.lower().strip()
        for name in possible_names:
            if col_lower == name.lower():
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


# Upload section
st.markdown('<div class="section-header">📁 เลือกไฟล์ Appointment</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "เลือกไฟล์ Excel หรือ CSV",
    type=['xlsx', 'xls', 'csv'],
    help="ไฟล์ข้อมูลนัดหมายทั้งหมด",
    label_visibility="collapsed"
)

if uploaded_file is not None:
    st.success(f"เลือกไฟล์: **{uploaded_file.name}**")

    # Read file
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            # Try reading different sheets
            xls = pd.ExcelFile(uploaded_file)
            sheet_names = xls.sheet_names

            if len(sheet_names) > 1:
                selected_sheet = st.selectbox("เลือก Sheet", sheet_names)
                df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
            else:
                df = pd.read_excel(uploaded_file)

        st.markdown('<div class="section-header">🔍 Preview ข้อมูล</div>', unsafe_allow_html=True)

        # Show columns found
        st.markdown("**คอลัมน์ที่พบในไฟล์:**")
        st.caption(", ".join(df.columns.tolist()))

        # Map columns
        st.markdown("---")
        st.markdown("#### 🔗 แมพคอลัมน์")

        col_mapping = {}
        cols = st.columns(3)

        with cols[0]:
            appt_id_col = find_column(df, 'appointment_id')
            col_mapping['appointment_id'] = st.selectbox(
                "Appointment ID *",
                options=[''] + df.columns.tolist(),
                index=df.columns.tolist().index(appt_id_col) + 1 if appt_id_col else 0
            )

        with cols[1]:
            appt_date_col = find_column(df, 'appt_date')
            col_mapping['appt_date'] = st.selectbox(
                "วันนัด (Appt Date) *",
                options=[''] + df.columns.tolist(),
                index=df.columns.tolist().index(appt_date_col) + 1 if appt_date_col else 0
            )

        with cols[2]:
            branch_col = find_column(df, 'branch_code')
            col_mapping['branch_code'] = st.selectbox(
                "รหัสศูนย์ (Branch Code) *",
                options=[''] + df.columns.tolist(),
                index=df.columns.tolist().index(branch_col) + 1 if branch_col else 0
            )

        # Optional columns
        with st.expander("คอลัมน์เพิ่มเติม (ไม่บังคับ)"):
            cols2 = st.columns(3)
            with cols2[0]:
                col_mapping['branch_name'] = st.selectbox(
                    "ชื่อศูนย์",
                    options=[''] + df.columns.tolist(),
                    index=0
                )
                col_mapping['appt_time'] = st.selectbox(
                    "เวลานัด",
                    options=[''] + df.columns.tolist(),
                    index=0
                )
            with cols2[1]:
                col_mapping['form_id'] = st.selectbox(
                    "Form ID",
                    options=[''] + df.columns.tolist(),
                    index=0
                )
                col_mapping['card_id'] = st.selectbox(
                    "Card ID",
                    options=[''] + df.columns.tolist(),
                    index=0
                )
            with cols2[2]:
                col_mapping['work_permit_no'] = st.selectbox(
                    "Work Permit No",
                    options=[''] + df.columns.tolist(),
                    index=0
                )
                col_mapping['appt_status'] = st.selectbox(
                    "สถานะนัดหมาย",
                    options=[''] + df.columns.tolist(),
                    index=0
                )

        # Validate required columns
        required_cols = ['appointment_id', 'appt_date', 'branch_code']
        missing_cols = [c for c in required_cols if not col_mapping.get(c)]

        if missing_cols:
            st.warning(f"กรุณาเลือกคอลัมน์ที่จำเป็น: {', '.join(missing_cols)}")
        else:
            # Show preview
            st.markdown("---")
            st.markdown("#### 📊 สรุปข้อมูล")

            total_records = len(df)

            # Parse dates for summary
            date_col = col_mapping['appt_date']
            df['_parsed_date'] = df[date_col].apply(parse_date)
            valid_dates = df['_parsed_date'].dropna()

            if len(valid_dates) > 0:
                min_date = valid_dates.min()
                max_date = valid_dates.max()
            else:
                min_date = max_date = None

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("จำนวนนัดหมาย", f"{total_records:,}")
            with col2:
                unique_appt = df[col_mapping['appointment_id']].nunique()
                st.metric("Unique Appointment", f"{unique_appt:,}")
            with col3:
                st.metric("วันที่เริ่มต้น", str(min_date) if min_date else "-")
            with col4:
                st.metric("วันที่สิ้นสุด", str(max_date) if max_date else "-")

            # Preview data
            st.markdown("---")
            st.markdown("#### 📋 ตัวอย่างข้อมูล")
            preview_cols = [c for c in col_mapping.values() if c]
            st.dataframe(df[preview_cols].head(10), use_container_width=True, hide_index=True)

            # Import button
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📥 นำเข้าข้อมูลนัดหมาย", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        session = get_session()

                        status_text.text("กำลังสร้าง Upload record...")
                        progress_bar.progress(10)

                        # Create upload record
                        upload = AppointmentUpload(
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

                        # Import appointments
                        appointments = []
                        for idx, row in df.iterrows():
                            appt = Appointment(
                                upload_id=upload.id,
                                appointment_id=str(row[col_mapping['appointment_id']]) if pd.notna(row[col_mapping['appointment_id']]) else None,
                                appt_date=parse_date(row[col_mapping['appt_date']]),
                                appt_time=str(row[col_mapping['appt_time']]) if col_mapping.get('appt_time') and pd.notna(row.get(col_mapping['appt_time'])) else None,
                                branch_code=str(row[col_mapping['branch_code']]) if pd.notna(row[col_mapping['branch_code']]) else None,
                                branch_name=str(row[col_mapping['branch_name']]) if col_mapping.get('branch_name') and pd.notna(row.get(col_mapping['branch_name'])) else None,
                                form_id=str(row[col_mapping['form_id']]) if col_mapping.get('form_id') and pd.notna(row.get(col_mapping['form_id'])) else None,
                                form_type=str(row[col_mapping['form_type']]) if col_mapping.get('form_type') and pd.notna(row.get(col_mapping['form_type'])) else None,
                                card_id=str(row[col_mapping['card_id']]) if col_mapping.get('card_id') and pd.notna(row.get(col_mapping['card_id'])) else None,
                                work_permit_no=str(row[col_mapping['work_permit_no']]) if col_mapping.get('work_permit_no') and pd.notna(row.get(col_mapping['work_permit_no'])) else None,
                                appt_status=str(row[col_mapping['appt_status']]) if col_mapping.get('appt_status') and pd.notna(row.get(col_mapping['appt_status'])) else None,
                            )
                            appointments.append(appt)

                            # Progress update
                            if idx % 1000 == 0:
                                progress = 30 + int((idx / total_records) * 50)
                                progress_bar.progress(progress)
                                status_text.text(f"กำลังประมวลผล {idx:,}/{total_records:,}...")

                        status_text.text("กำลังบันทึกข้อมูล...")
                        progress_bar.progress(85)

                        session.bulk_save_objects(appointments)
                        session.commit()

                        progress_bar.progress(100)
                        status_text.empty()

                        st.success("นำเข้าข้อมูลนัดหมายสำเร็จ!")

                        col1, col2 = st.columns(2)
                        with col1:
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

# Show existing appointment uploads
st.markdown("---")
st.markdown('<div class="section-header">📋 ข้อมูลนัดหมายที่มีในระบบ</div>', unsafe_allow_html=True)

session = get_session()
try:
    uploads = session.query(AppointmentUpload).order_by(AppointmentUpload.upload_date.desc()).all()

    if uploads:
        total_uploads = len(uploads)
        total_appts = sum(u.total_records or 0 for u in uploads)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("จำนวนไฟล์", f"{total_uploads}")
        with col2:
            st.metric("นัดหมายทั้งหมด", f"{total_appts:,}")

        st.markdown("---")

        # Table
        data = []
        for u in uploads:
            data.append({
                'ID': u.id,
                'ชื่อไฟล์': u.filename[:40] + '...' if len(u.filename) > 40 else u.filename,
                'วันที่อัพโหลด': u.upload_date.strftime('%Y-%m-%d %H:%M') if u.upload_date else '-',
                'ช่วงวันที่': f"{u.date_from} - {u.date_to}" if u.date_from else '-',
                'จำนวน': u.total_records or 0,
                'อัพโหลดโดย': u.uploaded_by or '-',
            })

        df_uploads = pd.DataFrame(data)
        st.dataframe(df_uploads, use_container_width=True, hide_index=True)

        # Delete option
        if can_delete():
            st.markdown("---")
            st.markdown("#### 🗑️ ลบข้อมูลนัดหมาย")

            col1, col2 = st.columns([3, 1])
            with col1:
                upload_to_delete = st.selectbox(
                    "เลือกไฟล์ที่ต้องการลบ",
                    options=[(u.id, u.filename) for u in uploads],
                    format_func=lambda x: x[1],
                    key="delete_appt_upload"
                )

            with col2:
                st.write("")
                st.write("")
                if st.button("🗑️ ลบ", type="secondary", use_container_width=True):
                    try:
                        upload_id = upload_to_delete[0]
                        upload = session.query(AppointmentUpload).filter(AppointmentUpload.id == upload_id).first()
                        if upload:
                            session.query(Appointment).filter(Appointment.upload_id == upload_id).delete()
                            session.delete(upload)
                            session.commit()
                            st.success(f"ลบข้อมูล {upload_to_delete[1]} สำเร็จ")
                            st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")
                        session.rollback()
    else:
        st.info("ยังไม่มีข้อมูลนัดหมายในระบบ - อัพโหลดไฟล์เพื่อเริ่มต้น")

finally:
    session.close()
