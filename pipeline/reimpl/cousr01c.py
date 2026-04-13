"""
Reimplementation of COUSR01C — CardDemo Add User Screen.

CICS online program. Accepts user details (ID, first name, last name,
password, type) and writes a new record to the USRSEC file.

Key presses:
  ENTER → validate and write user
  PF3   → return to admin menu
  PF4   → clear current screen
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Callable

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, SecUserData,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF4,
)


WS_PGMNAME = "COUSR01C"
WS_TRANID  = "CU01"

# CICS response codes
DFHRESP_NORMAL = 0
DFHRESP_DUPKEY = 16
DFHRESP_DUPREC = 22


@dataclass
class AddUserInput:
    first_name: str = ""
    last_name: str = ""
    user_id: str = ""
    password: str = ""
    user_type: str = ""   # 'A' or 'R'


@dataclass
class AddUserResult:
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    success: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False
    cleared: bool = False


class UserSecRepository:
    def __init__(self, users: dict[str, SecUserData]):
        self._users = users  # keyed by user_id

    def write(self, user: SecUserData) -> int:
        """Write user. Returns: 0=ok, 22=duplicate, -1=other."""
        key = user.sec_usr_id.strip()
        if key in self._users:
            return DFHRESP_DUPREC
        self._users[key] = user
        return DFHRESP_NORMAL

    def find(self, user_id: str) -> Optional[SecUserData]:
        return self._users.get(user_id.strip())


def process_add_user(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    user_input: AddUserInput,
    user_repo: UserSecRepository,
) -> AddUserResult:
    """Process add-user screen — mirrors COUSR01C PROCEDURE DIVISION."""
    result = AddUserResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result

    if eibaid in (DFHENTER, "ENTER"):
        return _process_enter(user_input, commarea, user_repo, result)
    elif eibaid in (DFHPF3, "PF3"):
        result.return_to_prev = True
        result.xctl_program = "COADM01C"
        commarea.cdemo_to_program = "COADM01C"
        result.commarea = commarea
        return result
    elif eibaid in (DFHPF4, "PF4"):
        result.cleared = True
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result
    else:
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result


def _process_enter(
    inp: AddUserInput,
    commarea: CarddemoCommarea,
    repo: UserSecRepository,
    result: AddUserResult,
) -> AddUserResult:
    """PROCESS-ENTER-KEY validation sequence."""
    if not inp.first_name or inp.first_name.strip() == "":
        result.error = True
        result.message = "First Name can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result

    if not inp.last_name or inp.last_name.strip() == "":
        result.error = True
        result.message = "Last Name can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result

    if not inp.user_id or inp.user_id.strip() == "":
        result.error = True
        result.message = "User ID can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result

    if not inp.password or inp.password.strip() == "":
        result.error = True
        result.message = "Password can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result

    if not inp.user_type or inp.user_type.strip() == "":
        result.error = True
        result.message = "User Type can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result

    # WRITE-USER-SEC-FILE
    new_user = SecUserData(
        sec_usr_id=inp.user_id.strip(),
        sec_usr_fname=inp.first_name[:20],
        sec_usr_lname=inp.last_name[:20],
        sec_usr_pwd=inp.password[:8],
        sec_usr_type=inp.user_type.strip()[0] if inp.user_type.strip() else "R",
    )
    resp = repo.write(new_user)

    if resp == DFHRESP_NORMAL:
        result.success = True
        result.message = f"User {new_user.sec_usr_id} has been added ..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
    elif resp in (DFHRESP_DUPKEY, DFHRESP_DUPREC):
        result.error = True
        result.message = "User ID already exist..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
    else:
        result.error = True
        result.message = "Unable to Add User..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message

    result.commarea = commarea
    return result


# ── Differential harness runner adapter ──────────────────────────────────────

_SEED_USERS: dict[str, SecUserData] = {
    "ADMIN001": SecUserData(sec_usr_id="ADMIN001", sec_usr_fname="John", sec_usr_lname="Admin", sec_usr_pwd="PASS1234", sec_usr_type="A"),
    "USER0001": SecUserData(sec_usr_id="USER0001", sec_usr_fname="Jane", sec_usr_lname="User", sec_usr_pwd="MYPASSWD", sec_usr_type="U"),
}


def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness.

    SCENARIO selects a hardcoded test path:
      FIRST_ENTRY    — context=0, first entry → show blank form
      VALID_INPUT    — add a new user successfully
      DUPLICATE_USER — attempt to add existing user → error
      MISSING_FIELD  — missing first name → validation error
      PF3_RETURN     — press PF3 → return to admin menu
    """
    scenario = inputs.get("SCENARIO", "FIRST_ENTRY")

    import copy
    repo = UserSecRepository(copy.deepcopy(_SEED_USERS))

    commarea = CarddemoCommarea(
        cdemo_from_tranid="CA00",
        cdemo_from_program="COADM01C",
        cdemo_user_id="ADMIN001",
        cdemo_user_type="A",
        cdemo_pgm_context=1,
    )

    if scenario == "FIRST_ENTRY":
        commarea.cdemo_pgm_context = 0
        result = process_add_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_input=AddUserInput(), user_repo=repo,
        )
    elif scenario == "VALID_INPUT":
        result = process_add_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_input=AddUserInput(
                first_name="Charlie", last_name="Brown",
                user_id="USER0099", password="NEWPASS1", user_type="R",
            ),
            user_repo=repo,
        )
    elif scenario == "DUPLICATE_USER":
        result = process_add_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_input=AddUserInput(
                first_name="Jane", last_name="User",
                user_id="USER0001", password="MYPASSWD", user_type="U",
            ),
            user_repo=repo,
        )
    elif scenario == "MISSING_FIELD":
        result = process_add_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_input=AddUserInput(
                first_name="", last_name="Brown",
                user_id="USER0099", password="NEWPASS1", user_type="R",
            ),
            user_repo=repo,
        )
    elif scenario == "PF3_RETURN":
        result = process_add_user(
            eibcalen=100, eibaid="PF3", commarea=commarea,
            user_input=AddUserInput(), user_repo=repo,
        )
    else:
        commarea.cdemo_pgm_context = 0
        result = process_add_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_input=AddUserInput(), user_repo=repo,
        )

    return {
        "ERROR": "Y" if result.error else "N",
        "SUCCESS": "Y" if result.success else "N",
        "MESSAGE": result.message,
        "XCTL_PROGRAM": result.xctl_program or "",
        "RETURN_TO_PREV": "Y" if result.return_to_prev else "N",
        "CLEARED": "Y" if result.cleared else "N",
    }
