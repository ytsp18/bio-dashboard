"""Queue Slots page - Calendar Heatmap showing available slots per center/day with automatic slot cutting."""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from io import BytesIO
from html import escape as html_escape
import calendar
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db
from streamlit_echarts import st_echarts
from utils.theme import apply_theme, render_theme_toggle
from utils.auth_check import require_login
from utils.branch_display import get_branch_short_name

init_db()

st.set_page_config(page_title="Queue Slots - Bio Dashboard", page_icon="🎯", layout="wide")


# ============================================================
# Cached Data Functions (local imports เพื่อป้องกัน cache break)
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_capacity_map():
    """ดึง max_capacity ของทุกศูนย์จาก BranchMaster."""
    from database.connection import get_session as _get_session
    from database.models import BranchMaster as _BM

    _session = _get_session()
    try:
        rows = _session.query(
            _BM.branch_code, _BM.branch_name, _BM.max_capacity
        ).filter(_BM.max_capacity.isnot(None)).all()

        result = {}
        for r in rows:
            result[r.branch_code] = {
                'name': get_branch_short_name(r.branch_code, r.branch_name),
                'capacity': r.max_capacity,
            }
        return result
    finally:
        _session.close()


@st.cache_data(ttl=3600, show_spinner=False)
def get_booked_slots(start_date, end_date, selected_branches=None):
    """ดึงจำนวน appointment ที่จองแล้ว GROUP BY branch_code, appt_date."""
    from database.connection import get_session as _get_session
    from database.models import Appointment as _Appt
    from sqlalchemy import func as _func, and_ as _and

    _session = _get_session()
    try:
        filters = [
            _Appt.appt_date >= start_date,
            _Appt.appt_date <= end_date,
            _Appt.appt_status.in_(['SUCCESS', 'WAITING']),
            _Appt.branch_code.isnot(None),
        ]
        if selected_branches:
            filters.append(_Appt.branch_code.in_(selected_branches))

        rows = _session.query(
            _Appt.branch_code,
            _Appt.appt_date,
            _func.count(_func.distinct(_Appt.appointment_id)).label('booked')
        ).filter(_and(*filters)).group_by(
            _Appt.branch_code, _Appt.appt_date
        ).all()

        result = {}
        for r in rows:
            key = (r.branch_code, r.appt_date.isoformat() if r.appt_date else None)
            result[key] = r.booked
        return result
    finally:
        _session.close()


@st.cache_data(ttl=3600, show_spinner=False)
def get_slot_cut_data(start_date, end_date, selected_branches=None):
    """ดึงข้อมูล slot ที่ถูกตัด — ผู้รับบริการไปออกบัตรผิดวัน/ผิดศูนย์แล้ว."""
    from database.connection import get_session as _get_session
    from database.models import Card as _Card
    from sqlalchemy import func as _func, and_ as _and, or_ as _or

    _session = _get_session()
    try:
        base_filters = [
            _or(_Card.wrong_date == True, _Card.wrong_branch == True),
            _Card.print_status == 'G',
            _Card.appt_branch.isnot(None),
            _Card.appt_date.isnot(None),
            _Card.appt_date >= start_date,
            _Card.appt_date <= end_date,
        ]
        if selected_branches:
            base_filters.append(_Card.appt_branch.in_(selected_branches))

        # นับ slot ที่ตัดรวม GROUP BY ศูนย์+วัน
        agg_rows = _session.query(
            _Card.appt_branch,
            _Card.appt_date,
            _func.count(_func.distinct(_Card.appointment_id)).label('cut_count')
        ).filter(_and(*base_filters)).group_by(
            _Card.appt_branch, _Card.appt_date
        ).all()

        by_branch_date = {}
        by_branch = {}
        total_cuts = 0
        for r in agg_rows:
            key = (r.appt_branch, r.appt_date.isoformat() if r.appt_date else None)
            by_branch_date[key] = r.cut_count
            by_branch[r.appt_branch] = by_branch.get(r.appt_branch, 0) + r.cut_count
            total_cuts += r.cut_count

        # ดึงรายละเอียดสำหรับตาราง expander
        detail_rows = _session.query(
            _Card.appointment_id,
            _Card.appt_branch,
            _Card.appt_date,
            _Card.branch_code,
            _Card.branch_name,
            _Card.print_date,
            _Card.serial_number,
            _Card.wrong_date,
            _Card.wrong_branch,
        ).filter(_and(*base_filters)).distinct().all()

        details = []
        for r in detail_rows:
            details.append({
                'Appointment ID': r.appointment_id,
                'ศูนย์นัดเดิม': r.appt_branch,
                'วันนัดเดิม': r.appt_date.strftime('%d/%m/%Y') if r.appt_date else '-',
                'ศูนย์ที่ไปจริง': get_branch_short_name(r.branch_code, r.branch_name),
                'วันที่ไปจริง': r.print_date.strftime('%d/%m/%Y') if r.print_date else '-',
                'Serial Number': r.serial_number or '-',
                'ผิดวัน': '✓' if r.wrong_date else '',
                'ผิดศูนย์': '✓' if r.wrong_branch else '',
            })

        return {
            'by_branch_date': by_branch_date,
            'by_branch': by_branch,
            'total_cuts': total_cuts,
            'details': details,
        }
    finally:
        _session.close()


