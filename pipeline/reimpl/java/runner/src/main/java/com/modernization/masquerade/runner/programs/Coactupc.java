package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.util.*;

/**
 * Java reimplementation of COACTUPC — CardDemo Account Update Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/coactupc.py}. Python is the source of truth.
 *
 * <p>Structure: standalone {@link #processAccountUpdate} method + thin
 * {@link #runVector} adapter.
 */
public class Coactupc implements ProgramRunner {

    // ── Inner data types ────────────────────────────────────────────────────

    static class AccountRecord {
        int acctId;
        String acctActiveStatus;
        BigDecimal acctCurrBal;
        BigDecimal acctCreditLimit;
        BigDecimal acctCashCreditLimit;
        String acctOpenDate;
        String acctExpirationDate;
        String acctReissueDate;
        String acctGroupId;

        AccountRecord(int acctId, String acctActiveStatus, BigDecimal acctCurrBal,
                      BigDecimal acctCreditLimit, BigDecimal acctCashCreditLimit,
                      String acctOpenDate, String acctExpirationDate) {
            this.acctId = acctId;
            this.acctActiveStatus = acctActiveStatus;
            this.acctCurrBal = acctCurrBal;
            this.acctCreditLimit = acctCreditLimit;
            this.acctCashCreditLimit = acctCashCreditLimit;
            this.acctOpenDate = acctOpenDate != null ? acctOpenDate : "";
            this.acctExpirationDate = acctExpirationDate != null ? acctExpirationDate : "";
            this.acctReissueDate = "";
            this.acctGroupId = "";
        }

        AccountRecord copy() {
            AccountRecord r = new AccountRecord(acctId, acctActiveStatus,
                    new BigDecimal(acctCurrBal.toPlainString()),
                    new BigDecimal(acctCreditLimit.toPlainString()),
                    new BigDecimal(acctCashCreditLimit.toPlainString()),
                    acctOpenDate, acctExpirationDate);
            r.acctReissueDate = this.acctReissueDate;
            r.acctGroupId = this.acctGroupId;
            return r;
        }
    }

    static class CustomerRecord {
        int custId;
        String custFirstName;
        String custMiddleName;
        String custLastName;
        String custAddrZip;
        int custSsn;
        int custFicoCreditScore;
        String custDobYyyyMmDd;

        CustomerRecord(int custId, String custFirstName, String custMiddleName,
                       String custLastName, String custAddrZip, int custSsn,
                       int custFicoCreditScore, String custDobYyyyMmDd) {
            this.custId = custId;
            this.custFirstName = custFirstName != null ? custFirstName : "";
            this.custMiddleName = custMiddleName != null ? custMiddleName : "";
            this.custLastName = custLastName != null ? custLastName : "";
            this.custAddrZip = custAddrZip != null ? custAddrZip : "";
            this.custSsn = custSsn;
            this.custFicoCreditScore = custFicoCreditScore;
            this.custDobYyyyMmDd = custDobYyyyMmDd != null ? custDobYyyyMmDd : "";
        }

