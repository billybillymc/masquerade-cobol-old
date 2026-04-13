package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Java reimplementation of CardDemo batch program CBIMPORT — Batch Data Import.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbimport.py} byte-for-byte. Python is the
 * source of truth.
 */
public class Cbimport implements ProgramRunner {

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "PROCESS_RECORDS").toUpperCase();
        Scenario scn = buildScenario(scenarioName);
        if (scn == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }

        // Run import
        List<String> log = new ArrayList<>();
        List<String> errors = new ArrayList<>();
        log.add("CBIMPORT: Starting Customer Data Import");
        log.add("CBIMPORT: Records to process: " + scn.records.size());

        int customers = 0, accounts = 0, xrefs = 0, transactions = 0, cards = 0;
        int errorCount = 0;

        for (ExportRecord rec : scn.records) {
            switch (rec.recType) {
                case "C": customers++; break;
                case "A": accounts++; break;
                case "X": xrefs++; break;
                case "T": transactions++; break;
                case "D": cards++; break;
                default:
                    errors.add("CBIMPORT: Unknown record type '" + rec.recType
                            + "' at seq " + rec.seqNum);
                    errorCount++;
                    break;
            }
        }

        log.add("CBIMPORT: Customers imported:     " + customers);
        log.add("CBIMPORT: Accounts imported:      " + accounts);
        log.add("CBIMPORT: Xrefs imported:         " + xrefs);
        log.add("CBIMPORT: Transactions imported:  " + transactions);
        log.add("CBIMPORT: Cards imported:         " + cards);
        log.add("CBIMPORT: Errors:                 " + errorCount);
        log.add("CBIMPORT: Import complete.");

        int totalImported = customers + accounts + xrefs + transactions + cards;

        Map<String, String> out = new LinkedHashMap<>();
        out.put("TOTAL_IMPORTED", String.valueOf(totalImported));
        out.put("CUSTOMERS", String.valueOf(customers));
        out.put("ACCOUNTS", String.valueOf(accounts));
        out.put("XREFS", String.valueOf(xrefs));
        out.put("TRANSACTIONS", String.valueOf(transactions));
        out.put("CARDS", String.valueOf(cards));
        out.put("ERRORS", String.valueOf(errorCount));
        for (int i = 0; i < log.size(); i++) {
            out.put("LOG_" + i, log.get(i));
        }
        for (int i = 0; i < errors.size(); i++) {
            out.put("ERROR_" + i, errors.get(i));
        }
        return out;
    }

    // ── Scenarios ─────────────────────────────────────────────────────────

    private Scenario buildScenario(String name) {
        switch (name) {
            case "PROCESS_RECORDS": return scenarioProcessRecords();
            case "EMPTY_INPUT":    return scenarioEmptyInput();
            case "BAD_TYPE":       return scenarioBadType();
            default: return null;
        }
    }

    private Scenario scenarioProcessRecords() {
        Scenario s = new Scenario();
        s.records.add(new ExportRecord(1, "C"));
        s.records.add(new ExportRecord(2, "A"));
        s.records.add(new ExportRecord(3, "X"));
        s.records.add(new ExportRecord(4, "T"));
        s.records.add(new ExportRecord(5, "D"));
        return s;
    }

    private Scenario scenarioEmptyInput() {
        return new Scenario();
    }

    private Scenario scenarioBadType() {
        Scenario s = new Scenario();
        s.records.add(new ExportRecord(1, "Z"));
        return s;
    }

    // ── Inner data types ─────────────────────────────────────────────────

    private static class Scenario {
        final List<ExportRecord> records = new ArrayList<>();
    }

    static class ExportRecord {
        final int seqNum;
        final String recType;

        ExportRecord(int seqNum, String recType) {
            this.seqNum = seqNum;
            this.recType = recType;
        }
    }
}
