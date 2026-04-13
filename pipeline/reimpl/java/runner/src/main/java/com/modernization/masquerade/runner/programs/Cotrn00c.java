package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Java reimplementation of COTRN00C — CardDemo Transaction List Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/cotrn00c.py}. Python is the source of truth.
 *
 * <p>Standalone business method: {@link #processTranList}. The {@link #runVector}
 * method is a thin adapter that builds scenario-specific parameters and delegates.
 */
public class Cotrn00c implements ProgramRunner {

    private static final int PAGE_SIZE = 10;
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    ";

    // ── Inner data types ─────────────────────────────────────────────────

    static class TranRecord {
        final String tranId;
        final String tranTypeCd;
        final String tranDesc;
        final BigDecimal tranAmt;
        final String tranCardNum;
        final String tranProcTs;

        TranRecord(String tranId, String tranTypeCd, String tranDesc,
                   BigDecimal tranAmt, String tranCardNum, String tranProcTs) {
            this.tranId = tranId;
            this.tranTypeCd = tranTypeCd;
            this.tranDesc = tranDesc;
            this.tranAmt = tranAmt;
            this.tranCardNum = tranCardNum;
            this.tranProcTs = tranProcTs;
        }
    }

    static class TranListRow {
        final String tranId;
        final String tranDesc;
        final BigDecimal tranAmt;

        TranListRow(String tranId, String tranDesc, BigDecimal tranAmt) {
            this.tranId = tranId;
            this.tranDesc = tranDesc;
            this.tranAmt = tranAmt;
        }
    }

    static class TranListResult {
        List<TranListRow> rows = new ArrayList<>();
        int pageNum = 1;
        boolean hasNext = false;
        boolean hasPrev = false;
        boolean error = false;
        String message = "";
        String xctlProgram = "";
        String selectedTranId = "";
    }

    static class TranRepo {
        private final List<TranRecord> trans;

        TranRepo(List<TranRecord> trans) {
            this.trans = trans;
            this.trans.sort((a, b) -> a.tranId.compareTo(b.tranId));
        }

        /** Return page rows and whether there is a next page. */
        PageResult getPage(int pageNum) {
            int start = (pageNum - 1) * PAGE_SIZE;
            int end = Math.min(start + PAGE_SIZE, trans.size());
            List<TranRecord> page = (start < trans.size())
                    ? trans.subList(start, end) : new ArrayList<>();
            return new PageResult(page, trans.size() > end);
        }
    }

    static class PageResult {
        final List<TranRecord> records;
        final boolean hasNext;
        PageResult(List<TranRecord> records, boolean hasNext) {
            this.records = records;
            this.hasNext = hasNext;
        }
    }

    // ── Standalone business method ──────────────────────────────────────

    /**
     * Process transaction list screen — mirrors Python's process_tran_list.
     *
     * @param eibcalen     CICS EIBCALEN
     * @param eibaid       aid key pressed
     * @param pgmContext   commarea program context (0 = initial)
     * @param fromProgram  commarea cdemo_from_program
     * @param tranRepo     transaction repository
     * @param pageNum      current page number
     * @param selectedRows list of (selFlag, tranId) pairs from screen
     * @return TranListResult with all output fields
     */
    TranListResult processTranList(
            int eibcalen,
            String eibaid,
            int pgmContext,
            String fromProgram,
            TranRepo tranRepo,
            int pageNum,
            List<String[]> selectedRows
    ) {
        TranListResult result = new TranListResult();

        if (eibcalen == 0) {
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (pgmContext == 0) {
            return loadPage(1, tranRepo, result);
        }

        switch (eibaid) {
            case "ENTER":
                return processEnter(selectedRows, pageNum, tranRepo, result);
            case "PF3": {
                String back = (fromProgram != null && !fromProgram.isEmpty()) ? fromProgram : "COMEN01C";
                result.xctlProgram = back;
                return result;
            }
            case "PF7":
                return loadPage(Math.max(1, pageNum - 1), tranRepo, result);
            case "PF8":
                return loadPage(pageNum + 1, tranRepo, result);
            default:
                result.error = true;
                result.message = CCDA_MSG_INVALID_KEY;
                return loadPage(pageNum, tranRepo, result);
        }
    }

    private TranListResult loadPage(int pageNum, TranRepo repo, TranListResult result) {
        PageResult pr = repo.getPage(pageNum);
        result.pageNum = pageNum;
        result.hasNext = pr.hasNext;
        result.hasPrev = pageNum > 1;
        result.rows = new ArrayList<>();
        for (TranRecord t : pr.records) {
            String desc = t.tranDesc.length() > 40 ? t.tranDesc.substring(0, 40) : t.tranDesc;
            result.rows.add(new TranListRow(t.tranId, desc, t.tranAmt));
        }
        return result;
    }

    private TranListResult processEnter(
            List<String[]> selectedRows, int pageNum,
            TranRepo repo, TranListResult result
    ) {
        if (selectedRows != null) {
            for (String[] sel : selectedRows) {
                String selFlag = sel[0];
                String tranId = sel[1];
                if (selFlag != null && !selFlag.trim().isEmpty()
                        && !selFlag.trim().equals("\0")
                        && tranId != null && !tranId.trim().isEmpty()) {
                    result.selectedTranId = tranId.trim();
                    result.xctlProgram = "COTRN01C";
                    return result;
                }
            }
        }
        return loadPage(pageNum, repo, result);
    }

    // ── Seed data ───────────────────────────────────────────────────────

    private static final int SEED_COUNT = 12;

    private List<TranRecord> buildSeedTrans() {
        List<TranRecord> list = new ArrayList<>();
        for (int i = 1; i <= SEED_COUNT; i++) {
            list.add(new TranRecord(
                    String.format("%016d", i),
                    "01",
                    String.format("PURCHASE %04d", i),
                    new BigDecimal(i * 10),
                    "4111111111111111",
                    "2025-01-15-10.30.00.000000"
            ));
        }
        return list;
    }

    // ── Thin runVector adapter ──────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "LIST_PAGE_1");

        TranRepo repo = new TranRepo(buildSeedTrans());
        List<String[]> noSelection = new ArrayList<>();

        TranListResult result;

        switch (scenario) {
            case "LIST_PAGE_1":
                result = processTranList(100, "ENTER", 1, "COMEN01C",
                        repo, 1, noSelection);
                break;

            case "LIST_PAGE_2":
                result = processTranList(100, "PF8", 1, "COMEN01C",
                        repo, 1, noSelection);
                break;

            case "SELECT_TRAN": {
                List<String[]> sel = new ArrayList<>();
                sel.add(new String[]{"S", "0000000000000003"});
                result = processTranList(100, "ENTER", 1, "COMEN01C",
                        repo, 1, sel);
                break;
            }

            case "INVALID_KEY":
                result = processTranList(100, "PF9", 1, "COMEN01C",
                        repo, 1, noSelection);
                break;

            case "PF3_RETURN":
                result = processTranList(100, "PF3", 1, "COMEN01C",
                        repo, 1, noSelection);
                break;

            default:
                result = processTranList(100, "ENTER", 1, "COMEN01C",
                        repo, 1, noSelection);
                break;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("PAGE_NUM", String.valueOf(result.pageNum));
        out.put("ROW_COUNT", String.valueOf(result.rows.size()));
        out.put("HAS_NEXT", result.hasNext ? "Y" : "N");
        out.put("HAS_PREV", result.hasPrev ? "Y" : "N");
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("XCTL_PROGRAM", result.xctlProgram);
        out.put("SELECTED_TRAN_ID", result.selectedTranId);

        for (int i = 0; i < result.rows.size(); i++) {
            TranListRow row = result.rows.get(i);
            out.put("ROW_" + i + "_TRAN_ID", row.tranId);
            out.put("ROW_" + i + "_AMT", String.format("%.2f", row.tranAmt));
            out.put("ROW_" + i + "_DESC", row.tranDesc);
        }

        return out;
    }
}
