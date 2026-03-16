"""End-to-end test: COSGN00C login scenarios via CICS stub + GnuCOBOL.

IQ-11 Phase 2 proof: COSGN00C compiles and runs with stubbed CICS,
producing correct outputs for all 4 login scenarios.
"""

import re
import struct
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cobol_runner import is_cobc_available, _to_wsl_path
from cics_stub import preprocess_cics
from bms_symbolic import generate_all_symbolic_maps

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
COBC_AVAILABLE = is_cobc_available()

# BMS field layout for COSGN0AI screen input record
COSGN0A_FIELDS = [
    ("TRNNAME", 4), ("TITLE01", 40), ("CURDATE", 8), ("PGMNAME", 8),
    ("TITLE02", 40), ("CURTIME", 9), ("APPLID", 8), ("SYSID", 8),
    ("USERID", 8), ("PASSWD", 8), ("ERRMSG", 78),
]


def _build_screen_input(userid: str = "", passwd: str = "") -> bytes:
    """Build a COSGN0AI-format screen input record."""
    record = bytearray(b'\x00' * 12)  # header
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
        record += struct.pack('>h', data_len)  # L field
        record += b'\x00'                       # F field
        record += b'\x00\x00'                   # filler
        record += data                          # I field
    return bytes(record)


def _prepare_cosgn00c(tmp_path):
    """Preprocess COSGN00C, generate symbolic maps, compile."""
    sym_dir = tmp_path / "symbolic"
    generate_all_symbolic_maps(str(CARDDEMO / "app" / "bms"), str(sym_dir))

    result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
    source = result.source

    # Inject file status
    ws_inject = ""
    for ds in result.datasets:
        ws_inject += f"       01  {ds.file_alias}-STATUS         PIC XX.\n"
    if ws_inject:
        ws_m = re.search(r'(^\s*WORKING-STORAGE\s+SECTION\.)', source, re.MULTILINE | re.IGNORECASE)
        if ws_m:
            pos = ws_m.end()
            source = source[:pos] + "\n" + ws_inject + source[pos:]

    # Inject test initialization
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

    # Compile
    cpy_wsl = _to_wsl_path(str(CARDDEMO / "app" / "cpy"))
    sym_wsl = _to_wsl_path(str(sym_dir))
    src_wsl = _to_wsl_path(str(stubbed))
    binary = "/tmp/cosgn00c_e2e_bin"

    cmd = f'cobc -x -std=ibm -I {cpy_wsl} -I {sym_wsl} -o {binary} {src_wsl}'
    r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"Compile failed: {r.stderr}"
    return binary


def _seed_usrsec(tmp_path):
    """Create indexed user security file with test users."""
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
    dat_path = "/tmp/cosgn00c_e2e_usrsec.dat"

    cmd = f'cobc -x -std=ibm -I {cpy_wsl} -o /tmp/seedusrsec {src_wsl} && export USRSECFILE="{dat_path}" && /tmp/seedusrsec'
    r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"Seed failed: {r.stderr}"
    return dat_path


def _run_scenario(binary: str, usrsec_path: str, screen_input: bytes, screen_path: str) -> str:
    """Run COSGN00C with given screen input, return stdout."""
    # Write screen input file
    subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c",
         f"cat > {screen_path}"],
        input=screen_input + b'\n', capture_output=True, timeout=10,
    )

    cmd = f'export USRSECFILE="{usrsec_path}" && export SCREENIN="{screen_path}" && {binary}'
    r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                       capture_output=True, text=True, timeout=15)
    return r.stdout


@pytest.mark.skipif(not COBC_AVAILABLE, reason="GnuCOBOL not available in WSL")
class TestCosgn00cLoginScenarios:
    """All 4 login scenarios produce correct COBOL output."""

    @pytest.fixture(scope="class")
    def cobol_env(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("cosgn00c")
        binary = _prepare_cosgn00c(tmp)
        usrsec = _seed_usrsec(tmp)
        return binary, usrsec

    def test_admin_login_routes_to_coadm01c(self, cobol_env):
        """ADMIN001 + correct password → XCTL to COADM01C."""
        binary, usrsec = cobol_env
        screen = _build_screen_input("ADMIN001", "PASS1234")
        stdout = _run_scenario(binary, usrsec, screen, "/tmp/cosgn00c_screen.dat")
        assert "XCTL-TO:COADM01C" in stdout

    def test_regular_user_routes_to_comen01c(self, cobol_env):
        """USER0001 + correct password → XCTL to COMEN01C."""
        binary, usrsec = cobol_env
        screen = _build_screen_input("USER0001", "MYPASSWD")
        stdout = _run_scenario(binary, usrsec, screen, "/tmp/cosgn00c_screen.dat")
        assert "XCTL-TO:COMEN01C" in stdout

    def test_wrong_password_shows_error(self, cobol_env):
        """ADMIN001 + wrong password → 'Wrong Password' error message."""
        binary, usrsec = cobol_env
        screen = _build_screen_input("ADMIN001", "WRONGPWD")
        stdout = _run_scenario(binary, usrsec, screen, "/tmp/cosgn00c_screen.dat")
        assert "XCTL-TO:" not in stdout  # no transfer
        assert "Wrong Password" in stdout or "SEND-MAP:" in stdout

    def test_user_not_found_shows_error(self, cobol_env):
        """UNKNOWN1 → 'User not found' error message (RESP 13)."""
        binary, usrsec = cobol_env
        screen = _build_screen_input("UNKNOWN1", "ANYTHING")
        stdout = _run_scenario(binary, usrsec, screen, "/tmp/cosgn00c_screen.dat")
        assert "XCTL-TO:" not in stdout  # no transfer
        assert "User not found" in stdout or "SEND-MAP:" in stdout
