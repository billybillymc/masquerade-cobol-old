"""
Reimplementation of COADM01C — CardDemo Admin Menu.

CICS online program. Presents a menu of admin functions (user management,
transaction type maintenance) and routes to the selected program via XCTL.

Admin menu options (from COADM02Y.cpy):
  1. User List (Security)               → COUSR00C
  2. User Add (Security)                → COUSR01C
  3. User Update (Security)             → COUSR02C
  4. User Delete (Security)             → COUSR03C
  5. Transaction Type List/Update (Db2) → COTRTLIC
  6. Transaction Type Maintenance (Db2) → COTRTUPC
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader,
    CCDA_MSG_INVALID_KEY, MENU_ADMIN_OPTIONS,
    DFHENTER, DFHPF3,
)


WS_PGMNAME = "COADM01C"
WS_TRANID  = "CA00"


@dataclass
class AdminMenuResult:
    """Result of processing one admin-menu screen interaction."""
    xctl_program: str = ""          # target program for XCTL (empty = stay/return)
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    menu_options: list[str] = field(default_factory=list)
    selected_option: int = 0
    message: str = ""
    error: bool = False
    return_to_signon: bool = False


def process_admin_menu(
    eibcalen: int,
    eibaid: str,
    commarea_bytes: CarddemoCommarea,
    option_input: str = "",
) -> AdminMenuResult:
    """Process admin menu screen interaction — mirrors COADM01C PROCEDURE DIVISION.

    Decision tree:
      IF EIBCALEN = 0     → redirect to COSGN00C (no commarea = unauth)
      ELSE
        IF NOT CDEMO-PGM-REENTER
          → first time here: send menu screen
        ELSE
          EVALUATE EIBAID
            WHEN ENTER → PROCESS-ENTER-KEY
            WHEN PF3   → return to signon
            WHEN OTHER → invalid key error
    """
    result = AdminMenuResult()

    if eibcalen == 0:
        result.return_to_signon = True
        result.xctl_program = "COSGN00C"
        return result

    commarea = commarea_bytes
    result.commarea = commarea

    # Populate menu option list for display
    result.menu_options = _build_menu_options()

    if commarea.cdemo_pgm_context == 0:
        # First entry (NOT CDEMO-PGM-REENTER) — send menu
        commarea.cdemo_pgm_context = 1
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        return result

    # Re-entry — process key press
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
    result: AdminMenuResult,
) -> AdminMenuResult:
    """PROCESS-ENTER-KEY logic."""
    option_x = option_input.strip().replace(" ", "0").zfill(2)
    try:
        option = int(option_x)
    except ValueError:
        option = 0

    result.selected_option = option
    admin_count = len(MENU_ADMIN_OPTIONS)

    if not option_input.strip().isdigit() or option > admin_count or option == 0:
        result.error = True
        result.message = "Please enter a valid option number..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result

    # Look up selected option
    opt_entry = MENU_ADMIN_OPTIONS[option - 1]
    target_pgm = opt_entry[2]

    if target_pgm.startswith("DUMMY"):
        result.message = f"This option is not installed ..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        return result

    # XCTL to target program
    commarea.cdemo_from_tranid = WS_TRANID
    commarea.cdemo_from_program = WS_PGMNAME
    commarea.cdemo_pgm_context = 0
    result.commarea = commarea
    result.xctl_program = target_pgm
    return result


def _build_menu_options() -> list[str]:
    """BUILD-MENU-OPTIONS — format the numbered option lines."""
    lines = []
    for num, name, pgm in MENU_ADMIN_OPTIONS:
        lines.append(f"{num:02d}. {name:<35}")
    return lines


# ── Differential harness runner adapter ──────────────────────────────────────

def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness.

    SCENARIO selects a hardcoded test path:
      VALID_OPTION_1  — select option 1 (User List) → COUSR00C
      VALID_OPTION_5  — select option 5 (Tran Type List) → COTRTLIC
      INVALID_OPTION  — select option 99 → error
      INVALID_KEY     — press PF9 → invalid key error
      PF3_RETURN      — press PF3 → return to sign-on
      FIRST_ENTRY     — first entry (context=0) → send menu
    """
    scenario = inputs.get("SCENARIO", "VALID_OPTION_1")

    commarea = CarddemoCommarea(
        cdemo_from_tranid="CC00",
        cdemo_from_program="COSGN00C",
        cdemo_user_id="ADMIN001",
        cdemo_user_type="A",
        cdemo_pgm_context=1,
    )

    if scenario == "FIRST_ENTRY":
        commarea.cdemo_pgm_context = 0
        result = process_admin_menu(
            eibcalen=100, eibaid="ENTER", commarea_bytes=commarea, option_input="",
        )
    elif scenario == "VALID_OPTION_1":
        result = process_admin_menu(
            eibcalen=100, eibaid="ENTER", commarea_bytes=commarea, option_input="1",
        )
    elif scenario == "VALID_OPTION_5":
        result = process_admin_menu(
            eibcalen=100, eibaid="ENTER", commarea_bytes=commarea, option_input="5",
        )
    elif scenario == "INVALID_OPTION":
        result = process_admin_menu(
            eibcalen=100, eibaid="ENTER", commarea_bytes=commarea, option_input="99",
        )
    elif scenario == "INVALID_KEY":
        result = process_admin_menu(
            eibcalen=100, eibaid="PF9", commarea_bytes=commarea, option_input="",
        )
    elif scenario == "PF3_RETURN":
        result = process_admin_menu(
            eibcalen=100, eibaid="PF3", commarea_bytes=commarea, option_input="",
        )
    else:
        result = process_admin_menu(
            eibcalen=100, eibaid="ENTER", commarea_bytes=commarea, option_input="1",
        )

    return {
        "XCTL_PROGRAM": result.xctl_program or "",
        "ERROR": "Y" if result.error else "N",
        "MESSAGE": result.message,
        "RETURN_TO_SIGNON": "Y" if result.return_to_signon else "N",
        "SELECTED_OPTION": str(result.selected_option),
    }
