"""
Tests for CardDemo COBOL reimplementations.

Covers business logic of all new Python modules:
  - cocrdslc, cocrdupc (card view/update)
  - cotrn00c, cotrn01c, cotrn02c (transaction list/view/add)
  - cobil00c (bill payment)
  - corpt00c (report submission)
  - coactupc (account update)
  - cbexport, cbimport (batch export/import)
"""

import sys
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reimpl.python.carddemo_data import (
    CarddemoCommarea, AccountRecord, CustomerRecord,
    CardRecord, CardXrefRecord, TranRecord,
    DFHENTER, DFHPF3, DFHPF4, DFHPF5, DFHPF7, DFHPF8, DFHPF12,
)


# ─── Fixtures / helpers ──────────────────────────────────────────────────────

def _commarea(context: int = 1, from_pgm: str = "COMEN01C") -> CarddemoCommarea:
    ca = CarddemoCommarea()
    ca.cdemo_pgm_context = context
    ca.cdemo_from_program = from_pgm
    ca.cdemo_user_type = "R"
    return ca


def _card(num="1234567890123456", acct=1001, cvv=123, name="JOHN DOE", exp="2027-12-31", status="Y"):
    return CardRecord(
        card_num=num, card_acct_id=acct, card_cvv_cd=cvv,
        card_embossed_name=name, card_expiration_date=exp, card_active_status=status,
    )


def _acct(acct_id=1001, bal="500.00", limit="5000.00", status="Y"):
    return AccountRecord(
        acct_id=acct_id, acct_active_status=status,
        acct_curr_bal=Decimal(bal), acct_credit_limit=Decimal(limit),
        acct_cash_credit_limit=Decimal("1000.00"),
    )


def _cust(cust_id=9001, first="Jane", last="Doe"):
    return CustomerRecord(
        cust_id=cust_id, cust_first_name=first, cust_last_name=last,
    )


def _xref(card_num="1234567890123456", cust_id=9001, acct_id=1001):
    return CardXrefRecord(
        xref_card_num=card_num, xref_cust_id=cust_id, xref_acct_id=acct_id,
    )


def _tran(tran_id="0000000000000001", amt="99.99", card="1234567890123456"):
    return TranRecord(
        tran_id=tran_id, tran_type_cd="01", tran_cat_cd=1,
        tran_source="POS TERM", tran_desc="Test transaction",
        tran_amt=Decimal(amt), tran_card_num=card,
        tran_merchant_id=42, tran_merchant_name="STORE",
        tran_merchant_city="NYC", tran_merchant_zip="10001",
        tran_orig_ts="2024-01-15", tran_proc_ts="2024-01-15",
    )


# ─── COCRDSLC — card view ────────────────────────────────────────────────────

class TestCocrdslc:
    def _setup(self):
        from reimpl.python.cocrdslc import (
            CardRepository, AccountRepository, XrefRepository,
            CustomerRepository, process_card_view,
        )
        card = _card()
        acct = _acct()
        cust = _cust()
        xref = _xref()
        card_repo = CardRepository({"1234567890123456": card})
        acct_repo = AccountRepository({1001: acct})
        xref_repo = XrefRepository({"1234567890123456": xref})
        cust_repo = CustomerRepository({9001: cust})
        return process_card_view, card_repo, acct_repo, xref_repo, cust_repo

    def test_eibcalen_zero_redirects_to_signon(self):
        fn, cr, ar, xr, cus = self._setup()
        result = fn(0, DFHENTER, _commarea(), "", cr, ar, xr, cus)
        assert result.return_to_prev
        assert result.xctl_program == "COSGN00C"

    def test_pf3_returns_to_caller(self):
        fn, cr, ar, xr, cus = self._setup()
        result = fn(100, DFHPF3, _commarea(), "", cr, ar, xr, cus)
        assert result.return_to_prev
        assert result.xctl_program == "COMEN01C"

    def test_lookup_existing_card(self):
        fn, cr, ar, xr, cus = self._setup()
        result = fn(100, DFHENTER, _commarea(), "1234567890123456", cr, ar, xr, cus)
        assert result.card_data is not None
        assert result.card_data.card_num == "1234567890123456"
        assert result.card_data.cust_name == "Jane Doe"
        assert not result.error

    def test_lookup_nonexistent_card_sets_error(self):
        fn, cr, ar, xr, cus = self._setup()
        result = fn(100, DFHENTER, _commarea(), "9999999999999999", cr, ar, xr, cus)
        assert result.error
        assert result.card_data is None

    def test_empty_card_num_sets_error(self):
        fn, cr, ar, xr, cus = self._setup()
        result = fn(100, DFHENTER, _commarea(), "   ", cr, ar, xr, cus)
        assert result.error


