"""
Reimplementation of COBOL program COSGN00C — CardDemo Sign-on Screen.

This is the ACTUAL business logic, translated from the COBOL source using
the generated skeleton, business rules, and decision tree as guides.

The differential harness (IQ-09) verifies this produces identical output
to the original COBOL program compiled and run via GnuCOBOL.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ── Data Structures (from copybooks via IQ-02) ─────────────────────────────

@dataclass
class SecUserData:
    """From CSUSR01Y.cpy — user security record."""
    sec_usr_id: str = ""
    sec_usr_fname: str = ""
    sec_usr_lname: str = ""
    sec_usr_pwd: str = ""
    sec_usr_type: str = ""


@dataclass
class CarddemoCommarea:
    """From COCOM01Y.cpy — communication area passed between programs."""
    cdemo_from_tranid: str = ""
    cdemo_from_program: str = ""
    cdemo_to_tranid: str = ""
    cdemo_to_program: str = ""
    cdemo_user_id: str = ""
    cdemo_user_type: str = ""
    cdemo_pgm_context: int = 0


@dataclass
class ScreenOutput:
    """What the program would SEND to the terminal."""
    trnname: str = ""
    title01: str = ""
    title02: str = ""
    curdate: str = ""
    curtime: str = ""
    pgmname: str = ""
    applid: str = ""
    sysid: str = ""
    errmsg: str = ""


@dataclass
class SignonResult:
    """Result of processing a sign-on attempt."""
    xctl_program: str = ""        # which program to transfer to ("" = no transfer)
    commarea: Optional[CarddemoCommarea] = None
    screen_output: Optional[ScreenOutput] = None
    message: str = ""
    error: bool = False


# ── Repository Interface (from IQ-06) ──────────────────────────────────────

class UserSecurityRepository:
    """Repository for CICS dataset WS-USRSEC-FILE."""

    def __init__(self, users: dict[str, SecUserData] = None):
        self._users = users or {}

    def find_by_id(self, user_id: str) -> tuple[int, Optional[SecUserData]]:
        """Read user by ID. Returns (resp_code, record).
        resp_code: 0 = found, 13 = not found."""
        key = user_id.strip().upper()
        if key in self._users:
            return 0, self._users[key]
        return 13, None


# ── Business Logic ──────────────────────────────────────────────────────────

WS_PGMNAME = "COSGN00C"
WS_TRANID = "CC00"
CCDA_TITLE01 = "      AWS Mainframe Modernization       "
CCDA_TITLE02 = "              CardDemo                  "
CCDA_MSG_THANK_YOU = "Thank you for using CCDA application... "
CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    "


def process_signon(
    user_id: str,
    password: str,
    eibcalen: int,
    eibaid: str,
    repository: UserSecurityRepository,
    applid: str = "TESTAPPL",
    sysid: str = "TEST",
) -> SignonResult:
    """Process a sign-on screen interaction.

    This is the reimplementation of COSGN00C's PROCEDURE DIVISION.
    The decision tree (from IQ-01/IQ-04):

    IF EIBCALEN = 0
        → first entry, show blank sign-on screen
    ELSE
        EVALUATE EIBAID
            WHEN DFHENTER → PROCESS-ENTER-KEY
            WHEN DFHPF3   → send "thank you" and return
            WHEN OTHER    → "invalid key" error

    PROCESS-ENTER-KEY:
        validate userid not blank
        validate password not blank
        READ user security file by userid
        EVALUATE WS-RESP-CD
            WHEN 0 → password match? → admin? → XCTL COADM01C / COMEN01C
            WHEN 13 → "user not found"
            WHEN OTHER → "unable to verify"
    """
    result = SignonResult()
    err_flg = False
    ws_message = ""

    # MAIN-PARA: initialize
    # SET ERR-FLG-OFF TO TRUE — already False
    # MOVE SPACES TO WS-MESSAGE, ERRMSGO — already empty

    if eibcalen == 0:
        # First entry — show blank sign-on screen
        screen = _populate_header(applid, sysid)
        screen.errmsg = ""
        result.screen_output = screen
        result.message = ""
        return result

    # EVALUATE EIBAID
    DFHENTER = "\x7d"  # EBCDIC Enter key
    DFHPF3 = "\xf3"    # EBCDIC PF3 key

    if eibaid == DFHENTER or eibaid == "ENTER":
        # PROCESS-ENTER-KEY
        # Validate input fields
        if not user_id or user_id.strip() == "" or user_id == "\x00" * len(user_id):
            err_flg = True
            ws_message = "Please enter User ID ..."
            screen = _populate_header(applid, sysid)
            screen.errmsg = ws_message
            result.screen_output = screen
            result.error = True
            result.message = ws_message
            return result

        if not password or password.strip() == "" or password == "\x00" * len(password):
            err_flg = True
            ws_message = "Please enter Password ..."
            screen = _populate_header(applid, sysid)
            screen.errmsg = ws_message
            result.screen_output = screen
            result.error = True
            result.message = ws_message
            return result

        # MOVE FUNCTION UPPER-CASE(USERIDI) TO WS-USER-ID, CDEMO-USER-ID
        ws_user_id = user_id.strip().upper()
        ws_user_pwd = password.strip().upper()

        # READ-USER-SEC-FILE
        resp_cd, sec_user = repository.find_by_id(ws_user_id)

        if resp_cd == 0 and sec_user is not None:
            # User found — check password
            if sec_user.sec_usr_pwd.strip().upper() == ws_user_pwd:
                # Password matches — set up commarea and route
                commarea = CarddemoCommarea(
                    cdemo_from_tranid=WS_TRANID,
                    cdemo_from_program=WS_PGMNAME,
                    cdemo_user_id=ws_user_id,
                    cdemo_user_type=sec_user.sec_usr_type,
                    cdemo_pgm_context=0,
                )

                if sec_user.sec_usr_type.strip().upper() == "A":
                    # Admin user → XCTL to COADM01C
                    result.xctl_program = "COADM01C"
                else:
                    # Regular user → XCTL to COMEN01C
                    result.xctl_program = "COMEN01C"

                result.commarea = commarea
                return result
            else:
                # Wrong password
                ws_message = "Wrong Password. Try again ..."
                screen = _populate_header(applid, sysid)
                screen.errmsg = ws_message
                result.screen_output = screen
                result.error = True
                result.message = ws_message
                return result

        elif resp_cd == 13:
            # User not found
            err_flg = True
            ws_message = "User not found. Try again ..."
            screen = _populate_header(applid, sysid)
            screen.errmsg = ws_message
            result.screen_output = screen
            result.error = True
            result.message = ws_message
            return result

        else:
            # Other error
            err_flg = True
            ws_message = "Unable to verify the User ..."
            screen = _populate_header(applid, sysid)
            screen.errmsg = ws_message
            result.screen_output = screen
            result.error = True
            result.message = ws_message
            return result

    elif eibaid == DFHPF3 or eibaid == "PF3":
        # PF3 — thank you and return
        result.message = CCDA_MSG_THANK_YOU
        return result

    else:
        # Invalid key
        err_flg = True
        ws_message = CCDA_MSG_INVALID_KEY
        screen = _populate_header(applid, sysid)
        screen.errmsg = ws_message
        result.screen_output = screen
        result.error = True
        result.message = ws_message
        return result


def _populate_header(applid: str, sysid: str) -> ScreenOutput:
    """POPULATE-HEADER-INFO paragraph — fill screen header fields."""
    now = datetime.now()
    return ScreenOutput(
        trnname=WS_TRANID,
        title01=CCDA_TITLE01,
        title02=CCDA_TITLE02,
        curdate=f"{now.month:02d}/{now.day:02d}/{now.year % 100:02d}",
        curtime=f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}",
        pgmname=WS_PGMNAME,
        applid=applid,
        sysid=sysid,
    )


# ── Differential harness runner adapter (W2) ───────────────────────────────
#
# `run_vector` is the canonical entry point used by the language-agnostic
# vector runner in `pipeline/vector_runner.py`. It maps the harness JSON shape
# (a flat dict of strings) to this program's native API and back, so the same
# vectors can drive Python and Java reimplementations interchangeably.
#
# Inputs accepted:
#   USERID  — required, the user ID being signed in
#   PASSWD  — required, the password attempt
#   EIBCALEN — optional (default "100"), nonzero = returning user
#   EIBAID  — optional (default "ENTER"), AID key
#
# Outputs produced:
#   XCTL_TARGET   — destination program on success ("" on no-transfer paths)
#   HAS_COMMAREA  — "Y" if a commarea was set, otherwise "N"
#   ERROR_MSG     — canonical short error label, or "" on success

_DEFAULT_RUNNER_REPOSITORY = UserSecurityRepository({
    "ADMIN001": SecUserData(
        sec_usr_id="ADMIN001", sec_usr_fname="John", sec_usr_lname="Admin",
        sec_usr_pwd="PASS1234", sec_usr_type="A",
    ),
    "USER0001": SecUserData(
        sec_usr_id="USER0001", sec_usr_fname="Jane", sec_usr_lname="User",
        sec_usr_pwd="MYPASSWD", sec_usr_type="U",
    ),
})


def _classify_message(message: str) -> str:
    """Reduce a free-text message to a stable canonical error label."""
    if not message:
        return ""
    if "Wrong Password" in message:
        return "Wrong Password"
    if "User not found" in message:
        return "User not found"
    if "Unable to verify" in message:
        return "Unable to verify"
    if "Please enter User ID" in message:
        return "Please enter User ID"
    if "Please enter Password" in message:
        return "Please enter Password"
    return ""


def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness.

    See the section comment above for the input/output contract.
    """
    user_id = str(inputs.get("USERID", ""))
    password = str(inputs.get("PASSWD", ""))
    eibcalen = int(inputs.get("EIBCALEN", 100))
    eibaid = str(inputs.get("EIBAID", "ENTER"))

    result = process_signon(
        user_id=user_id,
        password=password,
        eibcalen=eibcalen,
        eibaid=eibaid,
        repository=_DEFAULT_RUNNER_REPOSITORY,
    )

    return {
        "XCTL_TARGET": result.xctl_program or "",
        "HAS_COMMAREA": "Y" if result.commarea else "N",
        "ERROR_MSG": _classify_message(result.message),
    }
