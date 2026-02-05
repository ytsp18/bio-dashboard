"""Overview page - Modern Dashboard with Bar Charts."""
import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
from datetime import date, timedelta
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db, get_session, get_branch_name_map_cached
from database.models import Card, Report, DeliveryCard, Appointment, QLog, CardDeliveryRecord, CardDeliveryUpload, BranchMaster
from sqlalchemy import func, and_, or_, case, literal
from utils.theme import apply_theme
from utils.auth_check import require_login
from utils.logger import log_perf, log_info
from utils.metric_cards import (
    render_metric_card, inject_metric_cards_css, calculate_trend,
    render_operation_summary, render_action_card, render_kpi_gauge, render_mini_metric,
    render_uniform_card, render_card_grid
)
from datetime import datetime

init_db()


# Cached function for branch list
@st.cache_data(ttl=600)
def get_branch_list():
    """Get list of all branches from BranchMaster (primary) with fallback to Card table."""
    session = get_session()
    try:
        # First try to get from BranchMaster (authoritative source)
        branch_master_map = get_branch_name_map_cached()

        # Get all branch_codes that have data in cards table
        card_branches = session.query(
            Card.branch_code
        ).filter(
            Card.branch_code.isnot(None),
            Card.branch_code != ''
        ).distinct().order_by(Card.branch_code).all()

        result = []
        for b in card_branches:
            code = b.branch_code
            # Get name from BranchMaster first, fallback to code
            name = branch_master_map.get(code, code)
            result.append((code, name))

        return result
    finally:
        session.close()


