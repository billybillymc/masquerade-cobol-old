# IQ-11: COBOL Test Runner — End-to-End Behavioral Equivalence

**Status**: Planned
**Created**: 2026-03-15
**Prerequisites**: IQ-02 (copybook byte layouts), IQ-03 (CobolDecimal for record packing), IQ-09 (differential harness)

---

## Problem Statement

The differential harness (IQ-09) can compare expected vs actual outputs, but there
is no automated way to **produce** the golden expected outputs. Today, golden vectors
must be hand-crafted. The only authoritative source of correct behavior is the
COBOL program itself — compile it, feed it input, capture its output, and that
becomes the oracle.

The goal: a single command that takes a COBOL program + mock input data, runs it
through both the original COBOL and the modern reimplementation, and produces a
field-by-field equivalence report with a confidence score.

### Evidence

CardDemo has 44 programs. Batch programs like CODATE01 (date utility), CBACT01C
(account file processing), CBTRN01C (transaction processing) are pure computation
with sequential file I/O — no CICS dependency. These can be compiled with
GnuCOBOL and executed standalone.

CICS programs like COSGN00C, COACTUPC depend on `EXEC CICS` API calls that require
a CICS runtime. These cannot run standalone without a stub layer.

---

## Two-Phase Plan

### Phase 1: Batch Programs (No CICS)

**Scope**: Batch programs that use sequential file I/O and/or CALL statements.
No EXEC CICS, no DB2, no BMS screens.

**Candidates from CardDemo**:
- `CODATE01` — date format conversion utility (pure computation, no file I/O)
- `CBACT01C` — account file processing (sequential READ/WRITE)
- `CBCUS01C` — customer file processing (sequential READ/WRITE)
- `CBTRN01C` — transaction file processing (sequential READ/WRITE)
- `CBTRN02C` — transaction posting with balance calculation (sequential + COMPUTE)
- `CBTRN03C` — transaction report generation (sequential + COMPUTE + WRITE)
- `CBACT04C` — interest calculation batch (COMPUTE with S9(09)V99 fields)

**What gets built**:

#### 1. Record Packer/Unpacker (`pipeline/record_io.py`)

Converts between Python dicts and fixed-width COBOL records using copybook metadata.

```python
# Pack: Python dict → bytes matching copybook layout
record_bytes = pack_record(
    {"ACCT-ID": "12345678901", "ACCT-CURR-BAL": Decimal("5000.00"), ...},
    copybook="CVACT01Y",
    copybook_dict=cbd,
)
# Result: 300 bytes exactly matching ACCOUNT-RECORD layout

# Unpack: bytes → Python dict
fields = unpack_record(record_bytes, copybook="CVACT01Y", copybook_dict=cbd)
# Result: {"ACCT-ID": "12345678901", "ACCT-CURR-BAL": Decimal("5000.00"), ...}
```

**Implementation details**:
- Uses IQ-02 copybook field metadata (PIC, USAGE, size_bytes) for byte offsets
- DISPLAY fields: ASCII/EBCDIC character encoding (GnuCOBOL uses ASCII)
- COMP fields: binary encoding (2/4/8 bytes, big-endian)
- COMP-3 fields: packed decimal encoding (nibble-per-digit + sign nibble)
- FILLER: zero-filled padding at correct byte offsets
- Group items: recursively pack/unpack children
- OCCURS: repeated sub-records at correct stride

**Key challenge**: Computing byte offsets. Each field's offset is the sum of all
preceding sibling fields' `size_bytes`. Group items have no size of their own —
their size is the sum of their children. IQ-02's `CopybookField.size_bytes`
already computes per-field sizes.

#### 2. COBOL Compiler Wrapper (`pipeline/cobol_runner.py`)

Wraps GnuCOBOL (`cobc`) to compile and execute batch programs.

```python
result = compile_and_run(
    source_file="test-codebases/carddemo/app/cbl/CBACT01C.cbl",
    copybook_dirs=["test-codebases/carddemo/app/cpy"],
    input_files={"INFILE": "/tmp/test_input.dat"},
    output_files={"OUTFILE": "/tmp/test_output.dat"},
    timeout=30,
)
# result.return_code, result.stdout, result.stderr, result.output_files
```

**Implementation details**:
- `cobc -x -std=ibm -I <copybook_dirs> -o <binary> <source.cbl>` to compile
- Execute the compiled binary with environment variables for file assignments
  (GnuCOBOL uses `DD_<filename>` or `COB_FILE_<name>` for file mapping)
