"""Overview page - Summary statistics matching the report format."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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


# Cached function for overview stats
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_overview_stats(start_date, end_date):
    """Get cached overview statistics."""
    start_time = time.perf_counter()
    session = get_session()
    try:
        date_filter = and_(Card.print_date >= start_date, Card.print_date <= end_date)

        # Unique Serial counts
        # Total unique G from Cards table (รับที่ศูนย์)
        unique_at_center = session.query(func.count(func.distinct(Card.serial_number))).filter(
            date_filter, Card.print_status == 'G'
        ).scalar() or 0

        # Delivery cards - นับจาก DeliveryCard table โดยตรง (Sheet 7)
        # หา report IDs ที่มี cards ในช่วงวันที่เลือก
        report_ids_with_data = session.query(Card.report_id).filter(date_filter).distinct().subquery()

        unique_delivery = session.query(func.count(func.distinct(DeliveryCard.serial_number))).filter(
            DeliveryCard.print_status == 'G',
            DeliveryCard.report_id.in_(session.query(report_ids_with_data))
        ).scalar() or 0

        # Total = นับ Unique Serial รวมจากทั้งสองตาราง (ไม่นับซ้ำ)
        # ใช้ UNION เพื่อรวม Serial จาก Card และ DeliveryCard แล้วนับ distinct
        from sqlalchemy import union_all, literal_column

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

        # นับบัตรเสีย (B) รวมทั้งรับที่ศูนย์และจัดส่ง
        bad_at_center = session.query(Card).filter(date_filter, Card.print_status == 'B').count()
        bad_delivery = session.query(DeliveryCard).filter(
            DeliveryCard.print_status == 'B',
            DeliveryCard.report_id.in_(session.query(report_ids_with_data))
        ).count()
        bad_cards = bad_at_center + bad_delivery

        # Complete cards - ต้องมีข้อมูลครบ 4 fields และ 1 Appt = 1 G
        # 1. หา Appt ID ที่มี G = 1 เท่านั้น
        appt_one_g = session.query(Card.appointment_id).filter(
            date_filter, Card.print_status == 'G',
            Card.appointment_id.isnot(None), Card.appointment_id != ''
        ).group_by(Card.appointment_id).having(func.count(Card.id) == 1).subquery()

        # 2. นับ Unique Serial Number ที่มีข้อมูลครบ 4 fields และอยู่ใน Appt ที่มี G = 1
        # ใช้ Unique Serial เพื่อไม่นับ Serial ซ้ำ (ตาม Excel logic)
        complete_cards = session.query(func.count(func.distinct(Card.serial_number))).filter(
            date_filter, Card.print_status == 'G',
            Card.appointment_id.in_(session.query(appt_one_g)),
            # ต้องมี Card ID
            Card.card_id.isnot(None), Card.card_id != '',
            # ต้องมี Serial Number
            Card.serial_number.isnot(None), Card.serial_number != '',
            # ต้องมี Work Permit No
            Card.work_permit_no.isnot(None), Card.work_permit_no != ''
        ).scalar() or 0

        # 3. Unique Work Permit No จากบัตรสมบูรณ์
        unique_work_permit = session.query(func.count(func.distinct(Card.work_permit_no))).filter(
            date_filter, Card.print_status == 'G',
            Card.appointment_id.in_(session.query(appt_one_g)),
            Card.card_id.isnot(None), Card.card_id != '',
            Card.serial_number.isnot(None), Card.serial_number != '',
            Card.work_permit_no.isnot(None), Card.work_permit_no != ''
        ).scalar() or 0

        # Appt G > 1
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

        # Incomplete - บัตรดีที่ขาดข้อมูลใดข้อมูลหนึ่งใน 4 fields
        # (Appointment ID, Card ID, Serial Number, Work Permit No)
        incomplete = session.query(Card).filter(
            date_filter, Card.print_status == 'G',
            or_(
                Card.appointment_id.is_(None), Card.appointment_id == '',
                Card.card_id.is_(None), Card.card_id == '',
                Card.serial_number.is_(None), Card.serial_number == '',
                Card.work_permit_no.is_(None), Card.work_permit_no == ''
            )
        ).count()

        # Anomaly stats
        wrong_branch = session.query(Card).filter(date_filter, Card.wrong_branch == True).count()
        wrong_date = session.query(Card).filter(date_filter, Card.wrong_date == True).count()
        sla_over_12 = session.query(Card).filter(date_filter, Card.sla_over_12min == True).count()
        wait_over_1hr = session.query(Card).filter(date_filter, Card.wait_over_1hour == True).count()
        duplicate_serial = session.query(Card.serial_number).filter(
            date_filter, Card.print_status == 'G'
        ).group_by(Card.serial_number).having(func.count(Card.id) > 1).count()

        # SLA stats
        sla_total = session.query(Card).filter(
            date_filter, Card.print_status == 'G', Card.sla_minutes.isnot(None)
        ).count()
        sla_pass = session.query(Card).filter(
            date_filter, Card.print_status == 'G', Card.sla_minutes.isnot(None), Card.sla_minutes <= 12
        ).count()
        avg_sla = session.query(func.avg(Card.sla_minutes)).filter(
            date_filter, Card.print_status == 'G', Card.sla_minutes.isnot(None)
        ).scalar() or 0

        # Wait stats
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
def get_daily_stats(start_date, end_date):
    """Get cached daily statistics for chart."""
    start_time = time.perf_counter()
    session = get_session()
    try:
        date_filter = and_(Card.print_date >= start_date, Card.print_date <= end_date)

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
            func.sum(case((Card.print_status == 'B', 1), else_=0)).label('bad')
        ).filter(
            date_filter, Card.print_date.isnot(None)
        ).group_by(Card.print_date).order_by(Card.print_date).all()

        result = [(d.print_date, d.unique_g or 0, d.at_center or 0, d.delivery or 0, d.bad or 0) for d in daily_stats]
        return result
    finally:
        session.close()
        duration = (time.perf_counter() - start_time) * 1000
        log_perf(f"get_daily_stats({start_date} to {end_date})", duration)


@st.cache_data(ttl=60)  # Cache 1 minute only for date range
def get_date_range():
    """Get cached min/max dates."""
    start_time = time.perf_counter()
    session = get_session()
    try:
        min_date = session.query(func.min(Card.print_date)).scalar()
        max_date = session.query(func.max(Card.print_date)).scalar()

        # ถ้าไม่มีข้อมูล ให้ใช้วันที่ปัจจุบัน
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

# Check authentication
require_login()

# Apply dark theme
apply_theme()

# Dark mode colors
bg_color = '#0e1117'
card_bg = '#161b22'
card_header_bg = '#21262d'
card_border = '#30363d'
text_color = '#c9d1d9'
text_muted = '#8b949e'
chart_bg = 'rgba(0,0,0,0)'
chart_text = '#c9d1d9'
chart_grid = 'rgba(255,255,255,0.1)'
warning_header_bg = 'linear-gradient(90deg, #3d2d1f 0%, #2d2418 100%)'
warning_text = '#fbbf24'
blue_header_bg = 'linear-gradient(90deg, #1e3a5f 0%, #162d4d 100%)'
summary_bg = '#161b22'

# CSS
st.markdown(f"""
<style>
    .main .block-container {{
        padding-top: 1rem;
        padding-bottom: 2rem;
    }}

    .page-header {{
        color: {text_color};
        font-size: 1.5em;
        font-weight: 600;
        margin-bottom: 20px;
    }}

    .summary-row {{
        display: flex;
        gap: 12px;
        margin-bottom: 20px;
        flex-wrap: wrap;
    }}

    .summary-card {{
        flex: 1;
        min-width: 130px;
        background: {summary_bg};
        border: 1px solid {card_border};
        border-radius: 8px;
        padding: 16px 20px;
    }}

    .summary-label {{
        font-size: 0.8em;
        color: {text_muted};
        margin-bottom: 8px;
    }}

    .summary-value {{
        font-size: 1.6em;
        font-weight: 700;
        color: #58a6ff;
    }}

    .card-section {{
        background: {card_bg};
        border: 1px solid {card_border};
        border-radius: 8px;
        margin-bottom: 20px;
        overflow: hidden;
    }}

    .card-header {{
        background: {card_header_bg};
        padding: 14px 20px;
        border-bottom: 1px solid {card_border};
        font-weight: 600;
        font-size: 0.95em;
        color: {text_color};
        border-left: 4px solid #58a6ff;
    }}

    .card-header-warning {{
        background: {warning_header_bg};
        padding: 14px 20px;
        border-bottom: 1px solid {card_border};
        font-weight: 600;
        font-size: 0.95em;
        color: {warning_text};
        border-left: 4px solid #f59e0b;
    }}

    .card-header-blue {{
        background: {blue_header_bg};
        padding: 14px 20px;
        border-bottom: 1px solid {card_border};
        font-weight: 600;
        font-size: 0.95em;
        color: #60a5fa;
        border-left: 4px solid #3b82f6;
    }}

    .card-body {{
        padding: 20px;
    }}

    .metric-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 20px;
    }}

    .metric-item {{
        text-align: left;
    }}

    .metric-label {{
        font-size: 0.8em;
        color: {text_muted};
        margin-bottom: 6px;
    }}

    .metric-value {{
        font-size: 1.6em;
        font-weight: 700;
        color: {text_color};
    }}

    .metric-delta {{
        font-size: 0.85em;
        margin-top: 4px;
        color: #3fb950;
    }}

    .metric-delta-red {{
        color: #f85149;
    }}

    .progress-container {{
        margin-top: 20px;
    }}

    .progress-header {{
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
        font-size: 0.9em;
    }}

    .progress-bar {{
        height: 10px;
        border-radius: 5px;
        background: #30363d;
        overflow: hidden;
    }}

    .progress-fill {{
        height: 100%;
        border-radius: 5px;
        background: linear-gradient(90deg, #3fb950, #56d364);
    }}

    .progress-fill-red {{
        background: linear-gradient(90deg, #f85149, #ff7b72);
    }}

    /* Filter row */
    .filter-row {{
        display: flex;
        align-items: flex-end;
        gap: 10px;
        margin-bottom: 20px;
    }}

    [data-testid="column"] {{
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
    }}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="page-header">รายงานผลการออกบัตร</div>', unsafe_allow_html=True)

# Refresh button to clear cache
col_title, col_refresh = st.columns([6, 1])
with col_refresh:
    if st.button("🔄 รีเฟรช", use_container_width=True, help="รีเฟรชข้อมูลใหม่"):
        st.cache_data.clear()
        st.rerun()

# Use cached date range
min_date, max_date = get_date_range()

if not min_date or not max_date:
    st.info("ยังไม่มีข้อมูล - กรุณาอัพโหลดไฟล์รายงานก่อน")
else:
    # Initialize date filter state
    if 'filter_start' not in st.session_state:
        st.session_state.filter_start = min_date
    if 'filter_end' not in st.session_state:
        st.session_state.filter_end = max_date

    # Update filter bounds when data range changes (e.g., new data imported)
    if st.session_state.filter_start < min_date:
        st.session_state.filter_start = min_date
    if st.session_state.filter_end > max_date:
        st.session_state.filter_end = max_date
    # If stored end date is less than new max_date, update to include new data
    if st.session_state.filter_end < max_date:
        st.session_state.filter_end = max_date

    # Quick filter buttons
    col1, col2, col3, col4, col5 = st.columns([2.5, 2.5, 1, 1, 1])

    with col3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("วันนี้", use_container_width=True):
            st.session_state.filter_start = max_date
            st.session_state.filter_end = max_date
            st.rerun()
    with col4:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("7 วัน", use_container_width=True):
            st.session_state.filter_start = max_date - timedelta(days=7)
            st.session_state.filter_end = max_date
            st.rerun()
    with col5:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("30 วัน", use_container_width=True):
            st.session_state.filter_start = max_date - timedelta(days=30)
            st.session_state.filter_end = max_date
            st.rerun()

    # Date inputs
    with col1:
        start_date = st.date_input("วันที่เริ่มต้น", value=st.session_state.filter_start, min_value=min_date, max_value=max_date, key="overview_start")
        st.session_state.filter_start = start_date
    with col2:
        end_date = st.date_input("วันที่สิ้นสุด", value=st.session_state.filter_end, min_value=min_date, max_value=max_date, key="overview_end")
        st.session_state.filter_end = end_date

    # ==================== Use Cached Stats ====================
    stats = get_overview_stats(start_date, end_date)

    # Extract values from cached stats
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

    # Calculate derived values
    complete_pct = (complete_cards / unique_total * 100) if unique_total > 0 else 0
    total_anomalies = wrong_branch + wrong_date + appt_multiple_g + duplicate_serial + sla_over_12 + wait_over_1hr
    sla_fail = sla_total - sla_pass
    sla_pass_pct = (sla_pass / sla_total * 100) if sla_total > 0 else 0
    sla_fail_pct = (sla_fail / sla_total * 100) if sla_total > 0 else 0
    wait_fail = wait_total - wait_pass
    wait_pass_pct = (wait_pass / wait_total * 100) if wait_total > 0 else 0

    # ==================== Summary Cards ====================
    # Row 1: Unique Serial Numbers
    st.markdown(f"""
        <div class="summary-row">
            <div class="summary-card">
                <div class="summary-label">Unique SN รับที่ศูนย์</div>
                <div class="summary-value">{unique_at_center:,}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Unique SN จัดส่ง</div>
                <div class="summary-value">{unique_delivery:,}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">รวม Unique SN (G)</div>
                <div class="summary-value" style="color: #58a6ff;">{unique_total:,}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">บัตรเสีย (B)</div>
                <div class="summary-value" style="color: #f85149;">{bad_cards:,}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Row 2: Complete Cards Summary
    st.markdown(f"""
        <div class="summary-row">
            <div class="summary-card">
                <div class="summary-label">✅ บัตรสมบูรณ์</div>
                <div class="summary-value" style="color: #3fb950;">{complete_cards:,}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">⚠️ Appt G>1</div>
                <div class="summary-value" style="color: #f59e0b;">{appt_multiple_g:,}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">⚠️ ข้อมูลไม่ครบ</div>
                <div class="summary-value" style="color: #f59e0b;">{incomplete:,}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Unique Work Permit</div>
                <div class="summary-value">{unique_work_permit:,}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ==================== Line Chart ====================
    st.markdown(f"""
    <div class="card-section">
        <div class="card-header">สรุปจำนวนบัตร</div>
        <div class="card-body" style="padding: 10px 20px;">
    """, unsafe_allow_html=True)

    # Use cached daily stats
    daily_stats = get_daily_stats(start_date, end_date)

    if daily_stats:
        # daily_stats is now a list of tuples from cache
        daily_data = pd.DataFrame([{
            'วันที่': d[0],
            'Unique Serial (G)': d[1],
            'รับที่ศูนย์': d[2],
            'จัดส่ง': d[3],
            'บัตรเสีย': d[4]
        } for d in daily_stats])

        fig = go.Figure()

        # Line 1: Unique Serial (G) รวม
        fig.add_trace(go.Scatter(
            x=daily_data['วันที่'],
            y=daily_data['Unique Serial (G)'],
            name='Unique Serial (G)',
            mode='lines+markers+text',
            line=dict(color='#3b82f6', width=2),
            marker=dict(size=7),
            text=daily_data['Unique Serial (G)'],
            textposition='top center',
            textfont=dict(size=9, color=chart_text)
        ))

        # Line 2: รับที่ศูนย์
        fig.add_trace(go.Scatter(
            x=daily_data['วันที่'],
            y=daily_data['รับที่ศูนย์'],
            name='รับที่ศูนย์',
            mode='lines+markers',
            line=dict(color='#3fb950', width=2),
            marker=dict(size=6)
        ))

        # Line 3: จัดส่ง
        fig.add_trace(go.Scatter(
            x=daily_data['วันที่'],
            y=daily_data['จัดส่ง'],
            name='จัดส่ง',
            mode='lines+markers',
            line=dict(color='#a855f7', width=2),
            marker=dict(size=6)
        ))

        # Line 4: บัตรเสีย
        fig.add_trace(go.Scatter(
            x=daily_data['วันที่'],
            y=daily_data['บัตรเสีย'],
            name='บัตรเสีย',
            mode='lines+markers+text',
            line=dict(color='#f85149', width=2),
            marker=dict(size=6),
            text=daily_data['บัตรเสีย'],
            textposition='bottom center',
            textfont=dict(size=9, color=chart_text)
        ))

        fig.update_layout(
            height=380,
            margin=dict(l=10, r=10, t=20, b=10),
            plot_bgcolor=chart_bg,
            paper_bgcolor=chart_bg,
            font_color=chart_text,
            xaxis=dict(gridcolor=chart_grid, title='', showgrid=True),
            yaxis=dict(gridcolor=chart_grid, title='', showgrid=True),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,
                xanchor="center",
                x=0.5,
                font=dict(size=11)
            ),
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ไม่มีข้อมูลในช่วงเวลาที่เลือก")

    st.markdown("</div></div>", unsafe_allow_html=True)

    # ==================== สรุปบัตรสมบูรณ์ ====================
    st.markdown(f"""
    <div class="card-section">
        <div class="card-header">สรุปบัตรสมบูรณ์</div>
        <div class="card-body">
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-label">Unique SN รับที่ศูนย์</div>
                    <div class="metric-value">{unique_at_center:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Unique SN จัดส่ง</div>
                    <div class="metric-value">{unique_delivery:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">รวม Unique SN (G)</div>
                    <div class="metric-value" style="color: #58a6ff;">{unique_total:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">✅ บัตรสมบูรณ์ (1 Appt = 1 G)</div>
                    <div class="metric-value" style="color: #3fb950;">{complete_cards:,}</div>
                    <div class="metric-delta">{complete_pct:.2f}%</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">⚠️ Appt ID ที่มี G > 1</div>
                    <div class="metric-value" style="color: #f59e0b;">{appt_multiple_g:,}</div>
                    <div class="metric-delta" style="color: {text_muted};">{appt_multiple_records:,} รายการ</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">⚠️ ข้อมูลไม่ครบ</div>
                    <div class="metric-value" style="color: #f59e0b;">{incomplete:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Unique Work Permit No</div>
                    <div class="metric-value">{unique_work_permit:,}</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ==================== Anomaly ====================
    st.markdown(f"""
    <div class="card-section">
        <div class="card-header-warning">การออกบัตรผิดปกติ (Anomaly)</div>
        <div class="card-body">
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-label">ออกบัตรผิดศูนย์</div>
                    <div class="metric-value">{wrong_branch:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">ออกบัตรหลายใบ (G>1)</div>
                    <div class="metric-value">{appt_multiple_g:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">SLA เกิน 12 นาที</div>
                    <div class="metric-value">{sla_over_12:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">นัดหมายผิดวัน</div>
                    <div class="metric-value">{wrong_date:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Serial ซ้ำ</div>
                    <div class="metric-value">{duplicate_serial:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">รอคิวเกิน 1 ชม.</div>
                    <div class="metric-value">{wait_over_1hr:,}</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if total_anomalies > 0:
        st.warning(f"พบความผิดปกติรวม {total_anomalies:,} รายการ - กรุณาตรวจสอบในหน้า Anomaly")

    # ==================== SLA ออกบัตร ====================
    st.markdown(f"""
    <div class="card-section">
        <div class="card-header-blue">SLA ออกบัตร (เกณฑ์ 12 นาที)</div>
        <div class="card-body">
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-label">รายที่ตรวจสอบ</div>
                    <div class="metric-value">{sla_total:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">ผ่าน SLA (≤12 นาที)</div>
                    <div class="metric-value" style="color: #3fb950;">{sla_pass:,}</div>
                    <div class="metric-delta">+{sla_pass_pct:.1f}%</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">ไม่ผ่าน SLA (>12 นาที)</div>
                    <div class="metric-value" style="color: #f85149;">{sla_fail:,}</div>
                    <div class="metric-delta metric-delta-red">-{sla_fail_pct:.1f}%</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">SLA เฉลี่ย</div>
                    <div class="metric-value">{avg_sla:.2f} นาที</div>
                </div>
            </div>
            <div class="progress-container">
                <div class="progress-header">
                    <span style="color: {text_muted};">SLA Performance</span>
                    <span style="color: {text_color};">{sla_pass_pct:.1f}% ผ่านเกณฑ์</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {sla_pass_pct}%;"></div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ==================== SLA รอคิว ====================
    st.markdown(f"""
    <div class="card-section">
        <div class="card-header-blue">SLA รอคิว (เกณฑ์ 1 ชั่วโมง)</div>
        <div class="card-body">
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-label">รายที่ตรวจสอบ</div>
                    <div class="metric-value">{wait_total:,}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">ผ่าน (≤1 ชม.)</div>
                    <div class="metric-value" style="color: #3fb950;">{wait_pass:,}</div>
                    <div class="metric-delta">+{wait_pass_pct:.1f}%</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">ไม่ผ่าน (>1 ชม.)</div>
                    <div class="metric-value" style="color: #f85149;">{wait_fail:,}</div>
                    <div class="metric-delta metric-delta-red">-{100-wait_pass_pct:.1f}%</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">เวลารอเฉลี่ย</div>
                    <div class="metric-value">{avg_wait:.2f} นาที</div>
                </div>
            </div>
            <div class="progress-container">
                <div class="progress-header">
                    <span style="color: {text_muted};">Queue Performance</span>
                    <span style="color: {text_color};">{wait_pass_pct:.1f}% ผ่านเกณฑ์</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {wait_pass_pct}%;"></div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
