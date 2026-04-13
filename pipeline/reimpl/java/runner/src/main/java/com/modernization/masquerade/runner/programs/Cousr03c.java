package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.*;

/**
 * Java reimplementation of COUSR03C — CardDemo Delete User Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/cousr03c.py}. Python is the source of truth.
 *
 * <p>Structure: standalone {@link #processDeleteUser} method + thin
 * {@link #runVector} adapter.
 */
public class Cousr03c implements ProgramRunner {

    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    ";
    private static final int DFHRESP_NORMAL = 0;
    private static final int DFHRESP_NOTFND = 13;

    // ── Inner data types ────────────────────────────────────────────────────

    static class SecUserData {
        String secUsrId;
        String secUsrFname;
        String secUsrLname;
        String secUsrPwd;
        String secUsrType;

        SecUserData(String id, String fname, String lname, String pwd, String type) {
            this.secUsrId = id;
            this.secUsrFname = fname;
            this.secUsrLname = lname;
            this.secUsrPwd = pwd;
            this.secUsrType = type;
        }
    }

    static class DeleteUserResult {
        SecUserData userFound = null;
        String message = "";
        boolean error = false;
        boolean deleted = false;
        String xctlProgram = "";
        boolean returnToPrev = false;
        String confirmMessage = "";
    }

    // ── Repository ──────────────────────────────────────────────────────────

    static class UserSecRepository {
        private final Map<String, SecUserData> users;

        UserSecRepository(Map<String, SecUserData> users) {
            this.users = new LinkedHashMap<>(users);
        }

        SecUserData find(String userId) {
            return users.get(userId.trim());
        }

        int delete(String userId) {
            String key = userId.trim();
            if (!users.containsKey(key)) return DFHRESP_NOTFND;
            users.remove(key);
            return DFHRESP_NORMAL;
        }
    }

    // ── Standalone business method ──────────────────────────────────────────

    /**
     * Process delete-user screen — mirrors {@code process_delete_user} in
     * {@code pipeline/reimpl/cousr03c.py}.
     */
    DeleteUserResult processDeleteUser(
            int eibcalen, String eibaid, int pgmContext, String fromProgram,
            String userIdInput, UserSecRepository userRepo,
            String preloadedUserId) {

        DeleteUserResult result = new DeleteUserResult();

        if (eibcalen == 0) {
            result.returnToPrev = true;
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (pgmContext == 0) {
            if (preloadedUserId != null && !preloadedUserId.isEmpty()) {
                lookupAndDisplay(preloadedUserId, userRepo, result);
            }
            return result;
        }

        if ("ENTER".equals(eibaid)) {
            return processEnter(userIdInput, userRepo, result);
        } else if ("PF3".equals(eibaid)) {
            String back = (fromProgram != null && !fromProgram.isEmpty()) ? fromProgram : "COADM01C";
            result.xctlProgram = back;
            result.returnToPrev = true;
            return result;
        } else if ("PF4".equals(eibaid)) {
            return result;
        } else if ("PF5".equals(eibaid)) {
            return deleteUser(userIdInput, userRepo, result);
        } else if ("PF12".equals(eibaid)) {
            result.xctlProgram = "COADM01C";
            result.returnToPrev = true;
            return result;
        } else {
            result.error = true;
            result.message = CCDA_MSG_INVALID_KEY;
            return result;
        }
    }

    private void lookupAndDisplay(String userId, UserSecRepository repo, DeleteUserResult result) {
        SecUserData user = repo.find(userId);
        if (user == null) {
            result.error = true;
            result.message = "User ID NOT found...";
        } else {
            result.userFound = user;
            result.confirmMessage = "Press PF5 key to delete this user ...";
        }
    }

    private DeleteUserResult processEnter(String userId, UserSecRepository repo, DeleteUserResult result) {
        if (userId == null || userId.trim().isEmpty()) {
            result.error = true;
            result.message = "User ID can NOT be empty...";
            return result;
        }

        lookupAndDisplay(userId, repo, result);
        return result;
    }

    private DeleteUserResult deleteUser(String userId, UserSecRepository repo, DeleteUserResult result) {
        if (userId == null || userId.trim().isEmpty()) {
            result.error = true;
            result.message = "User ID can NOT be empty...";
            return result;
        }

        int resp = repo.delete(userId);
        if (resp == DFHRESP_NORMAL) {
            result.deleted = true;
            result.message = "User " + userId.trim() + " has been deleted ...";
        } else if (resp == DFHRESP_NOTFND) {
            result.error = true;
            result.message = "User ID NOT found...";
        } else {
            result.error = true;
            result.message = "Unable to Update User...";
        }

        return result;
    }

    // ── runVector adapter ───────────────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "FIRST_ENTRY");

        // Seed data
        Map<String, SecUserData> seedUsers = new LinkedHashMap<>();
        seedUsers.put("ADMIN001", new SecUserData("ADMIN001", "John", "Admin", "PASS1234", "A"));
        seedUsers.put("USER0001", new SecUserData("USER0001", "Jane", "User", "MYPASSWD", "U"));
        seedUsers.put("USER0002", new SecUserData("USER0002", "Bob", "Smith", "BOBPASS1", "U"));
        UserSecRepository repo = new UserSecRepository(seedUsers);

        DeleteUserResult result;

        switch (scenario) {
            case "FIRST_ENTRY":
                result = processDeleteUser(100, "ENTER", 0, "COUSR00C",
                        "", repo, "USER0002");
                break;
            case "LOOKUP_USER":
                result = processDeleteUser(100, "ENTER", 1, "COUSR00C",
                        "USER0001", repo, "");
                break;
            case "DELETE_USER":
                result = processDeleteUser(100, "PF5", 1, "COUSR00C",
                        "USER0002", repo, "");
                break;
            case "USER_NOT_FOUND":
                result = processDeleteUser(100, "PF5", 1, "COUSR00C",
                        "NOSUCHID", repo, "");
                break;
            case "PF3_RETURN":
                result = processDeleteUser(100, "PF3", 1, "COUSR00C",
                        "", repo, "");
                break;
            default:
                result = processDeleteUser(100, "ENTER", 0, "COUSR00C",
                        "", repo, "USER0002");
                break;
        }

        String userId = "";
        if (result.userFound != null) {
            userId = result.userFound.secUsrId;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("DELETED", result.deleted ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("XCTL_PROGRAM", result.xctlProgram != null ? result.xctlProgram : "");
        out.put("RETURN_TO_PREV", result.returnToPrev ? "Y" : "N");
        out.put("USER_ID", userId);
        out.put("CONFIRM_MESSAGE", result.confirmMessage);
        return out;
    }
}
