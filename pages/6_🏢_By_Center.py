"""By Center & Region page - Statistics by service center and region (Sheet 4 & 5)."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_echarts import st_echarts
from io import BytesIO
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session, get_branch_name_map_cached
from utils.branch_display import get_branch_short_name_map
from database.models import Card, BranchMaster
from services.data_service import DataService
from sqlalchemy import func, and_, case, or_
from utils.theme import apply_theme, render_theme_toggle
from utils.auth_check import require_login

init_db()

st.set_page_config(page_title="Center & Region - Bio Dashboard", page_icon="🏢", layout="wide")


@st.cache_data(ttl=3600, show_spinner=False)
def get_center_stats_cached(start_date, end_date):
    """Cached center statistics query."""
    from types import SimpleNamespace
    from database.connection import get_session as _get_session
    from database.models import Card as _Card
    from sqlalchemy import func as _func, and_ as _and, case as _case

    _session = _get_session()
    try:
        result = _session.query(
            _Card.branch_code,
            _Card.branch_name,
            _func.count(_Card.id).label('total'),
            _func.sum(_case((_Card.print_status == 'G', 1), else_=0)).label('good_count'),
            _func.sum(_case((_Card.print_status == 'B', 1), else_=0)).label('bad_count'),
            _func.avg(_Card.sla_minutes).label('avg_sla'),
            _func.max(_Card.sla_minutes).label('max_sla'),
            _func.sum(_case((_Card.sla_over_12min == True, 1), else_=0)).label('sla_over_count'),
            _func.sum(_case((_Card.wrong_branch == True, 1), else_=0)).label('wrong_branch_count'),
            _func.sum(_case((_Card.wrong_date == True, 1), else_=0)).label('wrong_date_count')
        ).filter(
            _and(_Card.print_date >= start_date, _Card.print_date <= end_date),
            _Card.branch_code.isnot(None)
        ).group_by(_Card.branch_code, _Card.branch_name).order_by(
            _func.count(_Card.id).desc()
        ).all()

        return [SimpleNamespace(
            branch_code=r.branch_code,
            branch_name=r.branch_name,
            total=r.total,
            good_count=r.good_count or 0,
            bad_count=r.bad_count or 0,
            avg_sla=float(r.avg_sla) if r.avg_sla else 0.0,
            max_sla=float(r.max_sla) if r.max_sla else 0.0,
            sla_over_count=r.sla_over_count or 0,
            wrong_branch_count=r.wrong_branch_count or 0,
            wrong_date_count=r.wrong_date_count or 0,
        ) for r in result]
    finally:
        _session.close()


@st.cache_data(ttl=3600, show_spinner=False)
def get_region_stats_cached(start_date, end_date):
    """Cached region statistics query."""
    from types import SimpleNamespace
    from database.connection import get_session as _get_session
    from database.models import Card as _Card
    from sqlalchemy import func as _func, and_ as _and, case as _case

    _session = _get_session()
    try:
        result = _session.query(
            _Card.region,
            _func.count(_Card.id).label('total'),
            _func.sum(_case((_Card.print_status == 'G', 1), else_=0)).label('good_count'),
            _func.sum(_case((_Card.print_status == 'B', 1), else_=0)).label('bad_count'),
            _func.avg(_Card.sla_minutes).label('avg_sla'),
            _func.max(_Card.sla_minutes).label('max_sla'),
            _func.sum(_case((_Card.sla_over_12min == True, 1), else_=0)).label('sla_over_count'),
            _func.sum(_case((_Card.wrong_branch == True, 1), else_=0)).label('wrong_branch_count'),
            _func.sum(_case((_Card.wrong_date == True, 1), else_=0)).label('wrong_date_count'),
            _func.count(_func.distinct(_Card.branch_code)).label('center_count')
        ).filter(
            _and(_Card.print_date >= start_date, _Card.print_date <= end_date),
            _Card.region.isnot(None),
            _Card.region != ''
        ).group_by(_Card.region).order_by(
            _func.count(_Card.id).desc()
        ).all()

        return [SimpleNamespace(
            region=r.region,
            total=r.total,
            good_count=r.good_count or 0,
            bad_count=r.bad_count or 0,
            avg_sla=float(r.avg_sla) if r.avg_sla else 0.0,
            max_sla=float(r.max_sla) if r.max_sla else 0.0,
            sla_over_count=r.sla_over_count or 0,
            wrong_branch_count=r.wrong_branch_count or 0,
            wrong_date_count=r.wrong_date_count or 0,
            center_count=r.center_count or 0,
        ) for r in result]
    finally:
        _session.close()


@st.cache_data(ttl=3600, show_spinner=False)
def get_service_funnel_by_branch_cached(start_date, end_date):
    """Get appointment service funnel (appointments, check-in, skip_queue, no_show) per branch."""
    from database.connection import get_session as _get_session
    from database.models import Appointment as _Appt, QLog as _QLog, BioRecord as _Bio
    from sqlalchemy import func as _func, and_ as _and

    _session = _get_session()
    try:
        # 1. Appointments per branch (exclude CANCEL/EXPIRED)
        appt_rows = _session.query(
            _Appt.branch_code,
            _func.count(_func.distinct(_Appt.appointment_id)).label('total')
        ).filter(
            _and(
                _Appt.appt_date >= start_date,
                _Appt.appt_date <= end_date,
                ~_Appt.appt_status.in_(['CANCEL', 'EXPIRED'])
            )
        ).group_by(_Appt.branch_code).all()
        appt_map = {r.branch_code: r.total for r in appt_rows}

        if not appt_map:
            return {}

        # 2. QLog check-in per branch
        qlog_rows = _session.query(
            _QLog.branch_code,
            _func.count(_func.distinct(_QLog.appointment_code)).label('checkin')
        ).filter(
            _and(
                _QLog.qlog_date >= start_date,
                _QLog.qlog_date <= end_date,
                _QLog.qlog_num.isnot(None),
            )
        ).group_by(_QLog.branch_code).all()
        qlog_map = {r.branch_code: r.checkin for r in qlog_rows}

        # 3. Bio served per branch (unique appointment_ids that got cards)
        bio_rows = _session.query(
            _Bio.branch_code,
            _func.count(_func.distinct(_Bio.appointment_id)).label('served')
        ).filter(
            _and(
                _Bio.print_date >= start_date,
                _Bio.print_date <= end_date,
            )
        ).group_by(_Bio.branch_code).all()
        bio_map = {r.branch_code: r.served for r in bio_rows}

        # 4. Skip queue per branch: Bio appointment_ids NOT in QLog
        # Get all QLog appointment_codes as a set per branch
        qlog_detail = _session.query(
            _QLog.branch_code, _QLog.appointment_code
        ).filter(
            _and(
                _QLog.qlog_date >= start_date,
                _QLog.qlog_date <= end_date,
                _QLog.qlog_num.isnot(None),
            )
        ).all()
        qlog_sets = {}
        for row in qlog_detail:
            qlog_sets.setdefault(row.branch_code, set()).add(row.appointment_code)

        bio_detail = _session.query(
            _Bio.branch_code, _Bio.appointment_id
        ).filter(
            _and(
                _Bio.print_date >= start_date,
                _Bio.print_date <= end_date,
            )
        ).all()
        bio_sets = {}
        for row in bio_detail:
            bio_sets.setdefault(row.branch_code, set()).add(row.appointment_id)

        # Compute skip_queue per branch
        all_branches = set(appt_map.keys()) | set(bio_map.keys())
        result = {}
        for bc in all_branches:
            total = appt_map.get(bc, 0)
            checkin = qlog_map.get(bc, 0)
            bio_appts = bio_sets.get(bc, set())
            qlog_appts = qlog_sets.get(bc, set())
            skip_queue = len(bio_appts - qlog_appts)
            no_show = max(0, total - checkin - skip_queue)
            result[bc] = {
                'total_appts': total,
                'checked_in': checkin,
                'skip_queue': skip_queue,
                'no_show': no_show,
                'bio_served': bio_map.get(bc, 0),
            }
        return result
    finally:
        _session.close()


# Check authentication
require_login()

# Apply theme
apply_theme()

# Additional CSS for Light Theme
st.markdown("""
<style>
    .page-header-center {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 2px solid #E2E8F0;
    }

    .page-header-icon {
        width: 48px;
        height: 48px;
        background: linear-gradient(135deg, #8B5CF6, #7C3AED);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
    }

    .section-header-green {
        background: #FFFFFF;
        color: #1E293B;
        padding: 16px 24px;
        border-radius: 12px 12px 0 0;
        font-size: 1rem;
        font-weight: 600;
        border-bottom: 1px solid #E2E8F0;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .section-header-purple {
        background: #FFFFFF;
        color: #1E293B;
        padding: 16px 24px;
        border-radius: 12px 12px 0 0;
        font-size: 1rem;
        font-weight: 600;
        border-bottom: 1px solid #E2E8F0;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .center-card {
        background: #FFFFFF;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.1);
        margin: 10px 0;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #3B82F6;
    }

    .region-card {
        background: #FFFFFF;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.1);
        margin: 10px 0;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #8B5CF6;
    }

    .rank-badge {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: 600;
        margin-right: 10px;
        font-size: 0.85rem;
    }

    .rank-gold {
        background: linear-gradient(135deg, #FEF3C7, #FDE68A);
        color: #92400E;
        border: 1px solid #F59E0B;
    }

    .rank-silver {
        background: linear-gradient(135deg, #F1F5F9, #E2E8F0);
        color: #475569;
        border: 1px solid #94A3B8;
    }

    .rank-bronze {
        background: linear-gradient(135deg, #FED7AA, #FDBA74);
        color: #9A3412;
        border: 1px solid #F97316;
    }

    .stat-box {
        background: #F8FAFC;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        text-align: center;
    }

    .stat-box-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #1E293B;
    }

    .stat-box-label {
        font-size: 0.8rem;
        color: #64748B;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Title - Modern Light Theme
st.markdown("""
<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #E2E8F0;">
    <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #8B5CF6, #7C3AED); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
        <span style="font-size: 24px;">🏢</span>
    </div>
    <div>
        <h1 style="font-size: 1.75rem; font-weight: 700; color: #1E293B; margin: 0;">สถิติตามศูนย์และภูมิภาค</h1>
        <p style="font-size: 0.9rem; color: #64748B; margin: 0;">วิเคราะห์ประสิทธิภาพการทำงานตามศูนย์บริการและภูมิภาค (Sheet 4 & 5)</p>
    </div>
</div>
""", unsafe_allow_html=True)


def extract_province_from_name(branch_name):
    """Extract province from branch name."""
    if not branch_name:
        return None

    # Common Thai provinces patterns
    province_patterns = [
        r'จังหวัด(\S+)',
        r'จ\.(\S+)',
        r'จ\s+(\S+)',
        r'อำเภอ\S+\s+จังหวัด(\S+)',
        r'อ\.\S+\s+จ\.(\S+)',
    ]

    for pattern in province_patterns:
        match = re.search(pattern, branch_name)
        if match:
            return match.group(1)

    # Common province names in center names
    thai_provinces = [
        'กรุงเทพ', 'กรุงเทพมหานคร', 'นนทบุรี', 'ปทุมธานี', 'สมุทรปราการ',
        'เชียงใหม่', 'เชียงราย', 'ลำปาง', 'ลำพูน', 'แพร่', 'น่าน', 'พะเยา', 'แม่ฮ่องสอน', 'อุตรดิตถ์',
        'พิษณุโลก', 'เพชรบูรณ์', 'สุโขทัย', 'ตาก', 'กำแพงเพชร', 'พิจิตร', 'นครสวรรค์', 'อุทัยธานี',
        'ขอนแก่น', 'อุดรธานี', 'นครราชสีมา', 'อุบลราชธานี', 'มหาสารคาม', 'ร้อยเอ็ด', 'กาฬสินธุ์',
        'สกลนคร', 'นครพนม', 'มุกดาหาร', 'ยโสธร', 'อำนาจเจริญ', 'หนองคาย', 'หนองบัวลำภู',
        'เลย', 'ชัยภูมิ', 'บุรีรัมย์', 'สุรินทร์', 'ศรีสะเกษ', 'บึงกาฬ',
        'ชลบุรี', 'ระยอง', 'จันทบุรี', 'ตราด', 'ฉะเชิงเทรา', 'ปราจีนบุรี', 'สระแก้ว', 'นครนายก',
        'สุพรรณบุรี', 'กาญจนบุรี', 'นครปฐม', 'ราชบุรี', 'สมุทรสาคร', 'สมุทรสงคราม',
        'เพชรบุรี', 'ประจวบคีรีขันธ์',
        'พระนครศรีอยุธยา', 'อ่างทอง', 'ลพบุรี', 'สิงห์บุรี', 'ชัยนาท', 'สระบุรี',
        'ภูเก็ต', 'สุราษฎร์ธานี', 'กระบี่', 'พังงา', 'ระนอง', 'ชุมพร', 'นครศรีธรรมราช',
        'สงขลา', 'พัทลุง', 'ตรัง', 'สตูล', 'ปัตตานี', 'ยะลา', 'นราธิวาส'
    ]

    for province in thai_provinces:
        if province in branch_name:
            return province

    return None


session = get_session()

try:
    # Theme toggle in sidebar
    render_theme_toggle()

    # Date filter
    st.markdown('<div class="section-header">📅 เลือกช่วงเวลา</div>', unsafe_allow_html=True)

    min_date = session.query(func.min(Card.print_date)).scalar()
    max_date = session.query(func.max(Card.print_date)).scalar()

    if min_date and max_date:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("วันที่เริ่มต้น", value=min_date, min_value=min_date, max_value=max_date)
        with col2:
            end_date = st.date_input("วันที่สิ้นสุด", value=max_date, min_value=min_date, max_value=max_date)

        # Date filter condition
        date_filter = and_(Card.print_date >= start_date, Card.print_date <= end_date)

        # Main tabs: Center vs Region
        main_tab1, main_tab2 = st.tabs([
            "🏢 ตามศูนย์บริการ (Sheet 4)",
            "🗺️ ตามภูมิภาค (Sheet 5)"
        ])

        # =============================================
        # TAB 1: BY CENTER (Sheet 4)
        # =============================================
        with main_tab1:
            st.markdown('<div class="section-header">🏢 สถิติตามศูนย์บริการ</div>', unsafe_allow_html=True)

            # Get center statistics (cached)
            center_stats = get_center_stats_cached(start_date, end_date)
            # Get appointment service funnel per branch (skip_queue, no_show)
            service_funnel = get_service_funnel_by_branch_cached(start_date, end_date)

            if center_stats:
                # Get branch name mapping from BranchMaster
                branch_name_map = get_branch_name_map_cached()
                short_name_map = get_branch_short_name_map()

                # Build province mapping using BranchMaster names
                province_to_centers = {}
                center_to_province = {}
                for cs in center_stats:
                    # Get branch name from BranchMaster first
                    branch_name = branch_name_map.get(cs.branch_code, cs.branch_name)
                    province = extract_province_from_name(branch_name)
                    if province:
                        if province not in province_to_centers:
                            province_to_centers[province] = []
                        province_to_centers[province].append(cs.branch_code)
                        center_to_province[cs.branch_code] = province

                # ===== NEW: SEARCH/FILTER SECTION =====
                st.markdown("#### 🔍 ค้นหาศูนย์บริการ")

                col1, col2, col3 = st.columns([1, 2, 1])

                with col1:
                    search_type = st.selectbox(
                        "ค้นหาโดย",
                        options=['รหัสศูนย์', 'ชื่อศูนย์', 'จังหวัด'],
                        key="center_search_type"
                    )

                with col2:
                    if search_type == 'รหัสศูนย์':
                        # Show branch_code with name from BranchMaster
                        branch_options = ['ทั้งหมด'] + sorted([cs.branch_code for cs in center_stats if cs.branch_code])
                        selected_filter = st.selectbox(
                            "เลือกศูนย์",
                            options=branch_options,
                            format_func=lambda x: branch_name_map.get(x, x) if x != 'ทั้งหมด' else x,
                            key="center_code_filter"
                        )
                    elif search_type == 'ชื่อศูนย์':
                        # Build options using BranchMaster names
                        name_options = ['ทั้งหมด'] + sorted([
                            f"{cs.branch_code} - {short_name_map.get(cs.branch_code, cs.branch_name or 'N/A')}"
                            for cs in center_stats
                        ])
                        selected_filter = st.selectbox(
                            "เลือกชื่อศูนย์",
                            options=name_options,
                            key="center_name_filter"
                        )
                    else:  # จังหวัด
                        province_options = ['ทั้งหมด'] + sorted(list(province_to_centers.keys()))
                        selected_filter = st.selectbox(
                            "เลือกจังหวัด",
                            options=province_options,
                            key="center_province_filter"
                        )

                with col3:
                    if st.button("🔄 ล้างตัวกรอง", use_container_width=True, key="clear_center_filter"):
                        st.rerun()

                # Filter center_stats based on selection
                filtered_center_stats = center_stats

                if selected_filter != 'ทั้งหมด':
                    if search_type == 'รหัสศูนย์':
                        filtered_center_stats = [cs for cs in center_stats if cs.branch_code == selected_filter]
                    elif search_type == 'ชื่อศูนย์':
                        # Extract branch code from "CODE - NAME" format
                        selected_code = selected_filter.split(' - ')[0] if ' - ' in selected_filter else selected_filter
                        filtered_center_stats = [cs for cs in center_stats if cs.branch_code == selected_code]
                    else:  # จังหวัด
                        province_center_codes = province_to_centers.get(selected_filter, [])
                        filtered_center_stats = [cs for cs in center_stats if cs.branch_code in province_center_codes]

                # Summary metrics (for filtered data)
                total_centers = len(filtered_center_stats)
                total_cards = sum(cs.total for cs in filtered_center_stats)
                total_good = sum(cs.good_count or 0 for cs in filtered_center_stats)
                avg_sla_all = sum((cs.avg_sla or 0) * cs.total for cs in filtered_center_stats) / total_cards if total_cards > 0 else 0

                # Aggregate funnel metrics for filtered centers
                filtered_codes = [cs.branch_code for cs in filtered_center_stats]
                total_appts_sum = sum(service_funnel.get(bc, {}).get('total_appts', 0) for bc in filtered_codes)
                total_checkin_sum = sum(service_funnel.get(bc, {}).get('checked_in', 0) for bc in filtered_codes)
                total_skip_queue_sum = sum(service_funnel.get(bc, {}).get('skip_queue', 0) for bc in filtered_codes)
                total_noshow_sum = sum(service_funnel.get(bc, {}).get('no_show', 0) for bc in filtered_codes)

                filter_text = f" (กรอง: {selected_filter})" if selected_filter != 'ทั้งหมด' else ""

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(f"🏢 จำนวนศูนย์{filter_text}", f"{total_centers:,}")
                with col2:
                    st.metric("📊 รวมทั้งหมด", f"{total_cards:,} ใบ")
                with col3:
                    good_rate = (total_good / total_cards * 100) if total_cards > 0 else 0
                    st.metric("✅ อัตราบัตรดีรวม", f"{good_rate:.1f}%")
                with col4:
                    st.metric("⏱️ SLA เฉลี่ยรวม", f"{avg_sla_all:.2f} นาที")

                # Appointment funnel metrics row
                if total_appts_sum > 0:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("📅 นัดหมาย", f"{total_appts_sum:,}")
                    with col2:
                        checkin_pct = (total_checkin_sum / total_appts_sum * 100) if total_appts_sum > 0 else 0
                        st.metric("🏢 มา Check-in", f"{total_checkin_sum:,}", f"{checkin_pct:.1f}%")
                    with col3:
                        skip_pct = (total_skip_queue_sum / total_appts_sum * 100) if total_appts_sum > 0 else 0
                        st.metric("⚠️ ไม่ผ่านตู้คิว", f"{total_skip_queue_sum:,}", f"{skip_pct:.1f}%")
                    with col4:
                        noshow_pct = (total_noshow_sum / total_appts_sum * 100) if total_appts_sum > 0 else 0
                        st.metric("❌ ไม่มา (No-Show)", f"{total_noshow_sum:,}", f"{noshow_pct:.1f}%")

                # Tabs for different views
                tab1, tab2, tab3, tab4 = st.tabs([
                    "📋 ตารางข้อมูล",
                    "📊 กราฟเปรียบเทียบ",
                    "🏆 Top / Bottom",
                    "🔍 รายละเอียดศูนย์"
                ])

                with tab1:
                    st.markdown("#### 📋 ข้อมูลศูนย์" + filter_text)

                    # Build DataFrame
                    center_data = []
                    for cs in filtered_center_stats:
                        good_rate = (cs.good_count / cs.total * 100) if cs.total > 0 else 0
                        bad_rate = (cs.bad_count / cs.total * 100) if cs.total > 0 else 0
                        province = center_to_province.get(cs.branch_code, '-')
                        # Get branch name from BranchMaster
                        branch_name = branch_name_map.get(cs.branch_code, cs.branch_name or '-')
                        funnel = service_funnel.get(cs.branch_code, {})
                        center_data.append({
                            'ศูนย์บริการ': short_name_map.get(cs.branch_code, branch_name or '-'),
                            'จังหวัด': province,
                            'จำนวนทั้งหมด': cs.total,
                            'บัตรดี': cs.good_count or 0,
                            'บัตรเสีย': cs.bad_count or 0,
                            'อัตราบัตรดี (%)': round(good_rate, 1),
                            'นัดหมาย': funnel.get('total_appts', 0),
                            'Check-in': funnel.get('checked_in', 0),
                            'ไม่ผ่านตู้คิว': funnel.get('skip_queue', 0),
                            'ไม่มา': funnel.get('no_show', 0),
                            'SLA เฉลี่ย': round(cs.avg_sla, 2) if cs.avg_sla else 0,
                            'SLA สูงสุด': round(cs.max_sla, 2) if cs.max_sla else 0,
                            'SLA เกิน': cs.sla_over_count or 0,
                            'ผิดศูนย์': cs.wrong_branch_count or 0,
                            'ผิดวัน': cs.wrong_date_count or 0
                        })

                    df = pd.DataFrame(center_data)

                    # Sort options
                    col1, col2 = st.columns(2)
                    with col1:
                        sort_options = {
                            'จำนวนทั้งหมด': 'จำนวนบัตรทั้งหมด',
                            'บัตรดี': 'จำนวนบัตรดี',
                            'อัตราบัตรดี (%)': 'อัตราบัตรดี',
                            'นัดหมาย': 'จำนวนนัดหมาย',
                            'ไม่ผ่านตู้คิว': 'ไม่ผ่านตู้คิว',
                            'ไม่มา': 'ไม่มา (No-Show)',
                            'SLA เฉลี่ย': 'SLA เฉลี่ย',
                            'SLA สูงสุด': 'SLA สูงสุด',
                            'จังหวัด': 'จังหวัด'
                        }
                        sort_by = st.selectbox(
                            "เรียงตาม",
                            options=list(sort_options.keys()),
                            format_func=lambda x: sort_options[x],
                            key="center_sort"
                        )
                    with col2:
                        sort_order = st.checkbox("เรียงจากน้อยไปมาก", value=False, key="center_order")

                    df_sorted = df.sort_values(sort_by, ascending=sort_order)

                    st.info(f"📊 แสดงข้อมูล **{len(df):,}** ศูนย์" + filter_text)

                    st.dataframe(df_sorted, use_container_width=True, hide_index=True, height=500)

                    # Export
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_sorted.to_excel(writer, index=False, sheet_name='Center Stats')

                    st.download_button(
                        label="📥 ดาวน์โหลด Excel",
                        data=buffer.getvalue(),
                        file_name=f"center_stats_{start_date}_{end_date}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="center_download"
                    )

                with tab2:
                    st.markdown("#### 📊 กราฟเปรียบเทียบ" + filter_text)

                    # Metric selection
                    col1, col2 = st.columns(2)
                    with col1:
                        metric_options = {
                            'จำนวนทั้งหมด': 'จำนวนบัตรทั้งหมด',
                            'บัตรดี': 'จำนวนบัตรดี',
                            'อัตราบัตรดี (%)': 'อัตราบัตรดี (%)',
                            'SLA เฉลี่ย': 'SLA เฉลี่ย (นาที)'
                        }
                        chart_metric = st.selectbox(
                            "ตัวชี้วัด",
                            options=list(metric_options.keys()),
                            format_func=lambda x: metric_options[x],
                            key="center_metric"
                        )
                    with col2:
                        # Handle case when df has fewer rows than min slider value
                        df_len = len(df)
                        if df_len <= 5:
                            top_n = df_len  # Show all if 5 or fewer
                            st.info(f"แสดงทั้งหมด {df_len} ศูนย์")
                        else:
                            top_n = st.slider("แสดงกี่ศูนย์", min_value=5, max_value=min(50, df_len), value=min(20, df_len), key="center_topn")

                    # Top N chart with ECharts
                    top_df = df.nlargest(top_n, chart_metric)

                    # Determine color based on metric
                    if chart_metric in ['บัตรดี', 'อัตราบัตรดี (%)']:
                        bar_color = "#10b981"
                        gradient_colors = ["#10b981", "#34d399"]
                    elif chart_metric == 'SLA เฉลี่ย':
                        bar_color = "#f59e0b"
                        gradient_colors = ["#f59e0b", "#fbbf24"]
                    else:
                        bar_color = "#3b82f6"
                        gradient_colors = ["#3b82f6", "#60a5fa"]

                    # Format values for display
                    if chart_metric == 'อัตราบัตรดี (%)':
                        formatted_values = [f"{v:.1f}%" for v in top_df[chart_metric].tolist()]
                    elif chart_metric == 'SLA เฉลี่ย':
                        formatted_values = [f"{v:.1f}" for v in top_df[chart_metric].tolist()]
                    else:
                        formatted_values = [f"{int(v):,}" for v in top_df[chart_metric].tolist()]

                    # ECharts Bar Chart - Light Theme
                    # Show branch names in chart (truncated for display)
                    chart_labels = [name[:20] + '...' if len(name) > 20 else name for name in top_df['ศูนย์บริการ'].tolist()]

                    bar_options = {
                        "animation": True,
                        "animationDuration": 1000,
                        "animationEasing": "elasticOut",
                        "backgroundColor": "transparent",
                        "title": {
                            "text": f"Top {top_n} ศูนย์ - {metric_options[chart_metric]}" + filter_text,
                            "left": "center",
                            "textStyle": {"color": "#1E293B", "fontSize": 16, "fontWeight": "600"}
                        },
                        "tooltip": {
                            "trigger": "axis",
                            "backgroundColor": "rgba(255, 255, 255, 0.95)",
                            "borderColor": "#E2E8F0",
                            "textStyle": {"color": "#1E293B"},
                            "axisPointer": {"type": "shadow"}
                        },
                        "grid": {
                            "left": "3%",
                            "right": "4%",
                            "bottom": "20%",
                            "top": "15%",
                            "containLabel": True
                        },
                        "xAxis": {
                            "type": "category",
                            "data": chart_labels,
                            "axisLabel": {
                                "color": "#64748B",
                                "rotate": 45,
                                "fontSize": 9,
                                "interval": 0
                            },
                            "axisLine": {"lineStyle": {"color": "#E2E8F0"}}
                        },
                        "yAxis": {
                            "type": "value",
                            "axisLabel": {"color": "#64748B"},
                            "axisLine": {"lineStyle": {"color": "#E2E8F0"}},
                            "splitLine": {"lineStyle": {"color": "#F1F5F9"}}
                        },
                        "series": [
                            {
                                "type": "bar",
                                "data": top_df[chart_metric].tolist(),
                                "barWidth": "60%",
                                "itemStyle": {
                                    "color": {
                                        "type": "linear",
                                        "x": 0, "y": 0, "x2": 0, "y2": 1,
                                        "colorStops": [
                                            {"offset": 0, "color": gradient_colors[0]},
                                            {"offset": 1, "color": gradient_colors[1]}
                                        ]
                                    },
                                    "borderRadius": [4, 4, 0, 0]
                                },
                                "emphasis": {
                                    "itemStyle": {
                                        "shadowBlur": 10,
                                        "shadowColor": "rgba(0, 0, 0, 0.3)"
                                    }
                                },
                                "label": {
                                    "show": True,
                                    "position": "top",
                                    "color": "#1E293B",
                                    "fontSize": 10,
                                    "formatter": "{c}"
                                }
                            }
                        ]
                    }

                    # Add SLA limit line if metric is SLA
                    if chart_metric == 'SLA เฉลี่ย':
                        bar_options["series"].append({
                            "type": "line",
                            "markLine": {
                                "silent": True,
                                "symbol": "none",
                                "lineStyle": {"color": "#ef4444", "type": "dashed", "width": 2},
                                "data": [{"yAxis": 12, "label": {"formatter": "SLA Limit (12 min)", "color": "#ef4444"}}]
                            }
                        })

                    st_echarts(options=bar_options, height="450px", key=f"center_bar_chart_{chart_metric}")

                    # Scatter plot: Volume vs SLA
                    if len(df) > 1:
                        st.markdown("#### 🎯 ความสัมพันธ์ระหว่างปริมาณงานและ SLA")

                        fig2 = px.scatter(
                            df,
                            x='จำนวนทั้งหมด',
                            y='SLA เฉลี่ย',
                            size='บัตรดี',
                            color='อัตราบัตรดี (%)',
                            hover_name='ศูนย์บริการ',
                            hover_data=['จังหวัด'],
                            title='ความสัมพันธ์ระหว่างจำนวนบัตรและ SLA' + filter_text,
                            color_continuous_scale='RdYlGn',
                            labels={
                                'จำนวนทั้งหมด': 'จำนวนบัตรทั้งหมด',
                                'SLA เฉลี่ย': 'SLA เฉลี่ย (นาที)',
                                'บัตรดี': 'บัตรดี',
                                'อัตราบัตรดี (%)': 'อัตราบัตรดี (%)'
                            }
                        )
                        fig2.add_hline(y=12, line_dash="dash", line_color="red", annotation_text="SLA Limit (12 min)")
                        st.plotly_chart(fig2, use_container_width=True)

                with tab3:
                    st.markdown("#### 🏆 ศูนย์ที่มีผลงานดี / ต้องปรับปรุง" + filter_text)

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("##### 🥇 Top 10 - บัตรดีมากที่สุด")
                        top_good = df.nlargest(10, 'บัตรดี')[['ศูนย์บริการ', 'จังหวัด', 'บัตรดี', 'อัตราบัตรดี (%)', 'SLA เฉลี่ย']]
                        st.dataframe(top_good, use_container_width=True, hide_index=True)

                        st.markdown("##### ⚡ Top 10 - SLA เร็วที่สุด")
                        # Filter only centers with significant volume
                        df_significant = df[df['จำนวนทั้งหมด'] >= 10]
                        if not df_significant.empty:
                            top_sla = df_significant.nsmallest(10, 'SLA เฉลี่ย')[['ศูนย์บริการ', 'จังหวัด', 'SLA เฉลี่ย', 'จำนวนทั้งหมด']]
                            st.dataframe(top_sla, use_container_width=True, hide_index=True)

                        st.markdown("##### 🌟 Top 10 - อัตราบัตรดีสูงสุด")
                        df_sig = df[df['จำนวนทั้งหมด'] >= 10]
                        if not df_sig.empty:
                            top_rate = df_sig.nlargest(10, 'อัตราบัตรดี (%)')[['ศูนย์บริการ', 'จังหวัด', 'อัตราบัตรดี (%)', 'จำนวนทั้งหมด']]
                            st.dataframe(top_rate, use_container_width=True, hide_index=True)

                    with col2:
                        st.markdown("##### ⚠️ Bottom 10 - SLA ช้าที่สุด")
                        bottom_sla = df.nlargest(10, 'SLA เฉลี่ย')[['ศูนย์บริการ', 'จังหวัด', 'SLA เฉลี่ย', 'SLA เกิน', 'จำนวนทั้งหมด']]
                        st.dataframe(bottom_sla, use_container_width=True, hide_index=True)

                        st.markdown("##### 📉 Bottom 10 - อัตราบัตรดีต่ำสุด")
                        df_sig = df[df['จำนวนทั้งหมด'] >= 10]
                        if not df_sig.empty:
                            bottom_rate = df_sig.nsmallest(10, 'อัตราบัตรดี (%)')[['ศูนย์บริการ', 'จังหวัด', 'อัตราบัตรดี (%)', 'บัตรเสีย', 'จำนวนทั้งหมด']]
                            st.dataframe(bottom_rate, use_container_width=True, hide_index=True)

                        st.markdown("##### 🚨 ศูนย์ที่มีข้อผิดปกติมาก")
                        df['รวมผิดปกติ'] = df['SLA เกิน'] + df['ผิดศูนย์'] + df['ผิดวัน']
                        anomaly_centers = df.nlargest(10, 'รวมผิดปกติ')[['ศูนย์บริการ', 'จังหวัด', 'SLA เกิน', 'ผิดศูนย์', 'ผิดวัน', 'รวมผิดปกติ']]
                        st.dataframe(anomaly_centers, use_container_width=True, hide_index=True)

                with tab4:
                    st.markdown("#### 🔍 รายละเอียดศูนย์")

                    # Center selection with multiple options
                    st.markdown("##### เลือกศูนย์เพื่อดูรายละเอียด")

                    col1, col2 = st.columns(2)

                    with col1:
                        detail_search_type = st.radio(
                            "เลือกโดย",
                            options=['รหัสศูนย์', 'ชื่อศูนย์', 'จังหวัด'],
                            horizontal=True,
                            key="detail_search_type"
                        )

                    with col2:
                        if detail_search_type == 'รหัสศูนย์':
                            # Show branch name from BranchMaster in dropdown
                            detail_options = [(cs.branch_code, branch_name_map.get(cs.branch_code, cs.branch_code)) for cs in filtered_center_stats]
                            selected_detail = st.selectbox(
                                "เลือกศูนย์",
                                options=detail_options,
                                format_func=lambda x: x[1],
                                key="detail_code"
                            )
                            selected_center_code = selected_detail[0] if selected_detail else None

                        elif detail_search_type == 'ชื่อศูนย์':
                            # Show full branch name from BranchMaster
                            detail_options = [(cs.branch_code, short_name_map.get(cs.branch_code, cs.branch_name or 'N/A')) for cs in filtered_center_stats]
                            selected_detail = st.selectbox(
                                "เลือกศูนย์",
                                options=detail_options,
                                format_func=lambda x: x[1],
                                key="detail_name"
                            )
                            selected_center_code = selected_detail[0] if selected_detail else None

                        else:  # จังหวัด
                            # First select province
                            available_provinces = sorted(set(center_to_province.get(cs.branch_code, 'ไม่ระบุ') for cs in filtered_center_stats))
                            selected_province = st.selectbox(
                                "เลือกจังหวัด",
                                options=available_provinces,
                                key="detail_province"
                            )

                            # Then select center in that province - show branch name
                            centers_in_prov = [cs for cs in filtered_center_stats if center_to_province.get(cs.branch_code, 'ไม่ระบุ') == selected_province]
                            if centers_in_prov:
                                detail_options = [(cs.branch_code, short_name_map.get(cs.branch_code, cs.branch_name or 'N/A')) for cs in centers_in_prov]
                                selected_detail = st.selectbox(
                                    "เลือกศูนย์",
                                    options=detail_options,
                                    format_func=lambda x: x[1],
                                    key="detail_center_in_prov"
                                )
                                selected_center_code = selected_detail[0] if selected_detail else None
                            else:
                                selected_center_code = None

                    if selected_center_code:
                        # Get center details
                        center_info = next((cs for cs in center_stats if cs.branch_code == selected_center_code), None)

                        if center_info:
                            province_name = center_to_province.get(center_info.branch_code, '-')
                            # Get branch name from BranchMaster
                            display_branch_name = short_name_map.get(center_info.branch_code, center_info.branch_name or center_info.branch_code)
                            st.markdown(f"### 🏢 {display_branch_name}")
                            st.markdown(f"**จังหวัด:** {province_name}")

                            # Metrics
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("📊 จำนวนทั้งหมด", f"{center_info.total:,}")
                            with col2:
                                good_rate = (center_info.good_count / center_info.total * 100) if center_info.total > 0 else 0
                                st.metric("✅ บัตรดี", f"{center_info.good_count:,}", f"{good_rate:.1f}%")
                            with col3:
                                st.metric("❌ บัตรเสีย", f"{center_info.bad_count or 0:,}")
                            with col4:
                                sla_status = "✅" if (center_info.avg_sla or 0) <= 12 else "⚠️"
                                st.metric("⏱️ SLA เฉลี่ย", f"{center_info.avg_sla:.2f} น." if center_info.avg_sla else "N/A", sla_status)

                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("⏱️ SLA สูงสุด", f"{center_info.max_sla:.2f} น." if center_info.max_sla else "N/A")
                            with col2:
                                st.metric("🕐 SLA เกิน 12 นาที", f"{center_info.sla_over_count or 0:,}")
                            with col3:
                                st.metric("🏢 ออกบัตรผิดศูนย์", f"{center_info.wrong_branch_count or 0:,}")
                            with col4:
                                st.metric("📅 นัดหมายผิดวัน", f"{center_info.wrong_date_count or 0:,}")

                            # Appointment funnel for this center
                            center_funnel = service_funnel.get(selected_center_code, {})
                            if center_funnel.get('total_appts', 0) > 0:
                                st.markdown("---")
                                st.markdown("##### 📅 สถิติบริการ (Appointment Funnel)")
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("📅 นัดหมาย", f"{center_funnel['total_appts']:,}")
                                with col2:
                                    ci_pct = (center_funnel['checked_in'] / center_funnel['total_appts'] * 100)
                                    st.metric("🏢 มา Check-in", f"{center_funnel['checked_in']:,}", f"{ci_pct:.1f}%")
                                with col3:
                                    sq_pct = (center_funnel['skip_queue'] / center_funnel['total_appts'] * 100)
                                    st.metric("⚠️ ไม่ผ่านตู้คิว", f"{center_funnel['skip_queue']:,}", f"{sq_pct:.1f}%")
                                with col4:
                                    ns_pct = (center_funnel['no_show'] / center_funnel['total_appts'] * 100)
                                    st.metric("❌ ไม่มา", f"{center_funnel['no_show']:,}", f"{ns_pct:.1f}%")

                            # Daily trend for this center
                            st.markdown("---")
                            st.markdown("##### 📈 แนวโน้มรายวัน")

                            daily_center = session.query(
                                Card.print_date,
                                func.count(Card.id).label('total'),
                                func.sum(case((Card.print_status == 'G', 1), else_=0)).label('good'),
                                func.avg(Card.sla_minutes).label('avg_sla')
                            ).filter(
                                date_filter,
                                Card.branch_code == selected_center_code
                            ).group_by(Card.print_date).order_by(Card.print_date).all()

                            if daily_center:
                                daily_data = pd.DataFrame([{
                                    'วันที่': str(d.print_date),
                                    'ทั้งหมด': d.total,
                                    'บัตรดี': d.good or 0,
                                    'SLA เฉลี่ย': round(d.avg_sla, 2) if d.avg_sla else 0
                                } for d in daily_center])

                                fig = go.Figure()
                                fig.add_trace(go.Bar(x=daily_data['วันที่'], y=daily_data['บัตรดี'], name='บัตรดี', marker_color='#2ecc71'))
                                fig.add_trace(go.Scatter(x=daily_data['วันที่'], y=daily_data['SLA เฉลี่ย'], name='SLA เฉลี่ย', yaxis='y2', line=dict(color='#e74c3c', width=2)))
                                fig.update_layout(
                                    title=f'แนวโน้มรายวัน - {selected_center_code}',
                                    yaxis=dict(title='จำนวน (ใบ)'),
                                    yaxis2=dict(title='SLA เฉลี่ย (นาที)', overlaying='y', side='right'),
                                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                                )
                                st.plotly_chart(fig, use_container_width=True)

                            # Top operators at this center
                            st.markdown("##### 👤 ผู้ให้บริการที่ศูนย์นี้")

                            operators = session.query(
                                Card.operator,
                                func.count(Card.id).label('total'),
                                func.sum(case((Card.print_status == 'G', 1), else_=0)).label('good'),
                                func.avg(Card.sla_minutes).label('avg_sla')
                            ).filter(
                                date_filter,
                                Card.branch_code == selected_center_code,
                                Card.operator.isnot(None)
                            ).group_by(Card.operator).order_by(func.count(Card.id).desc()).limit(10).all()

                            if operators:
                                op_data = pd.DataFrame([{
                                    'ผู้ให้บริการ': op.operator,
                                    'จำนวน': op.total,
                                    'บัตรดี': op.good or 0,
                                    'อัตราบัตรดี (%)': round((op.good or 0) / op.total * 100, 1) if op.total > 0 else 0,
                                    'SLA เฉลี่ย': round(op.avg_sla, 2) if op.avg_sla else 0
                                } for op in operators])
                                st.dataframe(op_data, use_container_width=True, hide_index=True)

            else:
                st.info("ไม่มีข้อมูลศูนย์ในช่วงเวลาที่เลือก")

        # =============================================
        # TAB 2: BY REGION (Sheet 5)
        # =============================================
        with main_tab2:
            st.markdown('<div class="section-header-purple">🗺️ สถิติตามภูมิภาค</div>', unsafe_allow_html=True)

            # Get region statistics (cached)
            region_stats = get_region_stats_cached(start_date, end_date)

            if region_stats:
                # Summary metrics
                total_regions = len(region_stats)
                total_cards = sum(rs.total for rs in region_stats)
                total_good = sum(rs.good_count or 0 for rs in region_stats)
                total_centers = sum(rs.center_count or 0 for rs in region_stats)
                avg_sla_all = sum((rs.avg_sla or 0) * rs.total for rs in region_stats) / total_cards if total_cards > 0 else 0

                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("🗺️ จำนวนภูมิภาค", f"{total_regions:,}")
                with col2:
                    st.metric("🏢 ศูนย์ทั้งหมด", f"{total_centers:,}")
                with col3:
                    st.metric("📊 รวมทั้งหมด", f"{total_cards:,} ใบ")
                with col4:
                    good_rate = (total_good / total_cards * 100) if total_cards > 0 else 0
                    st.metric("✅ อัตราบัตรดีรวม", f"{good_rate:.1f}%")
                with col5:
                    st.metric("⏱️ SLA เฉลี่ยรวม", f"{avg_sla_all:.2f} นาที")

                # Tabs for region views
                rtab1, rtab2, rtab3, rtab4 = st.tabs([
                    "📋 ตารางภูมิภาค",
                    "📊 กราฟเปรียบเทียบ",
                    "🏆 จัดอันดับ",
                    "🔍 รายละเอียดภูมิภาค"
                ])

                with rtab1:
                    st.markdown("#### 📋 ข้อมูลทุกภูมิภาค")

                    # Build DataFrame
                    region_data = []
                    for rs in region_stats:
                        good_rate = (rs.good_count / rs.total * 100) if rs.total > 0 else 0
                        region_data.append({
                            'ภูมิภาค': rs.region or 'ไม่ระบุ',
                            'จำนวนศูนย์': rs.center_count or 0,
                            'จำนวนทั้งหมด': rs.total,
                            'บัตรดี': rs.good_count or 0,
                            'บัตรเสีย': rs.bad_count or 0,
                            'อัตราบัตรดี (%)': round(good_rate, 1),
                            'SLA เฉลี่ย': round(rs.avg_sla, 2) if rs.avg_sla else 0,
                            'SLA สูงสุด': round(rs.max_sla, 2) if rs.max_sla else 0,
                            'SLA เกิน': rs.sla_over_count or 0,
                            'ผิดศูนย์': rs.wrong_branch_count or 0,
                            'ผิดวัน': rs.wrong_date_count or 0
                        })

                    df_region = pd.DataFrame(region_data)

                    # Sort options
                    col1, col2 = st.columns(2)
                    with col1:
                        sort_options_r = {
                            'จำนวนทั้งหมด': 'จำนวนบัตรทั้งหมด',
                            'บัตรดี': 'จำนวนบัตรดี',
                            'อัตราบัตรดี (%)': 'อัตราบัตรดี',
                            'SLA เฉลี่ย': 'SLA เฉลี่ย',
                            'จำนวนศูนย์': 'จำนวนศูนย์'
                        }
                        sort_by_r = st.selectbox(
                            "เรียงตาม",
                            options=list(sort_options_r.keys()),
                            format_func=lambda x: sort_options_r[x],
                            key="region_sort"
                        )
                    with col2:
                        sort_order_r = st.checkbox("เรียงจากน้อยไปมาก", value=False, key="region_order")

                    df_region_sorted = df_region.sort_values(sort_by_r, ascending=sort_order_r)

                    st.dataframe(df_region_sorted, use_container_width=True, hide_index=True, height=400)

                    # Export
                    buffer_r = BytesIO()
                    with pd.ExcelWriter(buffer_r, engine='xlsxwriter') as writer:
                        df_region_sorted.to_excel(writer, index=False, sheet_name='Region Stats')

                    st.download_button(
                        label="📥 ดาวน์โหลด Excel",
                        data=buffer_r.getvalue(),
                        file_name=f"region_stats_{start_date}_{end_date}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="region_download"
                    )

                with rtab2:
                    st.markdown("#### 📊 กราฟเปรียบเทียบภูมิภาค")

                    # Metric selection
                    metric_options_r = {
                        'จำนวนทั้งหมด': 'จำนวนบัตรทั้งหมด',
                        'บัตรดี': 'จำนวนบัตรดี',
                        'อัตราบัตรดี (%)': 'อัตราบัตรดี (%)',
                        'SLA เฉลี่ย': 'SLA เฉลี่ย (นาที)',
                        'จำนวนศูนย์': 'จำนวนศูนย์'
                    }
                    chart_metric_r = st.selectbox(
                        "ตัวชี้วัด",
                        options=list(metric_options_r.keys()),
                        format_func=lambda x: metric_options_r[x],
                        key="region_metric"
                    )

                    # Bar chart for all regions
                    color_scale_r = 'Purples'
                    if chart_metric_r == 'SLA เฉลี่ย':
                        color_scale_r = 'RdYlGn_r'
                    elif chart_metric_r in ['บัตรดี', 'อัตราบัตรดี (%)']:
                        color_scale_r = 'Greens'

                    fig_r1 = px.bar(
                        df_region.sort_values(chart_metric_r, ascending=False),
                        x='ภูมิภาค',
                        y=chart_metric_r,
                        title=f'เปรียบเทียบภูมิภาค - {metric_options_r[chart_metric_r]}',
                        color=chart_metric_r,
                        color_continuous_scale=color_scale_r,
                        text=chart_metric_r
                    )
                    if chart_metric_r == 'อัตราบัตรดี (%)':
                        fig_r1.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                    elif chart_metric_r == 'SLA เฉลี่ย':
                        fig_r1.update_traces(texttemplate='%{text:.1f}', textposition='outside')
                        fig_r1.add_hline(y=12, line_dash="dash", line_color="red", annotation_text="SLA Limit (12 min)")
                    else:
                        fig_r1.update_traces(texttemplate='%{text:,.0f}', textposition='outside')

                    fig_r1.update_layout(xaxis_tickangle=-45, showlegend=False)
                    st.plotly_chart(fig_r1, use_container_width=True)

                    # Pie chart for distribution
                    st.markdown("#### 🥧 สัดส่วนบัตรตามภูมิภาค")

                    col1, col2 = st.columns(2)
                    with col1:
                        fig_pie1 = px.pie(
                            df_region,
                            values='จำนวนทั้งหมด',
                            names='ภูมิภาค',
                            title='สัดส่วนจำนวนบัตรทั้งหมด',
                            hole=0.4
                        )
                        st.plotly_chart(fig_pie1, use_container_width=True)

                    with col2:
                        fig_pie2 = px.pie(
                            df_region,
                            values='จำนวนศูนย์',
                            names='ภูมิภาค',
                            title='สัดส่วนจำนวนศูนย์',
                            hole=0.4
                        )
                        st.plotly_chart(fig_pie2, use_container_width=True)

                    # Scatter plot
                    st.markdown("#### 🎯 ความสัมพันธ์ระหว่างปริมาณงานและ SLA")

                    fig_r2 = px.scatter(
                        df_region,
                        x='จำนวนทั้งหมด',
                        y='SLA เฉลี่ย',
                        size='จำนวนศูนย์',
                        color='อัตราบัตรดี (%)',
                        hover_name='ภูมิภาค',
                        title='ความสัมพันธ์ระหว่างจำนวนบัตรและ SLA ตามภูมิภาค',
                        color_continuous_scale='RdYlGn',
                        labels={
                            'จำนวนทั้งหมด': 'จำนวนบัตรทั้งหมด',
                            'SLA เฉลี่ย': 'SLA เฉลี่ย (นาที)',
                            'จำนวนศูนย์': 'จำนวนศูนย์',
                            'อัตราบัตรดี (%)': 'อัตราบัตรดี (%)'
                        }
                    )
                    fig_r2.add_hline(y=12, line_dash="dash", line_color="red", annotation_text="SLA Limit (12 min)")
                    st.plotly_chart(fig_r2, use_container_width=True)

                with rtab3:
                    st.markdown("#### 🏆 จัดอันดับภูมิภาค")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("##### 🥇 บัตรมากที่สุด")
                        top_cards = df_region.nlargest(5, 'จำนวนทั้งหมด')[['ภูมิภาค', 'จำนวนทั้งหมด', 'จำนวนศูนย์']]
                        st.dataframe(top_cards, use_container_width=True, hide_index=True)

                        st.markdown("##### 🌟 อัตราบัตรดีสูงสุด")
                        top_good_rate = df_region.nlargest(5, 'อัตราบัตรดี (%)')[['ภูมิภาค', 'อัตราบัตรดี (%)', 'จำนวนทั้งหมด']]
                        st.dataframe(top_good_rate, use_container_width=True, hide_index=True)

                        st.markdown("##### ⚡ SLA เร็วที่สุด")
                        top_sla = df_region.nsmallest(5, 'SLA เฉลี่ย')[['ภูมิภาค', 'SLA เฉลี่ย', 'จำนวนทั้งหมด']]
                        st.dataframe(top_sla, use_container_width=True, hide_index=True)

                    with col2:
                        st.markdown("##### ⚠️ SLA ช้าที่สุด")
                        bottom_sla = df_region.nlargest(5, 'SLA เฉลี่ย')[['ภูมิภาค', 'SLA เฉลี่ย', 'SLA เกิน']]
                        st.dataframe(bottom_sla, use_container_width=True, hide_index=True)

                        st.markdown("##### 📉 อัตราบัตรดีต่ำสุด")
                        bottom_good = df_region.nsmallest(5, 'อัตราบัตรดี (%)')[['ภูมิภาค', 'อัตราบัตรดี (%)', 'บัตรเสีย']]
                        st.dataframe(bottom_good, use_container_width=True, hide_index=True)

                        st.markdown("##### 🚨 ข้อผิดปกติมากที่สุด")
                        df_region['รวมผิดปกติ'] = df_region['SLA เกิน'] + df_region['ผิดศูนย์'] + df_region['ผิดวัน']
                        anomaly_regions = df_region.nlargest(5, 'รวมผิดปกติ')[['ภูมิภาค', 'SLA เกิน', 'ผิดศูนย์', 'ผิดวัน']]
                        st.dataframe(anomaly_regions, use_container_width=True, hide_index=True)

                with rtab4:
                    st.markdown("#### 🔍 รายละเอียดภูมิภาค")

                    # Region selection
                    region_options = [(rs.region, rs.region) for rs in region_stats]
                    selected_region = st.selectbox(
                        "🗺️ เลือกภูมิภาค",
                        options=region_options,
                        format_func=lambda x: x[1] or 'ไม่ระบุ',
                        key="region_select"
                    )

                    if selected_region:
                        region_name = selected_region[0]

                        # Get region details
                        region_info = next((rs for rs in region_stats if rs.region == region_name), None)

                        if region_info:
                            st.markdown(f"### 🗺️ ภูมิภาค: {region_name}")

                            # Metrics
                            col1, col2, col3, col4, col5 = st.columns(5)
                            with col1:
                                st.metric("🏢 จำนวนศูนย์", f"{region_info.center_count:,}")
                            with col2:
                                st.metric("📊 จำนวนทั้งหมด", f"{region_info.total:,}")
                            with col3:
                                good_rate = (region_info.good_count / region_info.total * 100) if region_info.total > 0 else 0
                                st.metric("✅ บัตรดี", f"{region_info.good_count:,}", f"{good_rate:.1f}%")
                            with col4:
                                st.metric("❌ บัตรเสีย", f"{region_info.bad_count or 0:,}")
                            with col5:
                                sla_status = "✅" if (region_info.avg_sla or 0) <= 12 else "⚠️"
                                st.metric("⏱️ SLA เฉลี่ย", f"{region_info.avg_sla:.2f} น." if region_info.avg_sla else "N/A", sla_status)

                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("⏱️ SLA สูงสุด", f"{region_info.max_sla:.2f} น." if region_info.max_sla else "N/A")
                            with col2:
                                st.metric("🕐 SLA เกิน 12 นาที", f"{region_info.sla_over_count or 0:,}")
                            with col3:
                                st.metric("🏢 ออกบัตรผิดศูนย์", f"{region_info.wrong_branch_count or 0:,}")
                            with col4:
                                st.metric("📅 นัดหมายผิดวัน", f"{region_info.wrong_date_count or 0:,}")

                            st.markdown("---")

                            # Centers in this region
                            st.markdown("##### 🏢 ศูนย์ในภูมิภาคนี้")

                            centers_in_region = session.query(
                                Card.branch_code,
                                Card.branch_name,
                                func.count(Card.id).label('total'),
                                func.sum(case((Card.print_status == 'G', 1), else_=0)).label('good'),
                                func.avg(Card.sla_minutes).label('avg_sla')
                            ).filter(
                                date_filter,
                                Card.region == region_name
                            ).group_by(Card.branch_code, Card.branch_name).order_by(
                                func.count(Card.id).desc()
                            ).all()

                            if centers_in_region:
                                centers_data = pd.DataFrame([{
                                    'ศูนย์บริการ': short_name_map.get(c.branch_code, c.branch_name or '-'),
                                    'จำนวน': c.total,
                                    'บัตรดี': c.good or 0,
                                    'อัตราบัตรดี (%)': round((c.good or 0) / c.total * 100, 1) if c.total > 0 else 0,
                                    'SLA เฉลี่ย': round(c.avg_sla, 2) if c.avg_sla else 0
                                } for c in centers_in_region])

                                st.dataframe(centers_data, use_container_width=True, hide_index=True, height=400)

                                # Chart
                                st.markdown("##### 📊 เปรียบเทียบศูนย์ในภูมิภาค")

                                fig_centers = px.bar(
                                    centers_data.head(20),
                                    x='ศูนย์บริการ',
                                    y='จำนวน',
                                    color='อัตราบัตรดี (%)',
                                    title=f'ศูนย์ในภูมิภาค {region_name} (Top 20)',
                                    color_continuous_scale='RdYlGn',
                                    text='จำนวน'
                                )
                                fig_centers.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
                                fig_centers.update_layout(xaxis_tickangle=-45)
                                st.plotly_chart(fig_centers, use_container_width=True)

                            # Daily trend for this region
                            st.markdown("##### 📈 แนวโน้มรายวัน")

                            daily_region = session.query(
                                Card.print_date,
                                func.count(Card.id).label('total'),
                                func.sum(case((Card.print_status == 'G', 1), else_=0)).label('good'),
                                func.avg(Card.sla_minutes).label('avg_sla')
                            ).filter(
                                date_filter,
                                Card.region == region_name
                            ).group_by(Card.print_date).order_by(Card.print_date).all()

                            if daily_region:
                                daily_r_data = pd.DataFrame([{
                                    'วันที่': str(d.print_date),
                                    'ทั้งหมด': d.total,
                                    'บัตรดี': d.good or 0,
                                    'SLA เฉลี่ย': round(d.avg_sla, 2) if d.avg_sla else 0
                                } for d in daily_region])

                                fig_daily = go.Figure()
                                fig_daily.add_trace(go.Bar(x=daily_r_data['วันที่'], y=daily_r_data['บัตรดี'], name='บัตรดี', marker_color='#9b59b6'))
                                fig_daily.add_trace(go.Scatter(x=daily_r_data['วันที่'], y=daily_r_data['SLA เฉลี่ย'], name='SLA เฉลี่ย', yaxis='y2', line=dict(color='#e74c3c', width=2)))
                                fig_daily.update_layout(
                                    title=f'แนวโน้มรายวัน - ภูมิภาค {region_name}',
                                    yaxis=dict(title='จำนวน (ใบ)'),
                                    yaxis2=dict(title='SLA เฉลี่ย (นาที)', overlaying='y', side='right'),
                                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                                )
                                st.plotly_chart(fig_daily, use_container_width=True)

            else:
                st.warning("⚠️ ไม่พบข้อมูลภูมิภาคในช่วงเวลาที่เลือก (คอลัมน์ region อาจไม่มีข้อมูล)")
                st.info("💡 หากข้อมูลภูมิภาคไม่แสดง กรุณาตรวจสอบว่าไฟล์ Excel มีข้อมูลในคอลัมน์ 'ภาค' หรือ 'Region'")

    else:
        st.markdown("""
        <div style='text-align: center; padding: 50px; background: #f8f9fa; border-radius: 15px;'>
            <h2>💡 ยังไม่มีข้อมูล</h2>
            <p>กรุณาอัพโหลดไฟล์รายงานก่อนที่หน้า Upload</p>
        </div>
        """, unsafe_allow_html=True)

finally:
    session.close()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888; padding: 10px;'>
    <p>🏢 Bio Unified Report - Center & Region Statistics (Sheet 4 & 5)</p>
</div>
""", unsafe_allow_html=True)
