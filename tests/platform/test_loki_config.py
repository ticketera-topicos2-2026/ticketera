"""Tests of the Loki configuration, infra/observability/loki/config.yaml (e1-request-log, task 4.2).

Requirement verified: log-collection, "Log retention is bounded" - Scenario: Retention setting (design RL-14).
Only the standard library is used, so the YAML file is read as text: each setting must appear exactly once, on
its own line, under its section.

Run from the repository root:

    docker run --rm --network none --read-only --user "$(id -u):$(id -g)" -v "$PWD:/repo:ro" -w /repo \\
      python:3.13-alpine@sha256:1e1f6334529d1fb26a2ef619d7cffb30a7c7d7cc1cc7338ebee283a58d1aeaca \\
      python -I -B -m unittest discover -s tests/platform -v
"""

import re
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LOKI_CONFIG = REPOSITORY_ROOT / "infra" / "observability" / "loki" / "config.yaml"
RETENTION_HOURS = "168h"


def section(text: str, name: str) -> str:
    """The indented lines under a top-level key, up to the next top-level key."""
    match = re.search(rf"^{name}:\n((?:[ \t]+.*\n|\n)*)", text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def settings(block: str, key: str) -> list[str]:
    return re.findall(rf"^[ \t]+{key}:[ \t]*(\S+)[ \t]*$", block, flags=re.MULTILINE)


class LokiRetentionTest(unittest.TestCase):
    """Req log-collection: Log retention is bounded - Scenario: Retention setting."""

    def setUp(self) -> None:
        self.text = LOKI_CONFIG.read_text(encoding="utf-8")

    def test_retention_period_is_seven_days(self) -> None:
        self.assertEqual(settings(section(self.text, "limits_config"), "retention_period"), [RETENTION_HOURS])

    def test_compactor_applies_retention(self) -> None:
        self.assertEqual(settings(section(self.text, "compactor"), "retention_enabled"), ["true"])

    def test_data_lives_under_the_volume_path(self) -> None:
        self.assertEqual(settings(section(self.text, "common"), "path_prefix"), ["/loki"])

    def test_usage_reporting_is_off(self) -> None:
        self.assertEqual(settings(section(self.text, "analytics"), "reporting_enabled"), ["false"])


if __name__ == "__main__":
    unittest.main()
