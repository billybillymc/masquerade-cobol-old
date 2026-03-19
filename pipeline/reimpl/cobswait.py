"""
Reimplementation of COBSWAIT — CardDemo wait utility.

Accepts a centisecond count and sleeps for that duration.
"""

import time


def wait_centiseconds(centiseconds: int) -> None:
    """Wait for the given number of centiseconds (hundredths of a second).

    COBOL original: CALL 'MVSWAIT' USING MVSWAIT-TIME
    where MVSWAIT-TIME is centiseconds (PIC 9(8) COMP).
    """
    if centiseconds < 0:
        centiseconds = 0
    time.sleep(centiseconds / 100.0)


def run(parm_value: str) -> None:
    """Entry point mirroring COBSWAIT's PROCEDURE DIVISION.

    ACCEPT PARM-VALUE FROM SYSIN
    MOVE PARM-VALUE TO MVSWAIT-TIME
    CALL 'MVSWAIT' USING MVSWAIT-TIME
    """
    try:
        cs = int(parm_value.strip())
    except (ValueError, AttributeError):
        cs = 0
    wait_centiseconds(cs)
