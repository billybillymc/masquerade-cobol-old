"""Cross-language parity fuzz tests for CobolDecimal (closes R1).

The W1 unit tests ran 49 hand-written scenarios on `cobol_decimal.py` and
49 mirror scenarios on `CobolDecimal.java` independently. Both passed,
but that's *structural* parity — both files implement the same set of
explicit cases. It is NOT proof that they produce byte-identical results
on the same inputs.

This file closes that gap by driving BOTH `cobol_decimal.py` (in-process
via PythonRunner) and `CobolDecimal.java` (subprocess via JavaRunner)
through the same input vectors and asserting byte-for-byte equality.

Categories explicitly target the R1 unverified surface:

  A. Overflow + fractional combined — integer part overflows, fractional
     part must be preserved through the modulus + add path
  B. Small-divisor divide() — non-terminating quotients that stress the
     intScale+10 buffer
  C. Edge cases the W1 unit tests didn't randomize — digits=0, scale=0,
     extreme PIC sizes, COMP-3 odd-digit boundaries
  D. Cross-PIC assign_to combinations
  E. from_display coercion edge cases
  F. Randomized fuzz — fixed seed for reproducibility

Skips cleanly if the Java runner JAR isn't built.
"""

import random
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vector_runner import (
    JavaRunner,
    PythonRunner,
    RunRequest,
)


RUNNER_JAR = (
    Path(__file__).resolve().parent.parent
    / "reimpl" / "java" / "runner" / "target" / "masquerade-runner.jar"
)
JAVA_BIN = "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot/bin/java.exe"


def _java_available() -> bool:
    return RUNNER_JAR.exists() and Path(JAVA_BIN).exists()


def _make_java_runner() -> JavaRunner:
    return JavaRunner(jar_path=RUNNER_JAR, java_bin=JAVA_BIN)


# Module-level singletons so we don't pay constructor cost per test.
PYTHON = PythonRunner()
JAVA = _make_java_runner() if _java_available() else None


def _check_parity(vector_id: str, inputs: dict) -> None:
    """Run the same vector through Python and Java; assert outputs identical."""
    request = RunRequest(
        program="COBOL_DECIMAL_OP",
        vector_id=vector_id,
        inputs=inputs,
    )
    py = PYTHON.run(request)
    jv = JAVA.run(request)

    assert py.ok, f"{vector_id}: Python errored: {py.errors}"
    assert jv.ok, f"{vector_id}: Java errored: {jv.errors}"

    if py.outputs != jv.outputs:
        diff_lines = [f"{vector_id}: outputs differ for inputs {inputs}"]
        for k in sorted(set(py.outputs) | set(jv.outputs)):
            pv = py.outputs.get(k, "<missing>")
            jv_v = jv.outputs.get(k, "<missing>")
            if pv != jv_v:
                diff_lines.append(f"  {k}:")
                diff_lines.append(f"    python: {pv!r}")
                diff_lines.append(f"    java:   {jv_v!r}")
        pytest.fail("\n".join(diff_lines))


