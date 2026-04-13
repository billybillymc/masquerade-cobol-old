package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Java reimplementation of CardDemo batch program CBACT04C — Interest Calculator.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbact04c.py} byte-for-byte. Python is the
 * source of truth.
 *
 * <p><b>Arithmetic strategy — important:</b> the Python uses plain
 * {@code Decimal} (not {@code CobolDecimal}) for the interest computation:
 * <pre>
 *   monthly_int = (cat_bal * dis_int_rate / Decimal("1200"))
 *                 .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
 * </pre>
 * This follows Python's {@code decimal} module's default context
 * (28 significant digits, ROUND_HALF_EVEN) for the intermediate
 * multiply/divide, then quantizes to 2dp with HALF_UP at the very end.
 * This is deliberate: COBOL COMPUTE intermediates have extended precision,
 * NOT the PIC scale of the operands. Using {@link com.modernization.masquerade.cobol.CobolDecimal}
 * would prematurely truncate to scale=max(s1,s2) in the multiply step and
 * produce wrong results for division by non-factor-of-10 divisors.
 *
 * <p>The Java port uses plain {@link BigDecimal} with
 * {@code MathContext(28, HALF_EVEN)} for the intermediate to match Python's
 * default {@code decimal} context byte-for-byte, then {@code setScale(2, HALF_UP)}
 * for the final quantize step — exactly mirroring the Python pattern.
 *
 * <p>Scenarios (matching the Python adapter):
 * <ul>
 *   <li>SINGLE — 1 account, 1 catbal, 1 rate</li>
 *   <li>MULTI_CAT — 1 account, 3 catbals, 3 different rates</li>
 *   <li>TWO_ACCOUNTS — 2 accounts, 1 catbal each, single rate</li>
 *   <li>ZERO_RATE — rate is 0, no interest, no transactions</li>
 * </ul>
 */
public class Cbact04c implements ProgramRunner {

    private static final String DEFAULT_GROUP = "DEFAULT";

    /**
     * Python's decimal module default context: 28-digit precision, ROUND_HALF_EVEN.
     * Every intermediate multiply/divide runs under this context so byte-for-byte
     * parity with Python's `Decimal * Decimal / Decimal` chain holds.
     */
    private static final MathContext PY_DEFAULT_CONTEXT =
            new MathContext(28, RoundingMode.HALF_EVEN);

