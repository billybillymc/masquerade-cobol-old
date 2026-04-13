package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of COADM01C — CardDemo Admin Menu.
 *
 * <p>Mirrors {@code pipeline/reimpl/coadm01c.py} run_vector. Python is the
 * source of truth.
 *
 * <p>Admin menu options:
 * <pre>
 *   1. User List (Security)               → COUSR00C
 *   2. User Add (Security)                → COUSR01C
 *   3. User Update (Security)             → COUSR02C
 *   4. User Delete (Security)             → COUSR03C
 *   5. Transaction Type List/Update (Db2) → COTRTLIC
 *   6. Transaction Type Maintenance (Db2) → COTRTUPC
 * </pre>
 */
public class Coadm01c implements ProgramRunner {

    private static final String WS_PGMNAME = "COADM01C";
    private static final String WS_TRANID = "CA00";
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    ";

    // Admin menu options: (num, name, target_pgm)
    private static final String[][] ADMIN_OPTIONS = {
        {"1", "User List (Security)",               "COUSR00C"},
        {"2", "User Add (Security)",                "COUSR01C"},
        {"3", "User Update (Security)",             "COUSR02C"},
        {"4", "User Delete (Security)",             "COUSR03C"},
        {"5", "Transaction Type List/Update (Db2)", "COTRTLIC"},
        {"6", "Transaction Type Maintenance (Db2)", "COTRTUPC"},
    };

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "VALID_OPTION_1");

        String xctlProgram = "";
        boolean error = false;
        String message = "";
        boolean returnToSignon = false;
        int selectedOption = 0;

        switch (scenario) {
            case "FIRST_ENTRY":
                // context=0, first time → send menu, no action
                break;

            case "VALID_OPTION_1":
                selectedOption = 1;
                xctlProgram = processEnterKey("1");
                if (xctlProgram == null) {
                    error = true;
                    message = "Please enter a valid option number...";
                    xctlProgram = "";
                }
                break;

            case "VALID_OPTION_5":
                selectedOption = 5;
                xctlProgram = processEnterKey("5");
                if (xctlProgram == null) {
                    error = true;
                    message = "Please enter a valid option number...";
                    xctlProgram = "";
                }
                break;

            case "INVALID_OPTION":
                selectedOption = 99;
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
                selectedOption = 1;
                xctlProgram = processEnterKey("1");
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
    private String processEnterKey(String optionInput) {
        String optX = optionInput.trim().replace(" ", "0");
        while (optX.length() < 2) optX = "0" + optX;

        int option;
        try {
            option = Integer.parseInt(optX);
        } catch (NumberFormatException e) {
            return null;
        }

        if (!optionInput.trim().matches("\\d+") || option > ADMIN_OPTIONS.length || option == 0) {
            return null;
        }

        String targetPgm = ADMIN_OPTIONS[option - 1][2];
        if (targetPgm.startsWith("DUMMY")) {
            return null; // not installed
        }
        return targetPgm;
    }
}
