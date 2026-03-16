"""
BMS screen → API contract mapper.

Maps CICS SEND MAP / RECEIVE MAP to typed request/response Pydantic schemas
and FastAPI route stubs using the existing bms_parser output.

RECEIVE MAP input fields (UNPROT) → request model fields
SEND MAP output fields (ASKIP/PROT) → response model fields
Field attributes map to validation annotations:
  - DRK → write_only (password-like)
  - IC → primary_input (initial cursor)
  - BRT → display_emphasis
  - LENGTH → max_length
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bms_parser import parse_bms_file, BmsMapset, BmsMap, BmsField, ScreenFlowIndex
from skeleton_generator import _cobol_name_to_python, _cobol_name_to_class


@dataclass
class SchemaField:
    """A field in a request or response schema."""
    name: str              # BMS field name (e.g., USERID)
    python_name: str       # snake_case (e.g., userid)
    max_length: int        # from BMS LENGTH
    write_only: bool       # DRK attribute → sensitive field
    primary_input: bool    # IC attribute → initial cursor
    display_emphasis: bool  # BRT attribute → highlighted
    required: bool         # input fields are required by default
    row: int
    col: int


@dataclass
class ApiContract:
    """API contract for a CICS screen program."""
    program: str
    map_name: str
    mapset_name: str
    request_fields: list[SchemaField]
    response_fields: list[SchemaField]
    request_class: str     # PascalCase request model name
    response_class: str    # PascalCase response model name
    route_path: str        # e.g., /cosgn00c/signon


def _bms_field_to_schema_field(f: BmsField) -> SchemaField:
    """Convert a BmsField to a SchemaField with attribute mapping."""
    attrs = [a.upper() for a in f.attributes]
    return SchemaField(
        name=f.name,
        python_name=_cobol_name_to_python(f.name),
        max_length=f.length,
        write_only="DRK" in attrs,
        primary_input="IC" in attrs,
        display_emphasis="BRT" in attrs,
        required=f.is_input,
        row=f.row,
        col=f.col,
    )


def map_screen_contracts(
    program_id: str,
    codebase_dir: str,
) -> list[ApiContract]:
    """Map a CICS program's screen operations to API contracts.

    Finds the BMS mapset used by the program, extracts input/output fields,
    and builds request/response schemas.
    """
    # Find which mapsets this program uses by scanning its source
    pgm_upper = program_id.upper()
    map_refs: list[tuple[str, str]] = []  # (map_name, mapset_name)

    _re_map = re.compile(r"MAP\s*\(\s*'([^']+)'\s*\)", re.IGNORECASE)
    _re_mapset = re.compile(r"MAPSET\s*\(\s*'([^']+)'\s*\)", re.IGNORECASE)

    for cbl_file in Path(codebase_dir).rglob("*.cbl"):
        if cbl_file.stem.upper() == pgm_upper:
            content = cbl_file.read_text(encoding="utf-8", errors="replace")
            maps = _re_map.findall(content)
            mapsets = _re_mapset.findall(content)
            for m in maps:
                ms = mapsets[0] if mapsets else m[:6]  # heuristic: mapset is first 6 chars
                map_refs.append((m.upper(), ms.upper()))
            break

    if not map_refs:
        return []

    # Parse BMS files to get field definitions
    contracts = []
    seen_maps = set()

    for bms_file in Path(codebase_dir).rglob("*.bms"):
        mapset = parse_bms_file(bms_file)
        if not mapset:
            continue

        for bms_map in mapset.maps:
            for map_name, mapset_name in map_refs:
                if bms_map.name.upper() == map_name and map_name not in seen_maps:
                    seen_maps.add(map_name)

                    # Split fields into request (input) and response (output)
                    request_fields = []
                    response_fields = []

                    for f in bms_map.fields:
                        if not f.name:
                            continue
                        sf = _bms_field_to_schema_field(f)
                        if f.is_input:
                            request_fields.append(sf)
                        elif f.name:  # named output field
                            response_fields.append(sf)

                    # Build class names
                    map_class = _cobol_name_to_class(map_name)
                    request_class = f"{map_class}Request"
                    response_class = f"{map_class}Response"

                    # Build route path
                    route_path = f"/{_cobol_name_to_python(program_id)}/{_cobol_name_to_python(map_name)}"

                    contracts.append(ApiContract(
                        program=program_id,
                        map_name=map_name,
                        mapset_name=mapset_name,
                        request_fields=request_fields,
                        response_fields=response_fields,
                        request_class=request_class,
                        response_class=response_class,
                        route_path=route_path,
                    ))

    return contracts


def generate_request_model_code(contract: ApiContract) -> str:
    """Generate a Pydantic BaseModel for the request (RECEIVE MAP fields)."""
    lines = []
    lines.append(f"from pydantic import BaseModel, Field")
    lines.append(f"from typing import Optional")
    lines.append(f"")
    lines.append(f"")
    lines.append(f"class {contract.request_class}(BaseModel):")
    lines.append(f'    """Request schema from BMS map {contract.map_name} (RECEIVE MAP).')
    lines.append(f"")
    lines.append(f"    Program: {contract.program}")
    lines.append(f"    Mapset: {contract.mapset_name}")
    lines.append(f'    """')

    if not contract.request_fields:
        lines.append(f"    pass")
    else:
        for f in contract.request_fields:
            constraints = []
            if f.max_length:
                constraints.append(f"max_length={f.max_length}")
            if f.write_only:
                constraints.append(f"json_schema_extra={{'writeOnly': True}}")
            if f.primary_input:
                constraints.append(f"description='Primary input field'")

            if constraints:
                field_def = f"Field(..., {', '.join(constraints)})"
            else:
                field_def = f"Field(...)"

            lines.append(f"    {f.python_name}: str = {field_def}")

    lines.append(f"")
    return "\n".join(lines)


