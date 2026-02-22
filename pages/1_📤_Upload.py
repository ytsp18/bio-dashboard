"""Upload page for importing all data files."""
import streamlit as st
import sys
import os
import tempfile
import pandas as pd
from datetime import datetime
import re
import gc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session
from database.models import (
    Report, Card, BadCard, CenterStat, AnomalySLA, WrongCenter, CompleteDiff, DeliveryCard,
    AppointmentUpload, Appointment, QLogUpload, QLog, BioUpload, BioRecord,
    CardDeliveryUpload, CardDeliveryRecord
)
from services.data_service import DataService
from services.excel_parser import ExcelParser
from utils.auth_check import require_login
from utils.theme import apply_theme
from auth import can_upload, can_delete

init_db()

st.set_page_config(page_title="Upload - Bio Dashboard", page_icon="📤", layout="wide")

apply_theme()
require_login()

if not can_upload():
    st.error("คุณไม่มีสิทธิ์อัพโหลดไฟล์ (Role: Viewer)")
    st.info("กรุณาติดต่อ Admin เพื่อขอสิทธิ์ User หรือ Admin")
    st.stop()

# Custom CSS
st.markdown("""
<style>
    .info-box {
        background: rgba(37, 99, 235, 0.08);
        border: 1px solid rgba(37, 99, 235, 0.2);
        border-left: 4px solid #2563eb;
        padding: 12px 16px;
        border-radius: 8px;
        color: #1d4ed8;
        margin: 10px 0;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown("""
<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #e5e7eb;">
    <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #3B82F6, #2563EB); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
        <span style="font-size: 24px;">📤</span>
    </div>
    <div>
        <h1 style="font-size: 1.75rem; font-weight: 700; color: #1f2937; margin: 0;">อัพโหลดข้อมูล</h1>
        <p style="font-size: 0.9rem; color: #6b7280; margin: 0;">นำเข้าข้อมูลเข้าสู่ระบบ Bio Dashboard</p>
    </div>
</div>
""", unsafe_allow_html=True)


# ==================== HELPER FUNCTIONS ====================

def parse_date(val):
    """Parse date from various formats."""
    if pd.isna(val):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date() if hasattr(val, 'date') else val
    try:
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
        match = re.match(r'(\d+):(\d+):(\d+)', duration_str)
        if match:
            hours, minutes, seconds = map(int, match.groups())
            return hours * 60 + minutes + seconds / 60
        return None
    except:
        return None


def safe_str(val):
    """Safely convert value to string, handling special characters."""
    if pd.isna(val):
        return None
    if val is None:
        return None
    result = str(val).strip()
    # Replace % with %% to avoid string formatting issues in some DB drivers
    # But only if the string contains % followed by a letter (formatting pattern)
    # Actually, leave % as is - the issue is elsewhere
    return result if result else None


def safe_float(val):
    if pd.isna(val):
        return None
    try:
        return float(val)
    except:
        return None


def safe_int(val):
    if pd.isna(val):
        return None
    try:
        return int(float(val))
    except:
        return None


def find_column(df, possible_names):
    """Find matching column name in dataframe."""
    for col in df.columns:
        col_clean = str(col).strip().lower()
        for name in possible_names:
            if col_clean == name.lower():
                return col
    return None


# ==================== MAIN TABS ====================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Bio Unified Report",
    "📅 Appointment",
    "⏱️ QLog",
    "🖨️ Bio Raw",
    "📦 Card Delivery"
])


# ==================== TAB 1: BIO UNIFIED REPORT ====================
with tab1:
    st.markdown('<div class="section-header">📊 Bio Unified Report</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="info-box">
        <strong>ไฟล์ที่รองรับ:</strong> Bio_unified_report_*.xlsx (ไฟล์ที่ join ข้อมูลแล้ว)
    </div>
    """, unsafe_allow_html=True)

    uploaded_unified = st.file_uploader(
        "เลือกไฟล์ Bio Unified Report",
        type=['xlsx'],
        key="unified_uploader"
    )

    if uploaded_unified is not None:
        st.success(f"เลือกไฟล์: **{uploaded_unified.name}**")

        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(uploaded_unified.getvalue())
            tmp_path = tmp_file.name

        try:
            parser = ExcelParser(tmp_path)
            parser.load()

            report_date = parser.extract_report_date()
            stats = parser.get_summary_stats()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("วันที่รายงาน", str(report_date))
            with col2:
                st.metric("จำนวนทั้งหมด", f"{stats['total_records']:,}")
            with col3:
                st.metric("บัตรดี (G)", f"{stats['good_cards']:,}")
            with col4:
                st.metric("บัตรเสีย (B)", f"{stats['bad_cards']:,}")

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📥 นำเข้า Bio Unified Report", type="primary", use_container_width=True, key="import_unified"):
                    progress = st.progress(0)
                    status = st.empty()

                    try:
                        def progress_cb(pct, msg):
                            progress.progress(min(pct, 100))
                            status.text(msg)

                        result = DataService.import_excel(
                            tmp_path,
                            original_filename=uploaded_unified.name,
                            progress_callback=progress_cb,
                        )
                        progress.progress(100)
                        status.empty()

                        # Show detailed import result
                        st.success(
                            f"นำเข้าสำเร็จ! บัตรดี: {result['total_good']:,} | "
                            f"บัตรเสีย: {result['total_bad']:,}\n\n"
                            f"cards: {result['cards_imported']:,} | "
                            f"bad_cards: {result['bad_cards_imported']:,} | "
                            f"centers: {result['centers_imported']:,} | "
                            f"SLA anomaly: {result['sla_anomalies_imported']:,} | "
                            f"wrong center: {result['wrong_center_imported']:,} | "
                            f"complete diff: {result['complete_diff_imported']:,} | "
                            f"delivery: {result['delivery_imported']:,}"
                        )
                        st.balloons()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")

            os.unlink(tmp_path)
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {str(e)}")

    # Show existing reports
    st.markdown("---")
    st.markdown("#### 📋 รายงานในระบบ")

    session = get_session()
    try:
        reports = session.query(Report).order_by(Report.report_date.desc()).all()
        if reports:
            data = [{
                'ID': r.id,
                'ชื่อไฟล์': r.filename[:40] + '...' if len(r.filename) > 40 else r.filename,
                'วันที่': r.report_date,
                'G': r.total_good or 0,
                'B': r.total_bad or 0,
            } for r in reports]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

            if can_delete():
                col1, col2 = st.columns([3, 1])
                with col1:
                    report_del = st.selectbox("เลือกรายงานที่ต้องการลบ", [(r.id, r.filename) for r in reports], format_func=lambda x: x[1], key="del_unified")
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ ลบ", key="btn_del_unified"):
                        rid = report_del[0]
                        session.query(Card).filter(Card.report_id == rid).delete()
                        session.query(BadCard).filter(BadCard.report_id == rid).delete()
                        session.query(CenterStat).filter(CenterStat.report_id == rid).delete()
                        session.query(AnomalySLA).filter(AnomalySLA.report_id == rid).delete()
                        session.query(WrongCenter).filter(WrongCenter.report_id == rid).delete()
                        session.query(CompleteDiff).filter(CompleteDiff.report_id == rid).delete()
                        session.query(DeliveryCard).filter(DeliveryCard.report_id == rid).delete()
                        session.query(Report).filter(Report.id == rid).delete()
                        session.commit()
                        st.success("ลบสำเร็จ!")
                        st.rerun()
        else:
            st.info("ยังไม่มีรายงานในระบบ")
    finally:
        session.close()