# Cached function for overview stats - OPTIMIZED version
@st.cache_data(ttl=300)
def get_overview_stats(start_date, end_date, selected_branches=None):
    """Get cached overview statistics - optimized with combined queries."""
    start_time = time.perf_counter()
    session = get_session()
    try:
        from sqlalchemy import union_all

        # Base date filter
        filters = [Card.print_date >= start_date, Card.print_date <= end_date]

        # Add branch filter if specified
        if selected_branches and len(selected_branches) > 0:
            filters.append(Card.branch_code.in_(selected_branches))

        date_filter = and_(*filters)

        # ==================== OPTIMIZED: Single query for Card table counts ====================
        # Combine multiple count queries into one query using CASE statements
        card_stats = session.query(
            # Basic counts
            func.count(func.distinct(case((Card.print_status == 'G', Card.serial_number)))).label('unique_at_center'),
            func.sum(case((Card.print_status == 'B', 1), else_=0)).label('bad_at_center'),
            # Anomaly counts
            func.sum(case((Card.wrong_branch == True, 1), else_=0)).label('wrong_branch'),
            func.sum(case((Card.wrong_date == True, 1), else_=0)).label('wrong_date'),
            func.sum(case((Card.sla_over_12min == True, 1), else_=0)).label('sla_over_12'),
            func.sum(case((Card.wait_over_1hour == True, 1), else_=0)).label('wait_over_1hr'),
            # SLA stats
            func.sum(case((and_(Card.print_status == 'G', Card.sla_minutes.isnot(None)), 1), else_=0)).label('sla_total'),
            func.sum(case((and_(Card.print_status == 'G', Card.sla_minutes.isnot(None), Card.sla_minutes <= 12), 1), else_=0)).label('sla_pass'),
            func.avg(case((and_(Card.print_status == 'G', Card.sla_minutes.isnot(None)), Card.sla_minutes))).label('avg_sla'),
            # Wait time stats
            func.sum(case((and_(Card.print_status == 'G', Card.wait_time_minutes.isnot(None)), 1), else_=0)).label('wait_total'),
            func.sum(case((and_(Card.print_status == 'G', Card.wait_time_minutes.isnot(None), Card.wait_time_minutes <= 60), 1), else_=0)).label('wait_pass'),
            func.avg(case((and_(Card.print_status == 'G', Card.wait_time_minutes.isnot(None)), Card.wait_time_minutes))).label('avg_wait'),
            # Incomplete count (Good cards with missing fields)
            func.sum(case((and_(
                Card.print_status == 'G',
                or_(
                    Card.appointment_id.is_(None), Card.appointment_id == '',
                    Card.card_id.is_(None), Card.card_id == '',
                    Card.serial_number.is_(None), Card.serial_number == '',
                    Card.work_permit_no.is_(None), Card.work_permit_no == ''
                )
            ), 1), else_=0)).label('incomplete'),
        ).filter(date_filter).first()

        unique_at_center = card_stats.unique_at_center or 0
        bad_at_center = card_stats.bad_at_center or 0
        wrong_branch = card_stats.wrong_branch or 0
        wrong_date = card_stats.wrong_date or 0
        sla_over_12 = card_stats.sla_over_12 or 0
        wait_over_1hr = card_stats.wait_over_1hr or 0
        sla_total = card_stats.sla_total or 0
        sla_pass = card_stats.sla_pass or 0
        avg_sla = card_stats.avg_sla or 0
        wait_total = card_stats.wait_total or 0
        wait_pass = card_stats.wait_pass or 0
        avg_wait = card_stats.avg_wait or 0
        incomplete = card_stats.incomplete or 0

        # ==================== Delivery queries (still separate due to different tables) ====================
        report_ids_with_data = session.query(Card.report_id).filter(date_filter).distinct().subquery()

        # CardDeliveryRecord filters
        cdr_filters = [CardDeliveryRecord.print_status == 'G']
        if start_date and end_date:
            cdr_filters.append(func.date(CardDeliveryRecord.create_date) >= start_date)
            cdr_filters.append(func.date(CardDeliveryRecord.create_date) <= end_date)

        # Combined delivery serials (union)
        delivery_bio_serials = session.query(DeliveryCard.serial_number.label('sn')).filter(
            DeliveryCard.print_status == 'G',
            DeliveryCard.report_id.in_(session.query(report_ids_with_data)),
            DeliveryCard.serial_number.isnot(None), DeliveryCard.serial_number != ''
        )
        delivery_cdr_serials = session.query(CardDeliveryRecord.serial_number.label('sn')).filter(
            and_(*cdr_filters),
            CardDeliveryRecord.serial_number.isnot(None), CardDeliveryRecord.serial_number != ''
        )
        combined_delivery = union_all(delivery_bio_serials, delivery_cdr_serials).subquery()
        unique_delivery = session.query(func.count(func.distinct(combined_delivery.c.sn))).scalar() or 0

        # Combined total serials (Card + Delivery)
        card_serials = session.query(Card.serial_number.label('sn')).filter(
            date_filter, Card.print_status == 'G',
            Card.serial_number.isnot(None), Card.serial_number != ''
        )
        combined_serials = union_all(card_serials, delivery_bio_serials, delivery_cdr_serials).subquery()
        unique_total = session.query(func.count(func.distinct(combined_serials.c.sn))).scalar() or 0

        # Bad delivery cards
        bad_delivery_bio = session.query(DeliveryCard).filter(
            DeliveryCard.print_status == 'B',
            DeliveryCard.report_id.in_(session.query(report_ids_with_data))
        ).count()
        cdr_bad_filters = [CardDeliveryRecord.print_status == 'B']
        if start_date and end_date:
            cdr_bad_filters.append(func.date(CardDeliveryRecord.create_date) >= start_date)
            cdr_bad_filters.append(func.date(CardDeliveryRecord.create_date) <= end_date)
        bad_delivery_cdr = session.query(CardDeliveryRecord).filter(and_(*cdr_bad_filters)).count()
        bad_cards = bad_at_center + bad_delivery_bio + bad_delivery_cdr

        # ==================== Appointment-related queries ====================
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

        duplicate_serial = session.query(Card.serial_number).filter(
            date_filter, Card.print_status == 'G'
        ).group_by(Card.serial_number).having(func.count(Card.id) > 1).count()

        # ==================== QLog Wait Time Stats (separate query) ====================
        # Logic SLA รอคิว (ตาม Logic documentation):
        # - Type A (OB centers): นำมาคิดทุกรายการ, ตก SLA ถ้า TimeCall - Train_Time > 60 นาที
        # - Type B (SC centers): นำมาคิดเฉพาะ EI และ T, ตก SLA ถ้า TimeCall > SLA_TimeEnd
        # - เฉพาะนัดหมายที่มีการออกบัตร (G) แล้วเท่านั้น
        # Note: ถ้าไม่มี sla_time_end/qlog_train_time จะ fallback ใช้ wait_time_seconds > 3600

        # Get appointment_codes that have printed cards (G) - from BioRecord
        from database.models import BioRecord
        printed_appt_codes = session.query(BioRecord.appointment_id).filter(
            BioRecord.print_date >= start_date,
            BioRecord.print_date <= end_date,
            BioRecord.print_status == 'G',
            BioRecord.appointment_id.isnot(None),
            BioRecord.appointment_id != ''
        )
        if selected_branches and len(selected_branches) > 0:
            printed_appt_codes = printed_appt_codes.filter(BioRecord.branch_code.in_(selected_branches))
        printed_appt_codes = printed_appt_codes.distinct().subquery()

        qlog_filters = [
            QLog.qlog_date >= start_date,
            QLog.qlog_date <= end_date,
            QLog.appointment_code.in_(session.query(printed_appt_codes.c.appointment_id))  # Only appointments with printed cards
        ]
        if selected_branches and len(selected_branches) > 0:
            qlog_filters.append(QLog.branch_code.in_(selected_branches))

        # Type A (OB centers) - ALL records that have printed cards
        # Correct logic: TimeCall - Train_Time > 60 min (fallback: wait_time_seconds > 3600)
        type_a_stats = session.query(
            func.count(QLog.id).label('total'),
            func.sum(case((QLog.wait_time_seconds <= 3600, 1), else_=0)).label('pass_count'),
            func.avg(QLog.wait_time_seconds).label('avg_wait')
        ).filter(
            and_(*qlog_filters),
            QLog.qlog_type == 'A',
            QLog.wait_time_seconds.isnot(None)
        ).first()

        # Type B (SC centers) - Only EI and T that have printed cards
        # Correct logic: TimeCall > SLA_TimeEnd (fallback: wait_time_seconds > 3600)
        type_b_stats = session.query(
            func.count(QLog.id).label('total'),
            func.sum(case((QLog.wait_time_seconds <= 3600, 1), else_=0)).label('pass_count'),
            func.avg(QLog.wait_time_seconds).label('avg_wait')
        ).filter(
            and_(*qlog_filters),
            QLog.qlog_type == 'B',
            QLog.sla_status.in_(['EI', 'T']),
            QLog.wait_time_seconds.isnot(None)
        ).first()

        type_a_total = type_a_stats.total or 0
        type_a_pass = type_a_stats.pass_count or 0
        type_b_total = type_b_stats.total or 0
        type_b_pass = type_b_stats.pass_count or 0

        qlog_wait_total = type_a_total + type_b_total
        qlog_wait_pass = type_a_pass + type_b_pass
        qlog_wait_over_1hr = qlog_wait_total - qlog_wait_pass

        # Weighted average (combine Type A and Type B averages)
        type_a_avg = type_a_stats.avg_wait or 0
        type_b_avg = type_b_stats.avg_wait or 0
        if qlog_wait_total > 0:
            qlog_avg_wait_sec = (type_a_avg * type_a_total + type_b_avg * type_b_total) / qlog_wait_total
        else:
            qlog_avg_wait_sec = 0
        qlog_avg_wait_min = qlog_avg_wait_sec / 60 if qlog_avg_wait_sec else 0

        # Use QLog data if Card wait_time is empty
        final_wait_total = wait_total if wait_total > 0 else qlog_wait_total
        final_wait_pass = wait_pass if wait_total > 0 else qlog_wait_pass
        final_avg_wait = avg_wait if wait_total > 0 else qlog_avg_wait_min
        final_wait_over_1hr = wait_over_1hr if wait_total > 0 else qlog_wait_over_1hr

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
            'duplicate_serial': duplicate_serial,
            'sla_total': sla_total,
            'sla_pass': sla_pass,
            'avg_sla': avg_sla,
            'wait_total': final_wait_total,
            'wait_pass': final_wait_pass,
            'avg_wait': final_avg_wait,
            'wait_over_1hr': final_wait_over_1hr,
        }
    finally:
        session.close()
        duration = (time.perf_counter() - start_time) * 1000
        log_perf(f"get_overview_stats({start_date} to {end_date})", duration)


