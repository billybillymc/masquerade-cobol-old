"""
Differential tests for CBSA DBCRFUN reimplementation.

Verifies that the Python reimplementation of DBCRFUN produces outputs
matching the COBOL business logic for all decision paths:

  - Credit to savings account (success)
  - Debit from savings with sufficient funds (success)
  - Debit from savings with insufficient funds (fail code 3)
  - Debit from mortgage account via payment (fail code 4)
  - Credit to mortgage account via payment (fail code 4)
  - Account not found (fail code 1)
  - Debit via teller with insufficient funds (allowed -- no fail)
  - PROCTRAN insert failure triggers rollback (fail code 2)
  - Transaction type classification: DEB / CRE / PDR / PCR

Uses the differential harness (TestVector / run_vectors) for
field-by-field equivalence checking.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reimpl"))

from differential_harness import TestVector, run_vectors, render_report_text
from reimpl.cbsa_dbcrfun import (
    Account,
    DebitCreditRequest,
    DebitCreditResult,
    InMemoryAccountRepository,
    InMemoryProcTranRepository,
    FailingProcTranRepository,
    process_debit_credit,
    SORTCODE,
    FACILTYPE_PAYMENT,
)


# -- Fixtures -----------------------------------------------------------------

def _make_savings_account(
    acc_no: str = "12345678",
    avail_bal: Decimal = Decimal("1000.00"),
    actual_bal: Decimal = Decimal("1000.00"),
) -> Account:
    return Account(
        eyecatcher="ACCT",
        cust_no="0000000001",
        sortcode=SORTCODE,
        acc_no=acc_no,
        acc_type="SAVING",
        int_rate=Decimal("1.50"),
        opened="01012020",
        overdraft_lim=0,
        last_stmt="01012026",
        next_stmt="01042026",
        avail_bal=avail_bal,
        actual_bal=actual_bal,
    )


def _make_mortgage_account(acc_no: str = "99990001") -> Account:
    return Account(
        eyecatcher="ACCT",
        cust_no="0000000002",
        sortcode=SORTCODE,
        acc_no=acc_no,
        acc_type="MORTGAGE",
        int_rate=Decimal("3.25"),
        opened="15062018",
        overdraft_lim=0,
        last_stmt="01012026",
        next_stmt="01042026",
        avail_bal=Decimal("250000.00"),
        actual_bal=Decimal("250000.00"),
    )


def _make_loan_account(acc_no: str = "99990002") -> Account:
    return Account(
        eyecatcher="ACCT",
        cust_no="0000000003",
        sortcode=SORTCODE,
        acc_no=acc_no,
        acc_type="LOAN",
        int_rate=Decimal("5.00"),
        opened="01032021",
        overdraft_lim=0,
        last_stmt="01012026",
        next_stmt="01042026",
        avail_bal=Decimal("10000.00"),
        actual_bal=Decimal("10000.00"),
    )


def _build_repos(*accounts: Account):
    """Create in-memory repos pre-loaded with the given accounts."""
    acct_repo = InMemoryAccountRepository()
    for a in accounts:
        acct_repo.add(a)
    proctran_repo = InMemoryProcTranRepository()
    return acct_repo, proctran_repo


def _run_scenario(request, acct_repo, proctran_repo) -> dict:
    """Run the Python reimplementation and return comparable output fields."""
    result = process_debit_credit(request, acct_repo, proctran_repo)
    return {
        "SUCCESS": "Y" if result.success else "N",
        "FAIL_CODE": result.fail_code,
        "AVAIL_BAL": str(result.avail_bal),
        "ACTUAL_BAL": str(result.actual_bal),
    }


# -- Scenario definitions -----------------------------------------------------
# Each scenario specifies:
#   - COBOL-derived expected outputs (the "golden" reference)
#   - Inputs that exercise a specific branch in DBCRFUN

class TestDebitCreditScenarios:
    """Core business logic scenarios matching COBOL decision paths."""

    def test_credit_to_savings_success(self):
        """Credit +500 to savings account via teller.

        COBOL path: amount >= 0, not restricted, UPDATE OK, PROCTRAN OK
        -> SUCCESS='Y', FAIL_CODE='0', balances increased.
        """
        acct_repo, pt_repo = _build_repos(_make_savings_account())
        request = DebitCreditRequest(
            acc_no="12345678",
            amount=Decimal("500.00"),
            facil_type=0,
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is True
        assert result.fail_code == "0"
        assert result.avail_bal == Decimal("1500.00")
        assert result.actual_bal == Decimal("1500.00")

        # Verify PROCTRAN record
        assert len(pt_repo.records) == 1
        rec = pt_repo.records[0]
        assert rec.tran_type == "CRE"
        assert rec.desc == "COUNTER RECVED"
        assert rec.amount == Decimal("500.00")

    def test_debit_from_savings_sufficient_funds(self):
        """Debit -200 from savings account via teller.

        COBOL path: amount < 0, not restricted, avail_bal + amount >= 0
        (teller -- FACILTYPE != 496 so insufficient funds check is skipped)
        -> SUCCESS='Y', FAIL_CODE='0', balances decreased.
        """
        acct_repo, pt_repo = _build_repos(_make_savings_account())
        request = DebitCreditRequest(
            acc_no="12345678",
            amount=Decimal("-200.00"),
            facil_type=0,
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is True
        assert result.fail_code == "0"
        assert result.avail_bal == Decimal("800.00")
        assert result.actual_bal == Decimal("800.00")

        assert len(pt_repo.records) == 1
        assert pt_repo.records[0].tran_type == "DEB"
        assert pt_repo.records[0].desc == "COUNTER WTHDRW"

    def test_debit_insufficient_funds_payment(self):
        """Debit -5000 from savings (balance 1000) via PAYMENT.

        COBOL path: amount < 0, FACILTYPE=496,
                    avail_bal + amount = -4000 < 0
        -> SUCCESS='N', FAIL_CODE='3' (insufficient funds).
        """
        acct_repo, pt_repo = _build_repos(_make_savings_account())
        request = DebitCreditRequest(
            acc_no="12345678",
            amount=Decimal("-5000.00"),
            facil_type=FACILTYPE_PAYMENT,
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is False
        assert result.fail_code == "3"
        # Balances should not have been updated
        assert len(pt_repo.records) == 0

    def test_debit_mortgage_payment_restricted(self):
        """Debit -100 from MORTGAGE account via PAYMENT.

        COBOL path: amount < 0, acc_type='MORTGAGE', FACILTYPE=496
        -> SUCCESS='N', FAIL_CODE='4' (restricted account type).
        """
        acct_repo, pt_repo = _build_repos(_make_mortgage_account())
        request = DebitCreditRequest(
            acc_no="99990001",
            amount=Decimal("-100.00"),
            facil_type=FACILTYPE_PAYMENT,
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is False
        assert result.fail_code == "4"
        assert len(pt_repo.records) == 0

    def test_credit_mortgage_payment_restricted(self):
        """Credit +100 to MORTGAGE account via PAYMENT.

        COBOL path: amount >= 0, but second check (lines 368-376):
                    acc_type='MORTGAGE' AND FACILTYPE=496
        -> SUCCESS='N', FAIL_CODE='4'.
        """
        acct_repo, pt_repo = _build_repos(_make_mortgage_account())
        request = DebitCreditRequest(
            acc_no="99990001",
            amount=Decimal("100.00"),
            facil_type=FACILTYPE_PAYMENT,
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is False
        assert result.fail_code == "4"
        assert len(pt_repo.records) == 0

    def test_account_not_found(self):
        """Debit from nonexistent account.

        COBOL path: SQLCODE = +100 -> fail_code '1'.
        """
        acct_repo, pt_repo = _build_repos()  # empty repo
        request = DebitCreditRequest(
            acc_no="00000000",
            amount=Decimal("-50.00"),
            facil_type=0,
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is False
        assert result.fail_code == "1"
        assert len(pt_repo.records) == 0


class TestEdgeCases:
    """Additional edge cases and boundary conditions."""

    def test_debit_insufficient_funds_teller_allowed(self):
        """Debit -5000 from savings (balance 1000) via TELLER.

        COBOL path: amount < 0, FACILTYPE != 496 so the insufficient
        funds check is SKIPPED.  The COBOL allows tellers to overdraw.
        -> SUCCESS='Y', FAIL_CODE='0', negative balance.
        """
        acct_repo, pt_repo = _build_repos(_make_savings_account())
        request = DebitCreditRequest(
            acc_no="12345678",
            amount=Decimal("-5000.00"),
            facil_type=0,  # teller
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is True
        assert result.fail_code == "0"
        assert result.avail_bal == Decimal("-4000.00")
        assert result.actual_bal == Decimal("-4000.00")

    def test_debit_mortgage_teller_allowed(self):
        """Debit -100 from MORTGAGE via TELLER.

        COBOL path: amount < 0, acc_type='MORTGAGE', but FACILTYPE != 496
        so the restricted-type check is skipped for the debit block.
        HOWEVER: the second check (lines 368-376) is OUTSIDE the debit IF,
        and it also requires FACILTYPE=496.  Since FACILTYPE=0, it passes.
        -> SUCCESS='Y', teller can debit mortgage.
        """
        acct_repo, pt_repo = _build_repos(_make_mortgage_account())
        request = DebitCreditRequest(
            acc_no="99990001",
            amount=Decimal("-100.00"),
            facil_type=0,  # teller
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is True
        assert result.fail_code == "0"

    def test_loan_account_payment_restricted(self):
        """Debit from LOAN account via PAYMENT.

        Same as mortgage: LOAN is also a restricted type.
        COBOL: HV-ACCOUNT-ACC-TYPE = 'LOAN    ' AND COMM-FACILTYPE = 496
        """
        acct_repo, pt_repo = _build_repos(_make_loan_account())
        request = DebitCreditRequest(
            acc_no="99990002",
            amount=Decimal("-50.00"),
            facil_type=FACILTYPE_PAYMENT,
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is False
        assert result.fail_code == "4"

    def test_proctran_failure_triggers_rollback(self):
        """PROCTRAN INSERT failure causes account rollback.

        COBOL path: UPDATE succeeds, but INSERT into PROCTRAN fails
        -> SYNCPOINT ROLLBACK, COMM-SUCCESS='N', COMM-FAIL-CODE='2'.
        The account balances should be reverted.
        """
        savings = _make_savings_account()
        original_avail = savings.avail_bal
        original_actual = savings.actual_bal

        acct_repo = InMemoryAccountRepository()
        acct_repo.add(savings)
        pt_repo = FailingProcTranRepository()

        request = DebitCreditRequest(
            acc_no="12345678",
            amount=Decimal("300.00"),
            facil_type=0,
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is False
        assert result.fail_code == "2"

        # Account should have been rolled back
        reverted = acct_repo.find(SORTCODE, "12345678")
        assert reverted is not None
        assert reverted.avail_bal == original_avail
        assert reverted.actual_bal == original_actual

    def test_zero_amount_credit(self):
        """Zero amount is treated as a credit (amount >= 0).

        COBOL: IF COMM-AMT < 0 ... ELSE (credit path).
        Zero is not < 0 so it takes the credit path.
        """
        acct_repo, pt_repo = _build_repos(_make_savings_account())
        request = DebitCreditRequest(
            acc_no="12345678",
            amount=Decimal("0.00"),
            facil_type=0,
        )
        result = process_debit_credit(request, acct_repo, pt_repo)

        assert result.success is True
        assert result.fail_code == "0"
        assert result.avail_bal == Decimal("1000.00")
        assert result.actual_bal == Decimal("1000.00")
        assert pt_repo.records[0].tran_type == "CRE"


class TestTransactionTypeClassification:
    """Verify DEB/CRE/PDR/PCR classification per COBOL logic."""

    def test_counter_debit(self):
        """Negative amount via teller -> DEB, 'COUNTER WTHDRW'."""
        acct_repo, pt_repo = _build_repos(_make_savings_account())
        request = DebitCreditRequest(
            acc_no="12345678",
            amount=Decimal("-100.00"),
            facil_type=0,
        )
        process_debit_credit(request, acct_repo, pt_repo)

        assert pt_repo.records[0].tran_type == "DEB"
        assert pt_repo.records[0].desc == "COUNTER WTHDRW"

    def test_counter_credit(self):
        """Positive amount via teller -> CRE, 'COUNTER RECVED'."""
        acct_repo, pt_repo = _build_repos(_make_savings_account())
        request = DebitCreditRequest(
            acc_no="12345678",
            amount=Decimal("100.00"),
            facil_type=0,
        )
        process_debit_credit(request, acct_repo, pt_repo)

        assert pt_repo.records[0].tran_type == "CRE"
        assert pt_repo.records[0].desc == "COUNTER RECVED"

    def test_payment_debit(self):
        """Negative amount via PAYMENT -> PDR, desc from origin[:14]."""
        acct_repo, pt_repo = _build_repos(
            _make_savings_account(avail_bal=Decimal("5000.00"),
                                  actual_bal=Decimal("5000.00"))
        )
        request = DebitCreditRequest(
            acc_no="12345678",
            amount=Decimal("-100.00"),
            facil_type=FACILTYPE_PAYMENT,
            origin="PAYMENTAPP  USERID01FACILITY",
        )
        process_debit_credit(request, acct_repo, pt_repo)

        assert pt_repo.records[0].tran_type == "PDR"
        # COMM-ORIGIN(1:14) = first 14 chars
        assert pt_repo.records[0].desc == "PAYMENTAPP  US"

    def test_payment_credit(self):
        """Positive amount via PAYMENT to non-restricted account -> PCR."""
        acct_repo, pt_repo = _build_repos(_make_savings_account())
        request = DebitCreditRequest(
            acc_no="12345678",
            amount=Decimal("100.00"),
            facil_type=FACILTYPE_PAYMENT,
            origin="XFERPROG  USERID01FACILITY",
        )
        process_debit_credit(request, acct_repo, pt_repo)

        assert pt_repo.records[0].tran_type == "PCR"
        assert pt_repo.records[0].desc == "XFERPROG  USER"


class TestDifferentialHarness:
    """Run all core scenarios through the differential harness framework.

    This uses the same TestVector / run_vectors / render_report_text
    pattern as the COSGN00C differential tests.  The 'expected' values
    are the golden reference derived from reading the COBOL source.
    """

    SCENARIOS = [
        {
            "id": "CREDIT_SAVINGS",
            "desc": "Credit +500 to savings via teller",
            "acc_no": "12345678",
            "amount": "500.00",
            "facil_type": 0,
            "expected": {
                "SUCCESS": "Y",
                "FAIL_CODE": "0",
                "AVAIL_BAL": "1500.00",
                "ACTUAL_BAL": "1500.00",
            },
        },
        {
            "id": "DEBIT_SAVINGS_OK",
            "desc": "Debit -200 from savings via teller",
            "acc_no": "12345678",
            "amount": "-200.00",
            "facil_type": 0,
            "expected": {
                "SUCCESS": "Y",
                "FAIL_CODE": "0",
                "AVAIL_BAL": "800.00",
                "ACTUAL_BAL": "800.00",
            },
        },
        {
            "id": "DEBIT_INSUFFICIENT",
            "desc": "Debit -5000 from savings (bal=1000) via payment",
            "acc_no": "12345678",
            "amount": "-5000.00",
            "facil_type": FACILTYPE_PAYMENT,
            "expected": {
                "SUCCESS": "N",
                "FAIL_CODE": "3",
                "AVAIL_BAL": "0.00",
                "ACTUAL_BAL": "0.00",
            },
        },
        {
            "id": "DEBIT_MORTGAGE_PAYMENT",
            "desc": "Debit -100 from mortgage via payment",
            "acc_no": "99990001",
            "amount": "-100.00",
            "facil_type": FACILTYPE_PAYMENT,
            "expected": {
                "SUCCESS": "N",
                "FAIL_CODE": "4",
                "AVAIL_BAL": "0.00",
                "ACTUAL_BAL": "0.00",
            },
        },
        {
            "id": "ACCOUNT_NOT_FOUND",
            "desc": "Debit from nonexistent account",
            "acc_no": "00000000",
            "amount": "-50.00",
            "facil_type": 0,
            "expected": {
                "SUCCESS": "N",
                "FAIL_CODE": "1",
                "AVAIL_BAL": "0.00",
                "ACTUAL_BAL": "0.00",
            },
        },
    ]

    def test_all_scenarios_via_harness(self):
        """All 5 scenarios produce outputs matching COBOL golden reference."""
        # Build shared repos with savings and mortgage accounts
        acct_repo = InMemoryAccountRepository()
        acct_repo.add(_make_savings_account())
        acct_repo.add(_make_mortgage_account())

        vectors = []
        for scenario in self.SCENARIOS:
            # Fresh repos per scenario (so balance mutations don't leak)
            s_acct_repo = InMemoryAccountRepository()
            s_acct_repo.add(_make_savings_account())
            s_acct_repo.add(_make_mortgage_account())
            s_pt_repo = InMemoryProcTranRepository()

            request = DebitCreditRequest(
                acc_no=scenario["acc_no"],
                amount=Decimal(scenario["amount"]),
                facil_type=scenario["facil_type"],
            )
            actual = _run_scenario(request, s_acct_repo, s_pt_repo)

            vectors.append(TestVector(
                vector_id=scenario["id"],
                program="DBCRFUN",
                inputs={
                    "ACC_NO": scenario["acc_no"],
                    "AMOUNT": scenario["amount"],
                    "FACIL_TYPE": str(scenario["facil_type"]),
                },
                expected_outputs=scenario["expected"],
                actual_outputs=actual,
                field_types={
                    "SUCCESS": "str",
                    "FAIL_CODE": "str",
                    "AVAIL_BAL": {
                        "type": "Decimal",
                        "digits": 10,
                        "scale": 2,
                        "signed": True,
                    },
                    "ACTUAL_BAL": {
                        "type": "Decimal",
                        "digits": 10,
                        "scale": 2,
                        "signed": True,
                    },
                },
            ))

        report = run_vectors(vectors)
        report_text = render_report_text(report)
        print("\n" + report_text)

        assert report.confidence_score == 100.0, \
            f"COBOL/Python mismatch!\n{report_text}"
        assert report.failed == 0
        assert report.passed == 5
