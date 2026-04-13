package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.*;

/**
 * Java reimplementation of COCRDUPC — CardDemo Credit Card Update Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/cocrdupc.py}. Python is the source of truth.
 *
 * <p>Standalone business method: {@link #processCardUpdate}. The {@link #runVector}
 * method is a thin adapter that builds scenario-specific parameters and delegates.
 */
public class Cocrdupc implements ProgramRunner {

    // ── Inner data types ─────────────────────────────────────────────────

    static class CardRecord {
        String cardNum;
        String acctId;
        String cvv;
        String embossedName;
        String expirationDate;
        String activeStatus;

        CardRecord(String cardNum, String acctId, String cvv,
                   String embossedName, String expirationDate, String activeStatus) {
            this.cardNum = cardNum;
            this.acctId = acctId;
            this.cvv = cvv;
            this.embossedName = embossedName;
            this.expirationDate = expirationDate;
            this.activeStatus = activeStatus;
        }

        CardRecord copy() {
            return new CardRecord(cardNum, acctId, cvv, embossedName, expirationDate, activeStatus);
        }
    }

    static class CardUpdateInput {
        String cardNum = "";
        String embossedName = "";
        String expirationDate = "";
        String activeStatus = "";
        String cvvCd = "";

        CardUpdateInput() {}

        CardUpdateInput(String cardNum, String embossedName, String expirationDate,
                        String activeStatus, String cvvCd) {
            this.cardNum = cardNum;
            this.embossedName = embossedName;
            this.expirationDate = expirationDate;
            this.activeStatus = activeStatus;
            this.cvvCd = cvvCd;
        }
    }

    static class CardUpdateResult {
        CardRecord cardFound = null;
        boolean error = false;
        boolean success = false;
        String message = "";
        String xctlProgram = "";
        boolean returnToPrev = false;
    }

    static class CardRepo {
        private final Map<String, CardRecord> cards;
        CardRepo(Map<String, CardRecord> cards) { this.cards = cards; }

        CardRecord find(String cardNum) {
            return cards.get(cardNum.trim());
        }

        boolean rewrite(CardRecord card) {
            String key = card.cardNum.trim();
            if (!cards.containsKey(key)) return false;
            cards.put(key, card);
            return true;
        }
    }

    // ── Standalone business method ──────────────────────────────────────

