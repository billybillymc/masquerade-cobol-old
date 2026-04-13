"""
Reimplementation of EFITA3B8 -- Taxe Fonciere Batie (built property tax)
calculator for the year 2018.

This is a faithful translation of the COBOL subroutine EFITA3B8 and its
copybooks (XCOMBAT, XRETB, XCOTB, XBASEB, XBXTDAN, XBXTDCOM, XBXTDDIR,
XBXTDSR).

EFITA3B8 is called with:
    PROCEDURE DIVISION USING COMBATM RETOURM CRM RCM PARM.

It validates the COMBAT input, reconstitutes tax bases, retrieves rates,
computes cotisations (taxes) and frais (fees), and returns results in
RETOUR with CR/RC error codes.

COPY REPLACING convention: COPY XCOMBAT REPLACING 'X' BY COMBAT means
every field 'X'-FIELD becomes COMBAT-FIELD in the main program.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional


# ---------------------------------------------------------------------------
# Helper: COBOL-style ROUNDED (half-up to integer)
# ---------------------------------------------------------------------------
def _round(value: Decimal) -> int:
    """COBOL COMPUTE ... ROUNDED -> round half-up to integer."""
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Fee rate constants  (from WORKING-STORAGE lines 99-104)
# ---------------------------------------------------------------------------
F800_FRS = Decimal("0.0800")   # frais OM total rate 8%
F800_ARN = Decimal("0.0440")   # frais assiette portion of 8% (4.4%)
F300_FRS = Decimal("0.0300")   # frais FDL total rate 3%
F300_ARN = Decimal("0.0100")   # frais assiette portion of 3% (1%)
F900_FRS = Decimal("0.0900")   # frais TSE total rate 9%
F900_ARN = Decimal("0.0540")   # frais assiette portion of 9% (5.4%)


# ---------------------------------------------------------------------------
# Valid OM zone codes (88-level in XCOMBAT)
# ---------------------------------------------------------------------------
VALID_GTAUOM = {"  ", " P", "P ", "RA", "RB", "RC", "RD", "RE"}


# ---------------------------------------------------------------------------
# Dataclasses mirroring COBOL copybooks
# ---------------------------------------------------------------------------

@dataclass
class OmZone:
    """One entry of the ABAOM OCCURS 6 array in XCOMBAT."""
    gtauom: str = "  "   # PIC X(2) -- zone code
    mbaom: int = 0       # PIC S9(10) -- base OM for this zone


@dataclass
class CombatInput:
    """All fields from XCOMBAT (COPY XCOMBAT REPLACING 'X' BY COMBAT).

    Represents the 600-byte input parameter COMBATM.
    """
    # --- GS12 header ---
    ccobnb: str = ""           # PIC X       -- code bati/non-bati (must be '2')
    # --- AIDFIC ---
    dan: str = ""              # PIC 9(4)    -- annee d'imposition
    cc2dep: str = ""           # PIC X(2)    -- code departement
    ccodir: str = ""           # PIC X       -- code direction
    ccocom: str = ""           # PIC X(3)    -- code commune
    dsrpar: str = ""           # PIC X       -- serie role parcelle
    # --- ANUPRO ---
    cgroup: str = ""           # PIC X       -- code groupe proprietaire
    nnupro: int = 0            # PIC 9(5)    -- numero compte proprietaire
    # --- A0008 (8 GTOTAU codes, not used in calc) ---
    gtotau: List[str] = field(default_factory=lambda: [""] * 8)
    # --- MBABA bases ---
    mbacom: int = 0            # PIC S9(10)  -- base communale
    mbadep: int = 0            # PIC S9(10)  -- base departementale
    mbareg: int = 0            # PIC S9(10)  -- base regionale
    mbasyn: int = 0            # PIC S9(10)  -- base syndicat
    mbacu: int = 0             # PIC S9(10)  -- base EPCI
    mbatse: int = 0            # PIC S9(10)  -- (not used in calc)
    mbbt13: List[int] = field(default_factory=lambda: [0, 0])  # S9(10) OCCURS 2
    # --- ABAOM OCCURS 6 ---
    abaom: List[OmZone] = field(default_factory=lambda: [OmZone() for _ in range(6)])
    # --- remaining ---
    mvltim: int = 0            # PIC S9(10)  -- montant TEOMI
    pvltom: Decimal = Decimal(0)  # PIC 9V9(15) -- pseudo taux
    mbage3: int = 0            # PIC S9(10)  -- base GEMAPI
    mbata3: int = 0            # PIC S9(10)  -- base TASA
    ccoifp: str = ""           # PIC X(3)    -- code commune absorbee
    ccpper: str = ""           # PIC X(3)    -- code tresorerie

    # Convenience helpers derived from composite fields
    @property
    def ac3dir(self) -> str:
        """CC2DEP + CCODIR"""
        return self.cc2dep + self.ccodir

    @property
    def aidfic(self) -> str:
        """DAN + AC3DIR + CCOCOM + DSRPAR"""
        return self.dan + self.ac3dir + self.ccocom + self.dsrpar

    @property
    def anupro(self) -> str:
        """CGROUP + NNUPRO"""
        return self.cgroup + str(self.nnupro).zfill(5)


@dataclass
class OmRetour:
    """One ACTOM entry in XRETB (OCCURS 6)."""
    gtauom: str = "  "
    mctom: int = 0


@dataclass
class RetourOutput:
    """All fields from XRETB (COPY XRETB REPLACING 'X' BY RETOURB).

    Represents the 600-byte output parameter RETOURM.
    """
    # --- AIDFIC ---
    dan: str = ""
    cc2dep: str = ""
    ccodir: str = ""
    ccocom: str = ""
    dsrpar: str = ""
    # --- ANUPRO ---
    cgroup: str = ""
    nnupro: int = 0
    # ---
    ccobnb: str = ""           # code bati/non-bati
    # --- cotisations ---
    mctcom: int = 0            # cotisation communale
    mctdep: int = 0            # cotisation departementale
    mctreg: int = 0            # cotisation regionale (unused in bati 2018)
    mctsyn: int = 0            # cotisation syndicat
    mctcu: int = 0             # cotisation EPCI
    mcttse: int = 0            # cotisation TSE (unused directly)
    mcbt13: List[int] = field(default_factory=lambda: [0, 0])  # TSE 1 & 2
    mcbtsa: int = 0            # amalgame TSE1 + TSE2 + TASA
    # --- OM ---
    actom: List[OmRetour] = field(default_factory=lambda: [OmRetour() for _ in range(6)])
    # --- frais ---
    mfa300: int = 0            # frais assiette 3%
    mfn300: int = 0            # frais non-valeur 3%
    mfa800: int = 0            # frais assiette 8%
    mfn800: int = 0            # frais non-valeur 8%
    mfa900: int = 0            # frais assiette 9%
    mfn900: int = 0            # frais non-valeur 9%
    # --- totals ---
    tcthfr: int = 0            # total cotisation hors frais
    tctfra: int = 0            # total des frais
    tctdu: int = 0             # total cotisation du (avec frais)
    tctom: int = 0             # total cotisations OM
    mvltim: int = 0            # montant TEOMI
    mcoge3: int = 0            # cotisation GEMAPI
    mcota3: int = 0            # cotisation TASA
    ccoifp: str = ""
    ccpper: str = ""

    @property
    def aidfic(self) -> str:
        return self.dan + self.cc2dep + self.ccodir + self.ccocom + self.dsrpar

    @property
    def anupro(self) -> str:
        return self.cgroup + str(self.nnupro).zfill(5)


# ---------------------------------------------------------------------------
# Rate structures (from XBXTDSR, XBXTDDIR, XBXTDCOM, XBXTDAN)
# ---------------------------------------------------------------------------

@dataclass
class RatesSpecialRole:
    """XBXTDSR -- taux du sous-role (special rates).

    Populated from ZES(4) = ZESTAUX(4).
    """
    jan: str = ""              # annee
    depdir: str = ""           # dept+dir
    ccocom: str = ""           # commune
    ccoifp: str = ""           # IFP
    taucom_b: Decimal = Decimal(0)      # taux bati communal
    tausyndsfp_b: Decimal = Decimal(0)  # taux bati syndicat
    taucudfpvn_b: Decimal = Decimal(0)  # taux bati EPCI
    tautse_b: Decimal = Decimal(0)      # taux bati TSE
    ptbgem: Decimal = Decimal(0)        # taux GEMAPI bati
    ptbtgp: Decimal = Decimal(0)        # taux TSE Grand Paris bati


@dataclass
class RatesDirection:
    """XBXTDDIR -- taux direction (departement-level rates)."""
    taudep_b: Decimal = Decimal(0)   # taux bati departement
    taureg_b: Decimal = Decimal(0)   # taux bati region
    ptbtas: Decimal = Decimal(0)     # taux bati TASA


@dataclass
class RatesCommune:
    """XBXTDCOM -- taux commune."""
    pbbomp: Decimal = Decimal(0)     # taux plein OM
    pbboma: Decimal = Decimal(0)     # taux reduit RA
    pbbomb: Decimal = Decimal(0)     # taux reduit RB
    pbbomc: Decimal = Decimal(0)     # taux reduit RC
    pbbomd: Decimal = Decimal(0)     # taux reduit RD
    pbbome: Decimal = Decimal(0)     # taux reduit RE


@dataclass
class RatesAnnual:
    """XBXTDAN -- taux annuels (not heavily used in bati calc)."""
    pass


@dataclass
class AllRates:
    """Aggregated rates from all sources, ready for calculation.

    In the COBOL, rates come from four record types loaded via EFITAUX2
    or FMSTAU2 into ZES(1..4), then distributed:
      - TAU-E-AN   = ZES(1) -> XBXTDAN   (annual)
      - TAU-D-DEP  = ZES(2) -> XBXTDDIR  (direction/departement)
      - TAU-C-COM  = ZES(3) -> XBXTDCOM  (commune)
      - TAU-R-ROL  = ZES(4) -> XBXTDSR   (special role)

    The fields below correspond to the rates actually used in the
    cotisation calculations in EFITA3B8:
      taucom  <- TAU-R-TAUCOM-B      (from XBXTDSR)
      taudep  <- TAU-D-TAUDEP-B      (from XBXTDDIR)
      tautas  <- TAU-D-PTBTAS        (from XBXTDDIR)
      tausyn  <- TAU-R-TAUSYNDSFP-B  (from XBXTDSR)
      taucu   <- TAU-R-TAUCUDFPVN-B  (from XBXTDSR)
      tautsen[0] <- TAU-R-TAUTSE-B   (from XBXTDSR)
      tautsen[1] <- TAU-R-PTBTGP     (from XBXTDSR)
      taugem  <- TAU-R-PTBGEM        (from XBXTDSR)
      tauom[0] <- TAU-C-PBBOMP       (from XBXTDCOM) -- taux plein
      tauom[1] <- TAU-C-PBBOMA       (from XBXTDCOM) -- taux reduit RA
      tauom[2] <- TAU-C-PBBOMB       (from XBXTDCOM) -- taux reduit RB
      tauom[3] <- TAU-C-PBBOMC       (from XBXTDCOM) -- taux reduit RC
      tauom[4] <- TAU-C-PBBOMD       (from XBXTDCOM) -- taux reduit RD
      tauom[5] <- TAU-C-PBBOME       (from XBXTDCOM) -- taux reduit RE
    """
    taucom: Decimal = Decimal(0)     # communal rate
    taudep: Decimal = Decimal(0)     # departmental rate
    tautas: Decimal = Decimal(0)     # TASA rate
    tausyn: Decimal = Decimal(0)     # syndicat rate
    taucu: Decimal = Decimal(0)      # EPCI rate
    tautsen: List[Decimal] = field(
        default_factory=lambda: [Decimal(0), Decimal(0)]
    )  # TSE 1 & TSE 2
    taugem: Decimal = Decimal(0)     # GEMAPI rate
    tauom: List[Decimal] = field(
        default_factory=lambda: [Decimal(0)] * 6
    )  # OM rates: [P, RA, RB, RC, RD, RE]


# ---------------------------------------------------------------------------
# Rate retrieval callback type
# ---------------------------------------------------------------------------
# In the COBOL, EFITAUX2 or FMSTAU2 is CALLed to fetch rates from TAUDIS.
# In this Python reimplementation the caller can supply a callback or use
# the built-in default (rates embedded in AllRates).

RateFetcher = Optional[
    "callable[[str, str, str, str, str], tuple[AllRates, int, int]]"
]


# ---------------------------------------------------------------------------
# Main calculation
# ---------------------------------------------------------------------------

def calculate_tax_batie(
    combat: CombatInput,
    parm: str = "",
    rates: Optional[AllRates] = None,
    rate_fetcher: RateFetcher = None,
) -> tuple[RetourOutput, int, int]:
    """Calculate built-property tax (Taxe Fonciere Batie) for 2018.

    Faithfully reimplements EFITA3B8.

    Parameters
    ----------
    combat : CombatInput
        The parsed 600-byte COMBAT input record.
    parm : str
        The PARM linkage byte. 'M' means use EFITAUX2 path; anything
        else means FMSTAU2 path. Only relevant when rate_fetcher is
        provided.
    rates : AllRates, optional
        Pre-loaded rates. If None and rate_fetcher is None, all rates
        default to zero (useful for unit tests where rates are embedded
        in the combat bases).
    rate_fetcher : callable, optional
        A callback ``(dan, ac3dir, ccocom, ccoifp, ccpper) -> (AllRates, cr, rc)``
        that mimics the CALL 'EFITAUX2'/'FMSTAU2' in COBOL.

    Returns
    -------
    (retour, cr, rc)
        retour : RetourOutput with all computed cotisations and frais.
        cr : int -- code retour (0 = OK, 12 = validation error, 24 = rate error)
        rc : int -- sous-code retour
    """
    # ------------------------------------------------------------------
    # INITIALIZE RETOURB BASEB COTISB
    # ------------------------------------------------------------------
    retour = RetourOutput()
    cr = 0
    rc = 0

    # Fee rate working variables (MOVE statements lines 99-104)
    w_f800frs = F800_FRS
    w_f800arn = F800_ARN
    w_f300frs = F300_FRS
    w_f300arn = F300_ARN
    w_f900frs = F900_FRS
    w_f900arn = F900_ARN

    # ------------------------------------------------------------------
    # VERIFICATION DES PARAMETRES ISSUS DE L'APPEL
    # ------------------------------------------------------------------

    # VERIFICATION DU CODE ARTICLE.  CCOBNB DOIT ETRE 2 (ART BATI)
    if combat.ccobnb != "2":
        cr = 12
        rc = 1

    # VERIFICATION DE L'ANNEE D'IMPOSITION
    if combat.dan != "2018":
        if cr == 0:
            cr = 12
            rc = 2

    # VERIFICATION DE LA NUMERICITE DES BASES D'IMPOSITION
    # In COBOL the fields are PIC S9(10) so NOT NUMERIC fires when the
    # raw bytes are not valid zoned-decimal.  In Python the fields are
    # already int, so we just guard against accidental non-int values.
    try:
        _check = [
            combat.mbacom, combat.mbadep, combat.mbareg,
            combat.mbasyn, combat.mbacu, combat.mbage3,
            combat.mbata3, combat.mbbt13[0], combat.mbbt13[1],
        ]
        for v in _check:
            int(v)
    except (ValueError, TypeError):
        cr = 12
        rc = 11

    # VERIFICATION DU ZONAGE ET DES BASES OM
    for ind in range(6):
        zone = combat.abaom[ind]
        if zone.gtauom not in VALID_GTAUOM:
            cr = 12
            rc = 5
        if zone.gtauom not in ("  ", ""):
            if zone.gtauom.strip() != "":
                try:
                    int(zone.mbaom)
                except (ValueError, TypeError):
                    cr = 12
                    rc = 6
        # MOVE 0 TO COMBAT-MBAOM(IND) when zone is blank
        if zone.gtauom == "  " or zone.gtauom.strip() == "":
            zone.mbaom = 0

    # ------------------------------------------------------------------
    # ON NE RENTRE DANS LA CALCULETTE QUE SI LE CR NON POSITIF
    # ------------------------------------------------------------------
    if cr <= 0:

        # --------------------------------------------------------------
        # RECUPERATION DES TAUX
        # --------------------------------------------------------------
        if rates is None:
            rates = AllRates()

        if rate_fetcher is not None:
            try:
                rates, fetched_cr, fetched_rc = rate_fetcher(
                    combat.dan, combat.ac3dir, combat.ccocom,
                    combat.ccoifp, combat.ccpper,
                )
                if fetched_cr != 0:
                    cr = fetched_cr
                    rc = fetched_rc
            except Exception:
                # ON EXCEPTION MOVE 24 TO CR MOVE 01 TO RC
                cr = 24
                rc = 1

        # If rate fetch failed, skip calculation
        if cr > 0:
            retour = _fill_retour_identity(retour, combat)
            return retour, cr, rc

        # --------------------------------------------------------------
        # CONSTITUTION DE BASEB ET COTISB
        # --------------------------------------------------------------
        # MOVE COMBAT-AIDFIC TO BASEB-CLE / COTISB-CLE
        # MOVE COMBAT-ANUPRO TO BASEB-ANUPRO / COTISB-ANUPRO
        # MOVE COMBAT-CCOBNB TO BASEB-ACODB / COTISB-ACODB
        # MOVE 'I'           TO BASEB-IMPOT / COTISB-IMPOT
        # MOVE 'BN'          TO BASEB-GNEXPL / COTISB-GNEXPL
        # (identity fields -- captured in retour at the end)

        # --- ALIMENTATION DES TAUX ---

        # TAUX COMMUNAL        <- TAU-R-TAUCOM-B
        taucom = rates.taucom
        # TAUX DEPARTEMENTAL   <- TAU-D-TAUDEP-B
        taudep = rates.taudep
        # TAUX TASA            <- TAU-D-PTBTAS
        tautas = rates.tautas
        # TAUX SYNDICAT        <- TAU-R-TAUSYNDSFP-B
        tausyn = rates.tausyn
        # TAUX EPCI            <- TAU-R-TAUCUDFPVN-B
        taucu = rates.taucu
        # TAUX TSE 1           <- TAU-R-TAUTSE-B
        tautsen_1 = rates.tautsen[0]
        # TAUX TSE 2           <- TAU-R-PTBTGP
        tautsen_2 = rates.tautsen[1]
        # TAUX GEMAPI          <- TAU-R-PTBGEM
        taugem = rates.taugem
        # TAUX OM (6 zones)    <- TAU-C-PBBOMP/A/B/C/D/E
        tauom = list(rates.tauom)

        # --- ALIMENTATION DES BASES ---

        # BASE COMMUNALE
        bbcom = combat.mbacom
        # BASE DEPARTEMENTALE
        bbdep = combat.mbadep
        # BASE SYNDICAT DE COMMUNE
        bbsyn = combat.mbasyn
        # BASE EPCI
        bbcu = combat.mbacu
        # BASE GEMAPI
        bbgem = combat.mbage3
        # BASE TASA
        bbtas = combat.mbata3
        # BASE TSE 1 & 2
        bbtsen_1 = combat.mbbt13[0]
        bbtsen_2 = combat.mbbt13[1]

        # OM zones
        gtauom_arr = [combat.abaom[i].gtauom for i in range(6)]
        bbteom_arr = [combat.abaom[i].mbaom for i in range(6)]

        # --------------------------------------------------------------
        # CALCUL DES COTISATIONS BATIES DE TAXE FONCIERE
        # --------------------------------------------------------------

        # COTISATION COMMUNALE
        coticom = _round(Decimal(bbcom) * taucom / 100)

        # COTISATION DEPARTEMENTALE
        cotidep = _round(Decimal(bbdep) * taudep / 100)

        # COTISATION SYNDICAT DE COMMUNE
        cotisyn = _round(Decimal(bbsyn) * tausyn / 100)

        # COTISATION EPCI
        coticu = _round(Decimal(bbcu) * taucu / 100)

        # COTISATION GEMAPI
        mcoge3 = _round(Decimal(bbgem) * taugem / 100)

        # COTISATION TASA
        mcota3 = _round(Decimal(bbtas) * tautas / 100)

        # COTISATION TSE 1
        cotitsen_1 = _round(Decimal(bbtsen_1) * tautsen_1 / 100)

        # COTISATION TSE 2
        cotitsen_2 = _round(Decimal(bbtsen_2) * tautsen_2 / 100)

        # COTISATION AMALGAMEE TSE 1 + TSE 2 + TASA
        mcbtsa = _round(
            Decimal(cotitsen_1) + Decimal(cotitsen_2) + Decimal(mcota3)
        )

        # --------------------------------------------------------------
        # COTISATION ORDURES MENAGERES  (EVALUATE on BASEB-GTAUOM)
        # --------------------------------------------------------------
        cotis_om = [0] * 6
        for ind in range(6):
            zone_code = gtauom_arr[ind]
            base = Decimal(bbteom_arr[ind])
            if zone_code == "  ":
                # WHEN '  '  -> MOVE ZERO TO COTISB-COTIS-OM(IND)
                cotis_om[ind] = 0
            elif zone_code == "P ":
                # WHEN 'P '  -> base * tauom plein / 100
                cotis_om[ind] = _round(base * tauom[0] / 100)
            elif zone_code == " P":
                # WHEN ' P'  -> base * tauom plein / 100
                cotis_om[ind] = _round(base * tauom[0] / 100)
            elif zone_code == "RA":
                # WHEN 'RA'  -> base * tauom reduit A / 100
                cotis_om[ind] = _round(base * tauom[1] / 100)
            elif zone_code == "RB":
                # WHEN 'RB'  -> base * tauom reduit B / 100
                cotis_om[ind] = _round(base * tauom[2] / 100)
            elif zone_code == "RC":
                # WHEN 'RC'  -> base * tauom reduit C / 100
                cotis_om[ind] = _round(base * tauom[3] / 100)
            elif zone_code == "RD":
                # WHEN 'RD'  -> base * tauom reduit D / 100
                cotis_om[ind] = _round(base * tauom[4] / 100)
            elif zone_code == "RE":
                # WHEN 'RE'  -> base * tauom reduit E / 100
                cotis_om[ind] = _round(base * tauom[5] / 100)
            # WHEN OTHER -> CONTINUE  (leave zero)

        # COTISATION TEOMI
        # MOVE COMBAT-MVLTIM TO COTISB-COTIS-OMI
        cotis_omi = combat.mvltim

        # --------------------------------------------------------------
        # CALCUL DES FRAIS
        # --------------------------------------------------------------

        # AMALGAME DES COTISATIONS OM ET DE TEOMI
        # COBOL PERFORM VARYING IND FROM 1 BY 1 UNTIL IND > 7
        #    ADD COTISB-COTIS-OM(IND) TO W-TOTCOTOM
        # Note: COTIS-OM has OCCURS 6, indices 1-6 used; index 7 is zero.
        # Then ADD COTISB-COTIS-OMI TO W-TOTCOTOM
        w_totcotom = sum(cotis_om) + cotis_omi

        # TOTAL DES COTISATIONS SOUMISES AUX FRAIS DE 3%
        w_totcot3 = coticom + cotidep + coticu + mcoge3

        # TOTAL DES COTISATIONS SOUMISES AUX FRAIS DE 8%
        w_totcot8 = w_totcotom + cotisyn + mcota3

        # TOTAL DES COTISATIONS SOUMISES AUX FRAIS DE 9%
        w_totcot9 = cotitsen_1 + cotitsen_2

        # FRAIS A 3%  (assiette 1%, degvt non-valeur 2%)
        fa300 = _round(Decimal(w_totcot3) * w_f300arn)
        w_frais_300 = _round(Decimal(w_totcot3) * w_f300frs)
        fn300 = w_frais_300 - fa300

        # FRAIS A 8%  (assiette 4.4%, degvt non-valeur 3.6%)
        fa800 = _round(Decimal(w_totcot8) * w_f800arn)
        w_frais_800 = _round(Decimal(w_totcot8) * w_f800frs)
        fn800 = w_frais_800 - fa800

        # FRAIS A 9%  (assiette 5.4%, degvt non-valeur 3.6%)
        fa900 = _round(Decimal(w_totcot9) * w_f900arn)
        w_frais_900 = _round(Decimal(w_totcot9) * w_f900frs)
        fn900 = w_frais_900 - fa900

        # REBALANCING:
        # "DANS CERTAINS CAS LES FRAIS D'ASSIETTE SONT INFERIEURS
        #  DE 1 EURO AUX FRAIS DE DEGREVEMENT ET NON VALEUR
        #  DANS CE CAS, ON REEQUILIBRE ARTIFICIELLEMENT"
        if fa800 < fn800:
            fa800 += 1
            fn800 -= 1

        if fa900 < fn900:
            fa900 += 1
            fn900 -= 1

        # --------------------------------------------------------------
        # ALIMENTATION DE LA ZONE DE LINK RETOUR
        # --------------------------------------------------------------

        # MOVE COTISB-CLE TO RETOURB-AIDFIC  (identity fields)
        retour.dan = combat.dan
        retour.cc2dep = combat.cc2dep
        retour.ccodir = combat.ccodir
        retour.ccocom = combat.ccocom
        retour.dsrpar = combat.dsrpar

        # MOVE COTISB-ANUPRO TO RETOURB-ANUPRO
        retour.cgroup = combat.cgroup
        retour.nnupro = combat.nnupro

        # MOVE COTISB-ACODB TO RETOURB-CCOBNB
        retour.ccobnb = combat.ccobnb

        # COTISATIONS TF BATIE
        # COMMUNE
        retour.mctcom = coticom
        # DEPARTEMENT
        retour.mctdep = cotidep
        # SYNDICAT DE COMMUNE
        retour.mctsyn = cotisyn
        # EPCI
        retour.mctcu = coticu
        # GEMAPI
        retour.mcoge3 = mcoge3
        # TASA
        retour.mcota3 = mcota3
        # TSE 1
        retour.mcbt13[0] = cotitsen_1
        # TSE 2
        retour.mcbt13[1] = cotitsen_2
        # AMALGAME TSE 1 + TSE 2 + TASA
        retour.mcbtsa = mcbtsa
        # TEOMI
        retour.mvltim = cotis_omi

        # ORDURES MENAGERES
        for ind in range(6):
            retour.actom[ind].gtauom = gtauom_arr[ind]
            retour.actom[ind].mctom = cotis_om[ind]

        # AMALGAME ORDURES MENAGERES + TEOMI
        retour.tctom = w_totcotom

        # COTISATION TF BATIE HORS FRAIS (COTISATION BRUTE)
        retour.tcthfr = w_totcot3 + w_totcot8 + w_totcot9

        # FRAIS DE LA FDL
        retour.mfa300 = fa300
        retour.mfn300 = fn300
        retour.mfa800 = fa800
        retour.mfn800 = fn800
        retour.mfa900 = fa900
        retour.mfn900 = fn900

        # ALIMENTATION TOTAL DES FRAIS
        retour.tctfra = fa300 + fn300 + fa800 + fn800 + fa900 + fn900

        # ALIMENTATION TOTAL DU
        retour.tctdu = (
            retour.tcthfr
            + retour.mfa300 + retour.mfn300
            + retour.mfa800 + retour.mfn800
            + retour.mfa900 + retour.mfn900
        )

    # ------------------------------------------------------------------
    # RETOUR MAJIC2  --  MOVE RETOURB TO RETOURM / CR TO CRM / RC TO RCM
    # ------------------------------------------------------------------
    return retour, cr, rc


def _fill_retour_identity(
    retour: RetourOutput, combat: CombatInput
) -> RetourOutput:
    """Copy identity fields from COMBAT to RETOUR (used on early exit
    when rate retrieval fails)."""
    retour.dan = combat.dan
    retour.cc2dep = combat.cc2dep
    retour.ccodir = combat.ccodir
    retour.ccocom = combat.ccocom
    retour.dsrpar = combat.dsrpar
    retour.cgroup = combat.cgroup
    retour.nnupro = combat.nnupro
    retour.ccobnb = combat.ccobnb
    return retour


# ── Differential harness runner adapter ────────────────────────────────────


def _scenario_happy_basic():
    combat = CombatInput(
        ccobnb="2", dan="2018", cc2dep="75", ccodir="2", ccocom="056",
        dsrpar="A", cgroup="P", nnupro=12345,
        mbacom=10000, mbadep=10000, mbasyn=5000, mbacu=5000,
        mbage3=10000, mbata3=10000, mbbt13=[5000, 5000],
    )
    rates = AllRates(
        taucom=Decimal("18.99"), taudep=Decimal("12.50"),
        tausyn=Decimal("2.00"), taucu=Decimal("4.00"),
        taugem=Decimal("0.50"), tautas=Decimal("1.00"),
        tautsen=[Decimal("0.80"), Decimal("0.20")],
    )
    return combat, rates


def _scenario_with_om():
    combat = CombatInput(
        ccobnb="2", dan="2018", cc2dep="75", ccodir="2", ccocom="056",
        dsrpar="A", cgroup="P", nnupro=12345,
        mbacom=10000, mbadep=10000, mbasyn=5000, mbacu=5000,
        mbage3=10000, mbata3=10000, mbbt13=[5000, 5000],
        abaom=[
            OmZone(gtauom="P ", mbaom=10000),
            OmZone(gtauom="RA", mbaom=8000),
            OmZone(gtauom="RB", mbaom=6000),
            OmZone(gtauom="  ", mbaom=0),
            OmZone(gtauom="  ", mbaom=0),
            OmZone(gtauom="  ", mbaom=0),
        ],
    )
    rates = AllRates(
        taucom=Decimal("18.99"), taudep=Decimal("12.50"),
        tausyn=Decimal("2.00"), taucu=Decimal("4.00"),
        taugem=Decimal("0.50"), tautas=Decimal("1.00"),
        tautsen=[Decimal("0.80"), Decimal("0.20")],
        tauom=[
            Decimal("10.00"), Decimal("7.50"), Decimal("5.00"),
            Decimal("3.00"), Decimal("2.00"), Decimal("1.00"),
        ],
    )
    return combat, rates


def _scenario_bad_ccobnb():
    combat = CombatInput(ccobnb="1", dan="2018", cc2dep="75", ccodir="2",
                         ccocom="056", dsrpar="A", cgroup="P", nnupro=12345)
    return combat, AllRates()


def _scenario_bad_year():
    combat = CombatInput(ccobnb="2", dan="2017", cc2dep="75", ccodir="2",
                         ccocom="056", dsrpar="A", cgroup="P", nnupro=12345)
    return combat, AllRates()


_TAXE_SCENARIOS = {
    "HAPPY_BASIC": _scenario_happy_basic,
    "WITH_OM": _scenario_with_om,
    "BAD_CCOBNB": _scenario_bad_ccobnb,
    "BAD_YEAR": _scenario_bad_year,
}


def run_vector(inputs: dict) -> dict:
    scenario_name = str(inputs.get("SCENARIO", "")).upper()
    if scenario_name not in _TAXE_SCENARIOS:
        return {"error": f"unknown scenario: {scenario_name!r}"}

    combat, rates = _TAXE_SCENARIOS[scenario_name]()
    retour, cr, rc = calculate_tax_batie(combat, rates=rates)

    return {
        "CR": str(cr), "RC": str(rc),
        "MCTCOM": str(retour.mctcom), "MCTDEP": str(retour.mctdep),
        "MCTSYN": str(retour.mctsyn), "MCTCU": str(retour.mctcu),
        "MCOGE3": str(retour.mcoge3), "MCOTA3": str(retour.mcota3),
        "MCBT13_0": str(retour.mcbt13[0]), "MCBT13_1": str(retour.mcbt13[1]),
        "MCBTSA": str(retour.mcbtsa), "TCTOM": str(retour.tctom),
        "TCTHFR": str(retour.tcthfr),
        "MFA300": str(retour.mfa300), "MFN300": str(retour.mfn300),
        "MFA800": str(retour.mfa800), "MFN800": str(retour.mfn800),
        "MFA900": str(retour.mfa900), "MFN900": str(retour.mfn900),
        "TCTFRA": str(retour.tctfra), "TCTDU": str(retour.tctdu),
        "MVLTIM": str(retour.mvltim),
    }
