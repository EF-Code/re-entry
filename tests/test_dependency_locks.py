from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).parents[1]


def _lock_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        assert str(requirement.specifier).startswith("=="), line
        versions[requirement.name.lower().replace("_", "-")] = str(
            requirement.specifier
        ).removeprefix("==")
    return versions


def test_project_requirements_are_exact_pinned_and_present_in_locks() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    lock_sets = {
        "runtime": _lock_versions(ROOT / "requirements-runtime.lock"),
        "dev": _lock_versions(ROOT / "requirements-dev.lock"),
    }

    build_requirements = project["build-system"]["requires"]
    all_requirements = list(project["project"]["dependencies"])
    all_requirements.extend(project["project"]["optional-dependencies"]["dev"])
    all_requirements.extend(project["project"]["optional-dependencies"]["live"])
    for raw_requirement in [*build_requirements, *all_requirements]:
        requirement = Requirement(raw_requirement)
        assert len(requirement.specifier) == 1
        specifier = next(iter(requirement.specifier))
        assert specifier.operator == "==", raw_requirement
        key = requirement.name.lower().replace("_", "-")
        lock_name = (
            "dev"
            if raw_requirement in project["project"]["optional-dependencies"]["dev"]
            else "runtime"
        )
        assert lock_sets[lock_name][key] == specifier.version
