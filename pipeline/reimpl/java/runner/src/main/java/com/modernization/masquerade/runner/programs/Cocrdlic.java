package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.*;

/**
 * Java reimplementation of COCRDLIC — CardDemo Credit Card List Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/cocrdlic.py}. Python is the source of truth.
 *
 * <p>Standalone business method: {@link #processCardList}. The {@link #runVector}
 * method is a thin adapter that builds scenario-specific parameters and delegates.
 */
public class Cocrdlic implements ProgramRunner {

    private static final int PAGE_SIZE = 7;

    // ── Inner data types ─────────────────────────────────────────────────

    static class CardRecord {
        final String cardNum;
        final String acctId;
        final String embossedName;
        final String activeStatus;

        CardRecord(String cardNum, String acctId, String embossedName, String activeStatus) {
            this.cardNum = cardNum;
            this.acctId = acctId;
            this.embossedName = embossedName;
            this.activeStatus = activeStatus;
        }
    }

    static class CardListRow {
        final String cardNum;
        final String acctId;
        final String embossedName;
        final String activeStatus;

        CardListRow(String cardNum, String acctId, String embossedName, String activeStatus) {
            this.cardNum = cardNum;
            this.acctId = acctId;
            this.embossedName = embossedName;
            this.activeStatus = activeStatus;
        }
    }

    static class CardListResult {
        List<CardListRow> rows = new ArrayList<>();
        int pageNum = 1;
        boolean hasNext = false;
        boolean hasPrev = false;
        boolean error = false;
        String message = "";
        String xctlProgram = "";
        String selectedCardNum = "";
        String selectedAction = "";
        boolean returnToPrev = false;
    }

    static class CardRepo {
        private final List<CardRecord> all;

        CardRepo(List<CardRecord> cards) {
            this.all = new ArrayList<>(cards);
            this.all.sort(Comparator.comparing(c -> c.cardNum));
        }

        PageResult getPage(int pageNum, int acctFilter, String cardFilter) {
            List<CardRecord> filtered = all;
            if (acctFilter != 0) {
                List<CardRecord> tmp = new ArrayList<>();
                String af = String.valueOf(acctFilter);
                for (CardRecord c : all) {
                    if (c.acctId.equals(af)) tmp.add(c);
                }
                filtered = tmp;
            }
            if (cardFilter != null && !cardFilter.trim().isEmpty()) {
                String prefix = cardFilter.trim();
                List<CardRecord> tmp = new ArrayList<>();
                for (CardRecord c : filtered) {
                    if (c.cardNum.startsWith(prefix)) tmp.add(c);
                }
                filtered = tmp;
            }
            int start = (pageNum - 1) * PAGE_SIZE;
            int end = Math.min(start + PAGE_SIZE, filtered.size());
            List<CardRecord> page = (start < filtered.size())
                    ? filtered.subList(start, end) : new ArrayList<>();
            return new PageResult(page, filtered.size() > end);
        }
    }

    static class PageResult {
        final List<CardRecord> records;
        final boolean hasNext;
        PageResult(List<CardRecord> records, boolean hasNext) {
            this.records = records;
            this.hasNext = hasNext;
        }
    }

    // ── Standalone business method ──────────────────────────────────────