@st.cache_data(ttl=300)
def get_daily_stats(start_date, end_date, selected_branches=None):
    """Get cached daily statistics for chart - separated by center type (SC/OB)."""
    start_time = time.perf_counter()
    session = get_session()
    try:
        from database.models import BioRecord

        # Base date filter for BioRecord
        filters = [BioRecord.print_date >= start_date, BioRecord.print_date <= end_date]

        # Add branch filter if specified
        if selected_branches and len(selected_branches) > 0:
            filters.append(BioRecord.branch_code.in_(selected_branches))

        date_filter = and_(*filters)

        # Query BioRecord data - separated by center type (SC vs OB)
        # SC = ศูนย์บริการ (branch_code contains '-SC-')
        # OB = ศูนย์แรกรับ (branch_code contains '-OB-')
        daily_stats = session.query(
            BioRecord.print_date,
            # SC ศูนย์บริการ
            func.count(func.distinct(BioRecord.serial_number)).filter(
                BioRecord.print_status == 'G',
                BioRecord.branch_code.like('%-SC-%')
            ).label('sc_good'),
            func.sum(case((and_(BioRecord.print_status == 'B', BioRecord.branch_code.like('%-SC-%')), 1), else_=0)).label('sc_bad'),
            # OB ศูนย์แรกรับ
            func.count(func.distinct(BioRecord.serial_number)).filter(
                BioRecord.print_status == 'G',
                BioRecord.branch_code.like('%-OB-%')
            ).label('ob_good'),
            func.sum(case((and_(BioRecord.print_status == 'B', BioRecord.branch_code.like('%-OB-%')), 1), else_=0)).label('ob_bad'),
        ).filter(
            date_filter, BioRecord.print_date.isnot(None)
        ).group_by(BioRecord.print_date).order_by(BioRecord.print_date).all()

        # Convert to dict for easy lookup
        bio_data = {d.print_date: {
            'sc_good': d.sc_good or 0, 'sc_bad': d.sc_bad or 0,
            'ob_good': d.ob_good or 0, 'ob_bad': d.ob_bad or 0
        } for d in daily_stats}

        # Query CardDeliveryRecord data (บัตรจัดส่ง 68/69)
        cdr_filters = [
            func.date(CardDeliveryRecord.create_date) >= start_date,
            func.date(CardDeliveryRecord.create_date) <= end_date
        ]
        if selected_branches and len(selected_branches) > 0:
            cdr_filters.append(CardDeliveryRecord.branch_code.in_(selected_branches))

        cdr_stats = session.query(
            func.date(CardDeliveryRecord.create_date).label('print_date'),
            func.count(func.distinct(CardDeliveryRecord.serial_number)).filter(
                CardDeliveryRecord.print_status == 'G'
            ).label('delivery_g'),
            func.sum(case((CardDeliveryRecord.print_status == 'B', 1), else_=0)).label('delivery_bad'),
        ).filter(
            and_(*cdr_filters),
            CardDeliveryRecord.create_date.isnot(None)
        ).group_by(func.date(CardDeliveryRecord.create_date)).all()

        # Convert to dict
        cdr_data = {d.print_date: {'delivery_g': d.delivery_g or 0, 'delivery_bad': d.delivery_bad or 0} for d in cdr_stats}

        # Merge all dates
        all_dates = sorted(set(bio_data.keys()) | set(cdr_data.keys()))

        result = []
        for dt in all_dates:
            bio = bio_data.get(dt, {'sc_good': 0, 'sc_bad': 0, 'ob_good': 0, 'ob_bad': 0})
            cdr = cdr_data.get(dt, {'delivery_g': 0, 'delivery_bad': 0})
            result.append((
                dt,
                bio['sc_good'],        # ศูนย์บริการ SC (G)
                bio['ob_good'],        # ศูนย์แรกรับ OB (G)
                cdr['delivery_g'],     # บัตรจัดส่ง (G)
                bio['sc_bad'],         # บัตรเสีย SC
                bio['ob_bad'],         # บัตรเสีย OB
                cdr['delivery_bad'],   # บัตรเสีย จัดส่ง
            ))

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


@st.cache_data(ttl=300)
def get_upcoming_appointments(selected_branches=None):
    """
    Get upcoming appointments for workload forecasting.
    Shows appointments from today onwards (future dates).
    Includes capacity comparison from BranchMaster.max_capacity.
    """
    start_time = time.perf_counter()
    session = get_session()
    try:
        from datetime import date as dt_date
        today = dt_date.today()

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
                'max_date': None
            }

        # Build base filter - confirmed or waiting appointments (exclude CANCEL, EXPIRED)
        base_filters = [
            Appointment.appt_date >= today,
            Appointment.appt_status.in_(['SUCCESS', 'WAITING'])  # Include both confirmed and pending
        ]

        # Add branch filter if specified
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
                'max_date': None
            }

        # Today's appointments
        today_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters),
            Appointment.appt_date == today
        ).scalar() or 0

        # Tomorrow's appointments
        tomorrow = today + timedelta(days=1)
        tomorrow_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters),
            Appointment.appt_date == tomorrow
        ).scalar() or 0

        # Next 7 days (including today)
        next_7_days = today + timedelta(days=6)
        next_7_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters),
            Appointment.appt_date <= next_7_days
        ).scalar() or 0

        # Next 30 days (including today)
        next_30_days = today + timedelta(days=29)
        next_30_count = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*base_filters),
            Appointment.appt_date <= next_30_days
        ).scalar() or 0

        # Daily breakdown for chart (next 30 days or until max date)
        chart_end_date = min(next_30_days, max_future_date)
        daily_appts = session.query(
            Appointment.appt_date,
            func.count(func.distinct(Appointment.appointment_id)).label('total')
        ).filter(
            and_(*base_filters),
            Appointment.appt_date <= chart_end_date
        ).group_by(Appointment.appt_date).order_by(Appointment.appt_date).all()

        daily_data = [{'date': d.appt_date, 'count': d.total} for d in daily_appts]

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

        # By center breakdown with capacity (top 15 centers with most appointments in next 7 days)
        branch_map = get_branch_name_map_cached()
        by_center_query = session.query(
            Appointment.branch_code,
            func.count(func.distinct(Appointment.appointment_id)).label('total')
        ).filter(
            and_(*base_filters),
            Appointment.appt_date <= next_7_days
        ).group_by(Appointment.branch_code).order_by(
            func.count(func.distinct(Appointment.appointment_id)).desc()
        ).limit(15).all()

        by_center = []
        for c in by_center_query:
            capacity = capacity_map.get(c.branch_code)
            # Calculate average daily appointments for 7 days
            avg_daily = c.total / 7
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

        # By center daily breakdown (for heatmap) - next 7 days
        by_center_daily_query = session.query(
            Appointment.branch_code,
            Appointment.appt_date,
            func.count(func.distinct(Appointment.appointment_id)).label('total')
        ).filter(
            and_(*base_filters),
            Appointment.appt_date <= next_7_days
        ).group_by(Appointment.branch_code, Appointment.appt_date).all()

        by_center_daily = []
        over_capacity_count = 0
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
            'max_date': max_future_date,
            'total_capacity': total_capacity
        }
    finally:
        session.close()
        duration = (time.perf_counter() - start_time) * 1000
        log_perf("get_upcoming_appointments", duration)


