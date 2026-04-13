"""
Reimplementation of Star Trek COBOL game (ctrek.cob) in Python.

A faithful translation of the ~1580-line COBOL program by Kurt Wilhelm (1979),
ported through OpenCOBOL by Harald Arnesen and Brian Tiffin (2010).

The player commands the USS Enterprise to destroy Klingons in an 8x8
(actually 9x9, quadrants 1-9) galaxy represented internally as a 126x126
master table (9 quadrants * 14 cells each).

Key design notes matching the COBOL source:
- The master table is 126x126 (9 quadrants of 14x14 sectors).
- Quadrants are numbered 1-9, sectors 1-14 within each quadrant.
- The RNG is a linear congruential generator: seed = frac(262147 * seed).
- The "generate table" (seed-table) is a 25-char string used for
  deterministic hit/miss outcomes (the 8400-generate paragraph).
"""

from __future__ import annotations

import math
from typing import Optional


# -- Constants from COBOL source -------------------------------------------

TITLE = "*STAR TREK*"
WELCOME_LINES = [
    "Congratulations - you have just been appointed",
    "Captain of the U.S.S. Enterprise.",
]
ENTER_NAME_PROMPT = "Please enter your name, Captain"
SKILL_PROMPT = "And your skill level (1-4)?"
INVALID_SKILL_MSG = "INVALID SKILL LEVEL"
RETRY_SKILL_MSG = "Enter your skill level (1-4)"

SEED_TABLE = "a4hfxnc89kd3jxf5dks3hb3m1"


def validate_skill_level(level: str) -> tuple[bool, str]:
    """Validate skill level input.

    Returns (valid, message). COBOL logic:
    IF skill-level < 1 OR > 4 -> INVALID SKILL LEVEL
    """
    try:
        n = int(level.strip())
        if n < 1 or n > 4:
            return False, INVALID_SKILL_MSG
        return True, ""
    except (ValueError, TypeError):
        return False, INVALID_SKILL_MSG


def get_mission_params(skill_level: int) -> dict:
    """Compute mission parameters based on skill level.

    From COBOL source (1260-assign paragraph):
    klingons = skill * 8
    star_dates = klingons (one star date per klingon)
    fuel = 40000 (constant)
    torpedoes = 5 (constant, adjusted by skill elsewhere)
    """
    klingons = skill_level * 8
    star_dates = klingons
    return {
        "klingons": klingons,
        "star_dates": star_dates,
        "fuel": 40000,
        "torpedoes": 5,
    }


def format_title_screen() -> list[str]:
    """Generate the title screen output."""
    return [TITLE, ""] + WELCOME_LINES + [""]


def format_mission_briefing(captain_name: str, params: dict) -> list[str]:
    """Generate the mission briefing text."""
    return [
        "*MESSAGE FROM STAR FLEET COMMAND*",
        "",
        f"Attention - Captain {captain_name}",
        "Your mission is to destroy the",
        f"{params['klingons']} Klingon ships that have invaded",
        "the galaxy to attack Star Fleet HQ",
    ]


# -- Helper: COBOL-style integer truncation --------------------------------

def _trunc(value: float) -> int:
    """Truncate toward zero, like COBOL PIC 99 COMPUTE assignment."""
    return int(value)


def _round(value: float) -> int:
    """COBOL ROUNDED: round half away from zero."""
    return int(math.floor(value + 0.5))


# -- Main game class -------------------------------------------------------

