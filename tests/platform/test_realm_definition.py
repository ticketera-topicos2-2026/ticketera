"""Static tests of the realm definition, infra/keycloak/ticketera-realm.json (e1-identity-access, task 1.3).

Requirements verified: identity-provisioning, the clients, test users and settings of the `ticketera` realm, and
api-gateway, the access token lifespan that the expired-token check relies on (IA-10, IA-11, IA-18). These tests
read the file as JSON and check what it declares; the smoke test checks how the running identity service behaves
(tests/smoke/identity-checks.sh). Client attributes and protocol mapper settings are strings in a realm
definition, so they are compared as strings.

Only the standard library is used, so no lockfile is needed. Run from the repository root:

    docker run --rm --network none --read-only --user "$(id -u):$(id -g)" -v "$PWD:/repo:ro" -w /repo \\
      python:3.13-alpine@sha256:1e1f6334529d1fb26a2ef619d7cffb30a7c7d7cc1cc7338ebee283a58d1aeaca \\
      python -I -B -m unittest discover -s tests/platform -v
"""

import json
import unittest
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REALM_FILE = REPOSITORY_ROOT / "infra" / "keycloak" / "ticketera-realm.json"

FRONTEND_CLIENT_ID = "ticketera-frontend"
API_TESTS_CLIENT_ID = "ticketera-api-tests"
ADMIN_CLI_CLIENT_ID = "admin-cli"
REALM_ROLE_MAPPER = "oidc-usermodel-realm-role-mapper"

# The test user of each platform role, and the environment variable placeholder of its password.
TEST_USER_ROLES = {"test-admin": "ADMIN", "test-event-owner": "EVENT_OWNER", "test-client": "CLIENT"}


def password_placeholder(role: str) -> str:
    """Returns the placeholder of a test user's password, for example ${TEST_USER_CLIENT_PASSWORD}."""
    return "${TEST_USER_" + role + "_PASSWORD}"


