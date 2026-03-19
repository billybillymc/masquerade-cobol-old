"""
Reimplementation of COUSR00C — CardDemo User List Screen.

CICS online program. Lists all users from the USRSEC file (10 per page),
allows selection via 'U' (update) or 'D' (delete) action codes, with
PF7 (previous page) and PF8 (next page) navigation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, SecUserData,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF7, DFHPF8,
)


WS_PGMNAME = "COUSR00C"
WS_TRANID  = "CU00"
PAGE_SIZE  = 10


@dataclass
class UserListRow:
    sel_flag: str = ""     # 'U', 'D', or space
    user_id: str = ""
    user_name: str = ""
    user_type: str = ""


@dataclass
class UserListResult:
    rows: list[UserListRow] = field(default_factory=list)
    page_num: int = 1
    has_next_page: bool = False
    has_prev_page: bool = False
    xctl_program: str = ""
    selected_user_id: str = ""
    selected_action: str = ""
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    return_to_prev: bool = False


# ── Repository ─────────────────────────────────────────────────────────────────

class UserSecRepository:
    """Ordered list of security users (simulates sequential VSAM browse)."""

    def __init__(self, users: list[SecUserData]):
        self._users = sorted(users, key=lambda u: u.sec_usr_id)

    def get_page(self, page_num: int) -> tuple[list[SecUserData], bool]:
        """Return (users_on_page, has_next_page)."""
        start = (page_num - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        page = self._users[start:end]
        has_next = len(self._users) > end
        return page, has_next

    def total_pages(self) -> int:
        import math
        return max(1, math.ceil(len(self._users) / PAGE_SIZE))


# ── Core logic ────────────────────────────────────────────────────────────────

def process_user_list(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    user_repo: UserSecRepository,
    page_num: int = 1,
    selected_rows: list[tuple[str, str]] = None,  # list of (sel_flag, user_id)
) -> UserListResult:
    """Process user list screen — mirrors COUSR00C PROCEDURE DIVISION."""
    result = UserListResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea

    if commarea.cdemo_pgm_context == 0:
        # First entry — load page 1 and display
        commarea.cdemo_pgm_context = 1
        return _load_page(1, user_repo, commarea, result)

    # Process key press
    if eibaid in (DFHENTER, "ENTER"):
        return _process_enter(selected_rows or [], page_num, user_repo, commarea, result)
    elif eibaid in (DFHPF3, "PF3"):
        result.return_to_prev = True
        result.xctl_program = "COADM01C"
        commarea.cdemo_to_program = "COADM01C"
        result.commarea = commarea
        return result
    elif eibaid in (DFHPF7, "PF7"):
        new_page = max(1, page_num - 1)
        return _load_page(new_page, user_repo, commarea, result)
    elif eibaid in (DFHPF8, "PF8"):
        new_page = page_num + 1
        return _load_page(new_page, user_repo, commarea, result)
    else:
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return _load_page(page_num, user_repo, commarea, result)


def _load_page(
    page_num: int,
    user_repo: UserSecRepository,
    commarea: CarddemoCommarea,
    result: UserListResult,
) -> UserListResult:
    users, has_next = user_repo.get_page(page_num)
    result.page_num = page_num
    result.has_next_page = has_next
    result.has_prev_page = page_num > 1
    result.rows = [
        UserListRow(
            user_id=u.sec_usr_id,
            user_name=f"{u.sec_usr_fname} {u.sec_usr_lname}".strip(),
            user_type="Admin" if u.sec_usr_type == "A" else "Regular",
        )
        for u in users
    ]
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.commarea = commarea
    return result


def _process_enter(
    selected_rows: list[tuple[str, str]],
    page_num: int,
    user_repo: UserSecRepository,
    commarea: CarddemoCommarea,
    result: UserListResult,
) -> UserListResult:
    """PROCESS-ENTER-KEY: check for row selection action."""
    for sel_flag, user_id in selected_rows:
        if sel_flag and sel_flag.strip() not in ("", "\x00") and user_id.strip():
            action = sel_flag.strip().upper()
            commarea.cdemo_pgm_context = 0
            result.selected_user_id = user_id.strip()
            result.selected_action = action

            if action in ("U", "u"):
                commarea.cdemo_to_program = "COUSR02C"
                result.xctl_program = "COUSR02C"
                result.commarea = commarea
                return result
            elif action in ("D", "d"):
                commarea.cdemo_to_program = "COUSR03C"
                result.xctl_program = "COUSR03C"
                result.commarea = commarea
                return result

    # No selection — refresh page
    return _load_page(page_num, user_repo, commarea, result)
