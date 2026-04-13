package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Java reimplementation of CardDemo batch program CBTRN02C — Daily Transaction Posting.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbtrn02c.py} byte-for-byte. Python is the
 * source of truth.
 *
 * <p><b>Why this program matters:</b> the credit-limit check uses the EXACT
 * calculation that the W1 CobolDecimal golden vector test was derived from:
 * <pre>
 *   temp_bal = acct_curr_cyc_credit - acct_curr_cyc_debit + tran_amt
 * </pre>
 * The CardDemo COBOL source at {@code CBTRN02C.cbl:403} computes this via a
 * COMPUTE statement with PIC S9(09)V99 operands. The W1 unit test verified
 * that {@code CobolDecimal} produces {@code 1649.50} for
 * {@code 5000.00 - 3500.75 + 150.25}; this program exercises the same math
 * in a full posting flow via the differential harness. The HAPPY_GOLDEN_VECTOR
 * scenario deliberately uses those exact values.
 *
 * <p>For parity with the Python reimpl, this class uses plain {@link BigDecimal}
 * (not {@link com.modernization.masquerade.cobol.CobolDecimal}) — the Python
 * uses plain {@code Decimal} for the arithmetic, so we match. Addition,
 * subtraction, and comparison produce byte-identical results between the two
 * for in-range values.
 *
 * <p>Validation fail codes:
 * <ul>
 *   <li>100 — card number not in XREF</li>
 *   <li>101 — card maps to a missing account (dangling xref)</li>
 *   <li>102 — over credit limit</li>
 *   <li>103 — transaction received after account expiration date</li>
 * </ul>
 */
public class Cbtrn02c implements ProgramRunner {

    private static final int FAIL_INVALID_CARD = 100;
    private static final int FAIL_ACCOUNT_NF   = 101;
    private static final int FAIL_OVERLIMIT    = 102;
    private static final int FAIL_EXPIRED      = 103;