class RealmDefinitionTest(unittest.TestCase):
    """What the realm definition declares about its clients, test users and settings."""

    realm: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        with REALM_FILE.open(encoding="utf-8") as stream:
            cls.realm = json.load(stream)

    def client(self, client_id: str) -> dict[str, Any]:
        """Returns the client the realm declares with this clientId; fails the test when there is not exactly one."""
        clients = [client for client in self.realm.get("clients", []) if client.get("clientId") == client_id]
        self.assertEqual(len(clients), 1, f"the realm must declare exactly one client {client_id}")
        return clients[0]

    def user(self, username: str) -> dict[str, Any]:
        """Returns the user the realm declares with this username; fails the test when there is not exactly one."""
        users = [user for user in self.realm.get("users", []) if user.get("username") == username]
        self.assertEqual(len(users), 1, f"the realm must declare exactly one user {username}")
        return users[0]

    def assert_flows(self, client: dict[str, Any], *, code_flow: bool, password_grant: bool) -> None:
        """Asserts which flows a client allows; the implicit flow and service accounts are always off."""
        self.assertIs(client.get("standardFlowEnabled"), code_flow, "standardFlowEnabled")
        self.assertIs(client.get("directAccessGrantsEnabled"), password_grant, "directAccessGrantsEnabled")
        self.assertIs(client.get("implicitFlowEnabled"), False, "implicitFlowEnabled")
        self.assertIs(client.get("serviceAccountsEnabled"), False, "serviceAccountsEnabled")

    def test_frontend_client_addresses_come_from_frontend_origin(self) -> None:
        """Scenario: Redirect address outside the frontend.
        Scenario: Token request from the frontend's address.
        Scenario: Token request from another origin.
        Scenario: Frontend address changed in local configuration.
        Req: The realm has a client for the frontend (identity-provisioning).

        Case: the redirect URIs are exactly ${FRONTEND_ORIGIN}/signin-callback and
        ${FRONTEND_ORIGIN}/silent-callback, with no wildcard; the only web origin is ${FRONTEND_ORIGIN}; the
        post-logout redirect URI is ${FRONTEND_ORIGIN}/ (IA-10, IA-11).
        """
        client = self.client(FRONTEND_CLIENT_ID)
        self.assertCountEqual(
            client.get("redirectUris", []),
            ["${FRONTEND_ORIGIN}/signin-callback", "${FRONTEND_ORIGIN}/silent-callback"],
        )
        self.assertEqual(client.get("webOrigins"), ["${FRONTEND_ORIGIN}"])
        self.assertEqual(client.get("attributes", {}).get("post.logout.redirect.uris"), "${FRONTEND_ORIGIN}/")

    def test_frontend_client_is_public_with_code_flow_only(self) -> None:
        """Scenario: Password grant with the frontend client.
        Req: The realm has a client for the frontend (identity-provisioning).

        Case: the client is public, so it has no secret, and allows only the authorization code flow (IA-10).
        """
        client = self.client(FRONTEND_CLIENT_ID)
        self.assertIs(client.get("publicClient"), True, "publicClient")
        self.assert_flows(client, code_flow=True, password_grant=False)

    def test_frontend_client_requires_pkce_s256(self) -> None:
        """Scenario: Authorization request without PKCE.
        Scenario: Authorization request with the plain PKCE method.
        Req: The realm has a client for the frontend (identity-provisioning).

        Case: the client attribute pkce.code.challenge.method is S256 (IA-10).
        """
        client = self.client(FRONTEND_CLIENT_ID)
        self.assertEqual(client.get("attributes", {}).get("pkce.code.challenge.method"), "S256")

    def test_frontend_client_tokens_carry_identity_and_roles(self) -> None:
        """Scenario: Access token of the frontend client.
        Scenario: ID token of the frontend client.
        Req: Tokens of the frontend client carry the user's identity and roles (identity-provisioning).

        Case: lightweight access tokens are off, so the access token keeps sub and realm_access.roles; one realm
        role mapper puts realm_access.roles in the ID token only, because the roles scope already puts it in the
        access token (IA-10).
        """
        client = self.client(FRONTEND_CLIENT_ID)
        attributes = client.get("attributes", {})
        self.assertEqual(attributes.get("client.use.lightweight.access.token.enabled"), "false")
        mappers = [
            mapper
            for mapper in client.get("protocolMappers", [])
            if mapper.get("protocolMapper") == REALM_ROLE_MAPPER
        ]
        self.assertEqual(len(mappers), 1, f"the frontend client must have exactly one {REALM_ROLE_MAPPER} mapper")
        config = mappers[0].get("config", {})
        self.assertEqual(config.get("claim.name"), "realm_access.roles")
        self.assertEqual(config.get("multivalued"), "true")
        self.assertEqual(config.get("id.token.claim"), "true")
        self.assertEqual(config.get("access.token.claim"), "false")

    def test_declared_default_scopes_keep_sub_and_roles_in_the_access_token(self) -> None:
        """Scenario: Access token of the frontend client.
        Req: Tokens of the frontend client carry the user's identity and roles (identity-provisioning).

        Scenario: Token for an API test.
        Req: The realm has a client for API tests (identity-provisioning).

        Case: the basic client scope puts sub in the access token and the roles scope puts realm_access.roles. A
        client that declares no defaultClientScopes gets the realm's defaults, which include both; a client that
        declares them replaces those defaults, so its list must include basic and roles.
        """
        for client_id in (FRONTEND_CLIENT_ID, API_TESTS_CLIENT_ID):
            with self.subTest(client_id=client_id):
                client = self.client(client_id)
                if "defaultClientScopes" in client:
                    scopes = client["defaultClientScopes"]
                    self.assertIn("basic", scopes, "the basic scope puts sub in the access token")
                    self.assertIn("roles", scopes, "the roles scope puts realm_access.roles in the access token")

    def test_api_tests_client_allows_the_password_grant_only(self) -> None:
        """Scenario: Token for an API test.
        Scenario: Browser sign-in with the API test client.
        Req: The realm has a client for API tests (identity-provisioning).

        Case: the client is public and allows only the password grant, with no authorization code flow;
        lightweight access tokens are off, so the access token keeps sub and realm_access.roles (IA-10).
        """
        client = self.client(API_TESTS_CLIENT_ID)
        self.assertIs(client.get("publicClient"), True, "publicClient")
        self.assert_flows(client, code_flow=False, password_grant=True)
        self.assertEqual(client.get("attributes", {}).get("client.use.lightweight.access.token.enabled"), "false")

    def test_api_tests_client_access_tokens_last_60_seconds(self) -> None:
        """Scenario: Expired token.
        Req: Requests forwarded on paths that are not public require a valid access token (api-gateway).

        Case: the client attribute access.token.lifespan is 60, so the smoke test can check a token that has
        expired (IA-18).
        """
        client = self.client(API_TESTS_CLIENT_ID)
        self.assertEqual(client.get("attributes", {}).get("access.token.lifespan"), "60")

    def test_admin_cli_allows_no_password_grant(self) -> None:
        """Scenario: Password grant with admin-cli in the ticketera realm.
        Req: The built-in admin client of the realm allows no password grant (identity-provisioning).

        Case: the realm declares admin-cli itself, public and with direct access grants off, so the identity
        service imports it instead of its default (IA-10).
        """
        client = self.client(ADMIN_CLI_CLIENT_ID)
        self.assertIs(client.get("publicClient"), True, "publicClient")
        self.assertIs(client.get("directAccessGrantsEnabled"), False, "directAccessGrantsEnabled")

    def test_registration_is_not_allowed(self) -> None:
        """Scenario: Sign-in page.
        Scenario: Registration address.
        Req: Users cannot register themselves (identity-provisioning).

        Case: registrationAllowed is stated as false, not left to the default.
        """
        self.assertIs(self.realm.get("registrationAllowed"), False, "registrationAllowed")

    def test_realm_display_name_is_gopass(self) -> None:
        """Scenario: Sign-in page title.
        Req: The sign-in page carries the GoPass name (identity-provisioning).
        """
        self.assertEqual(self.realm.get("displayName"), "GoPass")

    def test_each_platform_role_has_one_test_user(self) -> None:
        """Scenario: ADMIN test user.
        Scenario: EVENT_OWNER test user.
        Scenario: CLIENT test user.
        Req: The realm has one test user per platform role (identity-provisioning).

        Case: the realm declares exactly the users test-admin, test-event-owner and test-client, each enabled and
        holding only the realm role of its name (IA-11).
        """
        usernames = [user.get("username") for user in self.realm.get("users", [])]
        self.assertCountEqual(usernames, TEST_USER_ROLES)
        for username, role in TEST_USER_ROLES.items():
            with self.subTest(username=username):
                user = self.user(username)
                self.assertIs(user.get("enabled"), True, "enabled")
                self.assertEqual(user.get("realmRoles"), [role])

    def test_test_users_need_no_extra_step_at_first_sign_in(self) -> None:
        """Scenario: First sign-in needs no extra step.
        Req: The realm has one test user per platform role (identity-provisioning).

        Case: each test user has an email under example.com, a first and a last name and emailVerified true, as
        the declarative user profile requires, and no required actions (IA-11).
        """
        for username in TEST_USER_ROLES:
            with self.subTest(username=username):
                user = self.user(username)
                self.assertTrue(str(user.get("email", "")).endswith("@example.com"), "email under example.com")
                self.assertTrue(user.get("firstName"), "firstName")
                self.assertTrue(user.get("lastName"), "lastName")
                self.assertIs(user.get("emailVerified"), True, "emailVerified")
                self.assertEqual(user.get("requiredActions", []), [], "requiredActions")

    def test_test_user_passwords_are_placeholders(self) -> None:
        """Scenario: Test user passwords in the realm definition.
        Req: The realm definition contains no secrets (identity-provisioning).

        Case: each test user has one credential, a password that is not temporary and whose value is the
        placeholder of its role, such as ${TEST_USER_CLIENT_PASSWORD} (IA-11).
        """
        for username, role in TEST_USER_ROLES.items():
            with self.subTest(username=username):
                credentials = self.user(username).get("credentials", [])
                expected = [{"type": "password", "value": password_placeholder(role), "temporary": False}]
                self.assertEqual(credentials, expected)


if __name__ == "__main__":
    unittest.main()
