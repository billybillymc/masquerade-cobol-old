"""CobolCraft json-parse — JSON token parser.

COBOL source: test-codebases/cobolcraft/src/encoding/json-parse.cob

All functions use 1-based offsets to match the COBOL BINARY-LONG convention.
Return convention: (flag, new_offset) or (flag, new_offset, value)
  flag=0  success
  flag=1  parse error
"""


def _skip_whitespace(s: str, offset: int) -> int:
    """Advance offset past spaces, tabs, newlines."""
    n = len(s)
    while offset <= n and s[offset - 1] in ' \t\r\n':
        offset += 1
    return offset


# ── Delimiters ────────────────────────────────────────────────────────────────

def parse_object_start(s: str, offset: int):
    offset = _skip_whitespace(s, offset)
    if offset > len(s) or s[offset - 1] != '{':
        return 1, offset
    return 0, offset + 1


def parse_object_end(s: str, offset: int):
    offset = _skip_whitespace(s, offset)
    if offset > len(s) or s[offset - 1] != '}':
        return 1, offset
    return 0, offset + 1


def parse_array_start(s: str, offset: int):
    offset = _skip_whitespace(s, offset)
    if offset > len(s) or s[offset - 1] != '[':
        return 1, offset
    return 0, offset + 1


def parse_array_end(s: str, offset: int):
    offset = _skip_whitespace(s, offset)
    if offset > len(s) or s[offset - 1] != ']':
        return 1, offset
    return 0, offset + 1


def parse_comma(s: str, offset: int):
    offset = _skip_whitespace(s, offset)
    if offset > len(s) or s[offset - 1] != ',':
        return 1, offset
    return 0, offset + 1


# ── String ────────────────────────────────────────────────────────────────────

_ESCAPE_MAP = {
    '"':  '"',
    '/':  '/',
    '\\': '\\',
    'b':  '\x08',
    'f':  '\x0C',
    'n':  '\n',
    'r':  '\r',
    't':  '\t',
}


def parse_string(s: str, offset: int):
    n = len(s)
    offset = _skip_whitespace(s, offset)
    if offset > n or s[offset - 1] != '"':
        return 1, offset, ''
    offset += 1  # consume opening quote

    out = []
    escaping = False
    while offset <= n:
        ch = s[offset - 1]
        if escaping:
            if ch == 'u':
                if offset + 4 > n:
                    return 1, offset, ''
                hex4 = s[offset:offset + 4]
                out.append(chr(int(hex4, 16)))
                offset += 4
            elif ch in _ESCAPE_MAP:
                out.append(_ESCAPE_MAP[ch])
                offset += 1
            else:
                return 1, offset, ''
            escaping = False
        else:
            if ch == '"':
                return 0, offset + 1, ''.join(out)
            elif ch == '\\':
                escaping = True
                offset += 1
            else:
                out.append(ch)
                offset += 1

    return 1, offset, ''  # unterminated


def parse_object_key(s: str, offset: int):
    n = len(s)
    flag, offset, key = parse_string(s, offset)
    if flag != 0:
        return 1, offset, ''
    offset = _skip_whitespace(s, offset)
    if offset > n or s[offset - 1] != ':':
        return 1, offset, ''
    return 0, offset + 1, key


# ── Primitives ────────────────────────────────────────────────────────────────

def parse_null(s: str, offset: int):
    n = len(s)
    offset = _skip_whitespace(s, offset)
    if offset + 3 > n or s[offset - 1] != 'n':
        return 1, offset
    return 0, offset + 4


def parse_boolean(s: str, offset: int):
    n = len(s)
    offset = _skip_whitespace(s, offset)
    if offset > n:
        return 1, offset, 0
    ch = s[offset - 1]
    if ch == 't':
        if offset + 3 > n:
            return 1, offset, 0
        return 0, offset + 4, 1
    elif ch == 'f':
        if offset + 4 > n:
            return 1, offset, 0
        return 0, offset + 5, 0
    return 1, offset, 0


