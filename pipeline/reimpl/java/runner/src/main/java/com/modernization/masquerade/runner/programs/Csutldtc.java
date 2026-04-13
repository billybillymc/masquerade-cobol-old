package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.format.ResolverStyle;
import java.time.temporal.ChronoUnit;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of CardDemo CSUTLDTC — date validation utility.
 *
 * <p>Mirrors {@code pipeline/reimpl/csutldtc.py} byte-for-byte. The Python
 * version is the source of truth for all behavior, including subtle quirks:
 *
 * <ul>
 *   <li><b>Off-by-one Lilian:</b> the Python returns
 *       {@code (parsed - epoch).days + 1}, so 1582-10-14 maps to lillian=1
 *       and 1582-10-15 maps to lillian=2. This is technically wrong by one
 *       relative to the canonical Lilian definition, but Python is the
 *       source of truth — Java must reproduce this exactly.</li>
 *   <li><b>Lenient zero-padding:</b> Python's {@code strptime} accepts both
 *       {@code "2026-04-08"} and {@code "2026-4-8"} for {@code %Y-%m-%d}.
 *       Java's {@code DateTimeFormatter} is strict by default and would
 *       reject the second form. To match Python, this port uses lenient
 *       patterns ({@code yyyy-M-d} not {@code yyyy-MM-dd}).</li>
 *   <li><b>Off-by-one bad-month detection:</b> the Python {@code _has_bad_month}
 *       only knows about formats starting with "YYYY" or not — it does not
 *       handle {@code DD/MM/YYYY} correctly. Java mirrors the bug.</li>
 * </ul>
 *
 * <p>Output map keys (matching the Python {@code run_vector} adapter):
 * <ul>
 *   <li>{@code SEVERITY} — "0" on success, "3" on any validation error</li>
 *   <li>{@code RESULT_TEXT} — 15-char classification</li>
 *   <li>{@code LILLIAN} — Lilian day count as string ("0" if invalid)</li>
 *   <li>{@code RAW_MESSAGE} — full 80-char message identical to LS-RESULT</li>
 * </ul>
 */
public class Csutldtc implements ProgramRunner {

    // ── Result text constants — match the 15-char COBOL WS-RESULT slots ──

    private static final String VALID = "Date is valid  ";
    private static final String INSUFFICIENT = "Insufficient   ";
    private static final String BAD_DATE_VALUE = "Datevalue error";
    private static final String INVALID_ERA = "Invalid Era    ";
    private static final String UNSUPPORTED_RANGE = "Unsupp. Range  ";
    private static final String INVALID_MONTH = "Invalid month  ";
    private static final String BAD_PIC_STRING = "Bad Pic String ";
    private static final String NON_NUMERIC = "Nonnumeric data";
    private static final String YEAR_IN_ERA_ZERO = "YearInEra is 0 ";
    private static final String INVALID = "Date is invalid";

    private static final LocalDate LILIAN_EPOCH = LocalDate.of(1582, 10, 14);
    private static final LocalDate MIN_VALID = LocalDate.of(1582, 10, 15);
    private static final LocalDate MAX_VALID = LocalDate.of(9999, 12, 31);

    /**
     * Format pattern map. Keys are the COBOL-style format mask (uppercased)
     * the user passes; values are Java DateTimeFormatter patterns. Lenient
     * single-letter patterns ({@code M}, {@code d}) match Python strptime's
     * acceptance of unpadded values.
     */
    // Use `uuuu` (proleptic year) instead of `yyyy` (year of era) so STRICT
    // resolution doesn't require an era marker. `M` and `d` (single letter)
    // accept both zero-padded and unpadded values to match Python strptime.
    // `MM` and `dd` for the YYYYMMDD case where leading zeros are mandatory.
    private static final Map<String, DateTimeFormatter> FORMATS = new HashMap<>();
    static {
        FORMATS.put("YYYY-MM-DD", DateTimeFormatter.ofPattern("uuuu-M-d").withResolverStyle(ResolverStyle.STRICT));
        FORMATS.put("MM/DD/YYYY", DateTimeFormatter.ofPattern("M/d/uuuu").withResolverStyle(ResolverStyle.STRICT));
        FORMATS.put("YYYYMMDD",   DateTimeFormatter.ofPattern("uuuuMMdd").withResolverStyle(ResolverStyle.STRICT));
        FORMATS.put("MM/DD/YY",   DateTimeFormatter.ofPattern("M/d/uu").withResolverStyle(ResolverStyle.STRICT));
        FORMATS.put("DD/MM/YYYY", DateTimeFormatter.ofPattern("d/M/uuuu").withResolverStyle(ResolverStyle.STRICT));
        FORMATS.put("YYYY/MM/DD", DateTimeFormatter.ofPattern("uuuu/M/d").withResolverStyle(ResolverStyle.STRICT));
    }

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String lsDate = inputs.getOrDefault("LS_DATE", "");
        String lsFormat = inputs.getOrDefault("LS_DATE_FORMAT", "");