# ==================== TAB 2: APPOINTMENT ====================
with tab2:
    st.markdown('<div class="section-header section-header-orange">📅 ข้อมูลนัดหมาย (Appointment)</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="info-box">
        <strong>ไฟล์ที่รองรับ:</strong> appointment-*.csv<br>
        <strong>คอลัมน์หลัก:</strong> APPOINTMENT_CODE, APPOINTMENT_DATE, BRANCH_ID, STATUS
    </div>
    """, unsafe_allow_html=True)

    APPT_COLUMNS = {
        'appointment_id': ['APPOINTMENT_CODE', 'appointment_code', 'appointment_id'],
        'appt_date': ['APPOINTMENT_DATE', 'appointment_date', 'appt_date'],
        'branch_code': ['BRANCH_ID', 'branch_id', 'branch_code'],
        'appt_status': ['STATUS', 'status', 'appt_status'],
        'form_id': ['FORM_ID', 'form_id'],
        'form_type': ['FORM_TYPE', 'form_type'],
        'work_permit_no': ['STAY_PERMIS_NO', 'work_permit_no'],
    }

    uploaded_appt = st.file_uploader("เลือกไฟล์ Appointment", type=['csv', 'xlsx'], key="appt_uploader")

    if uploaded_appt is not None:
        st.success(f"เลือกไฟล์: **{uploaded_appt.name}**")

        try:
            if uploaded_appt.name.endswith('.csv'):
                # Try Thai encodings first (windows-874/tis-620), then others
                encodings = ['utf-8', 'utf-8-sig', 'windows-874', 'tis-620', 'cp874', 'cp1252', 'latin1']
                df = None
                for enc in encodings:
                    try:
                        uploaded_appt.seek(0)
                        # Read header first to get expected column count
                        header_line = uploaded_appt.readline().decode(enc).strip()
                        expected_cols = len(header_line.split(','))
                        uploaded_appt.seek(0)

                        # Read CSV with index_col=False to prevent pandas from using first column as index
                        # low_memory=False for large files to ensure consistent dtype inference
                        import warnings
                        with warnings.catch_warnings():
                            warnings.filterwarnings('ignore', message='Length of header or names does not match')
                            df = pd.read_csv(uploaded_appt, index_col=False, encoding=enc, low_memory=False)

                        # Verify columns are correct - if APPOINTMENT_CODE is not first column, there's a problem
                        if len(df.columns) > 0 and df.columns[0] != 'APPOINTMENT_CODE':
                            uploaded_appt.seek(0)
                            df = pd.read_csv(uploaded_appt, encoding=enc, low_memory=False)
                            if df.index.dtype == 'object':
                                df = df.reset_index()
                                df.columns = header_line.split(',') + ['_extra'] if len(df.columns) > expected_cols else df.columns

                        # Verify encoding by checking for valid Thai characters
                        sample_text = df.astype(str).values.flatten()[:100]
                        sample_str = ' '.join(str(x) for x in sample_text)
                        has_thai = any('\u0e00' <= c <= '\u0e7f' for c in sample_str)
                        has_garbage = any(ord(c) > 127 and not ('\u0e00' <= c <= '\u0e7f') for c in sample_str if c not in ' \n\t')
                        if has_thai or not has_garbage:
                            break
                        df = None
                    except (UnicodeDecodeError, LookupError):
                        continue
                if df is None:
                    st.error("ไม่สามารถอ่านไฟล์ได้ - กรุณาตรวจสอบ encoding ของไฟล์")
                    st.stop()
            else:
                df = pd.read_excel(uploaded_appt)

            # Auto-map columns
            col_map = {}
            for target, names in APPT_COLUMNS.items():
                col_map[target] = find_column(df, names)

            # Debug: Show column mapping
            with st.expander("🔍 Column Mapping Debug"):
                st.write("**Columns in file:**", list(df.columns))
                st.write("**Mapped columns:**", {k: v for k, v in col_map.items() if v is not None})
                st.write("**Missing:**", [k for k, v in col_map.items() if v is None])

            # Summary
            total = len(df)
            if col_map['appt_date']:
                df['_date'] = df[col_map['appt_date']].apply(parse_date)
                valid_dates = df['_date'].dropna()
                min_date = valid_dates.min() if len(valid_dates) > 0 else None
                max_date = valid_dates.max() if len(valid_dates) > 0 else None
                # Convert pandas NaT to None
                if pd.isna(min_date):
                    min_date = None
                if pd.isna(max_date):
                    max_date = None
            else:
                min_date = max_date = None

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("จำนวน Records", f"{total:,}")
            with col2:
                st.metric("วันที่เริ่ม", str(min_date) if min_date else "-")
            with col3:
                st.metric("วันที่สิ้นสุด", str(max_date) if max_date else "-")

            # Preview
            st.dataframe(df.head(5), use_container_width=True, hide_index=True)

            # Smart duplicate check - classify into new/changed/skip
            session = get_session()
            new_count = 0
            changed_count = 0
            skip_count = 0
            importable_count = 0
            has_classification = False
            try:
                if col_map.get('appointment_id'):
                    from sqlalchemy import text

                    # Extract file data for comparison
                    file_appt_ids_col = df[col_map['appointment_id']].astype(str).str.strip()
                    file_appt_ids_unique = file_appt_ids_col.unique().tolist()

                    # Query DB for existing (appointment_id, appt_date, branch_code)
                    existing_appt_ids = set()
                    existing_composites = set()
                    batch_size = 1000
                    for i in range(0, len(file_appt_ids_unique), batch_size):
                        batch = file_appt_ids_unique[i:i+batch_size]
                        result = session.execute(
                            text("SELECT appointment_id, appt_date, branch_code FROM appointments WHERE appointment_id IN :appts"),
                            {"appts": tuple(batch) if len(batch) > 1 else (batch[0], batch[0])}
                        )
                        for row in result:
                            appt_id = str(row[0]).strip()
                            existing_appt_ids.add(appt_id)
                            date_str = str(row[1]) if row[1] else 'None'
                            bc_str = str(row[2]).strip() if row[2] else 'None'
                            existing_composites.add(f"{appt_id}|{date_str}|{bc_str}")

                    # Vectorized classification
                    can_compare = col_map.get('appt_date') and col_map.get('branch_code')

                    if can_compare:
                        file_dates = pd.to_datetime(df[col_map['appt_date']], errors='coerce').dt.date.astype(str)
                        file_branches = df[col_map['branch_code']].astype(str).str.strip().fillna('None').replace({'nan': 'None', '': 'None'})
                        file_composites = file_appt_ids_col + '|' + file_dates + '|' + file_branches

                        is_new = ~file_appt_ids_col.isin(existing_appt_ids)
                        is_exact_match = file_composites.isin(existing_composites)

                        df['_class'] = 'changed'
                        df.loc[is_new, '_class'] = 'new'
                        df.loc[is_exact_match, '_class'] = 'skip'
                    else:
                        # Fallback: no date/branch columns -> skip all duplicates
                        is_new = ~file_appt_ids_col.isin(existing_appt_ids)
                        df['_class'] = 'skip'
                        df.loc[is_new, '_class'] = 'new'
                        if not can_compare and len(existing_appt_ids) > 0:
                            st.warning("⚠️ ไม่พบคอลัมน์วันนัด/สาขา ไม่สามารถตรวจสอบการเปลี่ยนแปลงได้ — รายการซ้ำจะถูกข้ามทั้งหมด")

                    new_count = int((df['_class'] == 'new').sum())
                    changed_count = int((df['_class'] == 'changed').sum())
                    skip_count = int((df['_class'] == 'skip').sum())
                    importable_count = new_count + changed_count
                    has_classification = True

                    # Display summary
                    st.markdown("##### 📊 สรุปการตรวจสอบข้อมูลซ้ำ")
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.metric("🆕 รายการใหม่", f"{new_count:,}")
                    with c2:
                        st.metric("🔄 เปลี่ยนวัน/สาขา", f"{changed_count:,}")
                    with c3:
                        st.metric("⏭️ ข้ามซ้ำ", f"{skip_count:,}")
                    with c4:
                        st.metric("📥 จะนำเข้า", f"{importable_count:,}")

                    if changed_count > 0:
                        st.info(f"ℹ️ พบ {changed_count:,} รายการที่เปลี่ยนวันนัด/สาขา — จะนำเข้าเป็น record ใหม่เพื่อเก็บประวัติ")
                    if skip_count > 0 and importable_count > 0:
                        st.warning(f"⚠️ {skip_count:,} รายการซ้ำ (วันนัด+สาขาเหมือนเดิม) จะถูกข้าม")
                    if importable_count == 0:
                        st.error("❌ ทุกรายการมีในฐานข้อมูลแล้ว ไม่มีรายการใหม่ที่จะนำเข้า")
            finally:
                session.close()

            # Import
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                no_importable = has_classification and importable_count == 0
                if st.button("📥 นำเข้า Appointment", type="primary", use_container_width=True, key="import_appt", disabled=no_importable):
                    progress = st.progress(0)
                    status_text = st.empty()
                    session = get_session()
                    try:
                        # Filter out skip rows if classification was done
                        if has_classification and '_class' in df.columns:
                            df_to_import = df[df['_class'].isin(['new', 'changed'])].copy()
                        else:
                            df_to_import = df

                        actual_total = len(df_to_import)

                        status_text.text("กำลังสร้าง upload record...")
                        upload = AppointmentUpload(
                            filename=uploaded_appt.name,
                            date_from=min_date, date_to=max_date,
                            total_records=actual_total,
                            uploaded_by=st.session_state.get('username', 'unknown')
                        )
                        session.add(upload)
                        session.flush()
                        upload_id = upload.id
                        progress.progress(10)

                        # Prepare data from filtered rows
                        status_text.text("กำลังเตรียมข้อมูล...")
                        import_df = pd.DataFrame({
                            'upload_id': upload_id,
                            'appointment_id': df_to_import[col_map['appointment_id']].astype(str).str.strip() if col_map.get('appointment_id') else None,
                            'appt_date': pd.to_datetime(df_to_import[col_map['appt_date']], errors='coerce') if col_map.get('appt_date') else None,
                            'branch_code': df_to_import[col_map['branch_code']].astype(str).str.strip() if col_map.get('branch_code') else None,
                            'appt_status': df_to_import[col_map['appt_status']].astype(str).str.strip() if col_map.get('appt_status') else None,
                            'form_id': df_to_import[col_map['form_id']].astype(str).str.strip() if col_map.get('form_id') else None,
                            'form_type': df_to_import[col_map['form_type']].astype(str).str.strip() if col_map.get('form_type') else None,
                            'work_permit_no': df_to_import[col_map['work_permit_no']].astype(str).str.strip() if col_map.get('work_permit_no') else None,
                        })
                        import_df = import_df.replace({'nan': None, 'None': None, '': None})
                        progress.progress(30)

                        # Use PostgreSQL COPY for maximum speed (fastest method)
                        status_text.text("กำลังนำเข้าข้อมูล...")
                        from database.connection import is_sqlite
                        from io import StringIO

                        total_records = len(import_df)

                        if is_sqlite:
                            # SQLite: use pandas to_sql (fast enough for local)
                            import_df.to_sql('appointments', session.bind, if_exists='append', index=False, method='multi', chunksize=5000)
                            progress.progress(95)
                        else:
                            # PostgreSQL: use COPY protocol (fastest possible method)
                            conn = session.connection().connection
                            cursor = conn.cursor()

                            columns = ['upload_id', 'appointment_id', 'appt_date', 'branch_code', 'appt_status', 'form_id', 'form_type', 'work_permit_no']

                            # Convert DataFrame to CSV string buffer
                            status_text.text("กำลังเตรียมข้อมูลสำหรับ COPY...")
                            buffer = StringIO()
                            import_df[columns].to_csv(buffer, index=False, header=False, na_rep='\\N')
                            buffer.seek(0)
                            progress.progress(50)

                            # Use COPY command (2-5x faster than execute_values)
                            status_text.text(f"กำลังนำเข้า {total_records:,} รายการด้วย COPY...")
                            cursor.copy_expert("""
                                COPY appointments (upload_id, appointment_id, appt_date, branch_code, appt_status, form_id, form_type, work_permit_no)
                                FROM STDIN WITH (FORMAT CSV, NULL '\\N')
                            """, buffer)
                            progress.progress(95)

                        session.commit()

                        # Free memory
                        del import_df, df_to_import, df
                        gc.collect()
                        progress.progress(100)
                        status_text.empty()

                        # Summary success message
                        msg_parts = []
                        if new_count > 0:
                            msg_parts.append(f"ใหม่ {new_count:,}")
                        if changed_count > 0:
                            msg_parts.append(f"อัปเดต {changed_count:,}")
                        if skip_count > 0:
                            msg_parts.append(f"ข้าม {skip_count:,}")
                        detail = " | ".join(msg_parts) if msg_parts else ""
                        st.success(f"นำเข้าสำเร็จ! {actual_total:,} รายการ ({detail})")
                        st.balloons()
                    except Exception as e:
                        session.rollback()
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")
                    finally:
                        session.close()

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {str(e)}")

    # Show existing
    st.markdown("---")
    st.markdown("#### 📋 ข้อมูล Appointment ในระบบ")
    session = get_session()
    try:
        uploads = session.query(AppointmentUpload).order_by(AppointmentUpload.upload_date.desc()).all()
        if uploads:
            data = [{'ID': u.id, 'ชื่อไฟล์': u.filename[:30], 'ช่วงวันที่': f"{u.date_from} - {u.date_to}", 'จำนวน': u.total_records or 0} for u in uploads]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

            if can_delete():
                col1, col2 = st.columns([3, 1])
                with col1:
                    sel = st.selectbox("เลือกไฟล์ที่ต้องการลบ", [(u.id, u.filename) for u in uploads], format_func=lambda x: x[1], key="del_appt")
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ ลบ", key="btn_del_appt"):
                        session.query(Appointment).filter(Appointment.upload_id == sel[0]).delete()
                        session.query(AppointmentUpload).filter(AppointmentUpload.id == sel[0]).delete()
                        session.commit()
                        st.success("ลบสำเร็จ!")
                        st.rerun()
        else:
            st.info("ยังไม่มีข้อมูล Appointment")
    finally:
        session.close()


# ==================== TAB 3: QLOG ====================
with tab3:
    st.markdown('<div class="section-header section-header-green">⏱️ ข้อมูล QLog (Check-in)</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="info-box">
        <strong>ไฟล์ที่รองรับ:</strong> qlog-*.csv<br>
        <strong>คอลัมน์หลัก:</strong> QLOG_ID, BRANCH_ID, QLOG_TIMEIN, APPOINTMENT_CODE, QLOG_STATUS
    </div>
    """, unsafe_allow_html=True)

    QLOG_COLUMNS = {
        'qlog_id': ['QLOG_ID'],
        'branch_code': ['BRANCH_ID'],
        'qlog_type': ['QLOG_TYPE'],
        'qlog_typename': ['QLOG_TYPENAME'],
        'qlog_num': ['QLOG_NUM'],
        'qlog_counter': ['QLOG_COUNTER'],
        'qlog_user': ['QLOG_USER'],
        'qlog_date': ['QLOG_DATE', 'QLOG_DATEIN'],
        'qlog_time_in': ['QLOG_TIMEIN'],
        'qlog_time_call': ['QLOG_TIMECALL'],
        'qlog_time_end': ['QLOG_TIMEEND'],
        'qlog_train_time': ['QLOG_TRAIN_TIME'],
        'wait_time_seconds': ['QLOG_COUNTWAIT'],
        'appointment_code': ['APPOINTMENT_CODE'],
        'appointment_time': ['APPOINTMENT_TIME'],
        'qlog_status': ['QLOG_STATUS'],
        'sla_status': ['SLA_STATUS'],
        'sla_time_start': ['SLA_TIMESTART'],
        'sla_time_end': ['SLA_TIMEEND'],
    }

    uploaded_qlog = st.file_uploader("เลือกไฟล์ QLog", type=['csv'], key="qlog_uploader")

    if uploaded_qlog is not None:
        st.success(f"เลือกไฟล์: **{uploaded_qlog.name}**")

        try:
            # Try Thai encodings first (windows-874/tis-620), then others
            encodings = ['utf-8', 'utf-8-sig', 'windows-874', 'tis-620', 'cp874', 'cp1252', 'latin1']
            df = None
            for enc in encodings:
                try:
                    uploaded_qlog.seek(0)
                    df = pd.read_csv(uploaded_qlog, encoding=enc, low_memory=False)
                    # Verify encoding by checking for valid Thai characters
                    sample_text = df.astype(str).values.flatten()[:100]
                    sample_str = ' '.join(str(x) for x in sample_text)
                    has_thai = any('\u0e00' <= c <= '\u0e7f' for c in sample_str)
                    has_garbage = any(ord(c) > 127 and not ('\u0e00' <= c <= '\u0e7f') for c in sample_str if c not in ' \n\t')
                    if has_thai or not has_garbage:
                        break
                    df = None
                except (UnicodeDecodeError, LookupError):
                    continue
            if df is None:
                st.error("ไม่สามารถอ่านไฟล์ได้ - กรุณาตรวจสอบ encoding ของไฟล์")
                st.stop()

            col_map = {}
            for target, names in QLOG_COLUMNS.items():
                col_map[target] = find_column(df, names)

            total = len(df)
            if col_map['qlog_date']:
                df['_date'] = df[col_map['qlog_date']].apply(parse_date)
                valid_dates = df['_date'].dropna()
                min_date = valid_dates.min() if len(valid_dates) > 0 else None
                max_date = valid_dates.max() if len(valid_dates) > 0 else None
                if pd.isna(min_date):
                    min_date = None
                if pd.isna(max_date):
                    max_date = None
            else:
                min_date = max_date = None

            # Status counts
            status_col = col_map.get('qlog_status')
            if status_col:
                status_counts = df[status_col].value_counts()
                served = status_counts.get('S', 0)
            else:
                served = 0

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("จำนวน Records", f"{total:,}")
            with col2:
                st.metric("Served (S)", f"{served:,}")
            with col3:
                st.metric("วันที่เริ่ม", str(min_date) if min_date else "-")
            with col4:
                st.metric("วันที่สิ้นสุด", str(max_date) if max_date else "-")

            st.dataframe(df.head(5), use_container_width=True, hide_index=True)

            # Note: QLog ID can be duplicated (same person can check-in multiple times)
            # So we don't block import for duplicates

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📥 นำเข้า QLog", type="primary", use_container_width=True, key="import_qlog"):
                    progress = st.progress(0)
                    status_text = st.empty()
                    session = get_session()
                    try:
                        status_text.text("กำลังสร้าง upload record...")
                        upload = QLogUpload(
                            filename=uploaded_qlog.name,
                            date_from=min_date, date_to=max_date,
                            total_records=total,
                            uploaded_by=st.session_state.get('username', 'unknown')
                        )
                        session.add(upload)
                        session.flush()
                        upload_id = upload.id
                        progress.progress(10)

                        # Prepare data - simple and fast
                        status_text.text("กำลังเตรียมข้อมูล...")
                        import_df = pd.DataFrame({
                            'upload_id': upload_id,
                            'qlog_id': df[col_map['qlog_id']].astype(str).str.strip() if col_map.get('qlog_id') else None,
                            'branch_code': df[col_map['branch_code']].astype(str).str.strip() if col_map.get('branch_code') else None,
                            'qlog_type': df[col_map['qlog_type']].astype(str).str.strip() if col_map.get('qlog_type') else None,
                            'qlog_typename': df[col_map['qlog_typename']].astype(str).str.strip() if col_map.get('qlog_typename') else None,
                            'qlog_num': pd.to_numeric(df[col_map['qlog_num']], errors='coerce') if col_map.get('qlog_num') else None,
                            'qlog_counter': pd.to_numeric(df[col_map['qlog_counter']], errors='coerce') if col_map.get('qlog_counter') else None,
                            'qlog_user': df[col_map['qlog_user']].astype(str).str.strip() if col_map.get('qlog_user') else None,
                            'qlog_date': pd.to_datetime(df[col_map['qlog_date']], errors='coerce') if col_map.get('qlog_date') else None,
                            'qlog_time_in': df[col_map['qlog_time_in']].astype(str).str.strip() if col_map.get('qlog_time_in') else None,
                            'qlog_time_call': df[col_map['qlog_time_call']].astype(str).str.strip() if col_map.get('qlog_time_call') else None,
                            'qlog_time_end': df[col_map['qlog_time_end']].astype(str).str.strip() if col_map.get('qlog_time_end') else None,
                            'qlog_train_time': df[col_map['qlog_train_time']].astype(str).str.strip() if col_map.get('qlog_train_time') else None,
                            'wait_time_seconds': pd.to_numeric(df[col_map['wait_time_seconds']], errors='coerce') if col_map.get('wait_time_seconds') else None,
                            'appointment_code': df[col_map['appointment_code']].astype(str).str.strip() if col_map.get('appointment_code') else None,
                            'appointment_time': df[col_map['appointment_time']].astype(str).str.strip() if col_map.get('appointment_time') else None,
                            'qlog_status': df[col_map['qlog_status']].astype(str).str.strip() if col_map.get('qlog_status') else None,
                            'sla_status': df[col_map['sla_status']].astype(str).str.strip() if col_map.get('sla_status') else None,
                            'sla_time_start': df[col_map['sla_time_start']].astype(str).str.strip() if col_map.get('sla_time_start') else None,
                            'sla_time_end': df[col_map['sla_time_end']].astype(str).str.strip() if col_map.get('sla_time_end') else None,
                        })
                        import_df = import_df.replace({'nan': None, 'None': None, '': None})
                        progress.progress(30)

                        # Use PostgreSQL COPY for maximum speed
                        status_text.text("กำลังนำเข้าข้อมูล...")
                        from database.connection import is_sqlite
                        from io import StringIO

                        total_records = len(import_df)

                        if is_sqlite:
                            import_df.to_sql('qlogs', session.bind, if_exists='append', index=False, method='multi', chunksize=5000)
                            progress.progress(95)
                        else:
                            # PostgreSQL: use COPY protocol (fastest possible method)
                            conn = session.connection().connection
                            cursor = conn.cursor()

                            columns = ['upload_id', 'qlog_id', 'branch_code', 'qlog_type', 'qlog_typename',
                                       'qlog_num', 'qlog_counter', 'qlog_user',
                                       'qlog_date', 'qlog_time_in', 'qlog_time_call', 'qlog_time_end', 'qlog_train_time',
                                       'wait_time_seconds', 'appointment_code', 'appointment_time',
                                       'qlog_status', 'sla_status', 'sla_time_start', 'sla_time_end']

                            # Convert DataFrame to CSV string buffer
                            status_text.text("กำลังเตรียมข้อมูลสำหรับ COPY...")
                            buffer = StringIO()
                            import_df[columns].to_csv(buffer, index=False, header=False, na_rep='\\N')
                            buffer.seek(0)
                            progress.progress(50)

                            # Use COPY command
                            status_text.text(f"กำลังนำเข้า {total_records:,} รายการด้วย COPY...")
                            cursor.copy_expert("""
                                COPY qlogs (upload_id, qlog_id, branch_code, qlog_type, qlog_typename,
                                    qlog_num, qlog_counter, qlog_user,
                                    qlog_date, qlog_time_in, qlog_time_call, qlog_time_end, qlog_train_time,
                                    wait_time_seconds, appointment_code, appointment_time,
                                    qlog_status, sla_status, sla_time_start, sla_time_end)
                                FROM STDIN WITH (FORMAT CSV, NULL '\\N')
                            """, buffer)
                            progress.progress(95)

                        session.commit()

                        # Free memory
                        del import_df, df
                        gc.collect()
                        progress.progress(100)
                        status_text.empty()
                        st.success(f"นำเข้าสำเร็จ! {total:,} รายการ")
                        st.balloons()
                    except Exception as e:
                        session.rollback()
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")
                    finally:
                        session.close()

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {str(e)}")

    # Show existing
    st.markdown("---")
    st.markdown("#### 📋 ข้อมูล QLog ในระบบ")
    session = get_session()
    try:
        uploads = session.query(QLogUpload).order_by(QLogUpload.upload_date.desc()).all()
        if uploads:
            data = [{'ID': u.id, 'ชื่อไฟล์': u.filename[:30], 'ช่วงวันที่': f"{u.date_from} - {u.date_to}", 'จำนวน': u.total_records or 0} for u in uploads]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

            if can_delete():
                col1, col2 = st.columns([3, 1])
                with col1:
                    sel = st.selectbox("เลือกไฟล์ที่ต้องการลบ", [(u.id, u.filename) for u in uploads], format_func=lambda x: x[1], key="del_qlog")
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ ลบ", key="btn_del_qlog"):
                        session.query(QLog).filter(QLog.upload_id == sel[0]).delete()
                        session.query(QLogUpload).filter(QLogUpload.id == sel[0]).delete()
                        session.commit()
                        st.success("ลบสำเร็จ!")
                        st.rerun()
        else:
            st.info("ยังไม่มีข้อมูล QLog")
    finally:
        session.close()


