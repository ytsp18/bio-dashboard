"""Excel file parser for Bio Unified Report."""
import pandas as pd
from datetime import datetime, date
from typing import Dict, List, Any, Optional
import re


class ExcelParser:
    """Parse Bio Unified Report Excel files."""

    SHEET_NAMES = {
        'summary': '1.สรุปภาพรวม',
        'good_cards': '2.รายการบัตรดี',
        'bad_cards': '3.รายการบัตรเสีย',
        'by_center': '4.สรุปตามศูนย์',
        'by_region': '5.สรุปตามภูมิภาค',
        'sla_over_12': '6.SLA เกิน 12 นาที',
        'wait_over_1hr': '6.5.SLA รอคิวเกิน 1 ชม.',
        'delivery': '7.บัตรจัดส่ง',
        'multi_card': '8.ออกบัตรหลายใบ',
        'wrong_center': '9.ออกบัตรผิดศูนย์',
        'wrong_date': '10.นัดหมายผิดวัน',
        'duplicate_serial': '11.Serial ซ้ำ',
        'all_data': '13.ข้อมูลทั้งหมด',
        'validation': '14.ตรวจสอบความถูกต้อง',
        'anomaly_sla': '15.Anomaly SLA Time',
        'after_midnight': '16.ออกบัตรเกินเที่ยงคืน',
        'reissue': '17.Reissue(มีB)',
        'card_sn_diff': '18.ผลต่างCardID-SN',
        'anomaly_g_more_1': '19.AnomalyG>1',
        'appt_g_more_1': '20.ApptID_G>1',
        'complete_cards': '21.บัตรสมบูรณ์',
        'complete_diff': '22.ส่วนต่างบัตรสมบูรณ์',
        'g_more_1': '20.ApptID_G>1',  # Alias
    }

    def __init__(self, file_path: str):
        """Initialize parser with file path."""
        self.file_path = file_path
        self.excel_file = None
        self._sheets_cache = {}

    def load(self):
        """Load the Excel file."""
        self.excel_file = pd.ExcelFile(self.file_path)
        return self

    def get_sheet_names(self) -> List[str]:
        """Get all sheet names in the file."""
        if self.excel_file is None:
            self.load()
        return self.excel_file.sheet_names

    def read_sheet(self, sheet_name: str, skip_rows: int = 0) -> pd.DataFrame:
        """Read a specific sheet."""
        if sheet_name in self._sheets_cache:
            return self._sheets_cache[sheet_name]

        if self.excel_file is None:
            self.load()

        if sheet_name in self.excel_file.sheet_names:
            df = pd.read_excel(
                self.excel_file,
                sheet_name=sheet_name,
                skiprows=skip_rows
            )
            self._sheets_cache[sheet_name] = df
            return df
        return pd.DataFrame()

    def extract_report_date(self) -> Optional[date]:
        """Extract report date from filename or content."""
        # Try to extract from filename
        # Pattern: Bio_unified_report_27_01_2569 or Bio_unified_report_ตุลาคม_2568
        # Use _original_filename if set (for temp files with original name stored)
        filename = getattr(self, '_original_filename', None) or self.file_path.split('/')[-1]

        # Pattern for daily report: DD_MM_YYYY
        daily_match = re.search(r'(\d{2})_(\d{2})_(\d{4})', filename)
        if daily_match:
            day, month, year = daily_match.groups()
            # Convert Buddhist year to Gregorian
            greg_year = int(year) - 543
            return date(greg_year, int(month), int(day))

        # Pattern for monthly report: เดือน_ปี
        month_map = {
            'มกราคม': 1, 'กุมภาพันธ์': 2, 'มีนาคม': 3, 'เมษายน': 4,
            'พฤษภาคม': 5, 'มิถุนายน': 6, 'กรกฎาคม': 7, 'สิงหาคม': 8,
            'กันยายน': 9, 'ตุลาคม': 10, 'พฤศจิกายน': 11, 'ธันวาคม': 12
        }
        for thai_month, month_num in month_map.items():
            if thai_month in filename:
                year_match = re.search(r'(\d{4})', filename)
                if year_match:
                    year = int(year_match.group(1))
                    greg_year = year - 543 if year > 2500 else year
                    return date(greg_year, month_num, 1)

        return date.today()

    def parse_all_data(self) -> pd.DataFrame:
        """Parse Sheet 13.ข้อมูลทั้งหมด."""
        df = self.read_sheet(self.SHEET_NAMES['all_data'])
        if df.empty:
            return df

        # Column mapping - support both formats (space and underscore)
        # Format 1: Daily reports use spaces (e.g., "Appointment ID")
        # Format 2: Monthly reports use underscores (e.g., "Appointment_ID")
        column_map = {
            # Row numbers
            '#': 'row_num',
            '#.1': 'row_num2',

            # Appointment ID (both formats)
            'Appointment ID': 'appointment_id',
            'Appointment_ID': 'appointment_id',

            # Form info
            'Form ID': 'form_id',
            'Form_ID': 'form_id',
            'Form Type': 'form_type',
            'Form_Type': 'form_type',

            # Branch info
            'Branch Code': 'branch_code',
            'Branch_Code': 'branch_code',
            'Branch Name': 'branch_name',
            'Branch_Name': 'branch_name',
            'Region': 'region',

            # Card info
            'Card ID': 'card_id',
            'Card_ID': 'card_id',
            'Work Permit No': 'work_permit_no',
            'Work_Permit_No': 'work_permit_no',
            'Serial Number': 'serial_number',
            'Serial_Number': 'serial_number',

            # Print info
            'Print Status': 'print_status',
            'Print_Status': 'print_status',
            'Reject Type': 'reject_type',
            'Reject_Type': 'reject_type',
            'OS ID': 'operator',
            'OS_ID': 'operator',
            'Print Date': 'print_date',
            'Print_Date': 'print_date',

            # SLA info
            'SLA Start': 'sla_start',
            'SLA_Start': 'sla_start',
            'SLA Stop': 'sla_stop',
            'SLA_Stop': 'sla_stop',
            'SLA Duration': 'sla_duration',
            'SLA_Duration': 'sla_duration',
            'SLA Confirm Type': 'sla_confirm_type',
            'SLA_Confirm_Type': 'sla_confirm_type',
            'BIO_SLA_Minutes': 'sla_minutes',
            'SLA_Minutes': 'sla_minutes',
            'SLA Minutes': 'sla_minutes',

            # Queue info
            'Qlog_ID': 'qlog_id',
            'Qlog ID': 'qlog_id',
            'Qlog_Branch': 'qlog_branch',
            'Qlog Branch': 'qlog_branch',
            'Qlog_Date': 'qlog_date',
            'Qlog Date': 'qlog_date',
            'Qlog_Queue_No': 'qlog_queue_no',
            'Qlog Queue No': 'qlog_queue_no',
            'Qlog_Type': 'qlog_type',
            'Qlog Type': 'qlog_type',
            'Qlog_TimeIn': 'qlog_time_in',
            'Qlog TimeIn': 'qlog_time_in',
            'Qlog_TimeCall': 'qlog_time_call',
            'Qlog TimeCall': 'qlog_time_call',
            'Qlog_Train_Time': 'qlog_train_time',
            'Wait_Time_Minutes': 'wait_time_minutes',
            'Wait Time Minutes': 'wait_time_minutes',
            'Wait_Time_HMS': 'wait_time_hms',
            'Wait Time HMS': 'wait_time_hms',
            'Qlog_SLA_Status': 'qlog_sla_status',
            'Qlog SLA Status': 'qlog_sla_status',
            'Qlog_SLA_TimeStart': 'qlog_sla_time_start',
            'Qlog_SLA_TimeEnd': 'qlog_sla_time_end',

            # Appointment info
            'Appt_ID': 'appt_id',
            'Appt ID': 'appt_id',
            'Appt_Date': 'appt_date',
            'Appt Date': 'appt_date',
            'Appt_Branch': 'appt_branch',
            'Appt Branch': 'appt_branch',
            'Appt_Status': 'appt_status',
            'Appt Status': 'appt_status',

            # Flags
            'Wrong_Date': 'wrong_date',
            'Wrong Date': 'wrong_date',
            'Wrong_Branch': 'wrong_branch',
            'Wrong Branch': 'wrong_branch',
            'Is_Mobile_Unit': 'is_mobile_unit',
            'Is Mobile Unit': 'is_mobile_unit',
            'Is_OB_Center': 'is_ob_center',
            'Is OB Center': 'is_ob_center',
            'Old_Appointment': 'old_appointment',
            'Old Appointment': 'old_appointment',
            'SLA_Over_12Min': 'sla_over_12min',
            'SLA Over 12Min': 'sla_over_12min',
            'Is_Valid_SLA_Status': 'is_valid_sla_status',
            'Is Valid SLA Status': 'is_valid_sla_status',
            'Wait_Over_1Hour': 'wait_over_1hour',
            'Wait Over 1Hour': 'wait_over_1hour',
            'Emergency': 'emergency',
        }

        # Rename columns that exist
        rename_dict = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename_dict)

        # Fix Serial Number and Work Permit - preserve leading zeros
        # These are stored as float in Excel, need to convert to string with proper format
        if 'serial_number' in df.columns:
            df['serial_number'] = df['serial_number'].apply(self._format_serial_number)
        if 'work_permit_no' in df.columns:
            df['work_permit_no'] = df['work_permit_no'].apply(self._format_work_permit)
        if 'card_id' in df.columns:
            df['card_id'] = df['card_id'].apply(self._format_card_id)

        return df

    def _format_serial_number(self, value) -> Optional[str]:
        """Format serial number - typically 13 digits with leading zeros."""
        if pd.isna(value):
            return None
        # Convert to string without decimal
        if isinstance(value, float):
            value = str(int(value))
        else:
            value = str(value).split('.')[0]  # Remove any decimal part
        # Pad with leading zeros if needed (standard length is 13)
        if len(value) < 13:
            value = value.zfill(13)
        return value

    def _format_work_permit(self, value) -> Optional[str]:
        """Format work permit number - typically 13 digits with leading zeros."""
        if pd.isna(value):
            return None
        # Convert to string without decimal
        if isinstance(value, float):
            value = str(int(value))
        else:
            value = str(value).split('.')[0]
        # Pad with leading zeros if needed (standard length is 13)
        if len(value) < 13:
            value = value.zfill(13)
        return value

    def _format_card_id(self, value) -> Optional[str]:
        """Format card ID - typically 13 digits."""
        if pd.isna(value):
            return None
        # Convert to string without decimal
        if isinstance(value, float):
            value = str(int(value))
        else:
            value = str(value).split('.')[0]
        # Pad with leading zeros if needed (standard length is 13)
        if len(value) < 13:
            value = value.zfill(13)
        return value

    def parse_good_cards(self) -> pd.DataFrame:
        """Parse Sheet 2.รายการบัตรดี."""
        df = self.read_sheet(self.SHEET_NAMES['good_cards'])
        if df.empty or len(df) == 0:
            return pd.DataFrame()

        # Expected columns
        expected_cols = [
            'ลำดับ', 'Appointment ID', 'รหัสศูนย์', 'ชื่อศูนย์', 'ภูมิภาค',
            'Card ID', 'Serial Number', 'Work Permit No', 'SLA (นาที)',
            'ผ่าน SLA', 'ผู้ให้บริการ', 'วันที่พิมพ์'
        ]

        # Map to standard names
        column_map = {
            'Appointment ID': 'appointment_id',
            'รหัสศูนย์': 'branch_code',
            'ชื่อศูนย์': 'branch_name',
            'ภูมิภาค': 'region',
            'Card ID': 'card_id',
            'Serial Number': 'serial_number',
            'Work Permit No': 'work_permit_no',
            'SLA (นาที)': 'sla_minutes',
            'ผ่าน SLA': 'sla_pass',
            'ผู้ให้บริการ': 'operator',
            'วันที่พิมพ์': 'print_date',
        }

        rename_dict = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename_dict)

        # Fix Serial Number, Work Permit, and Card ID - preserve leading zeros
        if 'serial_number' in df.columns:
            df['serial_number'] = df['serial_number'].apply(self._format_serial_number)
        if 'work_permit_no' in df.columns:
            df['work_permit_no'] = df['work_permit_no'].apply(self._format_work_permit)
        if 'card_id' in df.columns:
            df['card_id'] = df['card_id'].apply(self._format_card_id)

        return df

    def parse_bad_cards(self) -> pd.DataFrame:
        """Parse Sheet 3.รายการบัตรเสีย."""
        df = self.read_sheet(self.SHEET_NAMES['bad_cards'])
        if df.empty or len(df) == 0:
            return pd.DataFrame()

        column_map = {
            'Appointment ID': 'appointment_id',
            'รหัสศูนย์': 'branch_code',
            'ชื่อศูนย์': 'branch_name',
            'ภูมิภาค': 'region',
            'Card ID': 'card_id',
            'Serial Number': 'serial_number',
            'สาเหตุ': 'reject_reason',
            'ผู้ให้บริการ': 'operator',
            'วันที่พิมพ์': 'print_date',
        }

        rename_dict = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename_dict)

        # Fix Serial Number and Card ID - preserve leading zeros
        if 'serial_number' in df.columns:
            df['serial_number'] = df['serial_number'].apply(self._format_serial_number)
        if 'card_id' in df.columns:
            df['card_id'] = df['card_id'].apply(self._format_card_id)

        return df

    def parse_center_stats(self) -> pd.DataFrame:
        """Parse Sheet 4.สรุปตามศูนย์."""
        df = self.read_sheet(self.SHEET_NAMES['by_center'])
        if df.empty or len(df) == 0:
            return pd.DataFrame()

        # Column mapping - support both formats (with/without region column)
        column_map = {
            'รหัสศูนย์': 'branch_code',
            'ชื่อศูนย์': 'branch_name',
            'ภูมิภาค': 'region',
            'จำนวนบัตรดี': 'good_count',
            'SLA เฉลี่ย': 'avg_sla',
            'SLA สูงสุด': 'max_sla',
        }

        rename_dict = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename_dict)

        # Ensure good_count is numeric - handle cases where columns shifted
        if 'good_count' in df.columns:
            # Try to convert, if fails it means column order is wrong
            try:
                df['good_count'] = pd.to_numeric(df['good_count'], errors='coerce')
            except:
                pass

            # If good_count contains non-numeric after conversion, try to fix
            if df['good_count'].isna().all() or df['good_count'].dtype == object:
                # Check if region column has numeric values (columns shifted)
                if 'region' in df.columns:
                    try:
                        test_vals = pd.to_numeric(df['region'], errors='coerce')
                        if test_vals.notna().any():
                            # Columns are shifted - region has the count
                            df['good_count'] = test_vals
                            # Find actual region in good_count column
                            df['region'] = df['good_count'].apply(
                                lambda x: x if isinstance(x, str) else None
                            )
                    except:
                        pass

        # Ensure numeric columns
        for col in ['good_count', 'avg_sla', 'max_sla']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Fill NaN in good_count with 0
        if 'good_count' in df.columns:
            df['good_count'] = df['good_count'].fillna(0).astype(int)

        return df

    def parse_delivery_cards(self) -> pd.DataFrame:
        """Parse Sheet 7.บัตรจัดส่ง - Delivery cards."""
        df = self.read_sheet(self.SHEET_NAMES['delivery'])
        if df.empty or len(df) < 2:
            return pd.DataFrame()

        # Sheet has title row, then header row
        # Row 0: title (e.g., "รายการบัตรจัดส่ง (จำนวน 18 รายการ)")
        # Row 1: column headers (ลำดับ, Appointment ID, Serial Number, สถานะ, ...)
        # Row 2+: data

        # Find header row containing 'ลำดับ'
        header_row_idx = None
        for i in range(min(5, len(df))):  # Check first 5 rows
            row = df.iloc[i]
            first_val = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
            if first_val == 'ลำดับ':
                header_row_idx = i
                break

        if header_row_idx is None:
            return pd.DataFrame()

        # Set column names from header row
        header_row = df.iloc[header_row_idx]
        new_columns = [str(c).strip() if pd.notna(c) else f'col_{i}' for i, c in enumerate(header_row)]

        # Get data rows
        data_df = df.iloc[header_row_idx + 1:].copy()
        data_df.columns = new_columns
        data_df = data_df.reset_index(drop=True)

        # Filter out empty rows
        if 'ลำดับ' in data_df.columns:
            data_df = data_df[pd.to_numeric(data_df['ลำดับ'], errors='coerce').notna()]

        if len(data_df) == 0:
            return pd.DataFrame()

        column_map = {
            'ลำดับ': 'row_num',
            'Appointment ID': 'appointment_id',
            'Serial Number': 'serial_number',
            'สถานะ': 'print_status',
            'Card ID': 'card_id',
            'Work Permit No': 'work_permit_no',
        }

        rename_dict = {k: v for k, v in column_map.items() if k in data_df.columns}
        data_df = data_df.rename(columns=rename_dict)

        # Fix Serial Number format
        if 'serial_number' in data_df.columns:
            data_df['serial_number'] = data_df['serial_number'].apply(self._format_serial_number)

        # Mark as delivery
        data_df['is_delivery'] = True

        return data_df

    def parse_sla_over_12(self) -> pd.DataFrame:
        """Parse Sheet 6.SLA เกิน 12 นาที."""
        df = self.read_sheet(self.SHEET_NAMES['sla_over_12'])
        if df.empty or len(df) < 2:
            return pd.DataFrame()

        # Sheet has header row, need to skip it
        # First row is title, second is column headers
        df.columns = df.iloc[1].tolist()
        df = df.iloc[2:].reset_index(drop=True)

        if 'ลำดับ' not in df.columns:
            return pd.DataFrame()

        column_map = {
            'Appointment ID': 'appointment_id',
            'รหัสศูนย์': 'branch_code',
            'ชื่อศูนย์': 'branch_name',
            'Serial Number': 'serial_number',
            'SLA (นาที)': 'sla_minutes',
            'ผู้ให้บริการ': 'operator',
            'วันที่พิมพ์': 'print_date',
        }

        rename_dict = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename_dict)

        return df

    def parse_wrong_center(self) -> pd.DataFrame:
        """Parse Sheet 9.ออกบัตรผิดศูนย์."""
        df = self.read_sheet(self.SHEET_NAMES['wrong_center'])
        if df.empty or len(df) < 2:
            return pd.DataFrame()

        # Sheet has header row
        df.columns = df.iloc[1].tolist()
        df = df.iloc[2:].reset_index(drop=True)

        if 'ลำดับ' not in df.columns:
            return pd.DataFrame()

        column_map = {
            'Appointment ID': 'appointment_id',
            'ศูนย์ที่นัด': 'expected_branch',
            'ศูนย์ที่ออกบัตร': 'actual_branch',
            'Serial Number': 'serial_number',
            'สถานะ': 'status',
            'วันที่พิมพ์': 'print_date',
        }

        rename_dict = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename_dict)

        return df

    def parse_complete_diff(self) -> pd.DataFrame:
        """Parse Sheet 22.ส่วนต่างบัตรสมบูรณ์ - Appt ID with G > 1.

        This sheet has summary info at the top, and detail data below.
        The detail section starts with a row containing 'ลำดับ' header.
        If no detail section exists (no diff data), returns empty DataFrame.
        """
        df = self.read_sheet(self.SHEET_NAMES['complete_diff'])
        if df.empty:
            return pd.DataFrame()

        # Find the data section header row containing 'ลำดับ'
        # Search through all rows to find the header row
        header_row_idx = None
        for i in range(len(df)):
            row = df.iloc[i]
            first_val = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
            if first_val == 'ลำดับ':
                header_row_idx = i
                break

        if header_row_idx is None:
            # No detail section found - this means no diff data
            return pd.DataFrame()

        # Set column names from the header row
        header_row = df.iloc[header_row_idx]
        new_columns = [str(c).strip() if pd.notna(c) else f'col_{i}' for i, c in enumerate(header_row)]

        # Get data rows (after header)
        data_df = df.iloc[header_row_idx + 1:].copy()
        data_df.columns = new_columns
        data_df = data_df.reset_index(drop=True)

        # Filter out rows where first column is not numeric (summary/empty rows)
        if 'ลำดับ' in data_df.columns:
            data_df = data_df[pd.to_numeric(data_df['ลำดับ'], errors='coerce').notna()]

        if len(data_df) == 0:
            return pd.DataFrame()

        column_map = {
            'ลำดับ': 'row_num',
            'Appointment ID': 'appointment_id',
            'จำนวน G': 'g_count',
            'รหัสศูนย์': 'branch_code',
            'ชื่อศูนย์': 'branch_name',
            'ภูมิภาค': 'region',
            'Card ID': 'card_id',
            'Serial Number': 'serial_number',
            'Work Permit No': 'work_permit_no',
            'SLA (นาที)': 'sla_minutes',
            'ผู้ให้บริการ': 'operator',
            'วันที่พิมพ์': 'print_date',
        }

        rename_dict = {k: v for k, v in column_map.items() if k in data_df.columns}
        data_df = data_df.rename(columns=rename_dict)

        # Convert numeric columns
        if 'g_count' in data_df.columns:
            data_df['g_count'] = pd.to_numeric(data_df['g_count'], errors='coerce')
        if 'sla_minutes' in data_df.columns:
            data_df['sla_minutes'] = pd.to_numeric(data_df['sla_minutes'], errors='coerce')

        return data_df

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics from Sheet 1 Summary or calculate from data."""
        # Default values
        total = 0
        good = 0
        bad = 0
        good_pickup = 0
        good_delivery = 0
        unique_serial_g = 0

        # Try to read from Sheet 1 Summary first
        try:
            summary_df = self.read_sheet('1.สรุปภาพรวม')
            if not summary_df.empty:
                for idx, row in summary_df.iterrows():
                    cell = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
                    value = row.iloc[1] if len(row) > 1 else None

                    if 'จำนวนทั้งหมด' in cell and 'BIO' in cell and pd.notna(value):
                        try:
                            total = int(str(value).replace(',', ''))
                        except:
                            pass
                    elif 'G (บัตรดี) - รับที่ศูนย์' in cell and pd.notna(value):
                        try:
                            good_pickup = int(str(value).replace(',', ''))
                        except:
                            pass
                    elif 'G (บัตรดี) - จัดส่ง' in cell and pd.notna(value):
                        try:
                            good_delivery = int(str(value).replace(',', ''))
                        except:
                            pass
                    elif 'G (บัตรดี) - รวม' in cell and pd.notna(value):
                        try:
                            good = int(str(value).replace(',', ''))
                        except:
                            pass
                    elif 'รวม Unique Serial Number (G)' in cell and pd.notna(value):
                        try:
                            unique_serial_g = int(str(value).replace(',', ''))
                        except:
                            pass
                    elif unique_serial_g == 0 and 'G (บัตรดี) - Unique Serial' in cell and pd.notna(value):
                        # Fallback: use this if "รวม Unique Serial Number (G)" not found
                        try:
                            unique_serial_g = int(str(value).replace(',', ''))
                        except:
                            pass
                    elif 'B (บัตรเสีย) - รวม' in cell and pd.notna(value):
                        try:
                            bad = int(str(value).replace(',', ''))
                        except:
                            pass

                if total > 0 or good > 0 or bad > 0:
                    return {
                        'total_records': total,
                        'good_cards': good,
                        'bad_cards': bad,
                        'good_pickup': good_pickup,
                        'good_delivery': good_delivery,
                        'unique_serial_g': unique_serial_g,
                    }
        except:
            pass

        # Fallback: calculate from data sheets
        all_data = self.parse_all_data()
        good_cards_df = self.parse_good_cards()
        bad_cards_df = self.parse_bad_cards()
        delivery_df = self.parse_delivery_cards()

        # Calculate from Sheet 13
        total_from_all = len(all_data) if not all_data.empty else 0
        good_from_all = len(all_data[all_data['print_status'] == 'G']) if not all_data.empty and 'print_status' in all_data.columns else 0
        bad_from_all = len(all_data[all_data['print_status'] == 'B']) if not all_data.empty and 'print_status' in all_data.columns else 0

        # Calculate from Sheet 2+3+7 (include delivery)
        good_from_sheets = len(good_cards_df) if not good_cards_df.empty else 0
        bad_from_sheets = len(bad_cards_df) if not bad_cards_df.empty else 0

        # Add delivery cards (G status)
        delivery_good = 0
        if not delivery_df.empty and 'print_status' in delivery_df.columns:
            delivery_good = len(delivery_df[delivery_df['print_status'] == 'G'])

        good_total = good_from_sheets + delivery_good
        total_from_sheets = good_total + bad_from_sheets

        # Calculate unique serial
        all_serials = []
        if not good_cards_df.empty and 'serial_number' in good_cards_df.columns:
            all_serials.extend(good_cards_df['serial_number'].dropna().tolist())
        if not delivery_df.empty and 'serial_number' in delivery_df.columns:
            delivery_g = delivery_df[delivery_df.get('print_status', '') == 'G'] if 'print_status' in delivery_df.columns else delivery_df
            all_serials.extend(delivery_g['serial_number'].dropna().tolist())
        unique_serial_calc = len(set(all_serials))

        # Use the source with more data
        if total_from_all >= total_from_sheets:
            return {
                'total_records': total_from_all,
                'good_cards': good_from_all,
                'bad_cards': bad_from_all,
                'good_pickup': good_from_all,
                'good_delivery': 0,
                'unique_serial_g': unique_serial_calc,
            }
        else:
            return {
                'total_records': total_from_sheets,
                'good_cards': good_total,
                'bad_cards': bad_from_sheets,
                'good_pickup': good_from_sheets,
                'good_delivery': delivery_good,
                'unique_serial_g': unique_serial_calc,
            }

    def parse_date_value(self, value, report_month: int = None) -> Optional[date]:
        """Parse date from various formats.

        Args:
            value: The date value to parse
            report_month: The expected month from the report (e.g., 11 for November)
                          Used to detect and correct day/month swap issues
        """
        if pd.isna(value):
            return None

        if isinstance(value, (datetime, date)):
            result_date = value.date() if isinstance(value, datetime) else value

            # Check for day/month swap issue
            # If we have a report_month and the date's month doesn't match,
            # but the day equals the expected month, they might be swapped
            if report_month is not None:
                if result_date.month != report_month and result_date.day == report_month:
                    # Day and month appear to be swapped
                    # Only swap if the result would be valid (day <= 12)
                    if result_date.month <= 12:
                        try:
                            # Swap day and month
                            corrected = date(result_date.year, result_date.day, result_date.month)
                            return corrected
                        except ValueError:
                            pass  # Invalid date after swap, use original

            return result_date

        if isinstance(value, str):
            # Try DD-MM-YYYY format
            try:
                parts = value.split('-')
                if len(parts) == 3:
                    day, month, year = parts
                    return date(int(year), int(month), int(day))
            except:
                pass

            # Try other formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                try:
                    return datetime.strptime(value, fmt).date()
                except:
                    pass

        return None
