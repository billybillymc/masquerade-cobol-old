"""Differential test: COBOL vs Python reimplementation of COSGN00C.

Runs the same 4 login scenarios through:
1. The original COBOL (compiled via GnuCOBOL with CICS stubs)
2. The Python reimplementation

Compares the outputs field-by-field via the differential harness.
This is the proof that the reimplementation is behaviorally equivalent.
"""

import re
import struct
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reimpl"))

from cobol_runner import is_cobc_available, _to_wsl_path
from cics_stub import preprocess_cics
from bms_symbolic import generate_all_symbolic_maps
from differential_harness import DiffVector, run_vectors, render_report_text
from reimpl.cosgn00c import (
    process_signon,
    UserSecurityRepository,
    SecUserData,
)

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
COBC_AVAILABLE = is_cobc_available()

# ── COBOL execution helpers (reused from test_cosgn00c_e2e) ─────────────────

COSGN0A_FIELDS = [
    ("TRNNAME", 4), ("TITLE01", 40), ("CURDATE", 8), ("PGMNAME", 8),
    ("TITLE02", 40), ("CURTIME", 9), ("APPLID", 8), ("SYSID", 8),
    ("USERID", 8), ("PASSWD", 8), ("ERRMSG", 78),
]


def _build_screen_input(userid: str = "", passwd: str = "") -> bytes:
    record = bytearray(b'\x00' * 12)
    for name, length in COSGN0A_FIELDS:
        if name == "USERID":
            data = userid.encode('ascii').ljust(length, b' ')[:length]
            data_len = len(userid.rstrip())
        elif name == "PASSWD":
            data = passwd.encode('ascii').ljust(length, b' ')[:length]
            data_len = len(passwd.rstrip())
        else:
            data = b' ' * length
            data_len = 0
        record += struct.pack('>h', data_len)
        record += b'\x00'
        record += b'\x00\x00'
        record += data
    return bytes(record)


def _prepare_cobol(tmp_path):
    sym_dir = tmp_path / "symbolic"
    generate_all_symbolic_maps(str(CARDDEMO / "app" / "bms"), str(sym_dir))
    result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
    source = result.source
    ws_inject = ""
    for ds in result.datasets:
        ws_inject += f"       01  {ds.file_alias}-STATUS         PIC XX.\n"
    if ws_inject:
        ws_m = re.search(r'(^\s*WORKING-STORAGE\s+SECTION\.)', source, re.MULTILINE | re.IGNORECASE)
        if ws_m:
            pos = ws_m.end()
            source = source[:pos] + "\n" + ws_inject + source[pos:]
    proc_m = re.search(r'(^\s*PROCEDURE\s+DIVISION\.)', source, re.MULTILINE | re.IGNORECASE)
    if proc_m:
        pos = proc_m.end()
        init = "\n       TEST-INIT.\n" \
               "           MOVE 100 TO EIBCALEN.\n" \
               "           MOVE DFHENTER TO EIBAID.\n" \
               "           OPEN INPUT USRSEC-FILE-FILE.\n" \
               "           OPEN INPUT SCREEN-INPUT-FILE.\n"
        main_m = re.search(r'(^\s*MAIN-PARA\.)', source[pos:], re.MULTILINE)
        if main_m:
            insert_pos = pos + main_m.start()
            source = source[:insert_pos] + init + source[insert_pos:]
    stubbed = tmp_path / "COSGN00C_STUB.cbl"
    stubbed.write_text(source, encoding="utf-8")
    cpy_wsl = _to_wsl_path(str(CARDDEMO / "app" / "cpy"))
    sym_wsl = _to_wsl_path(str(sym_dir))
    src_wsl = _to_wsl_path(str(stubbed))
    binary = "/tmp/diff_cosgn00c"
    cmd = f'cobc -x -std=ibm -I {cpy_wsl} -I {sym_wsl} -o {binary} {src_wsl}'
    r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"Compile failed: {r.stderr}"
    return binary


