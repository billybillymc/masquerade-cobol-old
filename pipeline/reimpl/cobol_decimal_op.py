"""
CobolDecimal operation dispatcher — parity test fixture, not a real reimpl.

This module is NOT a reimplementation of any COBOL program. It exists to
exercise `cobol_decimal.CobolDecimal` from the same JSON I/O contract used
by the differential harness, so the Java side's `CobolDecimal.java` can
be tested for byte-for-byte equivalence on inputs that the W1 unit tests
don't randomize over (overflow paths, divide buffer edge cases, etc.).

The Java twin lives at:
  pipeline/reimpl/java/runner/.../programs/CobolDecimalOp.java
and is registered in ProgramRegistry as "COBOL_DECIMAL_OP".

Operation grammar:
  op == "set"
    inputs:  digits, scale, signed, usage, on_size_error, value, rounded
    outputs: value, error
  op == "add" | "subtract" | "multiply" | "divide"
    inputs:  a_digits, a_scale, a_signed, a_value,
             b_digits, b_scale, b_signed, b_value
    outputs: result_value, result_digits, result_scale, error
  op == "assign_to"
    inputs:  src_digits, src_scale, src_signed, src_value,
             target_digits, target_scale, target_signed, rounded
    outputs: value, error
  op == "from_display"
    inputs:  digits, scale, signed, raw
    outputs: value, error
  op == "storage_bytes"
    inputs:  digits, scale, signed, usage
    outputs: storage_bytes, error

Numeric values (`value`, `a_value`, `result_value`, etc.) are passed as
their canonical Decimal string forms — both languages format them via the
same convention so byte-for-byte equality is the gate.
"""

import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cobol_decimal import CobolDecimal, CobolOverflowError


def _str_value(cd: CobolDecimal) -> str:
    """Canonical decimal string for a CobolDecimal value.

    Forces the stored Decimal through `str()` which gives the same shape
    Java's `BigDecimal.toPlainString()` produces. Both languages MUST
    agree on this format.
    """
    return str(cd.value)


def _parse_bool(raw) -> bool:
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    return s in ("true", "1", "yes", "y")


def _parse_int(raw, fallback=0) -> int:
    if raw is None or raw == "":
        return fallback
    return int(str(raw).strip())


def run_vector(inputs: dict) -> dict:
    """Single-operation dispatcher. See module docstring for op grammar."""
    op = str(inputs.get("op", "")).strip().lower()

    try:
        if op == "set":
            digits = _parse_int(inputs.get("digits"), 9)
            scale = _parse_int(inputs.get("scale"), 0)
            signed = _parse_bool(inputs.get("signed", "true"))
            usage = str(inputs.get("usage", "DISPLAY"))
            ose = str(inputs.get("on_size_error", "truncate"))
            value = str(inputs.get("value", "0"))
            rounded = _parse_bool(inputs.get("rounded", "false"))

            cd = CobolDecimal(digits=digits, scale=scale, signed=signed,
                              usage=usage, on_size_error=ose)
            cd.set(Decimal(value), rounded=rounded)
            return {"value": _str_value(cd), "error": ""}

        if op in ("add", "subtract", "multiply", "divide"):
            a = CobolDecimal(
                digits=_parse_int(inputs.get("a_digits"), 9),
                scale=_parse_int(inputs.get("a_scale"), 0),
                signed=_parse_bool(inputs.get("a_signed", "true")),
            )
            a.set(Decimal(str(inputs.get("a_value", "0"))))

            b = CobolDecimal(
                digits=_parse_int(inputs.get("b_digits"), 9),
                scale=_parse_int(inputs.get("b_scale"), 0),
                signed=_parse_bool(inputs.get("b_signed", "true")),
            )
            b.set(Decimal(str(inputs.get("b_value", "0"))))

            if op == "add":
                result = a.add(b)
            elif op == "subtract":
                result = a.subtract(b)
            elif op == "multiply":
                result = a.multiply(b)
            else:  # divide
                result = a.divide(b)

            return {
                "result_value": _str_value(result),
                "result_digits": str(result.digits),
                "result_scale": str(result.scale),
                "error": "",
            }

        if op == "assign_to":
            src = CobolDecimal(
                digits=_parse_int(inputs.get("src_digits"), 9),
                scale=_parse_int(inputs.get("src_scale"), 0),
                signed=_parse_bool(inputs.get("src_signed", "true")),
            )
            src.set(Decimal(str(inputs.get("src_value", "0"))))
            target = CobolDecimal(
                digits=_parse_int(inputs.get("target_digits"), 9),
                scale=_parse_int(inputs.get("target_scale"), 0),
                signed=_parse_bool(inputs.get("target_signed", "true")),
            )
            rounded = _parse_bool(inputs.get("rounded", "false"))
            src.assign_to(target, rounded=rounded)
            return {"value": _str_value(target), "error": ""}

        if op == "from_display":
            cd = CobolDecimal(
                digits=_parse_int(inputs.get("digits"), 9),
                scale=_parse_int(inputs.get("scale"), 0),
                signed=_parse_bool(inputs.get("signed", "true")),
            )
            raw = inputs.get("raw")
            cd.from_display(raw)
            return {"value": _str_value(cd), "error": ""}

        if op == "storage_bytes":
            cd = CobolDecimal(
                digits=_parse_int(inputs.get("digits"), 9),
                scale=_parse_int(inputs.get("scale"), 0),
                signed=_parse_bool(inputs.get("signed", "true")),
                usage=str(inputs.get("usage", "DISPLAY")),
            )
            return {"storage_bytes": str(cd.storage_bytes), "error": ""}

        return {"error": f"unknown op: {op!r}"}

    except CobolOverflowError as e:
        return {"value": "", "error": f"OVERFLOW: {e}"}
    except (InvalidOperation, ValueError, ZeroDivisionError) as e:
        return {"value": "", "error": f"{type(e).__name__}: {e}"}
