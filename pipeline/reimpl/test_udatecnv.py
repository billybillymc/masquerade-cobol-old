"""Tests for UDATECNV — date/time conversion utility.

COBOL source: test-codebases/bankdemo/sources/cobol/core/UDATECNV.cbl
Copybook:     test-codebases/bankdemo/sources/copybook/CDATED.cpy

Interface:
    convert_date(ddi_type, ddi_data, ddo_type) -> str (DDO-DATA, 20 chars, right-padded)
    convert_time(env, time_input) -> str (DD-TIME-OUTPUT, 8 chars "HH:MM:SS")

DDI-TYPE values: '0'=ISO(yyyy-mm-dd), '1'=YYYYMMDD, '2'=YYMMDD, '3'=YYDDD
DDO-TYPE values: '1'=DD.MMM.YY, '2'=DD.MMM.YYYY
"""
import pytest
from udatecnv import convert_date, convert_time


# ── Date conversion ────────────────────────────────────────────────────────────

class TestISOInput:
    def test_iso_to_dd_mmm_yy(self):
        result = convert_date('0', '2024-03-15', '1')
        assert result.rstrip() == '15.Mar.24'

    def test_iso_to_dd_mmm_yyyy(self):
        result = convert_date('0', '2024-03-15', '2')
        assert result.rstrip() == '15.Mar.2024'

    def test_iso_january(self):
        result = convert_date('0', '1999-01-01', '2')
        assert result.rstrip() == '01.Jan.1999'

    def test_iso_december(self):
        result = convert_date('0', '2000-12-31', '1')
        assert result.rstrip() == '31.Dec.00'


class TestYYYYMMDDInput:
    def test_yyyymmdd_to_dd_mmm_yy(self):
        result = convert_date('1', '20240315', '1')
        assert result.rstrip() == '15.Mar.24'

    def test_yyyymmdd_to_dd_mmm_yyyy(self):
        result = convert_date('1', '20240315', '2')
        assert result.rstrip() == '15.Mar.2024'

    def test_yyyymmdd_june(self):
        result = convert_date('1', '19851106', '2')
        assert result.rstrip() == '06.Nov.1985'


class TestYYMMDDInput:
    def test_yymmdd_to_dd_mmm_yy(self):
        result = convert_date('2', '240315', '1')
        assert result.rstrip() == '15.Mar.24'

    def test_yymmdd_to_dd_mmm_yyyy_under_50(self):
        # YY < 50 → 20xx
        result = convert_date('2', '240315', '2')
        assert result.rstrip() == '15.Mar.2024'

    def test_yymmdd_to_dd_mmm_yyyy_over_50(self):
        # YY >= 50 → 19xx
        result = convert_date('2', '851106', '2')
        assert result.rstrip() == '06.Nov.1985'

    def test_yymmdd_exactly_50(self):
        result = convert_date('2', '500601', '2')
        assert result.rstrip() == '01.Jun.1950'

    def test_yymmdd_49(self):
        result = convert_date('2', '490601', '2')
        assert result.rstrip() == '01.Jun.2049'


class TestYYDDDInput:
    def test_yyddd_day_1(self):
        # 24001 = 2024, day 1 = Jan 01
        result = convert_date('3', '24001', '2')
        assert result.rstrip() == '01.Jan.2024'

    def test_yyddd_day_31(self):
        # 24031 = 2024, day 31 = Jan 31
        result = convert_date('3', '24031', '2')
        assert result.rstrip() == '31.Jan.2024'

    def test_yyddd_day_32(self):
        # day 32 = Feb 01
        result = convert_date('3', '24032', '2')
        assert result.rstrip() == '01.Feb.2024'

    def test_yyddd_leap_year_day_60(self):
        # 2024 is a leap year; day 60 = Feb 29
        result = convert_date('3', '24060', '2')
        assert result.rstrip() == '29.Feb.2024'

    def test_yyddd_non_leap_year_day_60(self):
        # 2023 is not a leap year; day 60 = Mar 01
        result = convert_date('3', '23060', '2')
        assert result.rstrip() == '01.Mar.2023'

    def test_yyddd_to_dd_mmm_yy(self):
        result = convert_date('3', '24075', '1')
        # day 75 of 2024: Jan31+Feb29=60, +15 = Mar 15
        assert result.rstrip() == '15.Mar.24'


class TestErrorCases:
    def test_invalid_ddi_type_returns_error1(self):
        result = convert_date('9', '20240315', '1')
        assert result.rstrip() == 'ERROR1'

    def test_invalid_ddo_type_returns_error2(self):
        result = convert_date('1', '20240315', '9')
        assert result.rstrip() == 'ERROR2'


# ── Time conversion ────────────────────────────────────────────────────────────

class TestTimeConvert:
    def test_cics_env_formats_time(self):
        # CICS: MOVE PIC 9(7) → PIC 9(6) truncates the high-order digit
        # Input "1234567" → 234567 → "23:45:67"
        result = convert_time('CICS', '1234567')
        assert result == '23:45:67'

    def test_cics_env_high_digit_discarded(self):
        # High digit discarded: "0123456" → 123456 → "12:34:56"
        result = convert_time('CICS', '0123456')
        assert result == '12:34:56'

    def test_cics_midnight(self):
        result = convert_time('CICS', '0000000')
        assert result == '00:00:00'

    def test_ims_env_divides_by_10(self):
        # IMS: DIVIDE 10 INTO DD-TIME-INPUT-N GIVING WS-WORK-TIME (integer division)
        # Input "1234560" → 1234560 / 10 = 123456 → "12:34:56"
        result = convert_time('IMS ', '1234560')
        assert result == '12:34:56'

    def test_invalid_time_returns_placeholder(self):
        result = convert_time('CICS', 'ABCDEFG')
        assert result == 'hh:mm:ss'
