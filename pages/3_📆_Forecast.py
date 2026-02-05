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
from database.models import Appointment, BranchMaster
from sqlalchemy import func, and_
from utils.theme import apply_theme
from utils.auth_check import require_login
from utils.logger import log_perf

init_db()


@st.cache_data(ttl=300)
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


@st.cache_data(ttl=300)
def get_upcoming_appointments_full(selected_branches=None, days_ahead=30):
    """
    Get detailed upcoming appointments for workload forecasting.
    Includes capacity comparison from BranchMaster.max_capacity.
    """
    start_time = time.perf_counter()
    session = get_session()
    try:
        today = date.today()
        end_date = today + timedelta(days=days_ahead - 1)

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

        # Build base filter - confirmed or waiting appointments (exclude CANCEL, EXPIRED)
        base_filters = [
            Appointment.appt_date >= today,
            Appointment.appt_status.in_(['SUCCESS', 'WAITING'])  # Include both confirmed and pending
        ]

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

        # Counts
        today_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters), Appointment.appt_date == today
        ).scalar() or 0

        tomorrow = today + timedelta(days=1)
        tomorrow_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters), Appointment.appt_date == tomorrow
        ).scalar() or 0

        next_7_days = today + timedelta(days=6)
        next_7_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters), Appointment.appt_date <= next_7_days
        ).scalar() or 0

        next_30_days = today + timedelta(days=29)
        next_30_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters), Appointment.appt_date <= next_30_days
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
        by_center_query = session.query(
            Appointment.branch_code,
            func.count(func.distinct(Appointment.appointment_id)).label('total')
        ).filter(
            and_(*base_filters),
            Appointment.appt_date <= chart_end_date
        ).group_by(Appointment.branch_code).order_by(
            func.count(func.distinct(Appointment.appointment_id)).desc()
        ).all()

        by_center = []
        for c in by_center_query:
            capacity = capacity_map.get(c.branch_code)
            # Calculate average daily based on days_ahead
            days_in_range = (chart_end_date - today).days + 1
            avg_daily = c.total / days_in_range if days_in_range > 0 else c.total
            status = 'normal'
            if capacity:
                usage_pct = (avg_daily / capacity) * 100
                if usage_pct >= 100:
                    status = 'over'
                elif usage_pct >= 80:
                    status = 'warning'
            else:
                usage_pct = None

            by_center.append({
                'branch_code': c.branch_code,
                'branch_name': branch_map.get(c.branch_code, c.branch_code),
                'count': c.total,
                'avg_daily': round(avg_daily, 1),
                'capacity': capacity,
                'usage_pct': round(usage_pct, 1) if usage_pct else None,
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
                'branch_name': branch_map.get(c.branch_code, c.branch_code),
                'date': c.appt_date,
                'count': c.total,
                'capacity': capacity,
                'usage_pct': round(usage_pct, 1) if usage_pct else None,
                'status': status
            })

        return {
            'has_data': True,
            'today': today_count,
            'tomorrow': tomorrow_count,
            'next_7_days': next_7_count,
            'next_30_days': next_30_count,
            'daily_data': daily_data,
            'by_center': by_center,
            'by_center_daily': by_center_daily,
            'over_capacity_count': over_capacity_count,
            'warning_count': warning_count,
            'max_date': max_future_date,
            'total_capacity': total_capacity
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
<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #374151;">
    <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #8B5CF6, #6366F1); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
        <span style="font-size: 24px;">📆</span>
    </div>
    <div>
        <h1 style="font-size: 1.75rem; font-weight: 700; color: #FAFAFA; margin: 0;">ปริมาณการนัดหมาย</h1>
        <p style="font-size: 0.9rem; color: #9CA3AF; margin: 0;">Upcoming Appointments - นัดหมายล่วงหน้า</p>
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

col1, col2, col3 = st.columns([4, 2, 1])

with col1:
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

with col2:
    days_ahead = st.selectbox(
        "📆 ช่วงเวลา",
        options=[7, 14, 30, 60, 90],
        index=2,
        format_func=lambda x: f"{x} วันข้างหน้า"
    )

with col3:
    if st.button("🔄 Reset", use_container_width=True):
        if 'forecast_branches' in st.session_state:
            del st.session_state.forecast_branches
        st.rerun()

selected_branches = tuple(selected_branch_codes) if selected_branch_codes else None

# Get Data
stats = get_upcoming_appointments_full(selected_branches, days_ahead)

if stats['has_data']:
    # Summary Metrics
    st.markdown("---")
    st.markdown("### 📊 สรุปภาพรวม")

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("📅 วันนี้", f"{stats['today']:,}")
    with col2:
        st.metric("📆 พรุ่งนี้", f"{stats['tomorrow']:,}")
    with col3:
        st.metric("📊 7 วัน", f"{stats['next_7_days']:,}")
    with col4:
        st.metric("📈 30 วัน", f"{stats['next_30_days']:,}")
    with col5:
        st.metric("🔴 เกิน Capacity", f"{stats['over_capacity_count']:,}", help="จำนวนศูนย์/วัน ที่เกิน capacity")
    with col6:
        st.metric("🟡 ใกล้เต็ม (≥80%)", f"{stats['warning_count']:,}", help="จำนวนศูนย์/วัน ที่ใช้งาน ≥80%")

    # Alerts
    if stats['over_capacity_count'] > 0:
        st.error(f"⚠️ **แจ้งเตือน:** พบ {stats['over_capacity_count']} ศูนย์/วัน ที่มีนัดหมายเกิน Capacity ที่รองรับได้!")
    if stats['warning_count'] > 0:
        st.warning(f"⚡ **เฝ้าระวัง:** พบ {stats['warning_count']} ศูนย์/วัน ที่มีนัดหมาย ≥80% ของ Capacity")

    st.markdown("---")

    # Tab Layout for different views
    tab1, tab2, tab3 = st.tabs(["📊 รายวัน", "🏢 รายศูนย์", "📋 ตารางรายละเอียด"])

    with tab1:
        st.markdown("### 📊 ปริมาณนัดหมายรายวัน")
        st.caption(f"📌 แสดงข้อมูล {days_ahead} วันข้างหน้า (นับจากวันนี้)")

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
                    "backgroundColor": "rgba(30, 41, 59, 0.95)",
                    "borderColor": "#475569",
                    "textStyle": {"color": "#F1F5F9"},
                },
                "legend": {
                    "data": ["แรกรับ (OB)", "Capacity OB", "80% Warning", "ค่าเฉลี่ย OB"],
                    "bottom": 0,
                    "textStyle": {"color": "#9CA3AF"},
                },
                "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "10%", "containLabel": True},
                "xAxis": {
                    "type": "category",
                    "data": upcoming_dates,
                    "axisLine": {"lineStyle": {"color": "#374151"}},
                    "axisLabel": {"color": "#9CA3AF", "rotate": 45 if len(upcoming_dates) > 15 else 0},
                },
                "yAxis": {
                    "type": "value",
                    "axisLine": {"lineStyle": {"color": "#374151"}},
                    "axisLabel": {"color": "#9CA3AF"},
                    "splitLine": {"lineStyle": {"color": "#1F2937"}},
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
                            "color": "#9CA3AF",
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
                    "backgroundColor": "rgba(30, 41, 59, 0.95)",
                    "borderColor": "#475569",
                    "textStyle": {"color": "#F1F5F9"},
                },
                "legend": {
                    "data": ["บริการ (SC)", "Capacity SC", "80% Warning", "ค่าเฉลี่ย SC"],
                    "bottom": 0,
                    "textStyle": {"color": "#9CA3AF"},
                },
                "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "10%", "containLabel": True},
                "xAxis": {
                    "type": "category",
                    "data": upcoming_dates,
                    "axisLine": {"lineStyle": {"color": "#374151"}},
                    "axisLabel": {"color": "#9CA3AF", "rotate": 45 if len(upcoming_dates) > 15 else 0},
                },
                "yAxis": {
                    "type": "value",
                    "axisLine": {"lineStyle": {"color": "#374151"}},
                    "axisLabel": {"color": "#9CA3AF"},
                    "splitLine": {"lineStyle": {"color": "#1F2937"}},
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
                            "color": "#9CA3AF",
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
        st.caption(f"📌 แสดงข้อมูล {days_ahead} วันข้างหน้า เทียบกับ Capacity ต่อวัน")

        if stats['by_center']:
            # Treemap - Appointments vs Capacity
            st.markdown("#### 🗺️ Treemap: ปริมาณนัดหมาย vs Capacity")

            # Treemap view mode selector
            treemap_col1, treemap_col2, treemap_col3 = st.columns([2, 1, 1])
            with treemap_col2:
                treemap_mode = st.radio(
                    "มุมมอง",
                    options=["รายวัน", "รายเดือน"],
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

            st.markdown("**ขนาดกล่อง** = ปริมาณนัดหมาย | **สี** = 🟢 ปกติ (<80%) | 🟡 ใกล้เต็ม (80-89%) | 🔴 เกิน (≥90%) | ⚫ ไม่มี Capacity")

            # Calculate days in range for monthly calculation
            today = date.today()
            chart_end_date = stats.get('max_date', today + timedelta(days=days_ahead-1))
            if chart_end_date:
                days_in_range = (chart_end_date - today).days + 1
            else:
                days_in_range = days_ahead

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

                if treemap_mode == "รายวัน":
                    # Daily view: use avg_daily vs daily capacity
                    display_value = c['avg_daily']
                    if capacity:
                        usage_pct = (c['avg_daily'] / capacity) * 100
                    else:
                        usage_pct = None
                    value_label = f"{c['avg_daily']:.0f}/วัน"
                    capacity_label = f"{capacity:,}/วัน" if capacity else "N/A"
                else:
                    # Monthly view: use total count vs monthly capacity (capacity * days)
                    display_value = c['count']
                    monthly_capacity = capacity * days_in_range if capacity else None
                    if monthly_capacity:
                        usage_pct = (c['count'] / monthly_capacity) * 100
                    else:
                        usage_pct = None
                    value_label = f"{c['count']:,} ({days_in_range} วัน)"
                    capacity_label = f"{monthly_capacity:,} ({days_in_range} วัน)" if monthly_capacity else "N/A"

                # Determine color based on usage
                # 🟢 Green = <80%, 🟡 Yellow = 80-89%, 🔴 Red = ≥90%
                if capacity is None:
                    color = '#6B7280'  # Gray - no capacity data
                    status = 'unknown'
                elif usage_pct and usage_pct >= 90:
                    color = '#EF4444'  # Red - ≥90%
                    status = 'over'
                elif usage_pct and usage_pct >= 80:
                    color = '#F59E0B'  # Yellow - 80-89%
                    status = 'warning'
                else:
                    color = '#10B981'  # Green - <80%
                    status = 'normal'

                usage_text = f"{usage_pct:.0f}%" if usage_pct else "N/A"

                treemap_data.append({
                    "name": c['branch_code'],  # Show branch_code in box
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
                    var chart = echarts.init(document.getElementById('treemap'), 'dark');
                    var option = {{
                        backgroundColor: 'transparent',
                        tooltip: {{
                            trigger: 'item',
                            backgroundColor: 'rgba(30, 41, 59, 0.95)',
                            borderColor: '#475569',
                            borderRadius: 8,
                            padding: [10, 14],
                            textStyle: {{color: '#F1F5F9', fontSize: 13}},
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
                                borderColor: '#1F2937',
                                borderWidth: 2,
                                gapWidth: 2
                            }},
                            levels: [{{
                                itemStyle: {{
                                    borderColor: '#374151',
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
                    st.caption(f"📌 แสดงนัดหมายรวม {days_in_range} วัน เทียบกับ Capacity รวม{type_desc} | จำนวน {len(filtered_centers)} ศูนย์")
            else:
                st.info(f"ไม่พบข้อมูลศูนย์ประเภท {center_type_filter}")

            st.markdown("---")

            col1, col2 = st.columns([3, 2])

            with col1:
                # Horizontal bar chart - top 20 (filtered by center type)
                bar_centers = filtered_centers[:20] if filtered_centers else stats['by_center'][:20]
                center_names = [c['branch_name'][:30] + '...' if len(c['branch_name']) > 30 else c['branch_name'] for c in reversed(bar_centers)]
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
                    var chart = echarts.init(document.getElementById('center_bar'), 'dark');
                    var option = {{
                        backgroundColor: 'transparent',
                        tooltip: {{
                            trigger: 'axis',
                            axisPointer: {{type: 'shadow'}},
                            backgroundColor: 'rgba(30, 41, 59, 0.95)',
                            borderColor: '#475569',
                            textStyle: {{color: '#F1F5F9'}},
                        }},
                        legend: {{
                            data: ['เฉลี่ย/วัน', 'Capacity'],
                            bottom: 0,
                            textStyle: {{color: '#9CA3AF'}},
                        }},
                        grid: {{left: '3%', right: '10%', bottom: '12%', top: '5%', containLabel: true}},
                        xAxis: {{
                            type: 'value',
                            axisLine: {{lineStyle: {{color: '#374151'}}}},
                            axisLabel: {{color: '#9CA3AF'}},
                            splitLine: {{lineStyle: {{color: '#1F2937'}}}},
                        }},
                        yAxis: {{
                            type: 'category',
                            data: {json.dumps(center_names, ensure_ascii=False)},
                            axisLine: {{lineStyle: {{color: '#374151'}}}},
                            axisLabel: {{color: '#9CA3AF', fontSize: 10}},
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
                                    color: '#9CA3AF',
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
                                itemStyle: {{color: '#F1F5F9', borderColor: '#374151', borderWidth: 1}}
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
                        "ศูนย์": c['branch_name'][:25] + '...' if len(c['branch_name']) > 25 else c['branch_name'],
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
                <div style="background: linear-gradient(135deg, #1E293B, #0F172A); border-radius: 8px; padding: 12px; border: 1px solid #374151; margin-top: 12px;">
                    <p style="color: #9CA3AF; font-size: 0.8rem; margin: 0;">
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

            # Apply conditional formatting based on capacity
            date_col_names = [col_rename[d] for d in date_cols_sorted]

            def highlight_capacity(row):
                """Apply color based on usage vs capacity."""
                capacity = row['Capacity/วัน']
                styles = [''] * len(row)

                for i, col in enumerate(row.index):
                    if col in date_col_names:
                        val = row[col]
                        if pd.notna(capacity) and capacity > 0:
                            usage_pct = (val / capacity) * 100
                            if usage_pct >= 100:
                                # Red - over capacity
                                styles[i] = 'background-color: rgba(239, 68, 68, 0.6); color: white; font-weight: bold'
                            elif usage_pct >= 80:
                                # Yellow/Orange - warning (80-99%)
                                styles[i] = 'background-color: rgba(245, 158, 11, 0.5); color: white; font-weight: bold'
                            elif usage_pct >= 50:
                                # Light green - moderate (50-79%)
                                styles[i] = 'background-color: rgba(16, 185, 129, 0.2)'
                            # else: no style (normal)
                return styles

            styled_df = display_df.style.apply(highlight_capacity, axis=1)

            st.markdown("""
            <div style="background: linear-gradient(135deg, #1E293B, #0F172A); border-radius: 8px; padding: 10px 16px; border: 1px solid #374151; margin-bottom: 12px;">
                <span style="color: #9CA3AF; font-size: 0.85rem;">
                    <b>สี:</b>
                    <span style="background: rgba(239, 68, 68, 0.6); padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🔴 เต็ม/เกิน (≥100%)</span>
                    <span style="background: rgba(245, 158, 11, 0.5); padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🟡 ใกล้เต็ม (80-99%)</span>
                    <span style="background: rgba(16, 185, 129, 0.2); padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🟢 ปกติ (50-79%)</span>
                    <span style="padding: 2px 8px; margin-left: 8px;">⬜ ว่าง (<50%)</span>
                </span>
            </div>
            """, unsafe_allow_html=True)

            st.dataframe(styled_df, hide_index=True, use_container_width=True, height=600)

            # Download button
            csv = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 ดาวน์โหลด CSV",
                csv,
                f"forecast_{date.today().strftime('%Y%m%d')}.csv",
                "text/csv",
                key="download_forecast_csv"
            )

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
