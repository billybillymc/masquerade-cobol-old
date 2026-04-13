package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.cobol.CobolDecimal;
import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of CBSA program DBCRFUN — Debit/Credit Function.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbsa_dbcrfun.py} byte-for-byte. The Python
 * version is the source of truth for behavior; this is the byte-for-byte
 * Java twin verified by the differential harness.
 *
 * <p><b>Why this program matters:</b> DBCRFUN is the first Java reimplementation
 * to use {@link CobolDecimal} for arithmetic — every other program ported so
 * far has been pure string/control-flow logic. The W1 foundation is finally
 * exercised in production-style code: account balances are PIC S9(10)V99
 * (digits=10, scale=2, signed) and every debit/credit goes through
 * {@code CobolDecimal.add}, {@code CobolDecimal.subtract}, and the
 * intermediate-precision rules.
 *
 * <p>The Python uses plain {@code Decimal}, not {@code CobolDecimal}. For
 * test inputs that fit comfortably within S9(10)V99 (every realistic value),
 * the two are equivalent — but if the parity tests pass, that's strong
 * evidence the W1 port matches the COBOL standard on real money math, not
 * just synthetic edge cases.
 *
 * <p>Decision tree (mirrors the Python):
 * <pre>
 *   1. SELECT account; not found → fail_code "1"
 *   2. IF amount &lt; 0 (debit/payment):
 *        2a. IF restricted account type AND payment → fail_code "4"
 *        2b. IF balance + amount &lt; 0 AND payment → fail_code "3"
 *   3. IF restricted account type AND payment → fail_code "4" (catches credits)
 *   4. Compute new balances; UPDATE account
 *   5. INSERT proctran (always succeeds in our in-memory impl)
 *   6. Success → "Y", fail_code "0"
 * </pre>
 */
public class Dbcrfun implements ProgramRunner {

    static final String SORTCODE = "987654";
    static final int FACILTYPE_PAYMENT = 496;

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String accNo = inputs.getOrDefault("ACC_NO", "");
        String amountStr = inputs.getOrDefault("AMOUNT", "0.00");
        int facilType = parseIntOr(inputs.get("FACIL_TYPE"), 0);
        String origin = inputs.getOrDefault("ORIGIN", "");

        // Parse the request amount through CobolDecimal at S9(10)V99 precision
        CobolDecimal amount = new CobolDecimal(10, 2, true);
        amount.set(new BigDecimal(amountStr));

        DebitCreditRequest request = new DebitCreditRequest();
        request.sortcode = SORTCODE;
        request.accNo = accNo;
        request.amount = amount;
        request.facilType = facilType;
        request.origin = origin;

        InMemoryAccountRepository accountRepo = seededRepository();
        DebitCreditResult result = processDebitCredit(request, accountRepo);