# ─── COCRDUPC — card update ──────────────────────────────────────────────────

class TestCocrdupc:
    def _setup(self):
        from reimpl.python.cocrdupc import CardRepository, process_card_update, CardUpdateInput
        card = _card()
        repo = CardRepository({"1234567890123456": card})
        return process_card_update, repo, CardUpdateInput

    def test_pf3_exits(self):
        fn, repo, Inp = self._setup()
        result = fn(100, DFHPF3, _commarea(), Inp(), repo)
        assert result.return_to_prev

    def test_pf5_saves_updated_name(self):
        fn, repo, Inp = self._setup()
        inp = Inp(card_num="1234567890123456", embossed_name="NEW NAME")
        ca = _commarea()
        ca.cdemo_pgm_context = 1
        result = fn(100, DFHPF5, ca, inp, repo)
        assert result.success
        assert result.card_found.card_embossed_name == "NEW NAME"

    def test_pf5_nonexistent_card_errors(self):
        fn, repo, Inp = self._setup()
        inp = Inp(card_num="9999999999999999")
        ca = _commarea()
        ca.cdemo_pgm_context = 1
        result = fn(100, DFHPF5, ca, inp, repo)
        assert result.error
        assert not result.success

    def test_invalid_cvv_errors(self):
        fn, repo, Inp = self._setup()
        inp = Inp(card_num="1234567890123456", cvv_cd="ABC")
        ca = _commarea()
        ca.cdemo_pgm_context = 1
        result = fn(100, DFHPF5, ca, inp, repo)
        assert result.error


# ─── COTRN00C — transaction list ─────────────────────────────────────────────

class TestCotrn00c:
    def _setup(self):
        from reimpl.python.cotrn00c import TranRepository, process_tran_list
        trans = [_tran(f"{i:016d}") for i in range(1, 16)]
        repo = TranRepository(trans)
        return process_tran_list, repo

    def test_eibcalen_zero_redirects(self):
        fn, repo = self._setup()
        result = fn(0, DFHENTER, _commarea(), repo)
        assert result.return_to_prev

    def test_first_page_has_10_rows(self):
        fn, repo = self._setup()
        ca = _commarea(context=0)
        result = fn(100, DFHENTER, ca, repo)
        assert len(result.rows) == 10
        assert result.has_next_page
        assert not result.has_prev_page

    def test_pf8_advances_page(self):
        fn, repo = self._setup()
        ca = _commarea()
        result = fn(100, DFHPF8, ca, repo, page_num=1)
        assert result.page_num == 2
        assert len(result.rows) == 5

    def test_pf7_at_page1_stays_on_page1(self):
        fn, repo = self._setup()
        ca = _commarea()
        result = fn(100, DFHPF7, ca, repo, page_num=1)
        assert result.page_num == 1

    def test_pf3_returns_to_caller(self):
        fn, repo = self._setup()
        result = fn(100, DFHPF3, _commarea(), repo)
        assert result.return_to_prev
        assert result.xctl_program == "COMEN01C"

    def test_row_selection_routes_to_view(self):
        fn, repo = self._setup()
        ca = _commarea()
        rows = [("S", "0000000000000001")]
        result = fn(100, DFHENTER, ca, repo, page_num=1, selected_rows=rows)
        assert result.xctl_program == "COTRN01C"
        assert result.selected_tran_id == "0000000000000001"


