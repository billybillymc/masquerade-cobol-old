package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of COTRN01C — CardDemo Transaction View Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/cotrn01c.py}. Python is the source of truth.
 *
 * <p>Standalone business method: {@link #processTranView}. The {@link #runVector}
 * method is a thin adapter that builds scenario-specific parameters and delegates.
 */
public class Cotrn01c implements ProgramRunner {

    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    ";

    // ── Inner data types ─────────────────────────────────────────────────

    static class TranRecord {
        final String tranId;
        final String tranTypeCd;
        final String tranAmt;
        final String tranDesc;
        final String tranCardNum;
        final String tranMerchantName;

        TranRecord(String tranId, String tranTypeCd, String tranAmt,
                   String tranDesc, String tranCardNum, String tranMerchantName) {
            this.tranId = tranId;
            this.tranTypeCd = tranTypeCd;
            this.tranAmt = tranAmt;
            this.tranDesc = tranDesc;
            this.tranCardNum = tranCardNum;
            this.tranMerchantName = tranMerchantName;
        }
    }

    static class TranViewResult {
        TranRecord tranRecord = null;
        boolean error = false;
        String message = "";
        String xctlProgram = "";
        boolean cleared = false;
    }

    static class TranRepo {
        private final Map<String, TranRecord> trans;
        TranRepo(Map<String, TranRecord> trans) { this.trans = trans; }

        TranRecord find(String tranId) {
            return trans.get(tranId.trim());
        }
    }

    // ── Standalone business method ──────────────────────────────────────

    /**
     * Process transaction view screen — mirrors Python's process_tran_view.
     *
     * @param eibcalen        CICS EIBCALEN
     * @param eibaid          aid key pressed
     * @param pgmContext      commarea program context (0 = initial)
     * @param fromProgram     commarea cdemo_from_program
     * @param tranIdInput     transaction ID typed by user
     * @param preloadedTranId transaction ID preloaded from previous screen
     * @param tranRepo        transaction repository
     * @return TranViewResult with all output fields
     */
    TranViewResult processTranView(
            int eibcalen,
            String eibaid,
            int pgmContext,
            String fromProgram,
            String tranIdInput,
            String preloadedTranId,
            TranRepo tranRepo
    ) {
        TranViewResult result = new TranViewResult();

        if (eibcalen == 0) {
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (pgmContext == 0) {
            if (preloadedTranId != null && !preloadedTranId.trim().isEmpty()) {
                lookupTran(preloadedTranId, tranRepo, result);
            }
            return result;
        }

        switch (eibaid) {
            case "ENTER":
                return processEnter(tranIdInput, tranRepo, result);
            case "PF3": {
                String back = (fromProgram != null && !fromProgram.isEmpty()) ? fromProgram : "COMEN01C";
                result.xctlProgram = back;
                return result;
            }
            case "PF4":
                result.cleared = true;
                return result;
            case "PF5":
                result.xctlProgram = "COTRN00C";
                return result;
            default:
                result.error = true;
                result.message = CCDA_MSG_INVALID_KEY;
                return result;
        }
    }

    private TranViewResult processEnter(String tranIdInput, TranRepo repo, TranViewResult result) {
        if (tranIdInput == null || tranIdInput.trim().isEmpty()) {
            result.error = true;
            result.message = "Tran ID can NOT be empty...";
            return result;
        }
        lookupTran(tranIdInput, repo, result);
        return result;
    }

    private void lookupTran(String tranId, TranRepo repo, TranViewResult result) {
        TranRecord tran = repo.find(tranId);
        if (tran == null) {
            result.error = true;
            result.message = "Transaction ID NOT found...";
        } else {
            result.tranRecord = tran;
            result.message = "";
        }
    }

    // ── Seed data ───────────────────────────────────────────────────────

    private static final Map<String, TranRecord> SEED_TRANS = new LinkedHashMap<>();
    static {
        SEED_TRANS.put("0000000000000001", new TranRecord(
                "0000000000000001", "01", "125.50", "PURCHASE AT STORE",
                "4111111111111111", "ACME STORE"));
        SEED_TRANS.put("0000000000000002", new TranRecord(
                "0000000000000002", "02", "500.00", "BILL PAYMENT",
                "4222222222222222", "UTILITY CO"));
    }

    // ── Thin runVector adapter ──────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "VIEW_FOUND");

        TranRepo repo = new TranRepo(new LinkedHashMap<>(SEED_TRANS));

        TranViewResult result;

        switch (scenario) {
            case "VIEW_FOUND":
                result = processTranView(100, "ENTER", 1, "COMEN01C",
                        "0000000000000001", "", repo);
                break;

            case "VIEW_NOT_FOUND":
                result = processTranView(100, "ENTER", 1, "COMEN01C",
                        "9999999999999999", "", repo);
                break;

            case "EMPTY_TRAN_ID":
                result = processTranView(100, "ENTER", 1, "COMEN01C",
                        "", "", repo);
                break;

            case "INVALID_KEY":
                result = processTranView(100, "PF9", 1, "COMEN01C",
                        "", "", repo);
                break;

            case "PF3_RETURN":
                result = processTranView(100, "PF3", 1, "COMEN01C",
                        "", "", repo);
                break;

            default:
                result = processTranView(100, "ENTER", 1, "COMEN01C",
                        "0000000000000001", "", repo);
                break;
        }

        String tranId = "";
        String tranType = "";
        String tranAmt = "";
        String tranDesc = "";
        String tranCard = "";
        String tranMerchant = "";
        if (result.tranRecord != null) {
            tranId = result.tranRecord.tranId;
            tranType = result.tranRecord.tranTypeCd;
            tranAmt = result.tranRecord.tranAmt;
            tranDesc = result.tranRecord.tranDesc;
            tranCard = result.tranRecord.tranCardNum;
            tranMerchant = result.tranRecord.tranMerchantName;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("XCTL_PROGRAM", result.xctlProgram);
        out.put("TRAN_ID", tranId);
        out.put("TRAN_TYPE", tranType);
        out.put("TRAN_AMT", tranAmt);
        out.put("TRAN_DESC", tranDesc);
        out.put("TRAN_CARD", tranCard);
        out.put("TRAN_MERCHANT", tranMerchant);
        return out;
    }
}
