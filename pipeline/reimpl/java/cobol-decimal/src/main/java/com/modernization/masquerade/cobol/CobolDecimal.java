package com.modernization.masquerade.cobol;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Objects;

/**
 * Fixed-point decimal with COBOL PIC semantics — Java port of
 * {@code pipeline/cobol_decimal.py}.
 *
 * <p>Faithfully reproduces COBOL arithmetic behavior:
 * <ul>
 *   <li>Silent left-truncation on overflow (no ON SIZE ERROR)</li>
 *   <li>Truncation of fractional digits (default) or ROUND_HALF_UP (ROUNDED phrase)</li>
 *   <li>COBOL-standard intermediate precision rules for ADD/SUB/MUL/DIV</li>
 *   <li>SPACES/blank coercion to zero for MOVE semantics</li>
 *   <li>Storage byte size computation for COMP, COMP-3, DISPLAY</li>
 * </ul>
 *
 * <p><b>Parity contract:</b> every test vector in {@code CobolDecimalTest} must
 * produce byte-identical results to the equivalent vector in
 * {@code pipeline/tests/test_cobol_decimal.py}. Drift between this class and
 * the Python original is a correctness bug.
 */
public final class CobolDecimal implements Comparable<CobolDecimal> {

    /** Behavior when an assigned value exceeds the integer-digit capacity. */
    public enum OnSizeError {
        /** Silently drop the leftmost digits that exceed PIC capacity (COBOL default). */
        TRUNCATE,
        /** Throw {@link CobolOverflowError}. */
        RAISE
    }

    private final int digits;
    private final int scale;
    private final boolean signed;
    private final String usage;
    private final OnSizeError onSizeError;
    private BigDecimal value;

    // ── Constructors ────────────────────────────────────────────────────

    /**
     * @param digits      Integer digit capacity (count of 9s before V in PIC).
     * @param scale       Decimal places (count of 9s after V in PIC).
     * @param signed      True if PIC has S prefix.
     * @param usage       Storage format — "DISPLAY", "COMP", "COMP-3", "BINARY".
     * @param onSizeError TRUNCATE (default, COBOL standard) or RAISE.
     */
    public CobolDecimal(int digits, int scale, boolean signed, String usage, OnSizeError onSizeError) {
        this.digits = digits;
        this.scale = scale;
        this.signed = signed;
        this.usage = usage == null ? "DISPLAY" : usage.toUpperCase();
        this.onSizeError = onSizeError == null ? OnSizeError.TRUNCATE : onSizeError;
        this.value = BigDecimal.ZERO;
    }

    public CobolDecimal(int digits, int scale, boolean signed) {
        this(digits, scale, signed, "DISPLAY", OnSizeError.TRUNCATE);
    }

    public CobolDecimal(int digits, int scale, boolean signed, String usage) {
        this(digits, scale, signed, usage, OnSizeError.TRUNCATE);
    }

    // ── Properties ──────────────────────────────────────────────────────

    public BigDecimal value() { return value; }
    public int digits() { return digits; }
    public int scale() { return scale; }
    public boolean signed() { return signed; }
    public String usage() { return usage; }
    public OnSizeError onSizeError() { return onSizeError; }

    /** Maximum storable value based on PIC digits and scale. */
    public BigDecimal maxValue() {
        BigDecimal intPart = digits > 0 ? new BigDecimal("9".repeat(digits)) : BigDecimal.ZERO;
        if (scale > 0) {
            BigDecimal fracPart = new BigDecimal("0." + "9".repeat(scale));
            return intPart.add(fracPart);
        }
        return intPart;
    }

    /** Minimum storable value (negative of max if signed, else zero). */
    public BigDecimal minValue() {
        return signed ? maxValue().negate() : BigDecimal.ZERO;
    }

    /** Total digit count (integer + fractional). */
    public int totalDigits() {
        return digits + scale;
    }

    /**
     * Byte size based on USAGE clause. Mirrors {@code cobol_decimal.py:storage_bytes}.
     * <ul>
     *   <li>DISPLAY: 1 byte per digit (sign embedded in last byte)</li>
     *   <li>COMP-3 / PACKED-DECIMAL: ceil((total_digits + 1) / 2)</li>
     *   <li>COMP / BINARY: 2 (≤4 digits), 4 (≤9), 8 (≤18)</li>
     * </ul>
     */
    public int storageBytes() {
        int td = totalDigits();
        switch (usage) {
            case "COMP-3":
            case "PACKED-DECIMAL":
                // ceil((td + 1) / 2) — written as integer math
                return (td + 1 + 1) / 2;
            case "COMP":
            case "BINARY":
            case "COMP-4":
            case "COMP-5":
                if (td <= 4) return 2;
                if (td <= 9) return 4;
                return 8;
            default:
                return td;
        }
    }

    // ── Mutation ────────────────────────────────────────────────────────