class StarTrekGame:
    """Full reimplementation of ctrek.cob."""

    def __init__(self, seed: int, captain_name: str = "KIRK", skill_level: int = 1):
        self.captain_name = captain_name.upper()[:12]
        self.skill_level = max(1, min(4, skill_level))
        self._output: list[str] = []

        # -- Working storage initialisation (0100-housekeeping) --
        self.shield_cnt: int = 0
        self.damage_cnt: int = 0
        self.fuel_count: int = 40000
        self.indicate_z: int = 0   # 0 = just-starting
        self.genrte_result: int = 0
        self.indicate_x: int = 0   # 1 = bye-bye
        self.indicate_y: int = 0   # 1 = trap-vec
        self.attack_flag: int = 0  # 1 = klingons-attacking
        self.too_late_flag: int = 0
        self.torps: int = 5
        self.var1: int = 1
        self.nx: int = 0
        self.base_cnt: int = 0

        self.generate_table: list[str] = list(SEED_TABLE)

        # Master table: 126x126, 1-indexed -> use [0] as padding.
        self.master_tbl: list[list[str]] = [
            [" " for _ in range(127)] for _ in range(127)
        ]

        # Mini table: 14x14, 1-indexed
        self.mini_table: list[list[str]] = [
            [" " for _ in range(15)] for _ in range(15)
        ]

        # Star table: 42x42, 1-indexed
        self.star_table: list[list[str]] = [
            [" " for _ in range(43)] for _ in range(43)
        ]

        # Scan table: 14x14, 1-indexed
        self.scan_table: list[list[str]] = [
            [" " for _ in range(15)] for _ in range(15)
        ]

        # Enterprise position in master table
        self.mrctr: int = 0
        self.mkctr: int = 0

        # Current quadrant
        self.q1: int = 0
        self.q2: int = 0
        self.qs_1: int = 0
        self.qs_2: int = 0

        # HQ position (quadrant)
        self.hq1: int = 0
        self.hq2: int = 0

        # Klingon/Romulon counts
        self.klgns: int = 0
        self.romulons: int = 0

        # Star date tracking
        self.s_date: int = 0
        self.ds_date: int = 0
        self.ws_date: int = 0

        # Klingon hit tally for current quadrant
        self.kh_tl: int = 0

        # Distance tracking
        self.dist_x: int = 30
        self.dist_r: int = 30
        self.dist_b: int = 30
        self.ct_k: int = 0
        self.ct_r: int = 0

        # Distance arrays
        self.dist_k_str: list[int] = [0] * 46   # dkc(1..45)
        self.dist_r_str: list[int] = [0] * 61   # drc(1..60)

        # Positions found by compute-dist
        self.e1: int = 0
        self.e2: int = 0
        self.k1: int = 0
        self.k2: int = 0
        self.r1: int = 0
        self.r2: int = 0
        self.b1: int = 0
        self.b2: int = 0

        # rx = number of K's to skip when destroying nearest
        self.rx: int = 0
        self.qx: int = 0

        # Scan keep: cv(1..18)
        self.scan_keep: list[int] = [0] * 19

        # k-or = total klingons at start
        self.k_or: int = 0
        self.klingons: int = 0

        # -- Skill-based computations (from 0100-housekeeping) --
        name_x = self.captain_name.ljust(12)[:12]
        vab6 = 0
        for ch in name_x:
            if ch.lower() == 'a':
                vab6 += 1
            if ch.lower() == 'e':
                vab6 += 1
        vab6 += 1
        vab5 = name_x.count(' ')
        # COBOL: compute vab6 rounded = (vab5 / 1.75) + (vab6 / skill-lev)
        vab6 = _round(vab5 / 1.75 + vab6 / self.skill_level)
        # compute k-or rounded = (skill-lev * 4) + vab6 + 5
        self.k_or = _round(self.skill_level * 4 + vab6 + 5)
        # compute vab1 = 9 - skill-lev
        self.vab1 = 9 - self.skill_level
        # compute vab2 rounded = (skill-lev / 3) * k-or
        self.vab2 = _round((self.skill_level / 3) * self.k_or)
        self.klingons = self.k_or

        # -- Seed initialisation --
        # COBOL: ACCEPT ws-time FROM TIME gives HHMMSSCC.
        # time-rev reverses the last 6 digits: CC SS MM
        # seed-x = rev-str / 1000000
        # For deterministic testing we treat seed as the 8-digit time value.
        seed_str = str(seed).zfill(8)
        ws_hour = int(seed_str[0:2])
        ws_min = int(seed_str[2:4])
        ws_sec = int(seed_str[4:6])
        ws_sixty = int(seed_str[6:8])

        # s-date from ds-table: ds-min=ws-min, ds-sec=ws-sec -> s-date = MMSS
        ds_min = ws_min
        ds_sec = ws_sec
        self.s_date = ds_min * 100 + ds_sec

        # time-flag logic
        ds_min_deadline = ds_min + 16
        if ds_min_deadline > 59:
            self.time_flag = 1
        else:
            self.time_flag = 0
        self.ds_date = ds_min_deadline * 100 + ds_sec

        # time-rev: CC SS MM
        rev_str_s = f"{ws_sixty:02d}{ws_sec:02d}{ws_min:02d}"
        rev_str = int(rev_str_s)
        self.seed_x = rev_str / 1000000.0

        # ws-date for too-late tracking
        self.ws_date = self.ds_date

        # game over / finished
        self.game_over = False
        self.game_won = False
        self._pending_input: Optional[str] = None

        # -- Initialize galaxy --
        self.initialize_galaxy()

        # Build initial output
        self._build_initial_output()

    # ================================================================
    # Output helpers
    # ================================================================

    def _display(self, text: str = "      ") -> None:
        self._output.append(text)

    def _flush_output(self) -> list[str]:
        out = self._output
        self._output = []
        return out

    # ================================================================
    # RNG  (1220-roll)
    # ================================================================

    def _roll(self, max_no: int) -> int:
        """Linear congruential RNG matching COBOL 1220-roll.

        seed-ast = 262147.0 * seed-x   (PIC 9(6)V9(6))
        seed-x = fractional part of seed-ast  (PIC V9(6))
        roll-x = seed-x * max-no + 1   (PIC 999V -> truncated to int)

        COBOL PIC 9(6)V9(6) holds 12 significant digits, so the intermediate
        seed-ast preserves enough precision to avoid short cycles. We use
        Python's full float precision for the intermediate and only truncate
        seed-x to 12 decimal places (matching the 6+6 COBOL layout).
        """
        seed_ast = 262147.0 * self.seed_x
        frac = seed_ast - int(seed_ast)
        # PIC V9(6) but intermediate has 12 digits — use 12dp to avoid short cycles
        self.seed_x = int(frac * 1000000000000) / 1000000000000.0
        roll_x = int(self.seed_x * max_no) + 1
        return roll_x

    def _dbl_roll(self, max_no: int) -> tuple[int, int]:
        """1225-dbl-roll: two rolls returning (a, b)."""
        a = self._roll(max_no)
        b = self._roll(max_no)
        return a, b

    # ================================================================
    # Generate  (8400-generate)
    # ================================================================

    def _generate(self) -> None:
        """8400-generate: advance nx in the 25-char seed table.

        Sets genrte_result (1 = no-way if digit) and
        indicate_y (1 = trap-vec if 'f').
        """
        if self.nx > 24:
            self.nx = 0
        self.nx += 1
        ch = self.generate_table[self.nx - 1]
        if ch.isdigit():
            self.genrte_result = 1   # no-way
        else:
            self.indicate_y = 0
            self.genrte_result = 0
            if ch == 'f':
                self.indicate_y = 1  # trap-vec

    @property
    def no_way(self) -> bool:
        return self.genrte_result == 1

    @property
    def trap_vec(self) -> bool:
        return self.indicate_y == 1

    @property
    def bye_bye(self) -> bool:
        return self.indicate_x == 1

    @property
    def just_starting(self) -> bool:
        return self.indicate_z == 0

    @property
    def klingons_attacking(self) -> bool:
        return self.attack_flag == 1

    @property
    def too_late(self) -> bool:
        return self.too_late_flag == 1

    # ================================================================
    # Galaxy initialisation  (1200-initialize-galaxy)
    # ================================================================

    def initialize_galaxy(self) -> None:
        """1200-initialize-galaxy: place all objects on master table."""
        for r in range(127):
            for c in range(127):
                self.master_tbl[r][c] = " "

        # Stars: 275
        for _ in range(275):
            a, b = self._dbl_roll(126)
            self.master_tbl[a][b] = "*"

        # Romulons: vab2
        for _ in range(self.vab2):
            a, b = self._dbl_roll(126)
            self.master_tbl[a][b] = "R"

        # Klingons: k-or, placed in empty cells
        for _ in range(self.k_or):
            a, b = self._dbl_roll(126)
            while self.master_tbl[a][b] != " ":
                a, b = self._dbl_roll(126)
            self.master_tbl[a][b] = "K"

        # Bases: vab1, placed in empty cells
        for _ in range(self.vab1):
            a, b = self._dbl_roll(126)
            while self.master_tbl[a][b] != " ":
                a, b = self._dbl_roll(126)
            self.master_tbl[a][b] = "B"

        # Enterprise: in empty cell
        a, b = self._dbl_roll(126)
        while self.master_tbl[a][b] != " ":
            a, b = self._dbl_roll(126)
        self.mrctr = a
        self.mkctr = b
        self.master_tbl[self.mrctr][self.mkctr] = "E"

        # HQ: in empty cell
        a, b = self._dbl_roll(126)
        while self.master_tbl[a][b] != " ":
            a, b = self._dbl_roll(126)
        self.master_tbl[a][b] = "H"
        # COBOL: hq1 = (b-1)/14 + 1, hq2 = (a-1)/14 + 1
        self.hq1 = (b - 1) // 14 + 1
        self.hq2 = (a - 1) // 14 + 1

    # ================================================================
    # Transfer helpers
    # ================================================================

    def _trans(self) -> None:
        """5900-trans: copy from master table to mini table for current quadrant."""
        x = (self.q1 - 1) * 14
        y = (self.q2 - 1) * 14
        for kcntr in range(1, 15):
            for rcntr in range(1, 15):
                a = y + rcntr
                b = x + kcntr
                if 1 <= a <= 126 and 1 <= b <= 126:
                    self.mini_table[rcntr][kcntr] = self.master_tbl[a][b]
                else:
                    self.mini_table[rcntr][kcntr] = " "

    def _trans_back(self) -> None:
        """5400-trans-back: copy mini table back to master table."""
        x = (self.q1 - 1) * 14
        y = (self.q2 - 1) * 14
        for kcntr in range(1, 15):
            for rcntr in range(1, 15):
                a = y + rcntr
                b = x + kcntr
                if 1 <= a <= 126 and 1 <= b <= 126:
                    self.master_tbl[a][b] = self.mini_table[rcntr][kcntr]

    def _trans_star(self) -> None:
        """7650-trans-star: copy 42x42 region from master to star table."""
        if self.q1 == 1:
            q9 = 2
        elif self.q1 == 9:
            q9 = 8
        else:
            q9 = self.q1
        if self.q2 == 1:
            r9 = 2
        elif self.q2 == 9:
            r9 = 8
        else:
            r9 = self.q2
        w = (q9 - 2) * 14
        z = (r9 - 2) * 14
        for rctr in range(1, 43):
            for kctr in range(1, 43):
                a = z + rctr
                b = w + kctr
                if 1 <= a <= 126 and 1 <= b <= 126:
                    self.star_table[rctr][kctr] = self.master_tbl[a][b]
                else:
                    self.star_table[rctr][kctr] = " "

    # ================================================================
    # Display helpers
    # ================================================================

    def _display_quadrant_grid(self) -> None:
        """6500-display-mt / 6600-mini-dis / 6700-mini-mod."""
        self._display("= = = = = = = = = = = = = = = =")
        for row in range(1, 15):
            md_row = [" "] * 29
            for col in range(1, 15):
                mod_ctr = 2 * col
                if mod_ctr < 29:
                    md_row[mod_ctr] = self.mini_table[row][col]
            self._display("=" + "".join(md_row) + " =")
        self._display("= = = = = = = = = = = = = = = =")

    def _con_red_str(self) -> str:
        return f"*Condition RED* {self.klgns:02d} Klingons in quadrant"

    def _con_green_str(self) -> str:
        return "*Condition GREEN*"

    def _quadrant_str(self) -> str:
        return f"Quadrant {self.q1},{self.q2}    STAR DATE: {self.s_date:04d}"

    # ================================================================
    # Initial output  (0100-housekeeping display portion)
    # ================================================================

    def _build_initial_output(self) -> None:
        self._display("      ")
        self._display("      *STAR TREK* ")
        self._display("      ")
        self._display("Congratulations - you have just been appointed ")
        self._display("Captain of the U.S.S. Enterprise. ")
        self._display("      ")
        self._display("      ")
        self._display("      *MESSAGE FROM STAR FLEET COMMAND* ")
        self._display("      ")
        self._display(f"Attention - Captain {self.captain_name}")
        self._display("Your mission is to destroy the ")
        self._display(f"{self.k_or:02d} Klingon ships that have invaded ")
        self._display("the galaxy to attack Star Fleet HQ ")
        self._display(f"on star date {self.ds_date:04d} - giving you 16 star dates.")
        # Initial quadrant display (4000-display-g)
        self._display_g()
        self.indicate_z = 1

    # ================================================================
    # 4000-display-g
    # ================================================================

    def _display_g(self) -> None:
        """4000-display-g: determine quadrant, display it, handle klingon fire."""
        self.klgns = 0
        self.romulons = 0
        self.base_cnt = 0
        self.qs_1 = self.q1
        self.qs_2 = self.q2
        self.q1 = (self.mkctr - 1) // 14 + 1
        self.q2 = (self.mrctr - 1) // 14 + 1
        if self.q1 != self.qs_1 or self.q2 != self.qs_2:
            self.kh_tl = 0
        self._trans()
        for r in range(1, 15):
            for c in range(1, 15):
                ch = self.mini_table[r][c]
                if ch == "K":
                    self.klgns += 1
                elif ch == "R":
                    self.romulons += 1
                elif ch == "B":
                    self.base_cnt += 1

        self._display("      ")
        if self.just_starting:
            self._display(f"You begin in quadrant {self.q1},{self.q2} with 40,000 ")
            self._display("units of fuel and 5 photon torpedoes. ")
            self._display("      ")
            self._display(f"Good luck, Captain {self.captain_name}")
            self._display("      ")
            if self.klgns > 0:
                self._display(self._con_red_str())
            else:
                self._display(self._con_green_str())
        else:
            if self.klgns > 0:
                self._display(self._con_red_str())
                var2 = self.klgns * self.fuel_count // (self.shield_cnt + 27)
                var2 = self._test_var(var2)
                var3 = int(0.75 * var2)
                self.damage_cnt += var2
                self.shield_cnt -= var3
                self._display("*ENTERPRISE ENCOUNTERING KLINGON FIRE* ")
                self._display(f"{var2:6d} unit hit on Enterprise ")
            else:
                self._display(self._con_green_str())

        self._display(self._quadrant_str())
        self._display_quadrant_grid()
        self._display("      ")
        self._ck_fuel_damage()
        self._ck_done()

    def _test_var(self, var2: int) -> int:
        """4200-test-var."""
        if var2 < 1776 and self.klgns > 0:
            var2 += 223
            var2 = _trunc(
                self.klgns * var2 / 3.5
                + var2 * self.damage_cnt / 760
                + self.nx * 17
            )
        return var2

    # ================================================================
    # 1100-chk-galaxy  (periodic K/R shuffling)
    # ================================================================

    def _chk_galaxy(self) -> None:
        """1100-chk-galaxy."""
        self.var1 += 1
        if self.var1 == 7:
            self._master_replace_all("      K", "K      ")
            self._reset_1120()
        elif self.var1 == 12:
            self._master_replace_all("R      ", "      R")
            self._reset_1120()
        elif self.var1 == 15:
            self._master_replace_all("K           ", "           K")
            self._reset_1120()
        elif self.var1 > 20:
            self._master_replace_all("         R", "R         ")
            self._reset_1120()
            self.var1 = 1

    def _master_replace_all(self, old: str, new: str) -> None:
        """INSPECT master-tbl REPLACING ALL old BY new (linear)."""
        flat = ""
        for r in range(1, 127):
            for c in range(1, 127):
                flat += self.master_tbl[r][c]
        flat = flat.replace(old, new)
        idx = 0
        for r in range(1, 127):
            for c in range(1, 127):
                self.master_tbl[r][c] = flat[idx]
                idx += 1

    def _reset_1120(self) -> None:
        """1120-reset: re-transfer and recount."""
        self._trans()
        self.klgns = 0
        self.romulons = 0
        self.base_cnt = 0
        for r in range(1, 15):
            for c in range(1, 15):
                ch = self.mini_table[r][c]
                if ch == "K":
                    self.klgns += 1
                elif ch == "R":
                    self.romulons += 1
                elif ch == "B":
                    self.base_cnt += 1

    # ================================================================
    # 7220-compute-dist
    # ================================================================

    def _compute_dist(self) -> None:
        """7220-compute-dist: find E, compute distances to K, R, B."""
        self.dist_b = 30
        self.dist_x = 30
        self.dist_r = 30
        self.ct_k = 0
        self.ct_r = 0

        # 7225-find-e
        for rcntr in range(1, 15):
            for kcntr in range(1, 15):
                if self.mini_table[rcntr][kcntr] == "E":
                    self.e1 = rcntr
                    self.e2 = kcntr

        # 7230-compute
        for rcntr in range(1, 15):
            for kcntr in range(1, 15):
                ch = self.mini_table[rcntr][kcntr]
                if ch == "K":
                    k1 = rcntr
                    k2 = kcntr
                    self.ct_k += 1
                    str_a = self.dist_x
                    dk1 = abs(k1 - self.e1)
                    dk2 = abs(k2 - self.e2)
                    d = _round(math.sqrt(dk1 ** 2 + dk2 ** 2))
                    self.dist_x = d
                    if self.ct_k <= 45:
                        self.dist_k_str[self.ct_k] = d
                    if self.dist_x > str_a:
                        self.dist_x = str_a
                if ch == "R":
                    r1 = rcntr
                    r2 = kcntr
                    self.ct_r += 1
                    str_r = self.dist_r
                    dr1 = abs(r1 - self.e1)
                    dr2 = abs(r2 - self.e2)
                    d = _round(math.sqrt(dr1 ** 2 + dr2 ** 2))
                    self.dist_r = d
                    if self.ct_r <= 60:
                        self.dist_r_str[self.ct_r] = d
                    if self.dist_r > str_r:
                        self.dist_r = str_r
                if ch == "B":
                    b1 = rcntr
                    b2 = kcntr
                    str_x = self.dist_b
                    db1 = abs(b1 - self.e1)
                    db2 = abs(b2 - self.e2)
                    self.dist_b = _round(math.sqrt(db1 ** 2 + db2 ** 2))
                    if self.dist_b > str_x:
                        self.dist_b = str_x

        # 7247-est-nbr
        str_x = 30
        self.rx = 0
        for rt in range(1, self.ct_k + 1):
            if rt <= 45 and self.dist_k_str[rt] < str_x:
                str_x = self.dist_k_str[rt]
                self.rx = rt - 1

        str_r = 30
        self.qx = 0
        for qt in range(1, self.ct_r + 1):
            if qt <= 60 and self.dist_r_str[qt] < str_r:
                str_r = self.dist_r_str[qt]
                self.qx = qt - 1

    # ================================================================
    # Mini-table helpers
    # ================================================================

    def _mini_replace_first(self, old: str, new: str) -> None:
        """INSPECT mini-table REPLACING FIRST old BY new."""
        for r in range(1, 15):
            for c in range(1, 15):
                if self.mini_table[r][c] == old:
                    self.mini_table[r][c] = new
                    return

    def _mini_replace_all(self, old: str, new: str) -> None:
        """INSPECT mini-table REPLACING ALL old BY new."""
        for r in range(1, 15):
            for c in range(1, 15):
                if self.mini_table[r][c] == old:
                    self.mini_table[r][c] = new

    def _mini_count(self, ch: str) -> int:
        count = 0
        for r in range(1, 15):
            for c in range(1, 15):
                if self.mini_table[r][c] == ch:
                    count += 1
        return count

    # ================================================================
    # Navigation  (7100-nav)
    # ================================================================

    def _nav(self, course_a: int, course_b: int,
             warp_a: int, warp_b: int) -> None:
        """7100-nav: navigate the Enterprise."""
        if not self._ck_fl():
            return

        self.fuel_count -= 200 * warp_a
        if warp_a > 0:
            rx_s = float(warp_a)
        else:
            rx_s = round(warp_b / 100.0, 2)

        srctr = self.mrctr
        skctr = self.mkctr

        warp1 = _round(warp_a * 5 + warp_b * 0.05)
        warp2 = _round(warp_a * 8 + warp_b * 0.08)
        warp3 = _round(course_b * 0.05 * rx_s)
        warp4 = _round(course_b * 0.03 * rx_s)

        if course_a == 1:
            srctr = srctr - warp2 + warp4
            skctr = skctr + warp3
        elif course_a == 2:
            srctr = srctr - warp1 + warp3
            skctr = skctr + warp1 + warp4
        elif course_a == 3:
            srctr = srctr + warp3
            skctr = skctr + warp2 - warp4
        elif course_a == 4:
            srctr = srctr + warp1 + warp4
            skctr = skctr + warp1 - warp3
        elif course_a == 5:
            srctr = srctr + warp2 - warp4
            skctr = skctr - warp3
        elif course_a == 6:
            srctr = srctr + warp1 - warp3
            skctr = skctr - warp1 - warp4
        elif course_a == 7:
            srctr = srctr - warp3
            skctr = skctr - warp2 + warp4
        elif course_a == 8:
            srctr = srctr - warp1 - warp4
            skctr = skctr - warp1 + warp3
        else:
            self._display("INVALID COURSE")
            return

        self._nav_ck(srctr, skctr)

    def _nav_ck(self, srctr: int, skctr: int) -> None:
        """7000-nav-ck: check navigation bounds and move."""
        if srctr < 1 or srctr > 126 or skctr < 1 or skctr > 126:
            self._display("Warp drive shut down - ")
            self._display("UNAUTHORIZED ATTEMPT TO LEAVE GALAXY ")
            self._dmg_com()
        else:
            self.master_tbl[self.mrctr][self.mkctr] = " "
            self.mrctr = srctr
            self.mkctr = skctr
            target = self.master_tbl[self.mrctr][self.mkctr]
            if target in ("K", "R", "B"):
                self._bomb()
            else:
                self.master_tbl[self.mrctr][self.mkctr] = "E"

    def _bomb(self) -> None:
        """8000-bomb: collision."""
        target = self.master_tbl[self.mrctr][self.mkctr]
        if target == "K":
            self._display("*ENTERPRISE DESTROYED IN COLLISION WITH KLINGON*")
        elif target == "R":
            self._display("*ENTERPRISE DESTROYED IN COLLISION WITH ROMULON*")
        else:
            self._display("*ENTERPRISE DESTROYED IN COLLISION WITH STAR BASE*")
        self.indicate_x = 1
        self._ck_done()

    # ================================================================
    # Phasers  (7200-pha)
    # ================================================================

    def _pha(self, var4_input: int) -> None:
        """7200-pha: fire phasers."""
        if self.klgns < 1 and self.romulons < 1:
            self._display("Science Officer Spock reports no enemy ")
            self._display(f"vessels in this quadrant, {self.captain_name}")
            return

        if not self._ck_fl():
            return

        if self.fuel_count < 9999:
            self._display(
                f"Maximum of {self.fuel_count:5d} units available to phasers "
            )

        var4 = var4_input
        if var4 < 300:
            var4 = 300

        self._compute_dist()
        var2 = 450000 // (self.shield_cnt + 100)
        self._generate()
        var2 = self._test_agn(var2)

        if self.klgns > 1 and self.trap_vec:
            self._display("*ENTERPRISE DESTROYED* ")
            self._display(f"Direct hits from {self.klgns} klingons ")
            self.indicate_x = 1
            self._ck_done()
            return

        dm_var4 = var4 - self.damage_cnt // 15
        var3 = var2 // 2

        if self.klgns > 0:
            if self.dist_x >= 10:
                var2 = var2 // (self.dist_x // 10)
            self.fuel_count -= var4
            var4 = dm_var4
            var4 += self.kh_tl
            if var4 < 400:
                self._display(f"{var4:6d} unit hit on Klingon ")
                self._display("*KLINGON DISABLED* ")
                self._display(f"{var2:6d} unit hit on Enterprise ")
                var4 = int(0.75 * var4)
                self.kh_tl += var4
                self.damage_cnt += var2
                self.shield_cnt -= int(0.75 * var2)
            else:
                for _ in range(self.rx):
                    self._mini_replace_first("K", "x")
                self._mini_replace_first("K", " ")
                self._mini_replace_all("x", "K")
                if self.dist_x > 0:
                    var4 = _trunc(var4 / (self.dist_x ** 0.224))
                self._display(f"{var4:6d} unit hit on Klingon ")
                self._display("*KLINGON DESTROYED* ")
                self.kh_tl = 0
                self.klgns -= 1
                self.klingons -= 1
                self._trans_back()
                if self.klgns > 0:
                    self._display(f"{var2:6d} unit hit on Enterprise ")
                    self.damage_cnt += var2
                    var2 = int(0.75 * var2)
                    self.shield_cnt -= var2
                else:
                    var2 = var3
                    self._display(f"{var2:6d} unit hit on Enterprise ")
                    self.damage_cnt += var3
                    self.shield_cnt -= var3
        else:
            self._display(
                f"There are 0 Klingons in this quadrant, {self.captain_name}"
            )

        self._dam_com_romulon()
        self._ck_fuel_damage()
        self._ck_done()

    def _pha_romulon(self, var4: int) -> None:
        """7250-romulon-ck for phasers."""
        if self.romulons > 2 and self.no_way:
            self._display("*ENTERPRISE FIRING ON ROMULONS*")
            self._display("*ROMULONS RETURNING FIRE* ")
            self._display(f"Simultaneous hits from {self.romulons} Romulons ")
            self._display("*ENTERPRISE DESTROYED*")
            self.indicate_x = 1
            self._ck_done()
            return

        self._generate()
        self._display("*ENTERPRISE FIRING ON ROMULONS* ")
        self.fuel_count -= var4
        var2 = 450000 // (self.shield_cnt + 100)
        var2 = self._test_agn(var2)
        var3 = var2 // 2

        if self.no_way or var4 < 447:
            if self.dist_r > 0:
                var4_hit = _trunc(var4 / (self.dist_r ** 0.224))
            else:
                var4_hit = var4
            self._display(f"{var4_hit:6d} unit hit on Romulon ")
            self._display("*ROMULON RETURNING FIRE*")
            self._generate()
            if self.no_way:
                self._display("*ENTERPRISE DESTROYED BY ROMULON TORPEDO* ")
                self.indicate_x = 1
                self._ck_done()
                return
            else:
                if self.dist_r >= 10:
                    var2 = 3 * var2 // (self.dist_r // 10)
                else:
                    var2 = 3 * var2
                self._display(f"{var2:6d} unit hit on Enterprise ")
                self.damage_cnt += var2
                var3 = var2 // 2
                if var3 < 9999:
                    self.shield_cnt -= var3
                else:
                    self.shield_cnt = 0
        else:
            if self.dist_x > 0:
                var4_hit = _trunc(var4 / (self.dist_x ** 0.125))
            else:
                var4_hit = var4
            self._display(f"{var4_hit:6d} unit hit on Romulon ")
            self._display("*ROMULON DESTROYED*")
            for _ in range(self.qx):
                self._mini_replace_first("R", "x")
            self._mini_replace_first("R", " ")
            self._mini_replace_all("x", "R")
            self.romulons -= 1
            self._trans_back()

        self._dmg_com()
        self._ck_fuel_damage()
        self._ck_done()

    # ================================================================
    # Torpedoes  (7300-tor)
    # ================================================================

    def _tor(self) -> None:
        """7300-tor: fire torpedo."""
        if self.klgns < 1 and self.romulons < 1:
            self._display(
                f"There are 0 enemy vessels in this quadrant, {self.captain_name}"
            )
            return

        self._generate()
        var2 = 250000 // (self.shield_cnt + 100)
        var2 = self._test_agn(var2)
        self._compute_dist()
        if self.klgns > 2:
            var2 = var2 * (self.klgns + 1) // 2
        var3 = int(0.75 * var2)

        if self.torps > 0:
            if self.klgns > 0:
                if self.shield_cnt < 475 and self.no_way:
                    self._display("*ENTERPRISE DESTROYED*")
                    self._display("Low shields at time of enemy attack ")
                    self.indicate_x = 1
                    self._ck_done()
                    return
                else:
                    if self.no_way and self.dist_x > 4:
                        if self.dist_x >= 10:
                            var2 = var2 // (self.dist_x // 10)
                        self._display("torpedo missed ")
                        self._display(f"{var2:6d} unit hit on Enterprise ")
                        self.damage_cnt += var2
                        self.torps -= 1
                        self.shield_cnt -= var3
                        self._dam_com_romulon()
                    else:
                        self._display("*KLINGON DESTROYED*")
                        self.damage_cnt -= var3
                        for _ in range(self.rx):
                            self._mini_replace_first("K", "x")
                        self._mini_replace_first("K", " ")
                        self._mini_replace_all("x", "K")
                        self.torps -= 1
                        self.klgns -= 1
                        self.klingons -= 1
                        self._trans_back()
                        if self.klgns > 0:
                            self._display(f"{var2:6d} unit hit on Enterprise ")
                            self.damage_cnt += var2
                            self.shield_cnt -= var3
                            self._dam_com_romulon()
                        else:
                            self._dam_com_romulon()
            else:
                self._display(
                    f"There are 0 Klingon vessels in this quadrant, "
                    f"{self.captain_name}"
                )
        else:
            self._display(f"0 torpedoes remaining, {self.captain_name}")

        self._ck_fuel_damage()
        self._ck_done()

    def _tor_romulon(self) -> None:
        """7350-romulon-ck for torpedoes."""
        var2 = 250000 // (self.shield_cnt + 100)
        var2 = self._test_agn(var2)
        var3 = int(0.75 * var2)

        if self.romulons > 1 and self.no_way:
            self._display("*ENTERPRISE FIRING ON ROMULONS*")
            self._display("*ROMULONS RETURNING FIRE*")
            self._display(f"Simultaneous hits from {self.romulons} Romulons ")
            self._display("*ENTERPRISE DESTROYED*")
            self.indicate_x = 1
            self._ck_done()
            return

        self._display("*ENTERPRISE FIRING ON ROMULONS*")
        self.torps -= 1
        if self.no_way and self.dist_r > 4:
            self._display("torpedo missed ")
            self._display("*ROMULONS RETURNING FIRE*")
            self._generate()
            if self.no_way and self.shield_cnt < 4000:
                self._display("*ENTERPRISE DESTROYED BY ROMULON TORPEDO*")
                self.indicate_x = 1
                self._ck_done()
                return
            else:
                if self.dist_r >= 10:
                    var2 = 3 * var2 // (self.dist_r // 10)
                else:
                    var2 = 3 * var2
                self._display(f"{var2:6d} unit hit on Enterprise ")
                self.damage_cnt += var2
                var3 = var2 // 2
                self.shield_cnt -= var3
        else:
            self._display("*ROMULON DESTROYED*")
            for _ in range(self.qx):
                self._mini_replace_first("R", "x")
            self._mini_replace_first("R", " ")
            self._mini_replace_all("x", "R")
            self.romulons -= 1
            self._trans_back()

        self._ck_fuel_damage()
        self._ck_done()

    # ================================================================
    # Shields  (7500-def)
    # ================================================================

    def _def(self, amount: int) -> None:
        """7500-def: set shield level."""
        self.fuel_count += self.shield_cnt
        self.shield_cnt = amount
        if self.shield_cnt < self.fuel_count:
            self.fuel_count -= self.shield_cnt
        else:
            self._display(f"Maximum amount to shields: {self.fuel_count:5d}")
            self.shield_cnt = min(amount, self.fuel_count)
            self.fuel_count -= self.shield_cnt
        self._display(f"Shields at {self.shield_cnt:4d} per your command ")

    # ================================================================
    # Docking  (7600-doc)
    # ================================================================

    def _doc(self) -> None:
        """7600-doc: attempt to dock at starbase."""
        self._generate()
        if self.base_cnt > 0:
            self._compute_dist()
            if self.dist_b < 7:
                if self.no_way:
                    self._display("*UNSUCCESSFUL DOCKING ATTEMPT* ")
                    self._display("Star base reports all bays in use ")
                    self._dmg_com()
                else:
                    self.torps = 5
                    self.fuel_count = 25000
                    self.damage_cnt = 0
                    self.shield_cnt = 0
                    self._display("Shields dropped to dock at star base ")
                    self._display("*DOCK SUCCESSFUL* ")
            else:
                self._display(f"The nearest star base is {self.dist_b} parsecs ")
                self._display("You must maneuver to within 6 parsecs to dock ")
        else:
            self._display(
                f"There are 0 star bases in this quadrant, {self.captain_name}"
            )
        self._ck_fuel_damage()
        self._ck_done()

    # ================================================================
    # Library Computer  (3000-com-fun)
    # ================================================================

    def _com_fun(self, comp_com: int) -> None:
        """3000-com-fun: library computer commands 1-6."""
        self._display("      ")
        if comp_com == 1:
            self._sta()
        elif comp_com == 2:
            self._display_g()
        elif comp_com == 3:
            self._lrs()
        elif comp_com == 4:
            self._com_4()
        elif comp_com == 5:
            self._intelligence()
        elif comp_com == 6:
            self._com_6()
        else:
            self._display(" INVALID COMPUTER COMMAND ")

    def _sta(self) -> None:
        """7400-sta: ship status."""
        var3 = self.damage_cnt // 60
        self._display("      ")
        self._display("FUEL UNITS   DAMAGE ")
        self._display("REMAINING    LEVEL  ")
        self._display("      ")
        self._display(f"   {self.fuel_count:5d}  {var3:6d}%")
        self._display("      ")
        self._display("===================")
        self._display("      ")
        self._display(" PHOTON      SHIELD ")
        self._display("TORPEDOES    LEVEL ")
        self._display("      ")
        self._display(f"    {self.torps}         {self.shield_cnt:4d}")
        self._display("      ")
        self._dmg_com()
        self._ck_fuel_damage()
        self._ck_done()

    def _lrs(self) -> None:
        """7700-lrs: long range scan."""
        self._trans_star()
        self.scan_keep = [0] * 19
        scan_ctr = 0

        if self.q1 == 1:
            qt1, qt3 = 1, 3
        elif self.q1 == 9:
            qt1, qt3 = 7, 9
        else:
            qt1, qt3 = self.q1 - 1, self.q1 + 1

        if self.q2 == 1:
            qt2, qt4 = 1, 3
        elif self.q2 == 9:
            qt2, qt4 = 7, 9
        else:
            qt2, qt4 = self.q2 - 1, self.q2 + 1

        for tr2 in range(3):
            for tr1 in range(3):
                qt = tr1 * 14
                rt = tr2 * 14
                for ktctr in range(1, 15):
                    for rtctr in range(1, 15):
                        qx_idx = qt + ktctr
                        rx_idx = rt + rtctr
                        if 1 <= rx_idx <= 42 and 1 <= qx_idx <= 42:
                            self.scan_table[rtctr][ktctr] = (
                                self.star_table[rx_idx][qx_idx]
                            )
                        else:
                            self.scan_table[rtctr][ktctr] = " "

                scan_ctr += 1
                k_count = 0
                for r in range(1, 15):
                    for c in range(1, 15):
                        if self.scan_table[r][c] == "K":
                            k_count += 1
                if scan_ctr <= 18:
                    self.scan_keep[scan_ctr] = k_count

                scan_ctr += 1
                b_count = 0
                for r in range(1, 15):
                    for c in range(1, 15):
                        if self.scan_table[r][c] == "B":
                            b_count += 1
                if scan_ctr <= 18:
                    self.scan_keep[scan_ctr] = b_count

        cv = self.scan_keep
        self._display("      ")
        self._display(f"===={qt1}==============={qt3}====")
        self._display("=       =       =       =")
        self._display(
            f"= {cv[1]:02d},{cv[2]:02d} = {cv[3]:02d},{cv[4]:02d}"
            f" = {cv[5]:02d},{cv[6]:02d} = "
        )
        self._display("=       =       =       =")
        self._display("=========================")
        self._display("=       =       =       =")
        self._display(
            f"= {cv[7]:02d},{cv[8]:02d} = {cv[9]:02d},{cv[10]:02d}"
            f" = {cv[11]:02d},{cv[12]:02d} ="
        )
        self._display("=       =       =       =")
        self._display("=========================")
        self._display("=       =       =       =")
        self._display(
            f"= {cv[13]:02d},{cv[14]:02d} = {cv[15]:02d},{cv[16]:02d}"
            f" = {cv[17]:02d},{cv[18]:02d} ="
        )
        self._display("=       =       =       =")
        self._display("=========================")
        self._display("KEY: ")
        self._display(f"Quadrants {qt1},{qt2} thru {qt3},{qt4}")
        self._display("Format - KLINGONS,STAR BASES ")
        if self.q1 == 1 or self.q1 == 9 or self.q2 == 1 or self.q2 == 9:
            self._display("*ENTERPRISE ON GALACTIC BOUNDARY*")
        self._display(f"Enterprise in quadrant {self.q1},{self.q2}")
        self._display("      ")
        self._dmg_com()
        self._ck_fuel_damage()
        self._ck_done()

    def _com_4(self) -> None:
        """3040-com: klingon tally."""
        bye_k = self.k_or - self.klingons
        self._display("      ")
        self._display(
            f"{bye_k:02d} Klingons destroyed, {self.klingons:02d} remain "
        )
        self._display(f"ATTACK DATE: {self.ds_date:04d}")
        self._display(f"STAR DATE: {self.s_date:04d}")
        self._display("      ")
        self._dmg_com()

    def _intelligence(self) -> None:
        """7800-int: intelligence report."""
        if self.klingons > 0:
            cx = 1
            dx = 1
            while dx <= 126:
                if 1 <= cx <= 126 and self.master_tbl[cx][dx] == "K":
                    break
                cx += 1
                if cx > 126:
                    dx += 1
                    cx = 1
            if dx <= 126:
                cx_1 = (dx - 1) // 14 + 1
                dx_1 = (cx - 1) // 14 + 1
                self._display(" ")
                self._display("Latest intelligence gathering reports ")
                self._display("indicate 1 or more Klingon vessels ")
                self._display(f"in the vicinity of quadrant {cx_1},{dx_1}")
                self._display(" ")
                self._display(f"Enterprise in quadrant {self.q1},{self.q2}")
                self._display(" ")

    def _com_6(self) -> None:
        """3060-com: terminate."""
        self._display("      ")
        self._display("*ENTERPRISE STRANDED - CAPTAIN BOOKED* ")
        self._display("      ")
        self.indicate_x = 1
        self._ck_done()

    # ================================================================
    # Damage / fuel checks
    # ================================================================

    def _dmg_com(self) -> None:
        """8100-dmg-com: klingon fire after action."""
        if self.klgns > 0:
            var2 = (
                (self.k_or - self.klingons) * self.klgns * self.fuel_count
                // (self.shield_cnt + 21)
            )
            var2 = self._test_agn(var2)
            var3 = int(0.75 * var2)
            self._display("*ENTERPRISE ENCOUNTERING KLINGON FIRE*")
            self._display(f"{var2:6d} unit hit on Enterprise ")
            self.damage_cnt += var2
            self.shield_cnt -= var3

    def _dam_com_romulon(self) -> None:
        """8120-dam-com: romulon fire after action."""
        if self.romulons > 0:
            var2 = self.romulons * self.fuel_count // (self.shield_cnt + 7)
            var2 = self._test_agn_romulon(var2)
            var3 = int(0.75 * var2)
            self._display("*ENTERPRISE ENCOUNTERING ROMULON FIRE*")
            self._display(f"{var2:6d} unit hit on Enterprise ")
            self.damage_cnt += var2
            self.shield_cnt -= var3

    def _test_agn(self, var2: int) -> int:
        """8150-test-agn."""
        if var2 < 325 and self.klgns > 0:
            var2 += 177
            var2 = _trunc(
                self.klgns * var2 / 2.7 + var2 * self.damage_cnt / 980
            )
        return var2

    def _test_agn_romulon(self, var2: int) -> int:
        """8160-test-agn."""
        if var2 < 525 and self.romulons > 0:
            var2 += 254
            var2 = _trunc(
                self.romulons * var2 / 4.7 + var2 * self.damage_cnt / 365
            )
        return var2

    def _ck_done(self) -> None:
        """8200-ck-done."""
        if self.bye_bye:
            self.game_over = True

    def _ck_fuel_damage(self) -> None:
        """8300-ck-fuel-damage."""
        if 0 < self.fuel_count < 4500:
            self._display(
                f"Lt. Scott reports fuel is running low, {self.captain_name}"
            )
        elif self.fuel_count <= 0:
            self._display("Fuel reserves depleted ")
            self._display("the Enterprise is drifting in space ")
            self._ck_shift()
        if self.damage_cnt > 6000:
            self._display("Enterprise stranded because of heavy damage ")
            self.indicate_x = 1
            self._ck_done()
            return
        if self.damage_cnt > 4500:
            self._display(
                f"Damage Control reports heavy damage to Enterprise, "
                f"{self.captain_name}"
            )
        if self.shield_cnt < 800 and (self.klgns > 0 or self.romulons > 0):
            self._display(
                f"Lt. Sulu reports shields dangerously low, {self.captain_name}"
            )

    def _ck_fl(self) -> bool:
        """8340-ck-fl: check fuel. Returns False if cannot continue."""
        if self.fuel_count <= 180:
            self._display("*INSUFFICIENT FUEL TO CONTINUE*")
            self._ck_shift()
            return False
        return True

    def _ck_shift(self) -> None:
        """8350-ck-shift."""
        if self.shield_cnt > 200:
            self._display("Lt. Sulu advises you lower shields ")
            self._display(f"to increase fuel supply, {self.captain_name}")
        else:
            self.indicate_x = 1
            self._ck_done()

    # ================================================================
    # Finish game  (8500-finish-game)
    # ================================================================

    def _finish_game(self) -> None:
        """8500-finish-game."""
        self._display("      ")
        if self.bye_bye:
            if self.s_date > self.ds_date:
                vae1 = self.klingons
                self.ds_date = self.ws_date
                self._display(f"It is now star date {self.s_date}")
                self._display(f"STAR DATE {self.ds_date} Star Fleet HQ")
                self._display(f"was destroyed by {vae1} klingon vessels")
                self._display(f"{self.captain_name} COURT MARTIALED")
            else:
                self._display(f"{self.captain_name} COURT MARTIALED")
        else:
            self._display("Congratulations on a job well done. ")
            self._display(
                f"The Federation is proud of you, {self.captain_name}"
            )
            self.game_won = True
        self._display("      ")

    # ================================================================
    # Command processing  (2000-process)
    # ================================================================

    def process_command(self, command: str) -> list[str]:
        """Process a command, return output lines.

        Commands:
          nav <course> <warp>                - navigate
          nav <course>.<cb> <warp>.<wb>      - navigate with decimals
          pha <units>                        - fire phasers
          pha_romulon <units>                - fire phasers at romulons
          tor                                - fire torpedo
          tor_romulon                        - fire torpedo at romulons
          def <amount>                       - set shields
          doc                                - dock at starbase
          com <1-6>                          - library computer
          com6_confirm                       - confirm terminate
        """
        self._output = []

        if self.game_over:
            self._finish_game()
            return self._flush_output()

        parts = command.strip().split()
        if not parts:
            self._display(
                "INVALID COMMAND - Do you want a list of commands? "
            )
            return self._flush_output()

        cmd = parts[0].lower()

        # Pre-command: generate and check (from 2000-process)
        self._generate()
        if self.no_way or self.klgns > 1:
            self.nx += 4

        if cmd in ("nav", "navigate"):
            if len(parts) >= 3:
                course_str = parts[1]
                warp_str = parts[2]
                if "." in course_str:
                    cp = course_str.split(".")
                    course_a = int(cp[0]) if cp[0] else 0
                    course_b = int(cp[1]) if len(cp) > 1 and cp[1] else 0
                else:
                    course_a = int(course_str)
                    course_b = 0
                if "." in warp_str:
                    wp = warp_str.split(".")
                    warp_a = int(wp[0]) if wp[0] else 0
                    warp_b = int(wp[1]) if len(wp) > 1 and wp[1] else 0
                else:
                    warp_a = int(warp_str)
                    warp_b = 0

                if course_a < 1 or course_a > 8:
                    self._display("INVALID COURSE")
                else:
                    self._nav(course_a, course_b, warp_a, warp_b)
                    self._display_g()
            elif len(parts) == 2:
                entry = parts[1]
                if len(entry) >= 2:
                    course_a = int(entry[0])
                    warp_a = int(entry[1])
                    self._nav(course_a, 0, warp_a, 0)
                    self._display_g()
                else:
                    self._display("INVALID COURSE")
            else:
                self._display("What course (1 - 8.99)? ")
                return self._flush_output()

        elif cmd in ("pha", "phasers"):
            if len(parts) >= 2:
                var4 = int(parts[1])
                self._pha(var4)
            else:
                self._display("How many units to phaser banks? ")
                return self._flush_output()

        elif cmd == "pha_romulon":
            if len(parts) >= 2:
                var4 = int(parts[1])
                self._pha_romulon(var4)
            else:
                self._display("How many units to phaser banks? ")

        elif cmd in ("tor", "torpedo"):
            self._tor()

        elif cmd == "tor_romulon":
            self._tor_romulon()

        elif cmd in ("def", "shields"):
            if len(parts) >= 2:
                amount = int(parts[1])
                self._def(amount)
            else:
                self._display("How many units to shields (0 - 9999)? ")

        elif cmd in ("doc", "dock"):
            self._doc()

        elif cmd in ("com", "computer"):
            if len(parts) >= 2:
                comp_com = int(parts[1])
                if comp_com == 6:
                    self._com_6()
                else:
                    self._com_fun(comp_com)
            else:
                self._display("*COMPUTER ACTIVE AND AWAITING COMMAND* ")

        elif cmd == "com6_confirm":
            self._com_6()

        else:
            self._display(
                "INVALID COMMAND - Do you want a list of commands? "
            )

        # Post-command processing (from 2000-process)
        self._chk_galaxy()

        # Check win condition
        if self.klingons < 1 and not self.game_over:
            self.game_over = True
            self._finish_game()

        if self.game_over and not self.game_won:
            self._finish_game()

        return self._flush_output()

    # ================================================================
    # Status (for differential testing)
    # ================================================================

    def get_status(self) -> dict:
        """Return current game state as a dict for differential testing."""
        return {
            "captain_name": self.captain_name,
            "skill_level": self.skill_level,
            "fuel_count": self.fuel_count,
            "shield_cnt": self.shield_cnt,
            "damage_cnt": self.damage_cnt,
            "torps": self.torps,
            "klingons": self.klingons,
            "klingons_initial": self.k_or,
            "klgns_in_quadrant": self.klgns,
            "romulons_in_quadrant": self.romulons,
            "base_cnt": self.base_cnt,
            "quadrant": (self.q1, self.q2),
            "enterprise_pos": (self.mrctr, self.mkctr),
            "hq_quadrant": (self.hq1, self.hq2),
            "s_date": self.s_date,
            "ds_date": self.ds_date,
            "seed_x": self.seed_x,
            "game_over": self.game_over,
            "game_won": self.game_won,
            "indicate_x": self.indicate_x,
            "nx": self.nx,
            "var1": self.var1,
        }

    def get_initial_output(self) -> list[str]:
        """Return initial output lines produced during construction."""
        return self._flush_output()

    # ================================================================
    # Instructions
    # ================================================================

    @staticmethod
    def get_instructions() -> list[str]:
        """0500-prt-inst + 0550-add-inst: return instruction text."""
        return [
            "      ",
            "You may use the following commands: ",
            "       nav  (to navigate) ",
            "       pha  (to fire phasers) ",
            "       tor  (to fire torpedo) ",
            "       def  (to raise or lower shields) ",
            "       doc  (to dock at a star base) ",
            "       com  (to request info from the library computer) ",
            "      ",
            "COURSE PLOT: ",
            "      ",
            "    1 ",
            "  8   2 ",
            "7  -x-  3 ",
            "  6   4 ",
            "    5 ",
            "      ",
        ]

    @staticmethod
    def get_computer_help() -> list[str]:
        """Return list of computer commands."""
        return [
            "Functions available from the library computer: ",
            "     1  To request ship status ",
            "     2  To request short range scan of quadrant ",
            "     3  To request long range scan ",
            "     4  To request tally of Klingons ",
            "     5  To request intelligence report ",
            "     6  To terminate program execution ",
            "      ",
        ]

    def galaxy_fingerprint(self) -> dict:
        """Return a digest of the galaxy state for parity testing."""
        counts = {"K": 0, "R": 0, "B": 0, "E": 0, "H": 0, "*": 0, " ": 0}
        for r in range(1, 127):
            for c in range(1, 127):
                ch = self.master_tbl[r][c]
                if ch in counts:
                    counts[ch] += 1
                else:
                    counts[ch] = counts.get(ch, 0) + 1
        return {
            "MRCTR": str(self.mrctr),
            "MKCTR": str(self.mkctr),
            "HQ1": str(self.hq1),
            "HQ2": str(self.hq2),
            "K_OR": str(self.k_or),
            "KLINGONS": str(self.klingons),
            "VAB1": str(self.vab1),
            "VAB2": str(self.vab2),
            "S_DATE": str(self.s_date),
            "DS_DATE": str(self.ds_date),
            "SEED_X": f"{self.seed_x:.12f}",
            "FUEL": str(self.fuel_count),
            "TORPS": str(self.torps),
            "COUNT_K": str(counts.get("K", 0)),
            "COUNT_R": str(counts.get("R", 0)),
            "COUNT_B": str(counts.get("B", 0)),
            "COUNT_STAR": str(counts.get("*", 0)),
            "COUNT_E": str(counts.get("E", 0)),
            "COUNT_H": str(counts.get("H", 0)),
        }


