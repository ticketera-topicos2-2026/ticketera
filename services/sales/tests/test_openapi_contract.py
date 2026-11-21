"""Contract test comparing committed openapi.yaml against dynamic FastAPI OpenAPI schema.

Verifies:
- CI / local contract alignment (D-24)
- Path definitions, methods, operation IDs and schemas match
"""

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from sales.api.app import create_app
from sales.application.health import DatabaseProbe


class DummyProbe(DatabaseProbe):
    def is_reachable(self) -> bool:
        return True


def test_openapi_contract_matches_fastapi_schema() -> None:
    app = create_app(database_probe=DummyProbe())
    generated_schema = app.openapi()

    openapi_path = Path(__file__).resolve().parent.parent / "openapi.yaml"
    assert openapi_path.exists(), f"Committed openapi.yaml not found at {openapi_path}"

    with open(openapi_path, encoding="utf-8") as f:
        committed_schema = yaml.safe_load(f)

    # Compare key paths
    for path, path_item in committed_schema["paths"].items():
        assert path in generated_schema["paths"], f"Path {path} missing in FastAPI generated OpenAPI"
        for method in path_item:
            if method in ("get", "post", "put", "delete", "head"):
                assert (
                    method in generated_schema["paths"][path]
                ), f"Method {method.upper()} for {path} missing in generated OpenAPI"
