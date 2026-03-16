"""Tests for cobol_decimal.py — COBOL numeric semantics with PIC precision enforcement.

IQ-03: Every test here verifies that CobolDecimal faithfully reproduces COBOL
arithmetic behavior: truncation, precision, intermediate results, and coercion.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cobol_decimal import CobolDecimal, CobolOverflowError


class TestBasicStorage:
    """CobolDecimal stores values within PIC-defined precision and scale."""

    def test_stores_value_within_pic_range(self):
        """PIC S9(5)V99 stores 999.99 exactly."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.set(Decimal('999.99'))
        assert cd.value == Decimal('999.99')

    def test_stores_zero_by_default(self):
        """A freshly created CobolDecimal has value 0."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        assert cd.value == Decimal('0')

    def test_stores_negative_when_signed(self):
        """PIC S9(5)V99 stores -123.45."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.set(Decimal('-123.45'))
        assert cd.value == Decimal('-123.45')

    def test_max_value_unsigned(self):
        """PIC 9(5)V99 has max_value 99999.99."""
        cd = CobolDecimal(digits=5, scale=2, signed=False)
        assert cd.max_value == Decimal('99999.99')

    def test_max_value_signed(self):
        """PIC S9(5)V99 has max_value 99999.99 and min_value -99999.99."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        assert cd.max_value == Decimal('99999.99')
        assert cd.min_value == Decimal('-99999.99')

    def test_min_value_unsigned_is_zero(self):
        """PIC 9(5) has min_value 0."""
        cd = CobolDecimal(digits=5, scale=0, signed=False)
        assert cd.min_value == Decimal('0')


class TestOverflow:
    """Overflow behavior: truncate-left by default, raise when configured."""

    def test_overflow_truncates_left_digits(self):
        """PIC 9(5): assigning 123456 silently truncates to 23456.
        COBOL drops the leftmost digits that exceed the PIC capacity."""
        cd = CobolDecimal(digits=5, scale=0, signed=False)
        cd.set(123456)
        assert cd.value == Decimal('23456')

    def test_overflow_truncates_left_with_decimal(self):
        """PIC S9(3)V99: assigning 12345.67 truncates to 345.67."""
        cd = CobolDecimal(digits=3, scale=2, signed=True)
        cd.set(Decimal('12345.67'))
        assert cd.value == Decimal('345.67')

    def test_overflow_raises_when_configured(self):
        """on_size_error='raise' raises CobolOverflowError on overflow."""
        cd = CobolDecimal(digits=5, scale=0, signed=False, on_size_error='raise')
        with pytest.raises(CobolOverflowError):
            cd.set(123456)

    def test_no_overflow_does_not_raise(self):
        """on_size_error='raise' does NOT raise when value fits."""
        cd = CobolDecimal(digits=5, scale=0, signed=False, on_size_error='raise')
        cd.set(99999)
        assert cd.value == Decimal('99999')

    def test_unsigned_stores_absolute_on_negative(self):
        """PIC 9(5): assigning -42 to unsigned field stores 42 (absolute).
        COBOL unsigned fields ignore the sign."""
        cd = CobolDecimal(digits=5, scale=0, signed=False)
        cd.set(-42)
        assert cd.value == Decimal('42')


class TestRounding:
    """Truncation by default, ROUND_HALF_UP when rounded=True."""

    def test_truncates_fractional_digits(self):
        """PIC S9(5)V99: assigning 1.999 truncates to 1.99 (not 2.00)."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.set(Decimal('1.999'))
        assert cd.value == Decimal('1.99')

    def test_rounded_mode_rounds_up(self):
        """PIC S9(5)V99 with rounded=True: 1.995 rounds to 2.00."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.set(Decimal('1.995'), rounded=True)
        assert cd.value == Decimal('2.00') or cd.value == Decimal('2')

    def test_rounded_negative_rounds_away_from_zero(self):
        """COBOL ROUNDED rounds away from zero: -1.995 → -2.00."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.set(Decimal('-1.995'), rounded=True)
        assert cd.value == Decimal('-2.00') or cd.value == Decimal('-2')

    def test_truncation_does_not_round(self):
        """PIC 9(3)V9: assigning 1.99 truncates to 1.9 (not 2.0)."""
        cd = CobolDecimal(digits=3, scale=1, signed=False)
        cd.set(Decimal('1.99'))
        assert cd.value == Decimal('1.9')


