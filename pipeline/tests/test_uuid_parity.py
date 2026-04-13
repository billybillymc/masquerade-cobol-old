"""Cross-language parity tests for CobolCraft UUID encoder/decoder.

Fifth Java reimplementation, third source codebase exercised (CardDemo,
CBSA, and now CobolCraft). UUID is pure binary/string conversion — no
arithmetic, no state, no decision tree. The gate here is byte-for-byte
equality on hex encoding and dash-positioning across many vectors.
"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from differential_harness import DiffVector, run_vectors
from vector_runner import (
    JavaRunner,
    PythonRunner,
    RunRequest,
    populate_actuals,
)


RUNNER_JAR = (
    Path(__file__).resolve().parent.parent
    / "reimpl" / "java" / "runner" / "target" / "masquerade-runner.jar"
)
JAVA_BIN = "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot/bin/java.exe"


def _java_available() -> bool:
    return RUNNER_JAR.exists() and Path(JAVA_BIN).exists()


def _make_java_runner() -> JavaRunner:
    return JavaRunner(jar_path=RUNNER_JAR, java_bin=JAVA_BIN)


# Module-level singletons so we don't pay constructor cost per test.
PYTHON = PythonRunner()
JAVA = _make_java_runner() if _java_available() else None


def _check_parity(vector_id: str, inputs: dict) -> None:
    """Run the same vector through Python and Java; assert outputs identical."""
    req = RunRequest(program="UUID", vector_id=vector_id, inputs=inputs)
    py = PYTHON.run(req)
    jv = JAVA.run(req)

    assert py.ok, f"{vector_id}: Python errored: {py.errors}"
    assert jv.ok, f"{vector_id}: Java errored: {jv.errors}"

    if py.outputs != jv.outputs:
        lines = [f"{vector_id}: mismatch for inputs {inputs}"]
        for k in sorted(set(py.outputs) | set(jv.outputs)):
            pv = py.outputs.get(k, "<missing>")
            jv_v = jv.outputs.get(k, "<missing>")
            if pv != jv_v:
                lines.append(f"  {k}:")
                lines.append(f"    python: {pv!r}")
                lines.append(f"    java:   {jv_v!r}")
        pytest.fail("\n".join(lines))


# ── to_string: bytes → UUID string ────────────────────────────────────────


# (vector_id, hex_bytes, expected_uuid_string, description)
TO_STRING_CASES = [
    ("TS_ALL_ZEROS",  "00000000000000000000000000000000",
     "00000000-0000-0000-0000-000000000000", "All zero bytes"),
    ("TS_ALL_ONES",   "ffffffffffffffffffffffffffffffff",
     "ffffffff-ffff-ffff-ffff-ffffffffffff", "All 0xFF bytes"),
    ("TS_RFC_4122",   "550e8400e29b41d4a716446655440000",
     "550e8400-e29b-41d4-a716-446655440000", "RFC 4122 example"),
    ("TS_NIL_UUID",   "00000000000000000000000000000001",
     "00000000-0000-0000-0000-000000000001", "Nil+1"),
    ("TS_SEQUENTIAL", "000102030405060708090a0b0c0d0e0f",
     "00010203-0405-0607-0809-0a0b0c0d0e0f", "Sequential bytes 0-15"),
    ("TS_HIGH_BYTE",  "7f80818283848586878889abcdef0123",
     "7f808182-8384-8586-8788-89abcdef0123", "High-bit transition"),
    ("TS_V4_SAMPLE",  "f47ac10b58cc4372a5670e02b2c3d479",
     "f47ac10b-58cc-4372-a567-0e02b2c3d479", "UUID v4 sample"),
    ("TS_MSB_ALL_SET", "ff00ff00ff00ff00ff00ff00ff00ff00",
     "ff00ff00-ff00-ff00-ff00-ff00ff00ff00", "Alternating FF/00"),
]


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestUuidToStringParity:
    """uuid_to_string: byte-identical 16-byte → 36-char conversion."""

    @pytest.mark.parametrize("vector_id,hex_bytes,expected,desc", TO_STRING_CASES)
    def test_to_string_parity(self, vector_id, hex_bytes, expected, desc):
        _check_parity(vector_id, {"op": "to_string", "HEX_BYTES": hex_bytes})

    @pytest.mark.parametrize("vector_id,hex_bytes,expected,desc", TO_STRING_CASES)
    def test_to_string_matches_expected(self, vector_id, hex_bytes, expected, desc):
        """Also verify Java produces the exact expected string (not just matches Python)."""
        jv = JAVA.run(RunRequest(
            program="UUID", vector_id=vector_id,
            inputs={"op": "to_string", "HEX_BYTES": hex_bytes},
        ))
        assert jv.ok, jv.errors
        assert jv.outputs["UUID_STRING"] == expected, desc


# ── from_string: UUID string → bytes ──────────────────────────────────────


# (vector_id, uuid_string, expected_hex_bytes, description)
FROM_STRING_CASES = [
    ("FS_ALL_ZEROS", "00000000-0000-0000-0000-000000000000",
     "00000000000000000000000000000000", "All zero bytes"),
    ("FS_ALL_ONES",  "ffffffff-ffff-ffff-ffff-ffffffffffff",
     "ffffffffffffffffffffffffffffffff", "All 0xFF bytes"),
    ("FS_RFC_4122",  "550e8400-e29b-41d4-a716-446655440000",
     "550e8400e29b41d4a716446655440000", "RFC 4122 example"),
    ("FS_V4_SAMPLE", "f47ac10b-58cc-4372-a567-0e02b2c3d479",
     "f47ac10b58cc4372a5670e02b2c3d479", "UUID v4 sample"),
    ("FS_UPPERCASE", "550E8400-E29B-41D4-A716-446655440000",
     "550e8400e29b41d4a716446655440000", "Uppercase input → lowercase output"),
    ("FS_MIXED",     "550e8400-E29B-41d4-a716-446655440000",
     "550e8400e29b41d4a716446655440000", "Mixed case input"),
]


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestUuidFromStringParity:
    """uuid_from_string: case-insensitive 36-char → 16-byte conversion."""

    @pytest.mark.parametrize("vector_id,uuid_str,expected,desc", FROM_STRING_CASES)
    def test_from_string_parity(self, vector_id, uuid_str, expected, desc):
        _check_parity(vector_id, {"op": "from_string", "UUID_STRING": uuid_str})

    @pytest.mark.parametrize("vector_id,uuid_str,expected,desc", FROM_STRING_CASES)
    def test_from_string_matches_expected(self, vector_id, uuid_str, expected, desc):
        jv = JAVA.run(RunRequest(
            program="UUID", vector_id=vector_id,
            inputs={"op": "from_string", "UUID_STRING": uuid_str},
        ))
        assert jv.ok, jv.errors
        assert jv.outputs["HEX_BYTES"] == expected, desc


# ── Round-trip: to_string . from_string == identity ───────────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestUuidRoundTrip:
    """Round-trip consistency: encoding + decoding preserves the original bytes."""

    def test_roundtrip_via_java(self):
        """Run a batch of random UUIDs through Java's to_string then from_string
        and assert the output bytes match the input."""
        rng = random.Random(20260409)
        for i in range(15):
            original_bytes = bytes(rng.randint(0, 255) for _ in range(16))
            original_hex = original_bytes.hex()

            to_str = JAVA.run(RunRequest(
                program="UUID", vector_id=f"RT_{i}_TO",
                inputs={"op": "to_string", "HEX_BYTES": original_hex},
            ))
            assert to_str.ok, to_str.errors
            uuid_str = to_str.outputs["UUID_STRING"]
            assert len(uuid_str) == 36

            from_str = JAVA.run(RunRequest(
                program="UUID", vector_id=f"RT_{i}_FROM",
                inputs={"op": "from_string", "UUID_STRING": uuid_str},
            ))
            assert from_str.ok, from_str.errors
            assert from_str.outputs["HEX_BYTES"] == original_hex, (
                f"RT_{i}: round-trip lost data. "
                f"original={original_hex}, after round-trip={from_str.outputs['HEX_BYTES']}"
            )

    def test_dashes_only_at_positions_8_13_18_23(self):
        """The COBOL inserts dashes after bytes 4, 6, 8, 10 (1-based).
        In the 36-char output that's positions 8, 13, 18, 23 (0-based).
        Verify this is consistent across all test vectors."""
        for vid, hex_bytes, _expected, _desc in TO_STRING_CASES:
            jv = JAVA.run(RunRequest(
                program="UUID", vector_id=vid,
                inputs={"op": "to_string", "HEX_BYTES": hex_bytes},
            ))
            s = jv.outputs["UUID_STRING"]
            dash_positions = [i for i, c in enumerate(s) if c == "-"]
            assert dash_positions == [8, 13, 18, 23], (
                f"{vid}: dashes at unexpected positions {dash_positions}"
            )


# ── Randomized fuzz ────────────────────────────────────────────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestUuidRandomFuzz:
    """Fixed-seed random UUIDs across both operations."""

    SEED = 20260409
    NUM_VECTORS = 20

    def test_random_to_string(self):
        rng = random.Random(self.SEED)
        for i in range(self.NUM_VECTORS):
            hex_bytes = bytes(rng.randint(0, 255) for _ in range(16)).hex()
            _check_parity(f"FUZZ_TS_{i}", {"op": "to_string", "HEX_BYTES": hex_bytes})

    def test_random_from_string(self):
        rng = random.Random(self.SEED + 1)
        for i in range(self.NUM_VECTORS):
            raw = bytes(rng.randint(0, 255) for _ in range(16)).hex()
            # Format as UUID string
            uuid_str = (
                f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"
            )
            _check_parity(f"FUZZ_FS_{i}", {"op": "from_string", "UUID_STRING": uuid_str})


# ── Differential harness with hand-derived expected outputs ───────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestUuidThroughHarness:
    """End-to-end: the differential harness at 100% confidence."""

    def test_all_at_100_percent(self):
        vectors = []
        for vid, hex_bytes, expected, _desc in TO_STRING_CASES:
            vectors.append(DiffVector(
                vector_id=vid,
                program="UUID",
                inputs={"op": "to_string", "HEX_BYTES": hex_bytes},
                expected_outputs={"UUID_STRING": expected, "error": ""},
                actual_outputs={},
                field_types={"UUID_STRING": "str", "error": "str"},
            ))
        for vid, uuid_str, expected, _desc in FROM_STRING_CASES:
            vectors.append(DiffVector(
                vector_id=vid,
                program="UUID",
                inputs={"op": "from_string", "UUID_STRING": uuid_str},
                expected_outputs={"HEX_BYTES": expected, "error": ""},
                actual_outputs={},
                field_types={"HEX_BYTES": "str", "error": "str"},
            ))

        populate_actuals(vectors, JAVA)
        report = run_vectors(vectors)

        assert report.confidence_score == 100.0, (
            f"UUID Java pilot failed: {report.failed} of {report.total_vectors} "
            f"vectors mismatched.\nMismatches: {report.mismatches}"
        )
        assert report.failed == 0


# ── Python-side independent sanity ────────────────────────────────────────


class TestPythonRunVectorWorks:
    def test_python_roundtrip(self):
        to_str = PYTHON.run(RunRequest(
            program="UUID", vector_id="V1",
            inputs={"op": "to_string", "HEX_BYTES": "deadbeefcafebabe0123456789abcdef"},
        ))
        assert to_str.ok
        assert to_str.outputs["UUID_STRING"] == "deadbeef-cafe-babe-0123-456789abcdef"

        from_str = PYTHON.run(RunRequest(
            program="UUID", vector_id="V2",
            inputs={"op": "from_string",
                    "UUID_STRING": to_str.outputs["UUID_STRING"]},
        ))
        assert from_str.ok
        assert from_str.outputs["HEX_BYTES"] == "deadbeefcafebabe0123456789abcdef"
