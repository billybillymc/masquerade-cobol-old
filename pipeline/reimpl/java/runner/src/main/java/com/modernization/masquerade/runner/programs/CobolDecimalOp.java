package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.cobol.CobolDecimal;
import com.modernization.masquerade.cobol.CobolOverflowError;
import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Parity test fixture, NOT a real reimplementation. Mirrors
 * {@code pipeline/reimpl/cobol_decimal_op.py}.
 *
 * <p>Exposes {@link CobolDecimal} operations through the differential harness
 * JSON contract so the Python and Java sides can be tested for byte-for-byte
 * equivalence on inputs that the W1 unit tests don't cover (overflow paths,
 * divide buffer edge cases, randomized fuzzing).
 *
 * <p>See the Python module's docstring for the operation grammar — every
 * Java code path here mirrors the Python one-for-one.
 */
public class CobolDecimalOp implements ProgramRunner {

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String op = inputs.getOrDefault("op", "").trim().toLowerCase();
        Map<String, String> out = new LinkedHashMap<>();

        try {
            switch (op) {
                case "set":         return doSet(inputs);
                case "add":         return doBinary(inputs, "add");
                case "subtract":    return doBinary(inputs, "subtract");
                case "multiply":    return doBinary(inputs, "multiply");
                case "divide":      return doBinary(inputs, "divide");
                case "assign_to":   return doAssignTo(inputs);
                case "from_display": return doFromDisplay(inputs);
                case "storage_bytes": return doStorageBytes(inputs);
                default:
                    out.put("error", "unknown op: '" + op + "'");
                    return out;
            }
        } catch (CobolOverflowError e) {
            out.put("value", "");
            out.put("error", "OVERFLOW: " + e.getMessage());
            return out;
        } catch (ArithmeticException e) {
            out.put("value", "");
            out.put("error", "ZeroDivisionError: " + e.getMessage());
            return out;
        } catch (NumberFormatException e) {
            out.put("value", "");
            out.put("error", "InvalidOperation: " + e.getMessage());
            return out;
        } catch (Exception e) {
            out.put("value", "");
            out.put("error", e.getClass().getSimpleName() + ": " + e.getMessage());
            return out;
        }
    }

    // ── op handlers ──────────────────────────────────────────────────────

    private Map<String, String> doSet(Map<String, String> in) {
        int digits = parseInt(in.get("digits"), 9);
        int scale = parseInt(in.get("scale"), 0);
        boolean signed = parseBool(in.get("signed"), true);
        String usage = in.getOrDefault("usage", "DISPLAY");
        String oseStr = in.getOrDefault("on_size_error", "truncate");
        CobolDecimal.OnSizeError ose = "raise".equalsIgnoreCase(oseStr)
                ? CobolDecimal.OnSizeError.RAISE : CobolDecimal.OnSizeError.TRUNCATE;
        String value = in.getOrDefault("value", "0");
        boolean rounded = parseBool(in.get("rounded"), false);

        CobolDecimal cd = new CobolDecimal(digits, scale, signed, usage, ose);
        cd.set(new BigDecimal(value), rounded);

        Map<String, String> out = new LinkedHashMap<>();
        out.put("value", strValue(cd));
        out.put("error", "");
        return out;
    }

    private Map<String, String> doBinary(Map<String, String> in, String op) {
        CobolDecimal a = new CobolDecimal(
                parseInt(in.get("a_digits"), 9),
                parseInt(in.get("a_scale"), 0),
                parseBool(in.get("a_signed"), true)
        );
        a.set(new BigDecimal(in.getOrDefault("a_value", "0")));

        CobolDecimal b = new CobolDecimal(
                parseInt(in.get("b_digits"), 9),
                parseInt(in.get("b_scale"), 0),
                parseBool(in.get("b_signed"), true)
        );
        b.set(new BigDecimal(in.getOrDefault("b_value", "0")));

        CobolDecimal result;
        switch (op) {
            case "add":      result = a.add(b); break;
            case "subtract": result = a.subtract(b); break;
            case "multiply": result = a.multiply(b); break;
            case "divide":   result = a.divide(b); break;
            default: throw new IllegalStateException(op);
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("result_value", strValue(result));
        out.put("result_digits", String.valueOf(result.digits()));
        out.put("result_scale", String.valueOf(result.scale()));
        out.put("error", "");
        return out;
    }

    private Map<String, String> doAssignTo(Map<String, String> in) {
        CobolDecimal src = new CobolDecimal(
                parseInt(in.get("src_digits"), 9),
                parseInt(in.get("src_scale"), 0),
                parseBool(in.get("src_signed"), true)
        );
        src.set(new BigDecimal(in.getOrDefault("src_value", "0")));

        CobolDecimal target = new CobolDecimal(
                parseInt(in.get("target_digits"), 9),
                parseInt(in.get("target_scale"), 0),
                parseBool(in.get("target_signed"), true)
        );
        boolean rounded = parseBool(in.get("rounded"), false);
        src.assignTo(target, rounded);

        Map<String, String> out = new LinkedHashMap<>();
        out.put("value", strValue(target));
        out.put("error", "");
        return out;
    }

    private Map<String, String> doFromDisplay(Map<String, String> in) {
        CobolDecimal cd = new CobolDecimal(
                parseInt(in.get("digits"), 9),
                parseInt(in.get("scale"), 0),
                parseBool(in.get("signed"), true)
        );
        // The "raw" input may legitimately be a digit string, "SPACES", or empty.
        // Java's runner contract serializes everything as string, including null
        // → we treat the empty string as null since the Python side handles
        // both identically (both → 0).
        Object raw = in.containsKey("raw") ? in.get("raw") : null;
        cd.fromDisplay(raw);

        Map<String, String> out = new LinkedHashMap<>();
        out.put("value", strValue(cd));
        out.put("error", "");
        return out;
    }

    private Map<String, String> doStorageBytes(Map<String, String> in) {
        CobolDecimal cd = new CobolDecimal(
                parseInt(in.get("digits"), 9),
                parseInt(in.get("scale"), 0),
                parseBool(in.get("signed"), true),
                in.getOrDefault("usage", "DISPLAY")
        );
        Map<String, String> out = new LinkedHashMap<>();
        out.put("storage_bytes", String.valueOf(cd.storageBytes()));
        out.put("error", "");
        return out;
    }

    // ── helpers ──────────────────────────────────────────────────────────

    /**
     * Canonical decimal string for a CobolDecimal value. MUST match Python's
     * {@code str(decimal_value)} convention byte-for-byte: trailing zeros
     * preserved, no exponential notation, leading sign on negatives only.
     */
    private static String strValue(CobolDecimal cd) {
        return cd.value().toPlainString();
    }

    private static int parseInt(String s, int fallback) {
        if (s == null || s.isEmpty()) return fallback;
        try {
            return Integer.parseInt(s.trim());
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    private static boolean parseBool(String s, boolean fallback) {
        if (s == null || s.isEmpty()) return fallback;
        String low = s.trim().toLowerCase();
        return "true".equals(low) || "1".equals(low) || "yes".equals(low) || "y".equals(low);
    }
}