# ─── COTRN01C — transaction view ────────────────────────────────────────────

class TestCotrn01c:
    def _setup(self):
        from reimpl.python.cotrn01c import TranRepository, process_tran_view
        tran = _tran()
        repo = TranRepository({"0000000000000001": tran})
        return process_tran_view, repo

    def test_lookup_existing_tran(self):
        fn, repo = self._setup()
        result = fn(100, DFHENTER, _commarea(), "0000000000000001", repo)
        assert result.tran_record is not None
        assert result.tran_record.tran_id == "0000000000000001"

    def test_empty_tran_id_errors(self):
        fn, repo = self._setup()
        result = fn(100, DFHENTER, _commarea(), "", repo)
        assert result.error

    def test_not_found_errors(self):
        fn, repo = self._setup()
        result = fn(100, DFHENTER, _commarea(), "9999999999999999", repo)
        assert result.error
        assert "NOT found" in result.message

    def test_pf4_clears_screen(self):
        fn, repo = self._setup()
        result = fn(100, DFHPF4, _commarea(), "", repo)
        assert result.cleared

    def test_pf5_returns_to_list(self):
        fn, repo = self._setup()
        result = fn(100, DFHPF5, _commarea(), "", repo)
        assert result.xctl_program == "COTRN00C"


# ─── COTRN02C — transaction add ──────────────────────────────────────────────

class TestCotrn02c:
    def _setup(self):
        from reimpl.python.cotrn02c import (
            TranRepository, XrefRepository, process_tran_add, TranAddInput,
        )
        xref = _xref()
        xref_repo = XrefRepository([xref])
        trans = [_tran()]
        tran_repo = TranRepository(trans)
        return process_tran_add, tran_repo, xref_repo, TranAddInput

    def _valid_input(self, Inp):
        return Inp(
            card_num="1234567890123456",
            type_cd="01",
            cat_cd="1",
            source="POS TERM",
            desc="Test purchase",
            amount="+00010000.00",
            orig_date="2024-03-15",
            proc_date="2024-03-15",
            merchant_id="123456789",
            merchant_name="STORE NAME",
            merchant_city="ANYTOWN",
            merchant_zip="12345",
            confirm="Y",
        )

    def test_valid_transaction_added_on_confirm_y(self):
        fn, tr, xr, Inp = self._setup()
        inp = self._valid_input(Inp)
        ca = _commarea()
        result = fn(100, DFHENTER, ca, inp, tr, xr)
        assert result.success
        assert result.tran_record is not None

    def test_missing_card_errors(self):
        fn, tr, xr, Inp = self._setup()
        inp = Inp(type_cd="01", cat_cd="1", source="POS",
                  desc="X", amount="+00010000.00",
                  orig_date="2024-03-15", proc_date="2024-03-15",
                  merchant_id="123", merchant_name="S", merchant_city="C",
                  merchant_zip="12345", confirm="Y")
        ca = _commarea()
        result = fn(100, DFHENTER, ca, inp, tr, xr)
        assert result.error

    def test_no_confirm_shows_message(self):
        fn, tr, xr, Inp = self._setup()
        inp = self._valid_input(Inp)
        inp.confirm = ""
        ca = _commarea()
        result = fn(100, DFHENTER, ca, inp, tr, xr)
        assert result.error
        assert "Confirm" in result.message

    def test_invalid_amount_format_errors(self):
        fn, tr, xr, Inp = self._setup()
        inp = self._valid_input(Inp)
        inp.amount = "999.99"  # missing sign
        ca = _commarea()
        result = fn(100, DFHENTER, ca, inp, tr, xr)
        assert result.error

    def test_invalid_date_errors(self):
        fn, tr, xr, Inp = self._setup()
        inp = self._valid_input(Inp)
        inp.orig_date = "2024-13-01"  # invalid month
        ca = _commarea()
        result = fn(100, DFHENTER, ca, inp, tr, xr)
        assert result.error


