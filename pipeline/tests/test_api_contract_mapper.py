"""Tests for api_contract_mapper.py — BMS screen to API contract generation.

IQ-07: Maps SEND MAP / RECEIVE MAP to typed request/response Pydantic schemas
and FastAPI route stubs.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api_contract_mapper import (
    ApiContract,
    SchemaField,
    map_screen_contracts,
    generate_request_model_code,
    generate_response_model_code,
    generate_route_stub_code,
)

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"


class TestScreenContractMapping:
    """BMS maps produce API contracts with request/response schemas."""

    def test_cosgn0a_produces_contract(self):
        """COSGN00C uses mapset COSGN00 → must produce at least one API contract."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        assert len(contracts) >= 1
        contract = contracts[0]
        assert contract.program == "COSGN00C"
        assert contract.map_name == "COSGN0A"

    def test_receive_fields_become_request_schema(self):
        """COSGN0A input fields (USERID, PASSWD) → request schema fields."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        contract = contracts[0]
        request_names = [f.name for f in contract.request_fields]
        assert "USERID" in request_names
        assert "PASSWD" in request_names

    def test_send_fields_become_response_schema(self):
        """COSGN0A output fields (ERRMSG, TITLE01, etc.) → response schema fields."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        contract = contracts[0]
        response_names = [f.name for f in contract.response_fields]
        assert "ERRMSG" in response_names

    def test_password_field_is_write_only(self):
        """PASSWD has DRK attribute → write_only=True (sensitive field)."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        contract = contracts[0]
        passwd = [f for f in contract.request_fields if f.name == "PASSWD"][0]
        assert passwd.write_only is True

    def test_field_has_max_length(self):
        """Fields carry max_length from BMS LENGTH= attribute."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        contract = contracts[0]
        userid = [f for f in contract.request_fields if f.name == "USERID"][0]
        assert userid.max_length == 8

    def test_bright_field_flagged(self):
        """ERRMSG has BRT attribute → display_emphasis=True."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        contract = contracts[0]
        errmsg = [f for f in contract.response_fields if f.name == "ERRMSG"][0]
        assert errmsg.display_emphasis is True

    def test_ic_field_is_primary(self):
        """USERID has IC (initial cursor) → primary_input=True."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        contract = contracts[0]
        userid = [f for f in contract.request_fields if f.name == "USERID"][0]
        assert userid.primary_input is True


class TestRequestModelGeneration:
    """Generated Pydantic request model code."""

    def test_generates_compilable_request_model(self):
        """Request model code compiles as valid Python."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        code = generate_request_model_code(contracts[0])
        try:
            compile(code, "<request>", "exec")
        except SyntaxError as e:
            raise AssertionError(f"Request model syntax error: {e}\n{code}")

    def test_request_model_has_userid_and_passwd(self):
        """Request model contains userid and passwd fields."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        code = generate_request_model_code(contracts[0])
        assert "userid" in code.lower()
        assert "passwd" in code.lower()

    def test_request_model_uses_pydantic_or_dataclass(self):
        """Request model uses Pydantic BaseModel or dataclass."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        code = generate_request_model_code(contracts[0])
        assert "BaseModel" in code or "dataclass" in code


class TestResponseModelGeneration:
    """Generated Pydantic response model code."""

    def test_generates_compilable_response_model(self):
        """Response model code compiles as valid Python."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        code = generate_response_model_code(contracts[0])
        try:
            compile(code, "<response>", "exec")
        except SyntaxError as e:
            raise AssertionError(f"Response model syntax error: {e}\n{code}")

    def test_response_model_has_errmsg(self):
        """Response model contains error message field."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        code = generate_response_model_code(contracts[0])
        assert "errmsg" in code.lower()


class TestRouteStubGeneration:
    """Generated FastAPI route stub code."""

    def test_generates_compilable_route(self):
        """Route stub compiles as valid Python."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        code = generate_route_stub_code(contracts[0])
        try:
            compile(code, "<route>", "exec")
        except SyntaxError as e:
            raise AssertionError(f"Route stub syntax error: {e}\n{code}")

    def test_route_has_post_endpoint(self):
        """Route stub has a POST endpoint (RECEIVE MAP = form submit)."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        code = generate_route_stub_code(contracts[0])
        assert "post" in code.lower() or "POST" in code

    def test_route_references_request_and_response_models(self):
        """Route stub uses the request and response model classes."""
        contracts = map_screen_contracts("COSGN00C", str(CARDDEMO))
        code = generate_route_stub_code(contracts[0])
        assert "Request" in code or "request" in code
        assert "Response" in code or "response" in code
