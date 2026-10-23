"""The versioned OpenAPI contract (openapi.json), consumed by cheles-frontend, must match the app."""

import json

from app.main import app
from tests.helpers import ROOT


def test_openapi_json_matches_the_app() -> None:
    contract = ROOT / "openapi.json"
    assert contract.exists(), "openapi.json is missing: run `uv run python -m app.cli openapi`"

    assert json.loads(contract.read_text()) == app.openapi(), (
        "openapi.json is out of date: run `uv run python -m app.cli openapi` and commit it"
    )
