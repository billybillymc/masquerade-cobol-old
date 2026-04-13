package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.*;

/**
 * Java reimplementation of COCRDSLC — CardDemo Credit Card View/Select Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/cocrdslc.py}. Python is the source of truth.
 *
 * <p>Standalone business method: {@link #processCardView}. The {@link #runVector}
 * method is a thin adapter that builds scenario-specific parameters and delegates.
 */
public class Cocrdslc implements ProgramRunner {

    // ── Inner data types ─────────────────────────────────────────────────

    static class CardRecord {
        final String cardNum;
        final String acctId;
        final String cvv;
        final String embossedName;
        final String expirationDate;
        final String activeStatus;

        CardRecord(String cardNum, String acctId, String cvv,
                   String embossedName, String expirationDate, String activeStatus) {
            this.cardNum = cardNum;
            this.acctId = acctId;
            this.cvv = cvv;
            this.embossedName = embossedName;
            this.expirationDate = expirationDate;
            this.activeStatus = activeStatus;
        }
    }

    static class AccountRecord {
        final String acctId;
        final double currBal;
        final double creditLimit;

        AccountRecord(String acctId, double currBal, double creditLimit) {
            this.acctId = acctId;
            this.currBal = currBal;
            this.creditLimit = creditLimit;
        }
    }

    static class XrefRecord {
        final String cardNum;
        final String custId;
        final String acctId;

        XrefRecord(String cardNum, String custId, String acctId) {
            this.cardNum = cardNum;
            this.custId = custId;
            this.acctId = acctId;
        }
    }

    static class CustomerRecord {
        final String custId;
        final String firstName;
        final String lastName;

        CustomerRecord(String custId, String firstName, String lastName) {
            this.custId = custId;
            this.firstName = firstName;
            this.lastName = lastName;
        }
    }

    static class CardDetailData {
        String cardNum = "";
        String acctId = "";
        String embossedName = "";
        String custName = "";
        String acctCurrBal = "";
    }

    static class CardViewResult {
        CardDetailData cardData = null;
        boolean error = false;
        String message = "";
        String xctlProgram = "";
        boolean returnToPrev = false;
    }

    // ── Repositories ────────────────────────────────────────────────────

    static class CardRepo {
        private final Map<String, CardRecord> cards;
        CardRepo(Map<String, CardRecord> cards) { this.cards = cards; }
        CardRecord find(String cardNum) { return cards.get(cardNum.trim()); }
    }

    static class AccountRepo {
        private final Map<String, AccountRecord> accounts;
        AccountRepo(Map<String, AccountRecord> accounts) { this.accounts = accounts; }
        AccountRecord find(String acctId) { return accounts.get(acctId); }
    }

    static class XrefRepo {
        private final Map<String, XrefRecord> byCard;
        XrefRepo(Map<String, XrefRecord> byCard) { this.byCard = byCard; }
        XrefRecord findByCard(String cardNum) { return byCard.get(cardNum.trim()); }
    }

    static class CustomerRepo {
        private final Map<String, CustomerRecord> customers;
        CustomerRepo(Map<String, CustomerRecord> customers) { this.customers = customers; }
        CustomerRecord find(String custId) { return customers.get(custId); }
    }

    // ── Standalone business method ──────────────────────────────────────

