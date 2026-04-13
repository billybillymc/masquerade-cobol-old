"""
Reimplementation of CBSTM03A — CardDemo Account Statement Generator.

Function: Read transactions (via CBSTM03B subroutine), group by card/account,
and generate statements in both plain-text and HTML formats.

Notable COBOL features exercised (now expressed in Python):
  1. Control block addressing → objects/references
  2. ALTER and GO TO → conditional dispatch
  3. COMP and COMP-3 → int / Decimal
  4. 2-dimensional array → list[list]
  5. Call to subroutine → Cbstm03bFileManager.execute()
"""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from .carddemo_data import TranRecord, AccountRecord, CustomerRecord, CardXrefRecord
from .cbstm03b import Cbstm03bFileManager, M03BArea, OPER_OPEN, OPER_READ, OPER_CLOSE


# ── Statement line structures (from COBOL STATEMENT-LINES) ────────────────────

@dataclass
class StatementData:
    card_num: str = ""
    acct_id: int = 0
    customer: CustomerRecord | None = None
    account: AccountRecord | None = None
    transactions: list[TranRecord] = field(default_factory=list)
    total_amount: Decimal = Decimal("0.00")


@dataclass
class StatementResult:
    plain_text_lines: list[str] = field(default_factory=list)
    html_lines: list[str] = field(default_factory=list)
    statements_produced: int = 0
    total_records_read: int = 0


# ── Repository interfaces ──────────────────────────────────────────────────────

class XrefRepository:
    def __init__(self, xrefs: dict[str, CardXrefRecord]):
        self._by_card = xrefs

    def find_by_card(self, card_num: str) -> CardXrefRecord | None:
        return self._by_card.get(card_num)


class AccountRepository:
    def __init__(self, accounts: dict[int, AccountRecord]):
        self._accounts = accounts

    def find(self, acct_id: int) -> AccountRecord | None:
        return self._accounts.get(acct_id)


class CustomerRepository:
    def __init__(self, customers: dict[int, CustomerRecord]):
        self._customers = customers

    def find(self, cust_id: int) -> CustomerRecord | None:
        return self._customers.get(cust_id)


# ── Core processing ───────────────────────────────────────────────────────────

def generate_statements(
    file_mgr: Cbstm03bFileManager,
    xref_repo: XrefRepository,
    account_repo: AccountRepository,
    customer_repo: CustomerRepository,
    logger: Callable[[str], None] = print,
) -> StatementResult:
    """Generate account statements — mirrors CBSTM03A PROCEDURE DIVISION."""
    result = StatementResult()

    # Group transactions by card number
    area = M03BArea(dd="TRNXFILE")
    area.oper = OPER_OPEN
    file_mgr.execute(area)

    transactions_by_card: dict[str, list[TranRecord]] = {}
    save_card = ""

    while True:
        area.oper = OPER_READ
        file_mgr.execute(area)
        if area.rc == "10":  # EOF
            break
        result.total_records_read += 1

        # Deserialize from fldt
        tran = _parse_fldt(area.fldt)
        if not tran:
            continue

        if tran.tran_card_num not in transactions_by_card:
            transactions_by_card[tran.tran_card_num] = []
        transactions_by_card[tran.tran_card_num].append(tran)

    area.oper = OPER_CLOSE
    file_mgr.execute(area)

    # Generate a statement per card number
    for card_num, trans_list in transactions_by_card.items():
        stmt_data = _build_statement_data(
            card_num, trans_list, xref_repo, account_repo, customer_repo
        )
        plain_lines = _format_plain_text(stmt_data)
        html_lines = _format_html(stmt_data)
        result.plain_text_lines.extend(plain_lines)
        result.html_lines.extend(html_lines)
        result.statements_produced += 1

    return result


