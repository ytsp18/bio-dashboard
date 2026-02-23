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
    def _copy_df_to_table(session, table_name, df, columns):
        """Bulk insert DataFrame using PostgreSQL COPY protocol (5-10x faster than ORM).
        Falls back to pandas to_sql for SQLite."""
        from database.connection import is_sqlite
        from io import StringIO

        if len(df) == 0:
            return 0

        # Ensure only requested columns, fill missing with None
        copy_df = pd.DataFrame()
        for col in columns:
            if col in df.columns:
                copy_df[col] = df[col]
            else:
                copy_df[col] = None

        # Replace nan/None text artifacts
        copy_df = copy_df.replace({'nan': None, 'None': None, '': None})

        if is_sqlite:
            # Use executemany via the session's own connection to avoid SQLite lock
            placeholders = ', '.join(['?'] * len(columns))
            cols_str = ', '.join(columns)
            sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
            raw_conn = session.connection().connection
            cursor = raw_conn.cursor()
            # Convert DataFrame to list of tuples, replacing NaN/pd.NA with None
            # Also convert pandas nullable types (Int64, boolean) to Python native
            def to_native(val):
                if pd.isna(val):
                    return None
                if hasattr(val, 'item'):  # numpy/pandas scalar
                    return val.item()
                return val
            records = [[to_native(v) for v in row] for row in copy_df.values]
            for i in range(0, len(records), 5000):
                cursor.executemany(sql, records[i:i+5000])
        else:
            conn = session.connection().connection
            cursor = conn.cursor()
            buffer = StringIO()
            copy_df.to_csv(buffer, index=False, header=False, na_rep='\\N')
            buffer.seek(0)
            cols_str = ', '.join(columns)
            cursor.copy_expert(
                f"COPY {table_name} ({cols_str}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')",
                buffer
            )
        return len(copy_df)

    @staticmethod
    def import_excel(file_path: str, original_filename: str = None, progress_callback=None) -> Dict[str, Any]:
        """Import data from Excel file to database using COPY protocol.

        Args:
            file_path: Path to the Excel file (can be temp file)
            original_filename: Original filename if different from file_path
            progress_callback: Optional callable(pct: int, msg: str) for progress updates
        """
        def _progress(pct, msg):
            if progress_callback:
                progress_callback(pct, msg)

        parser = ExcelParser(file_path)
        parser.load()

        # Extract report date - use original filename if provided
        if original_filename:
            parser._original_filename = original_filename
        report_date = parser.extract_report_date()
        report_month = report_date.month if report_date else None
        filename = original_filename if original_filename else file_path.split('/')[-1]

        _progress(5, "กำลังอ่านข้อมูลจาก Excel...")

        # Parse all data sources
        good_cards_df = parser.parse_good_cards()
        bad_cards_df = parser.parse_bad_cards()
        all_data = parser.parse_all_data()

        _progress(15, "กำลังวิเคราะห์ข้อมูล...")

        # Get summary stats from Excel (most accurate source)
        summary_stats = parser.get_summary_stats()

        # Determine which data source to use
        total_from_sheets = len(good_cards_df) + len(bad_cards_df)
        total_from_all = len(all_data)

        if total_from_all > 0 and total_from_sheets > 0:
            ratio = total_from_all / total_from_sheets
            use_sheet_13_only = ratio >= 0.8
        elif total_from_all > 0:
            use_sheet_13_only = True
        else:
            use_sheet_13_only = False

        # Build Sheet 13 lookup for enrichment (monthly reports)
        sheet13_lookup = {}
        if not use_sheet_13_only and total_from_all > 0:
            sheet13_indexed = all_data.set_index('serial_number', drop=False) if 'serial_number' in all_data.columns else pd.DataFrame()
            # De-duplicate index (keep first)
            if not sheet13_indexed.empty:
                sheet13_indexed = sheet13_indexed[~sheet13_indexed.index.duplicated(keep='first')]

        # Determine totals
        if summary_stats.get('good_cards', 0) > 0 or summary_stats.get('bad_cards', 0) > 0:
            total_good = summary_stats.get('good_cards', 0)
            total_bad = summary_stats.get('bad_cards', 0)
            total_records = summary_stats.get('total_records', 0)
        elif use_sheet_13_only:
            if 'print_status' in all_data.columns:
                total_good = len(all_data[all_data['print_status'] == 'G'])
                total_bad = len(all_data[all_data['print_status'] == 'B'])
            else:
                total_good = 0
                total_bad = 0
            total_records = total_from_all
        else:
            total_good = len(good_cards_df)
            total_bad = len(bad_cards_df)
            total_records = total_from_sheets

        _progress(20, "กำลังเตรียมนำเข้าฐานข้อมูล...")

        with session_scope() as session:
            # Check if report already exists
            existing = session.query(Report).filter(Report.filename == filename).first()
            if existing:
                session.delete(existing)
                session.flush()

            # Create report record (ORM - only 1 row)
            report = Report(
                filename=filename,
                report_date=report_date,
                total_good=total_good,
                total_bad=total_bad,
                total_records=total_records,
            )
            session.add(report)
            session.flush()
            report_id = report.id

            # --- Helper: safe string conversion ---
            def safe_str(val):
                return str(val) if pd.notna(val) else None

            def safe_float(val):
                try:
                    return float(val) if pd.notna(val) else None
                except (ValueError, TypeError):
                    return None

            def safe_int(val):
                try:
                    return int(float(val)) if pd.notna(val) else None
                except (ValueError, TypeError):
                    return None

            def safe_bool(val, default=False):
                if pd.notna(val):
                    return bool(val)
                return default

            def parse_date_col(series):
                """Convert date column using parser.parse_date_value."""
                return series.apply(lambda v: parser.parse_date_value(v, report_month))

            # --- Helper: enrich from Sheet 13 ---
            def enrich_column(df, col_name, sheet13_idx):
                """Merge a column from Sheet 13 into df based on serial_number."""
                if sheet13_idx.empty or col_name not in sheet13_idx.columns or 'serial_number' not in df.columns:
                    return pd.Series([None] * len(df), index=df.index)
                merged = df[['serial_number']].merge(
                    sheet13_idx[[col_name]],
                    left_on='serial_number', right_index=True, how='left'
                )
                return merged[col_name].apply(safe_str)

            # ==================== CARDS TABLE ====================
            _progress(25, f"กำลังเตรียม cards ({total_from_sheets:,} รายการ)...")

            cards_columns = [
                'report_id', 'appointment_id', 'form_id', 'form_type', 'branch_code',
                'branch_name', 'region', 'card_id', 'work_permit_no', 'serial_number',
                'print_status', 'reject_type', 'operator', 'print_date', 'sla_start',
                'sla_stop', 'sla_duration', 'sla_minutes', 'sla_over_12min',
                'qlog_id', 'qlog_branch', 'qlog_date', 'qlog_queue_no', 'qlog_type',
                'qlog_time_in', 'qlog_time_call', 'wait_time_minutes', 'wait_time_hms',
                'qlog_sla_status', 'appt_date', 'appt_branch', 'appt_status',
                'wrong_date', 'wrong_branch', 'is_mobile_unit', 'is_ob_center',
                'old_appointment', 'is_valid_sla_status', 'wait_over_1hour', 'emergency',
            ]

            if use_sheet_13_only:
                # Build cards_df directly from Sheet 13
                cards_df = pd.DataFrame()

                str_cols = ['appointment_id', 'form_id', 'form_type', 'branch_code', 'branch_name',
                            'region', 'card_id', 'work_permit_no', 'serial_number', 'print_status',
                            'reject_type', 'operator', 'sla_start', 'sla_stop', 'sla_duration',
                            'qlog_id', 'qlog_branch', 'qlog_type', 'qlog_time_in', 'qlog_time_call',
                            'wait_time_hms', 'qlog_sla_status', 'appt_branch', 'appt_status']
                for col in str_cols:
                    cards_df[col] = all_data[col].apply(safe_str) if col in all_data.columns else None

                # Float columns
                cards_df['sla_minutes'] = all_data['sla_minutes'].apply(safe_float) if 'sla_minutes' in all_data.columns else None
                cards_df['qlog_queue_no'] = all_data['qlog_queue_no'].apply(safe_float) if 'qlog_queue_no' in all_data.columns else None
                cards_df['wait_time_minutes'] = all_data['wait_time_minutes'].apply(safe_float) if 'wait_time_minutes' in all_data.columns else None

                # Date columns
                cards_df['print_date'] = parse_date_col(all_data['print_date']) if 'print_date' in all_data.columns else None
                cards_df['qlog_date'] = parse_date_col(all_data['qlog_date']) if 'qlog_date' in all_data.columns else None
                cards_df['appt_date'] = parse_date_col(all_data['appt_date']) if 'appt_date' in all_data.columns else None

                # Boolean columns
                bool_cols = {'wrong_date': False, 'wrong_branch': False, 'is_mobile_unit': False,
                             'is_ob_center': False, 'old_appointment': False, 'is_valid_sla_status': True,
                             'wait_over_1hour': False, 'emergency': False}
                for col, default in bool_cols.items():
                    if col in all_data.columns:
                        cards_df[col] = all_data[col].apply(lambda v: safe_bool(v, default))
                    else:
                        cards_df[col] = default

                # sla_over_12min: calculate from sla_minutes if not in data
                if 'sla_over_12min' in all_data.columns:
                    cards_df['sla_over_12min'] = all_data.apply(
                        lambda r: bool(r['sla_over_12min']) if pd.notna(r.get('sla_over_12min'))
                        else (safe_float(r.get('sla_minutes')) or 0) > 12, axis=1
                    )
                else:
                    cards_df['sla_over_12min'] = cards_df['sla_minutes'].apply(
                        lambda v: v > 12 if v is not None else False
                    )

                # Assign report_id AFTER DataFrame has rows
                cards_df['report_id'] = report_id
                cards_imported = len(cards_df)

            else:
                # Build cards from Sheet 2+3 with Sheet 13 enrichment
                # Good cards — assign Series columns first, then scalars
                good_df = pd.DataFrame()
                for col in ['appointment_id', 'branch_code', 'branch_name', 'region',
                            'card_id', 'serial_number', 'work_permit_no', 'operator']:
                    good_df[col] = good_cards_df[col].apply(safe_str) if col in good_cards_df.columns else None
                good_df['sla_minutes'] = good_cards_df['sla_minutes'].apply(safe_float) if 'sla_minutes' in good_cards_df.columns else None
                good_df['print_date'] = parse_date_col(good_cards_df['print_date']) if 'print_date' in good_cards_df.columns else None
                good_df['sla_over_12min'] = good_df['sla_minutes'].apply(lambda v: v > 12 if v is not None else False)
                good_df['print_status'] = 'G'
                good_df['reject_type'] = None

                # Enrich from Sheet 13
                for col in ['form_id', 'form_type', 'sla_start', 'sla_stop', 'sla_duration',
                            'qlog_id', 'qlog_branch', 'qlog_type', 'qlog_time_in', 'qlog_time_call',
                            'qlog_sla_status', 'appt_branch', 'appt_status']:
                    good_df[col] = enrich_column(good_df, col, sheet13_indexed) if not sheet13_indexed.empty else None

                # Bad cards — assign Series columns first, then scalars
                bad_df = pd.DataFrame()
                for col in ['appointment_id', 'branch_code', 'branch_name', 'region',
                            'card_id', 'serial_number', 'operator']:
                    bad_df[col] = bad_cards_df[col].apply(safe_str) if col in bad_cards_df.columns else None
                bad_df['reject_type'] = bad_cards_df['reject_reason'].apply(safe_str) if 'reject_reason' in bad_cards_df.columns else None
                bad_df['print_date'] = parse_date_col(bad_cards_df['print_date']) if 'print_date' in bad_cards_df.columns else None
                bad_df['print_status'] = 'B'

                # Enrich from Sheet 13
                for col in ['form_id', 'form_type', 'sla_start', 'sla_stop', 'sla_duration',
                            'qlog_id', 'qlog_type', 'qlog_sla_status']:
                    bad_df[col] = enrich_column(bad_df, col, sheet13_indexed) if not sheet13_indexed.empty else None

                cards_df = pd.concat([good_df, bad_df], ignore_index=True)
                # Assign report_id AFTER concat so DataFrame already has rows
                cards_df['report_id'] = report_id
                cards_imported = len(cards_df)

            _progress(35, f"กำลังนำเข้า cards ({cards_imported:,} รายการ)...")
            DataService._copy_df_to_table(session, 'cards', cards_df, cards_columns)

            # ==================== BAD_CARDS TABLE ====================
            _progress(55, f"กำลังนำเข้า bad_cards ({len(bad_cards_df):,} รายการ)...")
            bad_copy = pd.DataFrame()
            for col in ['appointment_id', 'branch_code', 'branch_name', 'region', 'card_id', 'serial_number', 'operator']:
                bad_copy[col] = bad_cards_df[col].apply(safe_str) if col in bad_cards_df.columns else None
            bad_copy['reject_reason'] = bad_cards_df['reject_reason'].apply(safe_str) if 'reject_reason' in bad_cards_df.columns else None
            bad_copy['print_date'] = parse_date_col(bad_cards_df['print_date']) if 'print_date' in bad_cards_df.columns else None
            bad_copy['report_id'] = report_id
            bad_imported = DataService._copy_df_to_table(session, 'bad_cards', bad_copy,
                ['report_id', 'appointment_id', 'branch_code', 'branch_name', 'region',
                 'card_id', 'serial_number', 'reject_reason', 'operator', 'print_date'])

            # ==================== CENTER_STATS TABLE ====================
            _progress(60, "กำลังนำเข้า center_stats...")
            center_stats_df = parser.parse_center_stats()
            cs_copy = pd.DataFrame()
            for col in ['branch_code', 'branch_name']:
                cs_copy[col] = center_stats_df[col].apply(safe_str) if col in center_stats_df.columns else None
            cs_copy['good_count'] = pd.to_numeric(center_stats_df['good_count'], errors='coerce').astype('Int64') if 'good_count' in center_stats_df.columns else 0
            cs_copy['avg_sla'] = center_stats_df['avg_sla'].apply(safe_float) if 'avg_sla' in center_stats_df.columns else None
            cs_copy['max_sla'] = center_stats_df['max_sla'].apply(safe_float) if 'max_sla' in center_stats_df.columns else None
            cs_copy['report_id'] = report_id
            centers_imported = DataService._copy_df_to_table(session, 'center_stats', cs_copy,
                ['report_id', 'branch_code', 'branch_name', 'good_count', 'avg_sla', 'max_sla'])

            # ==================== ANOMALY_SLA TABLE ====================
            _progress(65, "กำลังนำเข้า SLA anomalies...")
            sla_over_df = parser.parse_sla_over_12()
            sla_copy = pd.DataFrame()
            for col in ['appointment_id', 'branch_code', 'branch_name', 'serial_number', 'operator']:
                sla_copy[col] = sla_over_df[col].apply(safe_str) if col in sla_over_df.columns else None
            sla_copy['sla_minutes'] = sla_over_df['sla_minutes'].apply(safe_float) if 'sla_minutes' in sla_over_df.columns else None
            sla_copy['print_date'] = parse_date_col(sla_over_df['print_date']) if 'print_date' in sla_over_df.columns else None
            sla_copy['report_id'] = report_id
            sla_imported = DataService._copy_df_to_table(session, 'anomaly_sla', sla_copy,
                ['report_id', 'appointment_id', 'branch_code', 'branch_name', 'serial_number',
                 'sla_minutes', 'operator', 'print_date'])

            # ==================== WRONG_CENTERS TABLE ====================
            _progress(70, "กำลังนำเข้า wrong_centers...")
            wrong_center_df = parser.parse_wrong_center()
            wc_copy = pd.DataFrame()
            for col in ['appointment_id', 'expected_branch', 'actual_branch', 'serial_number', 'status']:
                wc_copy[col] = wrong_center_df[col].apply(safe_str) if col in wrong_center_df.columns else None
            wc_copy['print_date'] = parse_date_col(wrong_center_df['print_date']) if 'print_date' in wrong_center_df.columns else None
            wc_copy['report_id'] = report_id
            wrong_imported = DataService._copy_df_to_table(session, 'wrong_centers', wc_copy,
                ['report_id', 'appointment_id', 'expected_branch', 'actual_branch', 'serial_number',
                 'status', 'print_date'])

            # ==================== COMPLETE_DIFFS TABLE ====================
            _progress(75, "กำลังนำเข้า complete_diffs...")
            complete_diff_df = parser.parse_complete_diff()
            cd_copy = pd.DataFrame()
            for col in ['appointment_id', 'branch_code', 'branch_name', 'region', 'card_id',
                         'serial_number', 'work_permit_no', 'operator']:
                cd_copy[col] = complete_diff_df[col].apply(safe_str) if col in complete_diff_df.columns else None
            cd_copy['g_count'] = pd.to_numeric(complete_diff_df['g_count'], errors='coerce').astype('Int64') if 'g_count' in complete_diff_df.columns else None
            cd_copy['sla_minutes'] = complete_diff_df['sla_minutes'].apply(safe_float) if 'sla_minutes' in complete_diff_df.columns else None
            cd_copy['print_date'] = parse_date_col(complete_diff_df['print_date']) if 'print_date' in complete_diff_df.columns else None
            cd_copy['report_id'] = report_id
            diff_imported = DataService._copy_df_to_table(session, 'complete_diffs', cd_copy,
                ['report_id', 'appointment_id', 'g_count', 'branch_code', 'branch_name', 'region',
                 'card_id', 'serial_number', 'work_permit_no', 'sla_minutes', 'operator', 'print_date'])

            # ==================== DELIVERY_CARDS TABLE ====================
            _progress(80, "กำลังนำเข้า delivery_cards...")
            delivery_df = parser.parse_delivery_cards()
            dl_copy = pd.DataFrame()
            for col in ['appointment_id', 'serial_number', 'print_status', 'card_id', 'work_permit_no']:
                dl_copy[col] = delivery_df[col].apply(safe_str) if col in delivery_df.columns else None
            dl_copy['report_id'] = report_id
            delivery_imported = DataService._copy_df_to_table(session, 'delivery_cards', dl_copy,
                ['report_id', 'appointment_id', 'serial_number', 'print_status', 'card_id', 'work_permit_no'])

            _progress(95, "กำลังบันทึกข้อมูล...")

            # Determine data source description
            if use_sheet_13_only:
                data_source = 'Sheet 13 (Full Details)'
            elif not sheet13_indexed.empty:
                data_source = f'Sheet 2+3 (Enriched with {len(sheet13_indexed)} records from Sheet 13)'
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
