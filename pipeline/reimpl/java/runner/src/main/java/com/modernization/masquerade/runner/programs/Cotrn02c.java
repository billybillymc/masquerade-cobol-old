package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.util.*;
import java.util.regex.Pattern;

/**
 * Java reimplementation of COTRN02C — CardDemo Add Transaction Screen (CICS online).
 *
 * <p>Mirrors {@code pipeline/reimpl/cotrn02c.py}. Python is the source of truth.
 *
 * <p>Standalone business method: {@link #processTranAdd}. The {@link #runVector}
 * method is a thin adapter that builds scenario-specific parameters and delegates.
 *
 * <p>NOTE: This is the CICS online cotrn02c, NOT the batch cbtrn02c.
 */
public class Cotrn02c implements ProgramRunner {

    private static final Pattern AMT_RE = Pattern.compile("^[+-]\\d{8}\\.\\d{2}$");
    private static final Pattern DATE_RE = Pattern.compile("^\\d{4}-\\d{2}-\\d{2}$");

    // ── Inner data types ─────────────────────────────────────────────────

    static class TranAddInput {
        String acctId = "";
        String cardNum = "";
        String typeCd = "";
        String catCd = "";
        String source = "";
        String desc = "";
        String amount = "";
        String origDate = "";
        String procDate = "";
        String merchantId = "";
        String merchantName = "";
        String merchantCity = "";
        String merchantZip = "";
        String confirm = "";

        TranAddInput() {}

        TranAddInput(String acctId, String cardNum, String typeCd, String catCd,
                     String source, String desc, String amount,
                     String origDate, String procDate,
                     String merchantId, String merchantName,
                     String merchantCity, String merchantZip, String confirm) {
            this.acctId = acctId;
            this.cardNum = cardNum;
            this.typeCd = typeCd;
            this.catCd = catCd;
            this.source = source;
            this.desc = desc;
            this.amount = amount;
            this.origDate = origDate;
            this.procDate = procDate;
            this.merchantId = merchantId;
            this.merchantName = merchantName;
            this.merchantCity = merchantCity;
            this.merchantZip = merchantZip;
            this.confirm = confirm;
        }
    }

    static class TranAddResult {
        String tranId = "";
        boolean error = false;
        boolean success = false;
        String message = "";
        String xctlProgram = "";
        String resolvedCardNum = "";
        String resolvedAcctId = "";
    }

    static class XrefRecord {
        final String cardNum;
        final int acctId;

        XrefRecord(String cardNum, int acctId) {
            this.cardNum = cardNum;
            this.acctId = acctId;
        }
    }

    static class XrefRepo {
        private final Map<String, XrefRecord> byCard = new LinkedHashMap<>();
        private final Map<Integer, XrefRecord> byAcct = new LinkedHashMap<>();

        XrefRepo(List<XrefRecord> xrefs) {
            for (XrefRecord x : xrefs) {
                byCard.put(x.cardNum.trim(), x);
                byAcct.put(x.acctId, x);
            }
        }

        XrefRecord findByCard(String cardNum) { return byCard.get(cardNum.trim()); }
        XrefRecord findByAcct(int acctId) { return byAcct.get(acctId); }
    }

    static class TranRepo {
        private final List<String> tranIds;

        TranRepo(List<String> existingIds) {
            this.tranIds = new ArrayList<>(existingIds);
            Collections.sort(this.tranIds);
        }

        String nextId() {
            if (tranIds.isEmpty()) return "0000000000000001";
            String lastId = tranIds.get(tranIds.size() - 1).trim();
            try {
                long next = Long.parseLong(lastId) + 1;
                return String.format("%016d", next);
            } catch (NumberFormatException e) {
                return "0000000000000001";
            }
        }

        String write(String tranId) {
            if (tranIds.contains(tranId)) return "Tran ID already exist...";
            tranIds.add(tranId);
            Collections.sort(tranIds);
            return "";
        }
    }

    // ── Standalone business method ──────────────────────────────────────