def _parse_fldt(fldt: str) -> TranRecord | None:
    """Parse serialized FLDT back to TranRecord."""
    if not fldt or len(fldt) < 16:
        return None
    try:
        from decimal import Decimal
        return TranRecord(
            tran_id=fldt[0:16].strip(),
            tran_type_cd=fldt[16:18].strip(),
            tran_cat_cd=int(fldt[18:22].strip() or 0),
            tran_source=fldt[22:32].strip(),
            tran_desc=fldt[32:132].strip(),
            tran_amt=Decimal(fldt[132:146].strip() or "0"),
            tran_merchant_id=int(fldt[146:155].strip() or 0),
            tran_merchant_name=fldt[155:205].strip(),
            tran_merchant_city=fldt[205:255].strip(),
            tran_merchant_zip=fldt[255:265].strip(),
            tran_card_num=fldt[265:281].strip(),
            tran_orig_ts=fldt[281:307].strip(),
            tran_proc_ts=fldt[307:333].strip(),
        )
    except Exception:
        return None


def _build_statement_data(
    card_num: str,
    trans: list[TranRecord],
    xref_repo: XrefRepository,
    account_repo: AccountRepository,
    customer_repo: CustomerRepository,
) -> StatementData:
    stmt = StatementData(card_num=card_num)
    xref = xref_repo.find_by_card(card_num)
    if xref:
        stmt.acct_id = xref.xref_acct_id
        stmt.account = account_repo.find(xref.xref_acct_id)
        stmt.customer = customer_repo.find(xref.xref_cust_id)
    stmt.transactions = trans
    stmt.total_amount = sum((t.tran_amt for t in trans), Decimal("0.00"))
    return stmt


def _format_plain_text(stmt: StatementData) -> list[str]:
    """Generate plain text statement lines (80 chars)."""
    lines: list[str] = []
    lines.append("*" * 31 + "START OF STATEMENT" + "*" * 31)

    cust = stmt.customer
    if cust:
        name = f"{cust.cust_first_name.strip()} {cust.cust_last_name.strip()}"
        lines.append(f"{name:<75}     ")
        lines.append(f"{cust.cust_addr_line_1:<50}              ")
        lines.append(f"{cust.cust_addr_line_2:<50}              ")
        addr3 = f"{cust.cust_addr_state_cd} {cust.cust_addr_zip}"
        lines.append(f"{addr3:<80}")
    else:
        lines.append(f"Card: {stmt.card_num}")

    lines.append("-" * 80)
    lines.append(" " * 33 + "Basic Details" + " " * 34)
    lines.append(f"Account ID         :{stmt.acct_id!s:<20}{' ' * 40}")

    acct = stmt.account
    if acct:
        lines.append(f"Current Balance    :{float(acct.acct_curr_bal):9.2f}       {' ' * 40}")
        fico = cust.cust_fico_credit_score if cust else 0
        lines.append(f"FICO Score         :{fico!s:<20}{' ' * 40}")

    lines.append("-" * 80)
    lines.append(" " * 30 + "TRANSACTION SUMMARY " + " " * 30)
    lines.append("-" * 80)
    lines.append(f"{'Tran ID':<16}{'Tran Details':<51}{'  Tran Amount':>13}")

    for tran in stmt.transactions:
        detail = f"{tran.tran_desc[:49]}"
        lines.append(
            f"{tran.tran_id:<16} {detail:<49}${float(tran.tran_amt):>9.2f}-"
        )

    lines.append(f"{'Total EXP:':<10}{' ' * 56}${float(stmt.total_amount):>9.2f}-")
    lines.append("*" * 32 + "END OF STATEMENT" + "*" * 32)
    return lines


def _format_html(stmt: StatementData) -> list[str]:
    """Generate HTML statement."""
    lines: list[str] = []
    lines.append("<!DOCTYPE html>")
    lines.append("<html><head><title>CardDemo Statement</title></head><body>")
    lines.append("<table border='1'>")
    lines.append(f"<tr><th>Card Number</th><td>{stmt.card_num}</td></tr>")
    lines.append(f"<tr><th>Account ID</th><td>{stmt.acct_id}</td></tr>")

    if stmt.account:
        lines.append(f"<tr><th>Balance</th><td>${float(stmt.account.acct_curr_bal):.2f}</td></tr>")

    lines.append("</table>")
    lines.append("<table border='1'><tr><th>Tran ID</th><th>Description</th><th>Amount</th></tr>")
    for tran in stmt.transactions:
        lines.append(
            f"<tr><td>{tran.tran_id}</td>"
            f"<td>{tran.tran_desc[:60]}</td>"
            f"<td>${float(tran.tran_amt):.2f}</td></tr>"
        )
    lines.append(f"<tr><td colspan='2'><b>TOTAL</b></td><td>${float(stmt.total_amount):.2f}</td></tr>")
    lines.append("</table></body></html>")
    return lines


