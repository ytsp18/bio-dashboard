"""Anomaly page - Show all abnormal records with comprehensive analysis, search and comparison."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session
from database.models import Card, BadCard, AnomalySLA, WrongCenter
from sqlalchemy import func, and_, case, or_
from utils.theme import apply_theme, render_theme_toggle
from utils.auth_check import require_login

init_db()

st.set_page_config(page_title="Anomaly - Bio Dashboard", page_icon="⚠️", layout="wide")


@st.cache_data(ttl=300, show_spinner=False)
def get_anomaly_summary_cached(start_date, end_date):
    """Cached anomaly summary counts."""
    from database.connection import get_session as _get_session
    from database.models import Card as _Card
    from sqlalchemy import func as _func, and_ as _and

    _session = _get_session()
    try:
        _date_filter = _and(_Card.print_date >= start_date, _Card.print_date <= end_date)

        appt_g_more_than_1 = _session.query(_Card.appointment_id).filter(
            _date_filter, _Card.print_status == 'G'
        ).group_by(_Card.appointment_id).having(_func.count(_Card.id) > 1).count()

        card_id_g_more_than_1 = _session.query(_Card.card_id).filter(
            _date_filter, _Card.print_status == 'G',
            _Card.card_id.isnot(None), _Card.card_id != ''
        ).group_by(_Card.card_id).having(_func.count(_Card.id) > 1).count()

        wrong_date_count = _session.query(_Card).filter(_date_filter, _Card.wrong_date == True).count()
        wrong_branch_count = _session.query(_Card).filter(_date_filter, _Card.wrong_branch == True).count()

        branches = _session.query(_Card.branch_code).filter(
            _date_filter, _Card.branch_code.isnot(None)
        ).distinct().all()
        branch_list = sorted([b.branch_code for b in branches])

        return {
            'appt_g_more_than_1': appt_g_more_than_1,
            'card_id_g_more_than_1': card_id_g_more_than_1,
            'wrong_date_count': wrong_date_count,
            'wrong_branch_count': wrong_branch_count,
            'branch_list': branch_list,
        }
    finally:
        _session.close()

# Check authentication
require_login()

# Apply theme
apply_theme()

# Additional CSS for Anomaly page - Light Theme
st.markdown("""
<style>
    .section-header {
        background: linear-gradient(90deg, #F8FAFC 0%, #FFFFFF 100%);
        color: #DC2626;
        padding: 16px 24px;
        border-radius: 12px;
        margin: 20px 0 15px 0;
        font-size: 1.1em;
        font-weight: 600;
        border: 1px solid #FECACA;
        border-left: 4px solid #EF4444;
    }

    .section-header-blue {
        background: linear-gradient(90deg, #F8FAFC 0%, #FFFFFF 100%);
        color: #1E293B;
        padding: 16px 24px;
        border-radius: 12px;
        margin: 20px 0 15px 0;
        font-size: 1.1em;
        font-weight: 600;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #3B82F6;
    }

    .section-header-green {
        background: linear-gradient(90deg, #F8FAFC 0%, #FFFFFF 100%);
        color: #059669;
        padding: 16px 24px;
        border-radius: 12px;
        margin: 20px 0 15px 0;
        font-size: 1.1em;
        font-weight: 600;
        border: 1px solid #A7F3D0;
        border-left: 4px solid #10B981;
    }

    .anomaly-card {
        background: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #E2E8F0;
        border-left: 4px solid #EF4444;
        margin: 10px 0;
    }

    .anomaly-card-warning {
        border-left-color: #F59E0B;
    }

    .anomaly-card-info {
        border-left-color: #3B82F6;
    }

    .stat-badge {
        display: inline-block;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        margin: 5px;
    }

    .badge-danger {
        background: #FEE2E2;
        color: #DC2626;
    }

    .badge-warning {
        background: #FEF3C7;
        color: #D97706;
    }

    .badge-success {
        background: #D1FAE5;
        color: #059669;
    }

    /* Fix multiselect text color for better contrast */
    .stMultiSelect [data-baseweb="tag"] {
        background-color: #3B82F6 !important;
        color: white !important;
    }
    .stMultiSelect [data-baseweb="tag"] span {
        color: white !important;
    }
    .stMultiSelect [data-baseweb="tag"] svg {
        fill: white !important;
    }

    /* Summary table styling - Light Theme */
    .summary-table {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
        color: #1E293B;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .summary-table-header {
        font-size: 1.1em;
        font-weight: 600;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 1px solid #E2E8F0;
        color: #1E293B;
    }
    .summary-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid #F1F5F9;
    }
    .summary-row:last-child {
        border-bottom: none;
    }
    .summary-label {
        color: #64748B;
    }
    .summary-value {
        font-weight: 700;
        color: #2563EB;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown("""
<h1 style='text-align: center; color: #DC2626; margin-bottom: 5px;'>
    ⚠️ รายงานข้อมูลผิดปกติ
</h1>
<p style='text-align: center; color: #64748B; margin-bottom: 25px;'>
    ตรวจสอบและวิเคราะห์ข้อมูลผิดปกติทุกประเภท พร้อมฟังก์ชันค้นหาและเปรียบเทียบ
</p>
""", unsafe_allow_html=True)

session = get_session()

try:
    # Theme toggle in sidebar
    render_theme_toggle()

    # Date filter
    st.markdown('<div class="section-header-blue">📅 เลือกช่วงเวลา</div>', unsafe_allow_html=True)

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

        # ==================== SUMMARY STATISTICS TABLE ====================
        st.markdown('<div class="section-header">⚠️ รายการ Anomaly ที่ต้องตรวจสอบ</div>', unsafe_allow_html=True)

        # Calculate summary statistics (cached)
        _anomaly_summary = get_anomaly_summary_cached(start_date, end_date)
        appt_g_more_than_1 = _anomaly_summary['appt_g_more_than_1']
        card_id_g_more_than_1 = _anomaly_summary['card_id_g_more_than_1']

        # Display summary table
        st.markdown(f"""
        <div class="summary-table">
            <div class="summary-table-header">🔍 รายการที่ต้องตรวจสอบ</div>
            <div class="summary-row">
                <span class="summary-label">รายการนัดหมายที่มีบัตรดีมากกว่า 1 ใบ (Appt ID)</span>
                <span class="summary-value" style="color: #ff6b6b;">{appt_g_more_than_1:,}</span>
            </div>
            <div class="summary-row">
                <span class="summary-label">Card ID ที่มีบัตรดีมากกว่า 1 ใบ (รหัสประจำตัวคนต่างด้าว)</span>
                <span class="summary-value" style="color: #ff6b6b;">{card_id_g_more_than_1:,}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ==================== SEARCH SECTION ====================
        st.markdown('<div class="section-header-green">🔍 ค้นหาและตรวจสอบ Anomaly</div>', unsafe_allow_html=True)

        # Symmetrical layout: search input = button widths combined
        col1, col2 = st.columns(2)

        with col1:
            search_term = st.text_input(
                "🔍 ค้นหา",
                placeholder="ใส่ Appointment ID, Serial Number หรือ Card ID",
                help="ค้นหา anomaly ที่เกี่ยวข้องกับข้อมูลที่ระบุ"
            )

        with col2:
            # Add vertical spacing to align with text input
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                search_button = st.button("🔍 ค้นหา", type="primary", use_container_width=True)
            with btn_col2:
                clear_button = st.button("🔄 ล้างการค้นหา", use_container_width=True)

        if search_button and search_term:
            st.markdown("---")
            st.markdown(f"#### 🔍 ผลการค้นหา: `{search_term}`")

            # Find related cards
            related_cards = session.query(Card).filter(
                date_filter,
                or_(
                    Card.appointment_id.ilike(f'%{search_term}%'),
                    Card.serial_number.ilike(f'%{search_term}%'),
                    Card.card_id.ilike(f'%{search_term}%')
                )
            ).all()

            if related_cards:
                st.success(f"พบ {len(related_cards)} รายการที่ตรงกัน")

                # Show all anomalies for found cards
                anomalies_found = []

                for card in related_cards:
                    card_anomalies = []

                    # Check each anomaly type
                    if card.sla_over_12min:
                        card_anomalies.append({
                            'type': 'SLA>12',
                            'detail': f'SLA = {round(card.sla_minutes, 2) if card.sla_minutes else "-"} นาที'
                        })

                    if card.wrong_branch:
                        card_anomalies.append({
                            'type': 'ผิดศูนย์',
                            'detail': f'นัด: {card.appt_branch} | ออก: {card.branch_code}'
                        })

                    if card.wrong_date:
                        card_anomalies.append({
                            'type': 'ผิดวัน',
                            'detail': f'นัด: {card.appt_date} | ออก: {card.print_date}'
                        })

                    if card.wait_over_1hour:
                        card_anomalies.append({
                            'type': 'รอ>1ชม',
                            'detail': f'รอ {card.wait_time_hms or "-"}'
                        })

                    if card.print_status == 'B':
                        card_anomalies.append({
                            'type': 'บัตรเสีย',
                            'detail': f'สาเหตุ: {card.reject_type or "-"}'
                        })

                    # Check for multiple G per appointment
                    g_count = session.query(func.count(Card.id)).filter(
                        Card.appointment_id == card.appointment_id,
                        Card.print_status == 'G'
                    ).scalar() or 0

                    if g_count > 1:
                        card_anomalies.append({
                            'type': 'G>1',
                            'detail': f'มีบัตรดี {g_count} ใบ ต่อ Appointment'
                        })

                    # Check for duplicate serial
                    serial_count = session.query(func.count(Card.id)).filter(
                        Card.serial_number == card.serial_number,
                        Card.print_status == 'G'
                    ).scalar() or 0

                    if serial_count > 1:
                        card_anomalies.append({
                            'type': 'Serialซ้ำ',
                            'detail': f'Serial ถูกใช้ {serial_count} ครั้ง'
                        })

                    anomalies_found.append({
                        'card': card,
                        'anomalies': card_anomalies
                    })

                # Display results
                for item in anomalies_found:
                    card = item['card']
                    card_anomalies = item['anomalies']

                    with st.expander(f"📋 {card.appointment_id} - {card.serial_number or 'N/A'} ({'ดี' if card.print_status == 'G' else 'เสีย'})", expanded=True):
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("##### 📄 ข้อมูลบัตร")
                            st.markdown(f"""
                            | รายการ | ค่า |
                            |--------|-----|
                            | Appointment ID | `{card.appointment_id}` |
                            | Serial Number | `{card.serial_number or '-'}` |
                            | Card ID | `{card.card_id or '-'}` |
                            | Work Permit | `{card.work_permit_no or '-'}` |
                            | สถานะ | {'✅ บัตรดี' if card.print_status == 'G' else '❌ บัตรเสีย'} |
                            | รหัสศูนย์ | `{card.branch_code or '-'}` |
                            | ชื่อศูนย์ | {card.branch_name or '-'} |
                            | วันที่พิมพ์ | {card.print_date} |
                            | ผู้ให้บริการ | {card.operator or '-'} |
                            """)

                        with col2:
                            st.markdown("##### ⚠️ Anomaly ที่พบ")
                            if card_anomalies:
                                for anom in card_anomalies:
                                    if anom['type'] in ['SLA>12', 'บัตรเสีย', 'G>1', 'Serialซ้ำ']:
                                        st.error(f"🔴 **{anom['type']}**: {anom['detail']}")
                                    else:
                                        st.warning(f"🟠 **{anom['type']}**: {anom['detail']}")
                            else:
                                st.success("✅ ไม่พบ Anomaly")

                            st.markdown("##### 📊 ข้อมูล SLA & Queue")
                            st.markdown(f"""
                            | รายการ | ค่า |
                            |--------|-----|
                            | SLA Start | {card.sla_start or '-'} |
                            | SLA Stop | {card.sla_stop or '-'} |
                            | SLA (นาที) | {round(card.sla_minutes, 2) if card.sla_minutes else '-'} |
                            | Time In | {card.qlog_time_in or '-'} |
                            | Time Call | {card.qlog_time_call or '-'} |
                            | Wait Time | {card.wait_time_hms or '-'} |
                            """)

            else:
                st.info("🔍 ไม่พบข้อมูลที่ตรงกับคำค้นหา")

        # Get cached anomaly summary data
        branch_list = _anomaly_summary['branch_list']
        wrong_date_count = _anomaly_summary['wrong_date_count']
        wrong_branch_count = _anomaly_summary['wrong_branch_count']

        # Multiple cards per appointment (reuse from summary)
        multi_g_count = appt_g_more_than_1

        # Card ID G>1 (reuse from summary)
        card_id_g_count = card_id_g_more_than_1

        # ==================== Detailed Tabs ====================
        st.markdown('<div class="section-header">📋 รายละเอียดแต่ละประเภท</div>', unsafe_allow_html=True)

        tab1, tab2, tab3, tab4 = st.tabs([
            f"📅 ผิดวัน ({wrong_date_count:,})",
            f"🏢 ผิดศูนย์ ({wrong_branch_count:,})",
            f"🔄 Appt G>1 ({multi_g_count:,})",
            f"🔄 Card ID G>1 ({card_id_g_count:,})"
        ])

        # Tab 1: Wrong Date
        with tab1:
            st.markdown("#### 📅 นัดหมายผิดวัน")
            st.caption("บัตรที่ออกวันไม่ตรงกับวันที่นัดหมาย")

            col1, col2 = st.columns(2)
            with col1:
                wd_branch_filter = st.selectbox("กรองตามศูนย์", options=['ทั้งหมด'] + branch_list, key="wd_branch")
            with col2:
                wd_limit = st.slider("จำนวนแสดง", 100, 5000, 500, key="wd_limit")

            query = session.query(Card).filter(date_filter, Card.wrong_date == True)
            if wd_branch_filter != 'ทั้งหมด':
                query = query.filter(Card.branch_code == wd_branch_filter)

            wrong_date = query.limit(wd_limit).all()

            if wrong_date:
                data = [{
                    'Appointment ID': c.appointment_id,
                    'รหัสศูนย์': c.branch_code,
                    'ชื่อศูนย์': (c.branch_name[:30] + '...' if c.branch_name and len(c.branch_name) > 30 else c.branch_name) or '-',
                    'วันที่นัด': c.appt_date,
                    'วันที่ออกบัตร': c.print_date,
                    'Serial Number': c.serial_number,
                    'สถานะ': 'บัตรดี' if c.print_status == 'G' else 'บัตรเสีย',
                    'ผู้ให้บริการ': c.operator or '-',
                } for c in wrong_date]

                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True, hide_index=True, height=400)

                st.markdown("##### 📊 สรุปตามศูนย์")
                center_counts = df.groupby('รหัสศูนย์').size().reset_index(name='จำนวน')
                center_counts = center_counts.sort_values('จำนวน', ascending=False).head(15)
                st.dataframe(center_counts, use_container_width=True, hide_index=True)

                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Wrong Date')
                st.download_button("📥 ดาวน์โหลด Excel", buffer.getvalue(),
                    f"wrong_date_{start_date}_{end_date}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.success("✅ ไม่พบรายการนัดหมายผิดวัน")

        # Tab 2: Wrong Branch
        with tab2:
            st.markdown("#### 🏢 ออกบัตรผิดศูนย์")
            st.caption("บัตรที่ออกที่ศูนย์ไม่ตรงกับศูนย์ที่นัดหมาย")

            col1, col2 = st.columns(2)
            with col1:
                wb_branch_filter = st.selectbox("กรองตามศูนย์ที่ออกบัตร", options=['ทั้งหมด'] + branch_list, key="wb_branch")
            with col2:
                wb_limit = st.slider("จำนวนแสดง", 100, 5000, 500, key="wb_limit")

            query = session.query(Card).filter(date_filter, Card.wrong_branch == True)
            if wb_branch_filter != 'ทั้งหมด':
                query = query.filter(Card.branch_code == wb_branch_filter)

            wrong_branch = query.limit(wb_limit).all()

            if wrong_branch:
                data = [{
                    'Appointment ID': c.appointment_id,
                    'ศูนย์ที่นัด': c.appt_branch or '-',
                    'ศูนย์ที่ออกบัตร': c.branch_code,
                    'ชื่อศูนย์': (c.branch_name[:30] + '...' if c.branch_name and len(c.branch_name) > 30 else c.branch_name) or '-',
                    'Serial Number': c.serial_number,
                    'Card ID': c.card_id,
                    'สถานะ': 'บัตรดี' if c.print_status == 'G' else 'บัตรเสีย',
                    'วันที่พิมพ์': c.print_date,
                    'ผู้ให้บริการ': c.operator or '-',
                } for c in wrong_branch]

                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True, hide_index=True, height=400)

                # Summary by center
                st.markdown("##### 📊 สรุปตามศูนย์ที่ออกบัตร")
                center_counts = df.groupby('ศูนย์ที่ออกบัตร').size().reset_index(name='จำนวน')
                center_counts = center_counts.sort_values('จำนวน', ascending=False)
                st.dataframe(center_counts, use_container_width=True, hide_index=True)

                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Wrong Branch')
                    center_counts.to_excel(writer, index=False, sheet_name='Summary by Center')
                st.download_button("📥 ดาวน์โหลด Excel", buffer.getvalue(),
                    f"wrong_branch_{start_date}_{end_date}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.success("✅ ไม่พบรายการออกบัตรผิดศูนย์")

        # Tab 3: Multiple G per Appointment
        with tab3:
            st.markdown("#### 🔄 ออกบัตรดีหลายใบต่อ Appointment (G > 1)")
            st.caption("Appointment ID ที่มีบัตรดี (G) มากกว่า 1 ใบ")

            mg_limit = st.slider("จำนวน Appointment แสดง", 50, 500, 100, key="mg_limit")

            # Get appointments with multiple G cards
            multi_g_appts = session.query(
                Card.appointment_id,
                func.count(Card.id).label('count')
            ).filter(
                date_filter, Card.print_status == 'G'
            ).group_by(Card.appointment_id).having(func.count(Card.id) > 1).order_by(
                func.count(Card.id).desc()
            ).limit(mg_limit).all()

            if multi_g_appts:
                appt_ids = [a.appointment_id for a in multi_g_appts]
                multi_g_cards = session.query(Card).filter(
                    date_filter,
                    Card.print_status == 'G',
                    Card.appointment_id.in_(appt_ids)
                ).order_by(Card.appointment_id).all()

                data = [{
                    'Appointment ID': c.appointment_id,
                    'รหัสศูนย์': c.branch_code,
                    'ชื่อศูนย์': (c.branch_name[:25] + '...' if c.branch_name and len(c.branch_name) > 25 else c.branch_name) or '-',
                    'Card ID': c.card_id,
                    'Serial Number': c.serial_number,
                    'Work Permit': c.work_permit_no,
                    'SLA (นาที)': round(c.sla_minutes, 2) if c.sla_minutes else 0,
                    'ผู้ให้บริการ': c.operator or '-',
                    'วันที่': c.print_date,
                } for c in multi_g_cards]

                df = pd.DataFrame(data)
                st.info(f"พบ **{multi_g_count:,}** Appointment ที่มีบัตรดีมากกว่า 1 ใบ (แสดง {len(multi_g_appts)} รายการ รวม **{len(df):,}** บัตร)")
                st.dataframe(df, use_container_width=True, hide_index=True, height=400)

                # Summary by appointment
                st.markdown("##### 📊 สรุปจำนวนบัตรต่อ Appointment")
                appt_summary = df.groupby('Appointment ID').size().reset_index(name='จำนวนบัตร')
                appt_summary = appt_summary.sort_values('จำนวนบัตร', ascending=False)
                st.dataframe(appt_summary.head(20), use_container_width=True, hide_index=True)

                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Multi G Cards')
                    appt_summary.to_excel(writer, index=False, sheet_name='By Appointment')
                st.download_button("📥 ดาวน์โหลด Excel", buffer.getvalue(),
                    f"multi_g_cards_{start_date}_{end_date}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.success("✅ ไม่พบ Appointment ที่มีบัตรดีมากกว่า 1 ใบ")

        # Tab 4: Card ID G>1
        with tab4:
            st.markdown("#### 🔄 Card ID ที่มีบัตรดีมากกว่า 1 ใบ (รหัสประจำตัวคนต่างด้าว)")
            st.caption("Card ID ที่มีบัตรดี (G) มากกว่า 1 ใบ")

            cg_limit = st.slider("จำนวน Card ID แสดง", 50, 500, 100, key="cg_limit")

            # Get Card IDs with multiple G cards
            multi_g_card_ids = session.query(
                Card.card_id,
                func.count(Card.id).label('count')
            ).filter(
                date_filter, Card.print_status == 'G',
                Card.card_id.isnot(None), Card.card_id != ''
            ).group_by(Card.card_id).having(func.count(Card.id) > 1).order_by(
                func.count(Card.id).desc()
            ).limit(cg_limit).all()

            if multi_g_card_ids:
                card_id_list = [c.card_id for c in multi_g_card_ids]
                multi_g_by_card = session.query(Card).filter(
                    date_filter,
                    Card.print_status == 'G',
                    Card.card_id.in_(card_id_list)
                ).order_by(Card.card_id).all()

                data = [{
                    'Card ID': c.card_id,
                    'Appointment ID': c.appointment_id,
                    'รหัสศูนย์': c.branch_code,
                    'ชื่อศูนย์': (c.branch_name[:25] + '...' if c.branch_name and len(c.branch_name) > 25 else c.branch_name) or '-',
                    'Serial Number': c.serial_number,
                    'Work Permit': c.work_permit_no,
                    'ผู้ให้บริการ': c.operator or '-',
                    'วันที่': c.print_date,
                } for c in multi_g_by_card]

                df = pd.DataFrame(data)
                st.info(f"พบ **{card_id_g_count:,}** Card ID ที่มีบัตรดีมากกว่า 1 ใบ (แสดง {len(multi_g_card_ids)} รายการ รวม **{len(df):,}** บัตร)")
                st.dataframe(df, use_container_width=True, hide_index=True, height=400)

                # Summary by Card ID
                st.markdown("##### 📊 สรุปจำนวนบัตรต่อ Card ID")
                card_summary = df.groupby('Card ID').size().reset_index(name='จำนวนบัตร')
                card_summary = card_summary.sort_values('จำนวนบัตร', ascending=False)
                st.dataframe(card_summary.head(20), use_container_width=True, hide_index=True)

                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Card ID G More Than 1')
                    card_summary.to_excel(writer, index=False, sheet_name='By Card ID')
                st.download_button("📥 ดาวน์โหลด Excel", buffer.getvalue(),
                    f"card_id_g_more_than_1_{start_date}_{end_date}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.success("✅ ไม่พบ Card ID ที่มีบัตรดีมากกว่า 1 ใบ")

        # ==================== Export All ====================
        st.markdown("---")
        st.markdown('<div class="section-header-blue">📥 ส่งออกข้อมูลทั้งหมด</div>', unsafe_allow_html=True)

        if st.button("📥 ดาวน์โหลดรายงานความผิดปกติทั้งหมด", type="primary", use_container_width=True):
            with st.spinner("กำลังสร้างไฟล์..."):
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    # Summary sheet
                    summary_df = pd.DataFrame({
                        'ประเภทความผิดปกติ': [
                            'นัดหมายผิดวัน',
                            'Appt ID G > 1', 'Card ID G > 1'
                        ],
                        'จำนวน': [
                            wrong_date_count,
                            multi_g_count, card_id_g_count
                        ]
                    })
                    summary_df.to_excel(writer, index=False, sheet_name='Summary')

                    # Wrong Date
                    wrong_date_data = session.query(Card).filter(date_filter, Card.wrong_date == True).all()
                    if wrong_date_data:
                        pd.DataFrame([{
                            'Appointment ID': c.appointment_id, 'รหัสศูนย์': c.branch_code,
                            'วันที่นัด': c.appt_date, 'วันที่ออกบัตร': c.print_date,
                            'ผู้ให้บริการ': c.operator
                        } for c in wrong_date_data]).to_excel(writer, index=False, sheet_name='Wrong Date')

                st.download_button("📥 ดาวน์โหลด", buffer.getvalue(),
                    f"all_anomalies_{start_date}_{end_date}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    else:
        st.markdown("""
        <div style='text-align: center; padding: 50px; background: #F8FAFC; border-radius: 15px; border: 1px solid #E2E8F0;'>
            <h2 style='color: #1E293B;'>💡 ยังไม่มีข้อมูล</h2>
            <p style='color: #64748B;'>กรุณาอัพโหลดไฟล์รายงานก่อนที่หน้า Upload</p>
        </div>
        """, unsafe_allow_html=True)

finally:
    session.close()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #64748B; padding: 10px;'>
    <p>⚠️ Bio Unified Report - Anomaly Dashboard with Search & Comparison</p>
</div>
""", unsafe_allow_html=True)