# ─── COBIL00C — bill payment ─────────────────────────────────────────────────

class TestCobil00c:
    def _setup(self):
        from reimpl.python.cobil00c import (
            AccountRepository, XrefRepository, TranRepository, process_bill_pay,
        )
        acct = _acct()
        xref = _xref()
        trans: list = []
        acct_repo = AccountRepository({1001: acct})
        xref_repo = XrefRepository({1001: xref})
        tran_repo = TranRepository(trans)
        return process_bill_pay, acct_repo, xref_repo, tran_repo

    def test_empty_acct_id_errors(self):
        fn, ar, xr, tr = self._setup()
        result = fn(100, DFHENTER, _commarea(), "", "", ar, xr, tr)
        assert result.error

    def test_acct_with_zero_balance_rejected(self):
        fn, ar, xr, tr = self._setup()
        ar._accounts[1001].acct_curr_bal = Decimal("0.00")
        result = fn(100, DFHENTER, _commarea(), "1001", "", ar, xr, tr)
        assert result.error
        assert "nothing to pay" in result.message

    def test_confirm_y_creates_transaction_and_zeroes_balance(self):
        fn, ar, xr, tr = self._setup()
        result = fn(100, DFHENTER, _commarea(), "1001", "Y", ar, xr, tr)
        assert result.success
        assert result.tran_record is not None
        assert ar._accounts[1001].acct_curr_bal == Decimal("0.00")

    def test_no_confirm_prompts_user(self):
        fn, ar, xr, tr = self._setup()
        result = fn(100, DFHENTER, _commarea(), "1001", "", ar, xr, tr)
        assert not result.success
        assert "Confirm" in result.message

    def test_confirm_n_clears_screen(self):
        fn, ar, xr, tr = self._setup()
        result = fn(100, DFHENTER, _commarea(), "1001", "N", ar, xr, tr)
        assert result.cleared


# ─── CORPT00C — report submission ────────────────────────────────────────────

class TestCorpt00c:
    def _setup(self):
        from reimpl.python.corpt00c import process_report_screen
        return process_report_screen

    def test_monthly_report_calculates_dates(self):
        fn = self._setup()
        today = date(2024, 3, 15)
        result = fn(100, DFHENTER, _commarea(), "monthly", today=today)
        assert not result.error
        assert result.job_request.start_date == "2024-03-01"
        assert result.job_request.end_date == "2024-03-31"
        assert result.job_request.report_name == "Monthly"

    def test_yearly_report_full_year(self):
        fn = self._setup()
        today = date(2024, 6, 1)
        result = fn(100, DFHENTER, _commarea(), "yearly", today=today)
        assert result.job_request.start_date == "2024-01-01"
        assert result.job_request.end_date == "2024-12-31"

    def test_custom_report_with_valid_dates(self):
        fn = self._setup()
        result = fn(100, DFHENTER, _commarea(), "custom",
                    start_mm="01", start_dd="01", start_yyyy="2024",
                    end_mm="03", end_dd="31", end_yyyy="2024")
        assert not result.error
        assert result.job_request.start_date == "2024-01-01"
        assert result.job_request.end_date == "2024-03-31"

    def test_custom_report_missing_fields_errors(self):
        fn = self._setup()
        result = fn(100, DFHENTER, _commarea(), "custom",
                    start_mm="", start_dd="01", start_yyyy="2024",
                    end_mm="03", end_dd="31", end_yyyy="2024")
        assert result.error

    def test_no_report_type_errors(self):
        fn = self._setup()
        result = fn(100, DFHENTER, _commarea(), "")
        assert result.error

    def test_pf3_exits(self):
        fn = self._setup()
        result = fn(100, DFHPF3, _commarea(), "")
        assert result.return_to_prev
        assert result.xctl_program == "COMEN01C"


# ─── COACTUPC — account update ───────────────────────────────────────────────

