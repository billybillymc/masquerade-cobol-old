package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of CardDemo batch program CBACT03C — Cross-Reference Reader.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbact03c.py} byte-for-byte. Python is the
 * source of truth.
 */
public class Cbact03c implements ProgramRunner {

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        // Seed data — 2 cross-reference records
        String[] cardNums  = {"4111111111111111", "4222222222222222"};
        long[]   custIds   = {1, 2};
        long[]   acctIds   = {100000001, 100000002};

        Map<String, String> out = new LinkedHashMap<>();
        out.put("RECORDS_READ", String.valueOf(cardNums.length));

        for (int i = 0; i < cardNums.length; i++) {
            String line = String.format(
                "XREF-CARD-NUM:%s CUST-ID:%09d ACCT-ID:%011d",
                cardNums[i],
                custIds[i],
                acctIds[i]
            );
            out.put("DISPLAY_" + i, line);
        }

        return out;
    }
}
