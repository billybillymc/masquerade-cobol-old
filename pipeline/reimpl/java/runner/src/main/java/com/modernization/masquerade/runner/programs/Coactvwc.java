package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.util.*;

/**
 * Java reimplementation of COACTVWC — CardDemo Account View Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/coactvwc.py}. Python is the source of truth.
 *
 * <p>Structure: standalone {@link #processAccountView} method + thin
 * {@link #runVector} adapter.
 */
public class Coactvwc implements ProgramRunner {

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
        BigDecimal acctCurrCycCredit;
        BigDecimal acctCurrCycDebit;
        String acctGroupId;

        AccountRecord(int acctId, String acctActiveStatus, BigDecimal acctCurrBal,
                      BigDecimal acctCreditLimit, BigDecimal acctCashCreditLimit,
                      String acctOpenDate, String acctExpirationDate, String acctReissueDate,
                      BigDecimal acctCurrCycCredit, BigDecimal acctCurrCycDebit, String acctGroupId) {
            this.acctId = acctId;
            this.acctActiveStatus = acctActiveStatus;
            this.acctCurrBal = acctCurrBal;
            this.acctCreditLimit = acctCreditLimit;
            this.acctCashCreditLimit = acctCashCreditLimit;
            this.acctOpenDate = acctOpenDate != null ? acctOpenDate : "";
            this.acctExpirationDate = acctExpirationDate != null ? acctExpirationDate : "";
            this.acctReissueDate = acctReissueDate != null ? acctReissueDate : "";
            this.acctCurrCycCredit = acctCurrCycCredit;
            this.acctCurrCycDebit = acctCurrCycDebit;
            this.acctGroupId = acctGroupId != null ? acctGroupId : "";
        }
    }

    static class CustomerRecord {
        int custId;
        String custFirstName;
        String custLastName;
        int custSsn;
        String custDobYyyyMmDd;
        int custFicoCreditScore;
        String custAddrZip;
        String custPhoneNum1;
        String custPhoneNum2;

        CustomerRecord(int custId, String custFirstName, String custLastName,
                       int custSsn, String custDobYyyyMmDd, int custFicoCreditScore,
                       String custAddrZip, String custPhoneNum1, String custPhoneNum2) {
            this.custId = custId;
            this.custFirstName = custFirstName != null ? custFirstName : "";
            this.custLastName = custLastName != null ? custLastName : "";
            this.custSsn = custSsn;
            this.custDobYyyyMmDd = custDobYyyyMmDd != null ? custDobYyyyMmDd : "";
            this.custFicoCreditScore = custFicoCreditScore;
            this.custAddrZip = custAddrZip != null ? custAddrZip : "";
            this.custPhoneNum1 = custPhoneNum1 != null ? custPhoneNum1 : "";
            this.custPhoneNum2 = custPhoneNum2 != null ? custPhoneNum2 : "";
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

    static class AccountViewData {
        int acctId;
        String acctActiveStatus;
        String acctCurrBal;
        String custName;
        String custSsnMasked;

        AccountViewData(int acctId, String acctActiveStatus, String acctCurrBal,
                        String custName, String custSsnMasked) {
            this.acctId = acctId;
            this.acctActiveStatus = acctActiveStatus;
            this.acctCurrBal = acctCurrBal;
            this.custName = custName;
            this.custSsnMasked = custSsnMasked;
        }
    }

    static class AccountViewResult {
        AccountViewData accountData = null;
        String message = "";
        boolean error = false;
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

    static class CustomerRepository {
        private final Map<Integer, CustomerRecord> customers;

        CustomerRepository(Map<Integer, CustomerRecord> customers) {
            this.customers = new HashMap<>(customers);
        }

        CustomerRecord find(int custId) {
            return customers.get(custId);
        }
    }

    // ── Standalone business method ──────────────────────────────────────────

    /**
     * Process account view screen — mirrors {@code process_account_view} in
     * {@code pipeline/reimpl/coactvwc.py}.
     */
    AccountViewResult processAccountView(
            int eibcalen, String eibaid, int pgmContext, String fromProgram,
            String acctIdInput,
            AccountRepository accountRepo, XrefRepository xrefRepo, CustomerRepository customerRepo) {

        AccountViewResult result = new AccountViewResult();

        if ("PF3".equals(eibaid)) {
            String backPgm = (fromProgram != null && !fromProgram.isEmpty()) ? fromProgram : "COMEN01C";
            result.xctlProgram = backPgm;
            result.returnToPrev = true;
            return result;
        }

        if (pgmContext == 0) {
            // First entry — show blank search form
            result.message = "Enter or update id of account to display";
            return result;
        }

        // Re-entry with account ID — process lookup
        return processAccountLookup(acctIdInput, accountRepo, xrefRepo, customerRepo, result);
    }

    private AccountViewResult processAccountLookup(
            String acctIdInput,
            AccountRepository accountRepo, XrefRepository xrefRepo,
            CustomerRepository customerRepo,
            AccountViewResult result) {

        if (acctIdInput == null || acctIdInput.trim().isEmpty()) {
            result.error = true;
            result.message = "Account number not provided";
            return result;
        }

        int acctId;
        try {
            acctId = Integer.parseInt(acctIdInput.trim());
        } catch (NumberFormatException e) {
            result.error = true;
            result.message = "Account number must be a non zero 11 digit number";
            return result;
        }

        if (acctId == 0) {
            result.error = true;
            result.message = "Account number must be a non zero 11 digit number";
            return result;
        }

        AccountRecord acct = accountRepo.find(acctId);
        if (acct == null) {
            result.error = true;
            result.message = "Did not find this account in account master file";
            return result;
        }

        CardXrefRecord xref = xrefRepo.findByAcct(acctId);
        CustomerRecord cust = null;
        if (xref != null) {
            cust = customerRepo.find(xref.xrefCustId);
        }
        if (cust == null) {
            result.error = true;
            result.message = "Did not find associated customer in master file";
        }

        // Build view data
        String custName = "";
        String custSsnMasked = "";
        if (cust != null) {
            custName = cust.custFirstName.trim() + " " + cust.custLastName.trim();
            String ssn = String.format("%09d", cust.custSsn);
            custSsnMasked = ssn.substring(0, 3) + "-" + ssn.substring(3, 5) + "-" + ssn.substring(5);
        }

        String balFormatted = String.format("%,.2f", acct.acctCurrBal.doubleValue());

        result.accountData = new AccountViewData(
                acct.acctId, acct.acctActiveStatus, balFormatted, custName, custSsnMasked);

        if (!result.error) {
            result.message = "Displaying details of given Account";
        }

        return result;
    }

    // ── runVector adapter ───────────────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "FIRST_ENTRY");

        // Seed data
        Map<Integer, AccountRecord> seedAccounts = new HashMap<>();
        seedAccounts.put(10000001, new AccountRecord(10000001, "Y",
                new BigDecimal("1500.00"), new BigDecimal("5000.00"), new BigDecimal("1000.00"),
                "2020-01-15", "2028-01-15", "2025-01-15",
                new BigDecimal("200.00"), new BigDecimal("50.00"), "GOLD"));
        AccountRepository accountRepo = new AccountRepository(seedAccounts);

        Map<Integer, CardXrefRecord> seedXrefs = new HashMap<>();
        seedXrefs.put(10000001, new CardXrefRecord("4111111111110001", 100001, 10000001));
        XrefRepository xrefRepo = new XrefRepository(seedXrefs);

        Map<Integer, CustomerRecord> seedCustomers = new HashMap<>();
        seedCustomers.put(100001, new CustomerRecord(100001, "Jane", "User",
                123456789, "1985-03-15", 750, "10001", "212-555-0100", "212-555-0101"));
        CustomerRepository customerRepo = new CustomerRepository(seedCustomers);

        AccountViewResult result;

        switch (scenario) {
            case "FIRST_ENTRY":
                result = processAccountView(100, "ENTER", 0, "COMEN01C",
                        "", accountRepo, xrefRepo, customerRepo);
                break;
            case "VALID_INPUT":
                result = processAccountView(100, "ENTER", 1, "COMEN01C",
                        "10000001", accountRepo, xrefRepo, customerRepo);
                break;
            case "ACCT_NOT_FOUND":
                result = processAccountView(100, "ENTER", 1, "COMEN01C",
                        "99999999", accountRepo, xrefRepo, customerRepo);
                break;
            case "PF3_RETURN":
                result = processAccountView(100, "PF3", 1, "COMEN01C",
                        "", accountRepo, xrefRepo, customerRepo);
                break;
            default:
                result = processAccountView(100, "ENTER", 0, "COMEN01C",
                        "", accountRepo, xrefRepo, customerRepo);
                break;
        }

        String acctId = "";
        String acctStatus = "";
        String acctBal = "";
        String custName = "";
        String custSsn = "";
        if (result.accountData != null) {
            acctId = String.valueOf(result.accountData.acctId);
            acctStatus = result.accountData.acctActiveStatus;
            acctBal = result.accountData.acctCurrBal;
            custName = result.accountData.custName;
            custSsn = result.accountData.custSsnMasked;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("XCTL_PROGRAM", result.xctlProgram != null ? result.xctlProgram : "");
        out.put("RETURN_TO_PREV", result.returnToPrev ? "Y" : "N");
        out.put("ACCT_ID", acctId);
        out.put("ACCT_STATUS", acctStatus);
        out.put("ACCT_BAL", acctBal);
        out.put("CUST_NAME", custName);
        out.put("CUST_SSN", custSsn);
        return out;
    }
}