# ── A. Overflow + fractional path ──────────────────────────────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestOverflowFractional:
    """R1 high-risk area: integer part overflows, fractional part preserved.

    The Python `_truncate_to_pic` reconstructs:
        int_part = int_part % (10 ** digits)
        abs_d = Decimal(int_part) + frac_part
    The Java equivalent uses BigDecimal.remainder() and BigDecimal.add().
    These should produce identical results across all overflow cases.
    """

    def test_3_2_set_5_int_overflow_with_frac(self):
        """digits=3, scale=2, value=12345.67 → 345.67 (left-truncate int)"""
        _check_parity("OF_3_2_5", {
            "op": "set", "digits": "3", "scale": "2", "signed": "true",
            "value": "12345.67",
        })

    def test_3_2_extra_frac_truncates_then_overflows(self):
        """digits=3, scale=2, value=12345.6789 → 345.67 (frac truncates first)"""
        _check_parity("OF_3_2_LONG", {
            "op": "set", "digits": "3", "scale": "2", "signed": "true",
            "value": "12345.6789",
        })

    def test_2_3_no_overflow(self):
        """digits=2, scale=3, value=12.345 → 12.345 (fits in PIC 99V999)"""
        _check_parity("OF_2_3_OK", {
            "op": "set", "digits": "2", "scale": "3", "signed": "true",
            "value": "12.345",
        })

    def test_2_3_int_overflow(self):
        """digits=2, scale=3, value=123.456 → 23.456 (123 > 99)"""
        _check_parity("OF_2_3_INT", {
            "op": "set", "digits": "2", "scale": "3", "signed": "true",
            "value": "123.456",
        })

    def test_zero_digits_overflow(self):
        """digits=0, scale=2, value=1.99 → max_int=0, intpart=1 → overflow → 0.99"""
        _check_parity("OF_0_2", {
            "op": "set", "digits": "0", "scale": "2", "signed": "false",
            "value": "1.99",
        })

    def test_zero_digits_no_overflow(self):
        """digits=0, scale=2, value=0.99 → fits"""
        _check_parity("OF_0_2_OK", {
            "op": "set", "digits": "0", "scale": "2", "signed": "false",
            "value": "0.99",
        })

    def test_4_2_overflow(self):
        """digits=4, scale=2, value=99999.99 → 9999.99 (drop one int digit)"""
        _check_parity("OF_4_2", {
            "op": "set", "digits": "4", "scale": "2", "signed": "true",
            "value": "99999.99",
        })

    def test_5_0_overflow(self):
        """digits=5, scale=0, value=123456 → 23456 (no fractional)"""
        _check_parity("OF_5_0", {
            "op": "set", "digits": "5", "scale": "0", "signed": "false",
            "value": "123456",
        })

    def test_1_4_overflow(self):
        """digits=1, scale=4, value=12.3456 → 2.3456"""
        _check_parity("OF_1_4", {
            "op": "set", "digits": "1", "scale": "4", "signed": "true",
            "value": "12.3456",
        })

    def test_negative_overflow(self):
        """digits=3, scale=2, value=-12345.67 → -345.67 (sign preserved)"""
        _check_parity("OF_NEG", {
            "op": "set", "digits": "3", "scale": "2", "signed": "true",
            "value": "-12345.67",
        })

    def test_unsigned_negative_input(self):
        """digits=3, scale=2, signed=false, value=-12345.67 → 345.67 (abs first, then truncate)"""
        _check_parity("OF_UNSIGNED_NEG", {
            "op": "set", "digits": "3", "scale": "2", "signed": "false",
            "value": "-12345.67",
        })

    def test_overflow_raise_mode(self):
        """on_size_error=raise should produce identical error markers."""
        _check_parity("OF_RAISE", {
            "op": "set", "digits": "3", "scale": "2", "signed": "true",
            "on_size_error": "raise", "value": "12345.67",
        })


# ── B. Small-divisor divide() buffer ──────────────────────────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestDivideBuffer:
    """R1 medium-risk area: divide() uses intScale+10 buffer in Java vs
    Python's Decimal context (28-digit default precision). Verify the buffer
    is enough for real cases.
    """

    def test_10000_div_3(self):
        """Classic non-terminating division — digits=5, scale=0 / digits=1, scale=0"""
        _check_parity("DIV_10K_3", {
            "op": "divide",
            "a_digits": "5", "a_scale": "0", "a_signed": "true", "a_value": "10000",
            "b_digits": "1", "b_scale": "0", "b_signed": "true", "b_value": "3",
        })

    def test_100_div_7(self):
        _check_parity("DIV_100_7", {
            "op": "divide",
            "a_digits": "3", "a_scale": "0", "a_signed": "true", "a_value": "100",
            "b_digits": "1", "b_scale": "0", "b_signed": "true", "b_value": "7",
        })

    def test_div_with_scale_2_dividend(self):
        """Scaled dividend: 100.50 / 7 — intermediate scale should hold the result."""
        _check_parity("DIV_SCALE_2", {
            "op": "divide",
            "a_digits": "5", "a_scale": "2", "a_signed": "true", "a_value": "100.50",
            "b_digits": "1", "b_scale": "0", "b_signed": "true", "b_value": "7",
        })

    def test_div_small_divisor(self):
        """Divide by a small fractional divisor: 100 / 0.01 = 10000."""
        _check_parity("DIV_SMALL_DIV", {
            "op": "divide",
            "a_digits": "3", "a_scale": "0", "a_signed": "true", "a_value": "100",
            "b_digits": "1", "b_scale": "2", "b_signed": "true", "b_value": "0.01",
        })

    def test_div_negative_quotient(self):
        _check_parity("DIV_NEG", {
            "op": "divide",
            "a_digits": "5", "a_scale": "2", "a_signed": "true", "a_value": "-100.00",
            "b_digits": "1", "b_scale": "0", "b_signed": "true", "b_value": "3",
        })

    def test_div_by_zero(self):
        """Both languages must produce error markers for division by zero."""
        _check_parity("DIV_BY_0", {
            "op": "divide",
            "a_digits": "5", "a_scale": "2", "a_signed": "true", "a_value": "100.00",
            "b_digits": "5", "b_scale": "2", "b_signed": "true", "b_value": "0",
        })