@st.cache_data(ttl=300)
def get_noshow_stats(start_date, end_date, selected_branches=None):
    """
    Get No-show statistics from Appointment and QLog tables.
    No-show = Appointment (STATUS='SUCCESS') - QLog (QLOG_STATUS='S')
    """
    start_time = time.perf_counter()
    session = get_session()
    try:
        # Check if we have Appointment data
        has_appt_data = session.query(Appointment).first() is not None
        has_qlog_data = session.query(QLog).first() is not None

        if not has_appt_data:
            return {
                'has_data': False,
                'total_appointments': 0,
                'checked_in': 0,
                'no_show': 0,
                'daily_data': []
            }

        # Build date filter for Appointment
        appt_filters = [
            Appointment.appt_date >= start_date,
            Appointment.appt_date <= end_date,
            Appointment.appt_status == 'SUCCESS'  # Only confirmed appointments
        ]

        # Add branch filter if specified
        if selected_branches and len(selected_branches) > 0:
            appt_filters.append(Appointment.branch_code.in_(selected_branches))

        # Total appointments (confirmed)
        total_appts = session.query(func.count(func.distinct(Appointment.appointment_id))).filter(
            and_(*appt_filters)
        ).scalar() or 0

        # Get all appointment IDs for the period
        appt_ids_subq = session.query(Appointment.appointment_id).filter(
            and_(*appt_filters)
        ).distinct().subquery()

        # Count check-ins from QLog
        if has_qlog_data:
            qlog_filters = [
                QLog.qlog_date >= start_date,
                QLog.qlog_date <= end_date,
                QLog.qlog_status == 'S',  # Successfully served
                QLog.appointment_code.in_(session.query(appt_ids_subq))
            ]
            if selected_branches and len(selected_branches) > 0:
                qlog_filters.append(QLog.branch_code.in_(selected_branches))

            checked_in = session.query(func.count(func.distinct(QLog.appointment_code))).filter(
                and_(*qlog_filters)
            ).scalar() or 0
        else:
            checked_in = 0

        no_show = total_appts - checked_in

        # Daily breakdown for chart
        daily_data = []

        # Get daily appointment counts
        daily_appts = session.query(
            Appointment.appt_date,
            func.count(func.distinct(Appointment.appointment_id)).label('total')
        ).filter(
            and_(*appt_filters)
        ).group_by(Appointment.appt_date).all()

        # Get daily check-in counts from QLog
        if has_qlog_data:
            daily_checkins = session.query(
                QLog.qlog_date,
                func.count(func.distinct(QLog.appointment_code)).label('checkin')
            ).filter(
                QLog.qlog_date >= start_date,
                QLog.qlog_date <= end_date,
                QLog.qlog_status == 'S',
                QLog.appointment_code.in_(session.query(appt_ids_subq))
            )
            if selected_branches and len(selected_branches) > 0:
                daily_checkins = daily_checkins.filter(QLog.branch_code.in_(selected_branches))
            daily_checkins = daily_checkins.group_by(QLog.qlog_date).all()
            checkin_map = {d.qlog_date: d.checkin for d in daily_checkins}
        else:
            checkin_map = {}

        # Combine into daily_data
        for d in daily_appts:
            checkin = checkin_map.get(d.appt_date, 0)
            daily_data.append({
                'date': d.appt_date,
                'total_appt': d.total,
                'checked_in': checkin,
                'no_show': d.total - checkin
            })

        # Sort by date
        daily_data = sorted(daily_data, key=lambda x: x['date'])

        return {
            'has_data': True,
            'total_appointments': total_appts,
            'checked_in': checked_in,
            'no_show': no_show,
            'daily_data': daily_data
        }
    finally:
        session.close()
        duration = (time.perf_counter() - start_time) * 1000
        log_perf(f"get_noshow_stats({start_date} to {end_date})", duration)


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

    # Row 2: Branch filter and options
    col_branch, col_options = st.columns([4, 1])

    with col_branch:
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

    with col_options:
        show_trends = st.checkbox("📈 แสดง Trend", value=False, help="เปิดเพื่อแสดงการเปรียบเทียบกับช่วงก่อนหน้า (ช้าขึ้น)")

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

    # Get trend data only if enabled (to improve performance)
    if show_trends:
        # Calculate date ranges for comparison
        current_days = (end_date - start_date).days + 1

        # Previous period (same length as current period, immediately before)
        prev_day_end = start_date - timedelta(days=1)
        prev_day_start = prev_day_end - timedelta(days=current_days - 1)

        # Get previous period stats for trends (only 1 query instead of 3)
        stats_prev_day = get_overview_stats(prev_day_start, prev_day_end, selected_branches)

        # Calculate trends (only compare with previous period)
        trend_total_day = calculate_trend(unique_total, stats_prev_day['unique_total'])
        trend_bad_day = calculate_trend(bad_cards, stats_prev_day['bad_cards'])
        trend_complete_day = calculate_trend(complete_cards, stats_prev_day['complete_cards'])
    else:
        # No trends - set all to None for faster loading
        stats_prev_day = None
        trend_total_day = None
        trend_bad_day = None
        trend_complete_day = None

    # ==================== OPERATION SUMMARY PANEL ====================
    st.markdown("---")
    inject_metric_cards_css()

    # Calculate overall operation status
    # Thresholds for status determination
    bad_rate = (bad_cards / (unique_total + bad_cards) * 100) if (unique_total + bad_cards) > 0 else 0
    anomaly_rate = (total_anomalies / unique_total * 100) if unique_total > 0 else 0

    if bad_rate > 5 or anomaly_rate > 3 or total_anomalies > 50:
        overall_status = "critical"
        status_msg = "ต้องตรวจสอบ"
    elif bad_rate > 2 or anomaly_rate > 1 or total_anomalies > 20:
        overall_status = "warning"
        status_msg = "มีรายการต้องติดตาม"
    else:
        overall_status = "ok"
        status_msg = "ปกติ"

    # Build alerts list based on data
    alerts = []
    if bad_cards > 0 and bad_rate > 2:
        alerts.append({"message": f"บัตรเสีย {bad_cards:,} ใบ ({bad_rate:.1f}%)", "type": "warning"})
    if total_anomalies > 0:
        alerts.append({"message": f"พบความผิดปกติ {total_anomalies:,} รายการ", "type": "warning" if total_anomalies < 50 else "critical"})
    if sla_pass_pct < 90:
        alerts.append({"message": f"SLA ออกบัตร {sla_pass_pct:.1f}% (ต่ำกว่า 90%)", "type": "warning"})

    # Render Operation Summary Panel
    render_operation_summary(
        title="สรุปสถานะการดำเนินงาน",
        overall_status=overall_status,
        status_message=status_msg,
        metrics=[
            {"label": "บัตรดี (G)", "value": unique_total, "icon": "serial"},
            {"label": "บัตรเสีย (B)", "value": bad_cards, "icon": "error"},
            {"label": "สมบูรณ์", "value": complete_cards, "icon": "complete"},
            {"label": "Anomaly", "value": total_anomalies, "icon": "warning"},
            {"label": "SLA ผ่าน", "value": sla_pass, "icon": "sla"},
            {"label": "Work Permit", "value": unique_work_permit, "icon": "permit"},
        ],
        alerts=alerts if alerts else None,
        last_updated=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )

    # ==================== METRIC CARDS ====================
    st.markdown("### 📊 รายละเอียดการออกบัตร")
    st.caption("📌 ข้อมูลแยกตามประเภทการรับบัตร และสถานะความสมบูรณ์ของข้อมูล")

    # Row 1: ประเภทการรับบัตร (4 cards เท่ากัน)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_uniform_card(
            title="รับบัตรที่ศูนย์",
            value=unique_at_center,
            subtitle="ผู้รับบริการมารับบัตรด้วยตนเอง ที่ศูนย์บริการ",
            icon="center",
            card_type="info",
            trend_day=calculate_trend(unique_at_center, stats_prev_day['unique_at_center']) if show_trends else None,
        )
    with col2:
        render_uniform_card(
            title="จัดส่งบัตร",
            value=unique_delivery,
            subtitle="บัตรที่จัดส่งทางไปรษณีย์ หรือหน่วยเคลื่อนที่",
            icon="delivery",
            card_type="info",
            trend_day=calculate_trend(unique_delivery, stats_prev_day['unique_delivery']) if show_trends else None,
        )
    with col3:
        render_uniform_card(
            title="รวมบัตรดี (G)",
            value=unique_total,
            subtitle=f"บัตรที่พิมพ์สำเร็จทั้งหมด | Good Rate: {100-bad_rate:.1f}%",
            icon="serial",
            card_type="success",
            trend_day=trend_total_day,
        )
    with col4:
        render_uniform_card(
            title="บัตรเสีย (B)",
            value=bad_cards,
            subtitle=f"บัตรที่พิมพ์ไม่สำเร็จ / ต้องพิมพ์ใหม่ | {bad_rate:.1f}%",
            icon="error",
            card_type="danger" if bad_cards > 0 else "info",
            trend_day=trend_bad_day,
            inverse_trend=True,
        )

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # Row 2: สถานะข้อมูล (4 cards เท่ากัน)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_uniform_card(
            title="ข้อมูลครบถ้วน",
            value=complete_cards,
            subtitle=f"มีครบทุกฟิลด์ (Appt, Card ID, SN, WP) | {complete_pct:.1f}%",
            icon="complete",
            card_type="success",
            trend_day=trend_complete_day,
        )
    with col2:
        render_uniform_card(
            title="ออกบัตรหลายใบ",
            value=appt_multiple_g,
            subtitle=f"1 นัดหมาย ออกบัตรดีมากกว่า 1 ใบ | {appt_multiple_records:,} records",
            icon="warning",
            card_type="warning" if appt_multiple_g > 0 else "info",
            trend_day=calculate_trend(appt_multiple_g, stats_prev_day['appt_multiple_g']) if show_trends else None,
            inverse_trend=True,
        )
    with col3:
        render_uniform_card(
            title="ข้อมูลไม่ครบ",
            value=incomplete,
            subtitle="ขาด Appt ID, Card ID, SN หรือ Work Permit",
            icon="incomplete",
            card_type="warning" if incomplete > 0 else "info",
            trend_day=calculate_trend(incomplete, stats_prev_day['incomplete']) if show_trends else None,
            inverse_trend=True,
        )
    with col4:
        render_uniform_card(
            title="Work Permit",
            value=unique_work_permit,
            subtitle="จำนวนใบอนุญาตทำงานที่ไม่ซ้ำกัน",
            icon="permit",
            card_type="info",
            trend_day=calculate_trend(unique_work_permit, stats_prev_day['unique_work_permit']) if show_trends else None,
        )

    st.markdown("---")

    # ==================== DAILY CHARTS (FULL WIDTH) ====================
    st.markdown("### 📊 สรุปจำนวนบัตรรายวัน")

    daily_stats = get_daily_stats(start_date, end_date, selected_branches)

    if daily_stats:
        daily_data = pd.DataFrame([{
            'วันที่': d[0],
            'SC ศูนย์บริการ (G)': d[1],
            'OB แรกรับ (G)': d[2],
            'บัตรจัดส่ง (G)': d[3],
            'บัตรเสีย SC': d[4],
            'บัตรเสีย OB': d[5],
            'บัตรเสีย จัดส่ง': d[6],
        } for d in daily_stats])

        # Calculate totals
        daily_data['รวมบัตรดี'] = daily_data['SC ศูนย์บริการ (G)'] + daily_data['OB แรกรับ (G)'] + daily_data['บัตรจัดส่ง (G)']
        daily_data['รวมบัตรเสีย'] = daily_data['บัตรเสีย SC'] + daily_data['บัตรเสีย OB'] + daily_data['บัตรเสีย จัดส่ง']

        dates = [d.strftime('%d/%m') if hasattr(d, 'strftime') else str(d) for d in daily_data['วันที่']]

        # Mixed Bar + Line Chart (Bar for breakdown, Line for total)
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
                "data": ["SC ศูนย์บริการ", "OB แรกรับ", "บัตรจัดส่ง", "บัตรเสีย SC", "บัตรเสีย OB", "บัตรเสีย จัดส่ง", "รวมบัตรดี"],
                "bottom": 0,
                "textStyle": {"color": "#9CA3AF"},
            },
            "grid": {"left": "3%", "right": "4%", "bottom": "18%", "top": "10%", "containLabel": True},
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
                    "name": "SC ศูนย์บริการ",
                    "type": "bar",
                    "stack": "good",
                    "data": daily_data['SC ศูนย์บริการ (G)'].tolist(),
                    "itemStyle": {"color": "#10B981"},
                    "barMaxWidth": 50,
                },
                {
                    "name": "OB แรกรับ",
                    "type": "bar",
                    "stack": "good",
                    "data": daily_data['OB แรกรับ (G)'].tolist(),
                    "itemStyle": {"color": "#3B82F6"},
                    "barMaxWidth": 50,
                },
                {
                    "name": "บัตรจัดส่ง",
                    "type": "bar",
                    "stack": "good",
                    "data": daily_data['บัตรจัดส่ง (G)'].tolist(),
                    "itemStyle": {"color": "#8B5CF6"},
                    "barMaxWidth": 50,
                },
                {
                    "name": "บัตรเสีย SC",
                    "type": "bar",
                    "stack": "bad",
                    "data": daily_data['บัตรเสีย SC'].tolist(),
                    "itemStyle": {"color": "#EF4444"},
                    "barMaxWidth": 50,
                },
                {
                    "name": "บัตรเสีย OB",
                    "type": "bar",
                    "stack": "bad",
                    "data": daily_data['บัตรเสีย OB'].tolist(),
                    "itemStyle": {"color": "#F97316"},
                    "barMaxWidth": 50,
                },
                {
                    "name": "บัตรเสีย จัดส่ง",
                    "type": "bar",
                    "stack": "bad",
                    "data": daily_data['บัตรเสีย จัดส่ง'].tolist(),
                    "itemStyle": {"color": "#DC2626"},
                    "barMaxWidth": 50,
                },
                {
                    "name": "รวมบัตรดี",
                    "type": "line",
                    "data": daily_data['รวมบัตรดี'].tolist(),
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
    else:
        st.info("ไม่มีข้อมูลในช่วงเวลาที่เลือก")

    # ==================== APPOINTMENT & SERVICE ANALYSIS ====================
    noshow_stats = get_noshow_stats(start_date, end_date, selected_branches)

    if noshow_stats['has_data']:
        st.markdown("---")
        st.markdown("### 📅 ข้อมูลการนัดหมายและเข้าใช้บริการ")
        st.caption("📌 ข้อมูลจากตาราง Appointment และ QLog | No-Show = นัดหมายแล้วไม่มา Check-in")

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📋 นัดหมายทั้งหมด", f"{noshow_stats['total_appointments']:,}")
        with col2:
            st.metric("✅ มา Check-in", f"{noshow_stats['checked_in']:,}")
        with col3:
            noshow_pct = (noshow_stats['no_show'] / noshow_stats['total_appointments'] * 100) if noshow_stats['total_appointments'] > 0 else 0
            st.metric("❌ No-Show", f"{noshow_stats['no_show']:,}", f"{noshow_pct:.1f}%")
        with col4:
            checkin_pct = (noshow_stats['checked_in'] / noshow_stats['total_appointments'] * 100) if noshow_stats['total_appointments'] > 0 else 0
            st.metric("📊 อัตรามา Check-in", f"{checkin_pct:.1f}%")

        # Daily No-Show Chart
        if noshow_stats['daily_data']:
            noshow_df = pd.DataFrame(noshow_stats['daily_data'])
            noshow_dates = [d.strftime('%d/%m') if hasattr(d, 'strftime') else str(d) for d in noshow_df['date']]

            noshow_chart_options = {
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
                    "data": ["นัดหมาย (Appointment)", "มา Check-in", "No-Show"],
                    "bottom": 0,
                    "textStyle": {"color": "#9CA3AF"},
                },
                "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "10%", "containLabel": True},
                "xAxis": {
                    "type": "category",
                    "data": noshow_dates,
                    "axisLine": {"lineStyle": {"color": "#374151"}},
                    "axisLabel": {"color": "#9CA3AF", "rotate": 45 if len(noshow_dates) > 15 else 0},
                },
                "yAxis": {
                    "type": "value",
                    "axisLine": {"lineStyle": {"color": "#374151"}},
                    "axisLabel": {"color": "#9CA3AF"},
                    "splitLine": {"lineStyle": {"color": "#1F2937"}},
                },
                "series": [
                    {
                        "name": "นัดหมาย (Appointment)",
                        "type": "bar",
                        "data": noshow_df['total_appt'].tolist(),
                        "itemStyle": {"color": "#3B82F6"},
                        "barMaxWidth": 40,
                    },
                    {
                        "name": "มา Check-in",
                        "type": "bar",
                        "data": noshow_df['checked_in'].tolist(),
                        "itemStyle": {"color": "#10B981"},
                        "barMaxWidth": 40,
                    },
                    {
                        "name": "No-Show",
                        "type": "line",
                        "data": noshow_df['no_show'].tolist(),
                        "itemStyle": {"color": "#EF4444"},
                        "lineStyle": {"width": 3, "type": "dashed"},
                        "symbol": "circle",
                        "symbolSize": 8,
                        "smooth": True,
                        "label": {
                            "show": len(noshow_dates) <= 10,
                            "position": "top",
                            "color": "#EF4444",
                            "fontSize": 11,
                            "fontWeight": "bold"
                        }
                    },
                ]
            }
            st_echarts(options=noshow_chart_options, height="400px", key="noshow_chart")

            # Pie chart for No-Show ratio
            col1, col2 = st.columns(2)
            with col1:
                noshow_pie = {
                    "animation": True,
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
                        "name": "สถานะนัดหมาย",
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
                            {"value": noshow_stats['checked_in'], "name": "มา Check-in", "itemStyle": {"color": "#10B981"}},
                            {"value": noshow_stats['no_show'], "name": "No-Show", "itemStyle": {"color": "#EF4444"}}
                        ]
                    }]
                }
                st.markdown("**สัดส่วน Check-in / No-Show**")
                st_echarts(options=noshow_pie, height="280px", key="noshow_pie")

            with col2:
                # Info box
                st.markdown("""
                <div style="background: linear-gradient(135deg, #1E293B, #0F172A); border-radius: 12px; padding: 20px; border: 1px solid #374151;">
                    <h4 style="color: #F1F5F9; margin: 0 0 16px 0;">📊 สรุปข้อมูล No-Show</h4>
                    <ul style="color: #9CA3AF; margin: 0; padding-left: 20px;">
                        <li><b style="color: #3B82F6;">นัดหมาย (Appointment)</b> - จำนวนคนที่นัดหมายไว้ (STATUS=SUCCESS)</li>
                        <li><b style="color: #10B981;">มา Check-in</b> - จำนวนคนที่มา Check-in จริง (QLOG_STATUS=S)</li>
                        <li><b style="color: #EF4444;">No-Show</b> - นัดหมายแล้วไม่มา = นัดหมาย - Check-in</li>
                    </ul>
                    <hr style="border-color: #374151; margin: 16px 0;">
                    <p style="color: #6B7280; font-size: 0.85rem; margin: 0;">
                        💡 ข้อมูลมาจากไฟล์ Appointment และ QLog ที่อัพโหลดแยก
                    </p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("---")
        st.markdown("### 📅 ข้อมูลการนัดหมายและเข้าใช้บริการ")
        st.info("⚠️ ยังไม่มีข้อมูล Appointment/QLog - กรุณาอัพโหลดไฟล์ Appointment และ QLog ในหน้า Upload เพื่อดูข้อมูลการนัดหมาย")

    # ==================== UPCOMING APPOINTMENTS (WORKLOAD FORECAST) ====================
    upcoming_stats = get_upcoming_appointments(selected_branches)

    if upcoming_stats['has_data']:
        st.markdown("---")

        # Header with link to detailed page
        col_header, col_link = st.columns([5, 1])
        with col_header:
            st.markdown("### 📆 นัดหมายล่วงหน้า (Workload Forecast)")
        with col_link:
            st.page_link("pages/3_📆_Forecast.py", label="📊 ดูรายละเอียด", icon="➡️")

        st.caption("📌 แสดงปริมาณการนัดหมายที่จะเกิดขึ้นในอนาคต เทียบกับ Capacity ของแต่ละศูนย์")

        # Warning if over capacity
        if upcoming_stats['over_capacity_count'] > 0:
            st.warning(f"⚠️ พบ {upcoming_stats['over_capacity_count']} ศูนย์/วัน ที่มีนัดหมายเกิน Capacity - กรุณาเตรียมรับมือ!")

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📅 วันนี้", f"{upcoming_stats['today']:,}")
        with col2:
            st.metric("📆 พรุ่งนี้", f"{upcoming_stats['tomorrow']:,}")
        with col3:
            st.metric("📊 7 วันข้างหน้า", f"{upcoming_stats['next_7_days']:,}")
        with col4:
            st.metric("📈 30 วันข้างหน้า", f"{upcoming_stats['next_30_days']:,}")

        # Daily forecast chart
        if upcoming_stats['daily_data']:
            upcoming_df = pd.DataFrame(upcoming_stats['daily_data'])
            upcoming_dates = [d.strftime('%d/%m') if hasattr(d, 'strftime') else str(d) for d in upcoming_df['date']]

            # Mark today and tomorrow
            from datetime import date as dt_date
            today_dt = dt_date.today()

            # Calculate average for reference line
            avg_count = upcoming_df['count'].mean() if len(upcoming_df) > 0 else 0

            # Get total capacity for limit line
            total_capacity = upcoming_stats.get('total_capacity', 0)

            upcoming_chart_options = {
                "animation": True,
                "animationDuration": 800,
                "backgroundColor": "transparent",
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "shadow"},
                    "backgroundColor": "rgba(30, 41, 59, 0.95)",
                    "borderColor": "#475569",
                    "textStyle": {"color": "#F1F5F9"},
                },
                "legend": {
                    "data": ["นัดหมายล่วงหน้า", "Capacity รวม", "ค่าเฉลี่ย"],
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
                        "name": "นัดหมายล่วงหน้า",
                        "type": "bar",
                        "data": [
                            {
                                "value": row['count'],
                                "itemStyle": {
                                    "color": "#F59E0B" if row['date'] == today_dt else (
                                        "#3B82F6" if row['date'] == today_dt + timedelta(days=1) else "#6366F1"
                                    )
                                }
                            } for _, row in upcoming_df.iterrows()
                        ],
                        "barMaxWidth": 50,
                        "label": {
                            "show": len(upcoming_dates) <= 14,
                            "position": "top",
                            "color": "#9CA3AF",
                            "fontSize": 10
                        }
                    },
                    {
                        "name": "Capacity รวม",
                        "type": "line",
                        "data": [total_capacity] * len(upcoming_dates),
                        "itemStyle": {"color": "#10B981"},
                        "lineStyle": {"width": 3, "type": "solid"},
                        "symbol": "none",
                    },
                    {
                        "name": "ค่าเฉลี่ย",
                        "type": "line",
                        "data": [round(avg_count)] * len(upcoming_dates),
                        "itemStyle": {"color": "#EF4444"},
                        "lineStyle": {"width": 2, "type": "dashed"},
                        "symbol": "none",
                    }
                ]
            }
            st.markdown(f"**📊 ปริมาณนัดหมายรายวัน** (สีส้ม = วันนี้, สีฟ้า = พรุ่งนี้, เส้นเขียว = Capacity {total_capacity:,}, เส้นประแดง = ค่าเฉลี่ย)")
            st_echarts(options=upcoming_chart_options, height="350px", key="upcoming_daily_chart")
    else:
        st.markdown("---")
        st.markdown("### 📆 นัดหมายล่วงหน้า (Workload Forecast)")
        st.info("⚠️ ยังไม่มีข้อมูลนัดหมายล่วงหน้า - กรุณาอัพโหลดไฟล์ Appointment ที่มีวันนัดในอนาคต")

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

    # SLA Summary metrics with mini cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_mini_metric(
            label="ผ่าน SLA ออกบัตร",
            value=sla_pass,
            trend=calculate_trend(sla_pass, stats_prev_day['sla_pass']) if show_trends else None,
            card_type="success" if sla_pass_pct >= 90 else ("warning" if sla_pass_pct >= 80 else "danger"),
        )
    with col2:
        render_mini_metric(
            label="ไม่ผ่าน SLA",
            value=sla_fail,
            trend=calculate_trend(sla_fail, stats_prev_day['sla_total'] - stats_prev_day['sla_pass']) if show_trends else None,
            card_type="danger" if sla_fail > 0 else "info",
            inverse_trend=True,
        )
    with col3:
        render_mini_metric(
            label="ผ่าน SLA รอคิว",
            value=wait_pass,
            trend=calculate_trend(wait_pass, stats_prev_day['wait_pass']) if show_trends else None,
            card_type="success" if wait_pass_pct >= 90 else ("warning" if wait_pass_pct >= 80 else "danger"),
        )
    with col4:
        render_mini_metric(
            label="รอเกิน 1 ชม.",
            value=wait_fail,
            trend=calculate_trend(wait_fail, stats_prev_day['wait_total'] - stats_prev_day['wait_pass']) if show_trends else None,
            card_type="danger" if wait_fail > 0 else "info",
            inverse_trend=True,
        )

    st.markdown("---")

    # ==================== ANOMALY SECTION ====================
    st.markdown("### 🔍 รายการที่ต้องตรวจสอบ (Anomaly)")

    if total_anomalies > 0:
        st.warning(f"⚠️ พบ {total_anomalies:,} รายการต้องตรวจสอบ")

    # Use action cards for anomalies - making them actionable for operations
    col1, col2 = st.columns(2)

    with col1:
        render_action_card(
            title="ออกบัตรผิดศูนย์",
            description="ออกบัตรที่ศูนย์อื่นไม่ใช่ศูนย์ที่นัดหมาย",
            icon="center",
            status="warning" if wrong_branch > 0 else "ok",
            count=wrong_branch if wrong_branch > 0 else None,
            action_label="ดูรายละเอียด" if wrong_branch > 0 else None,
            action_page="pages/6_⚠️_Anomaly.py" if wrong_branch > 0 else None,
        )
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        render_action_card(
            title="นัดหมายผิดวัน",
            description="ออกบัตรวันที่ไม่ตรงกับวันนัดหมาย",
            icon="appointment",
            status="warning" if wrong_date > 0 else "ok",
            count=wrong_date if wrong_date > 0 else None,
            action_label="ดูรายละเอียด" if wrong_date > 0 else None,
            action_page="pages/6_⚠️_Anomaly.py" if wrong_date > 0 else None,
        )
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        render_action_card(
            title="Serial ซ้ำ",
            description="Serial Number ถูกใช้ซ้ำกัน",
            icon="serial",
            status="critical" if duplicate_serial > 0 else "ok",
            count=duplicate_serial if duplicate_serial > 0 else None,
            action_label="ดูรายละเอียด" if duplicate_serial > 0 else None,
            action_page="pages/6_⚠️_Anomaly.py" if duplicate_serial > 0 else None,
        )

    with col2:
        render_action_card(
            title="ออกบัตรหลายใบ (G>1)",
            description="1 Appointment ออกบัตรดีมากกว่า 1 ใบ",
            icon="warning",
            status="warning" if appt_multiple_g > 0 else "ok",
            count=appt_multiple_g if appt_multiple_g > 0 else None,
            action_label="ดูรายละเอียด" if appt_multiple_g > 0 else None,
            action_page="pages/6_⚠️_Anomaly.py" if appt_multiple_g > 0 else None,
        )
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        render_action_card(
            title="SLA เกิน 12 นาที",
            description="เวลาออกบัตรเกินมาตรฐาน SLA",
            icon="sla",
            status="warning" if sla_over_12 > 0 else "ok",
            count=sla_over_12 if sla_over_12 > 0 else None,
            action_label="ดูรายละเอียด" if sla_over_12 > 0 else None,
            action_page="pages/6_⚠️_Anomaly.py" if sla_over_12 > 0 else None,
        )
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        render_action_card(
            title="รอคิวเกิน 1 ชม.",
            description="เวลารอคิวเกินมาตรฐาน",
            icon="sla",
            status="warning" if wait_over_1hr > 0 else "ok",
            count=wait_over_1hr if wait_over_1hr > 0 else None,
            action_label="ดูรายละเอียด" if wait_over_1hr > 0 else None,
            action_page="pages/6_⚠️_Anomaly.py" if wait_over_1hr > 0 else None,
        )

    # Quick action button to Anomaly page
    if total_anomalies > 0:
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            st.page_link("pages/6_⚠️_Anomaly.py", label="📋 ไปหน้า Anomaly เพื่อตรวจสอบทั้งหมด", icon="➡️", use_container_width=True)
