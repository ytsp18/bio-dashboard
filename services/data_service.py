"""Data service for database operations."""
import pandas as pd
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session

from database.connection import session_scope, get_session, get_engine
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
        delivery_df = parser.parse_delivery_cards()

        # Get summary stats from Excel (most accurate source)
        summary_stats = parser.get_summary_stats()

        # Determine which data source to use for importing
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

        # Use summary stats from Excel (most accurate) if available
        # Otherwise calculate from data
        if summary_stats.get('good_cards', 0) > 0 or summary_stats.get('bad_cards', 0) > 0:
            total_good = summary_stats.get('good_cards', 0)
            total_bad = summary_stats.get('bad_cards', 0)
            total_records = summary_stats.get('total_records', 0)
        elif use_sheet_13_only:
            # Use Sheet 13 stats
            if 'print_status' in all_data.columns:
                total_good = len(all_data[all_data['print_status'] == 'G'])
                total_bad = len(all_data[all_data['print_status'] == 'B'])
            else:
                total_good = 0
                total_bad = 0
            total_records = total_from_all
        else:
            # Fallback: use Sheet 2+3 stats
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

            # Helper function to safely convert to string
            def safe_str(val):
                return str(val) if pd.notna(val) else None

            # Helper function to safely convert to float
            def safe_float(val):
                try:
                    return float(val) if pd.notna(val) else None
                except (ValueError, TypeError):
                    return None

            # Helper function to safely convert to bool
            def safe_bool(val, default=False):
                return bool(val) if pd.notna(val) else default

            if not use_sheet_13_only:
                # Build enrichment lookup from Sheet 13
                sheet13_df = all_data.set_index('serial_number') if 'serial_number' in all_data.columns and len(all_data) > 0 else pd.DataFrame()

                # Prepare good cards DataFrame for bulk insert
                if len(good_cards_df) > 0:
                    cards_df = good_cards_df.copy()
                    cards_df['report_id'] = report.id
                    cards_df['print_status'] = 'G'
                    cards_df['sla_minutes'] = pd.to_numeric(cards_df.get('sla_minutes'), errors='coerce')
                    cards_df['sla_over_12min'] = cards_df['sla_minutes'].apply(lambda x: x > 12 if pd.notna(x) else False)
                    cards_df['print_date'] = cards_df['print_date'].apply(lambda x: parser.parse_date_value(x, report_month))

                    # Enrich from Sheet 13 if available
                    if len(sheet13_df) > 0 and 'serial_number' in cards_df.columns:
                        for col in ['form_id', 'form_type', 'sla_start', 'sla_stop', 'sla_duration',
                                    'qlog_id', 'qlog_branch', 'qlog_type', 'qlog_time_in', 'qlog_time_call',
                                    'qlog_sla_status', 'appt_branch', 'appt_status']:
                            if col in sheet13_df.columns:
                                cards_df[col] = cards_df['serial_number'].map(sheet13_df[col])

                    # Select only needed columns and rename
                    col_mapping = {
                        'appointment_id': 'appointment_id', 'branch_code': 'branch_code',
                        'branch_name': 'branch_name', 'region': 'region', 'card_id': 'card_id',
                        'serial_number': 'serial_number', 'work_permit_no': 'work_permit_no',
                        'sla_minutes': 'sla_minutes', 'operator': 'operator', 'print_date': 'print_date',
                        'form_id': 'form_id', 'form_type': 'form_type', 'sla_start': 'sla_start',
                        'sla_stop': 'sla_stop', 'sla_duration': 'sla_duration', 'qlog_id': 'qlog_id',
                        'qlog_branch': 'qlog_branch', 'qlog_type': 'qlog_type', 'qlog_time_in': 'qlog_time_in',
                        'qlog_time_call': 'qlog_time_call', 'qlog_sla_status': 'qlog_sla_status',
                        'appt_branch': 'appt_branch', 'appt_status': 'appt_status',
                        'report_id': 'report_id', 'print_status': 'print_status', 'sla_over_12min': 'sla_over_12min'
                    }
                    import_cols = [c for c in col_mapping.keys() if c in cards_df.columns]
                    import_df = cards_df[import_cols].copy()
                    import_df = import_df.replace({pd.NA: None, pd.NaT: None, 'nan': None, 'None': None})

                    # Use pandas to_sql for fast bulk insert
                    import_df.to_sql('cards', get_engine(), if_exists='append', index=False, method='multi', chunksize=500)
                    cards_imported += len(import_df)

                # Prepare bad cards DataFrame for bulk insert
                if len(bad_cards_df) > 0:
                    cards_df = bad_cards_df.copy()
                    cards_df['report_id'] = report.id
                    cards_df['print_status'] = 'B'
                    cards_df['print_date'] = cards_df['print_date'].apply(lambda x: parser.parse_date_value(x, report_month))

                    # Rename reject_reason to reject_type
                    if 'reject_reason' in cards_df.columns:
                        cards_df['reject_type'] = cards_df['reject_reason']

                    # Enrich from Sheet 13 if available
                    if len(sheet13_df) > 0 and 'serial_number' in cards_df.columns:
                        for col in ['form_id', 'form_type', 'sla_start', 'sla_stop', 'sla_duration',
                                    'qlog_id', 'qlog_type', 'qlog_sla_status']:
                            if col in sheet13_df.columns:
                                cards_df[col] = cards_df['serial_number'].map(sheet13_df[col])

                    col_mapping = {
                        'appointment_id': 'appointment_id', 'branch_code': 'branch_code',
                        'branch_name': 'branch_name', 'region': 'region', 'card_id': 'card_id',
                        'serial_number': 'serial_number', 'reject_type': 'reject_type',
                        'operator': 'operator', 'print_date': 'print_date',
                        'form_id': 'form_id', 'form_type': 'form_type', 'sla_start': 'sla_start',
                        'sla_stop': 'sla_stop', 'sla_duration': 'sla_duration', 'qlog_id': 'qlog_id',
                        'qlog_type': 'qlog_type', 'qlog_sla_status': 'qlog_sla_status',
                        'report_id': 'report_id', 'print_status': 'print_status'
                    }
                    import_cols = [c for c in col_mapping.keys() if c in cards_df.columns]
                    import_df = cards_df[import_cols].copy()
                    import_df = import_df.replace({pd.NA: None, pd.NaT: None, 'nan': None, 'None': None})

                    import_df.to_sql('cards', get_engine(), if_exists='append', index=False, method='multi', chunksize=500)
                    cards_imported += len(import_df)

            else:
                # Import from Sheet 13 (all data) - use pandas to_sql for speed
                if len(all_data) > 0:
                    cards_df = all_data.copy()
                    cards_df['report_id'] = report.id
                    cards_df['sla_minutes'] = pd.to_numeric(cards_df.get('sla_minutes'), errors='coerce')
                    cards_df['sla_over_12min'] = cards_df['sla_minutes'].apply(lambda x: x > 12 if pd.notna(x) else False)
                    cards_df['print_date'] = cards_df['print_date'].apply(lambda x: parser.parse_date_value(x, report_month))
                    if 'qlog_date' in cards_df.columns:
                        cards_df['qlog_date'] = cards_df['qlog_date'].apply(lambda x: parser.parse_date_value(x, report_month))
                    if 'appt_date' in cards_df.columns:
                        cards_df['appt_date'] = cards_df['appt_date'].apply(lambda x: parser.parse_date_value(x, report_month))

                    # Convert boolean columns
                    bool_cols = ['wrong_date', 'wrong_branch', 'is_mobile_unit', 'is_ob_center',
                                 'old_appointment', 'is_valid_sla_status', 'wait_over_1hour', 'emergency']
                    for col in bool_cols:
                        if col in cards_df.columns:
                            cards_df[col] = cards_df[col].apply(lambda x: bool(x) if pd.notna(x) else False)

                    # Clean up NaN values
                    cards_df = cards_df.replace({pd.NA: None, pd.NaT: None, 'nan': None, 'None': None})

                    # Select columns that exist in the dataframe
                    possible_cols = ['report_id', 'appointment_id', 'form_id', 'form_type', 'branch_code',
                                     'branch_name', 'region', 'card_id', 'work_permit_no', 'serial_number',
                                     'print_status', 'reject_type', 'operator', 'print_date', 'sla_start',
                                     'sla_stop', 'sla_duration', 'sla_minutes', 'qlog_id', 'qlog_branch',
                                     'qlog_date', 'qlog_queue_no', 'qlog_type', 'qlog_time_in', 'qlog_time_call',
                                     'wait_time_minutes', 'wait_time_hms', 'qlog_sla_status', 'appt_date',
                                     'appt_branch', 'appt_status', 'wrong_date', 'wrong_branch', 'is_mobile_unit',
                                     'is_ob_center', 'old_appointment', 'sla_over_12min', 'is_valid_sla_status',
                                     'wait_over_1hour', 'emergency']
                    import_cols = [c for c in possible_cols if c in cards_df.columns]
                    import_df = cards_df[import_cols].copy()

                    import_df.to_sql('cards', get_engine(), if_exists='append', index=False, method='multi', chunksize=500)
                    cards_imported = len(import_df)

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
