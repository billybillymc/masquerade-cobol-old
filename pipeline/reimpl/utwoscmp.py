"""UTWOSCMP — one's complement byte utility.

COBOL source: test-codebases/bankdemo/sources/cobol/core/UTWOSCMP.cbl
Calling convention:
    CALL 'UTWOSCMP' USING LK-TWOS-CMP-LEN LK-TWOS-CMP-INPUT LK-TWOS-CMP-OUTPUT

For each byte in input[0:length], output[i] = 255 - input[i]  (bitwise NOT / one's complement).
The COBOL name says "twos complement" but the arithmetic (255 - byte) is one's complement.
"""


def twos_cmp(data: bytes) -> bytes:
    """Return the one's complement of every byte in *data*."""
    return bytes(255 - b for b in data)
