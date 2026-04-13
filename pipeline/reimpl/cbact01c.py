"""
Reimplementation of CBACT01C — CardDemo Batch Account File Reader.

Function: Read the account VSAM KSDS sequentially and write records to:
  - OUT-FILE:   flat sequential file with reformatted fields
  - ARRY-FILE:  array record (account ID + balance array)
  - VBRC-FILE:  variable-length records (VB1=12 bytes, VB2=39 bytes)

Also calls COBDATFT for date reformatting (replicated inline here).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Iterator, Callable

from .carddemo_data import AccountRecord, get_db2_timestamp


# ── Output record structures ──────────────────────────────────────────────────

@dataclass
class OutAcctRec:
    """OUT-FILE record — fixed sequential output."""
    acct_id: int = 0
    acct_active_status: str = ""
    acct_curr_bal: Decimal = Decimal("0.00")
    acct_credit_limit: Decimal = Decimal("0.00")
    acct_cash_credit_limit: Decimal = Decimal("0.00")
    acct_open_date: str = ""
    acct_expiration_date: str = ""
    acct_reissue_date: str = ""
    acct_curr_cyc_credit: Decimal = Decimal("0.00")
    acct_curr_cyc_debit: Decimal = Decimal("0.00")
    acct_group_id: str = ""


@dataclass
class ArrAcctBal:
    curr_bal: Decimal = Decimal("0.00")
    curr_cyc_debit: Decimal = Decimal("0.00")


@dataclass
class ArrArrayRec:
    """ARRY-FILE record — array of 5 balance entries."""
    acct_id: int = 0
    balances: list[ArrAcctBal] = field(
        default_factory=lambda: [ArrAcctBal() for _ in range(5)]
    )


@dataclass
class VbRec1:
    """Variable-length record type 1 (12 bytes)."""
    acct_id: int = 0
    acct_active_status: str = ""


@dataclass
class VbRec2:
    """Variable-length record type 2 (39 bytes)."""
    acct_id: int = 0
    acct_curr_bal: Decimal = Decimal("0.00")
    acct_credit_limit: Decimal = Decimal("0.00")
    acct_reissue_yyyy: str = ""


@dataclass
class ProcessResult:
    out_records: list[OutAcctRec] = field(default_factory=list)
    arr_records: list[ArrArrayRec] = field(default_factory=list)
    vb1_records: list[VbRec1] = field(default_factory=list)
    vb2_records: list[VbRec2] = field(default_factory=list)
    records_read: int = 0
    display_lines: list[str] = field(default_factory=list)


# ── Date conversion (inlined from COBDATFT) ───────────────────────────────────

def _reformat_date(date_str: str, in_type: str, out_type: str) -> str:
    """Simplified COBDATFT date reformatter.

    type '2' = YYYY-MM-DD (ISO),  type '1' = MM/DD/YYYY
    """
    if not date_str or date_str.strip() == "":
        return date_str
    try:
        if in_type == "2":
            # Input: YYYY-MM-DD
            y, m, d = date_str.strip().split("-")
        elif in_type == "1":
            m, d, y = date_str.strip().split("/")
        else:
            return date_str

        if out_type == "2":
            return f"{y}-{m}-{d}"
        elif out_type == "1":
            return f"{m}/{d}/{y}"
        return date_str
    except (ValueError, AttributeError):
        return date_str


# ── Core processing ───────────────────────────────────────────────────────────

def process_account_file(
    accounts: list[AccountRecord],
    logger: Callable[[str], None] = print,
) -> ProcessResult:
    """Process all account records — mirrors CBACT01C PROCEDURE DIVISION.

    For each account:
      1. Display the account record (1100-DISPLAY-ACCT-RECORD)
      2. Build and write OUT-FILE record (1300-POPUL / 1350-WRITE)
      3. Build and write ARRY-FILE record (1400-POPUL / 1450-WRITE)
      4. Build and write VBRC records (1500-POPUL / 1550,1575-WRITE)
    """
    result = ProcessResult()
    logger("START OF EXECUTION OF PROGRAM CBACT01C")

    for acct in accounts:
        result.records_read += 1

        # 1100-DISPLAY-ACCT-RECORD
        lines = _display_acct_record(acct)
        for line in lines:
            logger(line)
        result.display_lines.extend(lines)

        # 1300-POPUL-ACCT-RECORD + 1350-WRITE
        out_rec = _build_out_record(acct)
        result.out_records.append(out_rec)

        # 1400-POPUL-ARRAY-RECORD + 1450-WRITE
        arr_rec = _build_arr_record(acct)
        result.arr_records.append(arr_rec)

        # 1500-POPUL-VBRC-RECORD + 1550/1575-WRITE
        vb1, vb2 = _build_vb_records(acct)
        logger(f"VBRC-REC1:{vb1}")
        logger(f"VBRC-REC2:{vb2}")
        result.vb1_records.append(vb1)
        result.vb2_records.append(vb2)

    logger("END OF EXECUTION OF PROGRAM CBACT01C")
    return result


def _display_acct_record(acct: AccountRecord) -> list[str]:
    return [
        f"ACCT-ID                 :{acct.acct_id}",
        f"ACCT-ACTIVE-STATUS      :{acct.acct_active_status}",
        f"ACCT-CURR-BAL           :{acct.acct_curr_bal}",
        f"ACCT-CREDIT-LIMIT       :{acct.acct_credit_limit}",
        f"ACCT-CASH-CREDIT-LIMIT  :{acct.acct_cash_credit_limit}",
        f"ACCT-OPEN-DATE          :{acct.acct_open_date}",
        f"ACCT-EXPIRAION-DATE     :{acct.acct_expiration_date}",
        f"ACCT-REISSUE-DATE       :{acct.acct_reissue_date}",
        f"ACCT-CURR-CYC-CREDIT    :{acct.acct_curr_cyc_credit}",
        f"ACCT-CURR-CYC-DEBIT     :{acct.acct_curr_cyc_debit}",
        f"ACCT-GROUP-ID           :{acct.acct_group_id}",
        "-" * 49,
    ]


def _build_out_record(acct: AccountRecord) -> OutAcctRec:
    """1300-POPUL-ACCT-RECORD logic."""
    # MOVE ACCT-REISSUE-DATE TO CODATECN-INP-DATE; CALL 'COBDATFT'
    reissue_reformatted = _reformat_date(acct.acct_reissue_date, "2", "2")

    cyc_debit = acct.acct_curr_cyc_debit
    if cyc_debit == Decimal("0"):
        cyc_debit = Decimal("2525.00")  # COBOL: IF = 0 MOVE 2525.00

    return OutAcctRec(
        acct_id=acct.acct_id,
        acct_active_status=acct.acct_active_status,
        acct_curr_bal=acct.acct_curr_bal,
        acct_credit_limit=acct.acct_credit_limit,
        acct_cash_credit_limit=acct.acct_cash_credit_limit,
        acct_open_date=acct.acct_open_date,
        acct_expiration_date=acct.acct_expiration_date,
        acct_reissue_date=reissue_reformatted,
        acct_curr_cyc_credit=acct.acct_curr_cyc_credit,
        acct_curr_cyc_debit=cyc_debit,
        acct_group_id=acct.acct_group_id,
    )


def _build_arr_record(acct: AccountRecord) -> ArrArrayRec:
    """1400-POPUL-ARRAY-RECORD logic.

    ARR-ACCT-CURR-BAL(1) = ACCT-CURR-BAL, DEBIT(1) = 1005.00
    ARR-ACCT-CURR-BAL(2) = ACCT-CURR-BAL, DEBIT(2) = 1525.00
    ARR-ACCT-CURR-BAL(3) = -1025.00,      DEBIT(3) = -2500.00
    Elements 4 and 5 remain zero (INITIALIZE)
    """
    balances = [ArrAcctBal() for _ in range(5)]
    balances[0] = ArrAcctBal(acct.acct_curr_bal, Decimal("1005.00"))
    balances[1] = ArrAcctBal(acct.acct_curr_bal, Decimal("1525.00"))
    balances[2] = ArrAcctBal(Decimal("-1025.00"), Decimal("-2500.00"))
    return ArrArrayRec(acct_id=acct.acct_id, balances=balances)


def _build_vb_records(acct: AccountRecord) -> tuple[VbRec1, VbRec2]:
    """1500-POPUL-VBRC-RECORD logic."""
    vb1 = VbRec1(
        acct_id=acct.acct_id,
        acct_active_status=acct.acct_active_status,
    )
    # VB2: reissue year extracted from YYYY-MM-DD
    reissue_yyyy = acct.acct_reissue_date[:4] if acct.acct_reissue_date else ""
    vb2 = VbRec2(
        acct_id=acct.acct_id,
        acct_curr_bal=acct.acct_curr_bal,
        acct_credit_limit=acct.acct_credit_limit,
        acct_reissue_yyyy=reissue_yyyy,
    )
    return vb1, vb2


# ── run_vector adapter ───────────────────────────────────────────────────────

def _scenario_process_records():
    return [
        AccountRecord(
            acct_id=100000001,
            acct_active_status="Y",
            acct_curr_bal=Decimal("5000.00"),
            acct_credit_limit=Decimal("10000.00"),
            acct_cash_credit_limit=Decimal("3000.00"),
            acct_open_date="2020-03-15",
            acct_expiration_date="2029-12-31",
            acct_reissue_date="2025-03-15",
            acct_curr_cyc_credit=Decimal("1500.00"),
            acct_curr_cyc_debit=Decimal("0.00"),
            acct_group_id="GOLD",
        ),
        AccountRecord(
            acct_id=100000002,
            acct_active_status="Y",
            acct_curr_bal=Decimal("2500.50"),
            acct_credit_limit=Decimal("5000.00"),
            acct_cash_credit_limit=Decimal("1500.00"),
            acct_open_date="2021-07-01",
            acct_expiration_date="2028-06-30",
            acct_reissue_date="2024-07-01",
            acct_curr_cyc_credit=Decimal("800.00"),
            acct_curr_cyc_debit=Decimal("200.00"),
            acct_group_id="PLAT",
        ),
    ]


def _scenario_empty_input():
    return []


_SCENARIOS = {
    "PROCESS_RECORDS": _scenario_process_records,
    "EMPTY_INPUT": _scenario_empty_input,
}


def run_vector(inputs: dict) -> dict:
    """Adapter for the differential harness runner contract."""
    scenario_name = str(inputs.get("SCENARIO", "PROCESS_RECORDS")).upper()
    if scenario_name not in _SCENARIOS:
        return {"error": f"unknown scenario: {scenario_name!r}"}

    accounts = _SCENARIOS[scenario_name]()
    result = process_account_file(accounts, logger=lambda _: None)

    out: dict[str, str] = {
        "RECORDS_READ": str(result.records_read),
        "OUT_RECORDS": str(len(result.out_records)),
        "ARR_RECORDS": str(len(result.arr_records)),
        "VB1_RECORDS": str(len(result.vb1_records)),
        "VB2_RECORDS": str(len(result.vb2_records)),
    }
    for i, line in enumerate(result.display_lines):
        out[f"DISPLAY_{i}"] = line
    for i, orec in enumerate(result.out_records):
        cyc_debit_str = f"{orec.acct_curr_cyc_debit:.2f}"
        out[f"OUT_CYC_DEBIT_{i}"] = cyc_debit_str
    return out