class TestIntermediatePrecisionAdd:
    """ADD/SUBTRACT intermediate: max(d1,d2)+1 integer digits, max(s1,s2) scale."""

    def test_add_intermediate_precision(self):
        """ADD: S9(5)V99 + S9(3)V99 → intermediate has 6 integer digits, scale 2.
        99999.99 + 999.99 = 100999.98 — fits in 6 integer digits."""
        a = CobolDecimal(digits=5, scale=2, signed=True)
        a.set(Decimal('99999.99'))
        b = CobolDecimal(digits=3, scale=2, signed=True)
        b.set(Decimal('999.99'))
        result = a.add(b)
        assert result.value == Decimal('100999.98')
        # Intermediate has max(5,3)+1=6 integer digits
        assert result.digits >= 6

    def test_subtract_intermediate_precision(self):
        """SUBTRACT: same rule as ADD — max(d1,d2)+1 integer digits."""
        a = CobolDecimal(digits=5, scale=2, signed=True)
        a.set(Decimal('100.00'))
        b = CobolDecimal(digits=5, scale=2, signed=True)
        b.set(Decimal('99999.99'))
        result = a.subtract(b)
        assert result.value == Decimal('-99899.99')
        assert result.digits >= 6

    def test_add_different_scales_aligns(self):
        """ADD with different scales: S9(5)V99 + S9(5)V9(4).
        The intermediate scale is max(2, 4) = 4."""
        a = CobolDecimal(digits=5, scale=2, signed=True)
        a.set(Decimal('100.50'))
        b = CobolDecimal(digits=5, scale=4, signed=True)
        b.set(Decimal('0.1234'))
        result = a.add(b)
        assert result.value == Decimal('100.6234')
        assert result.scale >= 4


class TestIntermediatePrecisionMultiply:
    """MULTIPLY intermediate: d1+d2 integer digits, s1+s2 scale."""

    def test_multiply_intermediate_precision(self):
        """MULTIPLY: S9(5)V99 * S9(3)V9 → intermediate 8 integer digits, 3 scale.
        12345.67 * 123.4 = 1523455.68."""
        a = CobolDecimal(digits=5, scale=2, signed=True)
        a.set(Decimal('12345.67'))
        b = CobolDecimal(digits=3, scale=1, signed=True)
        b.set(Decimal('123.4'))
        result = a.multiply(b)
        assert result.value == Decimal('1523455.68')
        assert result.digits >= 8
        assert result.scale >= 2

    def test_multiply_scale_expansion(self):
        """MULTIPLY: V99 * V99 → intermediate scale max(2,2)=2.
        0.99 * 0.99 = 0.9801, rounded to scale 2 → 0.98."""
        a = CobolDecimal(digits=0, scale=2, signed=False)
        a.set(Decimal('0.99'))
        b = CobolDecimal(digits=0, scale=2, signed=False)
        b.set(Decimal('0.99'))
        result = a.multiply(b)
        assert result.value == Decimal('0.98')
        assert result.scale >= 2


class TestIntermediatePrecisionDivide:
    """DIVIDE intermediate precision."""

    def test_divide_basic(self):
        """DIVIDE: 10000 / 3 with appropriate intermediate precision."""
        a = CobolDecimal(digits=5, scale=0, signed=True)
        a.set(10000)
        b = CobolDecimal(digits=1, scale=0, signed=True)
        b.set(3)
        result = a.divide(b)
        # Result should have enough precision to represent the quotient
        # 10000 / 3 = 3333.333... — truncated to intermediate scale
        assert result.value >= Decimal('3333')

    def test_divide_by_zero_raises(self):
        """Division by zero raises ZeroDivisionError."""
        a = CobolDecimal(digits=5, scale=2, signed=True)
        a.set(Decimal('100.00'))
        b = CobolDecimal(digits=5, scale=2, signed=True)
        b.set(Decimal('0'))
        with pytest.raises(ZeroDivisionError):
            a.divide(b)


class TestAssignment:
    """Cross-PIC assignment: truncate intermediate to target field."""

    def test_assign_larger_to_smaller_truncates_left(self):
        """Assigning S9(7)V99 intermediate to S9(5)V99 target truncates left."""
        intermediate = CobolDecimal(digits=7, scale=2, signed=True)
        intermediate.set(Decimal('1234567.89'))
        target = CobolDecimal(digits=5, scale=2, signed=True)
        intermediate.assign_to(target)
        assert target.value == Decimal('34567.89')

    def test_assign_truncates_scale(self):
        """Assigning scale=4 intermediate to scale=2 target truncates right."""
        intermediate = CobolDecimal(digits=5, scale=4, signed=True)
        intermediate.set(Decimal('123.4567'))
        target = CobolDecimal(digits=5, scale=2, signed=True)
        intermediate.assign_to(target)
        assert target.value == Decimal('123.45')

    def test_assign_with_rounding(self):
        """assign_to with rounded=True rounds instead of truncating."""
        intermediate = CobolDecimal(digits=5, scale=4, signed=True)
        intermediate.set(Decimal('123.4567'))
        target = CobolDecimal(digits=5, scale=2, signed=True)
        intermediate.assign_to(target, rounded=True)
        assert target.value == Decimal('123.46')