class TestCoactupc:
    def _setup(self):
        from reimpl.python.coactupc import (
            AccountRepository, CustomerRepository, XrefRepository,
            process_account_update, AccountUpdateInput,
        )
        acct = _acct()
        cust = _cust()
        xref = _xref()
        acct_repo = AccountRepository({1001: acct})
        cust_repo = CustomerRepository({9001: cust})
        xref_repo = XrefRepository([xref])
        return process_account_update, acct_repo, cust_repo, xref_repo, AccountUpdateInput

    def test_initial_display_unknown_acct_errors(self):
        fn, ar, cr, xr, Inp = self._setup()
        inp = Inp(acct_id="9999")
        result = fn(100, DFHENTER, _commarea(), inp, ar, cr, xr)
        assert result.error

    def test_initial_display_valid_acct_shows_details(self):
        fn, ar, cr, xr, Inp = self._setup()
        inp = Inp(acct_id="1001")
        result = fn(100, DFHENTER, _commarea(), inp, ar, cr, xr)
        assert result.action == "S"
        assert result.acct_record is not None
        assert result.cust_record is not None

    def test_pf3_exits(self):
        fn, ar, cr, xr, Inp = self._setup()
        inp = Inp()
        result = fn(100, DFHPF3, _commarea(), inp, ar, cr, xr)
        assert result.return_to_prev

    def test_commit_updates_account_balance(self):
        fn, ar, cr, xr, Inp = self._setup()
        acct = ar._accounts[1001]
        cust = cr._customers[9001]
        inp = Inp(
            acct_id="1001",
            active_status="Y",
            credit_limit="9000.00",
            cash_credit_limit="1000.00",
            last_name="Smith",
        )
        result = fn(100, DFHPF5, _commarea(), inp, ar, cr, xr,
                    current_action="N", old_acct=acct, old_cust=cust)
        assert result.success
        assert ar._accounts[1001].acct_credit_limit == Decimal("9000.00")

    def test_invalid_status_causes_error(self):
        fn, ar, cr, xr, Inp = self._setup()
        acct = ar._accounts[1001]
        cust = cr._customers[9001]
        inp = Inp(acct_id="1001", active_status="X",
                  credit_limit="5000.00", cash_credit_limit="1000.00",
                  last_name="Doe")
        result = fn(100, DFHENTER, _commarea(), inp, ar, cr, xr,
                    current_action="S", old_acct=acct, old_cust=cust)
        assert result.error


# ─── CBEXPORT / CBIMPORT — batch round-trip ─────────────────────────────────

class TestCbexportImport:
    def _build_data(self):
        customers = [_cust(9001), _cust(9002, "Bob", "Smith")]
        accounts = [_acct(1001), _acct(1002, bal="250.00")]
        xrefs = [_xref("1234567890123456", 9001, 1001),
                 _xref("9876543210987654", 9002, 1002)]
        trans = [_tran("0000000000000001"), _tran("0000000000000002", "49.99")]
        cards = [_card(), _card("9876543210987654", 1002)]
        return customers, accounts, xrefs, trans, cards

    def test_export_counts_match_input(self):
        from reimpl.python.cbexport import run_export
        custs, accts, xrefs, trans, cards = self._build_data()
        result = run_export(custs, accts, xrefs, trans, cards)
        assert result.stats.customers == 2
        assert result.stats.accounts == 2
        assert result.stats.xrefs == 2
        assert result.stats.transactions == 2
        assert result.stats.cards == 2
        assert result.stats.total == 10
        assert not result.abended

    def test_export_records_have_sequence_numbers(self):
        from reimpl.python.cbexport import run_export
        custs, accts, xrefs, trans, cards = self._build_data()
        result = run_export(custs, accts, xrefs, trans, cards)
        seq_nums = [r.seq_num for r in result.records]
        assert seq_nums == list(range(1, 11))

    def test_import_round_trip_preserves_all_records(self):
        from reimpl.python.cbexport import run_export
        from reimpl.python.cbimport import run_import
        custs, accts, xrefs, trans, cards = self._build_data()
        export_result = run_export(custs, accts, xrefs, trans, cards)
        import_result = run_import(export_result.records)
        assert import_result.stats.customers == 2
        assert import_result.stats.accounts == 2
        assert import_result.stats.xrefs == 2
        assert import_result.stats.transactions == 2
        assert import_result.stats.cards == 2
        assert import_result.stats.errors == 0

    def test_import_unknown_type_logged_as_error(self):
        from reimpl.python.cbexport import ExportRecord
        from reimpl.python.cbimport import run_import
        bad = ExportRecord(seq_num=1, rec_type="Z", timestamp="", data=None)
        result = run_import([bad])
        assert result.stats.errors == 1
        assert len(result.errors) == 1

    def test_export_log_contains_summary(self):
        from reimpl.python.cbexport import run_export
        custs, accts, xrefs, trans, cards = self._build_data()
        result = run_export(custs, accts, xrefs, trans, cards)
        full_log = "\n".join(result.log)
        assert "Total records exported" in full_log
        assert "Export complete" in full_log


