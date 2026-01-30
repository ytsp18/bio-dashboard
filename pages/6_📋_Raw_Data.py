"""Raw Data page - View all data with comprehensive filters and complete columns."""
import streamlit as st
import pandas as pd
from io import BytesIO
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session, get_branch_name_map_cached
from database.models import Card, Report
from services.data_service import DataService
from sqlalchemy import func, and_
from utils.theme import apply_theme, render_theme_toggle
from utils.auth_check import require_login

init_db()

st.set_page_config(page_title="Raw Data - Bio Dashboard", page_icon="📋", layout="wide")

# Check authentication
require_login()

# Apply theme
apply_theme()

# Title - Light Theme
st.markdown("<h2 style='margin-bottom: 5px; color: #1E293B;'>📋 Raw Data</h2>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748B; margin-bottom: 20px;'>ดูและส่งออกข้อมูลบัตรทั้งหมด</p>", unsafe_allow_html=True)

session = get_session()

try:
    # Theme toggle in sidebar
    render_theme_toggle()

    # Check if data exists
    total_records = session.query(Card).count()

    if total_records == 0:
        st.info("ยังไม่มีข้อมูล - กรุณาอัพโหลดไฟล์รายงานก่อน")
    else:
        # Filter Section in Sidebar
        st.sidebar.markdown("### Filter")

        # Date filter
        min_date = session.query(func.min(Card.print_date)).scalar()
        max_date = session.query(func.max(Card.print_date)).scalar()

        start_date = st.sidebar.date_input("วันที่เริ่มต้น", value=min_date, min_value=min_date, max_value=max_date)
        end_date = st.sidebar.date_input("วันที่สิ้นสุด", value=max_date, min_value=min_date, max_value=max_date)

        # Branch filter
        branches = DataService.get_branch_list(session)
        selected_branches = st.sidebar.multiselect(
            "ศูนย์บริการ (ว่าง = ทั้งหมด)",
            options=branches,
            default=[]
        )

        # Status filter
        status_filter = st.sidebar.radio(
            "สถานะบัตร",
            options=['ทั้งหมด', 'บัตรดี (G)', 'บัตรเสีย (B)'],
            horizontal=True
        )

        # Flags filter
        st.sidebar.markdown("#### Flags")
        show_sla_over = st.sidebar.checkbox("SLA เกิน 12 นาที")
        show_wrong_branch = st.sidebar.checkbox("ออกบัตรผิดศูนย์")
        show_wrong_date = st.sidebar.checkbox("นัดหมายผิดวัน")
        show_wait_over = st.sidebar.checkbox("รอคิวเกิน 1 ชม.")

        # Display option - Show all or limited
        st.sidebar.markdown("#### การแสดงผล")
        show_all_rows = st.sidebar.checkbox("แสดงข้อมูลทั้งหมด", value=False, help="ถ้าไม่เลือก จะแสดงสูงสุด 5000 แถว")

        # Build query
        query = session.query(Card)

        # Apply filters
        query = query.filter(Card.print_date >= start_date)
        query = query.filter(Card.print_date <= end_date)

        if selected_branches:
            query = query.filter(Card.branch_code.in_(selected_branches))

        if status_filter == 'บัตรดี (G)':
            query = query.filter(Card.print_status == 'G')
        elif status_filter == 'บัตรเสีย (B)':
            query = query.filter(Card.print_status == 'B')

        if show_sla_over:
            query = query.filter(Card.sla_over_12min == True)
        if show_wrong_branch:
            query = query.filter(Card.wrong_branch == True)
        if show_wrong_date:
            query = query.filter(Card.wrong_date == True)
        if show_wait_over:
            query = query.filter(Card.wait_over_1hour == True)

        # Get total count after filters
        filtered_count = query.count()

        # Summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("ข้อมูลในระบบ", f"{total_records:,}")
        with col2:
            st.metric("ผลลัพธ์ที่กรอง", f"{filtered_count:,}")
        with col3:
            if show_all_rows:
                st.metric("แสดงผล", f"{filtered_count:,}")
            else:
                st.metric("แสดงผล", f"{min(5000, filtered_count):,}")

        # Execute query
        if show_all_rows:
            results = query.order_by(Card.print_date.desc()).all()
        else:
            results = query.order_by(Card.print_date.desc()).limit(5000).all()

        if results:
            # Get branch name mapping from BranchMaster
            branch_name_map = get_branch_name_map_cached()

            # Convert to DataFrame with columns ordered by importance
            data = []
            for card in results:
                flags = []
                if card.sla_over_12min:
                    flags.append("SLA>12")
                if card.wrong_branch:
                    flags.append("ผิดศูนย์")
                if card.wrong_date:
                    flags.append("ผิดวัน")
                if card.wait_over_1hour:
                    flags.append("รอ>1ชม")
                if card.emergency:
                    flags.append("Emergency")

                # Get branch name from BranchMaster
                branch_name = branch_name_map.get(card.branch_code, card.branch_name or card.branch_code or '-')

                # Order columns by importance - key card data first
                data.append({
                    # Primary card identification
                    'Appointment ID': card.appointment_id or '-',
                    'Card ID': card.card_id or '-',
                    'Serial Number': card.serial_number or '-',
                    'Work Permit': card.work_permit_no or '-',
                    'สถานะ': card.print_status or '-',
                    'วันที่พิมพ์': card.print_date,
                    'ผู้ให้บริการ': card.operator or '-',
                    # Center info
                    'ศูนย์บริการ': (branch_name[:60] if branch_name else '-'),
                    'ภูมิภาค': card.region or '-',
                    # SLA info
                    'SLA (นาที)': round(card.sla_minutes, 2) if card.sla_minutes else None,
                    'SLA Start': card.sla_start or '-',
                    'SLA Stop': card.sla_stop or '-',
                    'SLA Duration': card.sla_duration or '-',
                    'SLA Confirm Type': card.sla_confirm_type or '-',
                    'SLA Over 12min': 'Y' if card.sla_over_12min else 'N',
                    # Queue info (may be empty for monthly reports)
                    'Qlog ID': card.qlog_id or '-',
                    'Qlog Branch': card.qlog_branch or '-',
                    'Qlog Date': card.qlog_date or '-',
                    'Qlog Queue No': card.qlog_queue_no if card.qlog_queue_no else '-',
                    'Qlog Type': card.qlog_type or '-',
                    'Time In': card.qlog_time_in or '-',
                    'Time Call': card.qlog_time_call or '-',
                    'Wait (นาที)': round(card.wait_time_minutes, 2) if card.wait_time_minutes else None,
                    'Wait Time (HMS)': card.wait_time_hms or '-',
                    'Qlog SLA Status': card.qlog_sla_status or '-',
                    # Appointment info
                    'วันที่นัด': card.appt_date or '-',
                    'ศูนย์ที่นัด': card.appt_branch or '-',
                    'สถานะนัดหมาย': card.appt_status or '-',
                    # Flags
                    'Wrong Date': 'Y' if card.wrong_date else 'N',
                    'Wrong Branch': 'Y' if card.wrong_branch else 'N',
                    'Mobile Unit': 'Y' if card.is_mobile_unit else 'N',
                    'OB Center': 'Y' if card.is_ob_center else 'N',
                    'Old Appointment': 'Y' if card.old_appointment else 'N',
                    'Valid SLA Status': 'Y' if card.is_valid_sla_status else 'N',
                    'Wait Over 1hr': 'Y' if card.wait_over_1hour else 'N',
                    'Emergency': 'Y' if card.emergency else 'N',
                    'Flags': ', '.join(flags) if flags else '-',
                    # Other
                    'Form ID': card.form_id or '-',
                    'Form Type': card.form_type or '-',
                    'สาเหตุบัตรเสีย': card.reject_type or '-',
                })

            df = pd.DataFrame(data)

            # Column selector - reordered for better visibility
            col_groups = {
                'ข้อมูลหลัก (บัตร)': ['Appointment ID', 'Card ID', 'Serial Number', 'Work Permit', 'สถานะ', 'วันที่พิมพ์', 'ผู้ให้บริการ'],
                'ข้อมูลศูนย์': ['ศูนย์บริการ', 'ภูมิภาค'],
                'ข้อมูล SLA': ['SLA (นาที)', 'SLA Start', 'SLA Stop', 'SLA Duration', 'SLA Confirm Type', 'SLA Over 12min'],
                'ข้อมูล Queue': ['Qlog ID', 'Qlog Branch', 'Qlog Date', 'Qlog Queue No', 'Qlog Type', 'Time In', 'Time Call', 'Wait (นาที)', 'Wait Time (HMS)', 'Qlog SLA Status'],
                'ข้อมูลนัดหมาย': ['วันที่นัด', 'ศูนย์ที่นัด', 'สถานะนัดหมาย', 'Wrong Date', 'Wrong Branch'],
                'Flags': ['Mobile Unit', 'OB Center', 'Old Appointment', 'Valid SLA Status', 'Wait Over 1hr', 'Emergency', 'Flags'],
                'อื่นๆ': ['Form ID', 'Form Type', 'สาเหตุบัตรเสีย']
            }

            col1, col2 = st.columns([3, 1])

            with col1:
                selected_groups = st.multiselect(
                    "เลือกกลุ่มคอลัมน์",
                    options=list(col_groups.keys()),
                    default=['ข้อมูลหลัก (บัตร)', 'ข้อมูลศูนย์'],
                    key="col_groups"
                )

            with col2:
                show_all_cols = st.checkbox("แสดงทุกคอลัมน์", value=False)

            # Determine columns to show
            if show_all_cols:
                selected_cols = list(df.columns)
            else:
                selected_cols = []
                for group in selected_groups:
                    selected_cols.extend(col_groups[group])
                selected_cols = list(dict.fromkeys(selected_cols))

            if selected_cols:
                display_df = df[selected_cols]
            else:
                display_df = df

            # Display data - show ALL rows without limit
            st.caption(f"แสดง {len(display_df):,} แถว x {len(display_df.columns)} คอลัมน์")
            st.caption("*หมายเหตุ: ข้อมูล Queue (Qlog) อาจไม่มีสำหรับบางรายงาน โดยเฉพาะรายงานรายเดือน*")

            # Use st.dataframe with dynamic height based on data
            height = min(600, max(200, len(display_df) * 35 + 38))
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                height=height
            )

            # Export section
            st.markdown("---")

            col1, col2, col3 = st.columns(3)

            with col1:
                buffer1 = BytesIO()
                with pd.ExcelWriter(buffer1, engine='xlsxwriter') as writer:
                    display_df.to_excel(writer, index=False, sheet_name='Data')

                st.download_button(
                    "Excel (คอลัมน์ที่เลือก)",
                    buffer1.getvalue(),
                    f"raw_data_selected_{start_date}_{end_date}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            with col2:
                buffer2 = BytesIO()
                with pd.ExcelWriter(buffer2, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Data')

                st.download_button(
                    "Excel (ทุกคอลัมน์)",
                    buffer2.getvalue(),
                    f"raw_data_full_{start_date}_{end_date}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            with col3:
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "CSV (ทุกคอลัมน์)",
                    csv,
                    f"raw_data_{start_date}_{end_date}.csv",
                    "text/csv",
                    use_container_width=True
                )

            # Quick stats
            st.markdown("---")
            st.markdown("#### สถิติจากข้อมูลที่กรอง")

            col1, col2, col3, col4 = st.columns(4)

            good_count = len(df[df['สถานะ'] == 'G'])
            bad_count = len(df[df['สถานะ'] == 'B'])
            avg_sla = df['SLA (นาที)'].mean() if 'SLA (นาที)' in df.columns else 0
            avg_wait = df['Wait (นาที)'].mean() if 'Wait (นาที)' in df.columns else 0

            with col1:
                good_pct = (good_count / len(df) * 100) if len(df) > 0 else 0
                st.metric("บัตรดี (G)", f"{good_count:,}", f"{good_pct:.1f}%")

            with col2:
                bad_pct = (bad_count / len(df) * 100) if len(df) > 0 else 0
                st.metric("บัตรเสีย (B)", f"{bad_count:,}", f"{bad_pct:.1f}%")

            with col3:
                st.metric("SLA เฉลี่ย", f"{avg_sla:.2f} นาที" if avg_sla else "N/A")

            with col4:
                st.metric("เวลารอคิวเฉลี่ย", f"{avg_wait:.2f} นาที" if avg_wait else "N/A")

        else:
            st.warning("ไม่พบข้อมูลตามเงื่อนไขที่เลือก")

finally:
    session.close()
