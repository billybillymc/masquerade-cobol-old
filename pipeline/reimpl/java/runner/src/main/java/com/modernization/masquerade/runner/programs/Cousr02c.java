package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.*;

/**
 * Java reimplementation of COUSR02C — CardDemo Update User Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/cousr02c.py}. Python is the source of truth.
 *
 * <p>Structure: standalone {@link #processUpdateUser} method + thin
 * {@link #runVector} adapter.
 */
public class Cousr02c implements ProgramRunner {

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

        SecUserData copy() {
            return new SecUserData(secUsrId, secUsrFname, secUsrLname, secUsrPwd, secUsrType);
        }
    }

    static class UpdateUserInput {
        String userIdInput = "";
        String firstName = "";
        String lastName = "";
        String password = "";
        String userType = "";

        UpdateUserInput() {}

        UpdateUserInput(String userIdInput, String firstName, String lastName,
                        String password, String userType) {
            this.userIdInput = userIdInput != null ? userIdInput : "";
            this.firstName = firstName != null ? firstName : "";
            this.lastName = lastName != null ? lastName : "";
            this.password = password != null ? password : "";
            this.userType = userType != null ? userType : "";
        }
    }

    static class UpdateUserResult {
        SecUserData userFound = null;
        String message = "";
        boolean error = false;
        boolean success = false;
        String xctlProgram = "";
        boolean returnToPrev = false;
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

        int rewrite(SecUserData user) {
            String key = user.secUsrId.trim();
            if (!users.containsKey(key)) return DFHRESP_NOTFND;
            users.put(key, user);
            return DFHRESP_NORMAL;
        }
    }

    // ── Standalone business method ──────────────────────────────────────────

    /**
     * Process update-user screen — mirrors {@code process_update_user} in
     * {@code pipeline/reimpl/cousr02c.py}.
     */
    UpdateUserResult processUpdateUser(
            int eibcalen, String eibaid, int pgmContext, String fromProgram,
            UpdateUserInput userInput, UserSecRepository userRepo,
            String preloadedUserId) {

        UpdateUserResult result = new UpdateUserResult();

        if (eibcalen == 0) {
            result.returnToPrev = true;
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (pgmContext == 0) {
            if (preloadedUserId != null && !preloadedUserId.isEmpty()) {
                SecUserData user = userRepo.find(preloadedUserId);
                result.userFound = user;
                if (user == null) {
                    result.error = true;
                    result.message = "User ID NOT found...";
                }
            }
            return result;
        }

        if ("ENTER".equals(eibaid)) {
            return lookupUser(userInput.userIdInput, userRepo, result);
        } else if ("PF3".equals(eibaid)) {
            doUpdate(userInput, userRepo, result);
            String back = (fromProgram != null && !fromProgram.isEmpty()) ? fromProgram : "COADM01C";
            result.xctlProgram = back;
            result.returnToPrev = true;
            return result;
        } else if ("PF4".equals(eibaid)) {
            return result;
        } else if ("PF5".equals(eibaid)) {
            doUpdate(userInput, userRepo, result);
            return result;
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

    private UpdateUserResult lookupUser(String userId, UserSecRepository repo, UpdateUserResult result) {
        if (userId == null || userId.trim().isEmpty()) {
            result.error = true;
            result.message = "User ID can NOT be empty...";
            return result;
        }

        SecUserData user = repo.find(userId);
        if (user == null) {
            result.error = true;
            result.message = "User ID NOT found...";
        } else {
            result.userFound = user;
        }

        return result;
    }

    private void doUpdate(UpdateUserInput inp, UserSecRepository repo, UpdateUserResult result) {
        if (inp.userIdInput == null || inp.userIdInput.trim().isEmpty()) {
            result.error = true;
            result.message = "User ID can NOT be empty...";
            return;
        }

        SecUserData existing = repo.find(inp.userIdInput);
        if (existing == null) {
            result.error = true;
            result.message = "User ID NOT found...";
            return;
        }

        // Apply updates
        if (inp.firstName != null && !inp.firstName.trim().isEmpty()) {
            existing.secUsrFname = inp.firstName.length() > 20
                    ? inp.firstName.substring(0, 20) : inp.firstName;
        }
        if (inp.lastName != null && !inp.lastName.trim().isEmpty()) {
            existing.secUsrLname = inp.lastName.length() > 20
                    ? inp.lastName.substring(0, 20) : inp.lastName;
        }
        if (inp.password != null && !inp.password.trim().isEmpty()) {
            existing.secUsrPwd = inp.password.length() > 8
                    ? inp.password.substring(0, 8) : inp.password;
        }
        if (inp.userType != null && !inp.userType.trim().isEmpty()) {
            existing.secUsrType = inp.userType.trim().substring(0, 1);
        }

        int resp = repo.rewrite(existing);
        if (resp == DFHRESP_NORMAL) {
            result.success = true;
            result.userFound = existing;
            result.message = "User " + existing.secUsrId + " has been updated ...";
        } else {
            result.error = true;
            result.message = "Unable to Update User...";
        }
    }

    // ── runVector adapter ───────────────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "FIRST_ENTRY");

        // Seed data
        Map<String, SecUserData> seedUsers = new LinkedHashMap<>();
        seedUsers.put("ADMIN001", new SecUserData("ADMIN001", "John", "Admin", "PASS1234", "A"));
        seedUsers.put("USER0001", new SecUserData("USER0001", "Jane", "User", "MYPASSWD", "U"));
        UserSecRepository repo = new UserSecRepository(seedUsers);

        UpdateUserResult result;

        switch (scenario) {
            case "FIRST_ENTRY":
                result = processUpdateUser(100, "ENTER", 0, "COUSR00C",
                        new UpdateUserInput(), repo, "USER0001");
                break;
            case "LOOKUP_USER":
                result = processUpdateUser(100, "ENTER", 1, "COUSR00C",
                        new UpdateUserInput("USER0001", "", "", "", ""), repo, "");
                break;
            case "UPDATE_USER":
                result = processUpdateUser(100, "PF5", 1, "COUSR00C",
                        new UpdateUserInput("USER0001", "Janet", "Updated", "NEWPASS1", "A"),
                        repo, "");
                break;
            case "USER_NOT_FOUND":
                result = processUpdateUser(100, "ENTER", 1, "COUSR00C",
                        new UpdateUserInput("NOSUCHID", "", "", "", ""), repo, "");
                break;
            case "PF3_RETURN":
                result = processUpdateUser(100, "PF3", 1, "COUSR00C",
                        new UpdateUserInput("USER0001", "", "", "", ""), repo, "");
                break;
            default:
                result = processUpdateUser(100, "ENTER", 0, "COUSR00C",
                        new UpdateUserInput(), repo, "USER0001");
                break;
        }

        String userId = "";
        String userFname = "";
        String userLname = "";
        if (result.userFound != null) {
            userId = result.userFound.secUsrId;
            userFname = result.userFound.secUsrFname;
            userLname = result.userFound.secUsrLname;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("SUCCESS", result.success ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("XCTL_PROGRAM", result.xctlProgram != null ? result.xctlProgram : "");
        out.put("RETURN_TO_PREV", result.returnToPrev ? "Y" : "N");
        out.put("USER_ID", userId);
        out.put("USER_FNAME", userFname);
        out.put("USER_LNAME", userLname);
        return out;
    }
}
