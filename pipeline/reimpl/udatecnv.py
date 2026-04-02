"""UDATECNV — date/time conversion utility.

COBOL source: test-codebases/bankdemo/sources/cobol/core/UDATECNV.cbl
Copybook:     test-codebases/bankdemo/sources/copybook/CDATED.cpy

Calling convention:
    CALL 'UDATECNV' USING LK-DATE-WORK-AREA  (CDATED copybook layout)
"""

_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _is_leap(yy_2digit: int) -> bool:
    """Replicate COBOL leap-year check: divisible by 4 (no century correction)."""
    return (yy_2digit % 4) == 0


def _yyddd_to_mmdd(yy: int, ddd: int) -> tuple[int, int]:
    """Convert Julian day-of-year to (month, day), applying the COBOL leap-year rule."""
    days = list(_DAYS_IN_MONTH)
    days[1] = 29 if _is_leap(yy) else 28
    remaining = ddd
    for month_idx, month_days in enumerate(days):
        if remaining <= month_days:
            return month_idx + 1, remaining
        remaining -= month_days
    return 12, 31  # should not be reached for valid input


def _century(yy_str: str) -> str:
    """Return '20' if YY < '50' else '19' (COBOL sliding-window rule)."""
    return '20' if yy_str < '50' else '19'


def convert_date(ddi_type: str, ddi_data: str, ddo_type: str) -> str:
    """Convert a date from the input format/data to the output format.

    Args:
        ddi_type: '0'=ISO(yyyy-mm-dd), '1'=YYYYMMDD, '2'=YYMMDD, '3'=YYDDD
        ddi_data: date string in the format specified by ddi_type
        ddo_type: '1'=DD.MMM.YY, '2'=DD.MMM.YYYY

    Returns:
        20-character right-padded result, or 'ERROR1'/'ERROR2' on bad input.
    """
    if ddi_type not in ('0', '1', '2', '3'):
        return _pad('ERROR1')

    if ddo_type not in ('1', '2'):
        return _pad('ERROR2')

    d = ddi_data.ljust(20)

    if ddi_type == '0':        # ISO: yyyy-mm-dd  (d[4]='-', d[7]='-')
        yyyy = d[0:4]
        mm   = int(d[5:7])
        dd   = d[8:10]
        yy   = yyyy[2:4]
    elif ddi_type == '1':      # YYYYMMDD
        yyyy = d[0:4]
        mm   = int(d[4:6])
        dd   = d[6:8]
        yy   = yyyy[2:4]
    elif ddi_type == '2':      # YYMMDD
        yy   = d[0:2]
        mm   = int(d[2:4])
        dd   = d[4:6]
        yyyy = _century(yy) + yy
    else:                      # YYDDD
        yy   = d[0:2]
        ddd  = int(d[2:5])
        mm, day_int = _yyddd_to_mmdd(int(yy), ddd)
        dd   = f'{day_int:02d}'
        yyyy = _century(yy) + yy

    mon = _MONTHS[mm - 1]

    if ddo_type == '1':
        result = f'{dd}.{mon}.{yy}'
    else:
        result = f'{dd}.{mon}.{yyyy}'

    return _pad(result)


def _pad(s: str) -> str:
    return s.ljust(20)


def convert_time(env: str, time_input: str) -> str:
    """Convert time input to HH:MM:SS string.

    Args:
        env:        'CICS', 'IMS ', 'INET', or LOW-VALUES (null)
        time_input: 7-character numeric string (PIC X(7))

    Returns:
        8-character 'HH:MM:SS' string, or 'hh:mm:ss' on invalid input.
    """
    env = env.strip()
    if not time_input.isdigit():
        return 'hh:mm:ss'

    n = int(time_input)

    if env == 'CICS':
        # COBOL MOVE of PIC 9(7) into PIC 9(6) truncates the high-order digit
        work = n % 1_000_000
    elif env == 'IMS':
        work = n // 10
    else:
        # NULL / INET: use system time — for deterministic testing, caller
        # should provide actual HHMMSS in time_input when env is not CICS/IMS.
        work = n % 1_000_000

    hh = work // 10_000
    mm = (work % 10_000) // 100
    ss = work % 100
    return f'{hh:02d}:{mm:02d}:{ss:02d}'