# ─── COCRDLIC — card list ────────────────────────────────────────────────────

class TestCocrdlic:
    def _setup(self):
        from reimpl.python.cocrdlic import CardRepository, process_card_list
        cards = [_card(f"{i:016d}", 1001) for i in range(1, 10)]
        repo = CardRepository(cards)
        return process_card_list, repo

    def test_first_page_has_7_rows(self):
        fn, repo = self._setup()
        ca = _commarea(context=0)
        result = fn(100, DFHENTER, ca, repo)
        assert len(result.rows) == 7
        assert result.has_next_page

    def test_pf8_loads_next_page(self):
        fn, repo = self._setup()
        ca = _commarea()
        result = fn(100, DFHPF8, ca, repo, page_num=1)
        assert result.page_num == 2
        assert len(result.rows) == 2

    def test_selection_s_routes_to_cocrdslc(self):
        fn, repo = self._setup()
        ca = _commarea()
        rows = [("S", "0000000000000001")]
        result = fn(100, DFHENTER, ca, repo, page_num=1, selected_rows=rows)
        assert result.xctl_program == "COCRDSLC"

    def test_selection_u_routes_to_cocrdupc(self):
        fn, repo = self._setup()
        ca = _commarea()
        rows = [("U", "0000000000000001")]
        result = fn(100, DFHENTER, ca, repo, page_num=1, selected_rows=rows)
        assert result.xctl_program == "COCRDUPC"

    def test_multiple_selections_errors(self):
        fn, repo = self._setup()
        ca = _commarea()
        rows = [("S", "0000000000000001"), ("S", "0000000000000002")]
        result = fn(100, DFHENTER, ca, repo, page_num=1, selected_rows=rows)
        assert result.error


# ─── Edge-case / cross-cutting concerns ─────────────────────────────────────

class TestEdgeCases:
    def test_bill_pay_nonexistent_account(self):
        from reimpl.python.cobil00c import (
            AccountRepository, XrefRepository, TranRepository, process_bill_pay,
        )
        ar = AccountRepository({})
        xr = XrefRepository({})
        tr = TranRepository([])
        result = process_bill_pay(100, DFHENTER, _commarea(), "9999", "Y", ar, xr, tr)
        assert result.error

    def test_tran_add_increments_id(self):
        from reimpl.python.cotrn02c import TranRepository
        repo = TranRepository([_tran("0000000000000005")])
        assert repo.next_id() == "0000000000000006"

    def test_tran_add_empty_repo_starts_at_1(self):
        from reimpl.python.cotrn02c import TranRepository
        repo = TranRepository([])
        assert repo.next_id() == "0000000000000001"

    def test_card_update_pf12_routes_to_list(self):
        from reimpl.python.cocrdupc import CardRepository, process_card_update, CardUpdateInput
        repo = CardRepository({"1234567890123456": _card()})
        ca = _commarea()
        ca.cdemo_pgm_context = 1
        inp = CardUpdateInput(card_num="1234567890123456")
        result = process_card_update(100, DFHPF12, ca, inp, repo)
        assert result.xctl_program == "COCRDLIC"
