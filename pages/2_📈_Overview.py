"""Overview page - Modern Dashboard with Bar Charts."""
import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
from datetime import date, timedelta
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session
from database.models import Card, Report, DeliveryCard
from sqlalchemy import func, and_, or_, case
from utils.theme import apply_theme
from utils.auth_check import require_login
from utils.logger import log_perf, log_info

init_db()


# Cached function for branch list
@st.cache_data(ttl=600)
def get_branch_list():
    """Get list of all branches."""
    session = get_session()
    try:
        branches = session.query(
            Card.branch_code,
            Card.branch_name
        ).filter(
            Card.branch_code.isnot(None),
            Card.branch_code != ''
        ).distinct().order_by(Card.branch_code).all()

        return [(b.branch_code, b.branch_name or b.branch_code) for b in branches]
    finally:
        session.close()


# Cached function for overview stats
@st.cache_data(ttl=300)
def get_overview_stats(start_date, end_date, selected_branches=None):
    """Get cached overview statistics."""
    start_time = time.perf_counter()
    session = get_session()
    try:
        # Base date filter
        filters = [Card.print_date >= start_date, Card.print_date <= end_date]

        # Add branch filter if specified
        if selected_branches and len(selected_branches) > 0:
            filters.append(Card.branch_code.in_(selected_branches))

        date_filter = and_(*filters)

        # Unique Serial counts
        unique_at_center = session.query(func.count(func.distinct(Card.serial_number))).filter(
            date_filter, Card.print_status == 'G'
        ).scalar() or 0

        report_ids_with_data = session.query(Card.report_id).filter(date_filter).distinct().subquery()

        unique_delivery = session.query(func.count(func.distinct(DeliveryCard.serial_number))).filter(
            DeliveryCard.print_status == 'G',
            DeliveryCard.report_id.in_(session.query(report_ids_with_data))
        ).scalar() or 0

        from sqlalchemy import union_all

        card_serials = session.query(Card.serial_number.label('sn')).filter(
            date_filter, Card.print_status == 'G',
            Card.serial_number.isnot(None), Card.serial_number != ''
        )
        delivery_serials = session.query(DeliveryCard.serial_number.label('sn')).filter(
            DeliveryCard.print_status == 'G',
            DeliveryCard.report_id.in_(session.query(report_ids_with_data)),
            DeliveryCard.serial_number.isnot(None), DeliveryCard.serial_number != ''
        )
        combined_serials = union_all(card_serials, delivery_serials).subquery()
        unique_total = session.query(func.count(func.distinct(combined_serials.c.sn))).scalar() or 0

        bad_at_center = session.query(Card).filter(date_filter, Card.print_status == 'B').count()
        bad_delivery = session.query(DeliveryCard).filter(
            DeliveryCard.print_status == 'B',
            DeliveryCard.report_id.in_(session.query(report_ids_with_data))
        ).count()
        bad_cards = bad_at_center + bad_delivery

        appt_one_g = session.query(Card.appointment_id).filter(
            date_filter, Card.print_status == 'G',
            Card.appointment_id.isnot(None), Card.appointment_id != ''
        ).group_by(Card.appointment_id).having(func.count(Card.id) == 1).subquery()

        complete_cards = session.query(func.count(func.distinct(Card.serial_number))).filter(
            date_filter, Card.print_status == 'G',
            Card.appointment_id.in_(session.query(appt_one_g)),
            Card.card_id.isnot(None), Card.card_id != '',
            Card.serial_number.isnot(None), Card.serial_number != '',
            Card.work_permit_no.isnot(None), Card.work_permit_no != ''
        ).scalar() or 0

        unique_work_permit = session.query(func.count(func.distinct(Card.work_permit_no))).filter(
            date_filter, Card.print_status == 'G',
            Card.appointment_id.in_(session.query(appt_one_g)),
            Card.card_id.isnot(None), Card.card_id != '',
            Card.serial_number.isnot(None), Card.serial_number != '',
            Card.work_permit_no.isnot(None), Card.work_permit_no != ''
        ).scalar() or 0

        appt_multiple_g = session.query(Card.appointment_id).filter(
            date_filter, Card.print_status == 'G',
            Card.appointment_id.isnot(None), Card.appointment_id != ''
        ).group_by(Card.appointment_id).having(func.count(Card.id) > 1).count()

        appt_multiple_records = session.query(func.count(Card.id)).filter(
            date_filter, Card.print_status == 'G',
            Card.appointment_id.in_(
                session.query(Card.appointment_id).filter(
                    date_filter, Card.print_status == 'G',
                    Card.appointment_id.isnot(None), Card.appointment_id != ''
                ).group_by(Card.appointment_id).having(func.count(Card.id) > 1)
            )
        ).scalar() or 0

        incomplete = session.query(Card).filter(
            date_filter, Card.print_status == 'G',
            or_(
                Card.appointment_id.is_(None), Card.appointment_id == '',
                Card.card_id.is_(None), Card.card_id == '',
                Card.serial_number.is_(None), Card.serial_number == '',
                Card.work_permit_no.is_(None), Card.work_permit_no == ''
            )
        ).count()

        wrong_branch = session.query(Card).filter(date_filter, Card.wrong_branch == True).count()
        wrong_date = session.query(Card).filter(date_filter, Card.wrong_date == True).count()
        sla_over_12 = session.query(Card).filter(date_filter, Card.sla_over_12min == True).count()
        wait_over_1hr = session.query(Card).filter(date_filter, Card.wait_over_1hour == True).count()
        duplicate_serial = session.query(Card.serial_number).filter(
            date_filter, Card.print_status == 'G'
        ).group_by(Card.serial_number).having(func.count(Card.id) > 1).count()

        sla_total = session.query(Card).filter(
            date_filter, Card.print_status == 'G', Card.sla_minutes.isnot(None)
        ).count()
        sla_pass = session.query(Card).filter(
            date_filter, Card.print_status == 'G', Card.sla_minutes.isnot(None), Card.sla_minutes <= 12
        ).count()
        avg_sla = session.query(func.avg(Card.sla_minutes)).filter(
            date_filter, Card.print_status == 'G', Card.sla_minutes.isnot(None)
        ).scalar() or 0

        wait_total = session.query(Card).filter(
            date_filter, Card.print_status == 'G', Card.wait_time_minutes.isnot(None)
        ).count()
        wait_pass = session.query(Card).filter(
            date_filter, Card.print_status == 'G', Card.wait_time_minutes.isnot(None), Card.wait_time_minutes <= 60
        ).count()
        avg_wait = session.query(func.avg(Card.wait_time_minutes)).filter(
            date_filter, Card.print_status == 'G', Card.wait_time_minutes.isnot(None)
        ).scalar() or 0

        return {
            'unique_at_center': unique_at_center,
            'unique_delivery': unique_delivery,
            'unique_total': unique_total,
            'bad_cards': bad_cards,
            'complete_cards': complete_cards,
            'unique_work_permit': unique_work_permit,
            'appt_multiple_g': appt_multiple_g,
            'appt_multiple_records': appt_multiple_records,
            'incomplete': incomplete,
            'wrong_branch': wrong_branch,
            'wrong_date': wrong_date,
            'sla_over_12': sla_over_12,
            'wait_over_1hr': wait_over_1hr,
            'duplicate_serial': duplicate_serial,
            'sla_total': sla_total,
            'sla_pass': sla_pass,
            'avg_sla': avg_sla,
            'wait_total': wait_total,
            'wait_pass': wait_pass,
            'avg_wait': avg_wait,
        }
    finally:
        session.close()
        duration = (time.perf_counter() - start_time) * 1000
        log_perf(f"get_overview_stats({start_date} to {end_date})", duration)