# ============================================================
# หน้าหลัก
# ============================================================

require_login()
apply_theme()

st.title("🎯 Slot ว่าง & ตัดคิว")
st.caption("แสดง Slot ว่างรายศูนย์/รายวัน พร้อมตัด Slot อัตโนมัติจากผู้รับบริการที่ไปผิดวัน/ผิดศูนย์")

# ---------- ตัวกรอง ----------
today = date.today()

# เลือกเดือน/ปี
col_nav1, col_nav2, col_nav3 = st.columns([1, 3, 1])
with col_nav1:
    if st.button("◀ เดือนก่อน", key="prev_month", use_container_width=True):
        if 'slot_month' not in st.session_state:
            st.session_state.slot_month = today.month
            st.session_state.slot_year = today.year
        m = st.session_state.slot_month - 1
        if m < 1:
            m = 12
            st.session_state.slot_year -= 1
        st.session_state.slot_month = m
        st.rerun()

with col_nav3:
    if st.button("เดือนถัดไป ▶", key="next_month", use_container_width=True):
        if 'slot_month' not in st.session_state:
            st.session_state.slot_month = today.month
            st.session_state.slot_year = today.year
        m = st.session_state.slot_month + 1
        if m > 12:
            m = 1
            st.session_state.slot_year += 1
        st.session_state.slot_month = m
        st.rerun()

sel_month = st.session_state.get('slot_month', today.month)
sel_year = st.session_state.get('slot_year', today.year)