    /**
     * Process add transaction screen — mirrors Python's process_tran_add.
     *
     * @param eibcalen    CICS EIBCALEN
     * @param eibaid      aid key pressed
     * @param pgmContext  commarea program context (0 = initial)
     * @param fromProgram commarea cdemo_from_program
     * @param inp         transaction add input fields
     * @param tranRepo    transaction repository
     * @param xrefRepo    xref repository
     * @return TranAddResult with all output fields
     */
    TranAddResult processTranAdd(
            int eibcalen,
            String eibaid,
            int pgmContext,
            String fromProgram,
            TranAddInput inp,
            TranRepo tranRepo,
            XrefRepo xrefRepo
    ) {
        TranAddResult result = new TranAddResult();

        if (eibcalen == 0) {
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (pgmContext == 0) {
            // Initial entry — blank screen
            return result;
        }

        switch (eibaid) {
            case "ENTER":
                return processEnter(inp, tranRepo, xrefRepo, result);
            case "PF3": {
                String back = (fromProgram != null && !fromProgram.isEmpty()) ? fromProgram : "COMEN01C";
                result.xctlProgram = back;
                return result;
            }
            case "PF4":
                // Clear screen
                return result;
            case "PF5":
                // Copy last tran — not tested in harness scenarios
                return result;
            default:
                result.error = true;
                result.message = "Invalid key pressed.";
                return result;
        }
    }

    private TranAddResult processEnter(TranAddInput inp, TranRepo tranRepo,
                                        XrefRepo xrefRepo, TranAddResult result) {
        // Validate key fields
        if (!validateKeyFields(inp, xrefRepo, result)) return result;

        // Validate data fields
        if (!validateDataFields(inp, result)) return result;

        // Check confirmation
        String confirm = (inp.confirm != null) ? inp.confirm.trim().toUpperCase() : "";
        if (confirm.equals("Y")) {
            return addTransaction(inp, tranRepo, result);
        } else if (confirm.equals("N") || confirm.isEmpty()) {
            result.error = true;
            result.message = "Confirm to add this transaction...";
            return result;
        } else {
            result.error = true;
            result.message = "Invalid value. Valid values are (Y/N)...";
            return result;
        }
    }

    private boolean validateKeyFields(TranAddInput inp, XrefRepo xrefRepo, TranAddResult result) {
        String acctS = (inp.acctId != null) ? inp.acctId.trim() : "";
        String cardS = (inp.cardNum != null) ? inp.cardNum.trim() : "";

        if (!acctS.isEmpty()) {
            if (!acctS.matches("\\d+")) {
                result.error = true;
                result.message = "Account ID must be Numeric...";
                return false;
            }
            XrefRecord xref = xrefRepo.findByAcct(Integer.parseInt(acctS));
            if (xref == null) {
                result.error = true;
                result.message = "Account ID NOT found...";
                return false;
            }
            result.resolvedAcctId = acctS;
            result.resolvedCardNum = xref.cardNum.trim();
            return true;
        } else if (!cardS.isEmpty()) {
            if (!cardS.matches("\\d+")) {
                result.error = true;
                result.message = "Card Number must be Numeric...";
                return false;
            }
            XrefRecord xref = xrefRepo.findByCard(cardS);
            if (xref == null) {
                result.error = true;
                result.message = "Card Number NOT found...";
                return false;
            }
            result.resolvedCardNum = cardS;
            result.resolvedAcctId = String.valueOf(xref.acctId);
            return true;
        } else {
            result.error = true;
            result.message = "Account or Card Number must be entered...";
            return false;
        }
    }

    private boolean validateDataFields(TranAddInput inp, TranAddResult result) {
        String[][] checks = {
                {inp.typeCd, "Type CD can NOT be empty..."},
                {inp.catCd, "Category CD can NOT be empty..."},
                {inp.source, "Source can NOT be empty..."},
                {inp.desc, "Description can NOT be empty..."},
                {inp.amount, "Amount can NOT be empty..."},
                {inp.origDate, "Orig Date can NOT be empty..."},
                {inp.procDate, "Proc Date can NOT be empty..."},
                {inp.merchantId, "Merchant ID can NOT be empty..."},
                {inp.merchantName, "Merchant Name can NOT be empty..."},
                {inp.merchantCity, "Merchant City can NOT be empty..."},
                {inp.merchantZip, "Merchant Zip can NOT be empty..."},
        };
        for (String[] check : checks) {
            if (check[0] == null || check[0].trim().isEmpty()) {
                result.error = true;
                result.message = check[1];
                return false;
            }
        }

        if (!inp.typeCd.trim().matches("\\d+")) {
            result.error = true;
            result.message = "Type CD must be Numeric...";
            return false;
        }
        if (!inp.catCd.trim().matches("\\d+")) {
            result.error = true;
            result.message = "Category CD must be Numeric...";
            return false;
        }
        if (!AMT_RE.matcher(inp.amount.trim()).matches()) {
            result.error = true;
            result.message = "Amount should be in format -99999999.99";
            return false;
        }
        if (!DATE_RE.matcher(inp.origDate.trim()).matches()) {
            result.error = true;
            result.message = "Orig Date should be in format YYYY-MM-DD";
            return false;
        }
        if (!DATE_RE.matcher(inp.procDate.trim()).matches()) {
            result.error = true;
            result.message = "Proc Date should be in format YYYY-MM-DD";
            return false;
        }

        // Validate dates are real dates
        if (!isValidDate(inp.origDate.trim())) {
            result.error = true;
            result.message = "Orig Date - Not a valid date...";
            return false;
        }
        if (!isValidDate(inp.procDate.trim())) {
            result.error = true;
            result.message = "Proc Date - Not a valid date...";
            return false;
        }

        if (!inp.merchantId.trim().matches("\\d+")) {
            result.error = true;
            result.message = "Merchant ID must be Numeric...";
            return false;
        }

        return true;
    }

    private boolean isValidDate(String dateStr) {
        try {
            String[] parts = dateStr.split("-");
            int year = Integer.parseInt(parts[0]);
            int month = Integer.parseInt(parts[1]);
            int day = Integer.parseInt(parts[2]);
            if (month < 1 || month > 12) return false;
            int[] daysInMonth = {0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
            if ((year % 4 == 0 && year % 100 != 0) || year % 400 == 0) {
                daysInMonth[2] = 29;
            }
            return day >= 1 && day <= daysInMonth[month];
        } catch (Exception e) {
            return false;
        }
    }

    private TranAddResult addTransaction(TranAddInput inp, TranRepo tranRepo, TranAddResult result) {
        try {
            new BigDecimal(inp.amount.trim());
        } catch (NumberFormatException e) {
            result.error = true;
            result.message = "Invalid amount value";
            return result;
        }

        String newId = tranRepo.nextId();
        String err = tranRepo.write(newId);
        if (!err.isEmpty()) {
            result.error = true;
            result.message = err;
        } else {
            result.success = true;
            result.tranId = newId;
            result.message = "Transaction added successfully.  Your Tran ID is " + newId.trim() + ".";
        }
        return result;
    }

    // ── Seed data ───────────────────────────────────────────────────────

    private static final List<XrefRecord> SEED_XREFS = Arrays.asList(
            new XrefRecord("4111111111111111", 10000001),
            new XrefRecord("4222222222222222", 10000002)
    );

    // ── Thin runVector adapter ──────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "ADD_SUCCESS");

        TranRepo tranRepo = new TranRepo(new ArrayList<>(Arrays.asList("0000000000000001")));
        XrefRepo xrefRepo = new XrefRepo(new ArrayList<>(SEED_XREFS));

        TranAddResult result;

        switch (scenario) {
            case "ADD_SUCCESS":
                result = processTranAdd(100, "ENTER", 1, "COMEN01C",
                        new TranAddInput("10000001", "", "01", "1",
                                "ONLINE", "NEW PURCHASE", "+00000100.00",
                                "2025-03-15", "2025-03-15",
                                "100001", "TEST MERCHANT", "BOSTON", "02101", "Y"),
                        tranRepo, xrefRepo);
                break;

            case "ACCT_NOT_FOUND":
                result = processTranAdd(100, "ENTER", 1, "COMEN01C",
                        new TranAddInput("99999999", "", "01", "1",
                                "ONLINE", "TEST", "+00000050.00",
                                "2025-03-15", "2025-03-15",
                                "100001", "TEST", "NYC", "10001", "Y"),
                        tranRepo, xrefRepo);
                break;

            case "MISSING_FIELDS":
                result = processTranAdd(100, "ENTER", 1, "COMEN01C",
                        new TranAddInput("10000001", "", "01", "1",
                                "ONLINE", "", "+00000050.00",
                                "2025-03-15", "2025-03-15",
                                "100001", "TEST", "NYC", "10001", "Y"),
                        tranRepo, xrefRepo);
                break;

            case "INVALID_AMOUNT":
                result = processTranAdd(100, "ENTER", 1, "COMEN01C",
                        new TranAddInput("10000001", "", "01", "1",
                                "ONLINE", "TEST", "BADAMT",
                                "2025-03-15", "2025-03-15",
                                "100001", "TEST", "NYC", "10001", "Y"),
                        tranRepo, xrefRepo);
                break;

            case "INVALID_DATE":
                result = processTranAdd(100, "ENTER", 1, "COMEN01C",
                        new TranAddInput("10000001", "", "01", "1",
                                "ONLINE", "TEST", "+00000050.00",
                                "2025-13-45", "2025-03-15",
                                "100001", "TEST", "NYC", "10001", "Y"),
                        tranRepo, xrefRepo);
                break;

            case "CONFIRM_PENDING":
                result = processTranAdd(100, "ENTER", 1, "COMEN01C",
                        new TranAddInput("10000001", "", "01", "1",
                                "ONLINE", "TEST", "+00000050.00",
                                "2025-03-15", "2025-03-15",
                                "100001", "TEST", "NYC", "10001", ""),
                        tranRepo, xrefRepo);
                break;

            default:
                result = processTranAdd(100, "ENTER", 1, "COMEN01C",
                        new TranAddInput("10000001", "", "01", "1",
                                "ONLINE", "NEW PURCHASE", "+00000100.00",
                                "2025-03-15", "2025-03-15",
                                "100001", "TEST MERCHANT", "BOSTON", "02101", "Y"),
                        tranRepo, xrefRepo);
                break;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("SUCCESS", result.success ? "Y" : "N");
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("TRAN_ID", result.tranId);
        out.put("XCTL_PROGRAM", result.xctlProgram);
        return out;
    }
}