        CustomerRecord copy() {
            return new CustomerRecord(custId, custFirstName, custMiddleName,
                    custLastName, custAddrZip, custSsn, custFicoCreditScore, custDobYyyyMmDd);
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

    static class AccountUpdateInput {
        String acctId = "";
        String activeStatus = "";
        String creditLimit = "";
        String cashCreditLimit = "";
        String currBal = "";
        String lastName = "";

        AccountUpdateInput() {}

        AccountUpdateInput(String acctId, String activeStatus, String creditLimit,
                           String cashCreditLimit, String lastName) {
            this.acctId = acctId != null ? acctId : "";
            this.activeStatus = activeStatus != null ? activeStatus : "";
            this.creditLimit = creditLimit != null ? creditLimit : "";
            this.cashCreditLimit = cashCreditLimit != null ? cashCreditLimit : "";
            this.lastName = lastName != null ? lastName : "";
        }
    }

    static class AccountUpdateResult {
        AccountRecord acctRecord = null;
        CustomerRecord custRecord = null;
        String action = "";
        String message = "";
        boolean error = false;
        boolean success = false;
        String xctlProgram = "";
        boolean returnToPrev = false;
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

    static class CustomerRepository {
        private final Map<Integer, CustomerRecord> customers;

        CustomerRepository(Map<Integer, CustomerRecord> customers) {
            this.customers = new HashMap<>(customers);
        }

        CustomerRecord find(int custId) {
            return customers.get(custId);
        }

        boolean rewrite(CustomerRecord cust) {
            if (!customers.containsKey(cust.custId)) return false;
            customers.put(cust.custId, cust);
            return true;
        }
    }

    static class XrefRepository {
        private final Map<Integer, CardXrefRecord> byAcct;

        XrefRepository(List<CardXrefRecord> xrefs) {
            this.byAcct = new HashMap<>();
            for (CardXrefRecord x : xrefs) {
                this.byAcct.put(x.xrefAcctId, x);
            }
        }

        CardXrefRecord findByAcct(int acctId) {
            return byAcct.get(acctId);
        }
    }

    // ── Standalone business method ──────────────────────────────────────────

    /**
     * Process account update screen — mirrors {@code process_account_update} in
     * {@code pipeline/reimpl/coactupc.py}.
     */
    AccountUpdateResult processAccountUpdate(
            int eibcalen, String eibaid,
            AccountUpdateInput inp,
            AccountRepository acctRepo, CustomerRepository custRepo, XrefRepository xrefRepo,
            String currentAction,
            AccountRecord oldAcct, CustomerRecord oldCust) {

        AccountUpdateResult result = new AccountUpdateResult();

        if (eibcalen == 0) {
            result.returnToPrev = true;
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if ("PF3".equals(eibaid)) {
            result.xctlProgram = "COMEN01C";
            result.returnToPrev = true;
            return result;
        }

        if ("C".equals(currentAction) || "L".equals(currentAction)
                || "F".equals(currentAction) || currentAction.isEmpty()) {
            return initialDisplay(inp.acctId, acctRepo, custRepo, xrefRepo, result);
        }

        if ("S".equals(currentAction)) {
            return validateAndPreview(inp, oldAcct, oldCust, acctRepo, custRepo, result);
        }

        if ("N".equals(currentAction) || "E".equals(currentAction)) {
            if ("PF5".equals(eibaid) && "N".equals(currentAction)) {
                return commitChanges(inp, oldAcct, oldCust, acctRepo, custRepo, result);
            }
            if ("PF12".equals(eibaid)) {
                result.xctlProgram = "COCRDLIC";
                result.returnToPrev = true;
                return result;
            }
            return validateAndPreview(inp, oldAcct, oldCust, acctRepo, custRepo, result);
        }

        return result;
    }

    private AccountUpdateResult initialDisplay(
            String acctIdStr,
            AccountRepository acctRepo, CustomerRepository custRepo, XrefRepository xrefRepo,
            AccountUpdateResult result) {

        result.action = "";

        if (acctIdStr == null || acctIdStr.trim().isEmpty()) {
            result.message = "Enter or update id of account to update";
            return result;
        }

        String trimmed = acctIdStr.trim();
        try {
            for (char c : trimmed.toCharArray()) {
                if (!Character.isDigit(c)) throw new NumberFormatException();
            }
        } catch (NumberFormatException e) {
            result.error = true;
            result.message = "Account number must be a non zero 11 digit number";
            return result;
        }

        int acctId = Integer.parseInt(trimmed);
        if (acctId == 0) {
            result.error = true;
            result.message = "Account number must be a non zero 11 digit number";
            return result;
        }

        AccountRecord acct = acctRepo.find(acctId);
        if (acct == null) {
            result.error = true;
            result.message = "Did not find this account in account master file";
            return result;
        }

        CardXrefRecord xref = xrefRepo.findByAcct(acctId);
        if (xref == null) {
            result.error = true;
            result.message = "Did not find this account in account card xref file";
            return result;
        }

        CustomerRecord cust = custRepo.find(xref.xrefCustId);
        if (cust == null) {
            result.error = true;
            result.message = "Did not find associated customer in master file";
            return result;
        }

        result.action = "S";
        result.acctRecord = acct;
        result.custRecord = cust;
        result.message = "Details of selected account shown above";
        return result;
    }

    private AccountUpdateResult validateAndPreview(
            AccountUpdateInput inp, AccountRecord oldAcct, CustomerRecord oldCust,
            AccountRepository acctRepo, CustomerRepository custRepo,
            AccountUpdateResult result) {

        // Validate
        String status = inp.activeStatus != null ? inp.activeStatus.trim().toUpperCase() : "";
        if (!"Y".equals(status) && !"N".equals(status)) {
            result.action = "E";
            result.error = true;
            result.message = "Account Active Status must be Y or N";
            result.acctRecord = oldAcct;
            result.custRecord = oldCust;
            return result;
        }

        String creditLimitStr = inp.creditLimit != null ? inp.creditLimit.trim() : "";
        if (creditLimitStr.isEmpty()) {
            result.action = "E";
            result.error = true;
            result.message = "Credit Limit must be supplied";
            result.acctRecord = oldAcct;
            result.custRecord = oldCust;
            return result;
        }
        try {
            new BigDecimal(creditLimitStr);
        } catch (NumberFormatException e) {
            result.action = "E";
            result.error = true;
            result.message = "Credit Limit is not valid";
            result.acctRecord = oldAcct;
            result.custRecord = oldCust;
            return result;
        }

        String cashCreditLimitStr = inp.cashCreditLimit != null ? inp.cashCreditLimit.trim() : "";
        if (cashCreditLimitStr.isEmpty()) {
            result.action = "E";
            result.error = true;
            result.message = "Cash Credit Limit must be supplied";
            result.acctRecord = oldAcct;
            result.custRecord = oldCust;
            return result;
        }
        try {
            new BigDecimal(cashCreditLimitStr);
        } catch (NumberFormatException e) {
            result.action = "E";
            result.error = true;
            result.message = "Cash Credit Limit is not valid";
            result.acctRecord = oldAcct;
            result.custRecord = oldCust;
            return result;
        }

        String lastName = inp.lastName != null ? inp.lastName.trim() : "";
        if (lastName.isEmpty()) {
            result.action = "E";
            result.error = true;
            result.message = "Last name not provided";
            result.acctRecord = oldAcct;
            result.custRecord = oldCust;
            return result;
        }

        // Build proposed records
        AccountRecord newAcct = applyAcctInput(inp, oldAcct);
        CustomerRecord newCust = applyCustInput(inp, oldCust);

        result.action = "N";
        result.acctRecord = newAcct;
        result.custRecord = newCust;
        result.message = "Changes validated.Press F5 to save";
        return result;
    }

    private AccountUpdateResult commitChanges(
            AccountUpdateInput inp, AccountRecord oldAcct, CustomerRecord oldCust,
            AccountRepository acctRepo, CustomerRepository custRepo,
            AccountUpdateResult result) {

        AccountRecord newAcct = applyAcctInput(inp, oldAcct);
        CustomerRecord newCust = applyCustInput(inp, oldCust);

        if (!acctRepo.rewrite(newAcct)) {
            result.action = "L";
            result.error = true;
            result.message = "Could not lock account record for update";
            return result;
        }

        if (!custRepo.rewrite(newCust)) {
            result.action = "F";
            result.error = true;
            result.message = "Update of record failed";
            return result;
        }

        result.action = "C";
        result.success = true;
        result.acctRecord = newAcct;
        result.custRecord = newCust;
        result.message = "Changes committed to database";
        return result;
    }

    private AccountRecord applyAcctInput(AccountUpdateInput inp, AccountRecord old) {
        AccountRecord acct = old != null ? old.copy() : new AccountRecord(0, "", BigDecimal.ZERO,
                BigDecimal.ZERO, BigDecimal.ZERO, "", "");

        if (inp.activeStatus != null && !inp.activeStatus.trim().isEmpty()) {
            acct.acctActiveStatus = inp.activeStatus.trim().toUpperCase().substring(0, 1);
        }
        if (inp.creditLimit != null && !inp.creditLimit.trim().isEmpty()) {
            try {
                acct.acctCreditLimit = new BigDecimal(inp.creditLimit.trim());
            } catch (NumberFormatException e) { /* ignore */ }
        }
        if (inp.cashCreditLimit != null && !inp.cashCreditLimit.trim().isEmpty()) {
            try {
                acct.acctCashCreditLimit = new BigDecimal(inp.cashCreditLimit.trim());
            } catch (NumberFormatException e) { /* ignore */ }
        }
        if (inp.currBal != null && !inp.currBal.trim().isEmpty()) {
            try {
                acct.acctCurrBal = new BigDecimal(inp.currBal.trim());
            } catch (NumberFormatException e) { /* ignore */ }
        }
        return acct;
    }

    private CustomerRecord applyCustInput(AccountUpdateInput inp, CustomerRecord old) {
        CustomerRecord cust = old != null ? old.copy() : new CustomerRecord(0, "", "", "", "", 0, 0, "");
        if (inp.lastName != null && !inp.lastName.trim().isEmpty()) {
            cust.custLastName = inp.lastName.trim();
        }
        return cust;
    }

    // ── runVector adapter ───────────────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "FIRST_ENTRY");

        // Seed data
        Map<Integer, AccountRecord> seedAccounts = new HashMap<>();
        AccountRecord seedAcct = new AccountRecord(100000001, "Y",
                new BigDecimal("5000.00"), new BigDecimal("10000.00"),
                new BigDecimal("5000.00"), "2020-01-15", "2030-12-31");
        seedAccounts.put(100000001, seedAcct);
        AccountRepository acctRepo = new AccountRepository(seedAccounts);

        Map<Integer, CustomerRecord> seedCustomers = new HashMap<>();
        seedCustomers.put(1, new CustomerRecord(1, "John", "A", "Doe",
                "10001", 123456789, 750, "1990-01-15"));
        CustomerRepository custRepo = new CustomerRepository(seedCustomers);

        List<CardXrefRecord> seedXrefs = new ArrayList<>();
        seedXrefs.add(new CardXrefRecord("4111111111111111", 1, 100000001));
        XrefRepository xrefRepo = new XrefRepository(seedXrefs);

        AccountUpdateResult result;

        switch (scenario) {
            case "FIRST_ENTRY":
                result = processAccountUpdate(0, "ENTER",
                        new AccountUpdateInput(),
                        acctRepo, custRepo, xrefRepo, "", null, null);
                break;
            case "LOOKUP_ACCOUNT":
                result = processAccountUpdate(100, "ENTER",
                        new AccountUpdateInput("100000001", "", "", "", ""),
                        acctRepo, custRepo, xrefRepo, "", null, null);
                break;
            case "ACCT_NOT_FOUND":
                result = processAccountUpdate(100, "ENTER",
                        new AccountUpdateInput("999999999", "", "", "", ""),
                        acctRepo, custRepo, xrefRepo, "", null, null);
                break;
            case "VALIDATE_OK": {
                AccountRecord oldA = acctRepo.find(100000001);
                CustomerRecord oldC = custRepo.find(1);
                result = processAccountUpdate(100, "ENTER",
                        new AccountUpdateInput("100000001", "Y", "15000.00", "7500.00", "Doe Updated"),
                        acctRepo, custRepo, xrefRepo, "S", oldA, oldC);
                break;
            }
            case "VALIDATION_ERROR": {
                AccountRecord oldA = acctRepo.find(100000001);
                CustomerRecord oldC = custRepo.find(1);
                result = processAccountUpdate(100, "ENTER",
                        new AccountUpdateInput("100000001", "X", "15000.00", "7500.00", "Doe Updated"),
                        acctRepo, custRepo, xrefRepo, "S", oldA, oldC);
                break;
            }
            case "COMMIT_CHANGES": {
                AccountRecord oldA = acctRepo.find(100000001);
                CustomerRecord oldC = custRepo.find(1);
                result = processAccountUpdate(100, "PF5",
                        new AccountUpdateInput("100000001", "Y", "15000.00", "7500.00", "Doe Updated"),
                        acctRepo, custRepo, xrefRepo, "N", oldA, oldC);
                break;
            }
            case "PF3_RETURN":
                result = processAccountUpdate(100, "PF3",
                        new AccountUpdateInput(),
                        acctRepo, custRepo, xrefRepo, "", null, null);
                break;
            default:
                result = processAccountUpdate(0, "ENTER",
                        new AccountUpdateInput(),
                        acctRepo, custRepo, xrefRepo, "", null, null);
                break;
        }

        String acctIdOut = "";
        String acctStatusOut = "";
        String acctBalOut = "";
        if (result.acctRecord != null) {
            acctIdOut = String.valueOf(result.acctRecord.acctId);
            acctStatusOut = result.acctRecord.acctActiveStatus;
            acctBalOut = result.acctRecord.acctCurrBal.toPlainString();
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("ACTION", result.action);
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("SUCCESS", result.success ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("XCTL_PROGRAM", result.xctlProgram != null ? result.xctlProgram : "");
        out.put("RETURN_TO_PREV", result.returnToPrev ? "Y" : "N");
        out.put("ACCT_ID", acctIdOut);
        out.put("ACCT_STATUS", acctStatusOut);
        out.put("ACCT_BAL", acctBalOut);
        return out;
    }
}
