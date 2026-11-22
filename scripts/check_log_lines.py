"""Checks log lines against a JSON Schema (change e1-request-log, task 1.1; design RL-08).

Usage: check_log_lines.py <schema.json> < lines

Every non-empty line of standard input must be one JSON object that satisfies the schema. Prints one
"line <n>: <reason>" per failing line. Exit status: 0 when every line passes (also when there are none), 1 when any
line fails, 2 for a usage error, an unreadable schema or a schema keyword this checker does not support.

Only the standard library is used, so the quality job and the smoke test run it in a plain Python container. It
supports the subset of JSON Schema that tests/platform/*-log.schema.json use, and rejects any other keyword instead
of ignoring it, so a schema can never ask for a check that silently does not happen:

- at the top level: type "object", required, additionalProperties false, properties;
- in each property: type (a name or a list of "string", "integer", "number", "null"), pattern (applied to strings
  only, as in JSON Schema), const, enum, minimum, maximum.
"""

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

EXIT_ALL_LINES_PASS = 0
EXIT_SOME_LINE_FAILS = 1
EXIT_USAGE_ERROR = 2

ANNOTATION_KEYWORDS = {"$schema", "$id", "title", "description"}
TOP_LEVEL_KEYWORDS = ANNOTATION_KEYWORDS | {"type", "required", "additionalProperties", "properties"}
PROPERTY_KEYWORDS = ANNOTATION_KEYWORDS | {"type", "pattern", "const", "enum", "minimum", "maximum"}

# bool is a subclass of int in Python, but JSON true and false are never numbers.
TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "null": lambda value: value is None,
}


class SchemaError(Exception):
    """The schema cannot be read, or uses something this checker does not support."""


def load_schema(path: Path) -> dict[str, Any]:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SchemaError(f"cannot read the schema {path}: {error}") from error
    validate_schema(schema)
    return schema


def validate_schema(schema: Any) -> None:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise SchemaError('the schema must be an object with "type": "object"')
    reject_unknown_keywords(schema, TOP_LEVEL_KEYWORDS, "the schema")
    if schema.get("additionalProperties", False) is not False:
        raise SchemaError('only "additionalProperties": false is supported')
    for name, rules in schema.get("properties", {}).items():
        if not isinstance(rules, dict):
            raise SchemaError(f"property {name}: its rules must be an object")
        reject_unknown_keywords(rules, PROPERTY_KEYWORDS, f"property {name}")
        for type_name in allowed_types(rules):
            if type_name not in TYPE_CHECKS:
                raise SchemaError(f"property {name}: unsupported type {type_name}")
        if "pattern" in rules:
            try:
                re.compile(rules["pattern"])
            except re.error as error:
                raise SchemaError(f"property {name}: invalid pattern: {error}") from error


def reject_unknown_keywords(rules: dict[str, Any], supported: set[str], where: str) -> None:
    unknown = sorted(set(rules) - supported)
    if unknown:
        raise SchemaError(f"{where}: unsupported keyword(s): {', '.join(unknown)}")


def allowed_types(rules: dict[str, Any]) -> list[str]:
    declared = rules.get("type", [])
    return [declared] if isinstance(declared, str) else list(declared)


def line_problems(line: str, schema: dict[str, Any]) -> list[str]:
    try:
        document = json.loads(line)
    except ValueError:
        return ["not valid JSON"]
    if not isinstance(document, dict):
        return ["not a JSON object"]
    properties: dict[str, dict[str, Any]] = schema.get("properties", {})
    problems = [f"missing field {name}" for name in schema.get("required", []) if name not in document]
    if schema.get("additionalProperties", True) is False:
        problems += [f"unexpected field {name}" for name in document if name not in properties]
    for name, value in document.items():
        if name in properties:
            problems += [f"field {name}: {problem}" for problem in value_problems(value, properties[name])]
    return problems


def value_problems(value: Any, rules: dict[str, Any]) -> list[str]:
    types = allowed_types(rules)
    if types and not any(TYPE_CHECKS[type_name](value) for type_name in types):
        return [f"{json.dumps(value)} is not of type {' or '.join(types)}"]
    problems = []
    if "const" in rules and value != rules["const"]:
        problems.append(f"{json.dumps(value)} is not {json.dumps(rules['const'])}")
    if "enum" in rules and value not in rules["enum"]:
        problems.append(f"{json.dumps(value)} is not one of {json.dumps(rules['enum'])}")
    if "pattern" in rules and isinstance(value, str) and not re.search(rules["pattern"], value):
        problems.append(f"{json.dumps(value)} does not match {rules['pattern']}")
    if TYPE_CHECKS["number"](value):
        if "minimum" in rules and value < rules["minimum"]:
            problems.append(f"{value} is below {rules['minimum']}")
        if "maximum" in rules and value > rules["maximum"]:
            problems.append(f"{value} is above {rules['maximum']}")
    return problems


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print("usage: check_log_lines.py <schema.json> < lines", file=sys.stderr)
        return EXIT_USAGE_ERROR
    try:
        schema = load_schema(Path(arguments[0]))
    except SchemaError as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE_ERROR
    failed = False
    for number, line in enumerate(sys.stdin, start=1):
        if not line.strip():
            continue
        problems = line_problems(line, schema)
        if problems:
            failed = True
            print(f"line {number}: {'; '.join(problems)}")
    return EXIT_SOME_LINE_FAILS if failed else EXIT_ALL_LINES_PASS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
