package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of CardDemo batch program CBCUS01C — Customer File Reader.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbcus01c.py} byte-for-byte. Python is the
 * source of truth.
 */
public class Cbcus01c implements ProgramRunner {

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        // Seed data — 2 customer records
        // Fields: custId, firstName, middleName, lastName, ssn, dob, fico, zip
        Object[][] customers = {
            {1, "John", "A", "Doe",   123456789, "1990-01-15", 750, "10001"},
            {2, "Jane", "B", "Smith", 987654321, "1985-07-22", 680, "90210"},
        };

        Map<String, String> out = new LinkedHashMap<>();
        out.put("RECORDS_READ", String.valueOf(customers.length));

        for (int i = 0; i < customers.length; i++) {
            Object[] c = customers[i];
            String line = String.format(
                "CUST-ID:%09d NAME:%s %s %s SSN:%09d DOB:%s FICO:%03d ZIP:%s",
                ((Number) c[0]).intValue(),
                ((String) c[1]).trim(),
                ((String) c[2]).trim(),
                ((String) c[3]).trim(),
                ((Number) c[4]).intValue(),
                (String) c[5],
                ((Number) c[6]).intValue(),
                (String) c[7]
            );
            out.put("DISPLAY_" + i, line);
        }

        return out;
    }
}