        Map<String, String> out = new LinkedHashMap<>();
        out.put("SUCCESS", result.success ? "Y" : "N");
        out.put("FAIL_CODE", result.failCode);
        out.put("AVAIL_BAL", formatBalance(result.availBal));
        out.put("ACTUAL_BAL", formatBalance(result.actualBal));
        out.put("SORTCODE", result.sortcode);
        return out;
    }

    /**
     * The COBOL UPDATE-ACCOUNT-DB2 / WRITE-TO-PROCTRAN-DB2 sequence, ported.
     * Direct line-by-line correspondence with {@code process_debit_credit} in
     * cbsa_dbcrfun.py.
     */
    DebitCreditResult processDebitCredit(DebitCreditRequest request, InMemoryAccountRepository accountRepo) {
        DebitCreditResult result = new DebitCreditResult();
        result.sortcode = SORTCODE;

        // Step 3: Read account
        Account account = accountRepo.find(SORTCODE, request.accNo);
        if (account == null) {
            result.success = false;
            result.failCode = "1";
            return result;
        }

        // Step 4: Debit-specific checks
        if (request.amount.value().signum() < 0) {
            // 4a: Restricted account type for PAYMENT
            if (isRestrictedAccountType(account.accType) && request.facilType == FACILTYPE_PAYMENT) {
                result.success = false;
                result.failCode = "4";
                return result;
            }
            // 4b: Insufficient funds for PAYMENT
            CobolDecimal difference = account.availBal.add(request.amount);
            if (difference.value().signum() < 0 && request.facilType == FACILTYPE_PAYMENT) {
                result.success = false;
                result.failCode = "3";
                return result;
            }
        }

        // Step 5: Restricted account check (catches credits to MORTGAGE/LOAN via PAYMENT)
        if (isRestrictedAccountType(account.accType) && request.facilType == FACILTYPE_PAYMENT) {
            result.success = false;
            result.failCode = "4";
            return result;
        }

        // Step 6: Compute new balances. The intermediate from add() has digits+1, scale=2;
        // assigning back into the S9(10)V99 fields enforces the target precision.
        CobolDecimal newAvail = new CobolDecimal(10, 2, true);
        account.availBal.add(request.amount).assignTo(newAvail);
        CobolDecimal newActual = new CobolDecimal(10, 2, true);
        account.actualBal.add(request.amount).assignTo(newActual);
        account.availBal = newAvail;
        account.actualBal = newActual;

        // Step 7: Update account (in-memory always succeeds)
        accountRepo.update(account);
        result.availBal = account.availBal;
        result.actualBal = account.actualBal;

        // Step 8: Write PROCTRAN — in-memory impl always succeeds, so no rollback path
        // is exercised. The classification (DEB/CRE/PDR/PCR) happens here in the COBOL
        // but isn't surfaced in the runner contract, so it's a no-op for parity purposes.

        // Step 9: Success
        result.success = true;
        result.failCode = "0";
        return result;
    }

    // ── Helpers ──────────────────────────────────────────────────────────

    private static boolean isRestrictedAccountType(String accType) {
        if (accType == null) return false;
        String s = accType.trim().toUpperCase();
        return "MORTGAGE".equals(s) || "LOAN".equals(s);
    }

    private static int parseIntOr(String s, int fallback) {
        if (s == null || s.isEmpty()) return fallback;
        try {
            return Integer.parseInt(s.trim());
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    /**
     * Format a balance as a fixed scale-2 decimal string.
     * MUST match Python's {@code _format_balance} byte-for-byte.
     */
    private static String formatBalance(CobolDecimal bal) {
        BigDecimal v = bal.value().setScale(2, java.math.RoundingMode.DOWN);
        return v.toPlainString();
    }

    private InMemoryAccountRepository seededRepository() {
        InMemoryAccountRepository repo = new InMemoryAccountRepository();
        repo.add(makeAccount("0000000001", "ACC00001", "CHECKING", "1000.00"));
        repo.add(makeAccount("0000000002", "ACC00002", "CHECKING", "10.00"));
        repo.add(makeAccount("0000000003", "ACC00003", "MORTGAGE", "5000.00"));
        repo.add(makeAccount("0000000004", "ACC00004", "LOAN",     "500.00"));
        repo.add(makeAccount("0000000005", "ACC00005", "SAVING",   "2000.00"));
        return repo;
    }

    private static Account makeAccount(String custNo, String accNo, String accType, String balanceStr) {
        Account a = new Account();
        a.custNo = custNo;
        a.sortcode = SORTCODE;
        a.accNo = accNo;
        a.accType = accType;
        a.availBal = new CobolDecimal(10, 2, true);
        a.availBal.set(new BigDecimal(balanceStr));
        a.actualBal = new CobolDecimal(10, 2, true);
        a.actualBal.set(new BigDecimal(balanceStr));
        return a;
    }

    // ── Inner data types ─────────────────────────────────────────────────

    static class Account {
        String eyecatcher = "ACCT";
        String custNo = "0000000000";
        String sortcode = "000000";
        String accNo = "00000000";
        String accType = "";
        CobolDecimal availBal;
        CobolDecimal actualBal;
    }

    static class DebitCreditRequest {
        String sortcode = SORTCODE;
        String accNo = "";
        CobolDecimal amount;
        int facilType = 0;
        String origin = "";
    }

    static class DebitCreditResult {
        boolean success = false;
        String failCode = "0";
        CobolDecimal availBal = new CobolDecimal(10, 2, true);
        CobolDecimal actualBal = new CobolDecimal(10, 2, true);
        String sortcode = SORTCODE;
    }

    static class InMemoryAccountRepository {
        private final Map<String, Account> accounts = new HashMap<>();

        void add(Account a) {
            accounts.put(key(a.sortcode, a.accNo), a);
        }

        Account find(String sortcode, String accNo) {
            return accounts.get(key(sortcode, accNo));
        }

        boolean update(Account a) {
            String k = key(a.sortcode, a.accNo);
            if (accounts.containsKey(k)) {
                accounts.put(k, a);
                return true;
            }
            return false;
        }

        private static String key(String sortcode, String accNo) {
            return sortcode + ":" + accNo;
        }
    }
}
