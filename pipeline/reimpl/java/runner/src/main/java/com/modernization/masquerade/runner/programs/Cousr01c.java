package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.*;

/**
 * Java reimplementation of COUSR01C — CardDemo Add User Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/cousr01c.py}. Python is the source of truth.
 *
 * <p>Structure: standalone {@link #processAddUser} method + thin
 * {@link #runVector} adapter.
 */
public class Cousr01c implements ProgramRunner {

    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    ";
    private static final int DFHRESP_NORMAL = 0;
    private static final int DFHRESP_DUPREC = 22;

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

    static class AddUserInput {
        String firstName = "";
        String lastName = "";
        String userId = "";
        String password = "";
        String userType = "";

        AddUserInput() {}

        AddUserInput(String firstName, String lastName, String userId,
                     String password, String userType) {
            this.firstName = firstName != null ? firstName : "";
            this.lastName = lastName != null ? lastName : "";
            this.userId = userId != null ? userId : "";
            this.password = password != null ? password : "";
            this.userType = userType != null ? userType : "";
        }
    }

    static class AddUserResult {
        String message = "";
        boolean error = false;
        boolean success = false;
        String xctlProgram = "";
        boolean returnToPrev = false;
        boolean cleared = false;
    }

    // ── Repository ──────────────────────────────────────────────────────────

    static class UserSecRepository {
        private final Map<String, SecUserData> users;

        UserSecRepository(Map<String, SecUserData> users) {
            this.users = new LinkedHashMap<>(users);
        }

        int write(SecUserData user) {
            String key = user.secUsrId.trim();
            if (users.containsKey(key)) return DFHRESP_DUPREC;
            users.put(key, user);
            return DFHRESP_NORMAL;
        }
    }

    // ── Standalone business method ──────────────────────────────────────────

    /**
     * Process add-user screen — mirrors {@code process_add_user} in
     * {@code pipeline/reimpl/cousr01c.py}.
     */
    AddUserResult processAddUser(
            int eibcalen, String eibaid, int pgmContext,
            AddUserInput userInput, UserSecRepository userRepo) {

        AddUserResult result = new AddUserResult();

        if (eibcalen == 0) {
            result.returnToPrev = true;
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (pgmContext == 0) {
            // First entry — show blank form
            return result;
        }

        if ("ENTER".equals(eibaid)) {
            return processEnter(userInput, userRepo, result);
        } else if ("PF3".equals(eibaid)) {
            result.returnToPrev = true;
            result.xctlProgram = "COADM01C";
            return result;
        } else if ("PF4".equals(eibaid)) {
            result.cleared = true;
            return result;
        } else {
            result.error = true;
            result.message = CCDA_MSG_INVALID_KEY;
            return result;
        }
    }

    private AddUserResult processEnter(AddUserInput inp, UserSecRepository repo, AddUserResult result) {
        if (inp.firstName == null || inp.firstName.trim().isEmpty()) {
            result.error = true;
            result.message = "First Name can NOT be empty...";
            return result;
        }
        if (inp.lastName == null || inp.lastName.trim().isEmpty()) {
            result.error = true;
            result.message = "Last Name can NOT be empty...";
            return result;
        }
        if (inp.userId == null || inp.userId.trim().isEmpty()) {
            result.error = true;
            result.message = "User ID can NOT be empty...";
            return result;
        }
        if (inp.password == null || inp.password.trim().isEmpty()) {
            result.error = true;
            result.message = "Password can NOT be empty...";
            return result;
        }
        if (inp.userType == null || inp.userType.trim().isEmpty()) {
            result.error = true;
            result.message = "User Type can NOT be empty...";
            return result;
        }

        String typeChar = inp.userType.trim().isEmpty() ? "R" : inp.userType.trim().substring(0, 1);
        SecUserData newUser = new SecUserData(
                inp.userId.trim(),
                inp.firstName.length() > 20 ? inp.firstName.substring(0, 20) : inp.firstName,
                inp.lastName.length() > 20 ? inp.lastName.substring(0, 20) : inp.lastName,
                inp.password.length() > 8 ? inp.password.substring(0, 8) : inp.password,
                typeChar);

        int resp = repo.write(newUser);

        if (resp == DFHRESP_NORMAL) {
            result.success = true;
            result.message = "User " + newUser.secUsrId + " has been added ...";
        } else if (resp == DFHRESP_DUPREC) {
            result.error = true;
            result.message = "User ID already exist...";
        } else {
            result.error = true;
            result.message = "Unable to Add User...";
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
        UserSecRepository repo = new UserSecRepository(seedUsers);

        AddUserResult result;

        switch (scenario) {
            case "FIRST_ENTRY":
                result = processAddUser(100, "ENTER", 0,
                        new AddUserInput(), repo);
                break;
            case "VALID_INPUT":
                result = processAddUser(100, "ENTER", 1,
                        new AddUserInput("Charlie", "Brown", "USER0099", "NEWPASS1", "R"),
                        repo);
                break;
            case "DUPLICATE_USER":
                result = processAddUser(100, "ENTER", 1,
                        new AddUserInput("Jane", "User", "USER0001", "MYPASSWD", "U"),
                        repo);
                break;
            case "MISSING_FIELD":
                result = processAddUser(100, "ENTER", 1,
                        new AddUserInput("", "Brown", "USER0099", "NEWPASS1", "R"),
                        repo);
                break;
            case "PF3_RETURN":
                result = processAddUser(100, "PF3", 1,
                        new AddUserInput(), repo);
                break;
            default:
                result = processAddUser(100, "ENTER", 0,
                        new AddUserInput(), repo);
                break;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("SUCCESS", result.success ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("XCTL_PROGRAM", result.xctlProgram != null ? result.xctlProgram : "");
        out.put("RETURN_TO_PREV", result.returnToPrev ? "Y" : "N");
        out.put("CLEARED", result.cleared ? "Y" : "N");
        return out;
    }
}