    /**
     * Process card view screen — mirrors Python's process_card_view.
     *
     * @param eibcalen      CICS EIBCALEN (0 = first entry, no commarea)
     * @param eibaid        aid key pressed (ENTER, PF3, etc.)
     * @param pgmContext    commarea program context (0 = initial)
     * @param fromProgram   commarea cdemo_from_program
     * @param cardNumInput  card number typed by user
     * @param preloadedCardNum card number preloaded from previous screen
     * @param cardRepo      card repository
     * @param accountRepo   account repository
     * @param xrefRepo      xref repository
     * @param customerRepo  customer repository
     * @return CardViewResult with all output fields
     */
    CardViewResult processCardView(
            int eibcalen,
            String eibaid,
            int pgmContext,
            String fromProgram,
            String cardNumInput,
            String preloadedCardNum,
            CardRepo cardRepo,
            AccountRepo accountRepo,
            XrefRepo xrefRepo,
            CustomerRepo customerRepo
    ) {
        CardViewResult result = new CardViewResult();

        if (eibcalen == 0) {
            result.returnToPrev = true;
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (eibaid.equals("PF3")) {
            String back = (fromProgram != null && !fromProgram.isEmpty()) ? fromProgram : "COMEN01C";
            result.xctlProgram = back;
            result.returnToPrev = true;
            return result;
        }

        if (pgmContext == 0) {
            String searchNum = (preloadedCardNum != null && !preloadedCardNum.isEmpty())
                    ? preloadedCardNum : cardNumInput;
            if (searchNum != null && !searchNum.trim().isEmpty()) {
                lookupCard(searchNum, cardRepo, accountRepo, xrefRepo, customerRepo, result);
            }
            return result;
        }

        // Process ENTER with card number
        return processEnter(cardNumInput, cardRepo, accountRepo, xrefRepo, customerRepo, result);
    }

    private CardViewResult processEnter(
            String cardNumInput,
            CardRepo cardRepo, AccountRepo accountRepo,
            XrefRepo xrefRepo, CustomerRepo customerRepo,
            CardViewResult result
    ) {
        if (cardNumInput == null || cardNumInput.trim().isEmpty()) {
            result.error = true;
            result.message = "Card number not provided";
            return result;
        }
        lookupCard(cardNumInput, cardRepo, accountRepo, xrefRepo, customerRepo, result);
        return result;
    }

    private void lookupCard(
            String cardNum,
            CardRepo cardRepo, AccountRepo accountRepo,
            XrefRepo xrefRepo, CustomerRepo customerRepo,
            CardViewResult result
    ) {
        CardRecord card = cardRepo.find(cardNum);
        if (card == null) {
            result.error = true;
            result.message = "Card " + cardNum.trim() + " not found";
            return;
        }

        AccountRecord acct = accountRepo.find(card.acctId);
        XrefRecord xref = xrefRepo.findByCard(card.cardNum);
        CustomerRecord cust = null;
        if (xref != null) {
            cust = customerRepo.find(xref.custId);
        }

        CardDetailData data = new CardDetailData();
        data.cardNum = card.cardNum;
        data.acctId = card.acctId;
        data.embossedName = card.embossedName.trim();
        data.custName = (cust != null) ? (cust.firstName.trim() + " " + cust.lastName.trim()) : "";
        data.acctCurrBal = (acct != null) ? String.format("%,.2f", acct.currBal) : "";

        result.cardData = data;
        result.message = "Card record found";
    }

    // ── Seed data ───────────────────────────────────────────────────────

    private static final Map<String, CardRecord> SEED_CARDS = new LinkedHashMap<>();
    private static final Map<String, AccountRecord> SEED_ACCOUNTS = new LinkedHashMap<>();
    private static final Map<String, XrefRecord> SEED_XREFS = new LinkedHashMap<>();
    private static final Map<String, CustomerRecord> SEED_CUSTOMERS = new LinkedHashMap<>();

    static {
        SEED_CARDS.put("4111111111110001", new CardRecord("4111111111110001", "10000001", "123", "JANE USER", "2028-12-31", "Y"));
        SEED_CARDS.put("4111111111110002", new CardRecord("4111111111110002", "10000001", "456", "BOB SMITH", "2027-06-30", "Y"));

        SEED_ACCOUNTS.put("10000001", new AccountRecord("10000001", 1500.00, 5000.00));

        SEED_XREFS.put("4111111111110001", new XrefRecord("4111111111110001", "100001", "10000001"));
        SEED_XREFS.put("4111111111110002", new XrefRecord("4111111111110002", "100001", "10000001"));

        SEED_CUSTOMERS.put("100001", new CustomerRecord("100001", "Jane", "User"));
    }

    // ── Thin runVector adapter ──────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "FIRST_ENTRY");

        CardRepo cardRepo = new CardRepo(new LinkedHashMap<>(SEED_CARDS));
        AccountRepo accountRepo = new AccountRepo(new LinkedHashMap<>(SEED_ACCOUNTS));
        XrefRepo xrefRepo = new XrefRepo(new LinkedHashMap<>(SEED_XREFS));
        CustomerRepo customerRepo = new CustomerRepo(new LinkedHashMap<>(SEED_CUSTOMERS));

        CardViewResult result;

        switch (scenario) {
            case "FIRST_ENTRY":
                result = processCardView(100, "ENTER", 0, "COCRDLIC",
                        "", "4111111111110001",
                        cardRepo, accountRepo, xrefRepo, customerRepo);
                break;

            case "LOOKUP_CARD":
                result = processCardView(100, "ENTER", 1, "COCRDLIC",
                        "4111111111110002", "",
                        cardRepo, accountRepo, xrefRepo, customerRepo);
                break;

            case "CARD_NOT_FOUND":
                result = processCardView(100, "ENTER", 1, "COCRDLIC",
                        "9999999999999999", "",
                        cardRepo, accountRepo, xrefRepo, customerRepo);
                break;

            case "PF3_RETURN":
                result = processCardView(100, "PF3", 1, "COCRDLIC",
                        "", "",
                        cardRepo, accountRepo, xrefRepo, customerRepo);
                break;

            default:
                result = processCardView(100, "ENTER", 0, "COCRDLIC",
                        "", "4111111111110001",
                        cardRepo, accountRepo, xrefRepo, customerRepo);
                break;
        }

        String cardNumOut = "";
        String acctIdOut = "";
        String embossedNameOut = "";
        String custNameOut = "";
        String acctCurrBalOut = "";
        if (result.cardData != null) {
            cardNumOut = result.cardData.cardNum;
            acctIdOut = result.cardData.acctId;
            embossedNameOut = result.cardData.embossedName;
            custNameOut = result.cardData.custName;
            acctCurrBalOut = result.cardData.acctCurrBal;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("XCTL_PROGRAM", result.xctlProgram);
        out.put("RETURN_TO_PREV", result.returnToPrev ? "Y" : "N");
        out.put("CARD_NUM", cardNumOut);
        out.put("ACCT_ID", acctIdOut);
        out.put("EMBOSSED_NAME", embossedNameOut);
        out.put("CUST_NAME", custNameOut);
        out.put("ACCT_CURR_BAL", acctCurrBalOut);
        return out;
    }
}
