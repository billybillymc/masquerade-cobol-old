package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Java reimplementation of CardDemo batch program CBACT01C — Batch Account File Reader.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbact01c.py} byte-for-byte. Python is the
 * source of truth.
 */
public class Cbact01c implements ProgramRunner {

    private static final BigDecimal BD_0_00 = new BigDecimal("0.00");
    private static final BigDecimal BD_2525_00 = new BigDecimal("2525.00");

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "PROCESS_RECORDS").toUpperCase();
        List<AccountRecord> accounts = buildScenario(scenarioName);
        if (accounts == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }

        // Process accounts
        List<String> displayLines = new ArrayList<>();
        List<OutAcctRec> outRecords = new ArrayList<>();
        List<ArrArrayRec> arrRecords = new ArrayList<>();
        List<VbRec1> vb1Records = new ArrayList<>();
        List<VbRec2> vb2Records = new ArrayList<>();
        int recordsRead = 0;

        for (AccountRecord acct : accounts) {
            recordsRead++;

            // 1100-DISPLAY-ACCT-RECORD
            List<String> lines = displayAcctRecord(acct);
            displayLines.addAll(lines);

            // 1300-POPUL + 1350-WRITE
            OutAcctRec outRec = buildOutRecord(acct);
            outRecords.add(outRec);

            // 1400-POPUL + 1450-WRITE
            arrRecords.add(buildArrRecord(acct));

            // 1500-POPUL + 1550/1575-WRITE
            VbRec1 vb1 = new VbRec1(acct.acctId, acct.acctActiveStatus);
            String reissueYyyy = acct.acctReissueDate.length() >= 4
                    ? acct.acctReissueDate.substring(0, 4) : "";
            VbRec2 vb2 = new VbRec2(acct.acctId, acct.acctCurrBal,
                    acct.acctCreditLimit, reissueYyyy);
            vb1Records.add(vb1);
            vb2Records.add(vb2);
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("RECORDS_READ", String.valueOf(recordsRead));
        out.put("OUT_RECORDS", String.valueOf(outRecords.size()));
        out.put("ARR_RECORDS", String.valueOf(arrRecords.size()));
        out.put("VB1_RECORDS", String.valueOf(vb1Records.size()));
        out.put("VB2_RECORDS", String.valueOf(vb2Records.size()));
        for (int i = 0; i < displayLines.size(); i++) {
            out.put("DISPLAY_" + i, displayLines.get(i));
        }
        for (int i = 0; i < outRecords.size(); i++) {
            out.put("OUT_CYC_DEBIT_" + i,
                    outRecords.get(i).acctCurrCycDebit.setScale(2, RoundingMode.HALF_UP).toPlainString());
        }
        return out;
    }

    private List<String> displayAcctRecord(AccountRecord acct) {
        List<String> lines = new ArrayList<>();
        lines.add("ACCT-ID                 :" + acct.acctId);
        lines.add("ACCT-ACTIVE-STATUS      :" + acct.acctActiveStatus);
        lines.add("ACCT-CURR-BAL           :" + acct.acctCurrBal);
        lines.add("ACCT-CREDIT-LIMIT       :" + acct.acctCreditLimit);
        lines.add("ACCT-CASH-CREDIT-LIMIT  :" + acct.acctCashCreditLimit);
        lines.add("ACCT-OPEN-DATE          :" + acct.acctOpenDate);
        lines.add("ACCT-EXPIRAION-DATE     :" + acct.acctExpirationDate);
        lines.add("ACCT-REISSUE-DATE       :" + acct.acctReissueDate);
        lines.add("ACCT-CURR-CYC-CREDIT    :" + acct.acctCurrCycCredit);
        lines.add("ACCT-CURR-CYC-DEBIT     :" + acct.acctCurrCycDebit);
        lines.add("ACCT-GROUP-ID           :" + acct.acctGroupId);
        // 49 dashes
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 49; i++) sb.append('-');
        lines.add(sb.toString());
        return lines;
    }

    private OutAcctRec buildOutRecord(AccountRecord acct) {
        // Reformat date (trivially, same format in/out for type "2"->"2")
        String reissueReformatted = acct.acctReissueDate;

        BigDecimal cycDebit = acct.acctCurrCycDebit;
        if (cycDebit.compareTo(BigDecimal.ZERO) == 0) {
            cycDebit = BD_2525_00;
        }

        return new OutAcctRec(
                acct.acctId, acct.acctActiveStatus, acct.acctCurrBal,
                acct.acctCreditLimit, acct.acctCashCreditLimit,
                acct.acctOpenDate, acct.acctExpirationDate,
                reissueReformatted, acct.acctCurrCycCredit, cycDebit,
                acct.acctGroupId
        );
    }

    private ArrArrayRec buildArrRecord(AccountRecord acct) {
        BigDecimal[][] balances = new BigDecimal[5][2];
        for (int i = 0; i < 5; i++) {
            balances[i][0] = BD_0_00;
            balances[i][1] = BD_0_00;
        }
        balances[0][0] = acct.acctCurrBal;
        balances[0][1] = new BigDecimal("1005.00");
        balances[1][0] = acct.acctCurrBal;
        balances[1][1] = new BigDecimal("1525.00");
        balances[2][0] = new BigDecimal("-1025.00");
        balances[2][1] = new BigDecimal("-2500.00");
        return new ArrArrayRec(acct.acctId, balances);
    }

    // ── Scenarios ─────────────────────────────────────────────────────────

    private List<AccountRecord> buildScenario(String name) {
        switch (name) {
            case "PROCESS_RECORDS": return scenarioProcessRecords();
            case "EMPTY_INPUT":    return scenarioEmptyInput();
            default: return null;
        }
    }

    private List<AccountRecord> scenarioProcessRecords() {
        List<AccountRecord> list = new ArrayList<>();
        list.add(new AccountRecord(
                100000001, "Y", new BigDecimal("5000.00"),
                new BigDecimal("10000.00"), new BigDecimal("3000.00"),
                "2020-03-15", "2029-12-31", "2025-03-15",
                new BigDecimal("1500.00"), BD_0_00, "GOLD"
        ));
        list.add(new AccountRecord(
                100000002, "Y", new BigDecimal("2500.50"),
                new BigDecimal("5000.00"), new BigDecimal("1500.00"),
                "2021-07-01", "2028-06-30", "2024-07-01",
                new BigDecimal("800.00"), new BigDecimal("200.00"), "PLAT"
        ));
        return list;
    }

    private List<AccountRecord> scenarioEmptyInput() {
        return new ArrayList<>();
    }

    // ── Inner data types ─────────────────────────────────────────────────

    static class AccountRecord {
        final int acctId;
        final String acctActiveStatus;
        final BigDecimal acctCurrBal;
        final BigDecimal acctCreditLimit;
        final BigDecimal acctCashCreditLimit;
        final String acctOpenDate;
        final String acctExpirationDate;
        final String acctReissueDate;
        final BigDecimal acctCurrCycCredit;
        final BigDecimal acctCurrCycDebit;
        final String acctGroupId;

        AccountRecord(int acctId, String activeStatus, BigDecimal currBal,
                      BigDecimal creditLimit, BigDecimal cashCreditLimit,
                      String openDate, String expirationDate, String reissueDate,
                      BigDecimal currCycCredit, BigDecimal currCycDebit,
                      String groupId) {
            this.acctId = acctId;
            this.acctActiveStatus = activeStatus;
            this.acctCurrBal = currBal;
            this.acctCreditLimit = creditLimit;
            this.acctCashCreditLimit = cashCreditLimit;
            this.acctOpenDate = openDate;
            this.acctExpirationDate = expirationDate;
            this.acctReissueDate = reissueDate;
            this.acctCurrCycCredit = currCycCredit;
            this.acctCurrCycDebit = currCycDebit;
            this.acctGroupId = groupId;
        }
    }

    static class OutAcctRec {
        final int acctId;
        final String acctActiveStatus;
        final BigDecimal acctCurrBal;
        final BigDecimal acctCreditLimit;
        final BigDecimal acctCashCreditLimit;
        final String acctOpenDate;
        final String acctExpirationDate;
        final String acctReissueDate;
        final BigDecimal acctCurrCycCredit;
        final BigDecimal acctCurrCycDebit;
        final String acctGroupId;

        OutAcctRec(int acctId, String activeStatus, BigDecimal currBal,
                   BigDecimal creditLimit, BigDecimal cashCreditLimit,
                   String openDate, String expirationDate, String reissueDate,
                   BigDecimal currCycCredit, BigDecimal currCycDebit,
                   String groupId) {
            this.acctId = acctId;
            this.acctActiveStatus = activeStatus;
            this.acctCurrBal = currBal;
            this.acctCreditLimit = creditLimit;
            this.acctCashCreditLimit = cashCreditLimit;
            this.acctOpenDate = openDate;
            this.acctExpirationDate = expirationDate;
            this.acctReissueDate = reissueDate;
            this.acctCurrCycCredit = currCycCredit;
            this.acctCurrCycDebit = currCycDebit;
            this.acctGroupId = groupId;
        }
    }

    static class ArrArrayRec {
        final int acctId;
        final BigDecimal[][] balances;

        ArrArrayRec(int acctId, BigDecimal[][] balances) {
            this.acctId = acctId;
            this.balances = balances;
        }
    }

    static class VbRec1 {
        final int acctId;
        final String acctActiveStatus;

        VbRec1(int acctId, String activeStatus) {
            this.acctId = acctId;
            this.acctActiveStatus = activeStatus;
        }
    }

    static class VbRec2 {
        final int acctId;
        final BigDecimal acctCurrBal;
        final BigDecimal acctCreditLimit;
        final String acctReissueYyyy;

        VbRec2(int acctId, BigDecimal currBal, BigDecimal creditLimit,
               String reissueYyyy) {
            this.acctId = acctId;
            this.acctCurrBal = currBal;
            this.acctCreditLimit = creditLimit;
            this.acctReissueYyyy = reissueYyyy;
        }
    }
}
