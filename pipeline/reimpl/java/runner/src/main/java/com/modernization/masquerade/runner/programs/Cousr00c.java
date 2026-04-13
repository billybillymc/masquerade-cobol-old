package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.*;

/**
 * Java reimplementation of COUSR00C — CardDemo User List Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/cousr00c.py} run_vector. Python is the
 * source of truth.
 */
public class Cousr00c implements ProgramRunner {

    // Seed data — same users as Python adapter
    private static final String[][] SEED_USERS = {
        {"ADMIN001", "John",  "Admin", "PASS1234", "A"},
        {"USER0001", "Jane",  "User",  "MYPASSWD", "U"},
        {"USER0002", "Bob",   "Smith", "BOBPASS1", "U"},
        {"USER0003", "Alice", "Jones", "ALICEPASS","U"},
    };

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "FIRST_ENTRY");

        // Build sorted user list
        String[][] users = SEED_USERS.clone();
        Arrays.sort(users, Comparator.comparing(a -> a[0]));

        String xctlProgram = "";
        boolean error = false;
        String message = "";
        boolean returnToPrev = false;
        String selectedUserId = "";
        String selectedAction = "";
        int pageNum = 1;
        List<String[]> rows = new ArrayList<>();
        boolean hasNext = false;
        boolean hasPrev = false;

        switch (scenario) {
            case "FIRST_ENTRY":
                // context=0 → load page 1
                rows = getPage(users, 1);
                pageNum = 1;
                hasNext = users.length > 10;
                hasPrev = false;
                break;

            case "LIST_PAGE_1":
                // context=1, ENTER, no selection → refresh page
                rows = getPage(users, 1);
                pageNum = 1;
                hasNext = users.length > 10;
                hasPrev = false;
                break;

            case "SELECT_UPDATE":
                // ENTER with U selection on USER0001
                selectedUserId = "USER0001";
                selectedAction = "U";
                xctlProgram = "COUSR02C";
                break;

            case "SELECT_DELETE":
                // ENTER with D selection on USER0002
                selectedUserId = "USER0002";
                selectedAction = "D";
                xctlProgram = "COUSR03C";
                break;

            case "PF3_RETURN":
                returnToPrev = true;
                xctlProgram = "COADM01C";
                break;

            case "INVALID_KEY":
                error = true;
                message = "Invalid key pressed.                    ";
                rows = getPage(users, 1);
                pageNum = 1;
                hasNext = users.length > 10;
                hasPrev = false;
                break;

            default:
                // same as FIRST_ENTRY
                rows = getPage(users, 1);
                pageNum = 1;
                hasNext = users.length > 10;
                hasPrev = false;
                break;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("PAGE_NUM", String.valueOf(pageNum));
        out.put("ROW_COUNT", String.valueOf(rows.size()));
        out.put("HAS_NEXT", hasNext ? "Y" : "N");
        out.put("HAS_PREV", hasPrev ? "Y" : "N");
        out.put("ERROR", error ? "Y" : "N");
        out.put("MESSAGE", message);
        out.put("XCTL_PROGRAM", xctlProgram);
        out.put("SELECTED_USER_ID", selectedUserId);
        out.put("SELECTED_ACTION", selectedAction);
        out.put("RETURN_TO_PREV", returnToPrev ? "Y" : "N");

        for (int i = 0; i < rows.size(); i++) {
            String[] u = rows.get(i);
            String userName = (u[1] + " " + u[2]).trim();
            String userType = "A".equals(u[4]) ? "Admin" : "Regular";
            out.put("ROW_" + i + "_USER_ID", u[0]);
            out.put("ROW_" + i + "_USER_NAME", userName);
            out.put("ROW_" + i + "_USER_TYPE", userType);
        }
        return out;
    }

    private List<String[]> getPage(String[][] users, int pageNum) {
        int pageSize = 10;
        int start = (pageNum - 1) * pageSize;
        int end = Math.min(start + pageSize, users.length);
        List<String[]> page = new ArrayList<>();
        for (int i = start; i < end; i++) {
            page.add(users[i]);
        }
        return page;
    }
}