    private static final BigDecimal BD_0_00 = new BigDecimal("0.00");

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "").toUpperCase();
        Scenario scn = buildScenario(scenarioName);
        if (scn == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }

        // Snapshot account ids so we can report FINAL_BAL_<id> keys in a
        // stable order even though the accounts map is mutated in place.
        List<Integer> acctIds = new ArrayList<>(scn.accounts.keySet());
        acctIds.sort(Integer::compare);

        PostResult result = postDailyTransactions(
                scn.transactions, scn.xrefs, scn.accounts
        );

        // Build FAIL_CODES list in input order (0 = posted, else reject reason)
        List<String> failCodes = new ArrayList<>();
        Map<String, Integer> rejectedById = new HashMap<>();
        for (RejectRecord r : result.rejected) {
            rejectedById.put(r.tran.tranId, r.failReason);
        }
        List<String> postedIds = new ArrayList<>();
        for (DalyTranRecord t : result.posted) {
            postedIds.add(t.tranId);
        }
        for (DalyTranRecord t : scn.transactions) {
            if (postedIds.contains(t.tranId)) {
                failCodes.add("0");
            } else {
                failCodes.add(String.valueOf(rejectedById.getOrDefault(t.tranId, 0)));
            }
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("TRANSACTION_COUNT", String.valueOf(result.transactionCount));
        out.put("REJECT_COUNT", String.valueOf(result.rejectCount));
        out.put("POSTED_COUNT", String.valueOf(result.posted.size()));
        out.put("RETURN_CODE", String.valueOf(result.returnCode));
        out.put("FAIL_CODES", String.join(",", failCodes));

        for (int aid : acctIds) {
            out.put("FINAL_BAL_" + aid, formatBal(scn.accounts.get(aid).acctCurrBal));
        }
        return out;
    }

    /**
     * Process daily transactions — mirrors Python's post_daily_transactions
     * line-by-line. Validation order:
     *   1. Lookup card in XREF  (fail 100 on miss)
     *   2. Lookup account       (fail 101 on miss)
     *   3. Credit limit check   (fail 102 if over)
     *   4. Expiration check     (fail 103 if late)
     * Valid transactions post to the account (curr_bal, cyc_credit/debit).
     */
    PostResult postDailyTransactions(
            List<DalyTranRecord> transactions,
            Map<String, CardXrefRecord> xrefs,
            Map<Integer, AccountRecord> accounts
    ) {
        PostResult result = new PostResult();

        for (DalyTranRecord tran : transactions) {
            result.transactionCount++;

            int failReason = 0;
            CardXrefRecord xref = xrefs.get(tran.tranCardNum);
            AccountRecord acct = null;

            if (xref == null) {
                failReason = FAIL_INVALID_CARD;
            } else {
                acct = accounts.get(xref.xrefAcctId);
                if (acct == null) {
                    failReason = FAIL_ACCOUNT_NF;
                } else {
                    // Credit limit check:
                    // temp_bal = cyc_credit - cyc_debit + tran_amt
                    BigDecimal tempBal = acct.acctCurrCycCredit
                            .subtract(acct.acctCurrCycDebit)
                            .add(tran.tranAmt);
                    if (acct.acctCreditLimit.compareTo(tempBal) < 0) {
                        failReason = FAIL_OVERLIMIT;
                    }
                    // Expiration check (only if not already failed)
                    if (failReason == 0) {
                        String tranDate = tran.tranOrigTs.length() >= 10
                                ? tran.tranOrigTs.substring(0, 10) : "";
                        // ISO-8601 strings compare correctly via lexicographic order
                        if (acct.acctExpirationDate.compareTo(tranDate) < 0) {
                            failReason = FAIL_EXPIRED;
                        }
                    }
                }
            }

            if (failReason == 0 && acct != null) {
                // Post the transaction
                BigDecimal amt = tran.tranAmt;
                acct.acctCurrBal = acct.acctCurrBal.add(amt);
                if (amt.signum() >= 0) {
                    acct.acctCurrCycCredit = acct.acctCurrCycCredit.add(amt);
                } else {
                    acct.acctCurrCycDebit = acct.acctCurrCycDebit.add(amt);
                }
                accounts.put(acct.acctId, acct);
                result.posted.add(tran);
            } else {
                result.rejectCount++;
                result.rejected.add(new RejectRecord(tran, failReason));
            }
        }

        if (result.rejectCount > 0) {
            result.returnCode = 4;
        }
        return result;
    }

    private static String formatBal(BigDecimal d) {
        return d.setScale(2, RoundingMode.HALF_UP).toPlainString();
    }

    // ── Scenario builder ─────────────────────────────────────────────────

    private Scenario buildScenario(String name) {
        switch (name) {
            case "HAPPY_GOLDEN_VECTOR": return scenarioHappyGoldenVector();
            case "INVALID_CARD":        return scenarioInvalidCard();
            case "ACCT_NOT_FOUND":      return scenarioAcctNotFound();
            case "OVERLIMIT":           return scenarioOverlimit();
            case "EXPIRED":             return scenarioExpired();
            case "MIXED_BATCH":         return scenarioMixedBatch();
            default: return null;
        }
    }

    private Scenario scenarioHappyGoldenVector() {
        Scenario s = new Scenario();
        s.xrefs.put("4111000000001111",
                new CardXrefRecord("4111000000001111", 1, 100000001));
        s.accounts.put(100000001, new AccountRecord(
                100000001, new BigDecimal("1000.00"), new BigDecimal("10000.00"),
                new BigDecimal("5000.00"), new BigDecimal("3500.75"),
                "2099-12-31"
        ));
        s.transactions.add(makeTran(
                "TRN0000000000001", "01", 1,
                new BigDecimal("150.25"), "4111000000001111"
        ));
        return s;
    }

    private Scenario scenarioInvalidCard() {
        Scenario s = new Scenario();
        s.xrefs.put("4111000000001111",
                new CardXrefRecord("4111000000001111", 1, 100000001));
        s.accounts.put(100000001, new AccountRecord(
                100000001, new BigDecimal("1000.00"), new BigDecimal("10000.00"),
                BD_0_00, BD_0_00, "2099-12-31"
        ));
        s.transactions.add(makeTran(
                "TRN0000000000002", "01", 1,
                new BigDecimal("50.00"), "9999999999999999"  // not in xref
        ));
        return s;
    }

    private Scenario scenarioAcctNotFound() {
        Scenario s = new Scenario();
        s.xrefs.put("4111000000002222",
                new CardXrefRecord("4111000000002222", 2, 100000002));
        // accounts intentionally empty → 100000002 will not be found
        s.transactions.add(makeTran(
                "TRN0000000000003", "01", 1,
                new BigDecimal("25.00"), "4111000000002222"
        ));
        return s;
    }

    private Scenario scenarioOverlimit() {
        Scenario s = new Scenario();
        s.xrefs.put("4111000000003333",
                new CardXrefRecord("4111000000003333", 3, 100000003));
        s.accounts.put(100000003, new AccountRecord(
                100000003, new BigDecimal("50.00"), new BigDecimal("100.00"),
                new BigDecimal("50.00"), BD_0_00, "2099-12-31"
        ));
        // temp_bal = 50 - 0 + 200 = 250 > 100 credit limit
        s.transactions.add(makeTran(
                "TRN0000000000004", "01", 1,
                new BigDecimal("200.00"), "4111000000003333"
        ));
        return s;
    }

    private Scenario scenarioExpired() {
        Scenario s = new Scenario();
        s.xrefs.put("4111000000004444",
                new CardXrefRecord("4111000000004444", 4, 100000004));
        s.accounts.put(100000004, new AccountRecord(
                100000004, BD_0_00, new BigDecimal("10000.00"),
                BD_0_00, BD_0_00, "2020-01-01"
        ));
        s.transactions.add(makeTran(
                "TRN0000000000005", "01", 1,
                new BigDecimal("10.00"), "4111000000004444"
        ));
        return s;
    }

    private Scenario scenarioMixedBatch() {
        Scenario s = new Scenario();
        s.xrefs.put("4111000000001111",
                new CardXrefRecord("4111000000001111", 1, 100000001));
        s.xrefs.put("4111000000003333",
                new CardXrefRecord("4111000000003333", 3, 100000003));
        s.accounts.put(100000001, new AccountRecord(
                100000001, new BigDecimal("1000.00"), new BigDecimal("10000.00"),
                BD_0_00, BD_0_00, "2099-12-31"
        ));
        s.accounts.put(100000003, new AccountRecord(
                100000003, new BigDecimal("50.00"), new BigDecimal("100.00"),
                new BigDecimal("50.00"), BD_0_00, "2099-12-31"
        ));
        s.transactions.addAll(Arrays.asList(
                makeTran("TRN0000000000006", "01", 1,
                        new BigDecimal("75.00"), "4111000000001111"),
                makeTran("TRN0000000000007", "01", 1,
                        new BigDecimal("40.00"), "9999999999999999"),
                makeTran("TRN0000000000008", "01", 1,
                        new BigDecimal("500.00"), "4111000000003333")
        ));
        return s;
    }

    private static DalyTranRecord makeTran(
            String id, String typeCd, int catCd,
            BigDecimal amt, String cardNum
    ) {
        DalyTranRecord t = new DalyTranRecord();
        t.tranId = id;
        t.tranTypeCd = typeCd;
        t.tranCatCd = catCd;
        t.tranAmt = amt;
        t.tranCardNum = cardNum;
        t.tranOrigTs = "2026-04-09-12.00.00.000000";
        return t;
    }

    // ── Inner data types ─────────────────────────────────────────────────

    private static class Scenario {
        final Map<String, CardXrefRecord> xrefs = new HashMap<>();
        final TreeMap<Integer, AccountRecord> accounts = new TreeMap<>();
        final List<DalyTranRecord> transactions = new ArrayList<>();
    }

    static class DalyTranRecord {
        String tranId = "";
        String tranTypeCd = "";
        int tranCatCd = 0;
        String tranSource = "";
        String tranDesc = "";
        BigDecimal tranAmt = BD_0_00;
        String tranCardNum = "";
        String tranOrigTs = "";
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
        BigDecimal acctCurrBal;
        final BigDecimal acctCreditLimit;
        BigDecimal acctCurrCycCredit;
        BigDecimal acctCurrCycDebit;
        final String acctExpirationDate;

        AccountRecord(
                int acctId, BigDecimal currBal, BigDecimal creditLimit,
                BigDecimal cycCredit, BigDecimal cycDebit, String expirationDate
        ) {
            this.acctId = acctId;
            this.acctCurrBal = currBal;
            this.acctCreditLimit = creditLimit;
            this.acctCurrCycCredit = cycCredit;
            this.acctCurrCycDebit = cycDebit;
            this.acctExpirationDate = expirationDate;
        }
    }

    static class RejectRecord {
        final DalyTranRecord tran;
        final int failReason;

        RejectRecord(DalyTranRecord tran, int failReason) {
            this.tran = tran;
            this.failReason = failReason;
        }
    }

    static class PostResult {
        int transactionCount = 0;
        int rejectCount = 0;
        int returnCode = 0;
        final List<DalyTranRecord> posted = new ArrayList<>();
        final List<RejectRecord> rejected = new ArrayList<>();
    }
}
