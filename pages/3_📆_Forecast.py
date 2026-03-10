"""Forecast page - Upcoming Appointments Workload Forecast."""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from streamlit_echarts import st_echarts
from datetime import date, timedelta
import time
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session, get_branch_name_map_cached
from database.models import Appointment, BranchMaster, QLog
from sqlalchemy import func, and_, or_
from utils.theme import apply_theme
from utils.auth_check import require_login
from utils.logger import log_perf
from utils.branch_display import get_branch_short_name_map

init_db()


@st.cache_data(ttl=3600)
def get_checkin_data(selected_branches=None, start_date=None, end_date=None):
    """
    Get check-in data from QLog for comparison with appointments.
    Returns aggregated check-in counts by branch and date.
    """
    session = get_session()
    try:
        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = start_date + timedelta(days=29)

        # Check if we have QLog data
        has_qlog = session.query(QLog).first() is not None
        if not has_qlog:
            return {'has_data': False, 'by_branch': [], 'by_branch_date': []}

        # Build filters
        filters = [
            QLog.qlog_date >= start_date,
            QLog.qlog_date <= end_date,
        ]
        if selected_branches and len(selected_branches) > 0:
            filters.append(QLog.branch_code.in_(selected_branches))

        branch_map = get_branch_name_map_cached()

        # Aggregate by branch (total in range)
        by_branch_query = session.query(
            QLog.branch_code,
            func.count(QLog.id).label('checkin_count')
        ).filter(and_(*filters)).group_by(QLog.branch_code).all()

        by_branch = []
        for r in by_branch_query:
            by_branch.append({
                'branch_code': r.branch_code,
                'branch_name': branch_map.get(r.branch_code, r.branch_code),
                'checkin_count': r.checkin_count
            })

        # Aggregate by branch and date
        by_branch_date_query = session.query(
            QLog.branch_code,
            QLog.qlog_date,
            func.count(QLog.id).label('checkin_count')
        ).filter(and_(*filters)).group_by(QLog.branch_code, QLog.qlog_date).all()

        by_branch_date = []
        for r in by_branch_date_query:
            by_branch_date.append({
                'branch_code': r.branch_code,
                'branch_name': branch_map.get(r.branch_code, r.branch_code),
                'date': r.qlog_date,
                'checkin_count': r.checkin_count
            })

        return {
            'has_data': True,
            'by_branch': by_branch,
            'by_branch_date': by_branch_date
        }
    finally:
        session.close()


@st.cache_data(ttl=3600)
def get_branch_list_forecast():
    """Get list of all branches that have appointments."""
    session = get_session()
    try:
        branch_map = get_branch_name_map_cached()

        branches = session.query(
            Appointment.branch_code
        ).filter(
            Appointment.branch_code.isnot(None),
            Appointment.branch_code != ''
        ).distinct().order_by(Appointment.branch_code).all()

        result = []
        for b in branches:
            code = b.branch_code
            name = branch_map.get(code, code)
            result.append((code, name))

        return result
    finally:
        session.close()


@st.cache_data(ttl=3600)
def get_upcoming_appointments_full(selected_branches=None, start_date=None, end_date=None, include_all_status=False):
    """
    Get detailed appointments for workload forecasting.
    Includes capacity comparison from BranchMaster.max_capacity.

    Args:
        selected_branches: tuple of branch codes to filter (None = all)
        start_date: start date for range (default: today)
        end_date: end date for range (default: 30 days from start)
        include_all_status: if True, include all appointment statuses (for historical data)
                           if False, only include SUCCESS and WAITING (for future forecast)
    """
    start_time = time.perf_counter()
    session = get_session()
    try:
        today = date.today()
        # Default to today if no start_date provided
        if start_date is None:
            start_date = today
        # Default to 30 days from start if no end_date provided
        if end_date is None:
            end_date = start_date + timedelta(days=29)

        # Check if we have Appointment data
        has_appt_data = session.query(Appointment).first() is not None

        if not has_appt_data:
            return {
                'has_data': False,
                'today': 0,
                'tomorrow': 0,
                'next_7_days': 0,
                'next_30_days': 0,
                'daily_data': [],
                'by_center': [],
                'by_center_daily': [],
                'over_capacity_count': 0,
                'warning_count': 0,
                'max_date': None
            }

        # Build base filter
        base_filters = [
            Appointment.appt_date >= start_date,
            Appointment.appt_date <= end_date,
        ]

        # Filter by status based on mode
        if not include_all_status:
            # Future forecast: only confirmed or waiting appointments
            base_filters.append(Appointment.appt_status.in_(['SUCCESS', 'WAITING']))

        if selected_branches and len(selected_branches) > 0:
            base_filters.append(Appointment.branch_code.in_(selected_branches))

        # Get max appointment date in future
        max_future_date = session.query(func.max(Appointment.appt_date)).filter(
            and_(*base_filters)
        ).scalar()

        if not max_future_date:
            return {
                'has_data': False,
                'today': 0,
                'tomorrow': 0,
                'next_7_days': 0,
                'next_30_days': 0,
                'daily_data': [],
                'by_center': [],
                'by_center_daily': [],
                'over_capacity_count': 0,
                'warning_count': 0,
                'max_date': None
            }

        # Counts - use start_date as base (not today)
        # For "day 1" and "day 2" labels based on selected range
        day1_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters), Appointment.appt_date == start_date
        ).scalar() or 0

        day2 = start_date + timedelta(days=1)
        day2_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters), Appointment.appt_date == day2
        ).scalar() or 0

        # Calculate 7 days and 30 days from start_date
        day7_end = start_date + timedelta(days=6)
        day7_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters),
            Appointment.appt_date >= start_date,
            Appointment.appt_date <= day7_end
        ).scalar() or 0

        day30_end = start_date + timedelta(days=29)
        day30_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters),
            Appointment.appt_date >= start_date,
            Appointment.appt_date <= day30_end
        ).scalar() or 0

        # Get capacity map from BranchMaster
        # Exclude mobile units (-MB-) from total_capacity as they operate on-demand (max 160/day)
        # Mobile units have branch_code like ACR-MB-S-001, BKK-MB-S-001 (contains -MB-)
        capacity_map = {}
        total_capacity = 0
        branch_capacities = session.query(
            BranchMaster.branch_code,
            BranchMaster.max_capacity
        ).filter(BranchMaster.max_capacity.isnot(None)).all()
        for bc in branch_capacities:
            capacity_map[bc.branch_code] = bc.max_capacity
            # Only add to total_capacity if NOT a mobile unit (contains -MB-)
            if '-MB-' not in str(bc.branch_code).upper():
                total_capacity += bc.max_capacity

        # Daily breakdown
        chart_end_date = min(end_date, max_future_date)
        daily_appts = session.query(
            Appointment.appt_date,
            func.count(func.distinct(Appointment.appointment_id)).label('total')
        ).filter(
            and_(*base_filters),
            Appointment.appt_date <= chart_end_date
        ).group_by(Appointment.appt_date).order_by(Appointment.appt_date).all()

        daily_data = [{'date': d.appt_date, 'count': d.total} for d in daily_appts]

        # By center (all centers, not just top 15)
        branch_map = get_branch_name_map_cached()
        short_name_map = get_branch_short_name_map()
        by_center_query = session.query(
            Appointment.branch_code,
            func.count(func.distinct(Appointment.appointment_id)).label('total')
        ).filter(
            and_(*base_filters),
            Appointment.appt_date <= chart_end_date
        ).group_by(Appointment.branch_code).order_by(
            func.count(func.distinct(Appointment.appointment_id)).desc()
        ).all()

        # First get daily counts per branch, then find max
        # Step 1: Get count per branch per day
        daily_counts_subq = session.query(
            Appointment.branch_code,
            Appointment.appt_date,
            func.count(func.distinct(Appointment.appointment_id)).label('daily_count')
        ).filter(
            and_(*base_filters),
            Appointment.appt_date <= chart_end_date
        ).group_by(Appointment.branch_code, Appointment.appt_date).subquery()

        # Step 2: Get max daily count per branch
        max_daily_per_branch = session.query(
            daily_counts_subq.c.branch_code,
            func.max(daily_counts_subq.c.daily_count).label('max_daily')
        ).group_by(daily_counts_subq.c.branch_code).all()

        max_daily_map = {r.branch_code: r.max_daily for r in max_daily_per_branch}

        by_center = []
        for c in by_center_query:
            capacity = capacity_map.get(c.branch_code)
            max_daily = max_daily_map.get(c.branch_code, 0)
            # Calculate average daily based on days_ahead
            days_in_range = (chart_end_date - today).days + 1
            avg_daily = c.total / days_in_range if days_in_range > 0 else c.total

            # Use max_daily for status calculation (more accurate for detecting over-capacity days)
            status = 'normal'
            max_usage_pct = None
            if capacity and max_daily:
                max_usage_pct = (max_daily / capacity) * 100
                if max_usage_pct >= 100:
                    status = 'over'
                elif max_usage_pct >= 80:
                    status = 'warning'

            # Also calculate avg usage for reference
            avg_usage_pct = (avg_daily / capacity) * 100 if capacity else None

            by_center.append({
                'branch_code': c.branch_code,
                'branch_name': short_name_map.get(c.branch_code, branch_map.get(c.branch_code, c.branch_code)),
                'count': c.total,
                'avg_daily': round(avg_daily, 1),
                'max_daily': max_daily,
                'capacity': capacity,
                'usage_pct': round(avg_usage_pct, 1) if avg_usage_pct else None,
                'max_usage_pct': round(max_usage_pct, 1) if max_usage_pct else None,
                'status': status
            })

        # By center daily breakdown (for detailed view)
        by_center_daily_query = session.query(
            Appointment.branch_code,
            Appointment.appt_date,
            func.count(func.distinct(Appointment.appointment_id)).label('total')
        ).filter(
            and_(*base_filters),
            Appointment.appt_date <= chart_end_date
        ).group_by(Appointment.branch_code, Appointment.appt_date).all()

        by_center_daily = []
        over_capacity_count = 0
        warning_count = 0
        for c in by_center_daily_query:
            capacity = capacity_map.get(c.branch_code)
            status = 'normal'
            usage_pct = None
            if capacity:
                usage_pct = (c.total / capacity) * 100
                if usage_pct >= 100:
                    status = 'over'
                    over_capacity_count += 1
                elif usage_pct >= 80:
                    status = 'warning'
                    warning_count += 1

            by_center_daily.append({
                'branch_code': c.branch_code,
                'branch_name': short_name_map.get(c.branch_code, branch_map.get(c.branch_code, c.branch_code)),
                'date': c.appt_date,
                'count': c.total,
                'capacity': capacity,
                'usage_pct': round(usage_pct, 1) if usage_pct else None,
                'status': status
            })

        return {
            'has_data': True,
            'day1': day1_count,
            'day2': day2_count,
            'day7': day7_count,
            'day30': day30_count,
            'daily_data': daily_data,
            'by_center': by_center,
            'by_center_daily': by_center_daily,
            'over_capacity_count': over_capacity_count,
            'warning_count': warning_count,
            'max_date': max_future_date,
            'total_capacity': total_capacity,
            'start_date': start_date,
            'end_date': end_date
        }
    finally:
        session.close()
        duration = (time.perf_counter() - start_time) * 1000
        log_perf("get_upcoming_appointments_full", duration)


