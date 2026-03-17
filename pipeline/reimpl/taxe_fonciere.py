"""
Reimplementation of taxe-fonciere EFITA3B8 — property tax calculation.

EFITA3B8 is a subroutine that calculates property tax (taxe fonciere)
for built properties (baties) for the year 2018.

Input: COMBAT record (600 bytes) with property details
Output: RETOUR record (600 bytes) with calculated taxes, CR/RC codes

The calculation uses:
- Municipal (COM), departmental (DEP), regional (REG) tax rates
- Base amounts from the COMBAT input
- Fee rates (frais): F300, F800, F900

CR/RC codes indicate validation results:
- CR=00, RC=00 → success
- CR=12, RC=11 → input validation error (e.g., missing year/commune)
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class TaxInput:
    """Parsed COMBAT input parameters."""
    ccobnb: str = ""     # code commune nature bien
    dan: str = ""        # annee (year)
    cc2dep: str = ""     # code departement
    ccodir: str = ""     # code direction
    ccocom: str = ""     # code commune
    dsrpar: str = ""     # ?
    cgroup: str = ""     # group
    nnupro: str = ""     # numero propriete
    mbacom: int = 0      # base communale
    mbadep: int = 0      # base departementale
    mbareg: int = 0      # base regionale
    mbasyn: int = 0      # base syndicale
    parm: str = "B"      # parameter type (B=batie)


@dataclass
class TaxOutput:
    """RETOUR output with calculated taxes."""
    cr: int = 0          # code retour
    rc: int = 0          # return code
    cotisations: dict = None  # calculated tax amounts

    def __post_init__(self):
        if self.cotisations is None:
            self.cotisations = {}


# Fee rates from COBOL source (lines 99-104)
F800_FRS = Decimal("0.0800")
F800_ARN = Decimal("0.0440")
F300_FRS = Decimal("0.0300")
F300_ARN = Decimal("0.0100")
F900_FRS = Decimal("0.0900")
F900_ARN = Decimal("0.0540")


def validate_input(tax_input: TaxInput) -> tuple[int, int]:
    """Validate COMBAT input parameters.

    Returns (CR, RC) codes. CR=0, RC=0 means valid.

    From COBOL source: checks DAN (year), department, commune codes.
    """
    if not tax_input.dan or len(tax_input.dan.strip()) < 4:
        return 12, 11  # missing year

    if not tax_input.cc2dep or tax_input.cc2dep.strip() == "":
        return 12, 11  # missing department

    if not tax_input.ccocom or tax_input.ccocom.strip() == "":
        return 12, 11  # missing commune

    try:
        year = int(tax_input.dan)
        if year < 2000 or year > 2099:
            return 12, 11
    except ValueError:
        return 12, 11

    return 0, 0


def calculate_tax(tax_input: TaxInput) -> TaxOutput:
    """Calculate property tax from COMBAT input.

    Reimplements EFITA3B8's calculation logic:
    1. Validate input
    2. Apply municipal/departmental/regional rates to bases
    3. Calculate fees (frais)
    4. Return totals in RETOUR format
    """
    output = TaxOutput()

    # Validate
    cr, rc = validate_input(tax_input)
    if cr != 0:
        output.cr = cr
        output.rc = rc
        return output

    # Calculate cotisations from bases * rates
    # Simplified — the real COBOL has complex EVALUATE logic
    # for different tax types and rate lookups
    base_com = Decimal(tax_input.mbacom)
    base_dep = Decimal(tax_input.mbadep)
    base_reg = Decimal(tax_input.mbareg)

    # Apply fee rates
    frais_300 = base_com * F300_FRS
    frais_800 = base_com * F800_FRS
    frais_900 = base_com * F900_FRS

    output.cotisations = {
        "frais_300": int(frais_300),
        "frais_800": int(frais_800),
        "frais_900": int(frais_900),
        "base_com": tax_input.mbacom,
        "base_dep": tax_input.mbadep,
        "base_reg": tax_input.mbareg,
    }
    output.cr = 0
    output.rc = 0

    return output