def parse_integer(s: str, offset: int):
    n = len(s)
    offset = _skip_whitespace(s, offset)
    if offset > n:
        return 1, offset, 0

    sign = 1
    if s[offset - 1] == '-':
        sign = -1
        offset += 1

    found = False
    value = 0
    while offset <= n:
        code = ord(s[offset - 1])
        if code < 48 or code > 57:
            break
        value = value * 10 + (code - 48)
        offset += 1
        found = True

    if not found:
        return 1, offset, 0
    return 0, offset, sign * value


def parse_float(s: str, offset: int):
    flag, offset, int_val = parse_integer(s, offset)
    result = float(int_val)
    if flag != 0:
        return flag, offset, result

    n = len(s)
    if offset > n or s[offset - 1] != '.':
        return 0, offset, result

    offset += 1  # consume '.'
    multiplier = 0.1 if result >= 0 else -0.1
    found = False
    while offset <= n:
        code = ord(s[offset - 1])
        if code < 48 or code > 57:
            break
        result += (code - 48) * multiplier
        multiplier /= 10
        offset += 1
        found = True

    if not found:
        return 1, offset, result

    if offset > n or s[offset - 1] not in ('e', 'E'):
        return 0, offset, result

    offset += 1  # consume 'e'/'E'
    if offset <= n and s[offset - 1] == '+':
        offset += 1

    flag, offset, exp = parse_integer(s, offset)
    if flag != 0:
        return flag, offset, result
    result *= 10 ** exp
    return 0, offset, result


# ── SkipValue ─────────────────────────────────────────────────────────────────

def parse_skip_value(s: str, offset: int):
    n = len(s)
    offset = _skip_whitespace(s, offset)
    if offset > n:
        return 1, offset

    ch = s[offset - 1]

    if ch == '"':
        _, offset, _ = parse_string(s, offset)
        return 0, offset
    elif ch == 'n':
        return parse_null(s, offset)
    elif ch == 't':
        return 0, offset + 4
    elif ch == 'f':
        return 0, offset + 5
    elif ch == '-' or ('0' <= ch <= '9'):
        flag, offset, _ = parse_float(s, offset)
        return flag, offset
    elif ch == '[':
        offset += 1
        offset = _skip_whitespace(s, offset)
        if offset > n:
            return 1, offset
        if s[offset - 1] == ']':
            return 0, offset + 1
        while True:
            flag, offset = parse_skip_value(s, offset)
            if flag == 1:
                return 1, offset
            flag, offset = parse_comma(s, offset)
            if flag == 1:
                break
        offset = _skip_whitespace(s, offset)
        if offset > n or s[offset - 1] != ']':
            return 1, offset
        return 0, offset + 1
    elif ch == '{':
        offset += 1
        offset = _skip_whitespace(s, offset)
        if offset > n:
            return 1, offset
        if s[offset - 1] == '}':
            return 0, offset + 1
        while True:
            offset = _skip_whitespace(s, offset)
            if offset > n or s[offset - 1] != '"':
                return 1, offset
            # skip key string
            offset += 1
            while offset <= n:
                kch = s[offset - 1]
                offset += 1
                if kch == '"':
                    break
                if kch == '\\':
                    offset += 1
            offset = _skip_whitespace(s, offset)
            if offset > n or s[offset - 1] != ':':
                return 1, offset
            offset += 1
            flag, offset = parse_skip_value(s, offset)
            if flag == 1:
                return 1, offset
            flag, offset = parse_comma(s, offset)
            if flag == 1:
                break
        offset = _skip_whitespace(s, offset)
        if offset > n or s[offset - 1] != '}':
            return 1, offset
        return 0, offset + 1
    else:
        return 1, offset


# ── FindValue ─────────────────────────────────────────────────────────────────

def parse_find_value(s: str, offset: int, key: str):
    """Scan a JSON object body (no outer braces) for the given key.

    Returns (0, value_offset) if found, (1, original_offset) if not.
    """
    cur = offset
    while True:
        flag, cur, found_key = parse_object_key(s, cur)
        if flag == 1:
            return 1, offset
        if found_key.rstrip() == key.rstrip():
            return 0, cur
        flag, cur = parse_skip_value(s, cur)
        if flag == 1:
            return 1, offset
        flag, cur = parse_comma(s, cur)
        if flag == 1:
            return 1, offset