    private static final BigDecimal BD_1200 = new BigDecimal("1200");
    private static final BigDecimal BD_0_00 = new BigDecimal("0.00");

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "SINGLE").toUpperCase();
        Scenario scn = buildScenario(scenarioName);
        if (scn == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }

        InterestResult result = computeInterest(
                scn.catbals, scn.accounts, scn.xrefs, scn.rates,
                "2026-04-08"
        );

        Map<String, String> out = new LinkedHashMap<>();
        out.put("RECORDS_PROCESSED", String.valueOf(result.recordsProcessed));
        out.put("TOTAL_INTEREST", formatBal(result.totalInterest));
        out.put("TRANSACTIONS_WRITTEN", String.valueOf(result.transactionsWritten.size()));

        // Per-account final balances, sorted by account id for deterministic key order
        TreeMap<Integer, AccountRecord> sorted = new TreeMap<>(scn.accounts);
        for (Map.Entry<Integer, AccountRecord> e : sorted.entrySet()) {
            out.put("FINAL_BAL_" + e.getKey(), formatBal(e.getValue().acctCurrBal));
        }
        return out;
    }

    /**
     * Mirror of Python's {@code compute_interest} — the PROCEDURE DIVISION loop.
     * Walks the catbals, detects account boundaries, accumulates interest per
     * account, writes interest transactions, and updates account balances.
     */
    InterestResult computeInterest(
            List<TranCatBalRecord> catbals,
            Map<Integer, AccountRecord> accounts,
            Map<Integer, CardXrefRecord> xrefs,
            Map<RateKey, DisGroupRecord> rates,
            String parmDate
    ) {
        InterestResult result = new InterestResult();

        int lastAcctNum = -1;
        boolean firstTime = true;
        BigDecimal wsTotalInt = BD_0_00;
        int wsTranidSuffix = 0;
        AccountRecord currentAcct = null;
        CardXrefRecord currentXref = null;

        for (TranCatBalRecord catBal : catbals) {
            result.recordsProcessed++;

            if (catBal.trancatAcctId != lastAcctNum) {
                if (!firstTime && currentAcct != null) {
                    updateAccount(currentAcct, wsTotalInt, accounts);
                    result.accountsUpdated.add(currentAcct);
                } else {
                    firstTime = false;
                }
                wsTotalInt = BD_0_00;
                lastAcctNum = catBal.trancatAcctId;
                currentAcct = accounts.get(catBal.trancatAcctId);
                currentXref = xrefs.get(catBal.trancatAcctId);
            }

            // Look up interest rate
            DisGroupRecord disRec = null;
            if (currentAcct != null) {
                disRec = findRate(
                        rates,
                        currentAcct.acctGroupId,
                        catBal.trancatTypeCd,
                        catBal.trancatCd
                );
            }

            if (disRec != null && disRec.disIntRate.signum() != 0) {
                // 1300-COMPUTE-INTEREST
                // monthly = (cat_bal * rate / 1200).quantize(0.01, HALF_UP)
                // Intermediate uses PY_DEFAULT_CONTEXT (28 digits, HALF_EVEN)
                // then final setScale(2, HALF_UP) mirrors Python's .quantize.
                BigDecimal product = catBal.tranCatBal.multiply(disRec.disIntRate, PY_DEFAULT_CONTEXT);
                BigDecimal quotient = product.divide(BD_1200, PY_DEFAULT_CONTEXT);
                BigDecimal monthlyInt = quotient.setScale(2, RoundingMode.HALF_UP);

                wsTotalInt = wsTotalInt.add(monthlyInt);
                result.totalInterest = result.totalInterest.add(monthlyInt);

                // 1300-B-WRITE-TX — we just track count, the actual content
                // isn't exposed in the runner contract
                wsTranidSuffix++;
                result.transactionsWritten.add("TX_" + wsTranidSuffix);
            }
        }

        // Final account update for the last account processed
        if (!firstTime && currentAcct != null) {
            updateAccount(currentAcct, wsTotalInt, accounts);
            result.accountsUpdated.add(currentAcct);
        }

        return result;
    }

    /** 1050-UPDATE-ACCOUNT: add total interest to balance, zero cyclic amounts. */
    private void updateAccount(
            AccountRecord acct,
            BigDecimal totalInt,
            Map<Integer, AccountRecord> repo
    ) {
        acct.acctCurrBal = acct.acctCurrBal.add(totalInt);
        acct.acctCurrCycCredit = BD_0_00;
        acct.acctCurrCycDebit = BD_0_00;
        repo.put(acct.acctId, acct);
    }

    /** Look up an interest rate, falling back to DEFAULT group if not found. */
    private DisGroupRecord findRate(
            Map<RateKey, DisGroupRecord> rates,
            String groupId, String typeCd, int catCd
    ) {
        DisGroupRecord rec = rates.get(new RateKey(groupId, typeCd, catCd));
        if (rec == null) {
            rec = rates.get(new RateKey(DEFAULT_GROUP, typeCd, catCd));
        }
        return rec;
    }

    /**
     * Format a balance as a scale-2 decimal string. Mirrors Python's
     * {@code f"{d.quantize(Decimal('0.01')):.2f}"}.
     */
    private static String formatBal(BigDecimal d) {
        return d.setScale(2, RoundingMode.HALF_UP).toPlainString();
    }

    // ── Scenarios ─────────────────────────────────────────────────────────

    private Scenario buildScenario(String name) {
        switch (name) {
            case "SINGLE":       return scenarioSingle();
            case "MULTI_CAT":    return scenarioMultiCat();
            case "TWO_ACCOUNTS": return scenarioTwoAccounts();
            case "ZERO_RATE":    return scenarioZeroRate();
            default: return null;
        }
    }

    private Scenario scenarioSingle() {
        Scenario s = new Scenario();
        s.accounts.put(1, new AccountRecord(1, "GOLD", new BigDecimal("5000.00")));
        s.catbals.add(new TranCatBalRecord(1, "01", 1, new BigDecimal("1000.00")));
        s.xrefs.put(1, new CardXrefRecord("4111111111111111", 1));
        s.rates.put(new RateKey("GOLD", "01", 1),
                new DisGroupRecord("GOLD", "01", 1, new BigDecimal("18.99")));
        return s;
    }

    private Scenario scenarioMultiCat() {
        Scenario s = new Scenario();
        s.accounts.put(1, new AccountRecord(1, "PLAT", new BigDecimal("10000.00")));
        s.catbals.add(new TranCatBalRecord(1, "01", 1, new BigDecimal("5000.00")));
        s.catbals.add(new TranCatBalRecord(1, "01", 2, new BigDecimal("3000.00")));
        s.catbals.add(new TranCatBalRecord(1, "02", 1, new BigDecimal("2000.00")));
        s.xrefs.put(1, new CardXrefRecord("4222222222222222", 1));
        s.rates.put(new RateKey("PLAT", "01", 1),
                new DisGroupRecord("PLAT", "01", 1, new BigDecimal("18.99")));
        s.rates.put(new RateKey("PLAT", "01", 2),
                new DisGroupRecord("PLAT", "01", 2, new BigDecimal("22.49")));
        s.rates.put(new RateKey("PLAT", "02", 1),
                new DisGroupRecord("PLAT", "02", 1, new BigDecimal("24.99")));
        return s;
    }

    private Scenario scenarioTwoAccounts() {
        Scenario s = new Scenario();
        s.accounts.put(1, new AccountRecord(1, "GOLD", new BigDecimal("1000.00")));
        s.accounts.put(2, new AccountRecord(2, "GOLD", new BigDecimal("2000.00")));
        s.catbals.add(new TranCatBalRecord(1, "01", 1, new BigDecimal("500.00")));
        s.catbals.add(new TranCatBalRecord(2, "01", 1, new BigDecimal("800.00")));
        s.xrefs.put(1, new CardXrefRecord("4111111111111111", 1));
        s.xrefs.put(2, new CardXrefRecord("4333333333333333", 2));
        s.rates.put(new RateKey("GOLD", "01", 1),
                new DisGroupRecord("GOLD", "01", 1, new BigDecimal("15.00")));
        return s;
    }

    private Scenario scenarioZeroRate() {
        Scenario s = new Scenario();
        s.accounts.put(1, new AccountRecord(1, "GOLD", new BigDecimal("5000.00")));
        s.catbals.add(new TranCatBalRecord(1, "01", 1, new BigDecimal("1000.00")));
        s.xrefs.put(1, new CardXrefRecord("4111111111111111", 1));
        s.rates.put(new RateKey("GOLD", "01", 1),
                new DisGroupRecord("GOLD", "01", 1, new BigDecimal("0.00")));
        return s;
    }

    // ── Inner data types ─────────────────────────────────────────────────

    private static class Scenario {
        final Map<Integer, AccountRecord> accounts = new HashMap<>();
        final List<TranCatBalRecord> catbals = new ArrayList<>();
        final Map<Integer, CardXrefRecord> xrefs = new HashMap<>();
        final Map<RateKey, DisGroupRecord> rates = new HashMap<>();
    }

    static class AccountRecord {
        final int acctId;
        final String acctGroupId;
        BigDecimal acctCurrBal;
        BigDecimal acctCurrCycCredit = BD_0_00;
        BigDecimal acctCurrCycDebit = BD_0_00;

        AccountRecord(int acctId, String acctGroupId, BigDecimal acctCurrBal) {
            this.acctId = acctId;
            this.acctGroupId = acctGroupId;
            this.acctCurrBal = acctCurrBal;
        }
    }

    static class CardXrefRecord {
        final String xrefCardNum;
        final int xrefAcctId;

        CardXrefRecord(String cardNum, int acctId) {
            this.xrefCardNum = cardNum;
            this.xrefAcctId = acctId;
        }
    }

    static class TranCatBalRecord {
        final int trancatAcctId;
        final String trancatTypeCd;
        final int trancatCd;
        final BigDecimal tranCatBal;

        TranCatBalRecord(int acctId, String typeCd, int catCd, BigDecimal bal) {
            this.trancatAcctId = acctId;
            this.trancatTypeCd = typeCd;
            this.trancatCd = catCd;
            this.tranCatBal = bal;
        }
    }

    static class DisGroupRecord {
        final String disAcctGroupId;
        final String disTranTypeCd;
        final int disTranCatCd;
        final BigDecimal disIntRate;

        DisGroupRecord(String groupId, String typeCd, int catCd, BigDecimal rate) {
            this.disAcctGroupId = groupId;
            this.disTranTypeCd = typeCd;
            this.disTranCatCd = catCd;
            this.disIntRate = rate;
        }
    }

    /** Composite key for the rate lookup map. */
    static class RateKey {
        final String groupId;
        final String typeCd;
        final int catCd;

        RateKey(String groupId, String typeCd, int catCd) {
            this.groupId = groupId;
            this.typeCd = typeCd;
            this.catCd = catCd;
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof RateKey)) return false;
            RateKey k = (RateKey) o;
            return catCd == k.catCd && groupId.equals(k.groupId) && typeCd.equals(k.typeCd);
        }

        @Override
        public int hashCode() {
            int h = groupId.hashCode();
            h = 31 * h + typeCd.hashCode();
            h = 31 * h + catCd;
            return h;
        }
    }

    static class InterestResult {
        int recordsProcessed = 0;
        BigDecimal totalInterest = BD_0_00;
        final List<String> transactionsWritten = new ArrayList<>();
        final List<AccountRecord> accountsUpdated = new ArrayList<>();
    }
}