    /**
     * Process credit card list — mirrors Python's process_card_list.
     *
     * @param eibcalen     CICS EIBCALEN
     * @param eibaid       aid key pressed
     * @param pgmContext   commarea program context (0 = initial)
     * @param fromProgram  commarea cdemo_from_program
     * @param cardRepo     card repository
     * @param pageNum      current page number
     * @param acctFilter   account filter (0 = no filter)
     * @param cardFilter   card number prefix filter
     * @param selectedRows list of (selFlag, cardNum) pairs from screen
     * @return CardListResult with all output fields
     */
    CardListResult processCardList(
            int eibcalen,
            String eibaid,
            int pgmContext,
            String fromProgram,
            CardRepo cardRepo,
            int pageNum,
            int acctFilter,
            String cardFilter,
            List<String[]> selectedRows
    ) {
        CardListResult result = new CardListResult();

        if (eibcalen == 0) {
            result.returnToPrev = true;
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (pgmContext == 0) {
            return loadPage(pageNum, acctFilter, cardFilter, cardRepo, result);
        }

        switch (eibaid) {
            case "ENTER":
                return processEnter(selectedRows, pageNum, acctFilter, cardFilter, cardRepo, result);
            case "PF3": {
                String back = (fromProgram != null && !fromProgram.isEmpty()) ? fromProgram : "COMEN01C";
                result.xctlProgram = back;
                result.returnToPrev = true;
                return result;
            }
            case "PF7":
                return loadPage(Math.max(1, pageNum - 1), acctFilter, cardFilter, cardRepo, result);
            case "PF8":
                return loadPage(pageNum + 1, acctFilter, cardFilter, cardRepo, result);
            default:
                result.error = true;
                return loadPage(pageNum, acctFilter, cardFilter, cardRepo, result);
        }
    }

    private CardListResult loadPage(int pageNum, int acctFilter, String cardFilter,
                                     CardRepo repo, CardListResult result) {
        PageResult pr = repo.getPage(pageNum, acctFilter, cardFilter);
        result.pageNum = pageNum;
        result.hasNext = pr.hasNext;
        result.hasPrev = pageNum > 1;
        result.rows = new ArrayList<>();
        for (CardRecord c : pr.records) {
            result.rows.add(new CardListRow(
                    c.cardNum, c.acctId, c.embossedName.trim(), c.activeStatus));
        }
        if (pr.records.isEmpty()) {
            result.error = true;
            result.message = "NO RECORDS FOUND FOR THIS SEARCH CONDITION.";
        } else {
            result.message = "TYPE S FOR DETAIL, U TO UPDATE ANY RECORD";
        }
        return result;
    }

    private CardListResult processEnter(
            List<String[]> selectedRows, int pageNum, int acctFilter,
            String cardFilter, CardRepo repo, CardListResult result
    ) {
        // Collect valid selections
        List<String[]> selections = new ArrayList<>();
        if (selectedRows != null) {
            for (String[] sel : selectedRows) {
                String flag = sel[0];
                String cardNum = sel[1];
                if (flag != null && !flag.trim().isEmpty() && !flag.trim().equals("\0")
                        && cardNum != null && !cardNum.trim().isEmpty()) {
                    selections.add(sel);
                }
            }
        }

        if (selections.size() > 1) {
            result.error = true;
            result.message = "PLEASE SELECT ONLY ONE RECORD TO VIEW OR UPDATE";
            return loadPage(pageNum, acctFilter, cardFilter, repo, result);
        }

        if (!selections.isEmpty()) {
            String action = selections.get(0)[0].trim().toUpperCase();
            String cardNum = selections.get(0)[1].trim();

            if (!action.equals("S") && !action.equals("U")) {
                result.error = true;
                result.message = "INVALID ACTION CODE";
                return loadPage(pageNum, acctFilter, cardFilter, repo, result);
            }

            result.selectedCardNum = cardNum;
            result.selectedAction = action;

            if (action.equals("S")) {
                result.xctlProgram = "COCRDSLC";
            } else {
                result.xctlProgram = "COCRDUPC";
            }
            return result;
        }

        return loadPage(pageNum, acctFilter, cardFilter, repo, result);
    }

    // ── Seed data ───────────────────────────────────────────────────────

    private List<CardRecord> buildSeedCards() {
        List<CardRecord> list = new ArrayList<>();
        for (int i = 1; i <= 9; i++) {
            list.add(new CardRecord(
                    String.format("411111111111%04d", i),
                    "10000001",
                    String.format("TEST USER %04d", i),
                    "Y"
            ));
        }
        return list;
    }

    // ── Thin runVector adapter ──────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "FIRST_ENTRY");

        CardRepo repo = new CardRepo(buildSeedCards());
        List<String[]> noSelection = new ArrayList<>();

        CardListResult result;

        switch (scenario) {
            case "FIRST_ENTRY":
                result = processCardList(100, "ENTER", 0, "COMEN01C",
                        repo, 1, 0, "", noSelection);
                break;

            case "LIST_PAGE_1":
                result = processCardList(100, "ENTER", 1, "COMEN01C",
                        repo, 1, 0, "", noSelection);
                break;

            case "SELECT_VIEW": {
                List<String[]> sel = new ArrayList<>();
                sel.add(new String[]{"S", "4111111111110001"});
                result = processCardList(100, "ENTER", 1, "COMEN01C",
                        repo, 1, 0, "", sel);
                break;
            }

            case "SELECT_UPDATE": {
                List<String[]> sel = new ArrayList<>();
                sel.add(new String[]{"U", "4111111111110002"});
                result = processCardList(100, "ENTER", 1, "COMEN01C",
                        repo, 1, 0, "", sel);
                break;
            }

            case "PF3_RETURN":
                result = processCardList(100, "PF3", 1, "COMEN01C",
                        repo, 1, 0, "", noSelection);
                break;

            case "INVALID_KEY":
                result = processCardList(100, "PF9", 1, "COMEN01C",
                        repo, 1, 0, "", noSelection);
                break;

            default:
                result = processCardList(100, "ENTER", 0, "COMEN01C",
                        repo, 1, 0, "", noSelection);
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
        out.put("SELECTED_CARD_NUM", result.selectedCardNum);
        out.put("SELECTED_ACTION", result.selectedAction);
        out.put("RETURN_TO_PREV", result.returnToPrev ? "Y" : "N");

        for (int i = 0; i < result.rows.size(); i++) {
            CardListRow row = result.rows.get(i);
            out.put("ROW_" + i + "_CARD_NUM", row.cardNum);
            out.put("ROW_" + i + "_ACCT_ID", row.acctId);
            out.put("ROW_" + i + "_NAME", row.embossedName);
            out.put("ROW_" + i + "_STATUS", row.activeStatus);
        }
        return out;
    }
}
