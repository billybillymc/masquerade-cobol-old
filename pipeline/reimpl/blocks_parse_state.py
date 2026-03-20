"""
Reimplementation of Blocks-Parse-State — CobolCraft Minecraft server.

COBOL source: test-codebases/cobolcraft/src/blocks.cob
  Program-ID: Blocks-Parse-State (lines 236-295)

Signature (LINKAGE SECTION):
  LK-JSON          PIC X ANY LENGTH   -- the JSON buffer (passed by caller)
  LK-OFFSET        BINARY-LONG UNSIGNED -- current parse position (in/out)
  LK-FAILURE       BINARY-CHAR UNSIGNED -- 0 = OK, non-zero = error (in/out)
  LK-BLOCK-STATE   BINARY-LONG UNSIGNED -- OUT: parsed numeric state ID
  LK-IS-DEFAULT    BINARY-CHAR UNSIGNED -- OUT: 1 if this is the default state

Logic:
  1. Initialize LK-IS-DEFAULT = 0.
  2. Expect '{' (JsonParse-ObjectStart).
  3. Loop reading object keys until no comma:
     - "id"      -> read integer -> LK-BLOCK-STATE
     - "default" -> read boolean -> LK-IS-DEFAULT
     - anything else -> skip value
  4. Expect '}'.

The JSON for a single state entry looks like:
  {"id": 16, "default": true, "properties": {"facing": "north"}}
  (we only extract "id" and "default"; "properties" is skipped)
"""

from __future__ import annotations
import json as _json
from dataclasses import dataclass, field


@dataclass
class BlockStateResult:
    state_id: int   = 0    # LK-BLOCK-STATE
    is_default: bool = False  # LK-IS-DEFAULT


def parse_block_state(obj: dict) -> BlockStateResult:
    """Parse a single Minecraft block-state object.

    Mirrors Blocks-Parse-State PROCEDURE DIVISION: extracts "id" and "default",
    silently skips all other keys (matching the WHEN OTHER -> SkipValue branch).

    Args:
        obj: A dict representing one entry from the "states" array in blocks.json.
             Expected keys: "id" (int), optionally "default" (bool).

    Returns:
        BlockStateResult with state_id and is_default populated.

    Raises:
        ValueError: if "id" is missing (mirrors LK-FAILURE non-zero on bad parse).
    """
    if "id" not in obj:
        raise ValueError("block state object missing required key 'id'")
    return BlockStateResult(
        state_id=int(obj["id"]),
        is_default=bool(obj.get("default", False)),
    )


def parse_block_states(states_array: list[dict]) -> list[BlockStateResult]:
    """Parse the full 'states' array from a block entry.

    Corresponds to the PERFORM loop in Blocks-Parse-Block that calls
    Blocks-Parse-State for each element, tracking min/max IDs and the default.
    """
    results = []
    for entry in states_array:
        results.append(parse_block_state(entry))
    return results


def find_default_state(results: list[BlockStateResult]) -> BlockStateResult | None:
    """Return the state marked default=true, or None if absent."""
    for r in results:
        if r.is_default:
            return r
    return None


def state_id_range(results: list[BlockStateResult]) -> tuple[int, int]:
    """Return (min_state_id, max_state_id) across all parsed states.

    Mirrors the MOVE MIN/MAX logic in Blocks-Parse-Block after calling
    Blocks-Parse-State for each entry.
    """
    ids = [r.state_id for r in results]
    return (min(ids), max(ids)) if ids else (0, 0)
