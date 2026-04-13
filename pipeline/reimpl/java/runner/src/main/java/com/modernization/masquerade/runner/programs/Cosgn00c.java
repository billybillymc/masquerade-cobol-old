package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Java reimplementation of COBOL program COSGN00C — CardDemo Sign-on Screen.
 *
 * <p>This is the W6 pilot — the first program ported to Java end-to-end. The
 * differential harness verifies it produces identical outputs to both the
 * original COBOL (compiled via GnuCOBOL) and the Python reimplementation
 * ({@code pipeline/reimpl/cosgn00c.py}) for the same set of vectors.
 *
 * <p>The Python reimplementation in {@code pipeline/reimpl/cosgn00c.py} is the
 * source of truth for behavior. Any divergence between this class and that
 * file is a parity bug. The structural logic mirrors {@code process_signon}
 * 1:1 — same decision tree, same error messages, same output dict shape.
 *
 * <p>Decision tree (from IQ-01/IQ-04, mirrored from the Python version):
 * <pre>
 *   IF EIBCALEN = 0
 *       → first entry, blank sign-on screen, no error
 *   ELSE
 *       EVALUATE EIBAID
 *           WHEN ENTER → PROCESS-ENTER-KEY
 *           WHEN PF3   → "thank you" message and return
 *           WHEN OTHER → "invalid key" error
 *
 *   PROCESS-ENTER-KEY:
 *       validate userid not blank
 *       validate password not blank
 *       READ user security file by userid
 *       EVALUATE WS-RESP-CD
 *           WHEN 0 → password match? → admin? → XCTL COADM01C / COMEN01C
 *           WHEN 13 → "user not found"
 *           WHEN OTHER → "unable to verify"
 * </pre>
 */
public class Cosgn00c implements ProgramRunner {

    // ── Constants — mirror WS-* and CCDA-* literals from COSGN00C.cbl ────

    private static final String WS_PGMNAME = "COSGN00C";
    private static final String WS_TRANID = "CC00";
    private static final String CCDA_MSG_THANK_YOU = "Thank you for using CCDA application... ";
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    ";

    // ── Default seeded repository (parity with cosgn00c.py) ──────────────

    private final UserSecurityRepository repository = new UserSecurityRepository(Map.of(
            "ADMIN001", new SecUserData("ADMIN001", "John", "Admin", "PASS1234", "A"),
            "USER0001", new SecUserData("USER0001", "Jane", "User", "MYPASSWD", "U")
    ));

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String userId = inputs.getOrDefault("USERID", "");
        String password = inputs.getOrDefault("PASSWD", "");
        int eibcalen = parseIntOr(inputs.get("EIBCALEN"), 100);
        String eibaid = inputs.getOrDefault("EIBAID", "ENTER");

        SignonResult result = processSignon(userId, password, eibcalen, eibaid);

