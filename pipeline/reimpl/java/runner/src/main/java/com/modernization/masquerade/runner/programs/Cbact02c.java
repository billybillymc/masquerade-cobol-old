package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of CardDemo batch program CBACT02C — Card File Reader.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbact02c.py} byte-for-byte. Python is the
 * source of truth.
 */
public class Cbact02c implements ProgramRunner {

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        // Seed data — 2 card records
        String[][] cards = {
            {"4111111111111111", "100000001", "123", "JOHN DOE",  "2029-12-31", "Y"},
            {"4222222222222222", "100000002", "456", "JANE SMITH", "2028-06-30", "Y"},
        };

        Map<String, String> out = new LinkedHashMap<>();
        out.put("RECORDS_READ", String.valueOf(cards.length));

        for (int i = 0; i < cards.length; i++) {
            String[] c = cards[i];
            String line = String.format(
                "CARD-NUM:%s ACCT-ID:%011d CVV:%03d NAME:%s EXP:%s STATUS:%s",
                c[0],
                Long.parseLong(c[1]),
                Integer.parseInt(c[2]),
                c[3],
                c[4],
                c[5]
            );
            out.put("DISPLAY_" + i, line);
        }

        return out;
    }
}
