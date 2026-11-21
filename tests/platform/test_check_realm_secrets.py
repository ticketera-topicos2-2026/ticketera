"""Tests of the realm secret check, scripts/check_realm_secrets.py (project-bootstrap, task 2.4; user credentials
read field by field: e1-identity-access, task 1.1).

Requirement verified: continuous-integration, "The quality check rejects literal secrets in the realm
definition"; for user credentials also identity-provisioning, "The realm definition contains no secrets"
(e1-identity-access). The check inspects JSON keys, not values (DS-20), and only a value that is exactly ${NAME} is a
placeholder. Each test calls the script as a command, as the quality job does, on a small realm fixture from
fixtures/realm/, and asserts the exit status and, for a rejected realm, that the output names the field.

Interface of the script: check_realm_secrets.py <realm.json> [<realm.json> ...]; exit status 0 when there is no
literal secret, 1 when there is at least one, with one line "<file>: literal secret in <field path>" per finding,
and 2 for a usage error or a file that is missing or is not valid JSON.

Only the standard library is used, so no lockfile is needed. Run from the repository root:

    docker run --rm --network none --read-only --user "$(id -u):$(id -g)" -v "$PWD:/repo:ro" -w /repo \\
      python:3.13-alpine@sha256:1e1f6334529d1fb26a2ef619d7cffb30a7c7d7cc1cc7338ebee283a58d1aeaca \\
      python -I -B -m unittest discover -s tests/platform -v
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = REPOSITORY_ROOT / "scripts" / "check_realm_secrets.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "realm"

EXIT_NO_LITERAL_SECRET = 0
EXIT_LITERAL_SECRET = 1
EXIT_USAGE_ERROR = 2


def run_check(realm_file: Path) -> subprocess.CompletedProcess[str]:
    """Runs the check script on one realm file and captures its exit status and output."""
    return subprocess.run(
        [sys.executable, "-I", str(CHECK_SCRIPT), str(realm_file)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


class RealmSecretCheckTest(unittest.TestCase):
    """The realm secret check run as a command on realm fixtures."""

    def setUp(self) -> None:
        self.assertTrue(CHECK_SCRIPT.is_file(), f"check script not found: {CHECK_SCRIPT}")

    def assert_rejected(self, fixture_name: str, field_path: str) -> None:
        """Asserts that the check rejects the fixture and that its output names the field."""
        result = run_check(FIXTURES / fixture_name)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, EXIT_LITERAL_SECRET, output)
        self.assertIn(field_path, output)

    def assert_accepted(self, fixture_name: str) -> None:
        """Asserts that the check accepts the fixture."""
        result = run_check(FIXTURES / fixture_name)
        self.assertEqual(result.returncode, EXIT_NO_LITERAL_SECRET, result.stdout + result.stderr)

    def test_literal_client_secret_is_rejected(self) -> None:
        """Scenario: Realm definition with a literal client secret.

        Req: The quality check rejects literal secrets in the realm definition.
        """
        self.assert_rejected("literal-client-secret.json", "clients[0].secret")

    def test_client_secret_placeholder_is_accepted(self) -> None:
        """Scenario: Realm definition with a placeholder (the value is exactly ${FRONT_CLIENT_SECRET}).

        Req: The quality check rejects literal secrets in the realm definition.
        """
        self.assert_accepted("placeholder-client-secret.json")

    def test_client_authenticator_type_value_is_accepted(self) -> None:
        """Scenario: Realm definition with a placeholder, inverse case of DS-20: "client-secret" as the value of
        clientAuthenticatorType is not a secret, because the check inspects keys, not values.

        Req: The quality check rejects literal secrets in the realm definition.
        """
        self.assert_accepted("client-authenticator-type.json")

    def test_placeholder_with_default_value_is_rejected(self) -> None:
        """Scenario: Realm definition with a literal client secret, written as ${FRONT_CLIENT_SECRET:abc123}: the
        default value is a literal, so only exactly ${NAME} is a placeholder.

        Req: The quality check rejects literal secrets in the realm definition.
        """
        self.assert_rejected("placeholder-with-default-client-secret.json", "clients[0].secret")

    def test_partial_placeholder_is_rejected(self) -> None:
        """Scenario: Realm definition with a literal client secret, written as abc${FRONT_CLIENT_SECRET}: a value
        that only contains a placeholder is not exactly ${NAME}.

        Req: The quality check rejects literal secrets in the realm definition.
        """
        self.assert_rejected("partial-placeholder-client-secret.json", "clients[0].secret")

    def test_literal_private_key_is_rejected(self) -> None:
        """Scenario: Realm definition with a literal client secret, applied to privateKey, a secret field named in
        the requirement; a key that contains dots is written as ["..."] in the field path.

        Req: The quality check rejects literal secrets in the realm definition.
        """
        self.assert_rejected(
            "literal-private-key.json",
            'components["org.keycloak.keys.KeyProvider"][0].config.privateKey',
        )

    def test_literal_user_credentials_are_rejected(self) -> None:
        """Scenario: Realm definition with a literal client secret.
        Req: The quality check rejects literal secrets in the realm definition (continuous-integration).

        Scenario: Test user passwords in the realm definition.
        Req: The realm definition contains no secrets (identity-provisioning).

        Case: the value of a user credential is a literal password, and the output names that field (IA-12).
        """
        self.assert_rejected("literal-user-credentials.json", "users[0].credentials[0].value")

    def test_user_credential_placeholder_is_accepted(self) -> None:
        """Scenario: Realm definition with a placeholder.
        Req: The quality check rejects literal secrets in the realm definition (continuous-integration).

        Scenario: Test user passwords in the realm definition.
        Req: The realm definition contains no secrets (identity-provisioning).

        Case: the value of a user credential is exactly ${TEST_USER_CLIENT_PASSWORD}, next to the non-secret fields
        type, temporary and userLabel (IA-12).
        """
        self.assert_accepted("placeholder-user-credentials.json")

    def test_exported_password_hash_is_rejected(self) -> None:
        """Scenario: Realm definition with a literal client secret.
        Req: The quality check rejects literal secrets in the realm definition (continuous-integration).

        Scenario: Test user passwords in the realm definition.
        Req: The realm definition contains no secrets (identity-provisioning).

        Case: a user credential exported with its hash; secretData and credentialData are literals, and the output
        names each field (IA-12).
        """
        self.assert_rejected("exported-hash-user-credentials.json", "users[0].credentials[0].secretData")
        self.assert_rejected("exported-hash-user-credentials.json", "users[0].credentials[0].credentialData")

    def test_user_credential_placeholder_with_default_value_is_rejected(self) -> None:
        """Scenario: Realm definition with a literal client secret.
        Req: The quality check rejects literal secrets in the realm definition (continuous-integration).

        Scenario: Test user passwords in the realm definition.
        Req: The realm definition contains no secrets (identity-provisioning).

        Case: the value of a user credential is ${TEST_USER_CLIENT_PASSWORD:example-literal-password}; the default
        value is a literal, and the output names that field (IA-12).
        """
        self.assert_rejected("placeholder-with-default-user-credentials.json", "users[0].credentials[0].value")

    def test_literal_smtp_password_is_rejected(self) -> None:
        """Scenario: Realm definition with a literal client secret, applied to password, a field that holds a
        secret.

        Req: The quality check rejects literal secrets in the realm definition.
        """
        self.assert_rejected("literal-smtp-password.json", "smtpServer.password")

    def test_literal_identity_provider_client_secret_is_rejected(self) -> None:
        """Scenario: Realm definition with a literal client secret, applied to clientSecret in an identity provider.

        Req: The quality check rejects literal secrets in the realm definition.
        """
        self.assert_rejected(
            "literal-identity-provider-client-secret.json",
            "identityProviders[0].config.clientSecret",
        )

    def test_missing_realm_file_is_a_usage_error(self) -> None:
        """Guard of the check's interface: a missing file exits with 2 and is named, so a mistyped path in the
        quality job fails instead of passing.

        Req: The quality check rejects literal secrets in the realm definition.
        """
        missing_file = FIXTURES / "does-not-exist.json"
        result = run_check(missing_file)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, EXIT_USAGE_ERROR, output)
        self.assertIn(missing_file.name, output)


if __name__ == "__main__":
    unittest.main()
