"""Scenarios (scenarios/*.yaml): example businesses with the obligations they must get. The tests check
the rules against them, the site's checklist tests replay them, and they double as worked examples.

Each file is validated as it is read, so a misspelt key or a YAML surprise (an unquoted `NO` reads as
false) fails with the field it is in instead of quietly changing a test.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from legalgraph.load import REPO_ROOT

SCENARIOS_DIR = REPO_ROOT / "scenarios"


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    path: Path
    name: str
    description: str = ""
    facts: set[str] = Field(default_factory=set)
    expected: set[str] = Field(default_factory=set, alias="obligations")
    established_in: str | None = None
    markets: set[str] = Field(default_factory=set)
    # Obligation → the national provisions it must name.
    national: dict[str, set[str]] = Field(default_factory=dict)


def load_scenario(path: Path) -> Scenario:
    return Scenario.model_validate({**yaml.safe_load(path.read_text()), "path": path})


def load_scenarios(directory: Path = SCENARIOS_DIR) -> list[Scenario]:
    return [load_scenario(path) for path in sorted(directory.glob("*.yaml"))]
