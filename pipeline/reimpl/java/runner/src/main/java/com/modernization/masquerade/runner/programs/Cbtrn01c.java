package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Java reimplementation of CardDemo batch program CBTRN01C — Daily Transaction Validation.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbtrn01c.py} byte-for-byte. Python is the
 * source of truth.
 */
public class Cbtrn01c implements ProgramRunner {

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "PROCESS_RECORDS").toUpperCase();
        Scenario scn = buildScenario(scenarioName);
        if (scn == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }

        List<String> displayLines = new ArrayList<>();
        int recordsRead = 0;
        int successfulLookups = 0;
        int failedXref = 0;
        int failedAccount = 0;

        for (DalyTranRecord tran : scn.transactions) {
            recordsRead++;
            String line = tran.toString();
            displayLines.add(line);

            // 2000-LOOKUP-XREF
            CardXrefRecord xref = scn.xrefs.get(tran.tranCardNum);
            if (xref == null) {
                String msg = "CARD NUMBER " + tran.tranCardNum
                        + " COULD NOT BE VERIFIED. SKIPPING TRANSACTION ID-"
                        + tran.tranId;
                displayLines.add(msg);
                failedXref++;
            } else {
                displayLines.add("SUCCESSFUL READ OF XREF");
                displayLines.add("CARD NUMBER: " + xref.xrefCardNum);
                displayLines.add("ACCOUNT ID : " + xref.xrefAcctId);
                displayLines.add("CUSTOMER ID: " + xref.xrefCustId);

                // 3000-READ-ACCOUNT
                AccountRecord account = scn.accounts.get(xref.xrefAcctId);
                if (account == null) {
                    String msg = "ACCOUNT " + xref.xrefAcctId + " NOT FOUND";
                    displayLines.add(msg);
                    failedAccount++;
                } else {
                    displayLines.add("SUCCESSFUL READ OF ACCOUNT FILE");
                    successfulLookups++;
                }
            }
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("RECORDS_READ", String.valueOf(recordsRead));
        out.put("SUCCESSFUL_LOOKUPS", String.valueOf(successfulLookups));
        out.put("FAILED_XREF", String.valueOf(failedXref));
        out.put("FAILED_ACCOUNT", String.valueOf(failedAccount));
        for (int i = 0; i < displayLines.size(); i++) {
            out.put("DISPLAY_" + i, displayLines.get(i));
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
        s.xrefs.put("4111000000001111",
                new CardXrefRecord("4111000000001111", 1, 100000001));
        s.accounts.put(100000001,
                new AccountRecord(100000001, "Y"));
        s.transactions.add(makeTran("TRN0000000000001", "4111000000001111",
                "01", 1, 150.25));
        s.transactions.add(makeTran("TRN0000000000002", "9999999999999999",
                "01", 1, 50.00));
        return s;
    }

    private Scenario scenarioEmptyInput() {
        return new Scenario();
    }

    private static DalyTranRecord makeTran(String id, String cardNum,
                                            String typeCd, int catCd, double amt) {
        DalyTranRecord t = new DalyTranRecord();
        t.tranId = id;
        t.tranCardNum = cardNum;
        t.tranTypeCd = typeCd;
        t.tranCatCd = catCd;
        t.tranAmt = amt;
        return t;
    }

    // ── Inner data types ─────────────────────────────────────────────────

    private static class Scenario {
        final Map<String, CardXrefRecord> xrefs = new HashMap<>();
        final Map<Integer, AccountRecord> accounts = new HashMap<>();
        final List<DalyTranRecord> transactions = new ArrayList<>();
    }

    static class DalyTranRecord {
        String tranId = "";
        String tranTypeCd = "";
        int tranCatCd = 0;
        String tranSource = "";
        String tranDesc = "";
        double tranAmt = 0.0;
        int tranMerchantId = 0;
        String tranMerchantName = "";
        String tranMerchantCity = "";
        String tranMerchantZip = "";
        String tranCardNum = "";
        String tranOrigTs = "";
        String tranProcTs = "";

        @Override
        public String toString() {
            return "DalyTranRecord(tran_id='" + tranId
                    + "', tran_type_cd='" + tranTypeCd
                    + "', tran_cat_cd=" + tranCatCd
                    + ", tran_source='" + tranSource
                    + "', tran_desc='" + tranDesc
                    + "', tran_amt=" + tranAmt
                    + ", tran_merchant_id=" + tranMerchantId
                    + ", tran_merchant_name='" + tranMerchantName
                    + "', tran_merchant_city='" + tranMerchantCity
                    + "', tran_merchant_zip='" + tranMerchantZip
                    + "', tran_card_num='" + tranCardNum
                    + "', tran_orig_ts='" + tranOrigTs
                    + "', tran_proc_ts='" + tranProcTs + "')";
        }
    }

    static class CardXrefRecord {
        final String xrefCardNum;
        final int xrefCustId;
        final int xrefAcctId;

        CardXrefRecord(String cardNum, int custId, int acctId) {
            this.xrefCardNum = cardNum;
            this.xrefCustId = custId;
            this.xrefAcctId = acctId;
        }
    }

    static class AccountRecord {
        final int acctId;
        final String acctActiveStatus;

        AccountRecord(int acctId, String activeStatus) {
            this.acctId = acctId;
            this.acctActiveStatus = activeStatus;
        }
    }
}
