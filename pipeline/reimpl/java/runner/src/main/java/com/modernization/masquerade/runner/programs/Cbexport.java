package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Java reimplementation of CardDemo batch program CBEXPORT — Batch Data Export.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbexport.py} byte-for-byte. Python is the
 * source of truth.
 */
public class Cbexport implements ProgramRunner {

    private static final String EXPORT_TIMESTAMP = "2026-04-08 12:00:00.00";

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "PROCESS_RECORDS").toUpperCase();
        Scenario scn = buildScenario(scenarioName);
        if (scn == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }

        // Run export
        List<String> log = new ArrayList<>();
        log.add("CBEXPORT: Starting Customer Data Export");
        log.add("CBEXPORT: Export Timestamp: " + EXPORT_TIMESTAMP);

        int seq = 0;
        int customers = 0, accounts = 0, xrefs = 0, transactions = 0, cards = 0;

        for (int i = 0; i < scn.customerCount; i++) {
            seq++;
            customers++;
        }
        log.add("CBEXPORT: Customers exported: " + customers);

        for (int i = 0; i < scn.accountCount; i++) {
            seq++;
            accounts++;
        }
        log.add("CBEXPORT: Accounts exported: " + accounts);

        for (int i = 0; i < scn.xrefCount; i++) {
            seq++;
            xrefs++;
        }
        log.add("CBEXPORT: Xrefs exported: " + xrefs);

        for (int i = 0; i < scn.transactionCount; i++) {
            seq++;
            transactions++;
        }
        log.add("CBEXPORT: Transactions exported: " + transactions);

        for (int i = 0; i < scn.cardCount; i++) {
            seq++;
            cards++;
        }
        log.add("CBEXPORT: Cards exported: " + cards);

        int total = customers + accounts + xrefs + transactions + cards;
        log.add("CBEXPORT: Total records exported: " + total);
        log.add("CBEXPORT: Export complete.");

        Map<String, String> out = new LinkedHashMap<>();
        out.put("TOTAL_RECORDS", String.valueOf(total));
        out.put("CUSTOMERS", String.valueOf(customers));
        out.put("ACCOUNTS", String.valueOf(accounts));
        out.put("XREFS", String.valueOf(xrefs));
        out.put("TRANSACTIONS", String.valueOf(transactions));
        out.put("CARDS", String.valueOf(cards));
        out.put("ABENDED", "False");
        for (int i = 0; i < log.size(); i++) {
            out.put("LOG_" + i, log.get(i));
        }
        return out;
    }

    // ── Scenarios ─────────────────────────────────────────────────────────

    private Scenario buildScenario(String name) {
        switch (name) {
            case "PROCESS_RECORDS": return scenarioProcessRecords();
            case "EMPTY_INPUT":    return scenarioEmptyInput();
            default: return null;
        }
    }

    private Scenario scenarioProcessRecords() {
        Scenario s = new Scenario();
        s.customerCount = 1;
        s.accountCount = 1;
        s.xrefCount = 1;
        s.transactionCount = 1;
        s.cardCount = 1;
        return s;
    }

    private Scenario scenarioEmptyInput() {
        return new Scenario();
    }

    // ── Inner data types ─────────────────────────────────────────────────

    private static class Scenario {
        int customerCount = 0;
        int accountCount = 0;
        int xrefCount = 0;
        int transactionCount = 0;
        int cardCount = 0;
    }
}
