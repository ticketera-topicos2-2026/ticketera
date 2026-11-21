"""Realm secret check: rejects literal secrets in identity service realm definitions.

Requirement: continuous-integration, "The quality check rejects literal secrets in the realm definition" (DS-20).
The check inspects JSON keys, never values: every field whose key names a secret (for example `secret`,
`clientSecret` or `privateKey`, at any depth) must hold no literal, that is, a placeholder that is exactly
`${NAME}`, an empty value, or a list of those. Values are never searched, because `client-secret` is a legitimate
value of `clientAuthenticatorType`.

Each object of a `credentials` list, such as a user's password, is read field by field (IA-12): its `value` must be
exactly a `${NAME}` placeholder, and any field other than `type`, `value`, `temporary` and `userLabel`, such as the
`secretData` and `credentialData` of an exported password hash, is a literal secret. Requirement:
identity-provisioning, "The realm definition contains no secrets".

Usage: check_realm_secrets.py <realm.json> [<realm.json> ...]

Exit status: 0 when no file holds a literal secret; 1 when at least one does, with one line
"<file>: literal secret in <field path>" per finding on standard output; 2 for a usage error or a file that is
missing or is not valid JSON, reported on standard error and naming the file.

Only the standard library is used. Run it from the repository root in the digest-pinned Python container (DS-25):

    docker run --rm --network none --read-only --user "$(id -u):$(id -g)" -v "$PWD:/repo:ro" -w /repo \\
      python:3.13-alpine@sha256:1e1f6334529d1fb26a2ef619d7cffb30a7c7d7cc1cc7338ebee283a58d1aeaca \\
      python -I -B scripts/check_realm_secrets.py infra/keycloak/ticketera-realm.json

Change project-bootstrap, task 2.5 (tests: tests/platform/test_check_realm_secrets.py, task 2.4); credentials read
field by field: change e1-identity-access, task 1.2 (tests: task 1.1).
"""

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

EXIT_NO_LITERAL_SECRET = 0
EXIT_LITERAL_SECRET = 1
EXIT_USAGE_ERROR = 2

USAGE = "usage: check_realm_secrets.py <realm.json> [<realm.json> ...]"

# Keys whose values are secrets, compared without case: client and identity provider secrets, key material, user
# credentials and passwords such as that of the SMTP server.
SECRET_KEYS = frozenset({"secret", "clientsecret", "privatekey", "credentials", "password"})
CREDENTIALS_KEY = "credentials"
# Fields of a credential object that hold no secret, compared exactly; `value` must also be a placeholder.
CREDENTIAL_VALUE_FIELD = "value"
CREDENTIAL_NON_SECRET_FIELDS = frozenset({"type", CREDENTIAL_VALUE_FIELD, "temporary", "userLabel"})
PLACEHOLDER = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class RealmFileError(Exception):
    """A realm file that cannot be checked: missing, unreadable or not valid JSON."""


def is_secret_key(key: str) -> bool:
    """Tells whether a JSON key names a field that holds a secret."""
    return key.casefold() in SECRET_KEYS


def is_placeholder(value: object) -> bool:
    """Tells whether a value is exactly a ${NAME} placeholder, with no default value and no text around it."""
    return isinstance(value, str) and PLACEHOLDER.fullmatch(value) is not None


def holds_no_literal(value: object) -> bool:
    """Tells whether the value of a secret field holds no literal: null, an empty string, a placeholder that is
    exactly ${NAME}, or a list of those. A default value (${NAME:default}) or text around the placeholder is a
    literal."""
    if value is None:
        return True
    if isinstance(value, str):
        return value == "" or is_placeholder(value)
    if isinstance(value, list):
        return all(holds_no_literal(item) for item in value)
    return False


def field_path(parent: str, key: str) -> str:
    """Appends a key to a field path: `.key` for an identifier, `["key"]` otherwise, such as a key with dots."""
    if IDENTIFIER.fullmatch(key) is None:
        return f"{parent}[{json.dumps(key)}]"
    return f"{parent}.{key}" if parent else key


def literal_credential_paths(credential: dict[str, object], path: str) -> Iterator[str]:
    """Yields the path of every field of one credential object that holds a literal: a `value` that is not exactly
    a ${NAME} placeholder, and any field other than type, value, temporary and userLabel."""
    for key, child in credential.items():
        child_path = field_path(path, key)
        if key not in CREDENTIAL_NON_SECRET_FIELDS:
            yield child_path
        elif key == CREDENTIAL_VALUE_FIELD and not is_placeholder(child):
            yield child_path


def literal_secret_field_paths(key: str, value: object, path: str) -> Iterator[str]:
    """Yields the paths of a secret field that hold a literal: each object of a `credentials` list is read field by
    field, and any other value of a secret field must hold no literal as a whole."""
    if key.casefold() == CREDENTIALS_KEY and isinstance(value, list):
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            if isinstance(item, dict):
                yield from literal_credential_paths(item, item_path)
            elif not holds_no_literal(item):
                yield item_path
    elif not holds_no_literal(value):
        yield path


def literal_secret_paths(value: object, path: str = "") -> Iterator[str]:
    """Yields the path of every secret field, at any depth of a JSON value, that holds a literal."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = field_path(path, key)
            if is_secret_key(key):
                yield from literal_secret_field_paths(key, child, child_path)
            else:
                yield from literal_secret_paths(child, child_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from literal_secret_paths(item, f"{path}[{index}]")


def load_realm(realm_file: Path) -> object:
    """Reads a realm definition; raises RealmFileError, naming the file, when it cannot be read as JSON."""
    try:
        with realm_file.open(encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError:
        raise RealmFileError(f"{realm_file}: file not found") from None
    except OSError as error:
        raise RealmFileError(f"{realm_file}: cannot be read ({error.strerror})") from None
    except ValueError as error:
        raise RealmFileError(f"{realm_file}: not valid JSON ({error})") from None


def check_realm_file(realm_file: Path) -> int:
    """Checks one realm file, prints its findings or its error, and returns its exit status."""
    try:
        realm = load_realm(realm_file)
    except RealmFileError as error:
        print(f"check_realm_secrets: {error}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    paths = list(literal_secret_paths(realm))
    for path in paths:
        print(f"{realm_file}: literal secret in {path}")
    return EXIT_LITERAL_SECRET if paths else EXIT_NO_LITERAL_SECRET


def main(arguments: list[str]) -> int:
    """Checks every realm file named in the arguments and returns the most severe exit status."""
    if not arguments:
        print(USAGE, file=sys.stderr)
        return EXIT_USAGE_ERROR
    # Every file is checked; the exit statuses are ordered by severity, so the highest one wins.
    statuses = [check_realm_file(Path(argument)) for argument in arguments]
    return max(statuses)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
