"""
Differential tests for CobolCraft Blocks-Parse-State reimplementation.

Golden behavior is derived directly from the COBOL source at
test-codebases/cobolcraft/src/blocks.cob lines 236-295.

Each test vector mirrors the DiffVector approach: fixed inputs, expected outputs,
verified against the Python reimplementation.
"""

import pytest
from reimpl.blocks_parse_state import (
    BlockStateResult,
    parse_block_state,
    parse_block_states,
    find_default_state,
    state_id_range,
)


# ---------------------------------------------------------------------------
# parse_block_state — mirrors PROCEDURE DIVISION of Blocks-Parse-State
# ---------------------------------------------------------------------------

class TestParseBlockState:
    def test_id_only_state(self):
        """State with only 'id' — is_default must be False (LK-IS-DEFAULT init = 0)."""
        result = parse_block_state({"id": 42})
        assert result.state_id == 42
        assert result.is_default is False

    def test_id_and_default_true(self):
        """State with 'default': true — mirrors WHEN 'default' -> JsonParse-Boolean = 1."""
        result = parse_block_state({"id": 16, "default": True})
        assert result.state_id == 16
        assert result.is_default is True

    def test_id_and_default_false(self):
        """Explicit default=false — LK-IS-DEFAULT stays 0."""
        result = parse_block_state({"id": 7, "default": False})
        assert result.state_id == 7
        assert result.is_default is False

    def test_extra_keys_silently_skipped(self):
        """'properties' and other keys skipped — mirrors WHEN OTHER -> SkipValue."""
        result = parse_block_state({
            "id": 99,
            "default": True,
            "properties": {"facing": "north", "powered": "false"},
            "unknown_future_key": "ignored",
        })
        assert result.state_id == 99
        assert result.is_default is True

    def test_missing_id_raises(self):
        """'id' is mandatory — mirrors LK-FAILURE set when JsonParse-Integer fails."""
        with pytest.raises(ValueError, match="missing required key 'id'"):
            parse_block_state({"default": True})

    def test_state_id_zero(self):
        """State ID of 0 is valid (air block)."""
        result = parse_block_state({"id": 0})
        assert result.state_id == 0

    def test_large_state_id(self):
        """State IDs can be large integers (Minecraft 1.21 has ~25000 states)."""
        result = parse_block_state({"id": 24999})
        assert result.state_id == 24999


# ---------------------------------------------------------------------------
# parse_block_states — mirrors the PERFORM loop calling Blocks-Parse-State
# ---------------------------------------------------------------------------

class TestParseBlockStates:
    def test_empty_states_array(self):
        """Empty array produces empty results."""
        assert parse_block_states([]) == []

    def test_single_state(self):
        results = parse_block_states([{"id": 5, "default": True}])
        assert len(results) == 1
        assert results[0].state_id == 5
        assert results[0].is_default is True

    def test_multiple_states_ordered(self):
        """Order preserved — state[0] is first parsed state."""
        data = [
            {"id": 16, "default": False},
            {"id": 17, "default": True},
            {"id": 18, "default": False},
        ]
        results = parse_block_states(data)
        assert [r.state_id for r in results] == [16, 17, 18]
        assert [r.is_default for r in results] == [False, True, False]

    def test_exactly_one_default(self):
        """Minecraft guarantees exactly one default state per block."""
        data = [{"id": i, "default": (i == 3)} for i in range(6)]
        results = parse_block_states(data)
        defaults = [r for r in results if r.is_default]
        assert len(defaults) == 1
        assert defaults[0].state_id == 3


# ---------------------------------------------------------------------------
# find_default_state — mirrors BLOCK-ENTRY-DEFAULT-STATE-ID assignment
# ---------------------------------------------------------------------------

class TestFindDefaultState:
    def test_returns_default_state(self):
        results = [
            BlockStateResult(state_id=10, is_default=False),
            BlockStateResult(state_id=11, is_default=True),
            BlockStateResult(state_id=12, is_default=False),
        ]
        default = find_default_state(results)
        assert default is not None
        assert default.state_id == 11

    def test_no_default_returns_none(self):
        results = [
            BlockStateResult(state_id=5, is_default=False),
            BlockStateResult(state_id=6, is_default=False),
        ]
        assert find_default_state(results) is None

    def test_empty_list_returns_none(self):
        assert find_default_state([]) is None


# ---------------------------------------------------------------------------
# state_id_range — mirrors MOVE MIN/MAX to BLOCK-ENTRY-MINIMUM/MAXIMUM-STATE-ID
# ---------------------------------------------------------------------------

class TestStateIdRange:
    def test_single_state_min_equals_max(self):
        results = [BlockStateResult(state_id=42, is_default=True)]
        lo, hi = state_id_range(results)
        assert lo == 42
        assert hi == 42

    def test_range_across_multiple_states(self):
        """Mirrors BLOCK-ENTRY-MINIMUM-STATE-ID / MAXIMUM-STATE-ID after parsing."""
        results = [
            BlockStateResult(state_id=16, is_default=False),
            BlockStateResult(state_id=17, is_default=True),
            BlockStateResult(state_id=18, is_default=False),
            BlockStateResult(state_id=19, is_default=False),
        ]
        lo, hi = state_id_range(results)
        assert lo == 16
        assert hi == 19

    def test_empty_states_returns_zero_range(self):
        assert state_id_range([]) == (0, 0)

    def test_non_contiguous_ids(self):
        """IDs are not necessarily sequential (sparse state spaces are valid)."""
        results = [
            BlockStateResult(state_id=100, is_default=False),
            BlockStateResult(state_id=500, is_default=True),
            BlockStateResult(state_id=250, is_default=False),
        ]
        lo, hi = state_id_range(results)
        assert lo == 100
        assert hi == 500


# ---------------------------------------------------------------------------
# Integration: realistic blocks.json state entries
# ---------------------------------------------------------------------------

class TestRealisticBlockStateData:
    def test_oak_log_states(self):
        """oak_log has 3 axis values x 2 stripped states = 6 states total."""
        states = [
            {"id": 84, "default": False},
            {"id": 85, "default": False},
            {"id": 86, "default": True},
            {"id": 87, "default": False},
            {"id": 88, "default": False},
            {"id": 89, "default": False},
        ]
        results = parse_block_states(states)
        assert len(results) == 6
        lo, hi = state_id_range(results)
        assert lo == 84
        assert hi == 89
        default = find_default_state(results)
        assert default is not None
        assert default.state_id == 86

    def test_air_single_state(self):
        """Air has exactly one state (id=0, default=true)."""
        results = parse_block_states([{"id": 0, "default": True}])
        assert len(results) == 1
        assert results[0].state_id == 0
        assert results[0].is_default is True
        assert state_id_range(results) == (0, 0)
