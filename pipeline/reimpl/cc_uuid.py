"""CobolCraft uuid — UUID-ToString and UUID-FromString.

COBOL source: test-codebases/cobolcraft/src/encoding/uuid.cob

UUID-ToString converts a 16-byte big-endian binary UUID to the standard
36-character hyphenated hex string.  Dashes are inserted after bytes 4, 6, 8,
and 10 (1-based), matching the COBOL: IF INPUT-INDEX = 4 OR 6 OR 8 OR 10.

UUID-FromString is the inverse: parses the 36-char string back to 16 bytes,
skipping the dashes at the same positions.
"""

_HEX = '0123456789abcdef'


def uuid_to_string(buf: bytes) -> str:
    """Convert 16-byte UUID buffer to 36-char hyphenated hex string."""
    out = []
    for i, byte in enumerate(buf, start=1):
        out.append(_HEX[byte >> 4])
        out.append(_HEX[byte & 0x0F])
        if i in (4, 6, 8, 10):
            out.append('-')
    return ''.join(out)


def uuid_from_string(s: str) -> bytes:
    """Convert 36-char hyphenated UUID string to 16-byte buffer."""
    out = []
    idx = 0
    for byte_pos in range(1, 17):
        hi = _decode_hex(s[idx]);  idx += 1
        lo = _decode_hex(s[idx]);  idx += 1
        out.append((hi << 4) | lo)
        if byte_pos in (4, 6, 8, 10):
            idx += 1  # skip dash
    return bytes(out)


def _decode_hex(c: str) -> int:
    return _HEX.index(c.lower())
