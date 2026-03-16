"""
COBOL numeric semantics — fixed-point decimal with PIC precision enforcement.

Faithfully reproduces COBOL arithmetic behavior:
- Silent left-truncation on overflow (no ON SIZE ERROR)
- Truncation of fractional digits (default) or ROUND_HALF_UP (ROUNDED phrase)
- COBOL-standard intermediate precision rules for ADD/SUB/MUL/DIV
- SPACES/blank coercion to zero for MOVE semantics
- Storage byte size computation for COMP, COMP-3, DISPLAY

IQ-09 UPGRADE NOTE: When IQ-09 (Differential Test Harness) is implemented,
skeleton integration MUST be upgraded to use CobolDecimal for all numeric fields.
See specs/iq-03-cobol-numeric-semantics/spec.md DD-06 for details.
"""

import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, InvalidOperation
from functools import total_ordering
from typing import Optional, Union


class CobolOverflowError(ArithmeticError):
    """Raised when on_size_error='raise' and value exceeds PIC capacity."""
    pass


@total_ordering
class CobolDecimal:
    """Fixed-point decimal with COBOL PIC semantics.

    Enforces exact precision, scale, sign, and overflow behavior matching
    the COBOL standard.

    Args:
        digits: Integer digit capacity (count of 9s before V in PIC).
        scale: Decimal places (count of 9s after V in PIC).
        signed: True if PIC has S prefix.
        usage: Storage format — 'DISPLAY', 'COMP', 'COMP-3', 'BINARY'.
        on_size_error: 'truncate' (default, COBOL standard) or 'raise'.
    """

    __slots__ = ('digits', 'scale', 'signed', 'usage', 'on_size_error', '_value')

    def __init__(
        self,
        digits: int = 9,
        scale: int = 0,
        signed: bool = True,
        usage: str = 'DISPLAY',
        on_size_error: str = 'truncate',
    ):
        self.digits = digits
        self.scale = scale
        self.signed = signed
        self.usage = usage.upper() if usage else 'DISPLAY'
        self.on_size_error = on_size_error
        self._value = Decimal('0')

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def value(self) -> Decimal:
        return self._value

    @property
    def max_value(self) -> Decimal:
        """Maximum storable value based on PIC digits and scale."""
        int_part = Decimal('9' * self.digits) if self.digits > 0 else Decimal('0')
        if self.scale > 0:
            frac_part = Decimal('0.' + '9' * self.scale)
            return int_part + frac_part
        return int_part

    @property
    def min_value(self) -> Decimal:
        """Minimum storable value."""
        if self.signed:
            return -self.max_value
        return Decimal('0')

    @property
    def total_digits(self) -> int:
        """Total digit count (integer + fractional)."""
        return self.digits + self.scale

    @property
    def storage_bytes(self) -> int:
        """Byte size based on USAGE clause.

        Rules from COBOL standard:
        - DISPLAY: 1 byte per digit (sign embedded in last byte)
        - COMP-3 / PACKED-DECIMAL: ceil((total_digits + 1) / 2)
        - COMP / BINARY: 2 (≤4 digits), 4 (≤9), 8 (≤18)
        """
        td = self.total_digits
        usage = self.usage

        if usage in ('COMP-3', 'PACKED-DECIMAL'):
            return math.ceil((td + 1) / 2)
        elif usage in ('COMP', 'BINARY', 'COMP-4', 'COMP-5'):
            if td <= 4:
                return 2
            elif td <= 9:
                return 4
            else:
                return 8
        else:
            # DISPLAY: 1 byte per digit
            return td

    # ── Mutation ────────────────────────────────────────────────────────

    def set(
        self,
        value: Union[int, float, Decimal, str],
        rounded: bool = False,
    ) -> 'CobolDecimal':
        """Assign a value, enforcing PIC precision.

        Truncates or rounds fractional digits, then truncates left digits
        if the integer part exceeds the PIC capacity.

        Args:
            value: The value to store.
            rounded: If True, use ROUND_HALF_UP (COBOL ROUNDED phrase).
                     If False, truncate toward zero (COBOL default).
        Returns:
            self, for chaining.
        """
        d = Decimal(str(value))

        # Unsigned fields: take absolute value
        if not self.signed:
            d = abs(d)

        self._value = self._truncate_to_pic(d, rounded=rounded)
        return self

    def from_display(
        self,
        raw: Union[str, int, float, Decimal, None],
    ) -> 'CobolDecimal':
        """Coerce a display value into this field.

        Handles COBOL MOVE semantics:
        - SPACES / None / empty → 0
        - ZEROS → 0
        - Digit string → parse with implied decimal at scale position
        - Numeric types → direct conversion
        """
        if raw is None:
            self._value = Decimal('0')
            return self

        if isinstance(raw, (int, float)):
            return self.set(raw)

        if isinstance(raw, Decimal):
            return self.set(raw)

        # String handling
        s = str(raw).strip().upper()

        if s in ('', 'SPACES', 'SPACE', 'ZEROS', 'ZEROES', 'ZERO'):
            self._value = Decimal('0')
            return self

        # Digit string with implied decimal point
        # For PIC S9(5)V99, '1234567' → 12345.67 (last `scale` digits are fractional)
        s_clean = s.lstrip('+-')
        is_negative = s.startswith('-')

        if s_clean.isdigit() and self.scale > 0 and '.' not in s:
            # Implied decimal: last `scale` digits are fractional
            if len(s_clean) > self.scale:
                int_part = s_clean[:-self.scale]
                frac_part = s_clean[-self.scale:]
            else:
                int_part = '0'
                frac_part = s_clean.zfill(self.scale)
            d = Decimal(f"{int_part}.{frac_part}")
            if is_negative:
                d = -d
            return self.set(d)

        # Try parsing as a number directly
        try:
            return self.set(Decimal(s))
        except InvalidOperation:
            # Unparseable → zero (COBOL MOVE of non-numeric to numeric)
            self._value = Decimal('0')
            return self

    # ── Arithmetic (COBOL intermediate precision rules) ─────────────────

    def add(self, other: 'CobolDecimal') -> 'CobolDecimal':
        """ADD with COBOL intermediate precision.

        Intermediate: max(d1,d2)+1 integer digits, max(s1,s2) scale.
        """
        int_digits = max(self.digits, other.digits) + 1
        int_scale = max(self.scale, other.scale)
        result = CobolDecimal(digits=int_digits, scale=int_scale, signed=True)
        raw = self._value + other._value
        result._value = result._truncate_to_pic(raw)
        return result

    def subtract(self, other: 'CobolDecimal') -> 'CobolDecimal':
        """SUBTRACT with COBOL intermediate precision.

        Intermediate: max(d1,d2)+1 integer digits, max(s1,s2) scale.
        """
        int_digits = max(self.digits, other.digits) + 1
        int_scale = max(self.scale, other.scale)
        result = CobolDecimal(digits=int_digits, scale=int_scale, signed=True)
        raw = self._value - other._value
        result._value = result._truncate_to_pic(raw)
        return result

    def multiply(self, other: 'CobolDecimal') -> 'CobolDecimal':
        """MULTIPLY with COBOL intermediate precision.

        Intermediate integer digits: d1 + d2 (enough room for the product).
        Intermediate scale: max(s1, s2) — the COBOL standard specifies s1+s2
        as the theoretical maximum, but actual implementations truncate the
        intermediate to the receiving field's scale. Since the intermediate
        has no receiving field yet, we use the more precise operand's scale,
        which matches the result you'd get assigning into a field with that
        scale.
        """
        int_digits = self.digits + other.digits
        int_scale = max(self.scale, other.scale)
        result = CobolDecimal(digits=int_digits, scale=int_scale, signed=True)
        raw = self._value * other._value
        result._value = result._truncate_to_pic(raw, rounded=True)
        return result

    def divide(self, other: 'CobolDecimal') -> 'CobolDecimal':
        """DIVIDE with COBOL intermediate precision.

        Intermediate precision is implementation-defined in the COBOL standard.
        We use a conservative upper bound:
          integer digits = d1 + s2 + max(s1, s2)
          scale = max(s1, s2) + dividend scale
        This ensures the quotient has enough room for exact representation
        up to the receiving field's precision.
        """
        if other._value == 0:
            raise ZeroDivisionError("COBOL DIVIDE by zero")

        max_scale = max(self.scale, other.scale)
        int_digits = self.digits + other.scale + max_scale
        int_scale = max_scale + self.scale

        # Ensure minimum reasonable precision
        int_digits = max(int_digits, self.digits)
        int_scale = max(int_scale, self.scale)

        result = CobolDecimal(digits=int_digits, scale=int_scale, signed=True)
        raw = self._value / other._value
        result._value = result._truncate_to_pic(raw)
        return result

    def assign_to(
        self,
        target: 'CobolDecimal',
        rounded: bool = False,
    ) -> 'CobolDecimal':
        """Assign this value to a target CobolDecimal, truncating to target's PIC.

        This is the final step of a COBOL COMPUTE: the intermediate result
        is truncated (or rounded) to fit the receiving field.
        """
        target.set(self._value, rounded=rounded)
        return target

    # ── Internal ────────────────────────────────────────────────────────

    def _truncate_to_pic(self, d: Decimal, rounded: bool = False) -> Decimal:
        """Truncate a Decimal to fit this field's PIC definition.

        1. Truncate (or round) fractional digits to `self.scale`
        2. If integer part exceeds `self.digits`, truncate leftmost digits
        3. If on_size_error='raise', raise instead of truncating left
        """
        sign = Decimal('-1') if d < 0 else Decimal('1')
        abs_d = abs(d)

        # Step 1: Handle fractional digits
        if self.scale >= 0:
            quantize_exp = Decimal(10) ** -self.scale
            if rounded:
                abs_d = abs_d.quantize(quantize_exp, rounding=ROUND_HALF_UP)
            else:
                abs_d = abs_d.quantize(quantize_exp, rounding=ROUND_DOWN)

        # Step 2: Check integer part against digit capacity
        int_part = int(abs_d)
        max_int = 10 ** self.digits - 1 if self.digits > 0 else 0

        if int_part > max_int:
            if self.on_size_error == 'raise':
                raise CobolOverflowError(
                    f"Value {d} exceeds PIC capacity: "
                    f"{self.digits} integer digits (max {max_int})"
                )
            # Truncate left digits: keep only the rightmost `digits` digits
            int_part = int_part % (10 ** self.digits) if self.digits > 0 else 0
            # Reconstruct with fractional part preserved
            frac_part = abs_d - int(abs_d)
            abs_d = Decimal(int_part) + frac_part

        # Unsigned: already ensured positive in set()
        if not self.signed:
            return abs_d
        return abs_d * sign

    # ── Python protocol ─────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CobolDecimal):
            return self._value == other._value
        if isinstance(other, (int, float, Decimal)):
            return self._value == Decimal(str(other))
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, CobolDecimal):
            return self._value < other._value
        if isinstance(other, (int, float, Decimal)):
            return self._value < Decimal(str(other))
        return NotImplemented

    def __add__(self, other: 'CobolDecimal') -> 'CobolDecimal':
        return self.add(other)

    def __sub__(self, other: 'CobolDecimal') -> 'CobolDecimal':
        return self.subtract(other)

    def __mul__(self, other: 'CobolDecimal') -> 'CobolDecimal':
        return self.multiply(other)

    def __truediv__(self, other: 'CobolDecimal') -> 'CobolDecimal':
        return self.divide(other)

    def __repr__(self) -> str:
        sign = 'S' if self.signed else ''
        pic = f"{sign}9({self.digits})"
        if self.scale > 0:
            pic += f"V9({self.scale})"
        usage = f" {self.usage}" if self.usage != 'DISPLAY' else ''
        return f"CobolDecimal({pic}{usage}, value={self._value})"

    def __str__(self) -> str:
        return str(self._value)

    def __hash__(self) -> int:
        return hash(self._value)