        Map<String, String> output = new LinkedHashMap<>();
        output.put("XCTL_TARGET", result.xctlProgram == null ? "" : result.xctlProgram);
        output.put("HAS_COMMAREA", result.commarea != null ? "Y" : "N");
        output.put("ERROR_MSG", classifyMessage(result.message));
        return output;
    }

    /**
     * The COBOL PROCEDURE DIVISION for COSGN00C, ported to Java.
     * Direct line-by-line correspondence with {@code process_signon} in
     * {@code pipeline/reimpl/cosgn00c.py}.
     */
    SignonResult processSignon(String userId, String password, int eibcalen, String eibaid) {
        SignonResult result = new SignonResult();

        // First entry — show blank sign-on screen
        if (eibcalen == 0) {
            result.message = "";
            return result;
        }

        // EVALUATE EIBAID
        if ("ENTER".equals(eibaid) || "\u007D".equals(eibaid)) {
            // PROCESS-ENTER-KEY
            if (userId == null || userId.trim().isEmpty()) {
                result.error = true;
                result.message = "Please enter User ID ...";
                return result;
            }
            if (password == null || password.trim().isEmpty()) {
                result.error = true;
                result.message = "Please enter Password ...";
                return result;
            }

            // MOVE FUNCTION UPPER-CASE(USERIDI) TO WS-USER-ID
            String wsUserId = userId.trim().toUpperCase();
            String wsUserPwd = password.trim().toUpperCase();

            // READ-USER-SEC-FILE — returns (resp_cd, record)
            ReadResult read = repository.findById(wsUserId);

            if (read.respCode == 0 && read.record != null) {
                SecUserData secUser = read.record;
                // User found — check password
                if (secUser.secUsrPwd.trim().toUpperCase().equals(wsUserPwd)) {
                    // Password matches — set up commarea and route
                    CarddemoCommarea commarea = new CarddemoCommarea();
                    commarea.cdemoFromTranid = WS_TRANID;
                    commarea.cdemoFromProgram = WS_PGMNAME;
                    commarea.cdemoUserId = wsUserId;
                    commarea.cdemoUserType = secUser.secUsrType;
                    commarea.cdemoPgmContext = 0;

                    if ("A".equals(secUser.secUsrType.trim().toUpperCase())) {
                        result.xctlProgram = "COADM01C";
                    } else {
                        result.xctlProgram = "COMEN01C";
                    }
                    result.commarea = commarea;
                    return result;
                } else {
                    result.error = true;
                    result.message = "Wrong Password. Try again ...";
                    return result;
                }
            } else if (read.respCode == 13) {
                result.error = true;
                result.message = "User not found. Try again ...";
                return result;
            } else {
                result.error = true;
                result.message = "Unable to verify the User ...";
                return result;
            }
        } else if ("PF3".equals(eibaid) || "\u00F3".equals(eibaid)) {
            result.message = CCDA_MSG_THANK_YOU;
            return result;
        } else {
            result.error = true;
            result.message = CCDA_MSG_INVALID_KEY;
            return result;
        }
    }

    /**
     * Reduce a free-text message to a stable canonical error label.
     * Mirrors {@code _classify_message} in cosgn00c.py.
     */
    private String classifyMessage(String message) {
        if (message == null || message.isEmpty()) return "";
        if (message.contains("Wrong Password")) return "Wrong Password";
        if (message.contains("User not found")) return "User not found";
        if (message.contains("Unable to verify")) return "Unable to verify";
        if (message.contains("Please enter User ID")) return "Please enter User ID";
        if (message.contains("Please enter Password")) return "Please enter Password";
        return "";
    }

    private static int parseIntOr(String s, int fallback) {
        if (s == null || s.isEmpty()) return fallback;
        try {
            return Integer.parseInt(s.trim());
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    // ── Inner data types — local to keep the pilot self-contained ────────

    static class SecUserData {
        final String secUsrId;
        final String secUsrFname;
        final String secUsrLname;
        final String secUsrPwd;
        final String secUsrType;

        SecUserData(String id, String fname, String lname, String pwd, String type) {
            this.secUsrId = id;
            this.secUsrFname = fname;
            this.secUsrLname = lname;
            this.secUsrPwd = pwd;
            this.secUsrType = type;
        }
    }

    static class CarddemoCommarea {
        String cdemoFromTranid = "";
        String cdemoFromProgram = "";
        String cdemoUserId = "";
        String cdemoUserType = "";
        int cdemoPgmContext = 0;
    }

    static class SignonResult {
        String xctlProgram = "";
        CarddemoCommarea commarea = null;
        String message = "";
        boolean error = false;
    }

    static class ReadResult {
        final int respCode;
        final SecUserData record;

        ReadResult(int respCode, SecUserData record) {
            this.respCode = respCode;
            this.record = record;
        }
    }

    /** In-memory repository mirroring UserSecurityRepository in cosgn00c.py. */
    static class UserSecurityRepository {
        private final Map<String, SecUserData> users;

        UserSecurityRepository(Map<String, SecUserData> users) {
            this.users = new HashMap<>(users);
        }

        ReadResult findById(String userId) {
            String key = userId.trim().toUpperCase();
            if (users.containsKey(key)) {
                return new ReadResult(0, users.get(key));
            }
            return new ReadResult(13, null);
        }
    }
}
