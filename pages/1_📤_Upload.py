"""Upload page for importing all data files."""
import streamlit as st
import sys
import os
import tempfile
import pandas as pd
from datetime import datetime
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session
from database.models import (
    Report, Card, BadCard, CenterStat, AnomalySLA, WrongCenter, CompleteDiff, DeliveryCard,
    AppointmentUpload, Appointment, QLogUpload, QLog, BioUpload, BioRecord
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
    .section-header-orange { border-left-color: #F59E0B; }
    .section-header-green { border-left-color: #10B981; }
    .section-header-purple { border-left-color: #8B5CF6; }
    .info-box {
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-left: 4px solid #3B82F6;
        padding: 12px 16px;
        border-radius: 8px;
        color: #93C5FD;
        margin: 10px 0;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown("""
<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #374151;">
    <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #3B82F6, #2563EB); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
        <span style="font-size: 24px;">📤</span>
    </div>
    <div>
        <h1 style="font-size: 1.75rem; font-weight: 700; color: #FAFAFA; margin: 0;">อัพโหลดข้อมูล</h1>
        <p style="font-size: 0.9rem; color: #9CA3AF; margin: 0;">นำเข้าข้อมูลเข้าสู่ระบบ Bio Dashboard</p>
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
    if pd.isna(val):
        return None
    return str(val).strip() if val else None


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

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Bio Unified Report",
    "📅 Appointment",
    "⏱️ QLog",
    "🖨️ Bio Raw"
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
                        status.text("กำลังประมวลผล...")
                        progress.progress(30)
                        result = DataService.import_excel(tmp_path, original_filename=uploaded_unified.name)
                        progress.progress(100)
                        status.empty()

                        st.success(f"นำเข้าสำเร็จ! บัตรดี: {result['total_good']:,} | บัตรเสีย: {result['total_bad']:,}")
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
                df = pd.read_csv(uploaded_appt)
            else:
                df = pd.read_excel(uploaded_appt)

            # Auto-map columns
            col_map = {}
            for target, names in APPT_COLUMNS.items():
                col_map[target] = find_column(df, names)

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

            # Import
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📥 นำเข้า Appointment", type="primary", use_container_width=True, key="import_appt"):
                    progress = st.progress(0)
                    session = get_session()
                    try:
                        upload = AppointmentUpload(
                            filename=uploaded_appt.name,
                            date_from=min_date, date_to=max_date,
                            total_records=total,
                            uploaded_by=st.session_state.get('username', 'unknown')
                        )
                        session.add(upload)
                        session.flush()

                        records = []
                        for idx, row in df.iterrows():
                            records.append(Appointment(
                                upload_id=upload.id,
                                appointment_id=safe_str(row[col_map['appointment_id']]) if col_map.get('appointment_id') else None,
                                appt_date=parse_date(row[col_map['appt_date']]) if col_map.get('appt_date') else None,
                                branch_code=safe_str(row[col_map['branch_code']]) if col_map.get('branch_code') else None,
                                appt_status=safe_str(row[col_map['appt_status']]) if col_map.get('appt_status') else None,
                                form_id=safe_str(row[col_map['form_id']]) if col_map.get('form_id') else None,
                                form_type=safe_str(row[col_map['form_type']]) if col_map.get('form_type') else None,
                                work_permit_no=safe_str(row[col_map['work_permit_no']]) if col_map.get('work_permit_no') else None,
                            ))
                            if idx % 1000 == 0:
                                progress.progress(int(idx / total * 80))

                        session.bulk_save_objects(records)
                        session.commit()
                        progress.progress(100)
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
        'qlog_num': ['QLOG_NUM'],
        'qlog_user': ['QLOG_USER'],
        'qlog_date': ['QLOG_DATE', 'QLOG_DATEIN'],
        'qlog_time_in': ['QLOG_TIMEIN'],
        'qlog_time_call': ['QLOG_TIMECALL'],
        'qlog_time_end': ['QLOG_TIMEEND'],
        'wait_time_seconds': ['QLOG_COUNTWAIT'],
        'appointment_code': ['APPOINTMENT_CODE'],
        'qlog_status': ['QLOG_STATUS'],
        'sla_status': ['SLA_STATUS'],
    }

    uploaded_qlog = st.file_uploader("เลือกไฟล์ QLog", type=['csv'], key="qlog_uploader")

    if uploaded_qlog is not None:
        st.success(f"เลือกไฟล์: **{uploaded_qlog.name}**")

        try:
            df = pd.read_csv(uploaded_qlog)

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

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📥 นำเข้า QLog", type="primary", use_container_width=True, key="import_qlog"):
                    progress = st.progress(0)
                    session = get_session()
                    try:
                        upload = QLogUpload(
                            filename=uploaded_qlog.name,
                            date_from=min_date, date_to=max_date,
                            total_records=total,
                            uploaded_by=st.session_state.get('username', 'unknown')
                        )
                        session.add(upload)
                        session.flush()

                        records = []
                        for idx, row in df.iterrows():
                            records.append(QLog(
                                upload_id=upload.id,
                                qlog_id=safe_str(row[col_map['qlog_id']]) if col_map.get('qlog_id') else None,
                                branch_code=safe_str(row[col_map['branch_code']]) if col_map.get('branch_code') else None,
                                qlog_type=safe_str(row[col_map['qlog_type']]) if col_map.get('qlog_type') else None,
                                qlog_num=safe_int(row[col_map['qlog_num']]) if col_map.get('qlog_num') else None,
                                qlog_user=safe_str(row[col_map['qlog_user']]) if col_map.get('qlog_user') else None,
                                qlog_date=parse_date(row[col_map['qlog_date']]) if col_map.get('qlog_date') else None,
                                qlog_time_in=safe_str(row[col_map['qlog_time_in']]) if col_map.get('qlog_time_in') else None,
                                qlog_time_call=safe_str(row[col_map['qlog_time_call']]) if col_map.get('qlog_time_call') else None,
                                qlog_time_end=safe_str(row[col_map['qlog_time_end']]) if col_map.get('qlog_time_end') else None,
                                wait_time_seconds=safe_int(row[col_map['wait_time_seconds']]) if col_map.get('wait_time_seconds') else None,
                                appointment_code=safe_str(row[col_map['appointment_code']]) if col_map.get('appointment_code') else None,
                                qlog_status=safe_str(row[col_map['qlog_status']]) if col_map.get('qlog_status') else None,
                                sla_status=safe_str(row[col_map['sla_status']]) if col_map.get('sla_status') else None,
                            ))
                            if idx % 1000 == 0:
                                progress.progress(int(idx / total * 80))

                        session.bulk_save_objects(records)
                        session.commit()
                        progress.progress(100)
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
                df = pd.read_csv(uploaded_bio)
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

            # Status counts
            status_col = col_map.get('print_status')
            if status_col:
                status_counts = df[status_col].value_counts()
                good = status_counts.get('G', 0)
                bad = status_counts.get('B', 0)
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

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📥 นำเข้า Bio Raw", type="primary", use_container_width=True, key="import_bio"):
                    progress = st.progress(0)
                    session = get_session()
                    try:
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

                        records = []
                        for idx, row in df.iterrows():
                            sla_dur = row[col_map['sla_duration']] if col_map.get('sla_duration') else None
                            records.append(BioRecord(
                                upload_id=upload.id,
                                appointment_id=safe_str(row[col_map['appointment_id']]) if col_map.get('appointment_id') else None,
                                form_id=safe_str(row[col_map['form_id']]) if col_map.get('form_id') else None,
                                form_type=safe_str(row[col_map['form_type']]) if col_map.get('form_type') else None,
                                branch_code=safe_str(row[col_map['branch_code']]) if col_map.get('branch_code') else None,
                                card_id=safe_str(row[col_map['card_id']]) if col_map.get('card_id') else None,
                                work_permit_no=safe_str(row[col_map['work_permit_no']]) if col_map.get('work_permit_no') else None,
                                serial_number=safe_str(row[col_map['serial_number']]) if col_map.get('serial_number') else None,
                                print_status=safe_str(row[col_map['print_status']]) if col_map.get('print_status') else None,
                                reject_type=safe_str(row[col_map['reject_type']]) if col_map.get('reject_type') else None,
                                operator=safe_str(row[col_map['operator']]) if col_map.get('operator') else None,
                                print_date=parse_date(row[col_map['print_date']]) if col_map.get('print_date') else None,
                                sla_start=safe_str(row[col_map['sla_start']]) if col_map.get('sla_start') else None,
                                sla_stop=safe_str(row[col_map['sla_stop']]) if col_map.get('sla_stop') else None,
                                sla_duration=safe_str(sla_dur),
                                sla_minutes=parse_sla_duration(sla_dur),
                                emergency=safe_int(row[col_map['emergency']]) if col_map.get('emergency') else None,
                            ))
                            if idx % 1000 == 0:
                                progress.progress(int(idx / total * 80))

                        session.bulk_save_objects(records)
                        session.commit()
                        progress.progress(100)
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