@st.cache_data(ttl=300)
def get_daily_stats(start_date, end_date, selected_branches=None):
    """Get cached daily statistics for chart."""
    start_time = time.perf_counter()
    session = get_session()
    try:
        # Base date filter
        filters = [Card.print_date >= start_date, Card.print_date <= end_date]

        # Add branch filter if specified
        if selected_branches and len(selected_branches) > 0:
            filters.append(Card.branch_code.in_(selected_branches))

        date_filter = and_(*filters)

        daily_stats = session.query(
            Card.print_date,
            func.count(func.distinct(Card.serial_number)).filter(Card.print_status == 'G').label('unique_g'),
            func.count(func.distinct(Card.serial_number)).filter(
                Card.print_status == 'G',
                Card.is_mobile_unit == False,
                Card.is_ob_center == False
            ).label('at_center'),
            func.count(func.distinct(Card.serial_number)).filter(
                Card.print_status == 'G',
                or_(Card.is_mobile_unit == True, Card.is_ob_center == True)
            ).label('delivery'),
            func.sum(case((Card.print_status == 'B', 1), else_=0)).label('bad'),
            # Appointment counts - Scheduled vs Walk-in
            func.count(func.distinct(Card.appointment_id)).filter(
                Card.appointment_id.isnot(None),
                Card.appointment_id != ''
            ).label('scheduled_appt'),
            # Walk-in = records without appointment_id (unique by card_id or serial)
            func.count(Card.id).filter(
                or_(Card.appointment_id.is_(None), Card.appointment_id == '')
            ).label('walkin_count')
        ).filter(
            date_filter, Card.print_date.isnot(None)
        ).group_by(Card.print_date).order_by(Card.print_date).all()

        result = [(d.print_date, d.unique_g or 0, d.at_center or 0, d.delivery or 0, d.bad or 0, d.scheduled_appt or 0, d.walkin_count or 0) for d in daily_stats]
        return result
    finally:
        session.close()
        duration = (time.perf_counter() - start_time) * 1000
        log_perf(f"get_daily_stats({start_date} to {end_date})", duration)


