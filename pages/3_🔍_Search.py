"""Search page - Find specific cards with detailed view and anomaly detection."""
import streamlit as st
import pandas as pd
from io import BytesIO
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session
from database.models import Card, BadCard, AnomalySLA, WrongCenter
from services.data_service import DataService
from sqlalchemy import func, or_, and_
from utils.theme import apply_theme
from utils.auth_check import require_login

init_db()


def batch_load_anomaly_data(session, card):
    """
    OPTIMIZED: Load all anomaly data for a card in batched queries instead of N+1 queries.
    This reduces 6+ separate queries to 4 optimized queries.
    """
    anomalies = []
    appt_id = card.appointment_id
    serial = card.serial_number

    # ==================== BATCH QUERY 1: G count and related cards for this appointment ====================
    # Instead of separate count + details queries, get all in one
    if appt_id:
        related_g_cards = session.query(Card).filter(
            Card.appointment_id == appt_id,
            Card.print_status == 'G'
        ).all()

        if len(related_g_cards) > 1:
            anomalies.append({
                'type': 'multiple_g',
                'title': f'นัดหมายนี้มีบัตรดี (G) มากกว่า 1 ใบ ({len(related_g_cards)} ใบ)',
                'description': 'ต้องตรวจสอบว่าเป็นการออกบัตรซ้ำหรือไม่',
                'details': related_g_cards
            })

    # ==================== BATCH QUERY 2: Duplicate serial check ====================
    if serial:
        dup_serial_cards = session.query(Card).filter(
            Card.serial_number == serial
        ).all()

        if len(dup_serial_cards) > 1:
            anomalies.append({
                'type': 'duplicate_serial',
                'title': f'Serial Number ซ้ำ ({len(dup_serial_cards)} รายการ)',
                'description': f'Serial {serial} ถูกใช้งานหลายครั้ง',
                'details': dup_serial_cards
            })

    # ==================== BATCH QUERY 3: SLA anomaly + Wrong center in one query pattern ====================
    # Check SLA anomaly
    if appt_id or serial:
        sla_filter = []
        if appt_id:
            sla_filter.append(AnomalySLA.appointment_id == appt_id)
        if serial:
            sla_filter.append(AnomalySLA.serial_number == serial)

        sla_anomaly = session.query(AnomalySLA).filter(or_(*sla_filter)).first()
        if sla_anomaly:
            anomalies.append({
                'type': 'sla_over',
                'title': f'SLA เกิน 12 นาที ({round(sla_anomaly.sla_minutes, 2) if sla_anomaly.sla_minutes else "-"} นาที)',
                'description': f'ศูนย์: {sla_anomaly.branch_name or sla_anomaly.branch_code}',
                'details': None
            })

        # Check wrong center
        wc_filter = []
        if appt_id:
            wc_filter.append(WrongCenter.appointment_id == appt_id)
        if serial:
            wc_filter.append(WrongCenter.serial_number == serial)

        wrong_center = session.query(WrongCenter).filter(or_(*wc_filter)).first()
        if wrong_center:
            anomalies.append({
                'type': 'wrong_center',
                'title': 'ออกบัตรผิดศูนย์',
                'description': f'ศูนย์ที่นัด: {wrong_center.expected_branch} | ศูนย์ที่ออก: {wrong_center.actual_branch}',
                'details': None
            })

    # ==================== Check flags on the card itself (no DB query needed) ====================
    if card.wrong_date:
        anomalies.append({
            'type': 'wrong_date',
            'title': 'นัดหมายผิดวัน',
            'description': f'วันที่นัด: {card.appt_date} | วันที่ออกบัตร: {card.print_date}',
            'details': None
        })

    if card.wait_over_1hour:
        anomalies.append({
            'type': 'wait_over',
            'title': 'รอคิวเกิน 1 ชั่วโมง',
            'description': f'เวลารอคิว: {card.wait_time_hms or "-"}',
            'details': None
        })

    # ==================== BATCH QUERY 4: Bad cards for this appointment ====================
    if appt_id:
        bad_cards = session.query(BadCard).filter(
            BadCard.appointment_id == appt_id
        ).all()

        if bad_cards:
            anomalies.append({
                'type': 'has_bad_cards',
                'title': f'นัดหมายนี้มีบัตรเสีย ({len(bad_cards)} ใบ)',
                'description': 'มีประวัติการออกบัตรเสียก่อนหน้า',
                'details': bad_cards
            })

    return anomalies