# ── C. Edge cases the unit tests don't randomize ──────────────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestEdgeCases:
    """digits=0, scale=0, COMP-3 odd-digit boundaries, extreme sizes."""

    def test_digits_0_scale_0_zero(self):
        _check_parity("D0S0", {
            "op": "set", "digits": "0", "scale": "0", "signed": "false",
            "value": "0",
        })

    def test_digits_18_scale_0_max(self):
        """Max int range for COMP."""
        _check_parity("D18S0", {
            "op": "set", "digits": "18", "scale": "0", "signed": "true",
            "value": "999999999999999999",
        })

    def test_digits_10_scale_10(self):
        """Heavy fractional precision."""
        _check_parity("D10S10", {
            "op": "set", "digits": "10", "scale": "10", "signed": "true",
            "value": "1234567890.0123456789",
        })

    def test_storage_bytes_comp3_odd(self):
        """COMP-3 byte size for odd digit counts."""
        for d in [1, 3, 5, 7, 9, 11, 13, 15, 17]:
            _check_parity(f"SB_C3_{d}", {
                "op": "storage_bytes", "digits": str(d), "scale": "0",
                "signed": "true", "usage": "COMP-3",
            })

    def test_storage_bytes_comp3_even(self):
        for d in [2, 4, 6, 8, 10, 12, 14, 16, 18]:
            _check_parity(f"SB_C3_{d}E", {
                "op": "storage_bytes", "digits": str(d), "scale": "0",
                "signed": "true", "usage": "COMP-3",
            })

    def test_storage_bytes_comp_boundaries(self):
        """Java COMP byte sizes at the 4/9/18 digit boundaries."""
        for d in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 18]:
            _check_parity(f"SB_COMP_{d}", {
                "op": "storage_bytes", "digits": str(d), "scale": "0",
                "signed": "true", "usage": "COMP",
            })

    def test_storage_bytes_display_with_scale(self):
        _check_parity("SB_DISP_5_3", {
            "op": "storage_bytes", "digits": "5", "scale": "3",
            "signed": "true", "usage": "DISPLAY",
        })


