"""
Reimplementation of COUSR03C — CardDemo Delete User Screen.

CICS online program. Reads a user from USRSEC by user ID, displays their
data for confirmation, then deletes on PF5.

Key presses:
  ENTER → look up user by ID and display for confirmation
  PF3   → return to previous screen
  PF4   → clear screen
  PF5   → confirm and delete user
  PF12  → return to admin menu
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, SecUserData,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF4, DFHPF5, DFHPF12,
)


WS_PGMNAME = "COUSR03C"
WS_TRANID  = "CU03"

DFHRESP_NORMAL = 0
DFHRESP_NOTFND = 13


@dataclass
class DeleteUserResult:
    user_found: Optional[SecUserData] = None
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    deleted: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False
    confirm_message: str = ""


class UserSecRepository:
    def __init__(self, users: dict[str, SecUserData]):
        self._users = users

    def find(self, user_id: str) -> Optional[SecUserData]:
        return self._users.get(user_id.strip())

    def delete(self, user_id: str) -> int:
        key = user_id.strip()
        if key not in self._users:
            return DFHRESP_NOTFND
        del self._users[key]
        return DFHRESP_NORMAL


def process_delete_user(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    user_id_input: str,
    user_repo: UserSecRepository,
    preloaded_user_id: str = "",
) -> DeleteUserResult:
    """Process delete-user screen — mirrors COUSR03C PROCEDURE DIVISION."""
    result = DeleteUserResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        if preloaded_user_id:
            _lookup_and_display(preloaded_user_id, user_repo, result)
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result

    if eibaid in (DFHENTER, "ENTER"):
        return _process_enter(user_id_input, user_repo, commarea, result)
    elif eibaid in (DFHPF3, "PF3"):
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
        return _delete_user(user_id_input, user_repo, commarea, result)
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


def _lookup_and_display(user_id: str, repo: UserSecRepository, result: DeleteUserResult) -> None:
    user = repo.find(user_id)
    if user is None:
        result.error = True
        result.message = "User ID NOT found..."
    else:
        result.user_found = user
        result.confirm_message = "Press PF5 key to delete this user ..."


def _process_enter(
    user_id: str,
    repo: UserSecRepository,
    commarea: CarddemoCommarea,
    result: DeleteUserResult,
) -> DeleteUserResult:
    if not user_id or user_id.strip() == "":
        result.error = True
        result.message = "User ID can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    _lookup_and_display(user_id, repo, result)
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.confirm_message if not result.error else result.message
    result.commarea = commarea
    return result


def _delete_user(
    user_id: str,
    repo: UserSecRepository,
    commarea: CarddemoCommarea,
    result: DeleteUserResult,
) -> DeleteUserResult:
    if not user_id or user_id.strip() == "":
        result.error = True
        result.message = "User ID can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    resp = repo.delete(user_id)
    if resp == DFHRESP_NORMAL:
        result.deleted = True
        result.message = f"User {user_id.strip()} has been deleted ..."
    elif resp == DFHRESP_NOTFND:
        result.error = True
        result.message = "User ID NOT found..."
    else:
        result.error = True
        result.message = "Unable to Update User..."

    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result


# ── Differential harness runner adapter ──────────────────────────────────────

_SEED_USERS: dict[str, SecUserData] = {
    "ADMIN001": SecUserData(sec_usr_id="ADMIN001", sec_usr_fname="John", sec_usr_lname="Admin", sec_usr_pwd="PASS1234", sec_usr_type="A"),
    "USER0001": SecUserData(sec_usr_id="USER0001", sec_usr_fname="Jane", sec_usr_lname="User", sec_usr_pwd="MYPASSWD", sec_usr_type="U"),
    "USER0002": SecUserData(sec_usr_id="USER0002", sec_usr_fname="Bob", sec_usr_lname="Smith", sec_usr_pwd="BOBPASS1", sec_usr_type="U"),
}


def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness.

    SCENARIO selects a hardcoded test path:
      FIRST_ENTRY    — context=0, preloaded user → display for confirm
      LOOKUP_USER    — ENTER with user ID → display for confirm
      DELETE_USER    — PF5 with user ID → delete user
      USER_NOT_FOUND — PF5 with bad user ID → error
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
        result = process_delete_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_id_input="", user_repo=repo,
            preloaded_user_id="USER0002",
        )
    elif scenario == "LOOKUP_USER":
        result = process_delete_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_id_input="USER0001", user_repo=repo,
        )
    elif scenario == "DELETE_USER":
        result = process_delete_user(
            eibcalen=100, eibaid="PF5", commarea=commarea,
            user_id_input="USER0002", user_repo=repo,
        )
    elif scenario == "USER_NOT_FOUND":
        result = process_delete_user(
            eibcalen=100, eibaid="PF5", commarea=commarea,
            user_id_input="NOSUCHID", user_repo=repo,
        )
    elif scenario == "PF3_RETURN":
        result = process_delete_user(
            eibcalen=100, eibaid="PF3", commarea=commarea,
            user_id_input="", user_repo=repo,
        )
    else:
        commarea.cdemo_pgm_context = 0
        result = process_delete_user(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            user_id_input="", user_repo=repo,
            preloaded_user_id="USER0002",
        )

    user_id_out = ""
    if result.user_found:
        user_id_out = result.user_found.sec_usr_id

    return {
        "ERROR": "Y" if result.error else "N",
        "DELETED": "Y" if result.deleted else "N",
        "MESSAGE": result.message,
        "XCTL_PROGRAM": result.xctl_program or "",
        "RETURN_TO_PREV": "Y" if result.return_to_prev else "N",
        "USER_ID": user_id_out,
        "CONFIRM_MESSAGE": result.confirm_message,
    }