thai_months = ['', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
               'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
be_year = sel_year + 543

with col_nav2:
    st.markdown(f"<h3 style='text-align:center; margin:0;'>📅 {thai_months[sel_month]} {be_year}</h3>", unsafe_allow_html=True)

# ช่วงวันที่ของเดือนที่เลือก
first_day = date(sel_year, sel_month, 1)
last_day = date(sel_year, sel_month, calendar.monthrange(sel_year, sel_month)[1])

# ตัวกรองศูนย์
capacity_map = get_capacity_map()
if not capacity_map:
    st.warning("⚠️ ไม่พบข้อมูล Capacity ของศูนย์ — กรุณาตรวจสอบตาราง Branch Master")
    st.stop()
branch_options = {k: f"{v['name']} ({k})" for k, v in sorted(capacity_map.items(), key=lambda x: x[1]['name'])}

# โหมดแสดงผล: ทุกศูนย์ หรือ เลือกศูนย์
view_mode = st.radio(
    "🏢 โหมดแสดงผล",
    options=["all", "select"],
    format_func=lambda x: {"all": "📊 ทุกศูนย์ (รวม)", "select": "🏢 เลือกศูนย์ (รายศูนย์)"}[x],
    horizontal=True,
    key="slot_view_mode",
)

selected_branches = None
if view_mode == "select":
    selected_branches = st.multiselect(
        "เลือกศูนย์ (สูงสุด 6 ศูนย์)",
        options=list(branch_options.keys()),
        format_func=lambda x: branch_options.get(x, x),
        max_selections=6,
        key="slot_branches",
        placeholder="คลิกเพื่อเลือกศูนย์..."
    )
    if not selected_branches:
        st.info("กรุณาเลือกศูนย์อย่างน้อย 1 ศูนย์")
        st.stop()

# ---------- โหลดข้อมูล ----------
with st.spinner("กำลังโหลดข้อมูล..."):
    booked_data = get_booked_slots(first_day, last_day, selected_branches)
    cut_data = get_slot_cut_data(first_day, last_day, selected_branches)

# ---------- คำนวณสรุป ----------
total_capacity = 0
total_booked = 0
total_cuts = cut_data['total_cuts']
num_days = (last_day - first_day).days + 1

# นับวันทำการ (ไม่รวมเสาร์-อาทิตย์)
working_days = sum(1 for d in range(num_days) if (first_day + timedelta(days=d)).weekday() < 5)

all_branches_set = {bc for bc in capacity_map.keys() if '-MB-' not in str(bc).upper()}

if view_mode == "all":
    for bc in all_branches_set:
        total_capacity += capacity_map[bc]['capacity'] * working_days
    # นับเฉพาะ branch ที่มี capacity (ไม่รวม branch ที่ไม่ได้ตั้ง max_capacity)
    total_booked = sum(v for (b, d), v in booked_data.items() if b in all_branches_set)
else:
    for bc in selected_branches:
        cap = capacity_map.get(bc, {}).get('capacity', 0)
        total_capacity += cap * working_days
    total_booked = sum(v for (b, d), v in booked_data.items() if b in selected_branches)

total_available = total_capacity - total_booked + total_cuts

# ---------- Metrics สรุป ----------
st.markdown("---")
mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    st.metric("📦 Capacity รวม", f"{total_capacity:,}",
              help=f"max_capacity × {working_days} วันทำการ")
with mc2:
    st.metric("📅 จองแล้ว", f"{total_booked:,}",
              delta=f"{(total_booked/total_capacity*100):.0f}%" if total_capacity > 0 else None,
              delta_color="off")
with mc3:
    st.metric("✂️ ตัดแล้ว", f"{total_cuts:,}",
              help="Slot ที่ผู้รับบริการไปผิดวัน/ผิดศูนย์ → ตัดออกจากจองแล้ว")
with mc4:
    avail_pct = (total_available / total_capacity * 100) if total_capacity > 0 else 0
    st.metric("✅ Slot ว่าง", f"{total_available:,}",
              delta=f"{avail_pct:.0f}%",
              delta_color="normal" if avail_pct >= 10 else "inverse")


# ============================================================
# Calendar Heatmap
# ============================================================

def build_calendar_data(branches_list, booked, cuts, cap_map, month, year):
    """สร้างข้อมูล calendar heatmap สำหรับศูนย์ที่เลือก."""
    num_days = calendar.monthrange(year, month)[1]
    data = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        d_str = d.isoformat()
        day_booked = 0
        day_cuts = 0
        day_capacity = 0
        for bc in branches_list:
            day_booked += booked.get((bc, d_str), 0)
            day_cuts += cuts.get((bc, d_str), 0)
            cap = cap_map.get(bc, {}).get('capacity', 0)
            if d.weekday() < 5:  # นับ capacity เฉพาะวันทำการ
                day_capacity += cap
        available = day_capacity - day_booked + day_cuts
        # เก็บ: [วันที่, ว่าง, capacity, จอง, ตัด]
        data.append([d_str, available, day_capacity, day_booked, day_cuts])
    return data


def build_calendar_options(cal_data, month, year, title="", max_cap=None):
    """สร้าง ECharts options สำหรับ calendar heatmap.

    Data format: [date_str, available_count] — ใช้ available เป็นค่าหลัก
    เพื่อให้ label แสดง {c} = จำนวนว่าง และ visualMap map สีจากจำนวนว่าง
    """
    num_days = calendar.monthrange(year, month)[1]
    range_start = f"{year}-{month:02d}-01"
    range_end = f"{year}-{month:02d}-{num_days:02d}"

    # ข้อมูล heatmap: [{value: [date, count], ...}] — rich format for per-item label control
    heatmap_data = []
    for item in cal_data:
        d_str, available, capacity, booked, cuts = item
        if capacity > 0:
            heatmap_data.append({"value": [d_str, available]})
        else:
            # วันหยุด (capacity=0) → ค่า -1 + ซ่อน label
            heatmap_data.append({
                "value": [d_str, -1],
                "label": {"show": False}
            })

    if max_cap is None:
        max_cap = max((item[2] for item in cal_data), default=100)
    # คำนวณ threshold สำหรับ visualMap (สีตาม % ของ max capacity)
    threshold_20 = round(max_cap * 0.20)
    threshold_10 = round(max_cap * 0.10)

    options = {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}} if title else {},
        "tooltip": {
            "show": False,
        },
        "visualMap": {
            "min": -1,
            "max": max(max_cap, 1),
            "calculable": False,
            "orient": "horizontal",
            "left": "center",
            "bottom": 0,
            "show": False,  # Hide built-in legend — use HTML legend below chart
            "inRange": {
                "color": ["#7f1d1d", "#ef4444", "#eab308", "#22c55e", "#16a34a"]
            },
            "pieces": [
                {"min": -1, "max": -1, "color": "#e5e7eb", "label": "วันหยุด"},
                {"min": 0, "max": 0, "color": "#7f1d1d", "label": "เต็ม"},
                {"min": 1, "max": threshold_10, "color": "#ef4444", "label": f"<10% (≤{threshold_10})"},
                {"min": threshold_10 + 1, "max": threshold_20, "color": "#eab308", "label": f"10-20%"},
                {"min": threshold_20 + 1, "max": max_cap * 2, "color": "#22c55e", "label": f"≥20% (>{threshold_20})"},
            ],
            "type": "piecewise",
            "textStyle": {"fontSize": 11},
        },
        "calendar": {
            "range": [range_start, range_end],
            "cellSize": ["auto", 50],
            "top": 60 if title else 30,
            "left": 60,
            "right": 30,
            "orient": "horizontal",
            "dayLabel": {
                "nameMap": ["อา", "จ", "อ", "พ", "พฤ", "ศ", "ส"],
                "firstDay": 1,
            },
            "monthLabel": {"show": False},
            "yearLabel": {"show": False},
            "itemStyle": {
                "borderWidth": 2,
                "borderColor": "#fff",
            },
            "splitLine": {"show": False},
        },
        "series": [{
            "type": "heatmap",
            "coordinateSystem": "calendar",
            "data": heatmap_data,
            "label": {
                "show": True,
                "formatter": "{@[1]}",
                "fontSize": 10,
                "fontWeight": "bold",
                "color": "#333",
            },
            "emphasis": {
                "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)"}
            },
        }],
    }
    return options