- Capture stdout/stderr and output files
- Timeout protection (batch jobs shouldn't run forever)
- Temp directory management for input/output files
- Return code capture (COBOL STOP RUN / GOBACK return code)

**GnuCOBOL specifics**:
- `-std=ibm` for IBM COBOL compatibility mode
- `-I <dir>` for COPY statement resolution
- File assignment via environment variables: `export DD_INFILE=/path/to/file`
- Sequential files are just flat text files with fixed-width records
- Indexed files (VSAM equivalent) use GnuCOBOL's built-in ISAM support

**What we skip in Phase 1**:
- No EXEC CICS (filtered out at program selection)
- No EXEC SQL / DB2 (filtered out at program selection)
- No CALL to external programs that aren't available (mock with stubs)

#### 3. Golden Vector Generator (`pipeline/golden_generator.py`)

Orchestrates: mock data → pack → COBOL compile+run → unpack → save as golden vectors.

```python
vectors = generate_golden_vectors(
    program="CBACT01C",
    codebase_dir="test-codebases/carddemo",
    test_cases=[
        {"input_file": "ACCTFILE", "input_records": [
            {"ACCT-ID": "12345678901", "ACCT-ACTIVE-STATUS": "Y", "ACCT-CURR-BAL": "5000.00", ...},
        ]},
        {"input_file": "ACCTFILE", "input_records": [
            {"ACCT-ID": "99999999999", "ACCT-ACTIVE-STATUS": "N", "ACCT-CURR-BAL": "0.00", ...},
        ]},
    ],
)
# Saves to _analysis/golden_vectors/CBACT01C.json
# Each vector has: inputs (what we fed), expected_outputs (what COBOL produced)
```

**Test case generation strategy**:
- **Boundary values**: max PIC values (99999.99 for S9(5)V99), zero, negative
- **Happy path**: typical valid records
- **Error path**: invalid status codes, missing fields (SPACES)
- Use IQ-02 field metadata to auto-generate boundary test data

#### 4. Integration with Differential Harness (IQ-09)

The golden vectors feed directly into the existing differential harness:

```python
# Load golden vectors (produced by Phase 1)
golden = load_golden_vectors("CBACT01C", "_analysis/golden_vectors")

# Run the modern reimplementation with the same inputs
for vec in golden:
    vec.actual_outputs = run_modern_implementation("CBACT01C", vec.inputs)

# Compare
report = run_vectors(golden)
print(render_report_text(report))
# Confidence: 95.0% (19/20 vectors passed)
# Mismatch V014: ACCT-CURR-BAL expected=4999.99 actual=5000.00 (Decimal)
```

#### Phase 1 Deliverables

| Module | Purpose | Tests |
|--------|---------|-------|
| `record_io.py` | Pack/unpack Python dicts ↔ fixed-width COBOL records | PIC X, 9, S9V99, COMP, COMP-3, OCCURS, FILLER padding |
| `cobol_runner.py` | Compile with cobc + execute + capture output | Compile success, run with input, timeout, error handling |
| `golden_generator.py` | Orchestrate mock→pack→run→unpack→save | CODATE01 end-to-end, CBACT01C with boundary values |

**Phase 1 exit criteria**: At least one carddemo batch program (CODATE01 or
CBACT01C) compiles with GnuCOBOL, runs with mock input, produces output, and
the output is saved as golden vectors that the differential harness validates
at 100% confidence against a re-run.

---

### Phase 2: CICS Programs (Stub Layer)

**Scope**: CICS online programs that use EXEC CICS operations. These cannot run
standalone — they need a runtime for READ/WRITE/SEND/RECEIVE/XCTL/LINK/RETURN.

**Candidates from CardDemo**:
- `COSGN00C` — sign-on (READ user file, XCTL to admin/menu)
- `COACTUPC` — account update (READ/REWRITE account+customer files, SEND/RECEIVE MAP)
- `COUSR00C` — user list (STARTBR/READNEXT/ENDBR user file, SEND MAP)
- `COTRN00C` — transaction list (STARTBR/READNEXT transaction file)
- All 20+ CICS programs in CardDemo

**What gets built**:

#### 1. CICS Stub Preprocessor (`pipeline/cics_stub.py`)

Rewrites EXEC CICS commands into plain COBOL file I/O that GnuCOBOL can compile.

```
BEFORE (original CICS):
    EXEC CICS READ
        DATASET   (WS-USRSEC-FILE)
        INTO      (SEC-USER-DATA)
        RIDFLD    (WS-USER-ID)
        RESP      (WS-RESP-CD)
    END-EXEC.

AFTER (stubbed):
    READ USRSEC-FILE INTO SEC-USER-DATA
        KEY IS WS-USER-ID
        INVALID KEY
            MOVE 13 TO WS-RESP-CD
        NOT INVALID KEY
            MOVE 0 TO WS-RESP-CD
    END-READ.
```

**CICS operation mapping**:

| CICS Operation | Stub Replacement | Notes |
|----------------|-----------------|-------|
| `READ DATASET INTO RIDFLD RESP` | `READ file INTO KEY IS INVALID KEY` | RESP 0=found, 13=not found |
| `WRITE DATASET FROM` | `WRITE file FROM` | Sequential or indexed write |
| `REWRITE DATASET FROM` | `REWRITE file FROM` | Update in place |
| `DELETE DATASET RIDFLD` | `DELETE file KEY IS` | Delete by key |
| `STARTBR DATASET RIDFLD` | (set browse flag) | State tracking |
| `READNEXT INTO` | `READ file NEXT INTO` | Sequential forward read |
| `ENDBR` | (clear browse flag) | No-op |
| `SEND MAP MAPSET` | `WRITE MOCK-SCREEN-FILE FROM <map-output>` | Capture screen output to file |
| `RECEIVE MAP MAPSET` | `READ MOCK-SCREEN-FILE INTO <map-input>` | Feed screen input from file |
| `XCTL PROGRAM COMMAREA` | `CALL program USING COMMAREA` | Convert transfer to CALL |
| `LINK PROGRAM COMMAREA` | `CALL program USING COMMAREA` | Same as XCTL for testing |
| `RETURN TRANSID` | `STOP RUN` | End the program |
| `ASSIGN APPLID/SYSID` | `MOVE 'TEST' TO target` | Mock system values |
| `HANDLE AID/CONDITION` | (remove, handle inline) | Not needed for testing |

**Implementation details**:
- Source-to-source transformation: read .cbl, regex-replace EXEC CICS blocks,
  write stubbed .cbl
- Add FILE CONTROL entries for each DATASET referenced (SELECT ... ASSIGN TO ...)
- Add FD entries in FILE SECTION for each file
- Map DATASET names to physical files via environment variables
- RESP code simulation: INVALID KEY → RESP 13, successful → RESP 0
- COMMAREA passing: XCTL becomes CALL USING, preserving data flow
- Screen I/O: SEND MAP writes the output record to a mock file,
  RECEIVE MAP reads input record from a mock file

**Key challenges**:
- EXEC CICS spans multiple lines with continuations
- RESP/RESP2 must be set correctly (0 for success, 13 for NOTFND, etc.)
- Some programs check EIBRESP directly instead of RESP — need to set DFHEIBLK fields
- XCTL transfers control and doesn't return — CALL does return. For testing
  purposes this is acceptable since we're checking data state, not control flow.
- BMS maps have complex field layouts — the stub needs to pack/unpack the
  symbolic map fields (COSGN0AI/COSGN0AO) to/from a flat file

#### 2. VSAM File Simulator

GnuCOBOL supports indexed files natively (ORGANIZATION IS INDEXED, ACCESS MODE
IS DYNAMIC, RECORD KEY IS ...). The stub preprocessor adds the FILE CONTROL
entries, and GnuCOBOL handles the indexed access.

For testing, seed indexed files with known test data:
```python
seed_vsam_file(
    file_path="/tmp/usrsec.dat",
    copybook="CSUSR01Y",
    records=[
        {"SEC-USR-ID": "ADMIN001", "SEC-USR-PWD": "PASSWORD", "SEC-USR-TYPE": "A"},
        {"SEC-USR-ID": "USER0001", "SEC-USR-PWD": "PASS1234", "SEC-USR-TYPE": "U"},
    ],
    key_field="SEC-USR-ID",
    copybook_dict=cbd,
)
```

Uses `record_io.py` (from Phase 1) to pack records, then writes them as an
indexed file that GnuCOBOL can read.

#### 3. Screen I/O Simulator

BMS SEND/RECEIVE become file writes/reads:
- **SEND MAP**: Pack the symbolic output map fields into a record, write to
  `MOCK-SCREEN-OUT.dat`. The test harness reads this file to verify what the
  program would have displayed.
- **RECEIVE MAP**: Pack mock user input into a record, write to
  `MOCK-SCREEN-IN.dat` before running the program. The stub reads this
  file when RECEIVE MAP is executed.

The BMS map field layouts (from IQ-07's `api_contract_mapper.py`) define which
fields are input vs output and their positions.

#### 4. End-to-End CICS Test Flow

```python
# 1. Preprocess: stub out CICS commands
stubbed_source = preprocess_cics(
    source="test-codebases/carddemo/app/cbl/COSGN00C.cbl",
    copybook_dirs=["test-codebases/carddemo/app/cpy"],
)

# 2. Seed data files
seed_vsam_file("usrsec.dat", "CSUSR01Y", [
    {"SEC-USR-ID": "ADMIN001", "SEC-USR-PWD": "PASSWORD", "SEC-USR-TYPE": "A"},
])

# 3. Prepare screen input (simulates user typing ADMIN001 + PASSWORD)
write_screen_input("screen_in.dat", "COSGN00", {
    "USERID": "ADMIN001", "PASSWD": "PASSWORD",
})

# 4. Compile and run
result = compile_and_run(stubbed_source, input_files={
    "USRSEC-FILE": "usrsec.dat",
    "SCREEN-IN": "screen_in.dat",
    "SCREEN-OUT": "screen_out.dat",
    "COMMAREA-OUT": "commarea.dat",
})

# 5. Read outputs
screen_output = read_screen_output("screen_out.dat", "COSGN00")
commarea = unpack_record(read("commarea.dat"), "COCOM01Y", cbd)

# 6. Verify
assert result.return_code == 0
assert commarea["CDEMO-USER-ID"] == "ADMIN001"
assert commarea["CDEMO-USER-TYPE"] == "A"
# This means: admin login successful, routed to COADM01C
```

#### Phase 2 Deliverables

| Module | Purpose | Tests |
|--------|---------|-------|
| `cics_stub.py` | Source-to-source EXEC CICS → plain COBOL transformation | Each CICS op type stubbed correctly |
| `vsam_simulator.py` | Seed/read indexed files for GnuCOBOL | Indexed file CREATE/READ/WRITE/DELETE round-trip |
| `screen_simulator.py` | Pack/unpack BMS map fields for mock screen I/O | SEND MAP capture, RECEIVE MAP injection |
| Update `cobol_runner.py` | Handle stubbed CICS programs | Compile stubbed source, seed files, run, capture |
| Update `golden_generator.py` | Generate golden vectors for CICS programs | COSGN00C login scenarios (admin, user, wrong password, not found) |

**Phase 2 exit criteria**: COSGN00C compiles with stubbed CICS, runs with mock
user security file and screen input, produces correct COMMAREA output and screen
output for all 4 login scenarios (admin success, regular success, wrong password,
user not found), and these are saved as golden vectors that pass the differential
harness at 100%.

---

## Dependency Chain

```
Phase 1                          Phase 2
-------                          -------
record_io.py                     cics_stub.py
    |                                |
    v                                v
cobol_runner.py  -------->  cobol_runner.py (extended)
    |                                |
    v                                v
golden_generator.py ------>  golden_generator.py (extended)
    |                                |
    v                                v
differential_harness.py      differential_harness.py
(IQ-09, already built)       (same module, more vectors)
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| GnuCOBOL not installed on CI | Phase 1 blocked | `pytest.mark.skipif(not shutil.which('cobc'))` — tests skip gracefully |
| CardDemo uses IBM-specific COBOL extensions | Compilation failure | `-std=ibm` flag + manual fixups for unsupported extensions |
| COMP-3 packing is byte-order sensitive | Wrong numeric values | Test against known COMP-3 encodings from COBOL standard |
| CICS stub doesn't perfectly simulate RESP codes | False positives/negatives in Phase 2 | Map all RESP codes from IBM CICS documentation, test each |
| XCTL-to-CALL conversion changes control flow | Program behaves differently | Acceptable for data-state testing; note limitation in report |
| BMS symbolic map layout differs from runtime | Wrong screen field packing | Cross-reference with BMS parser output (IQ-07) |
| EBCDIC vs ASCII encoding | Character data mismatch | GnuCOBOL uses ASCII natively — no conversion needed |

## Success Metrics

- **Phase 1**: 3+ batch programs compile and run, 50+ golden vectors generated,
  differential harness validates at 100% on re-run
- **Phase 2**: 5+ CICS programs compile with stubs and run, 100+ golden vectors
  generated, differential harness validates at 95%+ on re-run (allowing for
  XCTL/control flow limitations)
- **Ultimate goal**: When a developer implements a skeleton, they run
  `python -m pipeline.test_equivalence COSGN00C` and get a confidence score
  with per-field mismatch details