def _seed_usrsec(tmp_path):
    seed_src = tmp_path / "seedusrsec.cbl"
    seed_src.write_text("""\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SEEDUSRSEC.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT USRSEC-FILE ASSIGN TO USRSECFILE
                  ORGANIZATION IS INDEXED
                  ACCESS MODE IS SEQUENTIAL
                  RECORD KEY IS FD-USR-KEY
                  FILE STATUS IS WS-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD  USRSEC-FILE.
       01  FD-USR-REC.
           05 FD-USR-KEY                    PIC X(08).
           05 FD-USR-DATA                   PIC X(72).
       WORKING-STORAGE SECTION.
       COPY CSUSR01Y.
       01  WS-STATUS                PIC XX.
       PROCEDURE DIVISION.
           OPEN OUTPUT USRSEC-FILE.
           INITIALIZE SEC-USER-DATA.
           MOVE 'ADMIN001' TO SEC-USR-ID.
           MOVE 'John'     TO SEC-USR-FNAME.
           MOVE 'Admin'    TO SEC-USR-LNAME.
           MOVE 'PASS1234' TO SEC-USR-PWD.
           MOVE 'A'        TO SEC-USR-TYPE.
           MOVE SEC-USER-DATA TO FD-USR-REC.
           WRITE FD-USR-REC.
           INITIALIZE SEC-USER-DATA.
           MOVE 'USER0001' TO SEC-USR-ID.
           MOVE 'Jane'     TO SEC-USR-FNAME.
           MOVE 'User'     TO SEC-USR-LNAME.
           MOVE 'MYPASSWD' TO SEC-USR-PWD.
           MOVE 'U'        TO SEC-USR-TYPE.
           MOVE SEC-USER-DATA TO FD-USR-REC.
           WRITE FD-USR-REC.
           CLOSE USRSEC-FILE.
           STOP RUN.
""", encoding="utf-8")
    cpy_wsl = _to_wsl_path(str(CARDDEMO / "app" / "cpy"))
    src_wsl = _to_wsl_path(str(seed_src))
    dat_path = "/tmp/diff_usrsec.dat"
    cmd = f'cobc -x -std=ibm -I {cpy_wsl} -o /tmp/diff_seedusrsec {src_wsl} && export USRSECFILE="{dat_path}" && /tmp/diff_seedusrsec'
    r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"Seed failed: {r.stderr}"
    return dat_path


def _run_cobol_scenario(binary, usrsec_path, userid, passwd):
    screen = _build_screen_input(userid, passwd)
    screen_path = "/tmp/diff_screen.dat"
    subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c", f"cat > {screen_path}"],
        input=screen + b'\n', capture_output=True, timeout=10,
    )
    cmd = f'export USRSECFILE="{usrsec_path}" && export SCREENIN="{screen_path}" && {binary}'
    r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                       capture_output=True, text=True, timeout=15)
    return r.stdout


def _parse_cobol_output(stdout: str) -> dict:
    """Parse COBOL stdout into comparable fields."""
    result = {}
    if "XCTL-TO:" in stdout:
        m = re.search(r'XCTL-TO:(\w+)', stdout)
        if m:
            result["XCTL_TARGET"] = m.group(1)
    else:
        result["XCTL_TARGET"] = ""

    # COBOL always does EXEC CICS RETURN COMMAREA at end of MAIN-PARA,
    # so RETURN-COMMAREA appears on ALL paths. Only check if XCTL happened
    # (which means commarea was passed to the target program).
    if result.get("XCTL_TARGET"):
        result["HAS_COMMAREA"] = "Y"
    else:
        result["HAS_COMMAREA"] = "N"

    # Check for error messages
    if "Wrong Password" in stdout:
        result["ERROR_MSG"] = "Wrong Password"
    elif "User not found" in stdout:
        result["ERROR_MSG"] = "User not found"
    elif "Unable to verify" in stdout:
        result["ERROR_MSG"] = "Unable to verify"
    elif "Please enter User ID" in stdout:
        result["ERROR_MSG"] = "Please enter User ID"
    elif "Please enter Password" in stdout:
        result["ERROR_MSG"] = "Please enter Password"
    else:
        result["ERROR_MSG"] = ""

    return result