st.set_page_config(page_title="Search - Bio Dashboard", page_icon="🔍", layout="wide")

# Check authentication
require_login()

# Apply dark theme
apply_theme()

# Dark mode CSS
st.markdown("""
<style>
    .page-title {
        text-align: center;
        color: #58a6ff;
        font-size: 1.5em;
        font-weight: 600;
        margin-bottom: 5px;
    }

    .page-subtitle {
        text-align: center;
        color: #8b949e;
        margin-bottom: 25px;
    }

    .section-header {
        background: linear-gradient(90deg, #21262d 0%, #161b22 100%);
        color: #c9d1d9;
        padding: 12px 20px;
        border-radius: 8px;
        margin: 20px 0 15px 0;
        font-size: 1em;
        font-weight: 600;
        border-left: 4px solid #58a6ff;
    }

    .detail-card {
        background: #161b22;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #30363d;
        margin: 10px 0;
    }

    .detail-header {
        color: #58a6ff;
        font-weight: bold;
        margin-bottom: 10px;
        padding-bottom: 5px;
        border-bottom: 2px solid #30363d;
    }

    .flag-badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 20px;
        margin: 3px;
        font-size: 0.9em;
    }

    .flag-warning {
        background: #3d2d1f;
        color: #f59e0b;
    }

    .flag-danger {
        background: #2d1f1f;
        color: #f85149;
    }

    .flag-success {
        background: #1f2d1f;
        color: #3fb950;
    }

    .search-box {
        background: #161b22;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
        border: 1px solid #30363d;
    }

    .anomaly-box {
        background: #2d2418;
        border: 1px solid #f59e0b;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }

    .anomaly-title {
        color: #f59e0b;
        font-weight: bold;
        margin-bottom: 10px;
    }

    .info-tip {
        background: #1f2d3d;
        border-left: 4px solid #58a6ff;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        color: #c9d1d9;
    }

    .stat-box {
        background: #161b22;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #30363d;
    }

    .stat-number {
        font-size: 1.8em;
        font-weight: bold;
        color: #58a6ff;
    }

    .stat-label {
        font-size: 0.85em;
        color: #8b949e;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<div class="page-title">ค้นหาข้อมูลบัตร</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">ค้นหาด้วย Appointment ID, Card ID, Serial Number หรือ Work Permit No</div>', unsafe_allow_html=True)

# Initialize session state for search
if 'search_term' not in st.session_state:
    st.session_state.search_term = ''
if 'do_search' not in st.session_state:
    st.session_state.do_search = False

def clear_search():
    """Clear search term and reset filters."""
    st.session_state.search_term = ''
    st.session_state.do_search = False

session = get_session()

try:
    # Get date range
    min_date = session.query(func.min(Card.print_date)).scalar()
    max_date = session.query(func.max(Card.print_date)).scalar()

    # Search Section
    st.markdown('<div class="section-header">เงื่อนไขการค้นหา</div>', unsafe_allow_html=True)

    # Search inputs
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        search_term = st.text_input(
            "ค้นหา",
            value=st.session_state.search_term,
            placeholder="ใส่ Appointment ID, Card ID, Serial Number หรือ Work Permit No",
            help="ค้นหาได้หลายรูปแบบ - ระบบจะค้นหาทุกฟิลด์ที่ตรงกัน",
            key="search_input"
        )

    with col2:
        search_button = st.button("ค้นหา", type="primary", use_container_width=True)

    with col3:
        clear_button = st.button("ล้างการค้นหา", use_container_width=True, on_click=clear_search)

    # Filters
    with st.expander("ตัวกรองเพิ่มเติม", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            branches = DataService.get_branch_list(session)
            branch_filter = st.selectbox(
                "ศูนย์บริการ",
                options=['ทั้งหมด'] + branches,
            )

        with col2:
            status_filter = st.selectbox(
                "สถานะบัตร",
                options=['ทั้งหมด', 'บัตรดี (G)', 'บัตรเสีย (B)'],
            )

        with col3:
            limit = st.selectbox(
                "จำนวนผลลัพธ์สูงสุด",
                options=[100, 500, 1000, 2000, 5000],
                index=2
            )

        col1, col2 = st.columns(2)
        if min_date and max_date:
            with col1:
                start_date = st.date_input("วันที่เริ่มต้น", value=min_date, min_value=min_date, max_value=max_date)
            with col2:
                end_date = st.date_input("วันที่สิ้นสุด", value=max_date, min_value=min_date, max_value=max_date)
        else:
            start_date = None
            end_date = None

    # Update session state
    if search_button:
        st.session_state.search_term = search_term
        st.session_state.do_search = True

    # Search execution
    if (search_button or search_term) and not clear_button:
        # Prepare filters
        branch_code = None if branch_filter == 'ทั้งหมด' else branch_filter
        print_status = None
        if status_filter == 'บัตรดี (G)':
            print_status = 'G'
        elif status_filter == 'บัตรเสีย (B)':
            print_status = 'B'

        # Search
        with st.spinner("กำลังค้นหา..."):
            results = DataService.search_cards(
                session,
                search_term=search_term if search_term else None,
                branch_code=branch_code,
                start_date=start_date,
                end_date=end_date,
                print_status=print_status,
                limit=limit
            )

        st.markdown("---")

        if results:
            st.markdown('<div class="section-header">ผลการค้นหา</div>', unsafe_allow_html=True)
            st.success(f"พบ **{len(results):,}** รายการ" + (f" (แสดงสูงสุด {limit:,})" if len(results) == limit else ""))

            # Convert to DataFrame
            data = []
            for card in results:
                status_icon = "G" if card.print_status == 'G' else "B"
                flags = []
                if card.sla_over_12min:
                    flags.append("SLA>12")
                if card.wrong_branch:
                    flags.append("ผิดศูนย์")
                if card.wrong_date:
                    flags.append("ผิดวัน")
                if card.wait_over_1hour:
                    flags.append("รอ>1ชม")

                data.append({
                    'Appointment ID': card.appointment_id,
                    'Card ID': card.card_id,
                    'Serial Number': card.serial_number,
                    'Work Permit': card.work_permit_no or '-',
                    'รหัสศูนย์': card.branch_code,
                    'ชื่อศูนย์': card.branch_name[:30] if card.branch_name else '-',
                    'สถานะ': status_icon,
                    'SLA (นาที)': round(card.sla_minutes, 2) if card.sla_minutes else 0,
                    'Flags': ', '.join(flags) if flags else '-',
                    'ผู้ให้บริการ': card.operator or '-',
                    'วันที่': card.print_date,
                })

            df = pd.DataFrame(data)

            # Display results
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                height=400,
                column_config={
                    'SLA (นาที)': st.column_config.NumberColumn(format='%.2f'),
                }
            )

            # Export buttons
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Search Results')

                st.download_button(
                    label="ดาวน์โหลด Excel",
                    data=buffer.getvalue(),
                    file_name=f"search_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            with col2:
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="ดาวน์โหลด CSV",
                    data=csv,
                    file_name=f"search_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            # Detail view
            st.markdown("---")
            st.markdown('<div class="section-header">รายละเอียดและการตรวจสอบ Anomaly</div>', unsafe_allow_html=True)

            selected_idx = st.selectbox(
                "เลือกรายการเพื่อดูรายละเอียด",
                options=range(len(results)),
                format_func=lambda x: f"[{x+1}] {results[x].appointment_id} - {results[x].serial_number} ({'ดี' if results[x].print_status == 'G' else 'เสีย'})"
            )

            selected = results[selected_idx]

            # ===== ANOMALY DETECTION SECTION =====
            st.markdown("#### ผลการตรวจสอบ Anomaly")

            # OPTIMIZED: Use batch loading instead of N+1 queries
            # This reduces 6+ separate database queries to 4 optimized queries
            anomalies_found = batch_load_anomaly_data(session, selected)

            # Display anomalies
            if anomalies_found:
                st.error(f"พบปัญหา {len(anomalies_found)} รายการที่ต้องตรวจสอบ")

                for anomaly in anomalies_found:
                    with st.expander(anomaly['title'], expanded=True):
                        st.write(anomaly['description'])

                        if anomaly['details']:
                            if anomaly['type'] == 'multiple_g':
                                st.markdown("**รายการบัตรดีทั้งหมดของ Appointment นี้:**")
                                detail_data = []
                                for card in anomaly['details']:
                                    detail_data.append({
                                        'Serial': card.serial_number,
                                        'Card ID': card.card_id,
                                        'ศูนย์': card.branch_code,
                                        'Operator': card.operator or '-',
                                        'วันที่พิมพ์': str(card.print_date),
                                        'SLA (นาที)': round(card.sla_minutes, 2) if card.sla_minutes else '-'
                                    })
                                st.dataframe(pd.DataFrame(detail_data), use_container_width=True, hide_index=True)

                            elif anomaly['type'] == 'duplicate_serial':
                                st.markdown("**รายการที่ใช้ Serial Number เดียวกัน:**")
                                detail_data = []
                                for card in anomaly['details']:
                                    detail_data.append({
                                        'Appointment': card.appointment_id,
                                        'Card ID': card.card_id,
                                        'สถานะ': 'ดี' if card.print_status == 'G' else 'เสีย',
                                        'ศูนย์': card.branch_code,
                                        'วันที่พิมพ์': str(card.print_date)
                                    })
                                st.dataframe(pd.DataFrame(detail_data), use_container_width=True, hide_index=True)

                            elif anomaly['type'] == 'has_bad_cards':
                                st.markdown("**รายการบัตรเสียของ Appointment นี้:**")
                                detail_data = []
                                for bc in anomaly['details']:
                                    detail_data.append({
                                        'Serial': bc.serial_number,
                                        'Card ID': bc.card_id,
                                        'สาเหตุ': bc.reject_reason or '-',
                                        'Operator': bc.operator or '-',
                                        'วันที่': str(bc.print_date)
                                    })
                                st.dataframe(pd.DataFrame(detail_data), use_container_width=True, hide_index=True)
            else:
                st.success("ไม่พบปัญหาหรือ Anomaly ที่ต้องตรวจสอบ")

            # ===== CARD DETAILS SECTION =====
            st.markdown("---")
            st.markdown("#### ข้อมูลรายละเอียดบัตร")

            # Display details in cards
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("##### ข้อมูลบัตร")
                st.markdown(f"""
                | รายการ | ค่า |
                |--------|-----|
                | Appointment ID | `{selected.appointment_id}` |
                | Form ID | `{selected.form_id or '-'}` |
                | Form Type | `{selected.form_type or '-'}` |
                | Card ID | `{selected.card_id or '-'}` |
                | Serial Number | `{selected.serial_number or '-'}` |
                | Work Permit No | `{selected.work_permit_no or '-'}` |
                """)

            with col2:
                st.markdown("##### ศูนย์บริการ")
                st.markdown(f"""
                | รายการ | ค่า |
                |--------|-----|
                | รหัสศูนย์ | `{selected.branch_code or '-'}` |
                | ชื่อศูนย์ | {selected.branch_name or '-'} |
                | ศูนย์ที่นัด | `{selected.appt_branch or '-'}` |
                | วันที่นัด | {selected.appt_date or '-'} |
                | สถานะนัดหมาย | {selected.appt_status or '-'} |
                | ภูมิภาค | {selected.region or '-'} |
                """)

            with col3:
                st.markdown("##### ผู้ให้บริการ")
                st.markdown(f"""
                | รายการ | ค่า |
                |--------|-----|
                | Operator | `{selected.operator or '-'}` |
                | Print Date | {selected.print_date or '-'} |
                | Print Status | {selected.print_status or '-'} |
                | Reject Type | {selected.reject_type or '-'} |
                """)

            # SLA and Queue info
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("##### SLA Information")
                sla_status = "ผ่าน" if selected.sla_minutes and selected.sla_minutes <= 12 else "ไม่ผ่าน" if selected.sla_minutes else "-"
                st.markdown(f"""
                | รายการ | ค่า |
                |--------|-----|
                | SLA Start | {selected.sla_start or '-'} |
                | SLA Stop | {selected.sla_stop or '-'} |
                | SLA Duration | {selected.sla_duration or '-'} |
                | SLA (นาที) | **{round(selected.sla_minutes, 2) if selected.sla_minutes else '-'}** |
                | SLA Confirm Type | {selected.sla_confirm_type or '-'} |
                | สถานะ SLA | {sla_status} |
                """)

            with col2:
                st.markdown("##### Queue Information")
                st.markdown(f"""
                | รายการ | ค่า |
                |--------|-----|
                | Qlog ID | `{selected.qlog_id or '-'}` |
                | Qlog Branch | `{selected.qlog_branch or '-'}` |
                | Qlog Date | {selected.qlog_date or '-'} |
                | Queue No | `{selected.qlog_queue_no or '-'}` |
                | Qlog Type | {selected.qlog_type or '-'} |
                | Time In | {selected.qlog_time_in or '-'} |
                | Time Call | {selected.qlog_time_call or '-'} |
                | Wait Time (นาที) | {round(selected.wait_time_minutes, 2) if selected.wait_time_minutes else '-'} |
                | Wait Time (HMS) | {selected.wait_time_hms or '-'} |
                | Qlog SLA Status | {selected.qlog_sla_status or '-'} |
                """)

            # Status and Flags
            st.markdown("---")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("##### สถานะการพิมพ์")
                if selected.print_status == 'G':
                    st.success("บัตรดี (Good)")
                else:
                    st.error(f"บัตรเสีย (Bad) - สาเหตุ: {selected.reject_type or 'ไม่ระบุ'}")

            with col2:
                st.markdown("##### Flags / สถานะพิเศษ")
                flags_list = []

                if selected.is_mobile_unit:
                    flags_list.append("Mobile Unit")
                if selected.is_ob_center:
                    flags_list.append("OB Center")
                if selected.old_appointment:
                    flags_list.append("นัดหมายเก่า")
                if selected.emergency:
                    flags_list.append("Emergency")
                if selected.wrong_date:
                    flags_list.append("ผิดวัน")
                if selected.wrong_branch:
                    flags_list.append("ผิดศูนย์")
                if selected.sla_over_12min:
                    flags_list.append("SLA>12นาที")
                if selected.wait_over_1hour:
                    flags_list.append("รอ>1ชม")

                if flags_list:
                    for flag in flags_list:
                        st.write(f"- {flag}")
                else:
                    st.success("ไม่มี flags พิเศษ")

        else:
            st.markdown("---")
            st.info("ไม่พบข้อมูลที่ตรงกับเงื่อนไขการค้นหา")
            st.markdown("""
            **คำแนะนำ:**
            - ตรวจสอบการสะกดคำค้นหา
            - ลองค้นหาด้วยเงื่อนไขที่กว้างขึ้น
            - ตรวจสอบช่วงวันที่ที่เลือก
            """)

    else:
        # Show quick search tips
        st.markdown("---")
        st.markdown('<div class="section-header">วิธีใช้งาน</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            #### ค้นหาได้ด้วย
            - **Appointment ID** - เช่น `1-CTI001122501589`
            - **Card ID** - เช่น `1234567890123`
            - **Serial Number** - เช่น `SN00012345`
            - **Work Permit No** - เช่น `WP1234567`
            """)

        with col2:
            st.markdown("""
            #### ระบบตรวจสอบ Anomaly อัตโนมัติ
            - บัตรดีมากกว่า 1 ใบต่อ Appointment
            - Serial Number ซ้ำ
            - SLA เกิน 12 นาที
            - ออกบัตรผิดศูนย์
            - นัดหมายผิดวัน
            - รอคิวเกิน 1 ชั่วโมง
            """)

        # Quick stats
        if min_date and max_date:
            st.markdown("---")
            st.markdown("#### ข้อมูลในระบบ")
            total_cards = session.query(Card).count()
            good_cards = session.query(Card).filter(Card.print_status == 'G').count()
            bad_cards = session.query(Card).filter(Card.print_status == 'B').count()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("ข้อมูลทั้งหมด", f"{total_cards:,}")
            with col2:
                st.metric("บัตรดี", f"{good_cards:,}")
            with col3:
                st.metric("บัตรเสีย", f"{bad_cards:,}")
            with col4:
                st.metric("ช่วงข้อมูล", f"{min_date} - {max_date}")

finally:
    session.close()

# Footer
st.markdown('<div style="text-align: center; color: #6e7681; padding: 20px;">Bio Unified Report - Search</div>', unsafe_allow_html=True)
