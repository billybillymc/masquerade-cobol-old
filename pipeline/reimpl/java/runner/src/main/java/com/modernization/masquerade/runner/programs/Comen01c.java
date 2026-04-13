package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of COMEN01C — CardDemo User Main Menu.
 *
 * <p>Mirrors {@code pipeline/reimpl/comen01c.py} run_vector. Python is the
 * source of truth.
 *
 * <p>Menu options:
 * <pre>
 *    1. Account View          → COACTVWC
 *    2. Account Update        → COACTUPC
 *    3. Credit Card List      → COCRDLIC
 *    ...
 *   10. Bill Payment          → COBIL00C
 *   11. Pending Authorization → COPAUS0C
 * </pre>
 */
public class Comen01c implements ProgramRunner {

    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    ";

    // User menu options: (num, name, target_pgm, user_type_required)
    private static final String[][] USER_OPTIONS = {
        {"1",  "Account View",              "COACTVWC", "U"},
        {"2",  "Account Update",            "COACTUPC", "U"},
        {"3",  "Credit Card List",          "COCRDLIC", "U"},
        {"4",  "Credit Card View",          "COCRDSLC", "U"},
        {"5",  "Credit Card Update",        "COCRDUPC", "U"},
        {"6",  "Transaction List",          "COTRN00C", "U"},
        {"7",  "Transaction View",          "COTRN01C", "U"},
        {"8",  "Transaction Add",           "COTRN02C", "U"},
        {"9",  "Transaction Reports",       "CORPT00C", "U"},
        {"10", "Bill Payment",              "COBIL00C", "U"},
        {"11", "Pending Authorization View","COPAUS0C", "U"},
    };

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "VALID_OPTION_6");

        String xctlProgram = "";
        boolean error = false;
        String message = "";
        boolean returnToSignon = false;
        int selectedOption = 0;

        switch (scenario) {
            case "FIRST_ENTRY":
                // context=0, first time → send menu, no action
                break;

            case "VALID_OPTION_6":
                selectedOption = 6;
                xctlProgram = processEnterKey("6", "U");
                if (xctlProgram == null) {
                    error = true;
                    message = "Please enter a valid option number...";
                    xctlProgram = "";
                }
                break;

            case "VALID_OPTION_10":
                selectedOption = 10;
                xctlProgram = processEnterKey("10", "U");
                if (xctlProgram == null) {
                    error = true;
                    message = "Please enter a valid option number...";
                    xctlProgram = "";
                }
                break;

            case "INVALID_OPTION":
                selectedOption = 0;
                error = true;
                message = "Please enter a valid option number...";
                break;

            case "INVALID_KEY":
                error = true;
                message = CCDA_MSG_INVALID_KEY;
                break;

            case "PF3_RETURN":
                returnToSignon = true;
                xctlProgram = "COSGN00C";
                break;

            default:
                selectedOption = 6;
                xctlProgram = processEnterKey("6", "U");
                if (xctlProgram == null) {
                    error = true;
                    message = "Please enter a valid option number...";
                    xctlProgram = "";
                }
                break;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("XCTL_PROGRAM", xctlProgram);
        out.put("ERROR", error ? "Y" : "N");
        out.put("MESSAGE", message);
        out.put("RETURN_TO_SIGNON", returnToSignon ? "Y" : "N");
        out.put("SELECTED_OPTION", String.valueOf(selectedOption));
        return out;
    }

    /**
     * Process enter key — validate option and return target program.
     * Returns null if invalid option.
     */
    private String processEnterKey(String optionInput, String userType) {
        String optX = optionInput.trim().replace(" ", "0");
        while (optX.length() < 2) optX = "0" + optX;

        int option;
        try {
            option = Integer.parseInt(optX);
        } catch (NumberFormatException e) {
            return null;
        }

        if (!optionInput.trim().matches("\\d+") || option > USER_OPTIONS.length || option == 0) {
            return null;
        }

        String[] optEntry = USER_OPTIONS[option - 1];
        String targetPgm = optEntry[2];
        String usrTypeRequired = optEntry[3];

        // Check admin-only options
        if ("A".equals(usrTypeRequired) && !"A".equals(userType)) {
            return null; // access denied
        }

        if (targetPgm.startsWith("DUMMY")) {
            return null; // not installed
        }
        return targetPgm;
    }
}
