"""Tests for repository_mapper.py — CICS/sequential file I/O to repository pattern.

IQ-06: Maps CICS file operations and sequential file I/O to typed repository
interfaces with methods derived from the actual operations found in the code.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repository_mapper import (
    RepositorySpec,
    RepositoryMethod,
    FileReaderSpec,
    map_cics_repositories,
    map_sequential_files,
    generate_repository_code,
    generate_file_reader_code,
    extract_cics_details,
)

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
PROGRAMS_JSON = CARDDEMO / "_analysis" / "programs.json"


def _load_programs() -> dict:
    return json.loads(PROGRAMS_JSON.read_text())


class TestCicsRepositoryMapping:
    """CICS file operations map to repository interfaces."""

    def test_read_with_ridfld_produces_find_by_id(self):
        """CICS READ DATASET(WS-USRSEC-FILE) with RIDFLD → find_by_id method."""
        programs = _load_programs()
        repos = map_cics_repositories("COSGN00C", programs["COSGN00C"],
                                      source_dir=str(CARDDEMO / "app" / "cbl"))
        assert len(repos) >= 1
        usrsec_repo = [r for r in repos if "USRSEC" in r.dataset.upper()]
        assert len(usrsec_repo) == 1
        repo = usrsec_repo[0]
        method_names = [m.name for m in repo.methods]
        assert "find_by_id" in method_names

    def test_find_by_id_has_key_and_return_type(self):
        """find_by_id should have a key parameter and a record return type."""
        programs = _load_programs()
        repos = map_cics_repositories("COSGN00C", programs["COSGN00C"],
                                      source_dir=str(CARDDEMO / "app" / "cbl"))
        repo = [r for r in repos if "USRSEC" in r.dataset.upper()][0]
        find = [m for m in repo.methods if m.name == "find_by_id"][0]
        assert find.key_field, "find_by_id must have a key_field"
        assert find.record_type, "find_by_id must have a record_type"

    def test_write_produces_save(self):
        """CICS WRITE on a dataset → save method."""
        programs = _load_programs()
        repos = map_cics_repositories("COUSR01C", programs["COUSR01C"],
                                      source_dir=str(CARDDEMO / "app" / "cbl"))
        usrsec_repo = [r for r in repos if "USRSEC" in r.dataset.upper()]
        assert len(usrsec_repo) >= 1
        method_names = [m.name for m in usrsec_repo[0].methods]
        assert "save" in method_names

    def test_delete_produces_delete(self):
        """CICS DELETE on a dataset → delete method."""
        programs = _load_programs()
        repos = map_cics_repositories("COUSR03C", programs["COUSR03C"],
                                      source_dir=str(CARDDEMO / "app" / "cbl"))
        usrsec_repo = [r for r in repos if "USRSEC" in r.dataset.upper()]
        assert len(usrsec_repo) >= 1
        method_names = [m.name for m in usrsec_repo[0].methods]
        assert "delete" in method_names

    def test_rewrite_produces_update(self):
        """CICS REWRITE → update method."""
        programs = _load_programs()
        repos = map_cics_repositories("COUSR02C", programs["COUSR02C"],
                                      source_dir=str(CARDDEMO / "app" / "cbl"))
        usrsec_repo = [r for r in repos if "USRSEC" in r.dataset.upper()]
        assert len(usrsec_repo) >= 1
        method_names = [m.name for m in usrsec_repo[0].methods]
        assert "update" in method_names

    def test_browse_produces_iterator(self):
        """STARTBR + READNEXT + ENDBR → browse method returning Iterator."""
        programs = _load_programs()
        repos = map_cics_repositories("COUSR00C", programs["COUSR00C"],
                                      source_dir=str(CARDDEMO / "app" / "cbl"))
        usrsec_repo = [r for r in repos if "USRSEC" in r.dataset.upper()]
        assert len(usrsec_repo) >= 1
        method_names = [m.name for m in usrsec_repo[0].methods]
        assert "browse" in method_names

    def test_repository_class_name_derived_from_dataset(self):
        """Repository class name is PascalCase of the dataset name."""
        programs = _load_programs()
        repos = map_cics_repositories("COSGN00C", programs["COSGN00C"],
                                      source_dir=str(CARDDEMO / "app" / "cbl"))
        repo = [r for r in repos if "USRSEC" in r.dataset.upper()][0]
        assert repo.class_name[0].isupper(), "Class name should be PascalCase"
        assert "Repository" in repo.class_name


class TestSequentialFileMapping:
    """Sequential file I/O maps to context manager readers/writers."""

    def test_sequential_input_produces_reader(self):
        """ORGANIZATION SEQUENTIAL with input → FileReaderSpec."""
        programs = _load_programs()
        # PAUDBLOD has sequential INFILE1, INFILE2
        if "PAUDBLOD" not in programs:
            pytest.skip("PAUDBLOD not in analysis")
        readers = map_sequential_files("PAUDBLOD", programs["PAUDBLOD"])
        assert len(readers) >= 1
        assert any(r.mode == "input" for r in readers)

    def test_sequential_output_produces_writer(self):
        """ORGANIZATION SEQUENTIAL with output → FileReaderSpec with mode=output."""
        programs = _load_programs()
        if "PAUDBUNL" not in programs:
            pytest.skip("PAUDBUNL not in analysis")
        files = map_sequential_files("PAUDBUNL", programs["PAUDBUNL"])
        assert len(files) >= 1
        assert any(f.mode == "output" for f in files)


class TestCicsDetailExtraction:
    """Extract INTO/RIDFLD from CICS READ source lines."""

    def test_extracts_into_and_ridfld(self):
        """COSGN00C READ-USER-SEC-FILE: INTO(SEC-USER-DATA), RIDFLD(WS-USER-ID)."""
        source_file = CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"
        details = extract_cics_details(str(source_file), start_line=211, end_line=219)
        assert details.get("into") == "SEC-USER-DATA"
        assert details.get("ridfld") == "WS-USER-ID"

    def test_handles_missing_ridfld(self):
        """A CICS SEND has no RIDFLD — returns None for ridfld."""
        source_file = CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"
        # SEND-SIGNON-SCREEN paragraph has a SEND, not a READ
        details = extract_cics_details(str(source_file), start_line=189, end_line=200)
        assert details.get("ridfld") is None


class TestRepositoryCodeGeneration:
    """Generated repository code is valid Python."""

    def test_generates_compilable_repository(self):
        """Repository code compiles as valid Python."""
        programs = _load_programs()
        repos = map_cics_repositories("COSGN00C", programs["COSGN00C"],
                                      source_dir=str(CARDDEMO / "app" / "cbl"))
        for repo in repos:
            code = generate_repository_code(repo)
            try:
                compile(code, f"<{repo.class_name}>", "exec")
            except SyntaxError as e:
                raise AssertionError(f"Repository {repo.class_name} has syntax error: {e}\n{code}")

    def test_repository_has_typed_record(self):
        """Generated repository references the copybook record type (IQ-02)."""
        programs = _load_programs()
        repos = map_cics_repositories("COSGN00C", programs["COSGN00C"],
                                      source_dir=str(CARDDEMO / "app" / "cbl"))
        repo = [r for r in repos if "USRSEC" in r.dataset.upper()][0]
        code = generate_repository_code(repo)
        # Should reference the record type from INTO(SEC-USER-DATA)
        assert "SecUserData" in code or "sec_user_data" in code.lower()

    def test_sequential_reader_generates_context_manager(self):
        """Sequential reader code has __enter__/__exit__ or 'with' pattern."""
        programs = _load_programs()
        if "PAUDBLOD" not in programs:
            pytest.skip("PAUDBLOD not in analysis")
        files = map_sequential_files("PAUDBLOD", programs["PAUDBLOD"])
        if not files:
            pytest.skip("No sequential files found")
        code = generate_file_reader_code(files[0])
        assert "__enter__" in code or "contextmanager" in code
        try:
            compile(code, "<reader>", "exec")
        except SyntaxError as e:
            raise AssertionError(f"Reader has syntax error: {e}\n{code}")
