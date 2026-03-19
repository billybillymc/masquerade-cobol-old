"""
Reimplementation of COMEN01C — CardDemo User Main Menu.

CICS online program. Presents the main menu for regular users and routes
to selected programs via XCTL.

Menu options (from COMEN02Y.cpy):
   1. Account View          → COACTVWC
   2. Account Update        → COACTUPC
   3. Credit Card List      → COCRDLIC
   4. Credit Card View      → COCRDSLC
   5. Credit Card Update    → COCRDUPC
   6. Transaction List      → COTRN00C
   7. Transaction View      → COTRN01C
   8. Transaction Add       → COTRN02C
   9. Transaction Reports   → CORPT00C
  10. Bill Payment          → COBIL00C
  11. Pending Authorization → COPAUS0C
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader,
    CCDA_MSG_INVALID_KEY, MENU_USER_OPTIONS,
    DFHENTER, DFHPF3,
)


WS_PGMNAME = "COMEN01C"
WS_TRANID  = "CM00"


@dataclass
class UserMenuResult:
    xctl_program: str = ""
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    menu_options: list[str] = field(default_factory=list)
    selected_option: int = 0
    message: str = ""
    error: bool = False
    return_to_signon: bool = False


def process_user_menu(
    eibcalen: int,
    eibaid: str,
    commarea_bytes: CarddemoCommarea,
    option_input: str = "",
) -> UserMenuResult:
    """Process user main menu screen — mirrors COMEN01C PROCEDURE DIVISION."""
    result = UserMenuResult()

    if eibcalen == 0:
        result.return_to_signon = True
        result.xctl_program = "COSGN00C"
        return result

    commarea = commarea_bytes
    result.commarea = commarea
    result.menu_options = _build_menu_options()

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        return result

    if eibaid in (DFHENTER, "ENTER"):
        return _process_enter_key(option_input, commarea, result)
    elif eibaid in (DFHPF3, "PF3"):
        result.return_to_signon = True
        result.xctl_program = "COSGN00C"
        commarea.cdemo_to_program = "COSGN00C"
        result.commarea = commarea
        return result
    else:
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result


def _process_enter_key(
    option_input: str,
    commarea: CarddemoCommarea,
    result: UserMenuResult,
) -> UserMenuResult:
    """PROCESS-ENTER-KEY — validate and route based on user's selection."""
    option_x = option_input.strip().replace(" ", "0").zfill(2)
    try:
        option = int(option_x)
    except ValueError:
        option = 0

    result.selected_option = option
    menu_count = len(MENU_USER_OPTIONS)

    if not option_input.strip().isdigit() or option > menu_count or option == 0:
        result.error = True
        result.message = "Please enter a valid option number..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result

    opt_entry = MENU_USER_OPTIONS[option - 1]  # (num, name, pgm, usrtype)
    target_pgm = opt_entry[2]
    usr_type_required = opt_entry[3] if len(opt_entry) > 3 else "U"

    # Check admin-only options
    if usr_type_required == "A" and commarea.cdemo_user_type != "A":
        result.error = True
        result.message = "No access - Admin Only option... "
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result

    if target_pgm.startswith("DUMMY"):
        result.message = f"This option {opt_entry[1].strip()} is coming soon ..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result

    commarea.cdemo_from_tranid = WS_TRANID
    commarea.cdemo_from_program = WS_PGMNAME
    commarea.cdemo_pgm_context = 0
    result.commarea = commarea
    result.xctl_program = target_pgm
    return result


def _build_menu_options() -> list[str]:
    lines = []
    for num, name, pgm, *rest in MENU_USER_OPTIONS:
        lines.append(f"{num:02d}. {name:<35}")
    return lines
