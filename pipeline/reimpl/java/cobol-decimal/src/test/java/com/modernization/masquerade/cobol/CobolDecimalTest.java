package com.modernization.masquerade.cobol;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Parity test suite for {@link CobolDecimal} — every test in this file mirrors a
 * test in {@code pipeline/tests/test_cobol_decimal.py}. If a test passes here it
 * MUST pass with byte-identical results in the Python suite, and vice versa.
 *
 * <p>This is the foundation gate for the Java reimplementation track. Drift
 * between this file and the Python test file is a correctness regression.
 */
@DisplayName("CobolDecimal parity with cobol_decimal.py")
class CobolDecimalTest {

    /** Helper for value equality that doesn't care about trailing zeros. */
    private static void assertValueEquals(String expected, BigDecimal actual) {
        assertEquals(0, new BigDecimal(expected).compareTo(actual),
                "expected " + expected + " but got " + actual);
    }

    // ── TestBasicStorage ────────────────────────────────────────────────

    @Nested
    @DisplayName("BasicStorage — values within PIC range")
    class BasicStorage {

        @Test
        @DisplayName("PIC S9(5)V99 stores 999.99 exactly")
        void storesValueWithinPicRange() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.set(new BigDecimal("999.99"));
            assertValueEquals("999.99", cd.value());
        }