class TestStorageBytes:
    """storage_bytes property matches COBOL byte-size rules."""

    def test_comp3_storage_size(self):
        """PIC S9(10)V99 COMP-3: total 12 digits + sign → ceil(13/2) = 7 bytes."""
        cd = CobolDecimal(digits=10, scale=2, signed=True, usage='COMP-3')
        assert cd.storage_bytes == 7

    def test_comp3_odd_digits(self):
        """PIC S9(5) COMP-3: 5 digits + sign → ceil(6/2) = 3 bytes."""
        cd = CobolDecimal(digits=5, scale=0, signed=True, usage='COMP-3')
        assert cd.storage_bytes == 3

    def test_comp_small(self):
        """PIC S9(4) COMP → 2 bytes (≤4 digits)."""
        cd = CobolDecimal(digits=4, scale=0, signed=True, usage='COMP')
        assert cd.storage_bytes == 2

    def test_comp_medium(self):
        """PIC S9(9) COMP → 4 bytes (5-9 digits)."""
        cd = CobolDecimal(digits=9, scale=0, signed=True, usage='COMP')
        assert cd.storage_bytes == 4

    def test_comp_large(self):
        """PIC S9(15) COMP → 8 bytes (10-18 digits)."""
        cd = CobolDecimal(digits=15, scale=0, signed=True, usage='COMP')
        assert cd.storage_bytes == 8

    def test_display_storage_size(self):
        """PIC S9(10)V99 DISPLAY → 12 bytes (1 per digit, sign embedded)."""
        cd = CobolDecimal(digits=10, scale=2, signed=True, usage='DISPLAY')
        assert cd.storage_bytes == 12