st.set_page_config(page_title="ปริมาณการนัดหมาย - Bio Dashboard", page_icon="📆", layout="wide")

require_login()
apply_theme()

# Page Header
st.markdown("""
<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #e5e7eb;">
    <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #8B5CF6, #6366F1); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
        <span style="font-size: 24px;">📆</span>
    </div>
    <div>
        <h1 style="font-size: 1.75rem; font-weight: 700; color: #1f2937; margin: 0;">ปริมาณการนัดหมาย</h1>
        <p style="font-size: 0.9rem; color: #6b7280; margin: 0;">Upcoming Appointments - นัดหมายล่วงหน้า</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Refresh button
col_title, col_refresh = st.columns([6, 1])
with col_refresh:
    if st.button("🔄 รีเฟรช", use_container_width=True, help="รีเฟรชข้อมูลใหม่"):
        st.cache_data.clear()
        st.rerun()

# Filter Section
st.markdown("### 📅 ตัวกรองข้อมูล")

branch_list = get_branch_list_forecast()
branch_options = {code: name if name and name != code else code for code, name in branch_list}

# Date range selection
today = date.today()

# View mode selection (3 options)
view_mode = st.radio(
    "📊 โหมดแสดงผล",
    options=["future", "history", "custom"],
    format_func=lambda x: {
        "future": "🔮 นัดหมายล่วงหน้า",
        "history": "📜 ข้อมูลย้อนหลัง",
        "custom": "⚙️ กำหนดเอง"
    }[x],
    horizontal=True,
    key="view_mode",
    help="เลือกโหมดการดูข้อมูล"
)

col_filter1, col_filter2 = st.columns([3, 4])

with col_filter1:
    if branch_list:
        selected_branch_codes = st.multiselect(
            "🏢 เลือกศูนย์ (เว้นว่างเพื่อดูทั้งหมด)",
            options=list(branch_options.keys()),
            format_func=lambda x: branch_options.get(x, x),
            key="forecast_branches",
            placeholder="ทุกศูนย์"
        )
    else:
        selected_branch_codes = []

# Set defaults based on view mode
include_all_status = False

if view_mode == "future":
    # Future mode: preset days ahead, only SUCCESS/WAITING
    col_date1, col_date2, col_date3 = st.columns([2, 2, 1])
    with col_date1:
        days_preset = st.selectbox(
            "ช่วงเวลา",
            options=[7, 14, 30, 60, 90],
            index=2,
            format_func=lambda x: f"{x} วันข้างหน้า",
            key="days_preset"
        )
    start_date = today
    end_date = today + timedelta(days=days_preset - 1)
    include_all_status = False
    with col_date2:
        st.markdown(f"**ช่วงวันที่:** {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")
        st.caption("🔮 แสดงเฉพาะนัดหมายที่ยืนยัน (SUCCESS, WAITING)")

elif view_mode == "history":
    # History mode: preset days back, all statuses
    col_date1, col_date2, col_date3 = st.columns([2, 2, 1])
    with col_date1:
        days_back = st.selectbox(
            "ช่วงเวลา",
            options=[7, 14, 30, 60, 90],
            index=2,
            format_func=lambda x: f"{x} วันย้อนหลัง",
            key="days_back"
        )
    end_date = today - timedelta(days=1)  # Yesterday
    start_date = end_date - timedelta(days=days_back - 1)
    include_all_status = True
    with col_date2:
        st.markdown(f"**ช่วงวันที่:** {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")
        st.caption("📜 แสดงข้อมูลทุกสถานะ (รวม CANCEL, EXPIRED)")

else:
    # Custom mode: user selects dates and status filter
    col_date1, col_date2, col_date3 = st.columns([2, 2, 1])
    with col_date1:
        start_date = st.date_input(
            "📅 วันที่เริ่มต้น",
            value=today - timedelta(days=30),
            min_value=today - timedelta(days=730),
            max_value=today + timedelta(days=365),
            key="start_date"
        )
    with col_date2:
        end_date = st.date_input(
            "📅 วันที่สิ้นสุด",
            value=today + timedelta(days=29),
            min_value=start_date,
            max_value=start_date + timedelta(days=365),
            key="end_date"
        )

    # Status filter for custom mode
    include_all_status = st.checkbox(
        "📋 รวมทุกสถานะ (CANCEL, EXPIRED, etc.)",
        value=start_date < today,  # Default to True if looking at past dates
        key="include_all_status",
        help="เลือกเพื่อรวมนัดหมายที่ถูกยกเลิกหรือหมดอายุ"
    )

    if include_all_status:
        st.caption("📋 แสดงข้อมูลทุกสถานะ")
    else:
        st.caption("🔮 แสดงเฉพาะนัดหมายที่ยืนยัน (SUCCESS, WAITING)")

# Reset button
if view_mode != "custom":
    with col_date3:
        if st.button("🔄 Reset", use_container_width=True):
            for key in ['forecast_branches', 'view_mode', 'days_preset', 'days_back', 'start_date', 'end_date', 'include_all_status']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
else:
    col_reset = st.columns([4, 1])[1]
    with col_reset:
        if st.button("🔄 Reset", use_container_width=True, key="reset_custom"):
            for key in ['forecast_branches', 'view_mode', 'days_preset', 'days_back', 'start_date', 'end_date', 'include_all_status']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

# Calculate days in range for display
days_in_range = (end_date - start_date).days + 1

# Mode indicator
mode_label = {
    "future": "🔮 นัดหมายล่วงหน้า",
    "history": "📜 ข้อมูลย้อนหลัง",
    "custom": "⚙️ กำหนดเอง"
}[view_mode]
status_label = "ทุกสถานะ" if include_all_status else "เฉพาะ SUCCESS/WAITING"
st.caption(f"📌 {mode_label} | {days_in_range} วัน ({start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}) | {status_label}")

selected_branches = tuple(selected_branch_codes) if selected_branch_codes else None

# Get Data
stats = get_upcoming_appointments_full(selected_branches, start_date, end_date, include_all_status)

# Branch short name map for display (used in treemap, bar chart, table)
short_name_map = get_branch_short_name_map()

if stats['has_data']:
    # Summary Metrics
    st.markdown("---")
    st.markdown("### 📊 สรุปภาพรวม")

    # Dynamic labels based on view mode
    if view_mode == "future":
        day1_label = "📅 วันนี้"
        day2_label = "📆 พรุ่งนี้"
    elif view_mode == "history":
        day1_label = f"📅 {start_date.strftime('%d/%m')}"
        day2_label = f"📆 {(start_date + timedelta(days=1)).strftime('%d/%m')}"
    else:
        day1_label = f"📅 {start_date.strftime('%d/%m')}"
        day2_label = f"📆 {(start_date + timedelta(days=1)).strftime('%d/%m')}"

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric(day1_label, f"{stats['day1']:,}")
    with col2:
        st.metric(day2_label, f"{stats['day2']:,}")
    with col3:
        st.metric("📊 7 วัน", f"{stats['day7']:,}", help=f"ตั้งแต่ {start_date.strftime('%d/%m')} - {(start_date + timedelta(days=6)).strftime('%d/%m')}")
    with col4:
        st.metric("📈 30 วัน", f"{stats['day30']:,}", help=f"ตั้งแต่ {start_date.strftime('%d/%m')} - {(start_date + timedelta(days=29)).strftime('%d/%m')}")
    with col5:
        st.metric("🔴 เกิน Capacity", f"{stats['over_capacity_count']:,}", help="นับรวมทุกศูนย์ทุกวัน — เช่น ศูนย์ A เกิน 3 วัน + ศูนย์ B เกิน 2 วัน = 5")
    with col6:
        st.metric("🟡 ใกล้เต็ม (≥80%)", f"{stats['warning_count']:,}", help="นับรวมทุกศูนย์ทุกวัน ที่ใช้งาน ≥80% ของ Capacity")

    # Alerts
    if stats['over_capacity_count'] > 0:
        # Count distinct centers that are over capacity
        over_centers = set()
        for c in stats.get('by_center', []):
            if c.get('status') == 'over':
                over_centers.add(c['branch_code'])
        n_centers = len(over_centers)
        st.error(f"⚠️ **แจ้งเตือน:** พบ **{n_centers} ศูนย์** มีวันที่นัดหมายเกิน Capacity (รวม {stats['over_capacity_count']:,} ศูนย์×วัน) — ดูรายละเอียดในตารางด้านล่าง")
    if stats['warning_count'] > 0:
        st.warning(f"⚡ **เฝ้าระวัง:** พบ {stats['warning_count']} ศูนย์/วัน ที่มีนัดหมาย ≥80% ของ Capacity")

    st.markdown("---")

    # Tab Layout for different views
    tab1, tab2, tab3 = st.tabs(["📊 รายวัน", "🏢 รายศูนย์", "📋 ตารางรายละเอียด"])

    with tab1:
        st.markdown("### 📊 ปริมาณนัดหมายรายวัน")
        st.caption(f"📌 แสดงข้อมูล {days_in_range} วัน ({start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')})")

        if stats['daily_data'] and stats['by_center_daily']:
            upcoming_df = pd.DataFrame(stats['daily_data'])
            today_dt = date.today()

            # Calculate daily data by center type from by_center_daily
            daily_by_type = {}
            for item in stats['by_center_daily']:
                d = item['date']
                branch_code = str(item['branch_code']).upper()
                count = item['count']

                if d not in daily_by_type:
                    daily_by_type[d] = {'ob': 0, 'sc': 0, 'other': 0}

                if '-OB-' in branch_code:
                    daily_by_type[d]['ob'] += count
                elif '-SC-' in branch_code:
                    daily_by_type[d]['sc'] += count
                else:
                    daily_by_type[d]['other'] += count

            # Sort dates and prepare data
            sorted_dates = sorted(daily_by_type.keys())
            upcoming_dates = [d.strftime('%d/%m') if hasattr(d, 'strftime') else str(d) for d in sorted_dates]
            ob_data = [daily_by_type[d]['ob'] for d in sorted_dates]
            sc_data = [daily_by_type[d]['sc'] for d in sorted_dates]
            other_data = [daily_by_type[d]['other'] for d in sorted_dates]
            total_data = [daily_by_type[d]['ob'] + daily_by_type[d]['sc'] + daily_by_type[d]['other'] for d in sorted_dates]

            # Calculate average line and get total capacity
            avg_count = sum(total_data) / len(total_data) if total_data else 0
            total_capacity = stats.get('total_capacity', 0)

            # Calculate capacity by type
            ob_capacity = 0
            sc_capacity = 0
            for c in stats['by_center']:
                branch_code = str(c['branch_code']).upper()
                cap = c['capacity'] or 0
                if '-OB-' in branch_code:
                    ob_capacity += cap
                elif '-SC-' in branch_code:
                    sc_capacity += cap

            # Calculate averages
            avg_ob = sum(ob_data) / len(ob_data) if ob_data else 0
            avg_sc = sum(sc_data) / len(sc_data) if sc_data else 0

            # Calculate 80% warning threshold
            ob_warning_80 = int(ob_capacity * 0.8) if ob_capacity else 0
            sc_warning_80 = int(sc_capacity * 0.8) if sc_capacity else 0

            # ===== Chart 1: ศูนย์แรกรับ (OB) =====
            st.markdown("#### 🟣 ศูนย์แรกรับ (OB)")
            ob_chart_options = {
                "animation": True,
                "animationDuration": 800,
                "backgroundColor": "transparent",
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "cross"},
                    "backgroundColor": "rgba(255, 255, 255, 0.95)",
                    "borderColor": "#d1d5db",
                    "textStyle": {"color": "#374151"},
                },
                "legend": {
                    "data": ["แรกรับ (OB)", "Capacity OB", "80% Warning", "ค่าเฉลี่ย OB"],
                    "bottom": 0,
                    "textStyle": {"color": "#6b7280"},
                },
                "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "10%", "containLabel": True},
                "xAxis": {
                    "type": "category",
                    "data": upcoming_dates,
                    "axisLine": {"lineStyle": {"color": "#d1d5db"}},
                    "axisLabel": {"color": "#6b7280", "rotate": 45 if len(upcoming_dates) > 15 else 0},
                },
                "yAxis": {
                    "type": "value",
                    "axisLine": {"lineStyle": {"color": "#d1d5db"}},
                    "axisLabel": {"color": "#6b7280"},
                    "splitLine": {"lineStyle": {"color": "#e5e7eb"}},
                },
                "series": [
                    {
                        "name": "แรกรับ (OB)",
                        "type": "bar",
                        "data": ob_data,
                        "itemStyle": {"color": "#8B5CF6"},
                        "barMaxWidth": 50,
                        "label": {
                            "show": len(upcoming_dates) <= 14,
                            "position": "top",
                            "color": "#6b7280",
                            "fontSize": 10,
                        }
                    },
                    {
                        "name": "Capacity OB",
                        "type": "line",
                        "data": [ob_capacity] * len(upcoming_dates),
                        "itemStyle": {"color": "#10B981"},
                        "lineStyle": {"width": 3, "type": "solid"},
                        "symbol": "none",
                    },
                    {
                        "name": "80% Warning",
                        "type": "line",
                        "data": [ob_warning_80] * len(upcoming_dates),
                        "itemStyle": {"color": "#F59E0B"},
                        "lineStyle": {"width": 2, "type": "dashed"},
                        "symbol": "none",
                    },
                    {
                        "name": "ค่าเฉลี่ย OB",
                        "type": "line",
                        "data": [round(avg_ob)] * len(upcoming_dates),
                        "itemStyle": {"color": "#EF4444"},
                        "lineStyle": {"width": 2, "type": "dotted"},
                        "symbol": "none",
                    }
                ]
            }
            st.markdown(f"**เส้นเขียว** = Capacity ({ob_capacity:,}) | **เส้นประเหลือง** = 80% ({ob_warning_80:,}) | **เส้นจุดแดง** = ค่าเฉลี่ย ({round(avg_ob):,})")
            st_echarts(options=ob_chart_options, height="350px", key="forecast_ob_chart")

            # ===== Chart 2: ศูนย์บริการ (SC) =====
            st.markdown("#### 🔵 ศูนย์บริการ (SC)")
            sc_chart_options = {
                "animation": True,
                "animationDuration": 800,
                "backgroundColor": "transparent",
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "cross"},
                    "backgroundColor": "rgba(255, 255, 255, 0.95)",
                    "borderColor": "#d1d5db",
                    "textStyle": {"color": "#374151"},
                },
                "legend": {
                    "data": ["บริการ (SC)", "Capacity SC", "80% Warning", "ค่าเฉลี่ย SC"],
                    "bottom": 0,
                    "textStyle": {"color": "#6b7280"},
                },
                "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "10%", "containLabel": True},
                "xAxis": {
                    "type": "category",
                    "data": upcoming_dates,
                    "axisLine": {"lineStyle": {"color": "#d1d5db"}},
                    "axisLabel": {"color": "#6b7280", "rotate": 45 if len(upcoming_dates) > 15 else 0},
                },
                "yAxis": {
                    "type": "value",
                    "axisLine": {"lineStyle": {"color": "#d1d5db"}},
                    "axisLabel": {"color": "#6b7280"},
                    "splitLine": {"lineStyle": {"color": "#e5e7eb"}},
                },
                "series": [
                    {
                        "name": "บริการ (SC)",
                        "type": "bar",
                        "data": sc_data,
                        "itemStyle": {"color": "#3B82F6"},
                        "barMaxWidth": 50,
                        "label": {
                            "show": len(upcoming_dates) <= 14,
                            "position": "top",
                            "color": "#6b7280",
                            "fontSize": 10,
                        }
                    },
                    {
                        "name": "Capacity SC",
                        "type": "line",
                        "data": [sc_capacity] * len(upcoming_dates),
                        "itemStyle": {"color": "#10B981"},
                        "lineStyle": {"width": 3, "type": "solid"},
                        "symbol": "none",
                    },
                    {
                        "name": "80% Warning",
                        "type": "line",
                        "data": [sc_warning_80] * len(upcoming_dates),
                        "itemStyle": {"color": "#F59E0B"},
                        "lineStyle": {"width": 2, "type": "dashed"},
                        "symbol": "none",
                    },
                    {
                        "name": "ค่าเฉลี่ย SC",
                        "type": "line",
                        "data": [round(avg_sc)] * len(upcoming_dates),
                        "itemStyle": {"color": "#EF4444"},
                        "lineStyle": {"width": 2, "type": "dotted"},
                        "symbol": "none",
                    }
                ]
            }
            st.markdown(f"**เส้นเขียว** = Capacity ({sc_capacity:,}) | **เส้นประเหลือง** = 80% ({sc_warning_80:,}) | **เส้นจุดแดง** = ค่าเฉลี่ย ({round(avg_sc):,})")
            st_echarts(options=sc_chart_options, height="350px", key="forecast_sc_chart")

            # Summary by type
            total_ob = sum(ob_data)
            total_sc = sum(sc_data)
            total_other = sum(other_data)

            st.markdown("---")
            st.markdown("#### 📊 สรุปรวม")
            col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
            with col_sum1:
                st.metric("🟣 แรกรับ (OB)", f"{total_ob:,}", help=f"Capacity: {ob_capacity:,}/วัน")
            with col_sum2:
                st.metric("🔵 บริการ (SC)", f"{total_sc:,}", help=f"Capacity: {sc_capacity:,}/วัน")
            with col_sum3:
                st.metric("⬛ อื่นๆ (MB)", f"{total_other:,}", help="รวมหน่วยเคลื่อนที่")
            with col_sum4:
                st.metric("📊 รวมทั้งหมด", f"{total_ob + total_sc + total_other:,}")

            # Daily stats table
            with st.expander("📋 ดูข้อมูลรายวัน"):
                table_data = []
                for d in sorted_dates:
                    table_data.append({
                        'วันที่': d.strftime('%d/%m/%Y') if hasattr(d, 'strftime') else str(d),
                        'แรกรับ (OB)': daily_by_type[d]['ob'],
                        'บริการ (SC)': daily_by_type[d]['sc'],
                        'อื่นๆ': daily_by_type[d]['other'],
                        'รวม': daily_by_type[d]['ob'] + daily_by_type[d]['sc'] + daily_by_type[d]['other']
                    })
                display_df = pd.DataFrame(table_data)
                st.dataframe(display_df, hide_index=True, use_container_width=True)
        else:
            st.info("ไม่มีข้อมูลนัดหมายในช่วงเวลาที่เลือก")

    with tab2:
        st.markdown("### 🏢 ปริมาณนัดหมายรายศูนย์")
        st.caption(f"📌 แสดงข้อมูล {days_in_range} วัน ({start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}) เทียบกับ Capacity ต่อวัน")

        if stats['by_center']:
            # Treemap - Appointments vs Capacity
            st.markdown("#### 🗺️ Treemap: ปริมาณนัดหมาย vs Capacity")

            # Treemap view mode selector
            treemap_col1, treemap_col2, treemap_col3 = st.columns([2, 1, 1])
            with treemap_col2:
                treemap_mode = st.radio(
                    "มุมมอง",
                    options=["รายวัน", "รายช่วง"],
                    horizontal=True,
                    key="treemap_mode"
                )
            with treemap_col3:
                center_type_filter = st.radio(
                    "ประเภทศูนย์",
                    options=["ทั้งหมด", "แรกรับ (OB)", "บริการ (SC)"],
                    horizontal=True,
                    key="center_type_filter"
                )

            st.markdown("**ขนาดกล่อง** = ปริมาณนัดหมาย | **สี** (จากวันที่มากสุด) = 🟢 ปกติ (<80%) | 🟡 ใกล้เต็ม (80-99%) | 🔴 เต็ม/เกิน (≥100%) | ⚫ ไม่มี Capacity")

            # Use days_in_range from filter selection
            treemap_days = days_in_range

            # Filter centers by type
            filtered_centers = stats['by_center']
            if center_type_filter == "แรกรับ (OB)":
                filtered_centers = [c for c in stats['by_center'] if '-OB-' in str(c['branch_code']).upper()]
            elif center_type_filter == "บริการ (SC)":
                filtered_centers = [c for c in stats['by_center'] if '-SC-' in str(c['branch_code']).upper()]

            # Prepare treemap data based on mode
            treemap_data = []
            for c in filtered_centers:
                capacity = c['capacity']
                max_daily = c.get('max_daily', 0)

                if treemap_mode == "รายวัน":
                    # Daily view: use max_daily for color, avg_daily for display
                    display_value = c['avg_daily']
                    value_label = f"เฉลี่ย {c['avg_daily']:.0f}, สูงสุด {max_daily}/วัน"
                    capacity_label = f"{capacity:,}/วัน" if capacity else "N/A"
                else:
                    # Range view: use total count vs range capacity (capacity * days)
                    display_value = c['count']
                    range_capacity = capacity * treemap_days if capacity else None
                    value_label = f"{c['count']:,} ({treemap_days} วัน)"
                    capacity_label = f"{range_capacity:,} ({treemap_days} วัน)" if range_capacity else "N/A"

                # Use max_usage_pct for color (from pre-calculated status)
                # This reflects the worst-case day, not average
                max_usage_pct = c.get('max_usage_pct')
                status = c.get('status', 'normal')

                # Determine color based on max_usage_pct (worst day)
                # 🟢 Green = <80%, 🟡 Yellow = 80-99%, 🔴 Red = ≥100%
                if capacity is None:
                    color = '#6B7280'  # Gray - no capacity data
                    status = 'unknown'
                elif max_usage_pct and max_usage_pct >= 100:
                    color = '#EF4444'  # Red - ≥100%
                    status = 'over'
                elif max_usage_pct and max_usage_pct >= 80:
                    color = '#F59E0B'  # Yellow - 80-99%
                    status = 'warning'
                else:
                    color = '#10B981'  # Green - <80%
                    status = 'normal'

                usage_text = f"สูงสุด {max_usage_pct:.0f}%" if max_usage_pct else "N/A"

                # Use short name for display, fall back to branch_code
                display_name = short_name_map.get(c['branch_code'], c['branch_code'] or '-')

                treemap_data.append({
                    "name": display_name,
                    "value": round(display_value, 1),
                    "itemStyle": {"color": color},
                    "branch_name": c['branch_name'],  # Full name for tooltip
                    "value_label": value_label,
                    "capacity_label": capacity_label,
                    "usage_pct": usage_text,
                    "status": status
                })

            if treemap_data:
                # Render treemap using components.html with ECharts CDN
                # Note: st_echarts doesn't support treemap type, so we use raw HTML
                treemap_chart_data = [
                    {
                        "name": item["name"],  # branch_code
                        "value": item["value"],
                        "itemStyle": item["itemStyle"],
                    }
                    for item in treemap_data
                ]

                treemap_html = f'''
                <div id="treemap" style="width: 100%; height: 400px;"></div>
                <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
                <script>
                    var chart = echarts.init(document.getElementById('treemap'));
                    var option = {{
                        backgroundColor: 'transparent',
                        tooltip: {{
                            trigger: 'item',
                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                            borderColor: '#d1d5db',
                            borderRadius: 8,
                            padding: [10, 14],
                            textStyle: {{color: '#374151', fontSize: 13}},
                        }},
                        series: [{{
                            type: 'treemap',
                            data: {json.dumps(treemap_chart_data, ensure_ascii=False)},
                            roam: false,
                            nodeClick: false,
                            width: '100%',
                            height: '100%',
                            breadcrumb: {{show: false}},
                            label: {{
                                show: true,
                                color: '#FFFFFF',
                                fontSize: 9,
                                fontWeight: 'bold',
                            }},
                            upperLabel: {{show: false}},
                            itemStyle: {{
                                borderColor: '#e5e7eb',
                                borderWidth: 2,
                                gapWidth: 2
                            }},
                            levels: [{{
                                itemStyle: {{
                                    borderColor: '#e5e7eb',
                                    borderWidth: 2,
                                    gapWidth: 2
                                }}
                            }}]
                        }}]
                    }};
                    chart.setOption(option);
                    window.addEventListener('resize', function() {{
                        chart.resize();
                    }});
                </script>
                '''
                components.html(treemap_html, height=420)

                # Show mode description and stats
                type_desc = ""
                if center_type_filter == "แรกรับ (OB)":
                    type_desc = " (เฉพาะศูนย์แรกรับ)"
                elif center_type_filter == "บริการ (SC)":
                    type_desc = " (เฉพาะศูนย์บริการ)"

                if treemap_mode == "รายวัน":
                    st.caption(f"📌 แสดงค่าเฉลี่ยนัดหมายต่อวัน เทียบกับ Capacity ต่อวัน{type_desc} | จำนวน {len(filtered_centers)} ศูนย์")
                else:
                    st.caption(f"📌 แสดงนัดหมายรวม {treemap_days} วัน เทียบกับ Capacity รวม{type_desc} | จำนวน {len(filtered_centers)} ศูนย์")
            else:
                st.info(f"ไม่พบข้อมูลศูนย์ประเภท {center_type_filter}")

            st.markdown("---")

            col1, col2 = st.columns([3, 2])

            with col1:
                # Horizontal bar chart - top 20 (filtered by center type)
                bar_centers = filtered_centers[:20] if filtered_centers else stats['by_center'][:20]
                center_names = [short_name_map.get(c['branch_code'], c['branch_name']) for c in reversed(bar_centers)]
                center_avg = [c['avg_daily'] for c in reversed(bar_centers)]
                center_capacity = [c['capacity'] if c['capacity'] else 0 for c in reversed(bar_centers)]
                center_colors = []
                for c in reversed(bar_centers):
                    if c['status'] == 'over':
                        center_colors.append('#EF4444')
                    elif c['status'] == 'warning':
                        center_colors.append('#F59E0B')
                    else:
                        center_colors.append('#10B981')

                bar_title = "Top 20 ศูนย์"
                if center_type_filter == "แรกรับ (OB)":
                    bar_title = "ศูนย์แรกรับ (OB)"
                elif center_type_filter == "บริการ (SC)":
                    bar_title = "ศูนย์บริการ (SC)"

                # Render horizontal bar chart using components.html
                bar_data = [{"value": v, "itemStyle": {"color": c}} for v, c in zip(center_avg, center_colors)]

                bar_html = f'''
                <div id="center_bar" style="width: 100%; height: 600px;"></div>
                <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
                <script>
                    var chart = echarts.init(document.getElementById('center_bar'));
                    var option = {{
                        backgroundColor: 'transparent',
                        tooltip: {{
                            trigger: 'axis',
                            axisPointer: {{type: 'shadow'}},
                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                            borderColor: '#d1d5db',
                            textStyle: {{color: '#374151'}},
                        }},
                        legend: {{
                            data: ['เฉลี่ย/วัน', 'Capacity'],
                            bottom: 0,
                            textStyle: {{color: '#6b7280'}},
                        }},
                        grid: {{left: '3%', right: '10%', bottom: '12%', top: '5%', containLabel: true}},
                        xAxis: {{
                            type: 'value',
                            axisLine: {{lineStyle: {{color: '#d1d5db'}}}},
                            axisLabel: {{color: '#6b7280'}},
                            splitLine: {{lineStyle: {{color: '#e5e7eb'}}}},
                        }},
                        yAxis: {{
                            type: 'category',
                            data: {json.dumps(center_names, ensure_ascii=False)},
                            axisLine: {{lineStyle: {{color: '#d1d5db'}}}},
                            axisLabel: {{color: '#6b7280', fontSize: 10}},
                        }},
                        series: [
                            {{
                                name: 'เฉลี่ย/วัน',
                                type: 'bar',
                                data: {json.dumps(bar_data)},
                                barMaxWidth: 20,
                                label: {{
                                    show: true,
                                    position: 'right',
                                    color: '#6b7280',
                                    fontSize: 9,
                                    formatter: '{{c}}'
                                }}
                            }},
                            {{
                                name: 'Capacity',
                                type: 'scatter',
                                data: {json.dumps(center_capacity)},
                                symbol: 'diamond',
                                symbolSize: 12,
                                itemStyle: {{color: '#374151', borderColor: '#e5e7eb', borderWidth: 1}}
                            }}
                        ]
                    }};
                    chart.setOption(option);
                    window.addEventListener('resize', function() {{
                        chart.resize();
                    }});
                </script>
                '''
                st.markdown(f"**{bar_title}** | 🔴 เกิน Capacity | 🟡 ≥80% | 🟢 ปกติ | ◆ = Capacity")
                components.html(bar_html, height=620)

            with col2:
                st.markdown("**📋 สรุป Capacity รายศูนย์**")

                # Filter options
                status_filter = st.selectbox(
                    "กรองตามสถานะ",
                    options=["ทั้งหมด", "🔴 เกิน Capacity", "🟡 ใกล้เต็ม", "🟢 ปกติ"],
                    index=0
                )

                # Use filtered_centers from Treemap filter (already filtered by center type)
                table_centers = filtered_centers if filtered_centers else stats['by_center']
                if status_filter == "🔴 เกิน Capacity":
                    table_centers = [c for c in table_centers if c['status'] == 'over']
                elif status_filter == "🟡 ใกล้เต็ม":
                    table_centers = [c for c in table_centers if c['status'] == 'warning']
                elif status_filter == "🟢 ปกติ":
                    table_centers = [c for c in table_centers if c['status'] == 'normal']

                table_data = []
                for c in table_centers[:30]:
                    status_icon = "🔴" if c['status'] == 'over' else ("🟡" if c['status'] == 'warning' else "🟢")
                    capacity_str = f"{c['capacity']:,}" if c['capacity'] else "-"
                    usage_str = f"{c['usage_pct']:.0f}%" if c['usage_pct'] else "-"
                    table_data.append({
                        "": status_icon,
                        "ศูนย์": short_name_map.get(c['branch_code'], c['branch_name']),
                        "รวม": f"{c['count']:,}",
                        "เฉลี่ย/วัน": f"{c['avg_daily']:.0f}",
                        "Capacity": capacity_str,
                        "ใช้งาน": usage_str
                    })

                if table_data:
                    df_capacity = pd.DataFrame(table_data)
                    st.dataframe(df_capacity, hide_index=True, use_container_width=True, height=500)
                else:
                    st.info("ไม่มีข้อมูลตามเงื่อนไขที่เลือก")

                st.markdown("""
                <div style="background: #ffffff; border-radius: 8px; padding: 12px; border: 1px solid #e5e7eb; margin-top: 12px;">
                    <p style="color: #6b7280; font-size: 0.8rem; margin: 0;">
                        <b>คำอธิบาย:</b><br>
                        • <b>รวม</b> = นัดหมายทั้งหมดในช่วงเวลา<br>
                        • <b>เฉลี่ย/วัน</b> = รวม ÷ จำนวนวัน<br>
                        • <b>ใช้งาน</b> = (เฉลี่ย/วัน ÷ Capacity) × 100%
                    </p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("ไม่มีข้อมูลนัดหมายในช่วงเวลาที่เลือก")

    with tab3:
        st.markdown("### 📋 ตารางรายละเอียด (ศูนย์ × วัน)")
        st.caption("📌 แสดงจำนวนนัดหมายของแต่ละศูนย์ในแต่ละวัน พร้อมเทียบ Capacity")

        if stats['by_center_daily']:
            # Convert to pivot table
            df_detail = pd.DataFrame(stats['by_center_daily'])

            # Pivot: rows = branch, columns = date
            pivot_df = df_detail.pivot_table(
                index=['branch_code', 'branch_name'],
                columns='date',
                values='count',
                fill_value=0,
                aggfunc='sum'
            ).reset_index()

            # Add capacity column
            capacity_map = {c['branch_code']: c['capacity'] for c in stats['by_center']}
            pivot_df['Capacity'] = pivot_df['branch_code'].map(capacity_map)

            # Reorder columns
            date_cols = [c for c in pivot_df.columns if isinstance(c, date)]
            date_cols_sorted = sorted(date_cols)

            # Format date columns
            col_rename = {d: d.strftime('%d/%m') for d in date_cols_sorted}
            pivot_df = pivot_df.rename(columns=col_rename)

            # Select columns to display
            display_cols = ['branch_name', 'Capacity'] + [col_rename[d] for d in date_cols_sorted]
            display_df = pivot_df[display_cols].copy()
            display_df.columns = ['ศูนย์', 'Capacity/วัน'] + [col_rename[d] for d in date_cols_sorted]

            # Sort by first date column descending
            if len(date_cols_sorted) > 0:
                first_date_col = col_rename[date_cols_sorted[0]]
                display_df = display_df.sort_values(first_date_col, ascending=False)

            # Build HTML table with conditional formatting
            date_col_names = [col_rename[d] for d in date_cols_sorted]

            def get_cell_style(val, capacity):
                """Get background color based on usage vs capacity."""
                if pd.isna(capacity) or capacity <= 0 or pd.isna(val):
                    return ''
                usage_pct = (val / capacity) * 100
                if usage_pct >= 100:
                    return 'background-color: #DC2626; color: white; font-weight: bold;'
                elif usage_pct >= 80:
                    return 'background-color: #D97706; color: white; font-weight: bold;'
                elif usage_pct >= 50:
                    return 'background-color: rgba(16, 185, 129, 0.3);'
                return ''

            # Build HTML table
            html_parts = ['''
            <style>
            .forecast-table { width: 100%; border-collapse: collapse; font-size: 13px; }
            .forecast-table th { background: #f3f4f6; color: #6b7280; padding: 8px 6px; text-align: center; border: 1px solid #e5e7eb; position: sticky; top: 0; }
            .forecast-table td { padding: 6px; text-align: center; border: 1px solid #e5e7eb; }
            .forecast-table tr:hover { background: rgba(59, 130, 246, 0.1); }
            .forecast-table .center-name { text-align: left; min-width: 200px; max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            </style>
            <div style="max-height: 600px; overflow: auto; border: 1px solid #e5e7eb; border-radius: 8px;">
            <table class="forecast-table">
            <thead><tr>
            ''']

            # Header row
            html_parts.append('<th class="center-name">ศูนย์</th>')
            html_parts.append('<th>Capacity/วัน</th>')
            for col in date_col_names:
                html_parts.append(f'<th>{col}</th>')
            html_parts.append('</tr></thead><tbody>')

            # Data rows
            for _, row in display_df.iterrows():
                html_parts.append('<tr>')
                center_name = str(row['ศูนย์'])[:40]
                capacity = row['Capacity/วัน']
                cap_str = f"{int(capacity):,}" if pd.notna(capacity) else '-'

                html_parts.append(f'<td class="center-name" title="{row["ศูนย์"]}">{center_name}</td>')
                html_parts.append(f'<td>{cap_str}</td>')

                for col in date_col_names:
                    val = row[col]
                    style = get_cell_style(val, capacity)
                    val_str = f"{int(val):,}" if pd.notna(val) and val > 0 else '0'
                    html_parts.append(f'<td style="{style}">{val_str}</td>')

                html_parts.append('</tr>')

            html_parts.append('</tbody></table></div>')

            # Legend
            st.markdown("""
            <div style="background: #ffffff; border-radius: 8px; padding: 10px 16px; border: 1px solid #e5e7eb; margin-bottom: 12px;">
                <span style="color: #6b7280; font-size: 0.85rem;">
                    <b>สี:</b>
                    <span style="background: #DC2626; color: white; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🔴 เต็ม/เกิน (≥100%)</span>
                    <span style="background: #D97706; color: white; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🟡 ใกล้เต็ม (80-99%)</span>
                    <span style="background: rgba(16, 185, 129, 0.3); padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🟢 ปกติ (50-79%)</span>
                    <span style="padding: 2px 8px; margin-left: 8px;">⬜ ว่าง (<50%)</span>
                </span>
            </div>
            """, unsafe_allow_html=True)

            # Render HTML table
            st.markdown(''.join(html_parts), unsafe_allow_html=True)

            # Download button
            csv = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 ดาวน์โหลด CSV",
                csv,
                f"forecast_{date.today().strftime('%Y%m%d')}.csv",
                "text/csv",
                key="download_forecast_csv"
            )

            # ============== Check-in Progress Bar Section ==============
            st.markdown("---")
            st.markdown("### 📊 สถานะ Check-in รายศูนย์")
            st.caption("แสดงจำนวน Check-in เทียบกับนัดหมาย (ข้อมูลจาก QLog)")

            # Get check-in data
            checkin_data = get_checkin_data(selected_branches, start_date, end_date)

            if checkin_data['has_data'] and checkin_data['by_branch']:
                # Build checkin lookup by branch_code
                checkin_by_branch = {c['branch_code']: c['checkin_count'] for c in checkin_data['by_branch']}

                # Build checkin lookup by branch_code and date
                checkin_by_branch_date = {}
                for c in checkin_data['by_branch_date']:
                    key = (c['branch_code'], c['date'])
                    checkin_by_branch_date[key] = c['checkin_count']

                # Build progress bar data
                progress_data = []
                for c in stats['by_center']:
                    appt_count = c['count']
                    checkin_count = checkin_by_branch.get(c['branch_code'], 0)
                    capacity = c['capacity']
                    capacity_total = capacity * days_in_range if capacity else None

                    # Calculate check-in rate
                    if appt_count > 0:
                        checkin_rate = (checkin_count / appt_count) * 100
                    else:
                        checkin_rate = 0

                    progress_data.append({
                        'branch_code': c['branch_code'],
                        'branch_name': c['branch_name'],
                        'appt_count': appt_count,
                        'checkin_count': checkin_count,
                        'checkin_rate': checkin_rate,
                        'capacity_total': capacity_total
                    })

                # Sort by check-in rate descending
                progress_data.sort(key=lambda x: x['checkin_rate'], reverse=True)

                # Summary metrics
                total_appt = sum(p['appt_count'] for p in progress_data)
                total_checkin = sum(p['checkin_count'] for p in progress_data)
                overall_rate = (total_checkin / total_appt * 100) if total_appt > 0 else 0

                col_sum1, col_sum2, col_sum3 = st.columns(3)
                with col_sum1:
                    st.metric("📅 นัดหมายทั้งหมด", f"{total_appt:,}")
                with col_sum2:
                    st.metric("✅ Check-in แล้ว", f"{total_checkin:,}")
                with col_sum3:
                    st.metric("📊 อัตรา Check-in", f"{overall_rate:.1f}%")

                st.markdown("")

                # View mode tabs: รวม vs รายวัน
                checkin_view = st.radio(
                    "มุมมอง",
                    options=["📊 รวมตามศูนย์", "📅 รายวัน"],
                    horizontal=True,
                    key="checkin_view_mode"
                )

                if checkin_view == "📊 รวมตามศูนย์":
                    # ========== AGGREGATE VIEW (Progress Bars) ==========

                    # Filter options - MUST be before building HTML
                    show_filter = st.radio(
                        "แสดง",
                        options=["ทั้งหมด", "เฉพาะมี Check-in", "เฉพาะต่ำกว่า 80%"],
                        horizontal=True,
                        key="checkin_filter"
                    )

                    filtered_data = progress_data
                    if show_filter == "เฉพาะมี Check-in":
                        filtered_data = [p for p in progress_data if p['checkin_count'] > 0]
                    elif show_filter == "เฉพาะต่ำกว่า 80%":
                        filtered_data = [p for p in progress_data if p['checkin_rate'] < 80]

                    # Legend
                    st.markdown("""
                    **สี Progress Bar:** 🟢 ≥80% | 🟡 50-79% | 🔴 <50% | 🚀 = มากกว่านัดหมาย (walk-in)
                    """)

                    # Build rows HTML
                    rows_html = ""
                    for p in filtered_data[:50]:
                        rate = p['checkin_rate']
                        if rate >= 80:
                            bar_color = '#10B981'
                        elif rate >= 50:
                            bar_color = '#F59E0B'
                        else:
                            bar_color = '#EF4444'

                        bar_width = round(min(rate, 100), 1)
                        stats_text = f"{p['checkin_count']:,} / {p['appt_count']:,}"
                        rate_display = f"🚀 {rate:.0f}%" if rate > 100 else f"{rate:.0f}%"

                        rows_html += f'''
                        <div class="checkin-row">
                            <div class="checkin-name" title="{p['branch_name']}">{p['branch_code']}</div>
                            <div class="checkin-bar-container">
                                <div class="checkin-bar" style="width: {bar_width}%; background: {bar_color};"></div>
                                <span class="checkin-bar-text">{rate_display}</span>
                            </div>
                            <div class="checkin-stats">{stats_text}</div>
                        </div>
                        '''

                    # Calculate height based on number of items
                    num_items = len(filtered_data[:50])
                    iframe_height = min(500, max(100, num_items * 45 + 20))

                    # Full HTML with styles
                    progress_html = f'''
                    <!DOCTYPE html>
                    <html>
                    <head>
                    <style>
                    body {{ margin: 0; padding: 0; background: transparent; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}
                    .checkin-container {{ max-height: 480px; overflow-y: auto; padding-right: 8px; }}
                    .checkin-row {{ display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #e5e7eb; }}
                    .checkin-name {{ width: 180px; font-size: 13px; color: #374151; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
                    .checkin-bar-container {{ flex: 1; margin: 0 12px; height: 24px; background: #f3f4f6; border-radius: 12px; overflow: hidden; position: relative; }}
                    .checkin-bar {{ height: 100%; border-radius: 12px; }}
                    .checkin-bar-text {{ position: absolute; right: 8px; top: 50%; transform: translateY(-50%); font-size: 11px; color: #374151; font-weight: bold; }}
                    .checkin-stats {{ width: 150px; text-align: right; font-size: 12px; color: #6b7280; }}
                    </style>
                    </head>
                    <body>
                    <div class="checkin-container">
                    {rows_html}
                    </div>
                    </body>
                    </html>
                    '''

                    components.html(progress_html, height=iframe_height, scrolling=True)

                else:
                    # ========== DAILY VIEW (Progress Bars per day) ==========
                    # Get dates from by_center_daily
                    all_dates = sorted(set(c['date'] for c in stats['by_center_daily']))

                    if len(all_dates) > 14:
                        # If more than 14 days, let user select date
                        selected_daily_date = st.select_slider(
                            "เลือกวันที่",
                            options=all_dates,
                            format_func=lambda x: x.strftime('%d/%m/%Y'),
                            key="daily_date_slider"
                        )
                        display_dates = [selected_daily_date]
                    else:
                        display_dates = all_dates

                    # Build appt lookup by branch and date
                    appt_by_branch_date = {}
                    for c in stats['by_center_daily']:
                        key = (c['branch_code'], c['date'])
                        appt_by_branch_date[key] = c['count']

                    # Get unique branches
                    branches_in_data = list(set(c['branch_code'] for c in stats['by_center_daily']))

                    # For each date, show progress bars
                    for d in display_dates:
                        st.markdown(f"#### 📅 {d.strftime('%d/%m/%Y')}")

                        # Calculate daily totals for this date
                        daily_appt_total = sum(appt_by_branch_date.get((b, d), 0) for b in branches_in_data)
                        daily_checkin_total = sum(checkin_by_branch_date.get((b, d), 0) for b in branches_in_data)
                        daily_rate = (daily_checkin_total / daily_appt_total * 100) if daily_appt_total > 0 else 0

                        st.caption(f"นัดหมาย: {daily_appt_total:,} | Check-in: {daily_checkin_total:,} | อัตรา: {daily_rate:.1f}%")

                        # Build data for this date
                        daily_data_list = []
                        for b in branches_in_data:
                            appt = appt_by_branch_date.get((b, d), 0)
                            checkin = checkin_by_branch_date.get((b, d), 0)
                            if appt > 0:
                                rate = (checkin / appt) * 100
                                daily_data_list.append({
                                    'branch_code': b,
                                    'appt': appt,
                                    'checkin': checkin,
                                    'rate': rate
                                })

                        # Sort by rate descending
                        daily_data_list.sort(key=lambda x: x['rate'], reverse=True)

                        # Build rows
                        rows_html = ""
                        for dd in daily_data_list[:30]:
                            rate = dd['rate']
                            if rate >= 80:
                                bar_color = '#10B981'
                            elif rate >= 50:
                                bar_color = '#F59E0B'
                            else:
                                bar_color = '#EF4444'

                            bar_width = round(min(rate, 100), 1)
                            rate_display = f"🚀 {rate:.0f}%" if rate > 100 else f"{rate:.0f}%"

                            rows_html += f'''
                            <div class="daily-row">
                                <div class="daily-name">{dd['branch_code']}</div>
                                <div class="daily-bar-container">
                                    <div class="daily-bar" style="width: {bar_width}%; background: {bar_color};"></div>
                                    <span class="daily-bar-text">{rate_display}</span>
                                </div>
                                <div class="daily-stats">{dd['checkin']:,} / {dd['appt']:,}</div>
                            </div>
                            '''

                        # Calculate height
                        num_items = len(daily_data_list[:30])
                        iframe_height = min(400, max(80, num_items * 38 + 20))

                        daily_html = f'''
                        <!DOCTYPE html>
                        <html>
                        <head>
                        <style>
                        body {{ margin: 0; padding: 0; background: transparent; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}
                        .daily-container {{ max-height: 380px; overflow-y: auto; }}
                        .daily-row {{ display: flex; align-items: center; padding: 6px 0; border-bottom: 1px solid #e5e7eb; }}
                        .daily-name {{ width: 160px; font-size: 12px; color: #374151; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
                        .daily-bar-container {{ flex: 1; margin: 0 10px; height: 20px; background: #f3f4f6; border-radius: 10px; overflow: hidden; position: relative; }}
                        .daily-bar {{ height: 100%; border-radius: 10px; }}
                        .daily-bar-text {{ position: absolute; right: 6px; top: 50%; transform: translateY(-50%); font-size: 10px; color: #374151; font-weight: bold; }}
                        .daily-stats {{ width: 100px; text-align: right; font-size: 11px; color: #6b7280; }}
                        </style>
                        </head>
                        <body>
                        <div class="daily-container">
                        {rows_html}
                        </div>
                        </body>
                        </html>
                        '''

                        components.html(daily_html, height=iframe_height, scrolling=True)

                # Show info about centers with no check-in
                no_checkin_count = len([p for p in progress_data if p['checkin_count'] == 0])
                if no_checkin_count > 0:
                    st.caption(f"ℹ️ {no_checkin_count} ศูนย์ ยังไม่มีข้อมูล Check-in ในช่วงเวลานี้")
            else:
                st.info("📭 ไม่มีข้อมูล Check-in (QLog) ในช่วงเวลาที่เลือก กรุณา upload ข้อมูล QLog ในหน้า Upload")

            # Highlight over capacity
            st.markdown("---")
            st.markdown("**🔴 ศูนย์/วัน ที่เกิน Capacity:**")

            over_capacity_items = [c for c in stats['by_center_daily'] if c['status'] == 'over']
            if over_capacity_items:
                over_df = pd.DataFrame(over_capacity_items)
                over_df['date'] = over_df['date'].apply(lambda x: x.strftime('%d/%m/%Y'))
                over_df = over_df[['date', 'branch_name', 'count', 'capacity', 'usage_pct']]
                over_df.columns = ['วันที่', 'ศูนย์', 'นัดหมาย', 'Capacity', 'ใช้งาน %']
                over_df = over_df.sort_values(['วันที่', 'ใช้งาน %'], ascending=[True, False])
                st.dataframe(over_df, hide_index=True, use_container_width=True)
            else:
                st.success("✅ ไม่มีศูนย์/วัน ที่เกิน Capacity")
        else:
            st.info("ไม่มีข้อมูลนัดหมายในช่วงเวลาที่เลือก")

else:
    st.markdown("---")
    st.info("""
    ⚠️ **ยังไม่มีข้อมูลนัดหมายล่วงหน้า**

    กรุณาอัพโหลดไฟล์ Appointment ที่มีวันนัดในอนาคต ในหน้า **Upload > Tab "📅 Appointment"**

    **ข้อมูลที่ต้องการ:**
    - ไฟล์ Appointment (appointment-*.csv) ที่มี APPOINTMENT_DATE ในอนาคต
    - ไฟล์ Branch Master (ถ้าต้องการเทียบ Capacity)
    """)
