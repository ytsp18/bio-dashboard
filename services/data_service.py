"""Data service for database operations."""
import pandas as pd
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session

from database.connection import session_scope, get_session
from database.models import Report, Card, BadCard, CenterStat, AnomalySLA, WrongCenter, CompleteDiff, DeliveryCard
from services.excel_parser import ExcelParser


class DataService:
    """Service for data operations."""

    @staticmethod
    def import_excel(file_path: str, original_filename: str = None) -> Dict[str, Any]:
        """Import data from Excel file to database.

        Args:
            file_path: Path to the Excel file (can be temp file)
            original_filename: Original filename if different from file_path
        """
        parser = ExcelParser(file_path)
        parser.load()

        # Extract report date - use original filename if provided
        if original_filename:
            # Create a temporary parser to extract date from original filename
            parser._original_filename = original_filename
        report_date = parser.extract_report_date()

        # Get report month for date correction
        report_month = report_date.month if report_date else None

        # Get filename - use original if provided
        filename = original_filename if original_filename else file_path.split('/')[-1]

        # Parse all data sources
        good_cards_df = parser.parse_good_cards()
        bad_cards_df = parser.parse_bad_cards()
        all_data = parser.parse_all_data()

        # Determine which data source to use
        total_from_sheets = len(good_cards_df) + len(bad_cards_df)
        total_from_all = len(all_data)

        # Decision logic:
        # - Daily reports: Sheet 13 contains ALL data with full details → use Sheet 13
        # - Monthly reports: Sheet 13 only contains anomaly cases (~10K), Sheet 2+3 has all (~56K)
        #   → use Sheet 2+3 but enrich with Sheet 13 details when possible

        # If Sheet 13 has >= 80% of Sheet 2+3 data, use Sheet 13 (daily report pattern)
        # Otherwise use Sheet 2+3 (monthly report pattern)
        if total_from_all > 0 and total_from_sheets > 0:
            ratio = total_from_all / total_from_sheets
            use_sheet_13_only = ratio >= 0.8  # Daily reports typically have equal or more in Sheet 13
        elif total_from_all > 0:
            use_sheet_13_only = True
        else:
            use_sheet_13_only = False

        # Build lookup from Sheet 13 for enrichment (for monthly reports)
        # Use serial_number as key since it's unique per card
        sheet13_lookup = {}
        if not use_sheet_13_only and total_from_all > 0:
            for _, row in all_data.iterrows():
                serial = row.get('serial_number')
                if pd.notna(serial):
                    # Use serial_number as primary key
                    sheet13_lookup[str(serial)] = row

        # Calculate stats
        if use_sheet_13_only:
            # Use Sheet 13 stats
            if 'print_status' in all_data.columns:
                total_good = len(all_data[all_data['print_status'] == 'G'])
                total_bad = len(all_data[all_data['print_status'] == 'B'])
            else:
                total_good = 0
                total_bad = 0
            total_records = total_from_all
        else:
            # Use Sheet 2+3 stats
            total_good = len(good_cards_df)
            total_bad = len(bad_cards_df)
            total_records = total_from_sheets

        with session_scope() as session:
            # Check if report already exists
            existing = session.query(Report).filter(
                Report.filename == filename
            ).first()

            if existing:
                # Delete existing data
                session.delete(existing)
                session.flush()

            # Create new report
            report = Report(
                filename=filename,
                report_date=report_date,
                total_good=total_good,
                total_bad=total_bad,
                total_records=total_records,
            )
            session.add(report)
            session.flush()

            cards_imported = 0
            BATCH_SIZE = 500  # Commit every 500 records to avoid timeout

            # Helper function to get enriched values from Sheet 13 row (pandas Series)
            def get_enriched_value(enriched_row, key, default=None):
                """Get value from enriched pandas Series row."""
                if enriched_row is None or isinstance(enriched_row, dict):
                    return default
                try:
                    val = enriched_row.get(key)
                    if pd.notna(val):
                        return str(val)
                except:
                    pass
                return default

            if not use_sheet_13_only:
                # Import from Sheet 2 (good cards) with Sheet 13 enrichment
                for _, row in good_cards_df.iterrows():
                    appt_id = str(row.get('appointment_id', '')) if pd.notna(row.get('appointment_id')) else None
                    serial = str(row.get('serial_number', '')) if pd.notna(row.get('serial_number')) else None

                    # Try to get enriched data from Sheet 13 using serial_number
                    enriched = sheet13_lookup.get(serial) if serial else None

                    # Safe float conversion for sla_minutes
                    sla_val = row.get('sla_minutes')
                    try:
                        sla_minutes = float(sla_val) if pd.notna(sla_val) else None
                    except (ValueError, TypeError):
                        sla_minutes = None

                    # Check if SLA over 12 minutes
                    sla_over_12 = sla_minutes > 12 if sla_minutes is not None else False

                    card = Card(
                        report_id=report.id,
                        appointment_id=appt_id,
                        branch_code=str(row.get('branch_code', '')) if pd.notna(row.get('branch_code')) else None,
                        branch_name=str(row.get('branch_name', '')) if pd.notna(row.get('branch_name')) else None,
                        region=str(row.get('region', '')) if pd.notna(row.get('region')) else None,
                        card_id=str(row.get('card_id', '')) if pd.notna(row.get('card_id')) else None,
                        serial_number=str(row.get('serial_number', '')) if pd.notna(row.get('serial_number')) else None,
                        work_permit_no=str(row.get('work_permit_no', '')) if pd.notna(row.get('work_permit_no')) else None,
                        print_status='G',
                        sla_minutes=sla_minutes,
                        operator=str(row.get('operator', '')) if pd.notna(row.get('operator')) else None,
                        print_date=parser.parse_date_value(row.get('print_date'), report_month),
                        sla_over_12min=sla_over_12,
                        # Enriched from Sheet 13 if available
                        form_id=get_enriched_value(enriched, 'form_id'),
                        form_type=get_enriched_value(enriched, 'form_type'),
                        sla_start=get_enriched_value(enriched, 'sla_start'),
                        sla_stop=get_enriched_value(enriched, 'sla_stop'),
                        sla_duration=get_enriched_value(enriched, 'sla_duration'),
                        qlog_id=get_enriched_value(enriched, 'qlog_id'),
                        qlog_branch=get_enriched_value(enriched, 'qlog_branch'),
                        qlog_type=get_enriched_value(enriched, 'qlog_type'),
                        qlog_time_in=get_enriched_value(enriched, 'qlog_time_in'),
                        qlog_time_call=get_enriched_value(enriched, 'qlog_time_call'),
                        qlog_sla_status=get_enriched_value(enriched, 'qlog_sla_status'),
                        appt_branch=get_enriched_value(enriched, 'appt_branch'),
                        appt_status=get_enriched_value(enriched, 'appt_status'),
                    )
                    session.add(card)
                    cards_imported += 1

                    # Commit in batches to avoid timeout
                    if cards_imported % BATCH_SIZE == 0:
                        session.flush()

                # Import from Sheet 3 (bad cards) with Sheet 13 enrichment
                for _, row in bad_cards_df.iterrows():
                    appt_id = str(row.get('appointment_id', '')) if pd.notna(row.get('appointment_id')) else None
                    serial = str(row.get('serial_number', '')) if pd.notna(row.get('serial_number')) else None
                    # Use serial_number for lookup
                    enriched = sheet13_lookup.get(serial) if serial else None

                    card = Card(
                        report_id=report.id,
                        appointment_id=appt_id,
                        branch_code=str(row.get('branch_code', '')) if pd.notna(row.get('branch_code')) else None,
                        branch_name=str(row.get('branch_name', '')) if pd.notna(row.get('branch_name')) else None,
                        region=str(row.get('region', '')) if pd.notna(row.get('region')) else None,
                        card_id=str(row.get('card_id', '')) if pd.notna(row.get('card_id')) else None,
                        serial_number=str(row.get('serial_number', '')) if pd.notna(row.get('serial_number')) else None,
                        print_status='B',
                        reject_type=str(row.get('reject_reason', '')) if pd.notna(row.get('reject_reason')) else None,
                        operator=str(row.get('operator', '')) if pd.notna(row.get('operator')) else None,
                        print_date=parser.parse_date_value(row.get('print_date'), report_month),
                        # Enriched from Sheet 13
                        form_id=get_enriched_value(enriched, 'form_id'),
                        form_type=get_enriched_value(enriched, 'form_type'),
                        sla_start=get_enriched_value(enriched, 'sla_start'),
                        sla_stop=get_enriched_value(enriched, 'sla_stop'),
                        sla_duration=get_enriched_value(enriched, 'sla_duration'),
                        qlog_id=get_enriched_value(enriched, 'qlog_id'),
                        qlog_type=get_enriched_value(enriched, 'qlog_type'),
                        qlog_sla_status=get_enriched_value(enriched, 'qlog_sla_status'),
                    )
                    session.add(card)
                    cards_imported += 1

                    # Commit in batches to avoid timeout
                    if cards_imported % BATCH_SIZE == 0:
                        session.flush()

            else:
                # Import from Sheet 13 (all data) - preferred source with full details
                for _, row in all_data.iterrows():
                    # Safe float conversion for sla_minutes
                    sla_val = row.get('sla_minutes')
                    try:
                        sla_minutes = float(sla_val) if pd.notna(sla_val) else None
                    except (ValueError, TypeError):
                        sla_minutes = None

                    # Calculate sla_over_12min if not in data
                    sla_over_12 = row.get('sla_over_12min')
                    if pd.isna(sla_over_12) and sla_minutes is not None:
                        sla_over_12 = sla_minutes > 12
                    else:
                        sla_over_12 = bool(sla_over_12) if pd.notna(sla_over_12) else False

                    card = Card(
                        report_id=report.id,
                        appointment_id=str(row.get('appointment_id', '')) if pd.notna(row.get('appointment_id')) else None,
                        form_id=str(row.get('form_id', '')) if pd.notna(row.get('form_id')) else None,
                        form_type=str(row.get('form_type', '')) if pd.notna(row.get('form_type')) else None,
                        branch_code=str(row.get('branch_code', '')) if pd.notna(row.get('branch_code')) else None,
                        branch_name=str(row.get('branch_name', '')) if pd.notna(row.get('branch_name')) else None,
                        region=str(row.get('region', '')) if pd.notna(row.get('region')) else None,
                        card_id=str(row.get('card_id', '')) if pd.notna(row.get('card_id')) else None,
                        work_permit_no=str(row.get('work_permit_no', '')) if pd.notna(row.get('work_permit_no')) else None,
                        serial_number=str(row.get('serial_number', '')) if pd.notna(row.get('serial_number')) else None,
                        print_status=str(row.get('print_status', '')) if pd.notna(row.get('print_status')) else None,
                        reject_type=str(row.get('reject_type', '')) if pd.notna(row.get('reject_type')) else None,
                        operator=str(row.get('operator', '')) if pd.notna(row.get('operator')) else None,
                        print_date=parser.parse_date_value(row.get('print_date'), report_month),
                        sla_start=str(row.get('sla_start', '')) if pd.notna(row.get('sla_start')) else None,
                        sla_stop=str(row.get('sla_stop', '')) if pd.notna(row.get('sla_stop')) else None,
                        sla_duration=str(row.get('sla_duration', '')) if pd.notna(row.get('sla_duration')) else None,
                        sla_minutes=sla_minutes,
                        qlog_id=str(row.get('qlog_id', '')) if pd.notna(row.get('qlog_id')) else None,
                        qlog_branch=str(row.get('qlog_branch', '')) if pd.notna(row.get('qlog_branch')) else None,
                        qlog_date=parser.parse_date_value(row.get('qlog_date'), report_month),
                        qlog_queue_no=float(row.get('qlog_queue_no')) if pd.notna(row.get('qlog_queue_no')) else None,
                        qlog_type=str(row.get('qlog_type', '')) if pd.notna(row.get('qlog_type')) else None,
                        qlog_time_in=str(row.get('qlog_time_in', '')) if pd.notna(row.get('qlog_time_in')) else None,
                        qlog_time_call=str(row.get('qlog_time_call', '')) if pd.notna(row.get('qlog_time_call')) else None,
                        wait_time_minutes=float(row.get('wait_time_minutes')) if pd.notna(row.get('wait_time_minutes')) else None,
                        wait_time_hms=str(row.get('wait_time_hms', '')) if pd.notna(row.get('wait_time_hms')) else None,
                        qlog_sla_status=str(row.get('qlog_sla_status', '')) if pd.notna(row.get('qlog_sla_status')) else None,
                        appt_date=parser.parse_date_value(row.get('appt_date'), report_month),
                        appt_branch=str(row.get('appt_branch', '')) if pd.notna(row.get('appt_branch')) else None,
                        appt_status=str(row.get('appt_status', '')) if pd.notna(row.get('appt_status')) else None,
                        wrong_date=bool(row.get('wrong_date')) if pd.notna(row.get('wrong_date')) else False,
                        wrong_branch=bool(row.get('wrong_branch')) if pd.notna(row.get('wrong_branch')) else False,
                        is_mobile_unit=bool(row.get('is_mobile_unit')) if pd.notna(row.get('is_mobile_unit')) else False,
                        is_ob_center=bool(row.get('is_ob_center')) if pd.notna(row.get('is_ob_center')) else False,
                        old_appointment=bool(row.get('old_appointment')) if pd.notna(row.get('old_appointment')) else False,
                        sla_over_12min=sla_over_12,
                        is_valid_sla_status=bool(row.get('is_valid_sla_status')) if pd.notna(row.get('is_valid_sla_status')) else True,
                        wait_over_1hour=bool(row.get('wait_over_1hour')) if pd.notna(row.get('wait_over_1hour')) else False,
                        emergency=bool(row.get('emergency')) if pd.notna(row.get('emergency')) else False,
                    )
                    session.add(card)
                    cards_imported += 1

                    # Commit in batches to avoid timeout
                    if cards_imported % BATCH_SIZE == 0:
                        session.flush()

            # Import to BadCard table (separate table for bad cards summary)
            bad_imported = 0
            for _, row in bad_cards_df.iterrows():
                bad_card = BadCard(
                    report_id=report.id,
                    appointment_id=str(row.get('appointment_id', '')) if pd.notna(row.get('appointment_id')) else None,
                    branch_code=str(row.get('branch_code', '')) if pd.notna(row.get('branch_code')) else None,
                    branch_name=str(row.get('branch_name', '')) if pd.notna(row.get('branch_name')) else None,
                    region=str(row.get('region', '')) if pd.notna(row.get('region')) else None,
                    card_id=str(row.get('card_id', '')) if pd.notna(row.get('card_id')) else None,
                    serial_number=str(row.get('serial_number', '')) if pd.notna(row.get('serial_number')) else None,
                    reject_reason=str(row.get('reject_reason', '')) if pd.notna(row.get('reject_reason')) else None,
                    operator=str(row.get('operator', '')) if pd.notna(row.get('operator')) else None,
                    print_date=parser.parse_date_value(row.get('print_date'), report_month),
                )
                session.add(bad_card)
                bad_imported += 1

            # Import center stats (Sheet 4)
            center_stats_df = parser.parse_center_stats()
            centers_imported = 0
            for _, row in center_stats_df.iterrows():
                # Safe conversion for good_count
                good_count_val = row.get('good_count', 0)
                if pd.notna(good_count_val):
                    try:
                        good_count = int(float(good_count_val))
                    except (ValueError, TypeError):
                        good_count = 0
                else:
                    good_count = 0

                # Safe conversion for SLA values
                avg_sla_val = row.get('avg_sla')
                try:
                    avg_sla = float(avg_sla_val) if pd.notna(avg_sla_val) else None
                except (ValueError, TypeError):
                    avg_sla = None

                max_sla_val = row.get('max_sla')
                try:
                    max_sla = float(max_sla_val) if pd.notna(max_sla_val) else None
                except (ValueError, TypeError):
                    max_sla = None

                center_stat = CenterStat(
                    report_id=report.id,
                    branch_code=str(row.get('branch_code', '')) if pd.notna(row.get('branch_code')) else None,
                    branch_name=str(row.get('branch_name', '')) if pd.notna(row.get('branch_name')) else None,
                    good_count=good_count,
                    avg_sla=avg_sla,
                    max_sla=max_sla,
                )
                session.add(center_stat)
                centers_imported += 1

            # Import SLA anomalies (Sheet 6)
            sla_over_df = parser.parse_sla_over_12()
            sla_imported = 0
            for _, row in sla_over_df.iterrows():
                anomaly = AnomalySLA(
                    report_id=report.id,
                    appointment_id=str(row.get('appointment_id', '')) if pd.notna(row.get('appointment_id')) else None,
                    branch_code=str(row.get('branch_code', '')) if pd.notna(row.get('branch_code')) else None,
                    branch_name=str(row.get('branch_name', '')) if pd.notna(row.get('branch_name')) else None,
                    serial_number=str(row.get('serial_number', '')) if pd.notna(row.get('serial_number')) else None,
                    sla_minutes=float(row.get('sla_minutes')) if pd.notna(row.get('sla_minutes')) else None,
                    operator=str(row.get('operator', '')) if pd.notna(row.get('operator')) else None,
                    print_date=parser.parse_date_value(row.get('print_date'), report_month),
                )
                session.add(anomaly)
                sla_imported += 1

            # Import wrong center (Sheet 9)
            wrong_center_df = parser.parse_wrong_center()
            wrong_imported = 0
            for _, row in wrong_center_df.iterrows():
                wrong = WrongCenter(
                    report_id=report.id,
                    appointment_id=str(row.get('appointment_id', '')) if pd.notna(row.get('appointment_id')) else None,
                    expected_branch=str(row.get('expected_branch', '')) if pd.notna(row.get('expected_branch')) else None,
                    actual_branch=str(row.get('actual_branch', '')) if pd.notna(row.get('actual_branch')) else None,
                    serial_number=str(row.get('serial_number', '')) if pd.notna(row.get('serial_number')) else None,
                    status=str(row.get('status', '')) if pd.notna(row.get('status')) else None,
                    print_date=parser.parse_date_value(row.get('print_date'), report_month),
                )
                session.add(wrong)
                wrong_imported += 1

            # Import complete diff (Sheet 22) - Appt ID with G > 1
            complete_diff_df = parser.parse_complete_diff()
            diff_imported = 0
            for _, row in complete_diff_df.iterrows():
                diff = CompleteDiff(
                    report_id=report.id,
                    appointment_id=str(row.get('appointment_id', '')) if pd.notna(row.get('appointment_id')) else None,
                    g_count=int(row.get('g_count')) if pd.notna(row.get('g_count')) else None,
                    branch_code=str(row.get('branch_code', '')) if pd.notna(row.get('branch_code')) else None,
                    branch_name=str(row.get('branch_name', '')) if pd.notna(row.get('branch_name')) else None,
                    region=str(row.get('region', '')) if pd.notna(row.get('region')) else None,
                    card_id=str(row.get('card_id', '')) if pd.notna(row.get('card_id')) else None,
                    serial_number=str(row.get('serial_number', '')) if pd.notna(row.get('serial_number')) else None,
                    work_permit_no=str(row.get('work_permit_no', '')) if pd.notna(row.get('work_permit_no')) else None,
                    sla_minutes=float(row.get('sla_minutes')) if pd.notna(row.get('sla_minutes')) else None,
                    operator=str(row.get('operator', '')) if pd.notna(row.get('operator')) else None,
                    print_date=parser.parse_date_value(row.get('print_date'), report_month),
                )
                session.add(diff)
                diff_imported += 1

            # Import delivery cards (Sheet 7)
            delivery_df = parser.parse_delivery_cards()
            delivery_imported = 0
            for _, row in delivery_df.iterrows():
                delivery = DeliveryCard(
                    report_id=report.id,
                    appointment_id=str(row.get('appointment_id', '')) if pd.notna(row.get('appointment_id')) else None,
                    serial_number=str(row.get('serial_number', '')) if pd.notna(row.get('serial_number')) else None,
                    print_status=str(row.get('print_status', '')) if pd.notna(row.get('print_status')) else None,
                    card_id=str(row.get('card_id', '')) if pd.notna(row.get('card_id')) else None,
                    work_permit_no=str(row.get('work_permit_no', '')) if pd.notna(row.get('work_permit_no')) else None,
                )
                session.add(delivery)
                delivery_imported += 1

            # Determine data source description
            if use_sheet_13_only:
                data_source = 'Sheet 13 (Full Details)'
            elif len(sheet13_lookup) > 0:
                data_source = f'Sheet 2+3 (Enriched with {len(sheet13_lookup)} records from Sheet 13)'
            else:
                data_source = 'Sheet 2+3 (Basic)'

            return {
                'report_id': report.id,
                'filename': filename,
                'report_date': report_date,
                'cards_imported': cards_imported,
                'bad_cards_imported': bad_imported,
                'centers_imported': centers_imported,
                'sla_anomalies_imported': sla_imported,
                'wrong_center_imported': wrong_imported,
                'complete_diff_imported': diff_imported,
                'delivery_imported': delivery_imported,
                'total_good': total_good,
                'total_bad': total_bad,
                'data_source': data_source,
            }

    @staticmethod
    def get_reports(session: Session) -> List[Report]:
        """Get all reports."""
        return session.query(Report).order_by(desc(Report.report_date)).all()

    @staticmethod
    def get_report_dates(session: Session) -> List[date]:
        """Get all unique report dates."""
        results = session.query(Report.report_date).distinct().order_by(desc(Report.report_date)).all()
        return [r[0] for r in results]

    @staticmethod
    def search_cards(
        session: Session,
        search_term: str = None,
        branch_code: str = None,
        start_date: date = None,
        end_date: date = None,
        print_status: str = None,
        limit: int = 1000
    ) -> List[Card]:
        """Search cards with various filters."""
        query = session.query(Card)

        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    Card.appointment_id.ilike(search_pattern),
                    Card.card_id.ilike(search_pattern),
                    Card.serial_number.ilike(search_pattern),
                    Card.work_permit_no.ilike(search_pattern),
                )
            )

        if branch_code:
            query = query.filter(Card.branch_code == branch_code)

        if start_date:
            query = query.filter(Card.print_date >= start_date)

        if end_date:
            query = query.filter(Card.print_date <= end_date)

        if print_status:
            query = query.filter(Card.print_status == print_status)

        return query.order_by(desc(Card.print_date)).limit(limit).all()

    @staticmethod
    def get_overview_stats(
        session: Session,
        start_date: date = None,
        end_date: date = None
    ) -> Dict[str, Any]:
        """Get overview statistics."""
        query = session.query(Card)

        if start_date:
            query = query.filter(Card.print_date >= start_date)
        if end_date:
            query = query.filter(Card.print_date <= end_date)

        total = query.count()
        good = query.filter(Card.print_status == 'G').count()
        bad = query.filter(Card.print_status == 'B').count()

        # Average SLA
        avg_sla = session.query(func.avg(Card.sla_minutes)).filter(
            Card.print_status == 'G'
        )
        if start_date:
            avg_sla = avg_sla.filter(Card.print_date >= start_date)
        if end_date:
            avg_sla = avg_sla.filter(Card.print_date <= end_date)
        avg_sla_result = avg_sla.scalar() or 0

        # SLA over 12 minutes
        sla_over_12 = query.filter(Card.sla_over_12min == True).count()

        # Wrong branch
        wrong_branch = query.filter(Card.wrong_branch == True).count()

        # Calculate good_rate from printed cards only (G + B)
        printed_total = good + bad

        return {
            'total': total,
            'good': good,
            'bad': bad,
            'printed_total': printed_total,
            'avg_sla': round(avg_sla_result, 2),
            'sla_over_12': sla_over_12,
            'wrong_branch': wrong_branch,
            'good_rate': round(good / printed_total * 100, 2) if printed_total > 0 else 0,
        }

    @staticmethod
    def get_center_stats(
        session: Session,
        start_date: date = None,
        end_date: date = None
    ) -> pd.DataFrame:
        """Get statistics by center."""
        query = session.query(
            Card.branch_code,
            Card.branch_name,
            func.count(Card.id).label('total'),
            func.sum(func.cast(Card.print_status == 'G', Integer)).label('good_count'),
            func.avg(Card.sla_minutes).label('avg_sla'),
            func.max(Card.sla_minutes).label('max_sla'),
        ).filter(Card.branch_code.isnot(None))

        if start_date:
            query = query.filter(Card.print_date >= start_date)
        if end_date:
            query = query.filter(Card.print_date <= end_date)

        results = query.group_by(Card.branch_code, Card.branch_name).all()

        data = []
        for r in results:
            data.append({
                'branch_code': r.branch_code,
                'branch_name': r.branch_name,
                'total': r.total,
                'good_count': r.good_count or 0,
                'avg_sla': round(r.avg_sla or 0, 2),
                'max_sla': round(r.max_sla or 0, 2),
            })

        return pd.DataFrame(data)

    @staticmethod
    def get_daily_trend(
        session: Session,
        start_date: date = None,
        end_date: date = None
    ) -> pd.DataFrame:
        """Get daily trend data."""
        query = session.query(
            Card.print_date,
            func.count(Card.id).label('total'),
            func.sum(func.cast(Card.print_status == 'G', Integer)).label('good'),
            func.sum(func.cast(Card.print_status == 'B', Integer)).label('bad'),
        ).filter(Card.print_date.isnot(None))

        if start_date:
            query = query.filter(Card.print_date >= start_date)
        if end_date:
            query = query.filter(Card.print_date <= end_date)

        results = query.group_by(Card.print_date).order_by(Card.print_date).all()

        data = []
        for r in results:
            data.append({
                'date': r.print_date,
                'total': r.total,
                'good': r.good or 0,
                'bad': r.bad or 0,
            })

        return pd.DataFrame(data)

    @staticmethod
    def get_branch_list(session: Session) -> List[str]:
        """Get list of all branch codes."""
        results = session.query(Card.branch_code).distinct().filter(
            Card.branch_code.isnot(None)
        ).order_by(Card.branch_code).all()
        return [r[0] for r in results]


# Import Integer for sum casting
from sqlalchemy import Integer
