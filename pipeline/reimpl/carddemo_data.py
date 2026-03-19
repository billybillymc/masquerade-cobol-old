"""
Shared data structures for the CardDemo application reimplementation.

All copybook structures translated from COBOL to Python dataclasses.
Each record type preserves field names (snake_case of the COBOL hyphenated names)
and data types faithful to the PIC clauses.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


# ── COCOM01Y — Communication Area ────────────────────────────────────────────

@dataclass
class CarddemoCommarea:
    """CARDDEMO-COMMAREA from COCOM01Y.cpy — passed between all CICS programs."""
    cdemo_from_tranid: str = ""       # PIC X(04)
    cdemo_from_program: str = ""      # PIC X(08)
    cdemo_to_tranid: str = ""         # PIC X(04)
    cdemo_to_program: str = ""        # PIC X(08)
    cdemo_user_id: str = ""           # PIC X(08)
    cdemo_user_type: str = ""         # PIC X(01)  'R'=regular, 'A'=admin
    cdemo_pgm_context: int = 0        # PIC S9(09) COMP; 0=fresh, 1=reenter


# ── CVACT01Y — Account Record ─────────────────────────────────────────────────

@dataclass
class AccountRecord:
    """ACCOUNT-RECORD from CVACT01Y.cpy (RECLN 300)."""
    acct_id: int = 0                   # PIC 9(11)
    acct_active_status: str = ""       # PIC X(01)  'Y'/'N'
    acct_curr_bal: Decimal = Decimal("0.00")          # PIC S9(10)V99
    acct_credit_limit: Decimal = Decimal("0.00")      # PIC S9(10)V99
    acct_cash_credit_limit: Decimal = Decimal("0.00") # PIC S9(10)V99
    acct_open_date: str = ""           # PIC X(10)  YYYY-MM-DD
    acct_expiration_date: str = ""     # PIC X(10)
    acct_reissue_date: str = ""        # PIC X(10)
    acct_curr_cyc_credit: Decimal = Decimal("0.00")   # PIC S9(10)V99
    acct_curr_cyc_debit: Decimal = Decimal("0.00")    # PIC S9(10)V99
    acct_addr_zip: str = ""            # PIC X(10)
    acct_group_id: str = ""            # PIC X(10)  e.g. "GOLD", "PLAT"


# ── CVACT02Y — Card Record ────────────────────────────────────────────────────

@dataclass
class CardRecord:
    """CARD-RECORD from CVACT02Y.cpy (RECLN 150)."""
    card_num: str = ""                 # PIC X(16)
    card_acct_id: int = 0             # PIC 9(11)
    card_cvv_cd: int = 0              # PIC 9(03)
    card_embossed_name: str = ""      # PIC X(50)
    card_expiration_date: str = ""    # PIC X(10)
    card_active_status: str = ""      # PIC X(01)


# ── CVACT03Y — Card Cross-Reference ──────────────────────────────────────────

@dataclass
class CardXrefRecord:
    """CARD-XREF-RECORD from CVACT03Y.cpy (RECLN 50)."""
    xref_card_num: str = ""           # PIC X(16)
    xref_cust_id: int = 0            # PIC 9(09)
    xref_acct_id: int = 0            # PIC 9(11)


# ── CVCUS01Y — Customer Record ───────────────────────────────────────────────

@dataclass
class CustomerRecord:
    """CUSTOMER-RECORD from CVCUS01Y.cpy (RECLN 500)."""
    cust_id: int = 0                   # PIC 9(09)
    cust_first_name: str = ""          # PIC X(25)
    cust_middle_name: str = ""         # PIC X(25)
    cust_last_name: str = ""           # PIC X(25)
    cust_addr_line_1: str = ""         # PIC X(50)
    cust_addr_line_2: str = ""         # PIC X(50)
    cust_addr_line_3: str = ""         # PIC X(50)
    cust_addr_state_cd: str = ""       # PIC X(02)
    cust_addr_country_cd: str = ""     # PIC X(03)
    cust_addr_zip: str = ""            # PIC X(10)
    cust_phone_num_1: str = ""         # PIC X(15)
    cust_phone_num_2: str = ""         # PIC X(15)
    cust_ssn: int = 0                  # PIC 9(09)
    cust_govt_issued_id: str = ""      # PIC X(20)
    cust_dob_yyyy_mm_dd: str = ""      # PIC X(10)
    cust_eft_account_id: str = ""      # PIC X(10)
    cust_pri_card_holder_ind: str = "" # PIC X(01)
    cust_fico_credit_score: int = 0    # PIC 9(03)


# ── CVTRA05Y — Transaction Record ────────────────────────────────────────────

@dataclass
class TranRecord:
    """TRAN-RECORD from CVTRA05Y.cpy (RECLN 350)."""
    tran_id: str = ""                  # PIC X(16)
    tran_type_cd: str = ""             # PIC X(02)  '01'=interest,'02'=fee,...
    tran_cat_cd: int = 0               # PIC 9(04)
    tran_source: str = ""              # PIC X(10)
    tran_desc: str = ""                # PIC X(100)
    tran_amt: Decimal = Decimal("0.00")  # PIC S9(09)V99
    tran_merchant_id: int = 0          # PIC 9(09)
    tran_merchant_name: str = ""       # PIC X(50)
    tran_merchant_city: str = ""       # PIC X(50)
    tran_merchant_zip: str = ""        # PIC X(10)
    tran_card_num: str = ""            # PIC X(16)
    tran_orig_ts: str = ""             # PIC X(26)  DB2 timestamp
    tran_proc_ts: str = ""             # PIC X(26)


# ── CVTRA01Y — Transaction Category Balance ───────────────────────────────────

@dataclass
class TranCatBalRecord:
    """TRAN-CAT-BAL-RECORD from CVTRA01Y.cpy."""
    trancat_acct_id: int = 0           # PIC 9(11)
    trancat_type_cd: str = ""          # PIC X(02)
    trancat_cd: int = 0                # PIC 9(04)
    tran_cat_bal: Decimal = Decimal("0.00")  # PIC S9(09)V99


# ── CVTRA02Y — Disclosure Group / Interest Rate ───────────────────────────────

@dataclass
class DisGroupRecord:
    """DIS-GROUP-RECORD from CVTRA02Y.cpy."""
    dis_acct_group_id: str = ""        # PIC X(10)
    dis_tran_type_cd: str = ""         # PIC X(02)
    dis_tran_cat_cd: int = 0           # PIC 9(04)
    dis_int_rate: Decimal = Decimal("0.00")  # PIC S9(09)V99


# ── CSUSR01Y — Security User Record ──────────────────────────────────────────

@dataclass
class SecUserData:
    """From CSUSR01Y.cpy — user security record."""
    sec_usr_id: str = ""               # PIC X(08)
    sec_usr_fname: str = ""            # PIC X(20)
    sec_usr_lname: str = ""            # PIC X(20)
    sec_usr_pwd: str = ""              # PIC X(08)
    sec_usr_type: str = ""             # PIC X(01)  'A'=admin, 'R'=regular


# ── COTTL01Y — Title constants ───────────────────────────────────────────────

CCDA_TITLE01 = "      AWS Mainframe Modernization       "
CCDA_TITLE02 = "              CardDemo                  "
CCDA_MSG_THANK_YOU = "Thank you for using CCDA application... "
CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    "


# ── COMEN02Y — User Menu Options ─────────────────────────────────────────────

MENU_USER_OPTIONS = [
    (1,  "Account View",                 "COACTVWC", "U"),
    (2,  "Account Update",               "COACTUPC", "U"),
    (3,  "Credit Card List",             "COCRDLIC", "U"),
    (4,  "Credit Card View",             "COCRDSLC", "U"),
    (5,  "Credit Card Update",           "COCRDUPC", "U"),
    (6,  "Transaction List",             "COTRN00C", "U"),
    (7,  "Transaction View",             "COTRN01C", "U"),
    (8,  "Transaction Add",              "COTRN02C", "U"),
    (9,  "Transaction Reports",          "CORPT00C", "U"),
    (10, "Bill Payment",                 "COBIL00C", "U"),
    (11, "Pending Authorization View",   "COPAUS0C", "U"),
]

# ── COADM02Y — Admin Menu Options ────────────────────────────────────────────

MENU_ADMIN_OPTIONS = [
    (1, "User List (Security)",               "COUSR00C"),
    (2, "User Add (Security)",                "COUSR01C"),
    (3, "User Update (Security)",             "COUSR02C"),
    (4, "User Delete (Security)",             "COUSR03C"),
    (5, "Transaction Type List/Update (Db2)", "COTRTLIC"),
    (6, "Transaction Type Maintenance (Db2)", "COTRTUPC"),
]


# ── EIBAID constants (CICS Attention Identifier Bytes) ───────────────────────

DFHENTER = "ENTER"    # Enter key
DFHPF1   = "PF1"
DFHPF2   = "PF2"
DFHPF3   = "PF3"
DFHPF4   = "PF4"
DFHPF5   = "PF5"
DFHPF6   = "PF6"
DFHPF7   = "PF7"
DFHPF8   = "PF8"
DFHPF9   = "PF9"
DFHPF10  = "PF10"
DFHPF11  = "PF11"
DFHPF12  = "PF12"
DFHCLEAR = "CLEAR"
DFHPA1   = "PA1"
DFHPA2   = "PA2"


# ── Helper: format DB2 timestamp ─────────────────────────────────────────────

def get_db2_timestamp(dt: datetime = None) -> str:
    """Return DB2-format timestamp: YYYY-MM-DD-HH.MM.SS.000000"""
    if dt is None:
        dt = datetime.now()
    return (
        f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}-"
        f"{dt.hour:02d}.{dt.minute:02d}.{dt.second:02d}."
        f"{dt.microsecond // 10000:02d}0000"
    )


def format_date_mm_dd_yy(dt: datetime = None) -> str:
    """MM/DD/YY format for screen display."""
    if dt is None:
        dt = datetime.now()
    return f"{dt.month:02d}/{dt.day:02d}/{dt.year % 100:02d}"


def format_time_hh_mm_ss(dt: datetime = None) -> str:
    """HH:MM:SS format for screen display."""
    if dt is None:
        dt = datetime.now()
    return f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"


# ── Screen Output base ────────────────────────────────────────────────────────

@dataclass
class ScreenHeader:
    """Common header fields present on every CardDemo screen."""
    trnname: str = ""
    title01: str = CCDA_TITLE01
    title02: str = CCDA_TITLE02
    curdate: str = ""
    curtime: str = ""
    pgmname: str = ""
    errmsg: str = ""

    @classmethod
    def now(cls, trnname: str, pgmname: str) -> "ScreenHeader":
        dt = datetime.now()
        return cls(
            trnname=trnname,
            pgmname=pgmname,
            curdate=format_date_mm_dd_yy(dt),
            curtime=format_time_hh_mm_ss(dt),
        )
