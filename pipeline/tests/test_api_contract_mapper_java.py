"""Tests for the Java emitters in api_contract_mapper.py (W5).

Verifies BMS screens → Spring REST controller + JSR-380 validated DTOs.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api_contract_mapper import (
    ApiContract,
    SchemaField,
    generate_request_model_code_java,
    generate_response_model_code_java,
    generate_route_stub_code_java,
    generate_request_model_code,
    generate_response_model_code,
    generate_route_stub_code,
)


def _make_contract(with_inputs=True, with_outputs=True) -> ApiContract:
    request_fields = []
    if with_inputs:
        request_fields = [
            SchemaField(
                name="USERID",
                python_name="userid",
                max_length=8,
                write_only=False,
                primary_input=True,
                display_emphasis=False,
                required=True,
                row=10, col=20,
            ),
            SchemaField(
                name="PASSWD",
                python_name="passwd",
                max_length=8,
                write_only=True,
                primary_input=False,
                display_emphasis=False,
                required=True,
                row=11, col=20,
            ),
        ]
    response_fields = []
    if with_outputs:
        response_fields = [
            SchemaField(
                name="ERRMSG",
                python_name="errmsg",
                max_length=78,
                write_only=False,
                primary_input=False,
                display_emphasis=True,
                required=False,
                row=23, col=1,
            ),
        ]
    return ApiContract(
        program="COSGN00C",
        map_name="COSGN0A",
        mapset_name="COSGN00",
        request_fields=request_fields,
        response_fields=response_fields,
        request_class="Cosgn0aRequest",
        response_class="Cosgn0aResponse",
        route_path="/cosgn00c/cosgn0a",
    )


# ── Java request DTO ───────────────────────────────────────────────────────


class TestJavaRequestDto:

    def test_emits_package(self):
        code = generate_request_model_code_java(_make_contract(), package="com.modernization.carddemo.cosgn00c.dto")
        assert "package com.modernization.carddemo.cosgn00c.dto;" in code

    def test_imports_validation_annotations(self):
        code = generate_request_model_code_java(_make_contract())
        assert "import jakarta.validation.constraints.NotNull;" in code
        assert "import jakarta.validation.constraints.Size;" in code

    def test_required_fields_get_notnull(self):
        code = generate_request_model_code_java(_make_contract())
        # USERID is required → expect @NotNull annotation
        assert "@NotNull" in code

    def test_max_length_emits_size_annotation(self):
        code = generate_request_model_code_java(_make_contract())
        assert "@Size(max = 8)" in code

    def test_write_only_emits_jackson_annotation(self):
        code = generate_request_model_code_java(_make_contract())
        assert "import com.fasterxml.jackson.annotation.JsonProperty;" in code
        assert "@JsonProperty(access = JsonProperty.Access.WRITE_ONLY)" in code

    def test_no_writeonly_omits_jackson_import(self):
        contract = _make_contract()
        for f in contract.request_fields:
            f.write_only = False
        code = generate_request_model_code_java(contract)
        assert "import com.fasterxml.jackson.annotation.JsonProperty;" not in code

    def test_emits_class_with_request_name(self):
        code = generate_request_model_code_java(_make_contract())
        assert "public class Cosgn0aRequest" in code

    def test_emits_getters_and_setters(self):
        code = generate_request_model_code_java(_make_contract())
        assert "public String getUserid()" in code
        assert "public void setUserid(String value)" in code
        assert "public String getPasswd()" in code

    def test_braces_balanced(self):
        code = generate_request_model_code_java(_make_contract())
        assert code.count("{") == code.count("}")

    def test_empty_request_still_compiles(self):
        contract = _make_contract(with_inputs=False)
        code = generate_request_model_code_java(contract)
        assert "public class Cosgn0aRequest" in code
        assert code.count("{") == code.count("}")


# ── Java response DTO ──────────────────────────────────────────────────────


class TestJavaResponseDto:

    def test_emits_package(self):
        code = generate_response_model_code_java(_make_contract(), package="com.modernization.carddemo.cosgn00c.dto")
        assert "package com.modernization.carddemo.cosgn00c.dto;" in code

    def test_emits_class_with_response_name(self):
        code = generate_response_model_code_java(_make_contract())
        assert "public class Cosgn0aResponse" in code

    def test_max_length_emits_size_annotation(self):
        code = generate_response_model_code_java(_make_contract())
        assert "@Size(max = 78)" in code

    def test_display_emphasis_documented_in_javadoc(self):
        code = generate_response_model_code_java(_make_contract())
        assert "Highlighted field (BMS BRT attribute)" in code

    def test_response_fields_default_to_empty_string(self):
        code = generate_response_model_code_java(_make_contract())
        assert 'private String errmsg = "";' in code

    def test_emits_getters_and_setters(self):
        code = generate_response_model_code_java(_make_contract())
        assert "public String getErrmsg()" in code
        assert "public void setErrmsg(String value)" in code

    def test_braces_balanced(self):
        code = generate_response_model_code_java(_make_contract())
        assert code.count("{") == code.count("}")


# ── Java route stub (Spring controller) ────────────────────────────────────


class TestJavaRouteStub:

    def test_emits_rest_controller_annotation(self):
        code = generate_route_stub_code_java(_make_contract())
        assert "@RestController" in code

    def test_emits_request_mapping(self):
        code = generate_route_stub_code_java(_make_contract())
        assert '@RequestMapping("/cosgn00c")' in code

    def test_emits_post_mapping(self):
        code = generate_route_stub_code_java(_make_contract())
        assert '@PostMapping("/cosgn0a")' in code

    def test_method_takes_valid_request_body(self):
        code = generate_route_stub_code_java(_make_contract())
        assert "@Valid @RequestBody Cosgn0aRequest request" in code

    def test_returns_response_dto(self):
        code = generate_route_stub_code_java(_make_contract())
        assert "Cosgn0aResponse" in code
        assert "return new Cosgn0aResponse();" in code

    def test_imports_dto_package(self):
        code = generate_route_stub_code_java(
            _make_contract(),
            dto_package="com.modernization.carddemo.cosgn00c.dto",
        )
        assert "import com.modernization.carddemo.cosgn00c.dto.Cosgn0aRequest;" in code
        assert "import com.modernization.carddemo.cosgn00c.dto.Cosgn0aResponse;" in code

    def test_braces_balanced(self):
        code = generate_route_stub_code_java(_make_contract())
        assert code.count("{") == code.count("}")


# ── Python emitters still work ─────────────────────────────────────────────


class TestPythonEmittersUnchanged:

    def test_python_request_model(self):
        code = generate_request_model_code(_make_contract())
        assert "class Cosgn0aRequest(BaseModel):" in code

    def test_python_response_model(self):
        code = generate_response_model_code(_make_contract())
        assert "class Cosgn0aResponse(BaseModel):" in code

    def test_python_route_stub(self):
        code = generate_route_stub_code(_make_contract())
        assert "from fastapi import APIRouter" in code
        assert "@router.post" in code