    /**
     * Process card update screen — mirrors Python's process_card_update.
     *
     * @param eibcalen         CICS EIBCALEN
     * @param eibaid           aid key pressed
     * @param pgmContext       commarea program context (0 = initial)
     * @param fromProgram      commarea cdemo_from_program
     * @param cardInput        update input fields
     * @param cardRepo         card repository
     * @param preloadedCardNum card number preloaded from previous screen
     * @return CardUpdateResult with all output fields
     */
    CardUpdateResult processCardUpdate(
            int eibcalen,
            String eibaid,
            int pgmContext,
            String fromProgram,
            CardUpdateInput cardInput,
            CardRepo cardRepo,
            String preloadedCardNum
    ) {
        CardUpdateResult result = new CardUpdateResult();

        if (eibcalen == 0) {
            result.returnToPrev = true;
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (pgmContext == 0) {
            if (preloadedCardNum != null && !preloadedCardNum.isEmpty()) {
                CardRecord card = cardRepo.find(preloadedCardNum);
                result.cardFound = card;
                if (card == null) {
                    result.error = true;
                    result.message = "Card " + preloadedCardNum.trim() + " not found";
                }
            }
            return result;
        }

        switch (eibaid) {
            case "ENTER":
                return lookupCard(cardInput.cardNum, cardRepo, result);
            case "PF3": {
                String back = (fromProgram != null && !fromProgram.isEmpty()) ? fromProgram : "COMEN01C";
                result.xctlProgram = back;
                result.returnToPrev = true;
                return result;
            }
            case "PF5":
                return saveCard(cardInput, cardRepo, result);
            case "PF12":
                result.xctlProgram = "COCRDLIC";
                result.returnToPrev = true;
                return result;
            default:
                result.error = true;
                result.message = "Invalid key pressed.";
                return result;
        }
    }

    private CardUpdateResult lookupCard(String cardNum, CardRepo repo, CardUpdateResult result) {
        if (cardNum == null || cardNum.trim().isEmpty()) {
            result.error = true;
            result.message = "Card number can NOT be empty...";
            return result;
        }
        CardRecord card = repo.find(cardNum);
        if (card == null) {
            result.error = true;
            result.message = "Card " + cardNum.trim() + " not found";
        } else {
            result.cardFound = card;
            result.message = "Press PF5 to save changes";
        }
        return result;
    }

    private CardUpdateResult saveCard(CardUpdateInput inp, CardRepo repo, CardUpdateResult result) {
        if (inp.cardNum == null || inp.cardNum.trim().isEmpty()) {
            result.error = true;
            result.message = "Card number can NOT be empty...";
            return result;
        }
        CardRecord card = repo.find(inp.cardNum);
        if (card == null) {
            result.error = true;
            result.message = "Card " + inp.cardNum.trim() + " not found";
            return result;
        }

        // Apply updates
        if (inp.embossedName != null && !inp.embossedName.trim().isEmpty()) {
            card.embossedName = inp.embossedName.length() > 50
                    ? inp.embossedName.substring(0, 50) : inp.embossedName;
        }
        if (inp.expirationDate != null && !inp.expirationDate.trim().isEmpty()) {
            card.expirationDate = inp.expirationDate.length() > 10
                    ? inp.expirationDate.substring(0, 10) : inp.expirationDate;
        }
        if (inp.activeStatus != null && !inp.activeStatus.trim().isEmpty()) {
            card.activeStatus = inp.activeStatus.trim().substring(0, 1);
        }
        if (inp.cvvCd != null && !inp.cvvCd.trim().isEmpty()) {
            try {
                Integer.parseInt(inp.cvvCd.trim());
                card.cvv = inp.cvvCd.trim();
            } catch (NumberFormatException e) {
                result.error = true;
                result.message = "CVV must be numeric";
                return result;
            }
        }

        boolean ok = repo.rewrite(card);
        if (ok) {
            result.success = true;
            result.cardFound = card;
            result.message = "Card " + card.cardNum.trim() + " has been updated ...";
        } else {
            result.error = true;
            result.message = "Unable to update card...";
        }
        return result;
    }

    // ── Seed data ───────────────────────────────────────────────────────

    private static final Map<String, CardRecord> SEED_CARDS = new LinkedHashMap<>();
    static {
        SEED_CARDS.put("4111111111110001", new CardRecord("4111111111110001", "10000001", "123", "JANE USER", "2028-12-31", "Y"));
        SEED_CARDS.put("4111111111110002", new CardRecord("4111111111110002", "10000001", "456", "BOB SMITH", "2027-06-30", "Y"));
    }

    private Map<String, CardRecord> deepCopySeedCards() {
        Map<String, CardRecord> copy = new LinkedHashMap<>();
        for (Map.Entry<String, CardRecord> e : SEED_CARDS.entrySet()) {
            copy.put(e.getKey(), e.getValue().copy());
        }
        return copy;
    }

    // ── Thin runVector adapter ──────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "FIRST_ENTRY");

        CardRepo repo = new CardRepo(deepCopySeedCards());

        CardUpdateResult result;

        switch (scenario) {
            case "FIRST_ENTRY":
                result = processCardUpdate(100, "ENTER", 0, "COCRDLIC",
                        new CardUpdateInput(), repo, "4111111111110001");
                break;

            case "LOOKUP_CARD":
                result = processCardUpdate(100, "ENTER", 1, "COCRDLIC",
                        new CardUpdateInput("4111111111110001", "", "", "", ""),
                        repo, "");
                break;

            case "UPDATE_CARD":
                result = processCardUpdate(100, "PF5", 1, "COCRDLIC",
                        new CardUpdateInput("4111111111110001", "JANE UPDATED", "2029-12-31", "Y", "999"),
                        repo, "");
                break;

            case "CARD_NOT_FOUND":
                result = processCardUpdate(100, "ENTER", 1, "COCRDLIC",
                        new CardUpdateInput("9999999999999999", "", "", "", ""),
                        repo, "");
                break;

            case "PF3_RETURN":
                result = processCardUpdate(100, "PF3", 1, "COCRDLIC",
                        new CardUpdateInput(), repo, "");
                break;

            default:
                result = processCardUpdate(100, "ENTER", 0, "COCRDLIC",
                        new CardUpdateInput(), repo, "4111111111110001");
                break;
        }

        String cardNumOut = "";
        String embossedNameOut = "";
        if (result.cardFound != null) {
            cardNumOut = result.cardFound.cardNum;
            embossedNameOut = result.cardFound.embossedName;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("SUCCESS", result.success ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("XCTL_PROGRAM", result.xctlProgram);
        out.put("RETURN_TO_PREV", result.returnToPrev ? "Y" : "N");
        out.put("CARD_NUM", cardNumOut);
        out.put("EMBOSSED_NAME", embossedNameOut);
        return out;
    }
}
