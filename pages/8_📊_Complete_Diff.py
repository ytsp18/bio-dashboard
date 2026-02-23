"""Complete Diff page - ส่วนต่างบัตรสมบูรณ์ (Appt ID with G > 1)."""
import streamlit as st
import pandas as pd
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session
from database.models import Card, Report, CompleteDiff
from sqlalchemy import func, and_, or_
from utils.auth_check import require_login
from utils.theme import apply_theme
from utils.branch_display import get_branch_short_name

init_db()

st.set_page_config(page_title="Complete Diff - Bio Dashboard", page_icon="📊", layout="wide")

# Check authentication
require_login()

# Apply light theme
apply_theme()

# Light theme CSS for Complete Diff page
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    /* Page title */
    .page-title {
        text-align: center;
        color: #1E293B;
        font-size: 1.8em;
        font-weight: 600;
        margin-bottom: 5px;
    }

    .page-subtitle {
        text-align: center;
        color: #64748B;
        margin-bottom: 25px;
        font-size: 0.95em;
    }

    /* Section headers */
    .section-header {
        background: linear-gradient(90deg, #F8FAFC 0%, #FFFFFF 100%);
        color: #1E293B;
        padding: 16px 24px;
        border-radius: 12px;
        margin: 25px 0 15px 0;
        font-size: 1em;
        font-weight: 600;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #3B82F6;
    }

    /* Stat cards */
    .stat-card {
        background: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    .stat-number {
        font-size: 2.2em;
        font-weight: 700;
        color: #2563EB;
    }

    .stat-number-warning {
        color: #DC2626 !important;
    }

    .stat-number-success {
        color: #059669 !important;
    }

    .stat-label {
        font-size: 0.85em;
        color: #64748B;
        margin-top: 8px;
    }

    /* Alert box */
    .alert-box {
        background: #FEF2F2;
        border-left: 4px solid #EF4444;
        padding: 15px 20px;
        border-radius: 6px;
        margin: 15px 0;
        color: #991B1B;
    }

    .alert-box strong {
        color: #DC2626;
    }

    /* Info box */
    .info-box {
        background: #EFF6FF;
        border-left: 4px solid #3B82F6;
        padding: 15px 20px;
        border-radius: 6px;
        margin: 15px 0;
        color: #1E40AF;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 60px 40px;
        background: #F8FAFC;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
    }

    .empty-state h2 {
        color: #1E293B;
        font-size: 1.3em;
        margin-bottom: 10px;
    }

    .empty-state p {
        color: #64748B;
    }

    /* Footer */
    .footer {
        text-align: center;
        color: #64748B;
        padding: 20px;
        font-size: 0.85em;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<div class="page-title">ส่วนต่างบัตรสมบูรณ์</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">ตรวจสอบ Appointment ID ที่มีบัตรดี (G) มากกว่า 1 ใบ</div>', unsafe_allow_html=True)

session = get_session()

try:
    # Sidebar filters
    st.sidebar.markdown("### ตัวกรอง")

    # Date filter
    st.sidebar.markdown("##### ช่วงวันที่")
    min_date = session.query(func.min(CompleteDiff.print_date)).scalar()
    max_date = session.query(func.max(CompleteDiff.print_date)).scalar()

    if min_date and max_date:
        start_date = st.sidebar.date_input("วันที่เริ่มต้น", value=min_date, min_value=min_date, max_value=max_date)
        end_date = st.sidebar.date_input("วันที่สิ้นสุด", value=max_date, min_value=min_date, max_value=max_date)
    else:
        start_date = None
        end_date = None

    # Search section
    st.sidebar.markdown("##### ค้นหา")
    search_term = st.sidebar.text_input(
        "Appointment ID, Serial, Card ID",
        placeholder="เช่น 1-CTI001122501589",
        key="diff_search"
    )

    # Check if data exists
    total_diffs = session.query(CompleteDiff).count()

    if total_diffs == 0:
        st.markdown("""
        <div class="empty-state">
            <h2>ยังไม่มีข้อมูลส่วนต่างบัตรสมบูรณ์</h2>
            <p>กรุณาอัพโหลดไฟล์รายงานที่มี Sheet 22.ส่วนต่างบัตรสมบูรณ์</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Build query
        query = session.query(CompleteDiff)

        if start_date and end_date:
            query = query.filter(CompleteDiff.print_date >= start_date)
            query = query.filter(CompleteDiff.print_date <= end_date)

        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    CompleteDiff.appointment_id.ilike(search_pattern),
                    CompleteDiff.serial_number.ilike(search_pattern),
                    CompleteDiff.card_id.ilike(search_pattern),
                    CompleteDiff.work_permit_no.ilike(search_pattern),
                )
            )

        results = query.order_by(CompleteDiff.print_date.desc()).all()

        # Summary stats
        st.markdown('<div class="section-header">สรุปภาพรวม</div>', unsafe_allow_html=True)

        total_records = len(results)
        unique_appts = len(set([r.appointment_id for r in results]))
        unique_serials = len(set([r.serial_number for r in results if r.serial_number]))
        diff_count = unique_serials - unique_appts if unique_serials > unique_appts else 0

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{total_records:,}</div>
                <div class="stat-label">รายการทั้งหมด</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number stat-number-warning">{unique_appts:,}</div>
                <div class="stat-label">Appointment ID (G > 1)</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{unique_serials:,}</div>
                <div class="stat-label">Unique Serial</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number {'stat-number-warning' if diff_count > 0 else 'stat-number-success'}">{diff_count:,}</div>
                <div class="stat-label">ส่วนต่างที่ต้องตรวจสอบ</div>
            </div>
            """, unsafe_allow_html=True)

        if results:
            # Alert box
            st.markdown(f"""
            <div class="alert-box">
                <strong>ข้อควรตรวจสอบ:</strong> พบ {unique_appts:,} Appointment ID ที่มีบัตรดี (G) มากกว่า 1 ใบ
                ซึ่งควรมีเพียง 1 ใบต่อ 1 นัดหมาย กรุณาตรวจสอบความถูกต้อง
            </div>
            """, unsafe_allow_html=True)

            # Detail table
            st.markdown('<div class="section-header">รายละเอียด Appointment ID ที่มี G > 1</div>', unsafe_allow_html=True)

            # Convert to DataFrame
            data = []
            for r in results:
                data.append({
                    'Appointment ID': r.appointment_id,
                    'จำนวน G': r.g_count,
                    'รหัสศูนย์': r.branch_code,
                    'ชื่อศูนย์': get_branch_short_name(r.branch_code, r.branch_name),
                    'ภูมิภาค': r.region or '-',
                    'Card ID': r.card_id,
                    'Serial Number': r.serial_number,
                    'Work Permit': r.work_permit_no,
                    'SLA (นาที)': round(r.sla_minutes, 2) if r.sla_minutes else None,
                    'ผู้ให้บริการ': r.operator or '-',
                    'วันที่พิมพ์': r.print_date,
                })

            df = pd.DataFrame(data)

            # Show dataframe
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                height=400
            )

            # Group by Appointment ID
            st.markdown('<div class="section-header">สรุปตาม Appointment ID</div>', unsafe_allow_html=True)

            appt_summary = df.groupby('Appointment ID').agg({
                'จำนวน G': 'first',
                'Serial Number': 'count',
                'รหัสศูนย์': 'first',
                'ชื่อศูนย์': 'first',
                'วันที่พิมพ์': 'first',
            }).reset_index()
            appt_summary.columns = ['Appointment ID', 'จำนวน G', 'จำนวนรายการ', 'รหัสศูนย์', 'ชื่อศูนย์', 'วันที่พิมพ์']

            st.dataframe(appt_summary, use_container_width=True, hide_index=True)

            # Charts
            col1, col2 = st.columns(2)

            with col1:
                # By Region
                region_df = df.groupby('ภูมิภาค').size().reset_index(name='จำนวน')
                fig = px.pie(
                    region_df,
                    values='จำนวน',
                    names='ภูมิภาค',
                    title='สัดส่วนตามภูมิภาค',
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='#1E293B',
                    title_font_color='#1E293B',
                    legend_font_color='#64748B'
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # By Date
                date_df = df.groupby('วันที่พิมพ์').size().reset_index(name='จำนวน')
                fig = px.bar(
                    date_df,
                    x='วันที่พิมพ์',
                    y='จำนวน',
                    title='จำนวนรายการตามวันที่',
                    color_discrete_sequence=['#3B82F6']
                )
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='#1E293B',
                    title_font_color='#1E293B',
                    xaxis=dict(gridcolor='#E2E8F0'),
                    yaxis=dict(gridcolor='#E2E8F0')
                )
                st.plotly_chart(fig, use_container_width=True)

            # Export section
            st.markdown('<div class="section-header">ส่งออกข้อมูล</div>', unsafe_allow_html=True)

            col1, col2, col3 = st.columns([1, 1, 2])

            with col1:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Complete Diff')
                    appt_summary.to_excel(writer, index=False, sheet_name='Summary')

                st.download_button(
                    "ดาวน์โหลด Excel",
                    buffer.getvalue(),
                    f"complete_diff_{start_date}_{end_date}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            with col2:
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "ดาวน์โหลด CSV",
                    csv,
                    f"complete_diff_{start_date}_{end_date}.csv",
                    "text/csv",
                    use_container_width=True
                )

        else:
            st.markdown("""
            <div class="info-box">
                ไม่พบข้อมูลตามเงื่อนไขที่เลือก
            </div>
            """, unsafe_allow_html=True)

        # Additional check from Cards table
        st.markdown('<div class="section-header">ตรวจสอบเพิ่มเติมจากข้อมูลบัตร</div>', unsafe_allow_html=True)

        # Find appointments with G > 1 from main cards table
        date_filter = and_(
            Card.print_date >= start_date,
            Card.print_date <= end_date
        ) if start_date and end_date else True

        appt_g_counts = session.query(
            Card.appointment_id,
            func.count(Card.id).label('g_count')
        ).filter(
            date_filter,
            Card.print_status == 'G'
        ).group_by(Card.appointment_id).having(
            func.count(Card.id) > 1
        ).all()

        if appt_g_counts:
            st.warning(f"พบ {len(appt_g_counts)} Appointment ID ที่มีบัตรดี (G) > 1 ในตาราง Cards")

            with st.expander("ดูรายละเอียด", expanded=False):
                appt_data = []
                for appt_id, count in appt_g_counts[:50]:  # Limit to 50
                    cards = session.query(Card).filter(
                        Card.appointment_id == appt_id,
                        Card.print_status == 'G'
                    ).all()

                    for card in cards:
                        appt_data.append({
                            'Appointment ID': card.appointment_id,
                            'จำนวน G': count,
                            'Card ID': card.card_id,
                            'Serial Number': card.serial_number,
                            'ศูนย์': card.branch_code,
                            'วันที่พิมพ์': card.print_date,
                        })

                if appt_data:
                    st.dataframe(pd.DataFrame(appt_data), use_container_width=True, hide_index=True)
        else:
            st.success("ไม่พบ Appointment ID ที่มีบัตรดี (G) > 1 ในช่วงเวลาที่เลือก")

finally:
    session.close()

# Footer
st.markdown('<div class="footer">Bio Unified Report - ส่วนต่างบัตรสมบูรณ์</div>', unsafe_allow_html=True)
