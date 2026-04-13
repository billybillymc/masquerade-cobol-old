package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.util.*;

/**
 * Java reimplementation of COBIL00C — CardDemo Bill Payment Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/cobil00c.py}. Python is the source of truth.
 *
 * <p>Structure: standalone {@link #processBillPay} method + thin
 * {@link #runVector} adapter, matching the Python's
 * {@code process_bill_pay} / {@code run_vector} split.
 */
public class Cobil00c implements ProgramRunner {

    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    ";

    // ── Inner data types ────────────────────────────────────────────────────

    static class AccountRecord {
        int acctId;
        String acctActiveStatus;
        BigDecimal acctCurrBal;
        BigDecimal acctCreditLimit;

        AccountRecord(int acctId, String acctActiveStatus, BigDecimal acctCurrBal, BigDecimal acctCreditLimit) {
            this.acctId = acctId;
            this.acctActiveStatus = acctActiveStatus;
            this.acctCurrBal = acctCurrBal;
            this.acctCreditLimit = acctCreditLimit;
        }

        AccountRecord copy() {
            return new AccountRecord(acctId, acctActiveStatus,
                    new BigDecimal(acctCurrBal.toPlainString()),
                    new BigDecimal(acctCreditLimit.toPlainString()));
        }
    }

    static class CardXrefRecord {
        String xrefCardNum;
        int xrefCustId;
        int xrefAcctId;

        CardXrefRecord(String xrefCardNum, int xrefCustId, int xrefAcctId) {
            this.xrefCardNum = xrefCardNum;
            this.xrefCustId = xrefCustId;
            this.xrefAcctId = xrefAcctId;
        }
    }

    static class TranRecord {
        String tranId;
        String tranTypeCd;
        int tranCatCd;
        String tranSource;
        String tranDesc;
        BigDecimal tranAmt;
        String tranCardNum;

        TranRecord(String tranId, String tranTypeCd, int tranCatCd, String tranSource,
                   String tranDesc, BigDecimal tranAmt, String tranCardNum) {
            this.tranId = tranId;
            this.tranTypeCd = tranTypeCd;
            this.tranCatCd = tranCatCd;
            this.tranSource = tranSource;
            this.tranDesc = tranDesc;
            this.tranAmt = tranAmt;
            this.tranCardNum = tranCardNum;
        }
    }

    static class BillPayResult {
        AccountRecord acctRecord = null;
        TranRecord tranRecord = null;
        String message = "";
        boolean error = false;
        boolean success = false;
        String xctlProgram = "";
        boolean returnToPrev = false;
        boolean cleared = false;
    }

    // ── Repositories ────────────────────────────────────────────────────────

    static class AccountRepository {
        private final Map<Integer, AccountRecord> accounts;

        AccountRepository(Map<Integer, AccountRecord> accounts) {
            this.accounts = new HashMap<>(accounts);
        }

        AccountRecord find(int acctId) {
            return accounts.get(acctId);
        }

        boolean rewrite(AccountRecord acct) {
            if (!accounts.containsKey(acct.acctId)) return false;
            accounts.put(acct.acctId, acct);
            return true;
        }
    }

    static class XrefRepository {
        private final Map<Integer, CardXrefRecord> byAcct;

        XrefRepository(Map<Integer, CardXrefRecord> byAcct) {
            this.byAcct = new HashMap<>(byAcct);
        }

        CardXrefRecord findByAcct(int acctId) {
            return byAcct.get(acctId);
        }
    }

    static class TranRepository {
        private final List<TranRecord> trans;

        TranRepository(List<TranRecord> trans) {
            this.trans = new ArrayList<>(trans);
            this.trans.sort(Comparator.comparing(t -> t.tranId));
        }

        String nextId() {
            if (trans.isEmpty()) return "0000000000000001";
            String lastId = trans.get(trans.size() - 1).tranId.trim();
            try {
                long next = Long.parseLong(lastId) + 1;
                return String.format("%016d", next);
            } catch (NumberFormatException e) {
                return "0000000000000001";
            }
        }

        boolean write(TranRecord tran) {
            trans.add(tran);
            trans.sort(Comparator.comparing(t -> t.tranId));
            return true;
        }
    }

    // ── Standalone business method ──────────────────────────────────────────

