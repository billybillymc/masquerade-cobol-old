"""
Migration effort estimation — converts structural metrics and readiness scores
into person-day estimates per program and for the full estate.

The model uses industry-standard productivity ranges for COBOL modernization,
adjusted by program complexity, CICS usage, coupling, and test difficulty.

Base rates (person-days per 1000 LOC of code):
  - Simple batch, high readiness:  2-3 days / KLOC
  - Moderate batch:                4-6 days / KLOC
  - Complex CICS online:           8-12 days / KLOC
  - Heavily coupled / unclear:    12-20 days / KLOC

These rates include: analysis, design, coding, unit testing.
They do NOT include: integration testing, UAT, data migration, or deployment.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProgramEstimate:
    program: str
    code_lines: int
    category: str
    readiness_score: float
    base_rate: float
    adjusted_rate: float
    effort_days: float
    risk_level: str
    notes: list[str]


def _base_rate(code_lines: int, has_cics: bool) -> float:
    """Base person-days per KLOC based on category."""
    if has_cics:
        if code_lines > 800:
            return 12.0
        elif code_lines > 400:
            return 10.0
        return 8.0
    else:
        if code_lines > 800:
            return 6.0
        elif code_lines > 400:
            return 4.5
        return 3.0


def _adjust_rate(base: float, readiness: dict) -> tuple[float, list[str]]:
    """Adjust base rate using readiness sub-scores."""
    multiplier = 1.0
    notes = []

    isolation = readiness["isolation"]
    simplicity = readiness["simplicity"]
    dep_clarity = readiness["dependency_clarity"]
    testability = readiness["testability"]

    if isolation < 30:
        multiplier *= 1.4
        notes.append("heavily coupled (+40%)")
    elif isolation < 60:
        multiplier *= 1.15
        notes.append("moderate coupling (+15%)")

    if dep_clarity < 50:
        multiplier *= 1.3
        notes.append("unresolved dependencies (+30%)")
    elif dep_clarity < 80:
        multiplier *= 1.1
        notes.append("some unclear deps (+10%)")

    if testability < 50:
        multiplier *= 1.2
        notes.append("hard to test (+20%)")

    if simplicity >= 80:
        multiplier *= 0.8
        notes.append("simple structure (-20%)")

    return base * multiplier, notes


def _risk_level(effort_days: float, readiness_score: float) -> str:
    if readiness_score >= 70 and effort_days <= 5:
        return "LOW"
    elif readiness_score >= 45 and effort_days <= 15:
        return "MEDIUM"
    elif readiness_score < 30 or effort_days > 30:
        return "HIGH"
    return "MEDIUM"


def estimate_program(readiness: dict) -> ProgramEstimate:
    """Estimate migration effort for a single program."""
    details = readiness["details"]
    code_lines = details["code_lines"]
    has_cics = details["has_cics"]
    category = "CICS Online" if has_cics else "Batch"

    base = _base_rate(code_lines, has_cics)
    adjusted, notes = _adjust_rate(base, readiness)

    kloc = max(code_lines / 1000, 0.05)
    effort = kloc * adjusted
    effort = max(effort, 0.5)

    risk = _risk_level(effort, readiness["composite"])

    return ProgramEstimate(
        program=readiness["program"],
        code_lines=code_lines,
        category=category,
        readiness_score=readiness["composite"],
        base_rate=round(base, 1),
        adjusted_rate=round(adjusted, 1),
        effort_days=round(effort, 1),
        risk_level=risk,
        notes=notes,
    )


def estimate_estate(readiness_ranking: list[dict], dead_code: Optional[dict] = None) -> dict:
    """Full estate migration effort estimate."""
    estimates = [estimate_program(r) for r in readiness_ranking]
    estimates.sort(key=lambda e: e.effort_days)

    total_effort = sum(e.effort_days for e in estimates)
    total_loc = sum(e.code_lines for e in estimates)
    batch_effort = sum(e.effort_days for e in estimates if e.category == "Batch")
    cics_effort = sum(e.effort_days for e in estimates if e.category == "CICS Online")
    high_risk = [e for e in estimates if e.risk_level == "HIGH"]
    low_risk = [e for e in estimates if e.risk_level == "LOW"]

    dead_loc = 0
    if dead_code:
        for orphan in dead_code.get("orphan_programs", []):
            dead_loc += orphan.get("code_lines", 0)

    quick_wins = [e for e in estimates if e.effort_days <= 3 and e.risk_level == "LOW"]
    quick_wins.sort(key=lambda e: e.readiness_score, reverse=True)

    # Wave planning: group into migration waves
    waves = []
    remaining = list(estimates)

    # Wave 1: Quick wins (low effort, high readiness)
    wave1 = [e for e in remaining if e.effort_days <= 5 and e.readiness_score >= 60]
    waves.append({"name": "Wave 1: Quick Wins", "programs": wave1})
    remaining = [e for e in remaining if e not in wave1]

    # Wave 2: Moderate (medium effort or medium readiness)
    wave2 = [e for e in remaining if e.effort_days <= 15 and e.risk_level != "HIGH"]
    waves.append({"name": "Wave 2: Core Migration", "programs": wave2})
    remaining = [e for e in remaining if e not in wave2]

    # Wave 3: Complex (everything else)
    waves.append({"name": "Wave 3: Complex Programs", "programs": remaining})

    return {
        "estimates": estimates,
        "summary": {
            "total_programs": len(estimates),
            "total_loc": total_loc,
            "total_effort_days": round(total_effort, 1),
            "total_effort_weeks": round(total_effort / 5, 1),
            "total_effort_months": round(total_effort / 22, 1),
            "batch_effort_days": round(batch_effort, 1),
            "cics_effort_days": round(cics_effort, 1),
            "high_risk_count": len(high_risk),
            "low_risk_count": len(low_risk),
            "dead_code_loc": dead_loc,
            "quick_win_count": len(quick_wins),
        },
        "waves": [
            {
                "name": w["name"],
                "program_count": len(w["programs"]),
                "effort_days": round(sum(p.effort_days for p in w["programs"]), 1),
                "programs": [p.program for p in w["programs"]],
            }
            for w in waves
        ],
        "quick_wins": [e.program for e in quick_wins[:10]],
    }