def generate_response_model_code(contract: ApiContract) -> str:
    """Generate a Pydantic BaseModel for the response (SEND MAP fields)."""
    lines = []
    lines.append(f"from pydantic import BaseModel, Field")
    lines.append(f"from typing import Optional")
    lines.append(f"")
    lines.append(f"")
    lines.append(f"class {contract.response_class}(BaseModel):")
    lines.append(f'    """Response schema from BMS map {contract.map_name} (SEND MAP).')
    lines.append(f"")
    lines.append(f"    Program: {contract.program}")
    lines.append(f"    Mapset: {contract.mapset_name}")
    lines.append(f'    """')

    if not contract.response_fields:
        lines.append(f"    pass")
    else:
        for f in contract.response_fields:
            constraints = []
            if f.max_length:
                constraints.append(f"max_length={f.max_length}")
            if f.display_emphasis:
                constraints.append(f"description='Highlighted field (BRT)'")

            default = f"''"
            if constraints:
                field_def = f"Field(default={default}, {', '.join(constraints)})"
            else:
                field_def = default

            lines.append(f"    {f.python_name}: str = {field_def}")

    lines.append(f"")
    return "\n".join(lines)


def generate_route_stub_code(contract: ApiContract) -> str:
    """Generate a FastAPI route stub using the request/response models."""
    lines = []
    lines.append(f"from fastapi import APIRouter")
    lines.append(f"")
    lines.append(f"router = APIRouter()")
    lines.append(f"")
    lines.append(f"")
    lines.append(f'@router.post("{contract.route_path}", response_model={contract.response_class})')
    lines.append(f"def {_cobol_name_to_python(contract.map_name)}(request: {contract.request_class}) -> {contract.response_class}:")
    lines.append(f'    """Handle screen interaction for {contract.program} map {contract.map_name}.')
    lines.append(f"")
    lines.append(f"    Original CICS: RECEIVE MAP('{contract.map_name}') MAPSET('{contract.mapset_name}')")
    lines.append(f"                   → process → SEND MAP('{contract.map_name}')")
    lines.append(f'    """')
    lines.append(f"    # TODO: Implement business logic from {contract.program}")
    lines.append(f"    return {contract.response_class}()")
    lines.append(f"")
    return "\n".join(lines)