st.markdown("---")

# ---------- Calendar Heatmap ----------
if view_mode == "all":
    # Classify branches by service type
    sc_branches = [bc for bc in all_branches_set if '-SC-' in str(bc).upper()]
    ob_branches = [bc for bc in all_branches_set if '-OB-' in str(bc).upper()]

    st.subheader("📅 Calendar Heatmap — แยกตามประเภทบริการ")

    # Show SC and OB heatmaps stacked vertically for full width
    st.markdown("**🏢 ศูนย์บริการ (SC)**")
    if sc_branches:
        cal_sc = build_calendar_data(sc_branches, booked_data, cut_data['by_branch_date'], capacity_map, sel_month, sel_year)
        max_cap_sc = sum(capacity_map.get(bc, {}).get('capacity', 0) for bc in sc_branches)
        options_sc = build_calendar_options(cal_sc, sel_month, sel_year, max_cap=max_cap_sc)
        st_echarts(options=options_sc, height="280px", key="cal_sc")
    else:
        st.info("ไม่พบข้อมูลศูนย์ SC")

    st.markdown("**🏗️ ศูนย์แรกรับ (OB)**")
    if ob_branches:
        cal_ob = build_calendar_data(ob_branches, booked_data, cut_data['by_branch_date'], capacity_map, sel_month, sel_year)
        max_cap_ob = sum(capacity_map.get(bc, {}).get('capacity', 0) for bc in ob_branches)
        options_ob = build_calendar_options(cal_ob, sel_month, sel_year, max_cap=max_cap_ob)
        st_echarts(options=options_ob, height="280px", key="cal_ob")
    else:
        st.info("ไม่พบข้อมูลศูนย์ OB")

    # คำอธิบายสี
    st.markdown("""
    <div style="background: #ffffff; border-radius: 8px; padding: 8px 16px; border: 1px solid #e5e7eb;">
        <span style="color: #6b7280; font-size: 0.85rem;">
            <b>สี:</b>
            <span style="background: #16a34a; color: white; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🟢 ≥20% ว่าง</span>
            <span style="background: #eab308; color: white; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🟡 10-20%</span>
            <span style="background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🔴 <10%</span>
            <span style="background: #7f1d1d; color: white; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">⚫ เกิน Cap</span>
            <span style="padding: 2px 8px; margin-left: 8px;">⬜ วันหยุด</span>
        </span>
    </div>
    """, unsafe_allow_html=True)

