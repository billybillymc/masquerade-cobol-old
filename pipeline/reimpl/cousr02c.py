"""
Reimplementation of COUSR02C — CardDemo Update User Screen.

CICS online program. Reads an existing user from USRSEC by user ID,
displays their data for editing, then rewrites on PF5 confirmation.

Key presses:
  ENTER → look up user by ID
  PF3   → save changes and return to previous screen
  PF4   → clear current screen
  PF5   → confirm and update user
  PF12  → return to admin menu without saving
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, SecUserData,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF4, DFHPF5, DFHPF12,
)


WS_PGMNAME = "COUSR02C"
WS_TRANID  = "CU02"

DFHRESP_NORMAL = 0
DFHRESP_NOTFND = 13


@dataclass
class UpdateUserInput:
    user_id_input: str = ""   # ID to look up
    first_name: str = ""
    last_name: str = ""
    password: str = ""
    user_type: str = ""


@dataclass
class UpdateUserResult:
    user_found: Optional[SecUserData] = None
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    success: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False


class UserSecRepository:
    def __init__(self, users: dict[str, SecUserData]):
        self._users = users

    def find(self, user_id: str) -> Optional[SecUserData]:
        return self._users.get(user_id.strip())

    def rewrite(self, user: SecUserData) -> int:
        key = user.sec_usr_id.strip()
        if key not in self._users:
            return DFHRESP_NOTFND
        self._users[key] = user
        return DFHRESP_NORMAL


def process_update_user(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    user_input: UpdateUserInput,
    user_repo: UserSecRepository,
    preloaded_user_id: str = "",
) -> UpdateUserResult:
    """Process update-user screen — mirrors COUSR02C PROCEDURE DIVISION."""
    result = UpdateUserResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        if preloaded_user_id:
            user = user_repo.find(preloaded_user_id)
            result.user_found = user
            if user is None:
                result.error = True
                result.message = "User ID NOT found..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result

    if eibaid in (DFHENTER, "ENTER"):
        return _lookup_user(user_input.user_id_input, user_repo, commarea, result)
    elif eibaid in (DFHPF3, "PF3"):
        _do_update(user_input, user_repo, result)
        back = commarea.cdemo_from_program or "COADM01C"
        result.xctl_program = back
        result.return_to_prev = True
        result.commarea = commarea
        return result
    elif eibaid in (DFHPF4, "PF4"):
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result
    elif eibaid in (DFHPF5, "PF5"):
        return _do_update(user_input, user_repo, commarea, result)
    elif eibaid in (DFHPF12, "PF12"):
        result.xctl_program = "COADM01C"
        result.return_to_prev = True
        commarea.cdemo_to_program = "COADM01C"
        result.commarea = commarea
        return result
    else:
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result


def _lookup_user(
    user_id: str,
    repo: UserSecRepository,
    commarea: CarddemoCommarea,
    result: UpdateUserResult,
) -> UpdateUserResult:
    if not user_id or user_id.strip() == "":
        result.error = True
        result.message = "User ID can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    user = repo.find(user_id)
    if user is None:
        result.error = True
        result.message = "User ID NOT found..."
    else:
        result.user_found = user

    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message if result.error else ""
    result.commarea = commarea
    return result


def _do_update(
    inp: UpdateUserInput,
    repo: UserSecRepository,
    commarea: CarddemoCommarea = None,
    result: UpdateUserResult = None,
) -> UpdateUserResult:
    if result is None:
        result = UpdateUserResult()

    if not inp.user_id_input or inp.user_id_input.strip() == "":
        result.error = True
        result.message = "User ID can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        if commarea:
            result.commarea = commarea
        return result

    existing = repo.find(inp.user_id_input)
    if existing is None:
        result.error = True
        result.message = "User ID NOT found..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        if commarea:
            result.commarea = commarea
        return result

    # Apply updates
    if inp.first_name.strip():
        existing.sec_usr_fname = inp.first_name[:20]
    if inp.last_name.strip():
        existing.sec_usr_lname = inp.last_name[:20]
    if inp.password.strip():
        existing.sec_usr_pwd = inp.password[:8]
    if inp.user_type.strip():
        existing.sec_usr_type = inp.user_type.strip()[0]

    resp = repo.rewrite(existing)
    if resp == DFHRESP_NORMAL:
        result.success = True
        result.user_found = existing
        result.message = f"User {existing.sec_usr_id} has been updated ..."
    else:
        result.error = True
        result.message = "Unable to Update User..."

    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    if commarea:
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
      FIRST_ENTRY    — context=0, preloaded user → display user
      LOOKUP_USER    — ENTER with user ID → find user
      UPDATE_USER    — PF5 with updated fields → save
      USER_NOT_FOUND — ENTER with bad user ID → error
      PF3_RETURN     — press PF3 → return to previous
    """
    scenario = inputs.get("SCENARIO", "FIRST_ENTRY")

    import copy
    repo = UserSecRepository(copy.deepcopy(_SEED_USERS))

    commarea = CarddemoCommarea(
        cdemo_from_tranid="CA00",
        cdemo_from_program="COUSR00C",
        cdemo_user_id="ADMIN001",
        cdemo_user_type="A",
        cdemo_pgm_context=1,
    )

    if scenario == "FIRST_ENTRY":
        commarea.cdemo_pgm_context = 0
        result = process_update_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_input=UpdateUserInput(), user_repo=repo,
            preloaded_user_id="USER0001",
        )
    elif scenario == "LOOKUP_USER":
        result = process_update_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_input=UpdateUserInput(user_id_input="USER0001"),
            user_repo=repo,
        )
    elif scenario == "UPDATE_USER":
        result = process_update_user(
            eibcalen=100, eibaid="PF5", commarea=commarea,
            user_input=UpdateUserInput(
                user_id_input="USER0001", first_name="Janet",
                last_name="Updated", password="NEWPASS1", user_type="A",
            ),
            user_repo=repo,
        )
    elif scenario == "USER_NOT_FOUND":
        result = process_update_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_input=UpdateUserInput(user_id_input="NOSUCHID"),
            user_repo=repo,
        )
    elif scenario == "PF3_RETURN":
        result = process_update_user(
            eibcalen=100, eibaid="PF3", commarea=commarea,
            user_input=UpdateUserInput(user_id_input="USER0001"),
            user_repo=repo,
        )
    else:
        commarea.cdemo_pgm_context = 0
        result = process_update_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_input=UpdateUserInput(), user_repo=repo,
            preloaded_user_id="USER0001",
        )

    user_id_out = ""
    user_fname_out = ""
    user_lname_out = ""
    if result.user_found:
        user_id_out = result.user_found.sec_usr_id
        user_fname_out = result.user_found.sec_usr_fname
        user_lname_out = result.user_found.sec_usr_lname

    return {
        "ERROR": "Y" if result.error else "N",
        "SUCCESS": "Y" if result.success else "N",
        "MESSAGE": result.message,
        "XCTL_PROGRAM": result.xctl_program or "",
        "RETURN_TO_PREV": "Y" if result.return_to_prev else "N",
        "USER_ID": user_id_out,
        "USER_FNAME": user_fname_out,
        "USER_LNAME": user_lname_out,
    }
