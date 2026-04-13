package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Java reimplementation of CardDemo batch program CBTRN03C — Transaction Detail Report.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbtrn03c.py} byte-for-byte. Python is the
 * source of truth.
 */
public class Cbtrn03c implements ProgramRunner {

    private static final BigDecimal BD_0_00 = new BigDecimal("0.00");
    private static final int PAGE_SIZE = 20;

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "PROCESS_RECORDS").toUpperCase();
        Scenario scn = buildScenario(scenarioName);
        if (scn == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }

        ReportResult result = generateReport(scn);

        Map<String, String> out = new LinkedHashMap<>();
        out.put("RECORDS_READ", String.valueOf(result.recordsRead));
        out.put("RECORDS_REPORTED", String.valueOf(result.recordsReported));
        out.put("GRAND_TOTAL", result.grandTotal.setScale(2, RoundingMode.HALF_UP).toPlainString());
        out.put("PAGE_COUNT", String.valueOf(result.pageCount));
        for (int i = 0; i < result.reportLines.size(); i++) {
            out.put("REPORT_LINE_" + i, result.reportLines.get(i));
        }
        return out;
    }

    private ReportResult generateReport(Scenario scn) {
        ReportResult result = new ReportResult();
        int lineCounter = 0;
        BigDecimal pageTotal = BD_0_00;
        BigDecimal accountTotal = BD_0_00;
        BigDecimal grandTotal = BD_0_00;
        String currCardNum = "";
        boolean firstTime = true;

        // Write first page header
        writePageHeader(result, 1, scn.startDate, scn.endDate);

        for (TranRecord tran : scn.transactions) {
            result.recordsRead++;

            // Date filter
            String procDate = tran.tranProcTs.length() >= 10
                    ? tran.tranProcTs.substring(0, 10) : "";
            if (procDate.compareTo(scn.startDate) < 0 || procDate.compareTo(scn.endDate) > 0) {
                continue;
            }

            result.recordsReported++;

            // Account break
            if (!tran.tranCardNum.equals(currCardNum)) {
                if (!firstTime) {
                    writeAccountTotals(result, currCardNum, accountTotal);
                    accountTotal = BD_0_00;
                } else {
                    firstTime = false;
                }
                currCardNum = tran.tranCardNum;
            }

            // Look up references
            TranTypeRecord tranType = scn.tranTypes.get(tran.tranTypeCd);
            String typeDesc = tranType != null ? tranType.tranTypeDesc.trim() : tran.tranTypeCd;
            TranCatgKey catgKey = new TranCatgKey(tran.tranTypeCd, tran.tranCatCd);
            TranCatgRecord tranCatg = scn.tranCatgs.get(catgKey);
            String catgDesc = tranCatg != null ? tranCatg.tranCatgDesc.trim() : String.valueOf(tran.tranCatCd);
            String detail = typeDesc + "/" + catgDesc + " " + (tran.tranDesc.length() > 30
                    ? tran.tranDesc.substring(0, 30) : tran.tranDesc);

            String line = String.format("%-16s %-51s $%12.2f",
                    tran.tranId, detail, tran.tranAmt.doubleValue());
            result.reportLines.add(line);

            pageTotal = pageTotal.add(tran.tranAmt);
            accountTotal = accountTotal.add(tran.tranAmt);
            grandTotal = grandTotal.add(tran.tranAmt);
            lineCounter++;

            // Page break
            if (lineCounter >= PAGE_SIZE) {
                result.reportLines.add(String.format("  PAGE TOTAL: $%14.2f", pageTotal.doubleValue()));
                result.reportLines.add(String.format("  GRAND TOTAL SO FAR: $%14.2f", grandTotal.doubleValue()));
                pageTotal = BD_0_00;
                lineCounter = 0;
                writePageHeader(result, result.pageCount + 1, scn.startDate, scn.endDate);
            }
        }

        // Final account total
        if (!firstTime) {
            writeAccountTotals(result, currCardNum, accountTotal);
        }

        // Grand total
        StringBuilder eq = new StringBuilder();
        for (int i = 0; i < 133; i++) eq.append('=');
        result.reportLines.add(eq.toString());
        result.reportLines.add(String.format("  GRAND TOTAL: $%14.2f", grandTotal.doubleValue()));
        result.reportLines.add(eq.toString());

        result.grandTotal = grandTotal;
        return result;
    }

    private void writePageHeader(ReportResult result, int pageNum, String startDate, String endDate) {
        StringBuilder eq = new StringBuilder();
        for (int i = 0; i < 133; i++) eq.append('=');
        StringBuilder dash = new StringBuilder();
        for (int i = 0; i < 133; i++) dash.append('-');

        result.reportLines.add(eq.toString());
        result.reportLines.add(String.format("  CARDEMO TRANSACTION DETAIL REPORT               PAGE: %05d", pageNum));
        result.reportLines.add("  DATE RANGE: " + startDate + " TO " + endDate);
        result.reportLines.add(eq.toString());
        result.reportLines.add(String.format("%-16s %-51s %13s", "TRAN ID", "TRAN DETAILS", "TRAN AMOUNT"));
        result.reportLines.add(dash.toString());
        result.pageCount++;
    }

    private void writeAccountTotals(ReportResult result, String cardNum, BigDecimal accTotal) {
        StringBuilder dash = new StringBuilder();
        for (int i = 0; i < 133; i++) dash.append('-');
        result.reportLines.add(dash.toString());
        result.reportLines.add(String.format("  ACCOUNT TOTAL FOR CARD %s: $%14.2f", cardNum, accTotal.doubleValue()));
        result.reportLines.add("");
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
        s.startDate = "2026-04-01";
        s.endDate = "2026-04-30";

        s.tranTypes.put("01", new TranTypeRecord("01", "Purchase"));
        s.tranCatgs.put(new TranCatgKey("01", 1),
                new TranCatgRecord("01", 1, "Retail"));

        s.transactions.add(new TranRecord(
                "TRN0000000000001", "01", 1, "Widget purchase",
                new BigDecimal("150.25"), "4111000000001111",
                "2026-04-01-12.00.00.000000"));
        s.transactions.add(new TranRecord(
                "TRN0000000000002", "01", 1, "Gadget purchase",
                new BigDecimal("75.50"), "4111000000001111",
                "2026-04-05-14.30.00.000000"));
        return s;
    }

    private Scenario scenarioEmptyInput() {
        Scenario s = new Scenario();
        s.startDate = "2026-04-01";
        s.endDate = "2026-04-30";
        return s;
    }

    // ── Inner data types ─────────────────────────────────────────────────

    private static class Scenario {
        String startDate = "";
        String endDate = "";
        final Map<String, TranTypeRecord> tranTypes = new HashMap<>();
        final Map<TranCatgKey, TranCatgRecord> tranCatgs = new HashMap<>();
        final List<TranRecord> transactions = new ArrayList<>();
    }

    static class TranRecord {
        final String tranId;
        final String tranTypeCd;
        final int tranCatCd;
        final String tranDesc;
        final BigDecimal tranAmt;
        final String tranCardNum;
        final String tranProcTs;

        TranRecord(String tranId, String tranTypeCd, int tranCatCd,
                   String tranDesc, BigDecimal tranAmt, String tranCardNum,
                   String tranProcTs) {
            this.tranId = tranId;
            this.tranTypeCd = tranTypeCd;
            this.tranCatCd = tranCatCd;
            this.tranDesc = tranDesc;
            this.tranAmt = tranAmt;
            this.tranCardNum = tranCardNum;
            this.tranProcTs = tranProcTs;
        }
    }

    static class TranTypeRecord {
        final String tranType;
        final String tranTypeDesc;

        TranTypeRecord(String tranType, String tranTypeDesc) {
            this.tranType = tranType;
            this.tranTypeDesc = tranTypeDesc;
        }
    }

    static class TranCatgKey {
        final String typeCd;
        final int catCd;

        TranCatgKey(String typeCd, int catCd) {
            this.typeCd = typeCd;
            this.catCd = catCd;
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof TranCatgKey)) return false;
            TranCatgKey k = (TranCatgKey) o;
            return catCd == k.catCd && typeCd.equals(k.typeCd);
        }

        @Override
        public int hashCode() {
            return 31 * typeCd.hashCode() + catCd;
        }
    }

    static class TranCatgRecord {
        final String tranTypeCd;
        final int tranCatCd;
        final String tranCatgDesc;

        TranCatgRecord(String typeCd, int catCd, String catgDesc) {
            this.tranTypeCd = typeCd;
            this.tranCatCd = catCd;
            this.tranCatgDesc = catgDesc;
        }
    }

    static class ReportResult {
        final List<String> reportLines = new ArrayList<>();
        int recordsRead = 0;
        int recordsReported = 0;
        BigDecimal grandTotal = BD_0_00;
        int pageCount = 0;
    }
}