        DateCheckResult result = validateDate(lsDate, lsFormat);

        Map<String, String> out = new LinkedHashMap<>();
        out.put("SEVERITY", String.valueOf(result.severity));
        out.put("RESULT_TEXT", result.resultText);
        out.put("LILLIAN", String.valueOf(result.lillian));
        out.put("RAW_MESSAGE", result.rawMessage);
        return out;
    }

    /**
     * Validate a date string against a format mask. Mirrors Python's
     * {@code validate_date} line-by-line.
     */
    DateCheckResult validateDate(String lsDate, String lsDateFormat) {
        String dateStr = lsDate == null ? "" : lsDate.trim();
        String fmtStr = lsDateFormat == null ? "" : lsDateFormat.trim().toUpperCase();

        if (dateStr.isEmpty()) {
            return makeResult(3, INSUFFICIENT, 0, dateStr, fmtStr);
        }
        if (!FORMATS.containsKey(fmtStr)) {
            return makeResult(3, BAD_PIC_STRING, 0, dateStr, fmtStr);
        }

        LocalDate parsed;
        try {
            parsed = LocalDate.parse(dateStr, FORMATS.get(fmtStr));
        } catch (DateTimeParseException e) {
            // Distinguish "invalid month" from generic "bad value", same as Python.
            String[] parts = splitParts(dateStr);
            if (parts != null && hasBadMonth(parts, fmtStr)) {
                return makeResult(3, INVALID_MONTH, 0, dateStr, fmtStr);
            }
            return makeResult(3, BAD_DATE_VALUE, 0, dateStr, fmtStr);
        } catch (Exception e) {
            return makeResult(3, INVALID, 0, dateStr, fmtStr);
        }

        if (parsed.getYear() == 0) {
            return makeResult(3, YEAR_IN_ERA_ZERO, 0, dateStr, fmtStr);
        }
        if (parsed.isBefore(MIN_VALID) || parsed.isAfter(MAX_VALID)) {
            return makeResult(3, UNSUPPORTED_RANGE, 0, dateStr, fmtStr);
        }

        long lillian = ChronoUnit.DAYS.between(LILIAN_EPOCH, parsed) + 1;
        return makeResult(0, VALID, lillian, dateStr, fmtStr);
    }

    /** Split a date string on its separator. Returns null if no separator found. */
    private static String[] splitParts(String dateStr) {
        if (dateStr.contains("-")) return dateStr.split("-");
        if (dateStr.contains("/")) return dateStr.split("/");
        return null;
    }

    /**
     * Check whether the parsed parts contain a month outside 1..12. Mirrors
     * the Python {@code _has_bad_month}, including the (buggy) assumption
     * that month is at index 1 only when format starts with "YYYY".
     */
    private static boolean hasBadMonth(String[] parts, String fmtStr) {
        if (!fmtStr.contains("MM") || parts.length < 2) {
            return false;
        }
        int monthIdx = fmtStr.startsWith("YYYY") ? 1 : 0;
        try {
            int month = Integer.parseInt(parts[monthIdx]);
            return month < 1 || month > 12;
        } catch (NumberFormatException | ArrayIndexOutOfBoundsException e) {
            return false;
        }
    }

    /**
     * Build the 80-char WS-MESSAGE result. Layout MUST match the Python
     * {@code _make_result} byte-for-byte.
     *
     * Python format string:
     *   {severity:04d}Mesg Code:{msg_no:04d} {result_text:<15} TstDate:{date_str:<10} Mask used:{fmt_str:<10}
     * Then truncated to 80 chars and right-padded to 80.
     */
    private static DateCheckResult makeResult(
            int severity,
            String resultText,
            long lillian,
            String dateStr,
            String fmtStr
    ) {
        int msgNo = severity == 0 ? 0 : 777;
        String body = String.format(
                "%04dMesg Code:%04d %-15s TstDate:%-10s Mask used:%-10s   ",
                severity, msgNo, resultText, dateStr, fmtStr
        );
        // Pad / truncate to exactly 80 characters (matches Python `[:80].ljust(80)`)
        if (body.length() > 80) {
            body = body.substring(0, 80);
        } else if (body.length() < 80) {
            StringBuilder sb = new StringBuilder(body);
            while (sb.length() < 80) sb.append(' ');
            body = sb.toString();
        }
        return new DateCheckResult(severity, msgNo, resultText, lillian, body);
    }

    // ── Result type ──────────────────────────────────────────────────────

    static class DateCheckResult {
        final int severity;
        final int msgNo;
        final String resultText;
        final long lillian;
        final String rawMessage;

        DateCheckResult(int severity, int msgNo, String resultText, long lillian, String rawMessage) {
            this.severity = severity;
            this.msgNo = msgNo;
            this.resultText = resultText;
            this.lillian = lillian;
            this.rawMessage = rawMessage;
        }
    }
}