# ── run_vector adapter ───────────────────────────────────────────────────────

def _scenario_process_records():
    from .carddemo_data import TranRecord as TR, CardXrefRecord as CXR
    trans = [
        TR(tran_id="TRN0000000000001", tran_type_cd="01", tran_cat_cd=1,
           tran_desc="Widget purchase", tran_amt=Decimal("150.25"),
           tran_card_num="4111000000001111",
           tran_orig_ts="2026-04-01-12.00.00.000000",
           tran_proc_ts="2026-04-01-12.00.00.000000"),
        TR(tran_id="TRN0000000000002", tran_type_cd="01", tran_cat_cd=1,
           tran_desc="Gadget purchase", tran_amt=Decimal("75.50"),
           tran_card_num="4111000000001111",
           tran_orig_ts="2026-04-05-14.30.00.000000",
           tran_proc_ts="2026-04-05-14.30.00.000000"),
    ]
    xrefs = {
        "4111000000001111": CXR(xref_card_num="4111000000001111",
                                xref_cust_id=1, xref_acct_id=100000001),
    }
    accounts = {
        100000001: AccountRecord(
            acct_id=100000001, acct_active_status="Y",
            acct_curr_bal=Decimal("5000.00"), acct_credit_limit=Decimal("10000.00"),
        ),
    }
    customers = {
        1: CustomerRecord(
            cust_id=1, cust_first_name="JOHN", cust_last_name="DOE",
            cust_addr_line_1="123 MAIN ST", cust_addr_line_2="APT 4B",
            cust_addr_state_cd="NY", cust_addr_zip="10001",
            cust_fico_credit_score=750,
        ),
    }
    return trans, xrefs, accounts, customers


def _scenario_empty_input():
    return [], {}, {}, {}


_CBSTM03A_SCENARIOS = {
    "PROCESS_RECORDS": _scenario_process_records,
    "EMPTY_INPUT": _scenario_empty_input,
}


def run_vector(inputs: dict) -> dict:
    """Adapter for the differential harness runner contract."""
    scenario_name = str(inputs.get("SCENARIO", "PROCESS_RECORDS")).upper()
    if scenario_name not in _CBSTM03A_SCENARIOS:
        return {"error": f"unknown scenario: {scenario_name!r}"}

    trans, xrefs, accounts, customers = _CBSTM03A_SCENARIOS[scenario_name]()
    file_mgr = Cbstm03bFileManager([
        TranRecord(
            tran_id=t.tran_id, tran_type_cd=t.tran_type_cd,
            tran_cat_cd=t.tran_cat_cd, tran_source=t.tran_source,
            tran_desc=t.tran_desc, tran_amt=t.tran_amt,
            tran_merchant_id=t.tran_merchant_id,
            tran_merchant_name=t.tran_merchant_name,
            tran_merchant_city=t.tran_merchant_city,
            tran_merchant_zip=t.tran_merchant_zip,
            tran_card_num=t.tran_card_num,
            tran_orig_ts=t.tran_orig_ts,
            tran_proc_ts=t.tran_proc_ts,
        ) for t in trans
    ])
    xref_repo = XrefRepository(xrefs)
    account_repo = AccountRepository(accounts)
    customer_repo = CustomerRepository(customers)

    result = generate_statements(file_mgr, xref_repo, account_repo, customer_repo,
                                  logger=lambda _: None)

    out: dict[str, str] = {
        "STATEMENTS_PRODUCED": str(result.statements_produced),
        "TOTAL_RECORDS_READ": str(result.total_records_read),
        "PLAIN_TEXT_LINE_COUNT": str(len(result.plain_text_lines)),
        "HTML_LINE_COUNT": str(len(result.html_lines)),
    }
    for i, line in enumerate(result.plain_text_lines):
        out[f"PLAIN_{i}"] = line
    for i, line in enumerate(result.html_lines):
        out[f"HTML_{i}"] = line
    return out