# ── D. Cross-PIC assign_to combinations ───────────────────────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestAssignTo:
    def test_truncate_scale_only(self):
        """Source scale=4 → target scale=2 (truncate fractional, no int overflow)."""
        _check_parity("AS_SCALE", {
            "op": "assign_to",
            "src_digits": "5", "src_scale": "4", "src_signed": "true", "src_value": "123.4567",
            "target_digits": "5", "target_scale": "2", "target_signed": "true",
        })

    def test_truncate_scale_with_rounding(self):
        """Same as above but with rounded=true (ROUND_HALF_UP)."""
        _check_parity("AS_SCALE_RND", {
            "op": "assign_to",
            "src_digits": "5", "src_scale": "4", "src_signed": "true", "src_value": "123.4567",
            "target_digits": "5", "target_scale": "2", "target_signed": "true",
            "rounded": "true",
        })

    def test_truncate_int_only(self):
        """Source has bigger int range → target overflows."""
        _check_parity("AS_INT", {
            "op": "assign_to",
            "src_digits": "7", "src_scale": "2", "src_signed": "true", "src_value": "1234567.89",
            "target_digits": "5", "target_scale": "2", "target_signed": "true",
        })

    def test_truncate_both_int_and_scale(self):
        """Both int overflow and scale truncation."""
        _check_parity("AS_BOTH", {
            "op": "assign_to",
            "src_digits": "7", "src_scale": "4", "src_signed": "true", "src_value": "1234567.8901",
            "target_digits": "5", "target_scale": "2", "target_signed": "true",
        })

    def test_signed_to_unsigned(self):
        """Negative source → unsigned target stores absolute."""
        _check_parity("AS_S2U", {
            "op": "assign_to",
            "src_digits": "5", "src_scale": "2", "src_signed": "true", "src_value": "-100.50",
            "target_digits": "5", "target_scale": "2", "target_signed": "false",
        })


# ── E. from_display coercion ───────────────────────────────────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestFromDisplay:
    def test_spaces(self):
        _check_parity("FD_SPACES", {
            "op": "from_display", "digits": "5", "scale": "2", "signed": "true",
            "raw": "SPACES",
        })

    def test_zeros(self):
        _check_parity("FD_ZEROS", {
            "op": "from_display", "digits": "5", "scale": "2", "signed": "true",
            "raw": "ZEROS",
        })

    def test_empty_string(self):
        _check_parity("FD_EMPTY", {
            "op": "from_display", "digits": "5", "scale": "2", "signed": "true",
            "raw": "",
        })

    def test_implied_decimal(self):
        """'1234567' with scale=2 → 12345.67"""
        _check_parity("FD_IMPLIED", {
            "op": "from_display", "digits": "5", "scale": "2", "signed": "true",
            "raw": "1234567",
        })

    def test_implied_decimal_short(self):
        """'42' with scale=2 → 0.42"""
        _check_parity("FD_IMPLIED_SHORT", {
            "op": "from_display", "digits": "5", "scale": "2", "signed": "true",
            "raw": "42",
        })

    def test_negative_digit_string(self):
        _check_parity("FD_NEG", {
            "op": "from_display", "digits": "5", "scale": "2", "signed": "true",
            "raw": "-1234567",
        })


