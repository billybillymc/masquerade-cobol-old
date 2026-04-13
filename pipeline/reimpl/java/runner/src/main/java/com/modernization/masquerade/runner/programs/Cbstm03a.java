package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Java reimplementation of CardDemo batch program CBSTM03A — Account Statement Generator.
 *
 * <p>Mirrors {@code pipeline/reimpl/cbstm03a.py} byte-for-byte. Python is the
 * source of truth.
 */
public class Cbstm03a implements ProgramRunner {

    private static final BigDecimal BD_0_00 = new BigDecimal("0.00");

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "PROCESS_RECORDS").toUpperCase();
        Scenario scn = buildScenario(scenarioName);
        if (scn == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }

        // Build file manager with transactions
        Cbstm03b.FileManager fileMgr = new Cbstm03b.FileManager(scn.transactions);

        // OPEN, READ all, CLOSE -- group by card number
        Cbstm03b.M03BArea area = new Cbstm03b.M03BArea();
        area.oper = "O";
        fileMgr.execute(area);

        Map<String, List<TranData>> transactionsByCard = new LinkedHashMap<>();
        int totalRecordsRead = 0;

        while (true) {
            area.oper = "R";
            fileMgr.execute(area);
            if ("10".equals(area.rc)) break;
            totalRecordsRead++;

            TranData tran = parseFldt(area.fldt);
            if (tran == null) continue;

            transactionsByCard.computeIfAbsent(tran.tranCardNum, k -> new ArrayList<>()).add(tran);
        }

        area.oper = "C";
        fileMgr.execute(area);

        // Generate statements
        List<String> plainTextLines = new ArrayList<>();
        List<String> htmlLines = new ArrayList<>();
        int statementsProduced = 0;

        for (Map.Entry<String, List<TranData>> entry : transactionsByCard.entrySet()) {
            String cardNum = entry.getKey();
            List<TranData> transList = entry.getValue();
            StatementData stmtData = buildStatementData(cardNum, transList, scn);
            plainTextLines.addAll(formatPlainText(stmtData));
            htmlLines.addAll(formatHtml(stmtData));
            statementsProduced++;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("STATEMENTS_PRODUCED", String.valueOf(statementsProduced));
        out.put("TOTAL_RECORDS_READ", String.valueOf(totalRecordsRead));
        out.put("PLAIN_TEXT_LINE_COUNT", String.valueOf(plainTextLines.size()));
        out.put("HTML_LINE_COUNT", String.valueOf(htmlLines.size()));
        for (int i = 0; i < plainTextLines.size(); i++) {
            out.put("PLAIN_" + i, plainTextLines.get(i));
        }
        for (int i = 0; i < htmlLines.size(); i++) {
            out.put("HTML_" + i, htmlLines.get(i));
        }
        return out;
    }

    private TranData parseFldt(String fldt) {
        if (fldt == null || fldt.length() < 16) return null;
        try {
            TranData t = new TranData();
            t.tranId = fldt.substring(0, 16).trim();
            t.tranTypeCd = fldt.substring(16, 18).trim();
            t.tranCatCd = Integer.parseInt(fldt.substring(18, 22).trim().isEmpty() ? "0" : fldt.substring(18, 22).trim());
            t.tranSource = fldt.substring(22, 32).trim();
            t.tranDesc = fldt.substring(32, 132).trim();
            t.tranAmt = new BigDecimal(fldt.substring(132, 146).trim().isEmpty() ? "0" : fldt.substring(132, 146).trim());
            t.tranMerchantId = Integer.parseInt(fldt.substring(146, 155).trim().isEmpty() ? "0" : fldt.substring(146, 155).trim());
            t.tranMerchantName = fldt.substring(155, 205).trim();
            t.tranMerchantCity = fldt.substring(205, 255).trim();
            t.tranMerchantZip = fldt.substring(255, 265).trim();
            t.tranCardNum = fldt.substring(265, 281).trim();
            t.tranOrigTs = fldt.substring(281, 307).trim();
            t.tranProcTs = fldt.substring(307, 333).trim();
            return t;
        } catch (Exception e) {
            return null;
        }
    }

    private StatementData buildStatementData(String cardNum, List<TranData> trans, Scenario scn) {
        StatementData stmt = new StatementData();
        stmt.cardNum = cardNum;
        CardXrefRecord xref = scn.xrefs.get(cardNum);
        if (xref != null) {
            stmt.acctId = xref.xrefAcctId;
            stmt.account = scn.accounts.get(xref.xrefAcctId);
            stmt.customer = scn.customers.get(xref.xrefCustId);
        }
        stmt.transactions = trans;
        BigDecimal total = BD_0_00;
        for (TranData t : trans) {
            total = total.add(t.tranAmt);
        }
        stmt.totalAmount = total;
        return stmt;
    }

    private List<String> formatPlainText(StatementData stmt) {
        List<String> lines = new ArrayList<>();
        StringBuilder stars31 = new StringBuilder();
        for (int i = 0; i < 31; i++) stars31.append('*');
        StringBuilder stars32 = new StringBuilder();
        for (int i = 0; i < 32; i++) stars32.append('*');

        lines.add(stars31.toString() + "START OF STATEMENT" + stars31.toString());

        CustomerRecord cust = stmt.customer;
        if (cust != null) {
            String name = cust.custFirstName.trim() + " " + cust.custLastName.trim();
            lines.add(String.format("%-75s     ", name));
            lines.add(String.format("%-50s              ", cust.custAddrLine1));
            lines.add(String.format("%-50s              ", cust.custAddrLine2));
            String addr3 = cust.custAddrStateCd + " " + cust.custAddrZip;
            lines.add(String.format("%-80s", addr3));
        } else {
            lines.add("Card: " + stmt.cardNum);
        }

        StringBuilder dashes80 = new StringBuilder();
        for (int i = 0; i < 80; i++) dashes80.append('-');

        lines.add(dashes80.toString());
        // 33 spaces + "Basic Details" + 34 spaces
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 33; i++) sb.append(' ');
        sb.append("Basic Details");
        for (int i = 0; i < 34; i++) sb.append(' ');
        lines.add(sb.toString());

        // 40 spaces padding
        StringBuilder pad40 = new StringBuilder();
        for (int i = 0; i < 40; i++) pad40.append(' ');

        lines.add(String.format("Account ID         :%-20s%s", String.valueOf(stmt.acctId), pad40.toString()));

        AccountRecord acct = stmt.account;
        if (acct != null) {
            lines.add(String.format("Current Balance    :%9.2f       %s", acct.acctCurrBal.doubleValue(), pad40.toString()));
            int fico = cust != null ? cust.custFicoCreditScore : 0;
            lines.add(String.format("FICO Score         :%-20s%s", String.valueOf(fico), pad40.toString()));
        }

        lines.add(dashes80.toString());
        // 30 spaces + "TRANSACTION SUMMARY " + 30 spaces
        StringBuilder sb2 = new StringBuilder();
        for (int i = 0; i < 30; i++) sb2.append(' ');
        sb2.append("TRANSACTION SUMMARY ");
        for (int i = 0; i < 30; i++) sb2.append(' ');
        lines.add(sb2.toString());
        lines.add(dashes80.toString());
        lines.add(String.format("%-16s%-51s%13s", "Tran ID", "Tran Details", "  Tran Amount"));

        for (TranData tran : stmt.transactions) {
            String detail = tran.tranDesc.length() > 49
                    ? tran.tranDesc.substring(0, 49) : tran.tranDesc;
            lines.add(String.format("%-16s %-49s$%9.2f-", tran.tranId, detail, tran.tranAmt.doubleValue()));
        }

        lines.add(String.format("%-10s%-56s$%9.2f-", "Total EXP:", "", stmt.totalAmount.doubleValue()));
        lines.add(stars32.toString() + "END OF STATEMENT" + stars32.toString());
        return lines;
    }

    private List<String> formatHtml(StatementData stmt) {
        List<String> lines = new ArrayList<>();
        lines.add("<!DOCTYPE html>");
        lines.add("<html><head><title>CardDemo Statement</title></head><body>");
        lines.add("<table border='1'>");
        lines.add("<tr><th>Card Number</th><td>" + stmt.cardNum + "</td></tr>");
        lines.add("<tr><th>Account ID</th><td>" + stmt.acctId + "</td></tr>");

        if (stmt.account != null) {
            lines.add(String.format("<tr><th>Balance</th><td>$%.2f</td></tr>", stmt.account.acctCurrBal.doubleValue()));
        }

        lines.add("</table>");
        lines.add("<table border='1'><tr><th>Tran ID</th><th>Description</th><th>Amount</th></tr>");
        for (TranData tran : stmt.transactions) {
            String desc = tran.tranDesc.length() > 60
                    ? tran.tranDesc.substring(0, 60) : tran.tranDesc;
            lines.add(String.format("<tr><td>%s</td><td>%s</td><td>$%.2f</td></tr>",
                    tran.tranId, desc, tran.tranAmt.doubleValue()));
        }
        lines.add(String.format("<tr><td colspan='2'><b>TOTAL</b></td><td>$%.2f</td></tr>",
                stmt.totalAmount.doubleValue()));
        lines.add("</table></body></html>");
        return lines;
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

        s.transactions.add(new Cbstm03b.TranRecord(
                "TRN0000000000001", "01", 1,
                "", "Widget purchase",
                new BigDecimal("150.25"), 0,
                "", "", "",
                "4111000000001111",
                "2026-04-01-12.00.00.000000",
                "2026-04-01-12.00.00.000000"
        ));
        s.transactions.add(new Cbstm03b.TranRecord(
                "TRN0000000000002", "01", 1,
                "", "Gadget purchase",
                new BigDecimal("75.50"), 0,
                "", "", "",
                "4111000000001111",
                "2026-04-05-14.30.00.000000",
                "2026-04-05-14.30.00.000000"
        ));

        s.xrefs.put("4111000000001111",
                new CardXrefRecord("4111000000001111", 1, 100000001));
        s.accounts.put(100000001, new AccountRecord(
                100000001, "Y", new BigDecimal("5000.00"), new BigDecimal("10000.00")));
        s.customers.put(1, new CustomerRecord(
                1, "JOHN", "DOE", "123 MAIN ST", "APT 4B",
                "NY", "10001", 750));
        return s;
    }

    private Scenario scenarioEmptyInput() {
        return new Scenario();
    }

    // ── Inner data types ─────────────────────────────────────────────────

    private static class Scenario {
        final List<Cbstm03b.TranRecord> transactions = new ArrayList<>();
        final Map<String, CardXrefRecord> xrefs = new HashMap<>();
        final Map<Integer, AccountRecord> accounts = new HashMap<>();
        final Map<Integer, CustomerRecord> customers = new HashMap<>();
    }

    static class TranData {
        String tranId = "";
        String tranTypeCd = "";
        int tranCatCd = 0;
        String tranSource = "";
        String tranDesc = "";
        BigDecimal tranAmt = BD_0_00;
        int tranMerchantId = 0;
        String tranMerchantName = "";
        String tranMerchantCity = "";
        String tranMerchantZip = "";
        String tranCardNum = "";
        String tranOrigTs = "";
        String tranProcTs = "";
    }

    static class StatementData {
        String cardNum = "";
        int acctId = 0;
        CustomerRecord customer = null;
        AccountRecord account = null;
        List<TranData> transactions = new ArrayList<>();
        BigDecimal totalAmount = BD_0_00;
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
        final BigDecimal acctCurrBal;
        final BigDecimal acctCreditLimit;

        AccountRecord(int acctId, String activeStatus,
                      BigDecimal currBal, BigDecimal creditLimit) {
            this.acctId = acctId;
            this.acctActiveStatus = activeStatus;
            this.acctCurrBal = currBal;
            this.acctCreditLimit = creditLimit;
        }
    }

    static class CustomerRecord {
        final int custId;
        final String custFirstName;
        final String custLastName;
        final String custAddrLine1;
        final String custAddrLine2;
        final String custAddrStateCd;
        final String custAddrZip;
        final int custFicoCreditScore;

        CustomerRecord(int custId, String firstName, String lastName,
                        String addrLine1, String addrLine2,
                        String addrStateCd, String addrZip,
                        int ficoCreditScore) {
            this.custId = custId;
            this.custFirstName = firstName;
            this.custLastName = lastName;
            this.custAddrLine1 = addrLine1;
            this.custAddrLine2 = addrLine2;
            this.custAddrStateCd = addrStateCd;
            this.custAddrZip = addrZip;
            this.custFicoCreditScore = ficoCreditScore;
        }
    }
}
