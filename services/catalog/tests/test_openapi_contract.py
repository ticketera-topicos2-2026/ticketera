"""Contract test: the committed openapi.yaml against the schema FastAPI generates (change e1-event-catalog,
task 4.1; D-24, design EC-02).

The agreed contract is written first. Every operation must exist on both sides with the same path, method,
operationId, success status and request body schema; neither side may have an operation the other lacks.
"""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from catalog.api.app import create_app

CONTRACT = Path(__file__).resolve().parent.parent / "openapi.yaml"
METHODS = {"get", "head", "post", "put", "patch", "delete"}


class ReachableProbe:
    def is_reachable(self) -> bool:
        return True


def operations(schema: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (path, method): operation
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if method in METHODS
    }


def success_status(operation: dict[str, Any]) -> str:
    codes: list[str] = [str(code) for code in operation["responses"] if str(code).startswith("2")]
    return min(codes)


def body_schema(operation: dict[str, Any]) -> str | None:
    content = operation.get("requestBody", {}).get("content", {}).get("application/json", {})
    reference = content.get("schema", {}).get("$ref")
    return reference.rsplit("/", 1)[-1] if isinstance(reference, str) else None


def test_every_operation_matches_the_agreed_contract() -> None:
    """D-24: the contract test fails when the implementation drifts from the agreed openapi.yaml."""
    agreed = operations(yaml.safe_load(CONTRACT.read_text(encoding="utf-8")))
    generated = operations(create_app(ReachableProbe()).openapi())

    assert sorted(generated) == sorted(agreed)
    for key, operation in agreed.items():
        actual = generated[key]
        assert actual.get("operationId") == operation["operationId"], key
        assert success_status(actual) == success_status(operation), key
        assert body_schema(actual) == body_schema(operation), key
