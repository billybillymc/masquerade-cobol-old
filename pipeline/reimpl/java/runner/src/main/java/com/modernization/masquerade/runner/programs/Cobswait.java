package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of COBSWAIT — CardDemo wait utility.
 *
 * <p>Mirrors {@code pipeline/reimpl/cobswait.py} byte-for-byte. Python is the
 * source of truth.
 *
 * <p>DO NOT SLEEP — just compute the coercion and derived values.
 */
public class Cobswait implements ProgramRunner {

    /**
     * Coerce PIC X(8) PARM-VALUE to PIC 9(8) COMP centiseconds.
     *
     * <p>COBOL MOVE of non-numeric data to a numeric item fills with zeros;
     * out-of-range positive values are left-truncated (COMP overflow).
     */
    static long coerceParm(String parmValue) {
        if (parmValue == null) return 0;
        String trimmed = parmValue.trim();
        if (trimmed.isEmpty()) return 0;
        long cs;
        try {
            cs = Long.parseLong(trimmed);
        } catch (NumberFormatException e) {
            return 0;
        }
        if (cs < 0) return 0;
        // Silent left-truncation for > 8 digits: mod 10^8
        return cs % 100000000L;
    }

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String parmValue = inputs.getOrDefault("PARM_VALUE", "");
        long cs = coerceParm(parmValue);
        double seconds = cs / 100.0;

        Map<String, String> out = new LinkedHashMap<>();
        out.put("REQUESTED_CS", String.valueOf(cs));
        out.put("COMPUTED_SECONDS", String.format("%.2f", seconds));
        return out;
    }
}