else:
    # โหมดรายศูนย์: หลาย calendar วาง grid
    st.subheader(f"📅 Calendar Heatmap — รายศูนย์ ({len(selected_branches)} ศูนย์)")

    if len(selected_branches) == 1:
        # ศูนย์เดียว: calendar เต็มจอ
        bc = selected_branches[0]
        info = capacity_map.get(bc, {})
        cal_data = build_calendar_data([bc], booked_data, cut_data['by_branch_date'], capacity_map, sel_month, sel_year)
        title = f"{info.get('name', bc)} (Cap: {info.get('capacity', '?')}/วัน)"
        options = build_calendar_options(cal_data, sel_month, sel_year, title=title, max_cap=info.get('capacity', 100))
        st_echarts(options=options, height="320px", key=f"cal_{bc}")
    else:
        # หลายศูนย์: วาง grid 2-3 คอลัมน์
        n_cols = 2 if len(selected_branches) <= 4 else 3
        cols = st.columns(n_cols)
        for i, bc in enumerate(selected_branches):
            info = capacity_map.get(bc, {})
            cal_data = build_calendar_data([bc], booked_data, cut_data['by_branch_date'], capacity_map, sel_month, sel_year)
            title = f"{info.get('name', bc)} ({info.get('capacity', '?')}/วัน)"
            options = build_calendar_options(cal_data, sel_month, sel_year, title=title, max_cap=info.get('capacity', 100))
            with cols[i % n_cols]:
                st_echarts(options=options, height="280px", key=f"cal_{bc}")

    # คำอธิบายสี (เหมือนโหมดรวม)
    st.markdown("""
    <div style="background: #ffffff; border-radius: 8px; padding: 8px 16px; border: 1px solid #e5e7eb;">
        <span style="color: #6b7280; font-size: 0.85rem;">
            <b>สี:</b>
            <span style="background: #16a34a; color: white; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🟢 ≥20% ว่าง</span>
            <span style="background: #eab308; color: white; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🟡 10-20%</span>
            <span style="background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">🔴 <10%</span>
            <span style="background: #7f1d1d; color: white; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">⚫ เกิน Cap</span>
            <span style="padding: 2px 8px; margin-left: 8px;">⬜ วันหยุด</span>
        </span>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# ตาราง Slot 7 วันข้างหน้า
# ============================================================

st.markdown("---")
st.subheader("📋 ตาราง Slot 7 วันข้างหน้า")

# สร้าง 7 วันทำการถัดไป
upcoming_dates = []
d = today
while len(upcoming_dates) < 7:
    if d.weekday() < 5:  # จันทร์-ศุกร์
        upcoming_dates.append(d)
    d += timedelta(days=1)

# กำหนดศูนย์ที่แสดง
table_branches = selected_branches if selected_branches else list(all_branches_set)

# โหลดข้อมูล 7 วัน (อาจต่างเดือนกับ calendar)
booked_7d = get_booked_slots(upcoming_dates[0], upcoming_dates[-1], table_branches if selected_branches else None)
cut_7d = get_slot_cut_data(upcoming_dates[0], upcoming_dates[-1], table_branches if selected_branches else None)

# สร้างข้อมูลตาราง
table_rows = []
for bc in table_branches:
    info = capacity_map.get(bc, {})
    cap = info.get('capacity', 0)
    name = info.get('name', bc)
    total_avail = 0
    row_data = {'branch_code': bc, 'name': name, 'capacity': cap, 'days': []}
    for ud in upcoming_dates:
        d_str = ud.isoformat()
        booked = booked_7d.get((bc, d_str), 0)
        cuts = cut_7d['by_branch_date'].get((bc, d_str), 0)
        available = cap - booked + cuts
        total_avail += available
        row_data['days'].append({
            'date': ud,
            'booked': booked,
            'cuts': cuts,
            'available': available,
        })
    row_data['total_avail'] = total_avail
    table_rows.append(row_data)

# Classify rows by service type then sort within each group
def get_service_type(bc):
    bc_upper = str(bc).upper()
    if '-SC-' in bc_upper:
        return 'SC'
    elif '-OB-' in bc_upper:
        return 'OB'
    elif '-MB-' in bc_upper:
        return 'MB'
    return 'OTHER'

for row in table_rows:
    row['service_type'] = get_service_type(row['branch_code'])

# Sort: SC first, then OB, then others — within each group sort by availability
type_order = {'SC': 0, 'OB': 1, 'MB': 2, 'OTHER': 3}
table_rows.sort(key=lambda x: (type_order.get(x['service_type'], 9), x['total_avail']))


def get_slot_cell_style(available, capacity):
    """กำหนดสี cell ตามจำนวน slot ว่างเทียบกับ capacity."""
    if capacity <= 0:
        return ''
    pct = available / capacity * 100
    if pct < 0:
        return 'background-color: #7f1d1d; color: white; font-weight: bold;'
    elif pct < 10:
        return 'background-color: #ef4444; color: white; font-weight: bold;'
    elif pct < 20:
        return 'background-color: #eab308; color: white; font-weight: bold;'
    elif pct >= 20:
        return 'background-color: rgba(34, 197, 94, 0.3);'
    return ''


# สร้างตาราง HTML
html_parts = ['''
<style>
.slot-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.slot-table th { background: #f3f4f6; color: #6b7280; padding: 8px 6px; text-align: center; border: 1px solid #e5e7eb; position: sticky; top: 0; z-index: 1; }
.slot-table td { padding: 6px; text-align: center; border: 1px solid #e5e7eb; }
.slot-table tr:hover { background: rgba(59, 130, 246, 0.08); }
.slot-table .center-name { text-align: left; min-width: 180px; max-width: 280px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
<div style="max-height: 500px; overflow: auto; border: 1px solid #e5e7eb; border-radius: 8px;">
<table class="slot-table">
<thead><tr>
<th class="center-name">ศูนย์</th>
<th>Cap/วัน</th>
''']

# หัวคอลัมน์วันที่
thai_day_names = ['จ', 'อ', 'พ', 'พฤ', 'ศ', 'ส', 'อา']
for ud in upcoming_dates:
    day_name = thai_day_names[ud.weekday()]
    html_parts.append(f'<th>{ud.strftime("%d/%m")}<br/><small>{day_name}</small></th>')
html_parts.append('</tr></thead><tbody>')

# แถวข้อมูล — แยกกลุ่มตามประเภทบริการ
type_labels = {'SC': '🏢 ศูนย์บริการ (SC)', 'OB': '🏗️ ศูนย์แรกรับ (OB)', 'MB': '🚐 หน่วยเคลื่อนที่ (MB)', 'OTHER': '📦 อื่นๆ'}
current_type = None
num_cols = len(upcoming_dates) + 2  # name + cap + dates
for row in table_rows:
    stype = row.get('service_type', 'OTHER')
    if stype != current_type:
        current_type = stype
        label = type_labels.get(stype, stype)
        html_parts.append(f'<tr><td colspan="{num_cols}" style="background: #f0f4ff; color: #3b82f6; font-weight: bold; text-align: left; padding: 8px 12px; border-top: 2px solid #93c5fd;">{label}</td></tr>')
    html_parts.append('<tr>')
    name = html_escape(str(row['name'])[:35])
    full_name = html_escape(str(row['name']))
    cap = row['capacity']
    cap_str = f"{cap:,}" if cap is not None and cap > 0 else '-'
    html_parts.append(f'<td class="center-name" title="{full_name}">{name}</td>')
    html_parts.append(f'<td>{cap_str}</td>')

    for day_data in row['days']:
        available = day_data['available']
        cuts = day_data['cuts']
        style = get_slot_cell_style(available, cap)

        if cap <= 0:
            cell_text = '-'
        elif available < 0:
            over = abs(available)
            cell_text = f"<b>เกิน {over}</b>"
            if cuts > 0:
                cell_text += f" <small style='color:#d97706;'>✂️{cuts}</small>"
        else:
            cell_text = f"{available}/{cap}"
            if cuts > 0:
                cell_text += f" <small style='color:#d97706;'>✂️{cuts}</small>"
        html_parts.append(f'<td style="{style}">{cell_text}</td>')

    html_parts.append('</tr>')

html_parts.append('</tbody></table></div>')
st.markdown(''.join(html_parts), unsafe_allow_html=True)

# คำอธิบายการอ่านค่า
st.markdown("""
<div style="background: #ffffff; border-radius: 8px; padding: 8px 16px; border: 1px solid #e5e7eb; margin-top: 8px;">
    <span style="color: #6b7280; font-size: 0.85rem;">
        <b>อ่านค่า:</b> <code>ว่าง/Cap</code> เช่น <code>12/80</code> = ว่าง 12 จาก 80 |
        <b style="color: #7f1d1d;">เกิน 5</b> = จองเกิน Cap 5 slot |
        <span style="color: #d97706;">✂️3</span> = ตัด 3 slot |
        <b>สี:</b>
        <span style="background: rgba(34,197,94,0.3); padding: 1px 6px; border-radius: 3px;">≥20%</span>
        <span style="background: #eab308; color: white; padding: 1px 6px; border-radius: 3px;">10-20%</span>
        <span style="background: #ef4444; color: white; padding: 1px 6px; border-radius: 3px;"><10%</span>
        <span style="background: #7f1d1d; color: white; padding: 1px 6px; border-radius: 3px;">เกิน</span>
    </span>
</div>
""", unsafe_allow_html=True)


# ============================================================
# รายละเอียดการตัด Slot
# ============================================================

st.markdown("---")

details = cut_data['details']
with st.expander(f"✂️ รายละเอียดการตัด Slot ({len(details):,} รายการ)", expanded=False):
    if details:
        df_details = pd.DataFrame(details)
        st.dataframe(df_details, hide_index=True, use_container_width=True, height=400)

        # ดาวน์โหลด Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_details.to_excel(writer, index=False, sheet_name='Slot Cuts')
        buffer.seek(0)

        st.download_button(
            label="📥 ดาวน์โหลด Excel",
            data=buffer,
            file_name=f"slot_cuts_{sel_month:02d}_{sel_year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_cuts",
        )
    else:
        st.info("ไม่มีข้อมูลการตัด Slot ในเดือนที่เลือก")

# คำอธิบายสูตรคำนวณ
st.markdown("""
<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px 16px; margin-top: 12px;">
    <b>📐 สูตรคำนวณ:</b><br/>
    <code>Slot ว่าง = Capacity - จองแล้ว + ตัดแล้ว</code><br/>
    <small style="color: #6b7280;">✂️ ตัด = ผู้รับบริการที่นัดไว้ที่ศูนย์/วันนี้ แต่ไปออกบัตรที่ศูนย์อื่นหรือวันอื่นแล้ว (print_status = G)</small>
</div>
""", unsafe_allow_html=True)