@st.cache_data(ttl=60)
def get_date_range():
    """Get cached min/max dates."""
    start_time = time.perf_counter()
    session = get_session()
    try:
        min_date = session.query(func.min(Card.print_date)).scalar()
        max_date = session.query(func.max(Card.print_date)).scalar()

        if min_date is None:
            min_date = date.today()
        if max_date is None:
            max_date = date.today()

        return min_date, max_date
    finally:
        session.close()
        duration = (time.perf_counter() - start_time) * 1000
        log_perf("get_date_range", duration)


st.set_page_config(page_title="Overview - Bio Dashboard", page_icon="📈", layout="wide")

require_login()
apply_theme()

# Page Header
st.markdown("""
<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #374151;">
    <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #3B82F6, #2563EB); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
        <span style="font-size: 24px;">📊</span>
    </div>
    <div>
        <h1 style="font-size: 1.75rem; font-weight: 700; color: #FAFAFA; margin: 0;">รายงานผลการออกบัตร</h1>
        <p style="font-size: 0.9rem; color: #9CA3AF; margin: 0;">Bio Unified Report Dashboard</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Refresh button
col_title, col_refresh = st.columns([6, 1])
with col_refresh:
    if st.button("🔄 รีเฟรช", use_container_width=True, help="รีเฟรชข้อมูลใหม่"):
        st.cache_data.clear()
        st.rerun()

min_date, max_date = get_date_range()

if not min_date or not max_date:
    st.info("ยังไม่มีข้อมูล - กรุณาอัพโหลดไฟล์รายงานก่อน")
else:
    if 'filter_start' not in st.session_state:
        st.session_state.filter_start = min_date
    if 'filter_end' not in st.session_state:
        st.session_state.filter_end = max_date

    if st.session_state.filter_start < min_date:
        st.session_state.filter_start = min_date
    if st.session_state.filter_end > max_date:
        st.session_state.filter_end = max_date
    if st.session_state.filter_end < max_date:
        st.session_state.filter_end = max_date

    # Filter Section
    st.markdown("### 📅 ตัวกรองข้อมูล")

    # Get branch list for filter
    branch_list = get_branch_list()
    # Map: code -> display name (show name only, fallback to code if no name)
    branch_options = {code: name if name and name != code else code for code, name in branch_list}
    # Reverse map: for getting code from selected display name
    branch_code_map = {code: code for code, name in branch_list}

    # Row 1: Date filters and quick buttons
    col1, col2, col3, col4, col5, col6 = st.columns([2.5, 2.5, 1, 1, 1, 1])

    with col3:
        if st.button("วันนี้", use_container_width=True):
            st.session_state.filter_start = max_date
            st.session_state.filter_end = max_date
            st.rerun()
    with col4:
        if st.button("7 วัน", use_container_width=True):
            st.session_state.filter_start = max_date - timedelta(days=7)
            st.session_state.filter_end = max_date
            st.rerun()
    with col5:
        if st.button("30 วัน", use_container_width=True):
            st.session_state.filter_start = max_date - timedelta(days=30)
            st.session_state.filter_end = max_date
            st.rerun()
    with col6:
        if st.button("🔄 Reset", use_container_width=True, help="รีเซ็ตตัวกรองทั้งหมด"):
            st.session_state.filter_start = min_date
            st.session_state.filter_end = max_date
            if 'overview_branches' in st.session_state:
                del st.session_state.overview_branches
            st.rerun()

    with col1:
        start_date = st.date_input("วันที่เริ่มต้น", value=st.session_state.filter_start, min_value=min_date, max_value=max_date, key="overview_start")
        st.session_state.filter_start = start_date
    with col2:
        end_date = st.date_input("วันที่สิ้นสุด", value=st.session_state.filter_end, min_value=min_date, max_value=max_date, key="overview_end")
        st.session_state.filter_end = end_date

    # Row 2: Branch filter
    if branch_list:
        selected_branch_codes = st.multiselect(
            "🏢 เลือกศูนย์ (เว้นว่างเพื่อดูทั้งหมด)",
            options=list(branch_options.keys()),
            format_func=lambda x: branch_options.get(x, x),
            key="overview_branches",
            placeholder="ทุกศูนย์"
        )
    else:
        selected_branch_codes = []

    # Convert to tuple for caching (lists are not hashable)
    selected_branches = tuple(selected_branch_codes) if selected_branch_codes else None

    # Get Stats
    stats = get_overview_stats(start_date, end_date, selected_branches)

    unique_at_center = stats['unique_at_center']
    unique_delivery = stats['unique_delivery']
    unique_total = stats['unique_total']
    bad_cards = stats['bad_cards']
    complete_cards = stats['complete_cards']
    unique_work_permit = stats['unique_work_permit']
    appt_multiple_g = stats['appt_multiple_g']
    appt_multiple_records = stats['appt_multiple_records']
    incomplete = stats['incomplete']
    wrong_branch = stats['wrong_branch']
    wrong_date = stats['wrong_date']
    sla_over_12 = stats['sla_over_12']
    wait_over_1hr = stats['wait_over_1hr']
    duplicate_serial = stats['duplicate_serial']
    sla_total = stats['sla_total']
    sla_pass = stats['sla_pass']
    avg_sla = stats['avg_sla']
    wait_total = stats['wait_total']
    wait_pass = stats['wait_pass']
    avg_wait = stats['avg_wait']

    complete_pct = (complete_cards / unique_total * 100) if unique_total > 0 else 0
    total_anomalies = wrong_branch + wrong_date + appt_multiple_g + duplicate_serial + sla_over_12 + wait_over_1hr
    sla_fail = sla_total - sla_pass
    sla_pass_pct = (sla_pass / sla_total * 100) if sla_total > 0 else 0
    wait_fail = wait_total - wait_pass
    wait_pass_pct = (wait_pass / wait_total * 100) if wait_total > 0 else 0

    # ==================== METRIC CARDS ====================
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏢 Unique SN รับที่ศูนย์", f"{unique_at_center:,}")
    with col2:
        st.metric("🚚 Unique SN จัดส่ง", f"{unique_delivery:,}")
    with col3:
        st.metric("✅ รวม Unique SN (G)", f"{unique_total:,}")
    with col4:
        st.metric("❌ บัตรเสีย (B)", f"{bad_cards:,}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 บัตรสมบูรณ์", f"{complete_cards:,}", f"{complete_pct:.1f}%")
    with col2:
        st.metric("⚠️ Appt G>1", f"{appt_multiple_g:,}")
    with col3:
        st.metric("📝 ข้อมูลไม่ครบ", f"{incomplete:,}")
    with col4:
        st.metric("🪪 Unique Work Permit", f"{unique_work_permit:,}")

    st.markdown("---")

    # ==================== DAILY CHARTS (FULL WIDTH) ====================
    st.markdown("### 📊 สรุปจำนวนบัตรรายวัน")

    daily_stats = get_daily_stats(start_date, end_date, selected_branches)

    if daily_stats:
        daily_data = pd.DataFrame([{
            'วันที่': d[0],
            'Unique Serial (G)': d[1],
            'รับที่ศูนย์': d[2],
            'จัดส่ง': d[3],
            'บัตรเสีย': d[4],
            'มีนัดหมาย': d[5],  # Scheduled appointments
            'Walk-in': d[6],    # Walk-in without appointment
        } for d in daily_stats])

        dates = [d.strftime('%d/%m') if hasattr(d, 'strftime') else str(d) for d in daily_data['วันที่']]

        # Mixed Bar + Line Chart (Bar for breakdown, Line for total and appointments)
        mixed_options = {
            "animation": True,
            "animationDuration": 800,
            "backgroundColor": "transparent",
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "cross"},
                "backgroundColor": "rgba(30, 41, 59, 0.95)",
                "borderColor": "#475569",
                "textStyle": {"color": "#F1F5F9"},
            },
            "legend": {
                "data": ["รับที่ศูนย์", "จัดส่ง", "บัตรเสีย", "รวมบัตรดี (G)"],
                "bottom": 0,
                "textStyle": {"color": "#9CA3AF"},
            },
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "10%", "containLabel": True},
            "xAxis": {
                "type": "category",
                "data": dates,
                "axisLine": {"lineStyle": {"color": "#374151"}},
                "axisLabel": {"color": "#9CA3AF", "rotate": 45 if len(dates) > 15 else 0},
            },
            "yAxis": {
                "type": "value",
                "axisLine": {"lineStyle": {"color": "#374151"}},
                "axisLabel": {"color": "#9CA3AF"},
                "splitLine": {"lineStyle": {"color": "#1F2937"}},
            },
            "series": [
                {
                    "name": "รับที่ศูนย์",
                    "type": "bar",
                    "stack": "cards",
                    "data": daily_data['รับที่ศูนย์'].tolist(),
                    "itemStyle": {"color": "#10B981"},
                    "barMaxWidth": 50,
                },
                {
                    "name": "จัดส่ง",
                    "type": "bar",
                    "stack": "cards",
                    "data": daily_data['จัดส่ง'].tolist(),
                    "itemStyle": {"color": "#8B5CF6"},
                    "barMaxWidth": 50,
                },
                {
                    "name": "บัตรเสีย",
                    "type": "bar",
                    "data": daily_data['บัตรเสีย'].tolist(),
                    "itemStyle": {"color": "#EF4444"},
                    "barMaxWidth": 50,
                },
                {
                    "name": "รวมบัตรดี (G)",
                    "type": "line",
                    "data": daily_data['Unique Serial (G)'].tolist(),
                    "itemStyle": {"color": "#00D4AA"},
                    "lineStyle": {"width": 3, "type": "solid"},
                    "symbol": "circle",
                    "symbolSize": 8,
                    "smooth": True,
                    "label": {
                        "show": len(dates) <= 10,
                        "position": "top",
                        "color": "#00D4AA",
                        "fontSize": 11,
                        "fontWeight": "bold"
                    }
                },
            ]
        }
        st_echarts(options=mixed_options, height="400px", key="daily_mixed_chart")

        # ==================== APPOINTMENT CHART (SEPARATE) ====================
        st.markdown("### 📅 สรุปประเภทการเข้ารับบริการรายวัน")
        st.caption("📌 มีนัดหมาย = มี Appointment ID | Walk-in = ไม่มี Appointment ID (มาโดยไม่ได้นัด)")

        appt_options = {
            "animation": True,
            "animationDuration": 800,
            "backgroundColor": "transparent",
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "cross"},
                "backgroundColor": "rgba(30, 41, 59, 0.95)",
                "borderColor": "#475569",
                "textStyle": {"color": "#F1F5F9"},
            },
            "legend": {
                "data": ["มีนัดหมาย (Scheduled)", "Walk-in"],
                "bottom": 0,
                "textStyle": {"color": "#9CA3AF"},
            },
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "10%", "containLabel": True},
            "xAxis": {
                "type": "category",
                "data": dates,
                "axisLine": {"lineStyle": {"color": "#374151"}},
                "axisLabel": {"color": "#9CA3AF", "rotate": 45 if len(dates) > 15 else 0},
            },
            "yAxis": {
                "type": "value",
                "axisLine": {"lineStyle": {"color": "#374151"}},
                "axisLabel": {"color": "#9CA3AF"},
                "splitLine": {"lineStyle": {"color": "#1F2937"}},
            },
            "series": [
                {
                    "name": "มีนัดหมาย (Scheduled)",
                    "type": "bar",
                    "stack": "service",
                    "data": daily_data['มีนัดหมาย'].tolist(),
                    "itemStyle": {"color": "#3B82F6"},
                    "barMaxWidth": 50,
                },
                {
                    "name": "Walk-in",
                    "type": "bar",
                    "stack": "service",
                    "data": daily_data['Walk-in'].tolist(),
                    "itemStyle": {"color": "#F59E0B"},
                    "barMaxWidth": 50,
                },
            ]
        }
        st_echarts(options=appt_options, height="350px", key="daily_appt_chart")
    else:
        st.info("ไม่มีข้อมูลในช่วงเวลาที่เลือก")

    st.markdown("---")

    # ==================== PIE CHART & SLA (COLUMNS) ====================
    st.markdown("### 📈 สัดส่วนการออกบัตร และ SLA")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Pie Chart: Good vs Bad Cards
        good_pct = (unique_total / (unique_total + bad_cards) * 100) if (unique_total + bad_cards) > 0 else 0
        bad_pct = (bad_cards / (unique_total + bad_cards) * 100) if (unique_total + bad_cards) > 0 else 0

        pie_options = {
            "animation": True,
            "animationDuration": 800,
            "backgroundColor": "transparent",
            "tooltip": {
                "trigger": "item",
                "backgroundColor": "rgba(30, 41, 59, 0.95)",
                "borderColor": "#475569",
                "textStyle": {"color": "#F1F5F9"},
                "formatter": "{b}: {c} ({d}%)"
            },
            "legend": {
                "orient": "horizontal",
                "bottom": 0,
                "textStyle": {"color": "#9CA3AF"},
            },
            "series": [{
                "name": "สถานะบัตร",
                "type": "pie",
                "radius": ["40%", "70%"],
                "center": ["50%", "45%"],
                "avoidLabelOverlap": True,
                "itemStyle": {
                    "borderRadius": 8,
                    "borderColor": "#1A1F2E",
                    "borderWidth": 2
                },
                "label": {
                    "show": True,
                    "color": "#F1F5F9",
                    "formatter": "{d}%"
                },
                "data": [
                    {"value": unique_total, "name": "บัตรดี (G)", "itemStyle": {"color": "#10B981"}},
                    {"value": bad_cards, "name": "บัตรเสีย (B)", "itemStyle": {"color": "#EF4444"}}
                ]
            }]
        }
        st.markdown("**สัดส่วนการออกบัตร**")
        st_echarts(options=pie_options, height="280px", key="pie_status")

    with col2:
        # Gauge Chart: SLA Performance
        sla_gauge = {
            "animation": True,
            "backgroundColor": "transparent",
            "tooltip": {
                "formatter": "{b}: {c}%"
            },
            "series": [{
                "name": "SLA ออกบัตร",
                "type": "gauge",
                "radius": "85%",
                "center": ["50%", "55%"],
                "startAngle": 200,
                "endAngle": -20,
                "min": 0,
                "max": 100,
                "splitNumber": 5,
                "itemStyle": {
                    "color": "#10B981" if sla_pass_pct >= 80 else ("#F59E0B" if sla_pass_pct >= 50 else "#EF4444")
                },
                "progress": {
                    "show": True,
                    "roundCap": True,
                    "width": 12
                },
                "pointer": {"show": False},
                "axisLine": {
                    "roundCap": True,
                    "lineStyle": {"width": 12, "color": [[1, "#374151"]]}
                },
                "axisTick": {"show": False},
                "splitLine": {"show": False},
                "axisLabel": {"show": False},
                "title": {
                    "show": True,
                    "offsetCenter": [0, "70%"],
                    "fontSize": 14,
                    "color": "#9CA3AF"
                },
                "detail": {
                    "valueAnimation": True,
                    "fontSize": 28,
                    "fontWeight": "bold",
                    "offsetCenter": [0, "0%"],
                    "formatter": "{value}%",
                    "color": "#F1F5F9"
                },
                "data": [{"value": round(sla_pass_pct, 1), "name": f"ผ่าน ≤12 นาที"}]
            }]
        }
        st.markdown(f"**SLA ออกบัตร** (เฉลี่ย {avg_sla:.1f} นาที)")
        st_echarts(options=sla_gauge, height="280px", key="sla_gauge")

    with col3:
        # Gauge Chart: Wait Time Performance
        wait_gauge = {
            "animation": True,
            "backgroundColor": "transparent",
            "tooltip": {
                "formatter": "{b}: {c}%"
            },
            "series": [{
                "name": "SLA รอคิว",
                "type": "gauge",
                "radius": "85%",
                "center": ["50%", "55%"],
                "startAngle": 200,
                "endAngle": -20,
                "min": 0,
                "max": 100,
                "splitNumber": 5,
                "itemStyle": {
                    "color": "#10B981" if wait_pass_pct >= 80 else ("#F59E0B" if wait_pass_pct >= 50 else "#EF4444")
                },
                "progress": {
                    "show": True,
                    "roundCap": True,
                    "width": 12
                },
                "pointer": {"show": False},
                "axisLine": {
                    "roundCap": True,
                    "lineStyle": {"width": 12, "color": [[1, "#374151"]]}
                },
                "axisTick": {"show": False},
                "splitLine": {"show": False},
                "axisLabel": {"show": False},
                "title": {
                    "show": True,
                    "offsetCenter": [0, "70%"],
                    "fontSize": 14,
                    "color": "#9CA3AF"
                },
                "detail": {
                    "valueAnimation": True,
                    "fontSize": 28,
                    "fontWeight": "bold",
                    "offsetCenter": [0, "0%"],
                    "formatter": "{value}%",
                    "color": "#F1F5F9"
                },
                "data": [{"value": round(wait_pass_pct, 1), "name": f"ผ่าน ≤1 ชม."}]
            }]
        }
        st.markdown(f"**SLA รอคิว** (เฉลี่ย {avg_wait:.1f} นาที)")
        st_echarts(options=wait_gauge, height="280px", key="wait_gauge")

    # SLA Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("ผ่าน SLA ออกบัตร", f"{sla_pass:,}", f"{sla_pass_pct:.1f}%")
    with col2:
        st.metric("ไม่ผ่าน SLA", f"{sla_fail:,}")
    with col3:
        st.metric("ผ่าน SLA รอคิว", f"{wait_pass:,}", f"{wait_pass_pct:.1f}%")
    with col4:
        st.metric("รอเกิน 1 ชม.", f"{wait_fail:,}")

    st.markdown("---")

    # ==================== ANOMALY SECTION ====================
    if total_anomalies > 0:
        st.warning(f"⚠️ พบความผิดปกติ {total_anomalies:,} รายการ - กรุณาตรวจสอบในหน้า Anomaly")

    st.markdown("### 🔍 การออกบัตรผิดปกติ (Anomaly)")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("ออกบัตรผิดศูนย์", f"{wrong_branch:,}")
        st.metric("นัดหมายผิดวัน", f"{wrong_date:,}")
    with col2:
        st.metric("ออกบัตรหลายใบ (G>1)", f"{appt_multiple_g:,}")
        st.metric("Serial ซ้ำ", f"{duplicate_serial:,}")
    with col3:
        st.metric("SLA เกิน 12 นาที", f"{sla_over_12:,}")
        st.metric("รอคิวเกิน 1 ชม.", f"{wait_over_1hr:,}")
