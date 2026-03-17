"""
Reimplementation of Star Trek COBOL game — validation and initialization logic.

Only the deterministic parts are reimplemented for differential testing:
- Title screen output
- Name/skill level input validation
- Invalid skill level error message
- Mission briefing text (parameterized by skill level)

The random game logic (Klingon placement, combat) is NOT reimplemented
since it depends on system time seeding.
"""


# ── Constants from COBOL source ────────────────────────────────────────────

TITLE = "*STAR TREK*"
WELCOME_LINES = [
    "Congratulations - you have just been appointed",
    "Captain of the U.S.S. Enterprise.",
]
ENTER_NAME_PROMPT = "Please enter your name, Captain"
SKILL_PROMPT = "And your skill level (1-4)?"
INVALID_SKILL_MSG = "INVALID SKILL LEVEL"
RETRY_SKILL_MSG = "Enter your skill level (1-4)"


def validate_skill_level(level: str) -> tuple[bool, str]:
    """Validate skill level input.

    Returns (valid, message). COBOL logic:
    IF skill-level < 1 OR > 4 → INVALID SKILL LEVEL
    """
    try:
        n = int(level.strip())
        if n < 1 or n > 4:
            return False, INVALID_SKILL_MSG
        return True, ""
    except (ValueError, TypeError):
        return False, INVALID_SKILL_MSG


def get_mission_params(skill_level: int) -> dict:
    """Compute mission parameters based on skill level.

    From COBOL source (1260-assign paragraph):
    klingons = skill * 8
    star_dates = klingons (one star date per klingon)
    fuel = 40000 (constant)
    torpedoes = 5 (constant, adjusted by skill elsewhere)
    """
    klingons = skill_level * 8
    star_dates = klingons
    return {
        "klingons": klingons,
        "star_dates": star_dates,
        "fuel": 40000,
        "torpedoes": 5,
    }


def format_title_screen() -> list[str]:
    """Generate the title screen output."""
    return [TITLE, ""] + WELCOME_LINES + [""]


def format_mission_briefing(captain_name: str, params: dict) -> list[str]:
    """Generate the mission briefing text."""
    return [
        "*MESSAGE FROM STAR FLEET COMMAND*",
        "",
        f"Attention - Captain {captain_name}",
        "Your mission is to destroy the",
        f"{params['klingons']} Klingon ships that have invaded",
        "the galaxy to attack Star Fleet HQ",
    ]