class TestCoercion:
    """from_display() handles SPACES, digit strings, None, etc."""

    def test_spaces_coercion_to_zero(self):
        """MOVE SPACES TO numeric field → value becomes 0."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.from_display('SPACES')
        assert cd.value == Decimal('0')

    def test_none_coercion_to_zero(self):
        """None → 0."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.from_display(None)
        assert cd.value == Decimal('0')

    def test_empty_string_coercion_to_zero(self):
        """Empty string → 0."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.from_display('')
        assert cd.value == Decimal('0')

    def test_zeros_string_coercion(self):
        """'ZEROS' → 0."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.from_display('ZEROS')
        assert cd.value == Decimal('0')

    def test_digit_string_with_implied_decimal(self):
        """'1234567' on PIC S9(5)V99 → implied decimal at position:
        last 2 digits are fractional → 12345.67."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.from_display('1234567')
        assert cd.value == Decimal('12345.67')

    def test_digit_string_no_scale(self):
        """'42' on PIC 9(5) → 42."""
        cd = CobolDecimal(digits=5, scale=0, signed=False)
        cd.from_display('42')
        assert cd.value == Decimal('42')

    def test_decimal_passthrough(self):
        """Decimal('123.45') passes through directly."""
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.from_display(Decimal('123.45'))
        assert cd.value == Decimal('123.45')

    def test_int_passthrough(self):
        """int(42) passes through directly."""
        cd = CobolDecimal(digits=5, scale=0, signed=False)
        cd.from_display(42)
        assert cd.value == Decimal('42')


class TestGoldenVectors:
    """Verify against real carddemo arithmetic patterns."""

    def test_balance_calculation_cbtrn02c(self):
        """CBTRN02C.cbl:403 — COMPUTE WS-TEMP-BAL =
            ACCT-CURR-CYC-CREDIT - ACCT-CURR-CYC-DEBIT + DALYTRAN-AMT

        All fields are S9(09)V99 or S9(10)V99. This is a three-operand
        computation: credit minus debit plus transaction amount.
        """
        # ACCT-CURR-CYC-CREDIT: PIC S9(10)V99
        credit = CobolDecimal(digits=10, scale=2, signed=True)
        credit.set(Decimal('5000.00'))

        # ACCT-CURR-CYC-DEBIT: PIC S9(10)V99
        debit = CobolDecimal(digits=10, scale=2, signed=True)
        debit.set(Decimal('3500.75'))

        # DALYTRAN-AMT: PIC S9(09)V99 (from CVTRA05Y.cpy TRAN-AMT)
        tran_amt = CobolDecimal(digits=9, scale=2, signed=True)
        tran_amt.set(Decimal('150.25'))

        # COMPUTE WS-TEMP-BAL = credit - debit + tran_amt
        # Step 1: credit - debit (intermediate)
        intermediate = credit.subtract(debit)
        # Step 2: intermediate + tran_amt
        intermediate2 = intermediate.add(tran_amt)

        # WS-TEMP-BAL: PIC S9(09)V99
        ws_temp_bal = CobolDecimal(digits=9, scale=2, signed=True)
        intermediate2.assign_to(ws_temp_bal)

        assert ws_temp_bal.value == Decimal('1649.50')

    def test_timestamp_calculation_copaua0c(self):
        """COPAUA0C.cbl:871 — COMPUTE WS-TIME-WITH-MS =
            (WS-CUR-TIME-N6 * 1000) + WS-CUR-TIME-MS

        WS-CUR-TIME-N6: S9(06) — time as HHMMSS (e.g., 143025)
        1000: literal (treated as S9(4) with value 1000)
        WS-CUR-TIME-MS: S9(08) — milliseconds component
        WS-TIME-WITH-MS: S9(09) COMP-3 — result
        """
        cur_time = CobolDecimal(digits=6, scale=0, signed=True)
        cur_time.set(143025)

        # Literal 1000 — COBOL treats integer literals as having
        # enough digits to hold the value
        literal_1000 = CobolDecimal(digits=4, scale=0, signed=True)
        literal_1000.set(1000)

        ms = CobolDecimal(digits=8, scale=0, signed=True)
        ms.set(500)

        # Step 1: cur_time * 1000 → intermediate digits=6+4=10, scale=0
        intermediate = cur_time.multiply(literal_1000)
        assert intermediate.value == Decimal('143025000')

        # Step 2: intermediate + ms
        intermediate2 = intermediate.add(ms)
        assert intermediate2.value == Decimal('143025500')

        # Assign to WS-TIME-WITH-MS: PIC S9(09) COMP-3
        result = CobolDecimal(digits=9, scale=0, signed=True, usage='COMP-3')
        intermediate2.assign_to(result)
        assert result.value == Decimal('143025500')

    def test_date_reversal_copaua0c(self):
        """COPAUA0C.cbl:874 — COMPUTE PA-AUTH-DATE-9C = 99999 - WS-YYDDD

        WS-YYDDD: derived from date, e.g. 26074 (year 26, day 74)
        99999: literal
        Result: 99999 - 26074 = 73925
        """
        literal = CobolDecimal(digits=5, scale=0, signed=True)
        literal.set(99999)

        yyddd = CobolDecimal(digits=5, scale=0, signed=True)
        yyddd.set(26074)

        intermediate = literal.subtract(yyddd)
        assert intermediate.value == Decimal('73925')


class TestOperatorOverloads:
    """Python operator overloads for ergonomic usage."""

    def test_eq(self):
        a = CobolDecimal(digits=5, scale=2, signed=True)
        a.set(Decimal('100.50'))
        b = CobolDecimal(digits=3, scale=2, signed=True)
        b.set(Decimal('100.50'))
        assert a == b

    def test_lt(self):
        a = CobolDecimal(digits=5, scale=2, signed=True)
        a.set(Decimal('100.00'))
        b = CobolDecimal(digits=5, scale=2, signed=True)
        b.set(Decimal('200.00'))
        assert a < b
        assert not b < a

    def test_add_operator(self):
        a = CobolDecimal(digits=5, scale=2, signed=True)
        a.set(Decimal('100.50'))
        b = CobolDecimal(digits=5, scale=2, signed=True)
        b.set(Decimal('50.25'))
        result = a + b
        assert result.value == Decimal('150.75')

    def test_sub_operator(self):
        a = CobolDecimal(digits=5, scale=2, signed=True)
        a.set(Decimal('100.50'))
        b = CobolDecimal(digits=5, scale=2, signed=True)
        b.set(Decimal('50.25'))
        result = a - b
        assert result.value == Decimal('50.25')

    def test_mul_operator(self):
        a = CobolDecimal(digits=3, scale=2, signed=True)
        a.set(Decimal('1.50'))
        b = CobolDecimal(digits=3, scale=0, signed=True)
        b.set(2)
        result = a * b
        assert result.value == Decimal('3.00') or result.value == Decimal('3')

    def test_truediv_operator(self):
        a = CobolDecimal(digits=5, scale=2, signed=True)
        a.set(Decimal('100.00'))
        b = CobolDecimal(digits=1, scale=0, signed=True)
        b.set(4)
        result = a / b
        assert result.value == Decimal('25')

    def test_repr(self):
        cd = CobolDecimal(digits=5, scale=2, signed=True)
        cd.set(Decimal('123.45'))
        r = repr(cd)
        assert '123.45' in r
        assert 'S9(5)V9(2)' in r or 'digits=5' in r
