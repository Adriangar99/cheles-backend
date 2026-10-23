"""Every scenario in the OpenSpec specs must have a test whose docstring quotes it.

Spec `<context>/<capability>/spec.md` maps to `tests/<context>/test_<capability>.py`; a test docstring starting with
`Scenario: <title>` (or `Scenarios: <title>, <title>`) covers those scenarios.
"""

import ast
import re
from collections import Counter
from pathlib import Path

from tests.helpers import ROOT

SPEC_ROOTS = [ROOT / "openspec" / "specs", *ROOT.glob("openspec/changes/*/specs")]
SCENARIO = re.compile(r"^#### Scenario: (.+?)\s*$", re.MULTILINE)


def spec_files() -> dict[str, Path]:
    """Capability path -> spec file; a capability under an active change wins over the main spec."""
    specs: dict[str, Path] = {}
    for root in SPEC_ROOTS:
        for spec in root.rglob("spec.md"):
            specs[spec.parent.relative_to(root).as_posix()] = spec
    return specs


def covered_scenarios(test_file: Path) -> Counter[str]:
    covered: Counter[str] = Counter()
    for node in ast.walk(ast.parse(test_file.read_text())):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            docstring = ast.get_docstring(node) or ""
            match = re.match(r"Scenarios?: (.+)", docstring)
            if match:
                covered.update(title.strip() for title in match.group(1).split(","))
    return covered


def test_every_spec_scenario_has_a_test() -> None:
    missing: list[str] = []
    for capability, spec in sorted(spec_files().items()):
        context, name = capability.split("/")
        test_file = ROOT / "tests" / context / f"test_{name.replace('-', '_')}.py"
        required = Counter(SCENARIO.findall(spec.read_text()))
        covered = covered_scenarios(test_file) if test_file.exists() else Counter()
        missing += [f"{capability}: {title}" for title in sorted(required - covered)]

    assert missing == []