# ── F. Randomized fuzz ─────────────────────────────────────────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestRandomFuzz:
    """Fixed-seed random PIC + value combinations.

    Each call shells out to a fresh JVM (~700ms cold start), so this stays
    modest. The fixed seed makes failures reproducible; bumping the seed
    sweeps a different region of input space.
    """

    SEED = 20260408
    NUM_VECTORS = 25

    def test_random_set_within_pic(self):
        """Random set() with values that fit comfortably inside the PIC."""
        rng = random.Random(self.SEED)
        for i in range(self.NUM_VECTORS):
            digits = rng.randint(1, 12)
            scale = rng.randint(0, 6)
            signed = rng.choice([True, False])
            # Generate a value definitely within the PIC range
            int_part = rng.randint(0, 10 ** digits - 1)
            frac_part = rng.randint(0, 10 ** scale - 1) if scale > 0 else 0
            sign = "-" if (signed and rng.random() < 0.3) else ""
            value = f"{sign}{int_part}.{frac_part:0{scale}d}" if scale > 0 else f"{sign}{int_part}"
            _check_parity(f"FUZZ_SET_{i}", {
                "op": "set", "digits": str(digits), "scale": str(scale),
                "signed": str(signed).lower(), "value": value,
            })

    def test_random_set_overflow(self):
        """Random set() with values that EXCEED the PIC range — exercises
        the overflow + fractional reconstruction path."""
        rng = random.Random(self.SEED + 1)
        for i in range(self.NUM_VECTORS):
            digits = rng.randint(1, 8)
            scale = rng.randint(0, 4)
            signed = True
            # Force an overflow: int part 10x bigger than max
            int_part = rng.randint(10 ** digits, 10 ** (digits + 2))
            frac_part = rng.randint(0, 10 ** scale - 1) if scale > 0 else 0
            value = f"{int_part}.{frac_part:0{scale}d}" if scale > 0 else f"{int_part}"
            _check_parity(f"FUZZ_OF_{i}", {
                "op": "set", "digits": str(digits), "scale": str(scale),
                "signed": "true", "value": value,
            })

    def test_random_add(self):
        rng = random.Random(self.SEED + 2)
        for i in range(self.NUM_VECTORS):
            a_digits = rng.randint(1, 8)
            a_scale = rng.randint(0, 4)
            b_digits = rng.randint(1, 8)
            b_scale = rng.randint(0, 4)
            a_int = rng.randint(0, 10 ** a_digits - 1)
            b_int = rng.randint(0, 10 ** b_digits - 1)
            a_frac = rng.randint(0, 10 ** a_scale - 1) if a_scale > 0 else 0
            b_frac = rng.randint(0, 10 ** b_scale - 1) if b_scale > 0 else 0
            a_val = f"{a_int}.{a_frac:0{a_scale}d}" if a_scale > 0 else f"{a_int}"
            b_val = f"{b_int}.{b_frac:0{b_scale}d}" if b_scale > 0 else f"{b_int}"
            _check_parity(f"FUZZ_ADD_{i}", {
                "op": "add",
                "a_digits": str(a_digits), "a_scale": str(a_scale),
                "a_signed": "true", "a_value": a_val,
                "b_digits": str(b_digits), "b_scale": str(b_scale),
                "b_signed": "true", "b_value": b_val,
            })

    def test_random_subtract(self):
        rng = random.Random(self.SEED + 3)
        for i in range(self.NUM_VECTORS):
            digits = rng.randint(2, 8)
            scale = rng.randint(0, 4)
            a_int = rng.randint(0, 10 ** digits - 1)
            b_int = rng.randint(0, 10 ** digits - 1)
            a_frac = rng.randint(0, 10 ** scale - 1) if scale > 0 else 0
            b_frac = rng.randint(0, 10 ** scale - 1) if scale > 0 else 0
            a_val = f"{a_int}.{a_frac:0{scale}d}" if scale > 0 else f"{a_int}"
            b_val = f"{b_int}.{b_frac:0{scale}d}" if scale > 0 else f"{b_int}"
            _check_parity(f"FUZZ_SUB_{i}", {
                "op": "subtract",
                "a_digits": str(digits), "a_scale": str(scale),
                "a_signed": "true", "a_value": a_val,
                "b_digits": str(digits), "b_scale": str(scale),
                "b_signed": "true", "b_value": b_val,
            })

    def test_random_multiply_small_to_avoid_overflow(self):
        """Multiply with small operands so the product doesn't overflow."""
        rng = random.Random(self.SEED + 4)
        for i in range(self.NUM_VECTORS):
            a_digits = rng.randint(1, 4)
            a_scale = rng.randint(0, 2)
            b_digits = rng.randint(1, 4)
            b_scale = rng.randint(0, 2)
            a_int = rng.randint(0, 99)
            b_int = rng.randint(0, 99)
            a_frac = rng.randint(0, 10 ** a_scale - 1) if a_scale > 0 else 0
            b_frac = rng.randint(0, 10 ** b_scale - 1) if b_scale > 0 else 0
            a_val = f"{a_int}.{a_frac:0{a_scale}d}" if a_scale > 0 else f"{a_int}"
            b_val = f"{b_int}.{b_frac:0{b_scale}d}" if b_scale > 0 else f"{b_int}"
            _check_parity(f"FUZZ_MUL_{i}", {
                "op": "multiply",
                "a_digits": str(a_digits), "a_scale": str(a_scale),
                "a_signed": "true", "a_value": a_val,
                "b_digits": str(b_digits), "b_scale": str(b_scale),
                "b_signed": "true", "b_value": b_val,
            })
