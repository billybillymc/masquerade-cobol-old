"""RTNCDE00 — standard return code handler.

COBOL source:  test-codebases/legacy-benchmark/src/programs/batch/RTNCDE00.cbl
Copybook:      test-codebases/legacy-benchmark/src/copybook/common/RTNCODE.cpy

DB2 operations (RC-LOG-CODE, RC-ANALYZE) are stubbed — callers inject a db_log
callable if they need real persistence.
"""
from dataclasses import dataclass, field


@dataclass
class ReturnCodeArea:
    request: str       = ' '
    program_id: str    = ' ' * 8
    current_code: int  = 0
    highest_code: int  = 0
    new_code: int      = 0
    status: str        = 'S'
    message: str       = ' ' * 80
    response_code: int = 0
    # RC-ANALYSIS-DATA
    start_time: str    = ' ' * 26
    end_time: str      = ' ' * 26
    total_codes: int   = 0
    max_code: int      = 0
    min_code: int      = 0
    # RC-RETURN-DATA
    return_value: int  = 0
    highest_return: int = 0
    return_status: str = ' '


def rtncde00(area: ReturnCodeArea, db_log=None, db_analyze=None) -> None:
    """Execute the RTNCDE00 return-code state machine.

    Args:
        area:        mutable ReturnCodeArea (mirrors RTNCODE copybook layout)
        db_log:      optional callable(area) for RC-LOG-CODE; returns 0 or 8
        db_analyze:  optional callable(area) for RC-ANALYZE; returns 0 or 8
    """
    req = area.request

    if req == 'I':
        _p100_init(area)
    elif req == 'S':
        _p200_set(area)
    elif req == 'G':
        _p300_get(area)
    elif req == 'L':
        _p400_log(area, db_log)
    elif req == 'A':
        _p500_analyze(area, db_analyze)


def _p100_init(area: ReturnCodeArea) -> None:
    area.current_code  = 0
    area.highest_code  = 0
    area.new_code      = 0
    area.program_id    = ' ' * 8
    area.status        = 'S'
    area.response_code = 0


def _p200_set(area: ReturnCodeArea) -> None:
    if area.new_code > area.highest_code:
        area.highest_code = area.new_code
    area.current_code = area.new_code

    code = area.new_code
    if code == 0:
        area.status = 'S'
    elif 1 <= code <= 4:
        area.status = 'W'
    elif 5 <= code <= 8:
        area.status = 'E'
    else:
        area.status = 'F'

    area.response_code = 0


def _p300_get(area: ReturnCodeArea) -> None:
    area.return_value   = area.current_code
    area.highest_return = area.highest_code
    area.return_status  = area.status
    area.response_code  = 0


def _p400_log(area: ReturnCodeArea, db_log) -> None:
    if db_log is not None:
        area.response_code = db_log(area)
    else:
        area.response_code = 0


def _p500_analyze(area: ReturnCodeArea, db_analyze) -> None:
    if db_analyze is not None:
        area.response_code = db_analyze(area)
    else:
        area.response_code = 0