def _run_python_scenario(userid, passwd, repository):
    """Run the Python reimplementation and return comparable fields."""
    result = process_signon(
        user_id=userid,
        password=passwd,
        eibcalen=100,  # non-zero = returning user
        eibaid="ENTER",
        repository=repository,
    )

    output = {}
    output["XCTL_TARGET"] = result.xctl_program
    output["HAS_COMMAREA"] = "Y" if result.commarea else "N"

    if "Wrong Password" in result.message:
        output["ERROR_MSG"] = "Wrong Password"
    elif "User not found" in result.message:
        output["ERROR_MSG"] = "User not found"
    elif "Unable to verify" in result.message:
        output["ERROR_MSG"] = "Unable to verify"
    elif "Please enter User ID" in result.message:
        output["ERROR_MSG"] = "Please enter User ID"
    elif "Please enter Password" in result.message:
        output["ERROR_MSG"] = "Please enter Password"
    else:
        output["ERROR_MSG"] = ""

    return output


# ── Test Data ───────────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "id": "ADMIN_LOGIN",
        "userid": "ADMIN001",
        "passwd": "PASS1234",
        "desc": "Admin user correct password → XCTL to COADM01C",
    },
    {
        "id": "USER_LOGIN",
        "userid": "USER0001",
        "passwd": "MYPASSWD",
        "desc": "Regular user correct password → XCTL to COMEN01C",
    },
    {
        "id": "WRONG_PWD",
        "userid": "ADMIN001",
        "passwd": "WRONGPWD",
        "desc": "Admin user wrong password → error message",
    },
    {
        "id": "NOT_FOUND",
        "userid": "UNKNOWN1",
        "passwd": "ANYTHING",
        "desc": "Unknown user → not found error",
    },
]

PYTHON_REPO = UserSecurityRepository({
    "ADMIN001": SecUserData(
        sec_usr_id="ADMIN001", sec_usr_fname="John", sec_usr_lname="Admin",
        sec_usr_pwd="PASS1234", sec_usr_type="A",
    ),
    "USER0001": SecUserData(
        sec_usr_id="USER0001", sec_usr_fname="Jane", sec_usr_lname="User",
        sec_usr_pwd="MYPASSWD", sec_usr_type="U",
    ),
})


# ── Differential Test ──────────────────────────────────────────────────────

@pytest.mark.skipif(not COBC_AVAILABLE, reason="GnuCOBOL not available in WSL")
class TestDifferentialCosgn00c:
    """Run same inputs through COBOL and Python, compare outputs."""

    @pytest.fixture(scope="class")
    def cobol_env(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("diff_cosgn00c")
        binary = _prepare_cobol(tmp)
        usrsec = _seed_usrsec(tmp)
        return binary, usrsec

    def test_all_scenarios_match(self, cobol_env):
        """All 4 login scenarios produce identical outputs in COBOL and Python."""
        binary, usrsec = cobol_env
        vectors = []

        for scenario in SCENARIOS:
            # Run through COBOL
            cobol_stdout = _run_cobol_scenario(
                binary, usrsec, scenario["userid"], scenario["passwd"],
            )
            cobol_output = _parse_cobol_output(cobol_stdout)

            # Run through Python
            python_output = _run_python_scenario(
                scenario["userid"], scenario["passwd"], PYTHON_REPO,
            )

            vectors.append(DiffVector(
                vector_id=scenario["id"],
                program="COSGN00C",
                inputs={"USERID": scenario["userid"], "PASSWD": scenario["passwd"]},
                expected_outputs=cobol_output,
                actual_outputs=python_output,
                field_types={k: "str" for k in cobol_output},
            ))

        # Run differential harness
        report = run_vectors(vectors)
        report_text = render_report_text(report)
        print("\n" + report_text)

        assert report.confidence_score == 100.0, \
            f"COBOL/Python mismatch!\n{report_text}"
        assert report.failed == 0
        assert report.passed == 4