    /**
     * Process bill payment screen — mirrors {@code process_bill_pay} in
     * {@code pipeline/reimpl/cobil00c.py}.
     */
    BillPayResult processBillPay(
            int eibcalen, String eibaid, int pgmContext,
            String acctIdInput, String confirm,
            AccountRepository acctRepo, XrefRepository xrefRepo, TranRepository tranRepo) {

        BillPayResult result = new BillPayResult();

        if (eibcalen == 0) {
            result.returnToPrev = true;
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (pgmContext == 0) {
            // First re-entry — show blank bill pay screen
            return result;
        }

        if ("ENTER".equals(eibaid)) {
            return processEnter(acctIdInput, confirm, acctRepo, xrefRepo, tranRepo, result);
        } else if ("PF3".equals(eibaid)) {
            result.xctlProgram = "COMEN01C";
            result.returnToPrev = true;
            return result;
        } else if ("PF4".equals(eibaid)) {
            result.cleared = true;
            return result;
        } else {
            result.error = true;
            result.message = CCDA_MSG_INVALID_KEY;
            return result;
        }
    }

    private BillPayResult processEnter(
            String acctIdInput, String confirm,
            AccountRepository acctRepo, XrefRepository xrefRepo, TranRepository tranRepo,
            BillPayResult result) {

        if (acctIdInput == null || acctIdInput.trim().isEmpty()) {
            result.error = true;
            result.message = "Acct ID can NOT be empty...";
            return result;
        }

        int acctId;
        try {
            acctId = Integer.parseInt(acctIdInput.trim());
        } catch (NumberFormatException e) {
            result.error = true;
            result.message = "Acct ID must be numeric...";
            return result;
        }

        String conf = confirm != null ? confirm.trim().toUpperCase() : "";

        if ("N".equals(conf)) {
            result.cleared = true;
            result.error = true;
            return result;
        } else if (!conf.isEmpty() && !"\u0000".equals(conf) && !"Y".equals(conf)) {
            result.error = true;
            result.message = "Invalid value. Valid values are (Y/N)...";
            return result;
        }

        AccountRecord acct = acctRepo.find(acctId);
        if (acct == null) {
            result.error = true;
            result.message = "Account " + acctId + " not found...";
            return result;
        }

        result.acctRecord = acct;

        if (acct.acctCurrBal.compareTo(BigDecimal.ZERO) <= 0) {
            result.error = true;
            result.message = "You have nothing to pay...";
            return result;
        }

        if ("Y".equals(conf)) {
            CardXrefRecord xref = xrefRepo.findByAcct(acctId);
            String cardNum = xref != null ? xref.xrefCardNum.trim() : "";

            TranRecord tran = new TranRecord(
                    tranRepo.nextId(), "02", 2, "POS TERM",
                    "BILL PAYMENT - ONLINE", acct.acctCurrBal, cardNum);
            tranRepo.write(tran);
            acct.acctCurrBal = acct.acctCurrBal.subtract(tran.tranAmt);
            acctRepo.rewrite(acct);

            result.success = true;
            result.tranRecord = tran;
            result.message = "Bill payment successful.";
        } else {
            result.message = "Confirm to make a bill payment...";
        }

        return result;
    }

    // ── runVector adapter ───────────────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "PAY_SUCCESS");

        // Seed data
        Map<Integer, AccountRecord> seedAccounts = new HashMap<>();
        seedAccounts.put(10000001, new AccountRecord(10000001, "Y",
                new BigDecimal("1500.00"), new BigDecimal("5000.00")));
        seedAccounts.put(10000002, new AccountRecord(10000002, "Y",
                BigDecimal.ZERO, new BigDecimal("3000.00")));

        AccountRepository acctRepo = new AccountRepository(seedAccounts);

        Map<Integer, CardXrefRecord> seedXrefs = new HashMap<>();
        seedXrefs.put(10000001, new CardXrefRecord("4111111111111111", 1, 10000001));
        XrefRepository xrefRepo = new XrefRepository(seedXrefs);

        List<TranRecord> seedTrans = new ArrayList<>();
        seedTrans.add(new TranRecord("0000000000000001", "01", 1, "ONLINE",
                "PURCHASE", new BigDecimal("50.00"), "4111111111111111"));
        TranRepository tranRepo = new TranRepository(seedTrans);

        BillPayResult result;

        switch (scenario) {
            case "PAY_SUCCESS":
                result = processBillPay(100, "ENTER", 1,
                        "10000001", "Y", acctRepo, xrefRepo, tranRepo);
                break;
            case "ACCT_NOT_FOUND":
                result = processBillPay(100, "ENTER", 1,
                        "99999999", "", acctRepo, xrefRepo, tranRepo);
                break;
            case "ZERO_BALANCE":
                result = processBillPay(100, "ENTER", 1,
                        "10000002", "", acctRepo, xrefRepo, tranRepo);
                break;
            case "EMPTY_ACCT_ID":
                result = processBillPay(100, "ENTER", 1,
                        "", "", acctRepo, xrefRepo, tranRepo);
                break;
            case "CONFIRM_NO":
                result = processBillPay(100, "ENTER", 1,
                        "10000001", "N", acctRepo, xrefRepo, tranRepo);
                break;
            case "INVALID_KEY":
                result = processBillPay(100, "PF9", 1,
                        "", "", acctRepo, xrefRepo, tranRepo);
                break;
            default:
                result = processBillPay(100, "ENTER", 1,
                        "10000001", "Y", acctRepo, xrefRepo, tranRepo);
                break;
        }

        String tranId = "";
        String tranAmt = "";
        if (result.tranRecord != null) {
            tranId = result.tranRecord.tranId;
            tranAmt = result.tranRecord.tranAmt.toPlainString();
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("SUCCESS", result.success ? "Y" : "N");
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("TRAN_ID", tranId);
        out.put("TRAN_AMT", tranAmt);
        out.put("XCTL_PROGRAM", result.xctlProgram != null ? result.xctlProgram : "");
        return out;
    }
}
