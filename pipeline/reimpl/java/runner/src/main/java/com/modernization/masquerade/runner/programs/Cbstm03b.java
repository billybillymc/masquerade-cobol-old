package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Java reimplementation of CardDemo subroutine CBSTM03B — Statement File I/O.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbstm03b.py} byte-for-byte. Python is the
 * source of truth.
 */
public class Cbstm03b implements ProgramRunner {

    private static final String OPER_OPEN  = "O";
    private static final String OPER_CLOSE = "C";
    private static final String OPER_READ  = "R";

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "PROCESS_RECORDS").toUpperCase();
        List<TranRecord> trans = buildScenario(scenarioName);
        if (trans == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }

        // Create file manager
        FileManager mgr = new FileManager(trans);

        // OPEN
        M03BArea area = new M03BArea();
        area.oper = OPER_OPEN;
        mgr.execute(area);
        String openRc = area.rc;

        // READ all
        int recordsRead = 0;
        List<String> fldtRecords = new ArrayList<>();
        while (true) {
            area.oper = OPER_READ;
            mgr.execute(area);
            if ("10".equals(area.rc)) {
                break;
            }
            recordsRead++;
            fldtRecords.add(area.fldt);
        }

        // CLOSE
        area.oper = OPER_CLOSE;
        mgr.execute(area);
        String closeRc = area.rc;

        Map<String, String> out = new LinkedHashMap<>();
        out.put("OPEN_RC", openRc);
        out.put("CLOSE_RC", closeRc);
        out.put("RECORDS_READ", String.valueOf(recordsRead));
        for (int i = 0; i < fldtRecords.size(); i++) {
            out.put("FLDT_" + i, fldtRecords.get(i));
        }
        return out;
    }

    // ── Scenarios ─────────────────────────────────────────────────────────

    private List<TranRecord> buildScenario(String name) {
        switch (name) {
            case "PROCESS_RECORDS": return scenarioProcessRecords();
            case "EMPTY_INPUT":    return scenarioEmptyInput();
            default: return null;
        }
    }

    private List<TranRecord> scenarioProcessRecords() {
        List<TranRecord> list = new ArrayList<>();
        list.add(new TranRecord(
                "TRN0000000000001", "01", 1,
                "ONLINE", "Widget purchase",
                new BigDecimal("150.25"), 123456789,
                "ACME WIDGETS", "NEW YORK", "10001",
                "4111000000001111",
                "2026-04-01-12.00.00.000000",
                "2026-04-01-12.00.00.000000"
        ));
        return list;
    }

    private List<TranRecord> scenarioEmptyInput() {
        return new ArrayList<>();
    }

    // ── File Manager (mirrors Cbstm03bFileManager) ───────────────────────

    static class M03BArea {
        String dd = "TRNXFILE";
        String oper = "";
        String rc = "00";
        String key = "";
        int keyLn = 0;
        String fldt = "";
    }

    static class FileManager {
        private final List<TranRecord> transactions;
        private int cursor = 0;
        private boolean isOpen = false;

        FileManager(List<TranRecord> transactions) {
            this.transactions = transactions;
        }

        void execute(M03BArea area) {
            String op = area.oper;
            if (OPER_OPEN.equals(op)) {
                cursor = 0;
                isOpen = true;
                area.rc = "00";
            } else if (OPER_CLOSE.equals(op)) {
                isOpen = false;
                area.rc = "00";
            } else if (OPER_READ.equals(op)) {
                if (!isOpen) {
                    area.rc = "35";
                } else if (cursor >= transactions.size()) {
                    area.rc = "10";
                } else {
                    TranRecord tran = transactions.get(cursor);
                    cursor++;
                    area.fldt = serialize(tran);
                    area.rc = "00";
                }
            } else {
                area.rc = "99";
            }
        }

        private String serialize(TranRecord tran) {
            return String.format("%-16s%-2s%04d%-10s%-100s%014.2f%09d%-50s%-50s%-10s%-16s%-26s%-26s",
                    tran.tranId, tran.tranTypeCd, tran.tranCatCd,
                    tran.tranSource, tran.tranDesc,
                    tran.tranAmt.doubleValue(), tran.tranMerchantId,
                    tran.tranMerchantName, tran.tranMerchantCity,
                    tran.tranMerchantZip, tran.tranCardNum,
                    tran.tranOrigTs, tran.tranProcTs);
        }
    }

    // ── Inner data types ─────────────────────────────────────────────────

    static class TranRecord {
        final String tranId;
        final String tranTypeCd;
        final int tranCatCd;
        final String tranSource;
        final String tranDesc;
        final BigDecimal tranAmt;
        final int tranMerchantId;
        final String tranMerchantName;
        final String tranMerchantCity;
        final String tranMerchantZip;
        final String tranCardNum;
        final String tranOrigTs;
        final String tranProcTs;

        TranRecord(String tranId, String tranTypeCd, int tranCatCd,
                   String tranSource, String tranDesc, BigDecimal tranAmt,
                   int tranMerchantId, String tranMerchantName,
                   String tranMerchantCity, String tranMerchantZip,
                   String tranCardNum, String tranOrigTs, String tranProcTs) {
            this.tranId = tranId;
            this.tranTypeCd = tranTypeCd;
            this.tranCatCd = tranCatCd;
            this.tranSource = tranSource;
            this.tranDesc = tranDesc;
            this.tranAmt = tranAmt;
            this.tranMerchantId = tranMerchantId;
            this.tranMerchantName = tranMerchantName;
            this.tranMerchantCity = tranMerchantCity;
            this.tranMerchantZip = tranMerchantZip;
            this.tranCardNum = tranCardNum;
            this.tranOrigTs = tranOrigTs;
            this.tranProcTs = tranProcTs;
        }
    }
}