    /** Assign a value, enforcing PIC precision. Truncates fractional digits. */
    public CobolDecimal set(BigDecimal v) {
        return set(v, false);
    }

    /**
     * Assign a value, enforcing PIC precision.
     *
     * @param v       The value to store.
     * @param rounded If true, use ROUND_HALF_UP (COBOL ROUNDED phrase).
     *                If false, truncate toward zero (COBOL default).
     */
    public CobolDecimal set(BigDecimal v, boolean rounded) {
        BigDecimal d = signed ? v : v.abs();
        this.value = truncateToPic(d, rounded);
        return this;
    }

    public CobolDecimal set(long v) {
        return set(BigDecimal.valueOf(v));
    }

    public CobolDecimal set(long v, boolean rounded) {
        return set(BigDecimal.valueOf(v), rounded);
    }

    public CobolDecimal set(String v) {
        return set(new BigDecimal(v));
    }

    /**
     * Coerce a display value into this field. Mirrors {@code cobol_decimal.py:from_display}.
     *
     * <p>Handles COBOL MOVE semantics:
     * <ul>
     *   <li>SPACES / null / empty → 0</li>
     *   <li>ZEROS → 0</li>
     *   <li>Digit string → parsed with implied decimal at scale position</li>
     *   <li>Numeric types → direct conversion</li>
     * </ul>
     */
    public CobolDecimal fromDisplay(Object raw) {
        if (raw == null) {
            this.value = BigDecimal.ZERO;
            return this;
        }
        if (raw instanceof BigDecimal bd) {
            return set(bd);
        }
        if (raw instanceof Number n) {
            return set(new BigDecimal(n.toString()));
        }

        String s = raw.toString().trim().toUpperCase();

        if (s.isEmpty()
                || s.equals("SPACES") || s.equals("SPACE")
                || s.equals("ZEROS") || s.equals("ZEROES") || s.equals("ZERO")) {
            this.value = BigDecimal.ZERO;
            return this;
        }

        // Digit string with implied decimal point.
        // For PIC S9(5)V99, '1234567' → 12345.67 (last `scale` digits are fractional).
        boolean isNegative = s.startsWith("-");
        String sClean = s.replaceAll("^[+-]", "");

        if (sClean.matches("\\d+") && scale > 0 && !s.contains(".")) {
            String intPart;
            String fracPart;
            if (sClean.length() > scale) {
                intPart = sClean.substring(0, sClean.length() - scale);
                fracPart = sClean.substring(sClean.length() - scale);
            } else {
                intPart = "0";
                // Left-pad with zeros to `scale` width
                StringBuilder padded = new StringBuilder();
                for (int i = 0; i < scale - sClean.length(); i++) padded.append('0');
                padded.append(sClean);
                fracPart = padded.toString();
            }
            BigDecimal d = new BigDecimal(intPart + "." + fracPart);
            if (isNegative) d = d.negate();
            return set(d);
        }

        try {
            return set(new BigDecimal(s));
        } catch (NumberFormatException e) {
            // Unparseable → zero (COBOL MOVE of non-numeric to numeric)
            this.value = BigDecimal.ZERO;
            return this;
        }
    }

    // ── Arithmetic (COBOL intermediate precision rules) ─────────────────

    /**
     * ADD with COBOL intermediate precision.
     * Intermediate: max(d1,d2)+1 integer digits, max(s1,s2) scale.
     */
    public CobolDecimal add(CobolDecimal other) {
        int intDigits = Math.max(this.digits, other.digits) + 1;
        int intScale = Math.max(this.scale, other.scale);
        CobolDecimal result = new CobolDecimal(intDigits, intScale, true);
        BigDecimal raw = this.value.add(other.value);
        result.value = result.truncateToPic(raw, false);
        return result;
    }

    /**
     * SUBTRACT with COBOL intermediate precision (same rule as ADD).
     */
    public CobolDecimal subtract(CobolDecimal other) {
        int intDigits = Math.max(this.digits, other.digits) + 1;
        int intScale = Math.max(this.scale, other.scale);
        CobolDecimal result = new CobolDecimal(intDigits, intScale, true);
        BigDecimal raw = this.value.subtract(other.value);
        result.value = result.truncateToPic(raw, false);
        return result;
    }

    /**
     * MULTIPLY with COBOL intermediate precision.
     * Intermediate integer digits: d1 + d2. Intermediate scale: max(s1, s2).
     * Multiplication uses {@code rounded=true} in the truncate step to match
     * the Python original.
     */
    public CobolDecimal multiply(CobolDecimal other) {
        int intDigits = this.digits + other.digits;
        int intScale = Math.max(this.scale, other.scale);
        CobolDecimal result = new CobolDecimal(intDigits, intScale, true);
        BigDecimal raw = this.value.multiply(other.value);
        result.value = result.truncateToPic(raw, true);
        return result;
    }

