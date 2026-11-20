"""Tests of the log line schemas and of their checker, scripts/check_log_lines.py (e1-request-log, task 1.1).

Requirements verified: api-gateway, "The gateway access log line has a fixed set of fields", and request-log, "The
request log line has a fixed set of fields". The schemas live in tests/platform/ and are shared by every service and
by the smoke test, so all of them check the same line.

Interface of the script: check_log_lines.py <schema.json> reads log lines on standard input; every non-empty line
must be one JSON object that satisfies the schema. Exit status 0 when every line passes, 1 when any line fails (one
"line <n>: <reason>" per failure), 2 for a usage error, an unreadable schema or a schema keyword it does not support.

Only the standard library is used. Run from the repository root:

    docker run --rm --network none --read-only --user "$(id -u):$(id -g)" -v "$PWD:/repo:ro" -w /repo \\
      python:3.13-alpine@sha256:1e1f6334529d1fb26a2ef619d7cffb30a7c7d7cc1cc7338ebee283a58d1aeaca \\
      python -I -B -m unittest discover -s tests/platform -v
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = REPOSITORY_ROOT / "scripts" / "check_log_lines.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "log-schema"
GATEWAY_SCHEMA = Path(__file__).resolve().parent / "gateway-log.schema.json"
SERVICE_SCHEMA = Path(__file__).resolve().parent / "request-log.schema.json"

EXIT_ALL_LINES_PASS = 0
EXIT_SOME_LINE_FAILS = 1
EXIT_USAGE_ERROR = 2

GATEWAY_LINE = {
    "timestamp": "2026-11-20T21:47:47+00:00",
    "service": "gateway",
    "correlation_id": "3f2a9c0d4b5e6f708192a3b4c5d6e7f8",
    "method": "GET",
    "path": "/api/catalog/health",
    "status": 200,
    "duration_seconds": 0.004,
    "client_address": "172.18.0.1",
}

SERVICE_LINE = {
    "timestamp": "2026-11-20T21:47:47.123+00:00",
    "service": "catalog",
    "correlation_id": "3f2a9c0d4b5e6f708192a3b4c5d6e7f8",
    "method": "GET",
    "route": "/health",
    "status": 200,
    "duration_seconds": 0.002,
    "user_id": None,
}


def run_check(schema: Path, *lines: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-B", str(CHECK_SCRIPT), str(schema)],
        input="".join(line + "\n" for line in lines),
        capture_output=True,
        text=True,
        check=False,
    )


def with_changes(line: dict[str, object], **changes: object) -> str:
    return json.dumps({**line, **changes})


def without(line: dict[str, object], field: str) -> str:
    return json.dumps({key: value for key, value in line.items() if key != field})


class GatewayLineTest(unittest.TestCase):
    """Req api-gateway: The gateway access log line has a fixed set of fields - Scenario: Fields of a gateway line."""

    def assert_rejected(self, line: str, field: str) -> None:
        result = run_check(GATEWAY_SCHEMA, line)
        self.assertEqual(result.returncode, EXIT_SOME_LINE_FAILS, result.stdout + result.stderr)
        self.assertIn(field, result.stdout)

    def test_valid_line_passes(self) -> None:
        result = run_check(GATEWAY_SCHEMA, json.dumps(GATEWAY_LINE))
        self.assertEqual(result.returncode, EXIT_ALL_LINES_PASS, result.stdout + result.stderr)

    def test_extra_field_fails(self) -> None:
        self.assert_rejected(with_changes(GATEWAY_LINE, authorization="Bearer x"), "authorization")

    def test_missing_field_fails(self) -> None:
        self.assert_rejected(without(GATEWAY_LINE, "correlation_id"), "correlation_id")

    def test_status_as_string_fails(self) -> None:
        self.assert_rejected(with_changes(GATEWAY_LINE, status="200"), "status")

    def test_short_correlation_id_fails(self) -> None:
        self.assert_rejected(with_changes(GATEWAY_LINE, correlation_id="3f2a9c0d4b5e6f708192a3b4c5d6e7f"), "correlation_id")

    def test_other_service_name_fails(self) -> None:
        self.assert_rejected(with_changes(GATEWAY_LINE, service="catalog"), "service")

    def test_negative_duration_fails(self) -> None:
        self.assert_rejected(with_changes(GATEWAY_LINE, duration_seconds=-0.001), "duration_seconds")

    def test_line_that_is_not_json_fails(self) -> None:
        self.assert_rejected('172.18.0.1 - - [20/Nov/2026:21:47:47 +0000] "GET / HTTP/1.1" 200', "JSON")


class ServiceLineTest(unittest.TestCase):
    """Req request-log: The request log line has a fixed set of fields - Scenarios: Fields of a request log line;
    Same schema in every service."""

    def assert_rejected(self, line: str, field: str) -> None:
        result = run_check(SERVICE_SCHEMA, line)
        self.assertEqual(result.returncode, EXIT_SOME_LINE_FAILS, result.stdout + result.stderr)
        self.assertIn(field, result.stdout)

    def test_valid_lines_of_every_service_pass(self) -> None:
        lines = [with_changes(SERVICE_LINE, service=service) for service in ("catalog", "sales", "payments")]
        result = run_check(SERVICE_SCHEMA, *lines)
        self.assertEqual(result.returncode, EXIT_ALL_LINES_PASS, result.stdout + result.stderr)

    def test_null_correlation_id_route_and_user_pass(self) -> None:
        line = with_changes(SERVICE_LINE, correlation_id=None, route=None, user_id=None)
        result = run_check(SERVICE_SCHEMA, line)
        self.assertEqual(result.returncode, EXIT_ALL_LINES_PASS, result.stdout + result.stderr)

    def test_authenticated_user_passes(self) -> None:
        line = with_changes(SERVICE_LINE, user_id="5b0c1d2e-3f40-4a5b-8c6d-7e8f9a0b1c2d", status=403)
        result = run_check(SERVICE_SCHEMA, line)
        self.assertEqual(result.returncode, EXIT_ALL_LINES_PASS, result.stdout + result.stderr)

    def test_extra_field_fails(self) -> None:
        self.assert_rejected(with_changes(SERVICE_LINE, query="access_token=x"), "query")

    def test_missing_user_field_fails(self) -> None:
        self.assert_rejected(without(SERVICE_LINE, "user_id"), "user_id")

    def test_unknown_service_fails(self) -> None:
        self.assert_rejected(with_changes(SERVICE_LINE, service="gateway"), "service")

    def test_malformed_correlation_id_fails(self) -> None:
        self.assert_rejected(with_changes(SERVICE_LINE, correlation_id='abc"}'), "correlation_id")

    def test_boolean_status_fails(self) -> None:
        self.assert_rejected(with_changes(SERVICE_LINE, status=True), "status")

    def test_timestamp_without_milliseconds_fails(self) -> None:
        self.assert_rejected(with_changes(SERVICE_LINE, timestamp="2026-11-20T21:47:47+00:00"), "timestamp")


class CheckerTest(unittest.TestCase):
    """Behavior of the checker itself, which both schemas rely on."""

    def test_every_failing_line_is_reported_with_its_number(self) -> None:
        result = run_check(
            SERVICE_SCHEMA,
            json.dumps(SERVICE_LINE),
            with_changes(SERVICE_LINE, status="200"),
            "",
            with_changes(SERVICE_LINE, extra=1),
        )
        self.assertEqual(result.returncode, EXIT_SOME_LINE_FAILS)
        self.assertIn("line 2:", result.stdout)
        self.assertIn("line 4:", result.stdout)
        self.assertNotIn("line 1:", result.stdout)

    def test_no_lines_pass(self) -> None:
        result = run_check(SERVICE_SCHEMA)
        self.assertEqual(result.returncode, EXIT_ALL_LINES_PASS, result.stdout + result.stderr)

    def test_unsupported_schema_keyword_is_a_usage_error(self) -> None:
        result = run_check(FIXTURES / "unsupported-keyword.schema.json", "{}")
        self.assertEqual(result.returncode, EXIT_USAGE_ERROR)
        self.assertIn("format", result.stderr)

    def test_missing_schema_is_a_usage_error(self) -> None:
        result = run_check(REPOSITORY_ROOT / "missing.schema.json", "{}")
        self.assertEqual(result.returncode, EXIT_USAGE_ERROR)


if __name__ == "__main__":
    unittest.main()