# ── Differential harness runner adapter ────────────────────────────────────


def _status_to_strings(status: dict) -> dict:
    """Convert a status dict to flat string dict matching Java formatting."""
    out = {}
    for k, v in status.items():
        if k == "seed_x":
            out[str(k)] = f"{v:.12f}"
        elif isinstance(v, tuple):
            out[str(k)] = f"({v[0]}, {v[1]})"
        elif isinstance(v, bool):
            out[str(k)] = "True" if v else "False"
        else:
            out[str(k)] = str(v)
    return out


def run_vector(inputs: dict) -> dict:
    scenario = str(inputs.get("SCENARIO", "")).upper()

    if scenario == "INIT_STATE":
        seed = int(inputs.get("SEED", "12345678"))
        skill = int(inputs.get("SKILL_LEVEL", "1"))
        name = str(inputs.get("CAPTAIN_NAME", "KIRK"))
        game = StarTrekGame(seed=seed, captain_name=name, skill_level=skill)
        return game.galaxy_fingerprint()

    if scenario == "MISSION_PARAMS":
        skill = int(inputs.get("SKILL_LEVEL", "1"))
        params = get_mission_params(skill)
        return {k.upper(): str(v) for k, v in params.items()}

    if scenario == "SKILL_VALIDATION":
        level = str(inputs.get("LEVEL", "1"))
        valid, msg = validate_skill_level(level)
        return {"VALID": "Y" if valid else "N", "MESSAGE": msg}

    if scenario == "GAME_STATUS":
        seed = int(inputs.get("SEED", "12345678"))
        skill = int(inputs.get("SKILL_LEVEL", "1"))
        name = str(inputs.get("CAPTAIN_NAME", "KIRK"))
        game = StarTrekGame(seed=seed, captain_name=name, skill_level=skill)
        status = game.get_status()
        return _status_to_strings(status)

    if scenario == "PROCESS_COMMANDS":
        seed = int(inputs.get("SEED", "12345678"))
        skill = int(inputs.get("SKILL_LEVEL", "1"))
        name = str(inputs.get("CAPTAIN_NAME", "KIRK"))
        game = StarTrekGame(seed=seed, captain_name=name, skill_level=skill)
        # Flush initial output
        game.get_initial_output()
        cmds = str(inputs.get("COMMANDS", ""))
        if cmds:
            for cmd in cmds.split(";"):
                cmd = cmd.strip()
                if cmd:
                    game.process_command(cmd)
        status = game.get_status()
        return _status_to_strings(status)

    if scenario == "INITIAL_OUTPUT":
        seed = int(inputs.get("SEED", "12345678"))
        skill = int(inputs.get("SKILL_LEVEL", "1"))
        name = str(inputs.get("CAPTAIN_NAME", "KIRK"))
        game = StarTrekGame(seed=seed, captain_name=name, skill_level=skill)
        lines = game.get_initial_output()
        return {
            "LINE_COUNT": str(len(lines)),
            "FIRST_LINE": lines[0] if lines else "",
            "LAST_LINE": lines[-1] if lines else "",
        }

    return {"error": f"unknown scenario: {scenario!r}"}
