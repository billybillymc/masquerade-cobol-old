"""
Reimplementation of CBSTM03B — CardDemo Statement File I/O Subroutine.

CBSTM03A calls CBSTM03B as a subroutine passing an operation code:
  'O' = Open file
  'C' = Close file
  'R' = Read next record
  'K' = Read by key
  'W' = Write record
  'Z' = Rewrite record

This subroutine manages the transaction file and returns records/status codes.
"""

from __future__ import annotations
from dataclasses import dataclass

from .carddemo_data import TranRecord


# ── Operation codes (88-level condition names in COBOL) ───────────────────────

OPER_OPEN    = "O"
OPER_CLOSE   = "C"
OPER_READ    = "R"
OPER_READ_K  = "K"
OPER_WRITE   = "W"
OPER_REWRITE = "Z"


@dataclass
class M03BArea:
    """WS-M03B-AREA — linkage area between CBSTM03A and CBSTM03B."""
    dd: str = "TRNXFILE"   # dataset name
    oper: str = ""          # operation code
    rc: str = "00"          # return code: '00'=ok, '10'=EOF, '23'=not-found
    key: str = ""           # record key for keyed reads
    key_ln: int = 0         # length of key
    fldt: str = ""          # record data area (1000 chars)


class Cbstm03bFileManager:
    """Stateful file I/O manager, injected with a transaction list."""

    def __init__(self, transactions: list[TranRecord]):
        self._transactions = transactions
        self._cursor = 0
        self._by_id: dict[str, TranRecord] = {t.tran_id: t for t in transactions}
        self._is_open = False

    def execute(self, area: M03BArea) -> M03BArea:
        """Process a single CALL 'CBSTM03B' invocation."""
        op = area.oper

        if op == OPER_OPEN:
            self._cursor = 0
            self._is_open = True
            area.rc = "00"

        elif op == OPER_CLOSE:
            self._is_open = False
            area.rc = "00"

        elif op == OPER_READ:
            if not self._is_open:
                area.rc = "35"
            elif self._cursor >= len(self._transactions):
                area.rc = "10"  # EOF
            else:
                tran = self._transactions[self._cursor]
                self._cursor += 1
                area.fldt = self._serialize(tran)
                area.rc = "00"

        elif op == OPER_READ_K:
            key = area.key.strip()
            tran = self._by_id.get(key)
            if tran is None:
                area.rc = "23"  # not found
            else:
                area.fldt = self._serialize(tran)
                area.rc = "00"

        elif op == OPER_WRITE:
            tran = self._deserialize(area.fldt)
            if tran.tran_id not in self._by_id:
                self._transactions.append(tran)
                self._by_id[tran.tran_id] = tran
                area.rc = "00"
            else:
                area.rc = "22"  # duplicate key

        elif op == OPER_REWRITE:
            tran = self._deserialize(area.fldt)
            if tran.tran_id in self._by_id:
                self._by_id[tran.tran_id] = tran
                area.rc = "00"
            else:
                area.rc = "23"  # not found

        else:
            area.rc = "99"

        return area

    def _serialize(self, tran: TranRecord) -> str:
        """Serialize a TranRecord into the 1000-char FLDT area."""
        return (
            f"{tran.tran_id:<16}"
            f"{tran.tran_type_cd:<2}"
            f"{tran.tran_cat_cd:04d}"
            f"{tran.tran_source:<10}"
            f"{tran.tran_desc:<100}"
            f"{float(tran.tran_amt):014.2f}"
            f"{tran.tran_merchant_id:09d}"
            f"{tran.tran_merchant_name:<50}"
            f"{tran.tran_merchant_city:<50}"
            f"{tran.tran_merchant_zip:<10}"
            f"{tran.tran_card_num:<16}"
            f"{tran.tran_orig_ts:<26}"
            f"{tran.tran_proc_ts:<26}"
        )

    def _deserialize(self, fldt: str) -> TranRecord:
        """Deserialize FLDT area back into a TranRecord (best-effort)."""
        from decimal import Decimal
        try:
            return TranRecord(
                tran_id=fldt[0:16].strip(),
                tran_type_cd=fldt[16:18].strip(),
                tran_cat_cd=int(fldt[18:22] or 0),
                tran_source=fldt[22:32].strip(),
                tran_desc=fldt[32:132].strip(),
                tran_amt=Decimal(fldt[132:146].strip() or "0"),
                tran_merchant_id=int(fldt[146:155] or 0),
                tran_merchant_name=fldt[155:205].strip(),
                tran_merchant_city=fldt[205:255].strip(),
                tran_merchant_zip=fldt[255:265].strip(),
                tran_card_num=fldt[265:281].strip(),
                tran_orig_ts=fldt[281:307].strip(),
                tran_proc_ts=fldt[307:333].strip(),
            )
        except Exception:
            return TranRecord()
