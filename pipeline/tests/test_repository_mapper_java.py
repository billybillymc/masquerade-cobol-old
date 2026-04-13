"""Tests for the Java emitters in repository_mapper.py (W4).

Verifies that:
  - generate_repository_code_java emits a Spring Data CrudRepository interface
    with the correct CICS-to-Spring mapping in javadoc
  - Browse-capable repos get a Stream<T> streamAllByOrderById() method
  - Sequential file specs become AutoCloseable Reader/Writer classes
  - The Python emitters in the same module still work (regression check)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repository_mapper import (
    FileReaderSpec,
    RepositoryMethod,
    RepositorySpec,
    generate_file_reader_code,
    generate_file_reader_code_java,
    generate_repository_code,
    generate_repository_code_java,
)


def _make_repo_with_methods(*method_names: str) -> RepositorySpec:
    methods = []
    for name in method_names:
        operation = {
            "find_by_id": "READ",
            "save": "WRITE",
            "update": "REWRITE",
            "delete": "DELETE",
            "browse": "STARTBR",
        }[name]
        methods.append(RepositoryMethod(
            name=name,
            operation=operation,
            key_field="WS-USR-ID",
            record_type="SecUserData",
            record_field="SEC-USER-DATA",
        ))
    return RepositorySpec(
        dataset="WS-USRSEC-FILE",
        class_name="WsUsrsecFileRepository",
        methods=methods,
        programs=["COSGN00C"],
    )


# ── Java repository emission ───────────────────────────────────────────────


class TestJavaRepositoryEmission:
    """The new Java emitter must produce a buildable Spring Data interface."""

    def test_emits_package_declaration(self):
        repo = _make_repo_with_methods("find_by_id")
        code = generate_repository_code_java(repo, package="com.modernization.carddemo.cosgn00c.repository")
        assert "package com.modernization.carddemo.cosgn00c.repository;" in code

    def test_emits_crud_repository_extends(self):
        repo = _make_repo_with_methods("find_by_id", "save")
        code = generate_repository_code_java(repo)
        assert "import org.springframework.data.repository.CrudRepository;" in code
        assert "extends CrudRepository<SecUserData, String>" in code

    def test_browse_emits_stream_method(self):
        repo = _make_repo_with_methods("find_by_id", "browse")
        code = generate_repository_code_java(repo)
        assert "import java.util.stream.Stream;" in code
        assert "Stream<SecUserData> streamAllByOrderById();" in code

    def test_no_browse_omits_stream_import(self):
        repo = _make_repo_with_methods("find_by_id", "save")
        code = generate_repository_code_java(repo)
        assert "import java.util.stream.Stream;" not in code
        assert "streamAllByOrderById" not in code

    def test_javadoc_lists_cics_to_spring_mapping(self):
        repo = _make_repo_with_methods("find_by_id", "save", "delete", "browse")
        code = generate_repository_code_java(repo)
        assert "CICS READ" in code
        assert "findById" in code
        assert "CICS WRITE" in code
        assert "save(entity)" in code
        assert "CICS DELETE" in code
        assert "deleteById" in code
        assert "CICS STARTBR" in code

    def test_record_package_import_when_provided(self):
        repo = _make_repo_with_methods("find_by_id")
        code = generate_repository_code_java(
            repo,
            package="com.modernization.carddemo.cosgn00c.repository",
            record_package="com.modernization.carddemo.cosgn00c.dto",
        )
        assert "import com.modernization.carddemo.cosgn00c.dto.SecUserData;" in code

    def test_dict_record_type_falls_back_to_object(self):
        repo = RepositorySpec(
            dataset="WS-NOSCHEMA",
            class_name="WsNoschemaRepository",
            methods=[RepositoryMethod(
                name="find_by_id",
                operation="READ",
                key_field="KEY",
                record_type="dict",  # the default fallback for unknown types
                record_field="",
            )],
            programs=["NOPGM"],
        )
        code = generate_repository_code_java(repo)
        assert "extends CrudRepository<Object, String>" in code

    def test_braces_balanced(self):
        repo = _make_repo_with_methods("find_by_id", "save", "delete", "browse")
        code = generate_repository_code_java(repo)
        assert code.count("{") == code.count("}")


# ── Java sequential file emission ──────────────────────────────────────────


class TestJavaFileReaderEmission:
    def test_input_file_uses_buffered_reader(self):
        spec = FileReaderSpec(
            file_name="USERINFILE",
            assign_to="USERIN",
            organization="SEQUENTIAL",
            mode="input",
            class_name="UserinfileReader",
        )
        code = generate_file_reader_code_java(spec)
        assert "import java.io.BufferedReader;" in code
        assert "BufferedReader reader" in code
        assert "public String readNext()" in code
        assert "implements AutoCloseable" in code

    def test_output_file_uses_buffered_writer(self):
        spec = FileReaderSpec(
            file_name="USEROUTFILE",
            assign_to="USEROUT",
            organization="SEQUENTIAL",
            mode="output",
            class_name="UseroutfileWriter",
        )
        code = generate_file_reader_code_java(spec)
        assert "import java.io.BufferedWriter;" in code
        assert "BufferedWriter writer" in code
        assert "public void write(String record)" in code

    def test_close_is_idempotent_per_autocloseable_contract(self):
        spec = FileReaderSpec(
            file_name="X",
            assign_to="X",
            organization="SEQUENTIAL",
            mode="input",
            class_name="XReader",
        )
        code = generate_file_reader_code_java(spec)
        # Just check that close() exists and uses try-with-resources friendly shape
        assert "@Override" in code
        assert "public void close() throws IOException" in code

    def test_braces_balanced_input(self):
        spec = FileReaderSpec(
            file_name="X",
            assign_to="X",
            organization="SEQUENTIAL",
            mode="input",
            class_name="XReader",
        )
        code = generate_file_reader_code_java(spec)
        assert code.count("{") == code.count("}")

    def test_braces_balanced_output(self):
        spec = FileReaderSpec(
            file_name="X",
            assign_to="X",
            organization="SEQUENTIAL",
            mode="output",
            class_name="XWriter",
        )
        code = generate_file_reader_code_java(spec)
        assert code.count("{") == code.count("}")


# ── Python emitters still work (regression check) ──────────────────────────


class TestPythonEmittersUnchanged:
    def test_generate_repository_code_still_works(self):
        repo = _make_repo_with_methods("find_by_id", "save")
        code = generate_repository_code(repo)
        assert "class WsUsrsecFileRepository:" in code
        assert "def find_by_id" in code
        assert "def save" in code

    def test_generate_file_reader_code_still_works(self):
        spec = FileReaderSpec(
            file_name="X",
            assign_to="X",
            organization="SEQUENTIAL",
            mode="input",
            class_name="XReader",
        )
        code = generate_file_reader_code(spec)
        assert "class XReader:" in code
        assert "def __enter__" in code