# ==================== TAB 4: BIO RAW ====================
with tab4:
    st.markdown('<div class="section-header section-header-purple">🖨️ ข้อมูล Bio Raw (Card Print)</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="info-box">
        <strong>ไฟล์ที่รองรับ:</strong> ALL-*-*.csv, BIO_*.xlsx, *_BIO.xlsx<br>
        <strong>คอลัมน์หลัก:</strong> Appointment ID, Serial Number, Print Status, Print Date
    </div>
    """, unsafe_allow_html=True)

    BIO_COLUMNS = {
        'appointment_id': ['Appointment ID', 'appointment_id'],
        'form_id': ['Form ID', 'form_id'],
        'form_type': ['Form Type', 'form_type'],
        'branch_code': ['Branch Code', 'branch_code'],
        'card_id': ['Card ID', 'card_id'],
        'work_permit_no': ['Work Permit No', 'work_permit_no'],
        'serial_number': ['Serial Number', 'serial_number'],
        'print_status': ['Print Status', 'print_status'],
        'reject_type': ['Reject Type', 'reject_type'],
        'operator': ['OS ID', 'os_id', 'Operator'],
        'print_date': ['Print Date', 'print_date'],
        'sla_start': ['SLA Start', 'sla_start'],
        'sla_stop': ['SLA Stop', 'sla_stop'],
        'sla_duration': ['SLA Duration', 'sla_duration'],
        'emergency': ['Emergency', 'emergency'],
    }

    uploaded_bio = st.file_uploader("เลือกไฟล์ Bio Raw", type=['csv', 'xlsx'], key="bio_uploader")

    if uploaded_bio is not None:
        st.success(f"เลือกไฟล์: **{uploaded_bio.name}**")

        try:
            if uploaded_bio.name.endswith('.csv'):
                # Try Thai encodings first, then others
                # windows-874/tis-620 are Thai encodings that should be tried before cp1252/latin1
                encodings = ['utf-8', 'utf-8-sig', 'windows-874', 'tis-620', 'cp874', 'cp1252', 'latin1']
                df = None
                for enc in encodings:
                    try:
                        uploaded_bio.seek(0)
                        df = pd.read_csv(uploaded_bio, encoding=enc, low_memory=False)
                        # Verify encoding is correct by checking for Thai characters
                        # If data contains Thai, valid encoding should have Thai unicode range
                        sample_text = df.astype(str).values.flatten()[:100]
                        sample_str = ' '.join(str(x) for x in sample_text)
                        # Check if contains valid Thai characters (unicode range 0E00-0E7F)
                        has_thai = any('\u0e00' <= c <= '\u0e7f' for c in sample_str)
                        has_garbage = any(ord(c) > 127 and not ('\u0e00' <= c <= '\u0e7f') for c in sample_str if c not in ' \n\t')
                        # If we found Thai chars or no high-byte chars at all, this encoding is good
                        if has_thai or not has_garbage:
                            break
                        # Otherwise try next encoding
                        df = None
                    except (UnicodeDecodeError, LookupError):
                        continue
                if df is None:
                    st.error("ไม่สามารถอ่านไฟล์ได้ - กรุณาตรวจสอบ encoding ของไฟล์")
                    st.stop()
            else:
                df = pd.read_excel(uploaded_bio)

            col_map = {}
            for target, names in BIO_COLUMNS.items():
                col_map[target] = find_column(df, names)

            total = len(df)
            if col_map['print_date']:
                df['_date'] = df[col_map['print_date']].apply(parse_date)
                valid_dates = df['_date'].dropna()
                min_date = valid_dates.min() if len(valid_dates) > 0 else None
                max_date = valid_dates.max() if len(valid_dates) > 0 else None
                if pd.isna(min_date):
                    min_date = None
                if pd.isna(max_date):
                    max_date = None
            else:
                min_date = max_date = None

            # Status counts - convert to int to avoid numpy.int64 issues with psycopg2
            status_col = col_map.get('print_status')
            if status_col:
                status_counts = df[status_col].value_counts()
                good = int(status_counts.get('G', 0))
                bad = int(status_counts.get('B', 0))
            else:
                good = bad = 0

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("จำนวน Records", f"{total:,}")
            with col2:
                st.metric("บัตรดี (G)", f"{good:,}")
            with col3:
                st.metric("บัตรเสีย (B)", f"{bad:,}")
            with col4:
                st.metric("ช่วงวันที่", f"{min_date} - {max_date}" if min_date else "-")

            st.dataframe(df.head(5), use_container_width=True, hide_index=True)

            # Check for duplicates before import (warning only)
            # Bio Raw allows same serial with different status (G->B or B->G changes)
            session = get_session()
            try:
                if col_map.get('serial_number') and col_map.get('print_status'):
                    from sqlalchemy import text
                    # Create composite key for checking
                    df['_check_key'] = df[col_map['serial_number']].astype(str).str.strip() + '_' + df[col_map['print_status']].astype(str).str.strip()
                    file_keys = df['_check_key'].unique().tolist()

                    existing_keys = set()
                    batch_size = 1000
                    for i in range(0, len(file_keys), batch_size):
                        batch = file_keys[i:i+batch_size]
                        result = session.execute(
                            text("SELECT serial_number || '_' || print_status FROM bio_records WHERE serial_number || '_' || print_status IN :keys"),
                            {"keys": tuple(batch) if len(batch) > 1 else (batch[0], batch[0])}
                        )
                        existing_keys.update(row[0] for row in result)

                    if existing_keys:
                        st.warning(f"⚠️ พบข้อมูลซ้ำในฐานข้อมูล {len(existing_keys):,} รายการ (Serial+Status เดียวกัน)")

                    # Clean up temp column
                    if '_check_key' in df.columns:
                        df = df.drop(columns=['_check_key'])
            finally:
                session.close()

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📥 นำเข้า Bio Raw", type="primary", use_container_width=True, key="import_bio"):
                    progress = st.progress(0)
                    status_text = st.empty()
                    session = get_session()
                    try:
                        status_text.text("กำลังสร้าง upload record...")
                        upload = BioUpload(
                            filename=uploaded_bio.name,
                            date_from=min_date, date_to=max_date,
                            total_records=total,
                            total_good=good,
                            total_bad=bad,
                            uploaded_by=st.session_state.get('username', 'unknown')
                        )
                        session.add(upload)
                        session.flush()
                        upload_id = upload.id
                        progress.progress(10)

                        # Prepare data - simple and fast
                        status_text.text("กำลังเตรียมข้อมูล...")
                        import_df = pd.DataFrame({
                            'upload_id': upload_id,
                            'appointment_id': df[col_map['appointment_id']].astype(str).str.strip() if col_map.get('appointment_id') else None,
                            'form_id': df[col_map['form_id']].astype(str).str.strip() if col_map.get('form_id') else None,
                            'form_type': df[col_map['form_type']].astype(str).str.strip() if col_map.get('form_type') else None,
                            'branch_code': df[col_map['branch_code']].astype(str).str.strip() if col_map.get('branch_code') else None,
                            'card_id': df[col_map['card_id']].astype(str).str.strip() if col_map.get('card_id') else None,
                            'work_permit_no': df[col_map['work_permit_no']].astype(str).str.strip() if col_map.get('work_permit_no') else None,
                            'serial_number': df[col_map['serial_number']].astype(str).str.strip() if col_map.get('serial_number') else None,
                            'print_status': df[col_map['print_status']].astype(str).str.strip() if col_map.get('print_status') else None,
                            'reject_type': df[col_map['reject_type']].astype(str).str.strip() if col_map.get('reject_type') else None,
                            'operator': df[col_map['operator']].astype(str).str.strip() if col_map.get('operator') else None,
                            'print_date': pd.to_datetime(df[col_map['print_date']], errors='coerce') if col_map.get('print_date') else None,
                            'sla_start': df[col_map['sla_start']].astype(str).str.strip() if col_map.get('sla_start') else None,
                            'sla_stop': df[col_map['sla_stop']].astype(str).str.strip() if col_map.get('sla_stop') else None,
                            'sla_duration': df[col_map['sla_duration']].astype(str).str.strip() if col_map.get('sla_duration') else None,
                            'emergency': pd.to_numeric(df[col_map['emergency']], errors='coerce').astype('Int64') if col_map.get('emergency') else None,
                            'sla_minutes': df[col_map['sla_duration']].apply(parse_sla_duration) if col_map.get('sla_duration') else None,
                        })
                        import_df = import_df.replace({'nan': None, 'None': None, '': None})
                        progress.progress(30)

                        # Use PostgreSQL COPY for maximum speed
                        status_text.text("กำลังนำเข้าข้อมูล...")
                        from database.connection import is_sqlite
                        from io import StringIO

                        total_records = len(import_df)

                        if is_sqlite:
                            import_df.to_sql('bio_records', session.bind, if_exists='append', index=False, method='multi', chunksize=5000)
                            progress.progress(95)
                        else:
                            # PostgreSQL: use COPY protocol (fastest possible method)
                            conn = session.connection().connection
                            cursor = conn.cursor()

                            columns = ['upload_id', 'appointment_id', 'form_id', 'form_type', 'branch_code',
                                       'card_id', 'work_permit_no', 'serial_number', 'print_status', 'reject_type',
                                       'operator', 'print_date', 'sla_start', 'sla_stop', 'sla_duration', 'emergency', 'sla_minutes']

                            # Convert DataFrame to CSV string buffer
                            status_text.text("กำลังเตรียมข้อมูลสำหรับ COPY...")
                            # Fix: Keep Int64 dtype (not object/float) so to_csv writes integers, not "0.0"
                            copy_df = import_df[columns].copy()
                            if 'emergency' in copy_df.columns:
                                # Ensure Int64 dtype is preserved (not converted to float via apply/lambda)
                                copy_df['emergency'] = pd.to_numeric(copy_df['emergency'], errors='coerce').astype('Int64')
                            buffer = StringIO()
                            copy_df.to_csv(buffer, index=False, header=False, na_rep='\\N')
                            buffer.seek(0)
                            progress.progress(50)

                            # Use COPY command
                            status_text.text(f"กำลังนำเข้า {total_records:,} รายการด้วย COPY...")
                            cursor.copy_expert("""
                                COPY bio_records (upload_id, appointment_id, form_id, form_type, branch_code,
                                    card_id, work_permit_no, serial_number, print_status, reject_type,
                                    operator, print_date, sla_start, sla_stop, sla_duration, emergency, sla_minutes)
                                FROM STDIN WITH (FORMAT CSV, NULL '\\N')
                            """, buffer)
                            progress.progress(95)

                        session.commit()

                        # Free memory
                        del import_df, df
                        gc.collect()
                        progress.progress(100)
                        status_text.empty()
                        st.success(f"นำเข้าสำเร็จ! {total:,} รายการ (G: {good:,} | B: {bad:,})")
                        st.balloons()
                    except Exception as e:
                        session.rollback()
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")
                    finally:
                        session.close()

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {str(e)}")

    # Show existing
    st.markdown("---")
    st.markdown("#### 📋 ข้อมูล Bio Raw ในระบบ")
    session = get_session()
    try:
        uploads = session.query(BioUpload).order_by(BioUpload.upload_date.desc()).all()
        if uploads:
            data = [{'ID': u.id, 'ชื่อไฟล์': u.filename[:30], 'ช่วงวันที่': f"{u.date_from} - {u.date_to}", 'G': u.total_good or 0, 'B': u.total_bad or 0} for u in uploads]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

            if can_delete():
                col1, col2 = st.columns([3, 1])
                with col1:
                    sel = st.selectbox("เลือกไฟล์ที่ต้องการลบ", [(u.id, u.filename) for u in uploads], format_func=lambda x: x[1], key="del_bio")
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ ลบ", key="btn_del_bio"):
                        session.query(BioRecord).filter(BioRecord.upload_id == sel[0]).delete()
                        session.query(BioUpload).filter(BioUpload.id == sel[0]).delete()
                        session.commit()
                        st.success("ลบสำเร็จ!")
                        st.rerun()
        else:
            st.info("ยังไม่มีข้อมูล Bio Raw")
    finally:
        session.close()


# ==================== TAB 5: CARD DELIVERY ====================
with tab5:
    st.markdown('<div class="section-header section-header-purple">📦 ข้อมูล Card Delivery (บัตรจัดส่ง)</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="info-box">
        <strong>ไฟล์ที่รองรับ:</strong> Card-Delivery-Report-*.xlsx<br>
        <strong>ลักษณะข้อมูล:</strong> เลขนัดหมายขึ้นต้นด้วย 68, 69 (ไม่มี SLA time)
    </div>
    """, unsafe_allow_html=True)

    uploaded_card_delivery = st.file_uploader(
        "เลือกไฟล์ Card Delivery",
        type=['xlsx', 'csv'],
        key="card_delivery_uploader"
    )

    if uploaded_card_delivery:
        try:
            # Read file
            if uploaded_card_delivery.name.endswith('.csv'):
                df = pd.read_csv(uploaded_card_delivery)
            else:
                df = pd.read_excel(uploaded_card_delivery, sheet_name=0)

            total = len(df)

            # Column mapping for Card Delivery
            col_map = {}
            columns_lower = {c.lower(): c for c in df.columns}

            # Map columns
            col_mappings = {
                'appointment_id': ['appointment_id'],
                'serial_number': ['serial_number'],
                'alien_card_id': ['alien_card_id'],
                'branch_code': ['branch_code'],
                'print_status': ['print_status'],
                'print_remark': ['print_remark'],
                'print_status_id': ['print_status_id'],
                'send_status_id': ['send_status_id'],
                'send_flag': ['send_flag'],
                'send_date': ['send_date'],
                'create_by': ['create_by'],
                'create_date': ['create_date'],
                'update_by': ['update_by'],
                'update_date': ['update_date'],
                'versions': ['versions'],
            }

            for key, patterns in col_mappings.items():
                for pattern in patterns:
                    if pattern in columns_lower:
                        col_map[key] = columns_lower[pattern]
                        break

            st.success(f"เลือกไฟล์: {uploaded_card_delivery.name}")

            # Get date range from create_date
            if col_map.get('create_date'):
                df['_create_date'] = pd.to_datetime(df[col_map['create_date']], errors='coerce')
                min_date = df['_create_date'].min().date() if pd.notna(df['_create_date'].min()) else None
                max_date = df['_create_date'].max().date() if pd.notna(df['_create_date'].max()) else None
            else:
                min_date = max_date = None

            # Status counts (convert to Python int to avoid numpy.int64 issues)
            if col_map.get('print_status'):
                status_counts = df[col_map['print_status']].value_counts()
                good = int(status_counts.get('G', 0))
                bad = int(status_counts.get('B', 0))
            else:
                good = bad = 0

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("จำนวน Records", f"{total:,}")
            with col2:
                st.metric("Good (G)", f"{good:,}")
            with col3:
                st.metric("Bad (B)", f"{bad:,}")
            with col4:
                st.metric("ช่วงวันที่", f"{min_date} - {max_date}" if min_date else "-")

            # Preview
            st.dataframe(df.head(5), use_container_width=True, hide_index=True)

            # Check for duplicates - block import if found
            session = get_session()
            duplicate_found = False
            try:
                if col_map.get('serial_number'):
                    file_serials = df[col_map['serial_number']].astype(str).str.strip().unique().tolist()
                    from sqlalchemy import text
                    existing_serials = set()
                    batch_size = 1000
                    for i in range(0, len(file_serials), batch_size):
                        batch = file_serials[i:i+batch_size]
                        result = session.execute(
                            text("SELECT serial_number FROM card_delivery_records WHERE serial_number IN :serials"),
                            {"serials": tuple(batch) if len(batch) > 1 else (batch[0], batch[0])}
                        )
                        existing_serials.update(row[0] for row in result)

                    if existing_serials:
                        st.error(f"❌ พบ Serial Number ซ้ำในฐานข้อมูล {len(existing_serials):,} รายการ - ไม่สามารถนำเข้าได้")
                        duplicate_found = True
            finally:
                session.close()

            # Import button
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📥 นำเข้า Card Delivery", type="primary", use_container_width=True, key="import_card_delivery", disabled=duplicate_found):
                    progress = st.progress(0)
                    status_text = st.empty()
                    session = get_session()
                    try:
                        status_text.text("กำลังสร้าง upload record...")
                        upload = CardDeliveryUpload(
                            filename=uploaded_card_delivery.name,
                            date_from=min_date, date_to=max_date,
                            total_records=total,
                            total_good=good,
                            total_bad=bad,
                            uploaded_by=st.session_state.get('username', 'unknown')
                        )
                        session.add(upload)
                        session.flush()
                        upload_id = upload.id
                        progress.progress(10)

                        # Prepare data
                        status_text.text("กำลังเตรียมข้อมูล...")
                        import_df = pd.DataFrame({
                            'upload_id': upload_id,
                            'appointment_id': df[col_map['appointment_id']].astype(str).str.strip() if col_map.get('appointment_id') else None,
                            'serial_number': df[col_map['serial_number']].astype(str).str.strip() if col_map.get('serial_number') else None,
                            'alien_card_id': df[col_map['alien_card_id']].astype(str).str.strip() if col_map.get('alien_card_id') else None,
                            'branch_code': df[col_map['branch_code']].astype(str).str.strip() if col_map.get('branch_code') else None,
                            'print_status': df[col_map['print_status']].astype(str).str.strip() if col_map.get('print_status') else None,
                            'print_remark': df[col_map['print_remark']].astype(str).str.strip() if col_map.get('print_remark') else None,
                            'print_status_id': pd.to_numeric(df[col_map['print_status_id']], errors='coerce') if col_map.get('print_status_id') else None,
                            'send_status_id': pd.to_numeric(df[col_map['send_status_id']], errors='coerce') if col_map.get('send_status_id') else None,
                            'send_flag': df[col_map['send_flag']].astype(str).str.strip() if col_map.get('send_flag') else None,
                            'send_date': pd.to_datetime(df[col_map['send_date']], errors='coerce') if col_map.get('send_date') else None,
                            'create_by': df[col_map['create_by']].astype(str).str.strip() if col_map.get('create_by') else None,
                            'create_date': pd.to_datetime(df[col_map['create_date']], errors='coerce') if col_map.get('create_date') else None,
                            'update_by': df[col_map['update_by']].astype(str).str.strip() if col_map.get('update_by') else None,
                            'update_date': pd.to_datetime(df[col_map['update_date']], errors='coerce') if col_map.get('update_date') else None,
                            'versions': pd.to_numeric(df[col_map['versions']], errors='coerce') if col_map.get('versions') else None,
                        })
                        import_df = import_df.replace({'nan': None, 'None': None, '': None})
                        progress.progress(30)

                        # Use PostgreSQL COPY for maximum speed
                        status_text.text("กำลังนำเข้าข้อมูล...")
                        from database.connection import is_sqlite
                        from io import StringIO

                        total_records = len(import_df)

                        if is_sqlite:
                            import_df.to_sql('card_delivery_records', session.bind, if_exists='append', index=False, method='multi', chunksize=5000)
                            progress.progress(95)
                        else:
                            # PostgreSQL: use COPY protocol
                            conn = session.connection().connection
                            cursor = conn.cursor()

                            columns = ['upload_id', 'appointment_id', 'serial_number', 'alien_card_id', 'branch_code',
                                       'print_status', 'print_remark', 'print_status_id', 'send_status_id', 'send_flag',
                                       'send_date', 'create_by', 'create_date', 'update_by', 'update_date', 'versions']

                            status_text.text("กำลังเตรียมข้อมูลสำหรับ COPY...")
                            buffer = StringIO()
                            import_df[columns].to_csv(buffer, index=False, header=False, na_rep='\\N')
                            buffer.seek(0)
                            progress.progress(50)

                            status_text.text(f"กำลังนำเข้า {total_records:,} รายการด้วย COPY...")
                            cursor.copy_expert("""
                                COPY card_delivery_records (upload_id, appointment_id, serial_number, alien_card_id, branch_code,
                                    print_status, print_remark, print_status_id, send_status_id, send_flag,
                                    send_date, create_by, create_date, update_by, update_date, versions)
                                FROM STDIN WITH (FORMAT CSV, NULL '\\N')
                            """, buffer)
                            progress.progress(95)

                        session.commit()

                        # Free memory
                        del import_df, df
                        gc.collect()
                        progress.progress(100)
                        status_text.empty()
                        st.success(f"นำเข้าสำเร็จ! {total:,} รายการ (G: {good:,} | B: {bad:,})")
                        st.balloons()
                    except Exception as e:
                        session.rollback()
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")
                    finally:
                        session.close()

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {str(e)}")

    # Show existing
    st.markdown("---")
    st.markdown("#### 📋 ข้อมูล Card Delivery ในระบบ")
    session = get_session()
    try:
        uploads = session.query(CardDeliveryUpload).order_by(CardDeliveryUpload.upload_date.desc()).all()
        if uploads:
            data = [{'ID': u.id, 'ชื่อไฟล์': u.filename[:30], 'ช่วงวันที่': f"{u.date_from} - {u.date_to}", 'G': u.total_good or 0, 'B': u.total_bad or 0} for u in uploads]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

            if can_delete():
                col1, col2 = st.columns([3, 1])
                with col1:
                    sel = st.selectbox("เลือกไฟล์ที่ต้องการลบ", [(u.id, u.filename) for u in uploads], format_func=lambda x: x[1], key="del_card_delivery")
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ ลบ", key="btn_del_card_delivery"):
                        session.query(CardDeliveryRecord).filter(CardDeliveryRecord.upload_id == sel[0]).delete()
                        session.query(CardDeliveryUpload).filter(CardDeliveryUpload.id == sel[0]).delete()
                        session.commit()
                        st.success("ลบสำเร็จ!")
                        st.rerun()
        else:
            st.info("ยังไม่มีข้อมูล Card Delivery")
    finally:
        session.close()