        @Test
        @DisplayName("freshly created CobolDecimal has value 0")
        void storesZeroByDefault() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            assertValueEquals("0", cd.value());
        }

        @Test
        @DisplayName("PIC S9(5)V99 stores -123.45")
        void storesNegativeWhenSigned() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.set(new BigDecimal("-123.45"));
            assertValueEquals("-123.45", cd.value());
        }

        @Test
        @DisplayName("PIC 9(5)V99 has max_value 99999.99")
        void maxValueUnsigned() {
            CobolDecimal cd = new CobolDecimal(5, 2, false);
            assertValueEquals("99999.99", cd.maxValue());
        }

        @Test
        @DisplayName("PIC S9(5)V99 has max=99999.99 and min=-99999.99")
        void maxValueSigned() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            assertValueEquals("99999.99", cd.maxValue());
            assertValueEquals("-99999.99", cd.minValue());
        }

        @Test
        @DisplayName("PIC 9(5) has min_value 0")
        void minValueUnsignedIsZero() {
            CobolDecimal cd = new CobolDecimal(5, 0, false);
            assertValueEquals("0", cd.minValue());
        }
    }

    // ── TestOverflow ────────────────────────────────────────────────────

    @Nested
    @DisplayName("Overflow — truncate-left default, raise when configured")
    class Overflow {

        @Test
        @DisplayName("PIC 9(5): assigning 123456 silently truncates to 23456")
        void overflowTruncatesLeftDigits() {
            CobolDecimal cd = new CobolDecimal(5, 0, false);
            cd.set(123456);
            assertValueEquals("23456", cd.value());
        }

        @Test
        @DisplayName("PIC S9(3)V99: assigning 12345.67 truncates to 345.67")
        void overflowTruncatesLeftWithDecimal() {
            CobolDecimal cd = new CobolDecimal(3, 2, true);
            cd.set(new BigDecimal("12345.67"));
            assertValueEquals("345.67", cd.value());
        }

        @Test
        @DisplayName("on_size_error=RAISE raises CobolOverflowError on overflow")
        void overflowRaisesWhenConfigured() {
            CobolDecimal cd = new CobolDecimal(5, 0, false, "DISPLAY", CobolDecimal.OnSizeError.RAISE);
            assertThrows(CobolOverflowError.class, () -> cd.set(123456));
        }

        @Test
        @DisplayName("on_size_error=RAISE does NOT raise when value fits")
        void noOverflowDoesNotRaise() {
            CobolDecimal cd = new CobolDecimal(5, 0, false, "DISPLAY", CobolDecimal.OnSizeError.RAISE);
            cd.set(99999);
            assertValueEquals("99999", cd.value());
        }

        @Test
        @DisplayName("PIC 9(5): assigning -42 to unsigned stores 42 (absolute)")
        void unsignedStoresAbsoluteOnNegative() {
            CobolDecimal cd = new CobolDecimal(5, 0, false);
            cd.set(-42);
            assertValueEquals("42", cd.value());
        }
    }

    // ── TestRounding ────────────────────────────────────────────────────

    @Nested
    @DisplayName("Rounding — truncate by default, ROUND_HALF_UP when rounded")
    class Rounding {

        @Test
        @DisplayName("PIC S9(5)V99: 1.999 truncates to 1.99 (not 2.00)")
        void truncatesFractionalDigits() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.set(new BigDecimal("1.999"));
            assertValueEquals("1.99", cd.value());
        }

        @Test
        @DisplayName("PIC S9(5)V99 with rounded=true: 1.995 rounds to 2.00")
        void roundedModeRoundsUp() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.set(new BigDecimal("1.995"), true);
            assertValueEquals("2.00", cd.value());
        }

        @Test
        @DisplayName("COBOL ROUNDED rounds away from zero: -1.995 → -2.00")
        void roundedNegativeRoundsAwayFromZero() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.set(new BigDecimal("-1.995"), true);
            assertValueEquals("-2.00", cd.value());
        }

        @Test
        @DisplayName("PIC 9(3)V9: assigning 1.99 truncates to 1.9 (not 2.0)")
        void truncationDoesNotRound() {
            CobolDecimal cd = new CobolDecimal(3, 1, false);
            cd.set(new BigDecimal("1.99"));
            assertValueEquals("1.9", cd.value());
        }
    }

    // ── TestIntermediatePrecisionAdd ────────────────────────────────────

    @Nested
    @DisplayName("Intermediate precision: ADD/SUBTRACT")
    class IntermediatePrecisionAdd {

        @Test
        @DisplayName("ADD: S9(5)V99 + S9(3)V99 = 99999.99 + 999.99 = 100999.98")
        void addIntermediatePrecision() {
            CobolDecimal a = new CobolDecimal(5, 2, true);
            a.set(new BigDecimal("99999.99"));
            CobolDecimal b = new CobolDecimal(3, 2, true);
            b.set(new BigDecimal("999.99"));
            CobolDecimal result = a.add(b);
            assertValueEquals("100999.98", result.value());
            assertTrue(result.digits() >= 6, "intermediate digits should be ≥ 6");
        }

        @Test
        @DisplayName("SUBTRACT: same precision rule as ADD")
        void subtractIntermediatePrecision() {
            CobolDecimal a = new CobolDecimal(5, 2, true);
            a.set(new BigDecimal("100.00"));
            CobolDecimal b = new CobolDecimal(5, 2, true);
            b.set(new BigDecimal("99999.99"));
            CobolDecimal result = a.subtract(b);
            assertValueEquals("-99899.99", result.value());
            assertTrue(result.digits() >= 6);
        }

        @Test
        @DisplayName("ADD: S9(5)V99 + S9(5)V9(4) → intermediate scale max(2,4)=4")
        void addDifferentScalesAligns() {
            CobolDecimal a = new CobolDecimal(5, 2, true);
            a.set(new BigDecimal("100.50"));
            CobolDecimal b = new CobolDecimal(5, 4, true);
            b.set(new BigDecimal("0.1234"));
            CobolDecimal result = a.add(b);
            assertValueEquals("100.6234", result.value());
            assertTrue(result.scale() >= 4);
        }
    }

    // ── TestIntermediatePrecisionMultiply ───────────────────────────────

    @Nested
    @DisplayName("Intermediate precision: MULTIPLY")
    class IntermediatePrecisionMultiply {

        @Test
        @DisplayName("MULTIPLY: S9(5)V99 * S9(3)V9 = 12345.67 * 123.4 = 1523455.68")
        void multiplyIntermediatePrecision() {
            CobolDecimal a = new CobolDecimal(5, 2, true);
            a.set(new BigDecimal("12345.67"));
            CobolDecimal b = new CobolDecimal(3, 1, true);
            b.set(new BigDecimal("123.4"));
            CobolDecimal result = a.multiply(b);
            assertValueEquals("1523455.68", result.value());
            assertTrue(result.digits() >= 8);
            assertTrue(result.scale() >= 2);
        }

        @Test
        @DisplayName("MULTIPLY: V99 * V99 → 0.99 * 0.99 = 0.98 at scale 2")
        void multiplyScaleExpansion() {
            CobolDecimal a = new CobolDecimal(0, 2, false);
            a.set(new BigDecimal("0.99"));
            CobolDecimal b = new CobolDecimal(0, 2, false);
            b.set(new BigDecimal("0.99"));
            CobolDecimal result = a.multiply(b);
            assertValueEquals("0.98", result.value());
            assertTrue(result.scale() >= 2);
        }
    }

    // ── TestIntermediatePrecisionDivide ─────────────────────────────────

    @Nested
    @DisplayName("Intermediate precision: DIVIDE")
    class IntermediatePrecisionDivide {

        @Test
        @DisplayName("DIVIDE: 10000 / 3 has enough precision for the quotient")
        void divideBasic() {
            CobolDecimal a = new CobolDecimal(5, 0, true);
            a.set(10000);
            CobolDecimal b = new CobolDecimal(1, 0, true);
            b.set(3);
            CobolDecimal result = a.divide(b);
            // 10000 / 3 = 3333.333... — truncated to intermediate scale
            assertTrue(result.value().compareTo(new BigDecimal("3333")) >= 0);
        }

        @Test
        @DisplayName("Division by zero raises ArithmeticException")
        void divideByZeroRaises() {
            CobolDecimal a = new CobolDecimal(5, 2, true);
            a.set(new BigDecimal("100.00"));
            CobolDecimal b = new CobolDecimal(5, 2, true);
            b.set(new BigDecimal("0"));
            assertThrows(ArithmeticException.class, () -> a.divide(b));
        }
    }

    // ── TestAssignment ──────────────────────────────────────────────────

    @Nested
    @DisplayName("Cross-PIC assignment — truncate intermediate to target field")
    class Assignment {

        @Test
        @DisplayName("Assign S9(7)V99 → S9(5)V99 truncates left")
        void assignLargerToSmallerTruncatesLeft() {
            CobolDecimal intermediate = new CobolDecimal(7, 2, true);
            intermediate.set(new BigDecimal("1234567.89"));
            CobolDecimal target = new CobolDecimal(5, 2, true);
            intermediate.assignTo(target);
            assertValueEquals("34567.89", target.value());
        }

        @Test
        @DisplayName("Assign scale=4 → scale=2 truncates right")
        void assignTruncatesScale() {
            CobolDecimal intermediate = new CobolDecimal(5, 4, true);
            intermediate.set(new BigDecimal("123.4567"));
            CobolDecimal target = new CobolDecimal(5, 2, true);
            intermediate.assignTo(target);
            assertValueEquals("123.45", target.value());
        }

        @Test
        @DisplayName("assignTo with rounded=true rounds instead of truncating")
        void assignWithRounding() {
            CobolDecimal intermediate = new CobolDecimal(5, 4, true);
            intermediate.set(new BigDecimal("123.4567"));
            CobolDecimal target = new CobolDecimal(5, 2, true);
            intermediate.assignTo(target, true);
            assertValueEquals("123.46", target.value());
        }
    }

    // ── TestStorageBytes ────────────────────────────────────────────────

    @Nested
    @DisplayName("storageBytes — matches COBOL byte-size rules")
    class StorageBytes {

        @Test
        @DisplayName("PIC S9(10)V99 COMP-3 → 7 bytes")
        void comp3StorageSize() {
            CobolDecimal cd = new CobolDecimal(10, 2, true, "COMP-3");
            assertEquals(7, cd.storageBytes());
        }

        @Test
        @DisplayName("PIC S9(5) COMP-3 → 3 bytes")
        void comp3OddDigits() {
            CobolDecimal cd = new CobolDecimal(5, 0, true, "COMP-3");
            assertEquals(3, cd.storageBytes());
        }

        @Test
        @DisplayName("PIC S9(4) COMP → 2 bytes")
        void compSmall() {
            CobolDecimal cd = new CobolDecimal(4, 0, true, "COMP");
            assertEquals(2, cd.storageBytes());
        }

        @Test
        @DisplayName("PIC S9(9) COMP → 4 bytes")
        void compMedium() {
            CobolDecimal cd = new CobolDecimal(9, 0, true, "COMP");
            assertEquals(4, cd.storageBytes());
        }

        @Test
        @DisplayName("PIC S9(15) COMP → 8 bytes")
        void compLarge() {
            CobolDecimal cd = new CobolDecimal(15, 0, true, "COMP");
            assertEquals(8, cd.storageBytes());
        }

        @Test
        @DisplayName("PIC S9(10)V99 DISPLAY → 12 bytes")
        void displayStorageSize() {
            CobolDecimal cd = new CobolDecimal(10, 2, true, "DISPLAY");
            assertEquals(12, cd.storageBytes());
        }
    }

    // ── TestCoercion ────────────────────────────────────────────────────

    @Nested
    @DisplayName("fromDisplay — SPACES, digit strings, null, etc.")
    class Coercion {

        @Test
        @DisplayName("MOVE SPACES TO numeric → 0")
        void spacesCoercionToZero() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.fromDisplay("SPACES");
            assertValueEquals("0", cd.value());
        }

        @Test
        @DisplayName("null → 0")
        void nullCoercionToZero() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.fromDisplay(null);
            assertValueEquals("0", cd.value());
        }

        @Test
        @DisplayName("empty string → 0")
        void emptyStringCoercionToZero() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.fromDisplay("");
            assertValueEquals("0", cd.value());
        }

        @Test
        @DisplayName("'ZEROS' → 0")
        void zerosStringCoercion() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.fromDisplay("ZEROS");
            assertValueEquals("0", cd.value());
        }

        @Test
        @DisplayName("'1234567' on PIC S9(5)V99 → 12345.67")
        void digitStringWithImpliedDecimal() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.fromDisplay("1234567");
            assertValueEquals("12345.67", cd.value());
        }

        @Test
        @DisplayName("'42' on PIC 9(5) → 42")
        void digitStringNoScale() {
            CobolDecimal cd = new CobolDecimal(5, 0, false);
            cd.fromDisplay("42");
            assertValueEquals("42", cd.value());
        }

        @Test
        @DisplayName("BigDecimal('123.45') passes through")
        void decimalPassthrough() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.fromDisplay(new BigDecimal("123.45"));
            assertValueEquals("123.45", cd.value());
        }

        @Test
        @DisplayName("Integer 42 passes through")
        void intPassthrough() {
            CobolDecimal cd = new CobolDecimal(5, 0, false);
            cd.fromDisplay(42);
            assertValueEquals("42", cd.value());
        }
    }

    // ── TestGoldenVectors — real CardDemo arithmetic patterns ───────────

    @Nested
    @DisplayName("Golden vectors from real CardDemo programs")
    class GoldenVectors {

        @Test
        @DisplayName("CBTRN02C balance: credit - debit + tran_amt = 1649.50")
        void balanceCalculationCbtrn02c() {
            // ACCT-CURR-CYC-CREDIT: PIC S9(10)V99
            CobolDecimal credit = new CobolDecimal(10, 2, true);
            credit.set(new BigDecimal("5000.00"));

            // ACCT-CURR-CYC-DEBIT: PIC S9(10)V99
            CobolDecimal debit = new CobolDecimal(10, 2, true);
            debit.set(new BigDecimal("3500.75"));

            // DALYTRAN-AMT: PIC S9(09)V99
            CobolDecimal tranAmt = new CobolDecimal(9, 2, true);
            tranAmt.set(new BigDecimal("150.25"));

            // COMPUTE WS-TEMP-BAL = credit - debit + tran_amt
            CobolDecimal intermediate = credit.subtract(debit);
            CobolDecimal intermediate2 = intermediate.add(tranAmt);

            // WS-TEMP-BAL: PIC S9(09)V99
            CobolDecimal wsTempBal = new CobolDecimal(9, 2, true);
            intermediate2.assignTo(wsTempBal);

            assertValueEquals("1649.50", wsTempBal.value());
        }

        @Test
        @DisplayName("COPAUA0C timestamp: cur_time * 1000 + ms = 143025500")
        void timestampCalculationCopaua0c() {
            CobolDecimal curTime = new CobolDecimal(6, 0, true);
            curTime.set(143025);

            CobolDecimal literal1000 = new CobolDecimal(4, 0, true);
            literal1000.set(1000);

            CobolDecimal ms = new CobolDecimal(8, 0, true);
            ms.set(500);

            CobolDecimal intermediate = curTime.multiply(literal1000);
            assertValueEquals("143025000", intermediate.value());

            CobolDecimal intermediate2 = intermediate.add(ms);
            assertValueEquals("143025500", intermediate2.value());

            // PIC S9(09) COMP-3
            CobolDecimal result = new CobolDecimal(9, 0, true, "COMP-3");
            intermediate2.assignTo(result);
            assertValueEquals("143025500", result.value());
        }

        @Test
        @DisplayName("COPAUA0C date reversal: 99999 - 26074 = 73925")
        void dateReversalCopaua0c() {
            CobolDecimal literal = new CobolDecimal(5, 0, true);
            literal.set(99999);

            CobolDecimal yyddd = new CobolDecimal(5, 0, true);
            yyddd.set(26074);

            CobolDecimal intermediate = literal.subtract(yyddd);
            assertValueEquals("73925", intermediate.value());
        }
    }

    // ── TestOperatorOverloads → ValueSemantics ──────────────────────────

    @Nested
    @DisplayName("Value semantics: equals, compareTo, debug repr")
    class ValueSemantics {

        @Test
        @DisplayName("equals compares numeric value, not PIC")
        void eq() {
            CobolDecimal a = new CobolDecimal(5, 2, true);
            a.set(new BigDecimal("100.50"));
            CobolDecimal b = new CobolDecimal(3, 2, true);
            b.set(new BigDecimal("100.50"));
            assertEquals(a, b);
        }

        @Test
        @DisplayName("compareTo orders by numeric value")
        void lt() {
            CobolDecimal a = new CobolDecimal(5, 2, true);
            a.set(new BigDecimal("100.00"));
            CobolDecimal b = new CobolDecimal(5, 2, true);
            b.set(new BigDecimal("200.00"));
            assertTrue(a.compareTo(b) < 0);
            assertFalse(b.compareTo(a) < 0);
        }

        @Test
        @DisplayName("add via method: 100.50 + 50.25 = 150.75")
        void addMethod() {
            CobolDecimal a = new CobolDecimal(5, 2, true);
            a.set(new BigDecimal("100.50"));
            CobolDecimal b = new CobolDecimal(5, 2, true);
            b.set(new BigDecimal("50.25"));
            CobolDecimal result = a.add(b);
            assertValueEquals("150.75", result.value());
        }

        @Test
        @DisplayName("subtract via method: 100.50 - 50.25 = 50.25")
        void subMethod() {
            CobolDecimal a = new CobolDecimal(5, 2, true);
            a.set(new BigDecimal("100.50"));
            CobolDecimal b = new CobolDecimal(5, 2, true);
            b.set(new BigDecimal("50.25"));
            CobolDecimal result = a.subtract(b);
            assertValueEquals("50.25", result.value());
        }

        @Test
        @DisplayName("multiply via method: 1.50 * 2 = 3.00")
        void mulMethod() {
            CobolDecimal a = new CobolDecimal(3, 2, true);
            a.set(new BigDecimal("1.50"));
            CobolDecimal b = new CobolDecimal(3, 0, true);
            b.set(2);
            CobolDecimal result = a.multiply(b);
            assertValueEquals("3.00", result.value());
        }

        @Test
        @DisplayName("divide via method: 100.00 / 4 = 25")
        void truedivMethod() {
            CobolDecimal a = new CobolDecimal(5, 2, true);
            a.set(new BigDecimal("100.00"));
            CobolDecimal b = new CobolDecimal(1, 0, true);
            b.set(4);
            CobolDecimal result = a.divide(b);
            assertValueEquals("25", result.value());
        }

        @Test
        @DisplayName("toDebugString reports value and PIC")
        void debugRepr() {
            CobolDecimal cd = new CobolDecimal(5, 2, true);
            cd.set(new BigDecimal("123.45"));
            String r = cd.toDebugString();
            assertTrue(r.contains("123.45"));
            assertTrue(r.contains("S9(5)V9(2)"));
        }
    }
}