    /**
     * DIVIDE with conservative intermediate precision.
     * Intermediate integer digits = d1 + s2 + max(s1, s2).
     * Intermediate scale = max(s1, s2) + dividend scale.
     */
    public CobolDecimal divide(CobolDecimal other) {
        if (other.value.signum() == 0) {
            throw new ArithmeticException("COBOL DIVIDE by zero");
        }

        int maxScale = Math.max(this.scale, other.scale);
        int intDigits = this.digits + other.scale + maxScale;
        int intScale = maxScale + this.scale;

        // Ensure minimum reasonable precision
        intDigits = Math.max(intDigits, this.digits);
        intScale = Math.max(intScale, this.scale);

        CobolDecimal result = new CobolDecimal(intDigits, intScale, true);
        // BigDecimal.divide requires explicit scale + rounding for non-terminating quotients.
        // Use a generous buffer beyond intScale so the subsequent truncateToPic has room.
        BigDecimal raw = this.value.divide(other.value, intScale + 10, RoundingMode.DOWN);
        result.value = result.truncateToPic(raw, false);
        return result;
    }

    /**
     * Assign this value to a target CobolDecimal, truncating to the target's PIC.
     * This is the final step of a COBOL COMPUTE: the intermediate result is
     * truncated (or rounded) to fit the receiving field.
     */
    public CobolDecimal assignTo(CobolDecimal target) {
        return assignTo(target, false);
    }

    public CobolDecimal assignTo(CobolDecimal target, boolean rounded) {
        target.set(this.value, rounded);
        return target;
    }

    // ── Internal ────────────────────────────────────────────────────────

    /**
     * Truncate a BigDecimal to fit this field's PIC definition.
     * <ol>
     *   <li>Truncate (or round) fractional digits to {@code this.scale}</li>
     *   <li>If integer part exceeds {@code this.digits}, truncate leftmost digits</li>
     *   <li>If onSizeError == RAISE, raise instead of truncating left</li>
     * </ol>
     */
    private BigDecimal truncateToPic(BigDecimal d, boolean rounded) {
        int sign = d.signum() < 0 ? -1 : 1;
        BigDecimal absD = d.abs();

        // Step 1: Handle fractional digits
        if (scale >= 0) {
            absD = absD.setScale(scale, rounded ? RoundingMode.HALF_UP : RoundingMode.DOWN);
        }

        // Step 2: Check integer part against digit capacity
        BigDecimal intPart = absD.setScale(0, RoundingMode.DOWN);
        BigDecimal maxInt = digits > 0
                ? BigDecimal.TEN.pow(digits).subtract(BigDecimal.ONE)
                : BigDecimal.ZERO;

        if (intPart.compareTo(maxInt) > 0) {
            if (onSizeError == OnSizeError.RAISE) {
                throw new CobolOverflowError(
                        "Value " + d + " exceeds PIC capacity: "
                                + digits + " integer digits (max " + maxInt + ")");
            }
            // Truncate left digits: keep only the rightmost `digits` digits.
            // intPart % (10^digits), then re-attach the original fractional part.
            BigDecimal modulus = digits > 0 ? BigDecimal.TEN.pow(digits) : BigDecimal.ONE;
            BigDecimal intMod = digits > 0 ? intPart.remainder(modulus) : BigDecimal.ZERO;
            BigDecimal fracPart = absD.subtract(intPart);
            absD = intMod.add(fracPart);
        }

        if (!signed) return absD;
        return sign < 0 ? absD.negate() : absD;
    }

    // ── Comparable / equals / hashCode ──────────────────────────────────

    @Override
    public int compareTo(CobolDecimal other) {
        return this.value.compareTo(other.value);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o instanceof CobolDecimal cd) {
            return this.value.compareTo(cd.value) == 0;
        }
        if (o instanceof BigDecimal bd) {
            return this.value.compareTo(bd) == 0;
        }
        if (o instanceof Number n) {
            return this.value.compareTo(new BigDecimal(n.toString())) == 0;
        }
        return false;
    }

    @Override
    public int hashCode() {
        // stripTrailingZeros so equal numeric values share a hash, matching the
        // Python behavior of hash(self._value) where Decimal('2.00') and
        // Decimal('2') hash equally.
        return Objects.hashCode(this.value.stripTrailingZeros());
    }

    @Override
    public String toString() {
        return value.toPlainString();
    }

    /** Debug rendering similar to {@code __repr__} on the Python class. */
    public String toDebugString() {
        String signPrefix = signed ? "S" : "";
        String pic = signPrefix + "9(" + digits + ")";
        if (scale > 0) pic += "V9(" + scale + ")";
        String u = !"DISPLAY".equals(usage) ? " " + usage : "";
        return "CobolDecimal(" + pic + u + ", value=" + value + ")";
    }
}
