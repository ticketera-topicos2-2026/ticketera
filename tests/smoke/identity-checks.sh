# shellcheck shell=bash
# Identity checks of the smoke test: the clients, settings, test users and tokens of the ticketera realm, verified
# through the gateway (IA-17). Sourced by tests/smoke/smoke-test.sh, whose helpers it uses (pass, fail, http_get,
# http_headers, last_response, expect_allowed_origin, response_header_values, run_python, json_string_field,
# config_value) and whose main calls run_identity_checks; it is not run on its own.
#
# Test user passwords and the bootstrap administrator's credentials are read from the environment of the identity
# service in "docker compose config", so the checks use the values the running system was started with. Passwords,
# refresh tokens and the administrator's access token reach curl on its standard input, never on its command line.
#
# A rejection check must not pass because a client, a user or the realm is missing. The identity service answers an
# unknown client with "Client not found." on its error page, with invalid_client (401) at its token endpoint, and
# with an Access-Control-Allow-Origin header that echoes any origin, and an unknown user with invalid_grant, as a
# wrong password. So each check asserts the answer of an existing client, and the wrong-password check needs the
# right password to work first. The markers below come from the pages of Keycloak 26.8 and its login theme.
#
# Change e1-identity-access, tasks 1.4 and 1.5 (design: Test Strategy, platform/identity-provisioning,
# identity/access-token).

readonly REALM_PATH="/auth/realms/ticketera"
readonly MASTER_REALM_PATH="/auth/realms/master"
readonly ADMIN_REALM_PATH="/auth/admin/realms/ticketera"
readonly FRONTEND_CLIENT_ID="ticketera-frontend"
readonly API_TESTS_CLIENT_ID="ticketera-api-tests"
readonly ADMIN_CLI_CLIENT_ID="admin-cli"
readonly SIGNIN_CALLBACK_PATH="/signin-callback"
readonly -a PLATFORM_ROLES=(ADMIN EVENT_OWNER CLIENT)
readonly WRONG_PASSWORD="smoke-test-wrong-password"
# PKCE example of RFC 7636, appendix B: the verifier and its S256 challenge.
readonly PKCE_VERIFIER="dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
readonly PKCE_CHALLENGE="E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
readonly SIGNIN_FORM_MARKER='id="kc-form-login"'
readonly REGISTRATION_LINK_MARKER="/login-actions/registration"
readonly REGISTRATION_FORM_MARKER='id="kc-register-form"'
readonly CLIENT_NOT_FOUND_MESSAGE="Client not found."
readonly REALM_DISPLAY_NAME="GoPass"
readonly REALM_NAME="ticketera"

# Prints the value of the environment variable named argv[1] of the identity service, read from
# "docker compose config --format json" on standard input; exits with the reason when it is not set.
readonly IDENTITY_ENVIRONMENT_PROGRAM='
import json, sys

service = json.load(sys.stdin).get("services", {}).get("identity") or {}
environment = service.get("environment") or {}
value = environment.get(sys.argv[1]) if isinstance(environment, dict) else None
if not value:
    sys.exit(f"{sys.argv[1]} is not set for the identity service in docker compose config")
print(value)
'

# Reads a token on standard input, either a JWT or a JSON object of claims (as the admin API generates them), and
# prints three lines: its sub, its sid and its realm roles separated by spaces, each empty when absent. The JWT
# signature is not verified: the token comes straight from the identity service.
readonly TOKEN_CLAIMS_PROGRAM='
import base64, json, sys

text = sys.stdin.read().strip()
try:
    if text.startswith("{"):
        claims = json.loads(text)
    else:
        payload = text.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
except (IndexError, ValueError):
    sys.exit("it is neither a JWT nor a JSON object of claims")
if not isinstance(claims, dict):
    sys.exit("its claims are not a JSON object")
access = claims.get("realm_access")
roles = access.get("roles") if isinstance(access, dict) else None
print(claims.get("sub") or "")
print(claims.get("sid") or "")
print(" ".join(role for role in roles if isinstance(role, str)) if isinstance(roles, list) else "")
'

# Reads the JSON answer of an admin API search on standard input and prints the id of its only result; exits with
# the reason when there is not exactly one.
readonly ONLY_ID_PROGRAM='
import json, sys

try:
    items = json.load(sys.stdin)
except ValueError:
    sys.exit("it is not JSON")
if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict) or not items[0].get("id"):
    sys.exit("it is not a list of exactly one object with an id")
print(items[0]["id"])
'

# Reads the sessions of a user from the admin API on standard input and prints the address of the session whose id
# is argv[1], empty when it has none; exits with the reason when the session is not listed.
readonly SESSION_ADDRESS_PROGRAM='
import json, sys

try:
    sessions = json.load(sys.stdin)
except ValueError:
    sys.exit("it is not JSON")
for session in sessions if isinstance(sessions, list) else []:
    if isinstance(session, dict) and session.get("id") == sys.argv[1]:
        print(session.get("ipAddress") or "")
        sys.exit(0)
sys.exit(f"the session {sys.argv[1]} is not listed")
'

# Set by run_identity_checks: a reason that makes every identity check fail, the frontend's address and the
# Compose configuration.
identity_problem=""
identity_frontend_origin=""
identity_compose_config=""
# Set by load_signin_page: the sign-in page of the frontend client, or the reason it was not shown.
signin_page=""
signin_page_problem=""
LOCATION=""
# Set by the token helpers: the reason no token was issued or its claims could not be read, and the claims read.
TOKEN_PROBLEM=""
CLAIMS_PROBLEM=""
CLAIM_SUB=""
CLAIM_SID=""
CLAIM_ROLES=""
# Set by check_test_user_token: the sub of each test user's API test token, by platform role.
declare -A test_user_subs=()

# Prints the value of an environment variable of the identity service in the Compose configuration; prints the
# reason and fails when it cannot be read.
identity_environment_value() {
  if [[ -z $identity_compose_config ]]; then
    printf 'docker compose config could not be read\n'
    return 1
  fi
  run_python "$IDENTITY_ENVIRONMENT_PROGRAM" "$1" <<< "$identity_compose_config"
}

# Prints the username of the test user of a platform role: test-admin, test-event-owner or test-client.
test_username() {
  local name=${1,,}
  printf 'test-%s\n' "${name//_/-}"
}

# Fails every check named after the reason.
# Usage: fail_each <reason> <check name>...
fail_each() {
  local reason=$1 check
  shift
  for check in "$@"; do
    fail "$check" "$reason"
  done
}

# Requests tokens with the password grant and sets STATUS, BODY and ERROR as http_get does (the form data makes it
# a POST). The password reaches curl on its standard input. Extra arguments are passed to curl.
# Usage: password_grant <realm path> <client id> <username> <password> [curl arguments...]
password_grant() {
  local realm_path=$1 client_id=$2 username=$3 password=$4
  shift 4
  http_get "http://localhost:${gateway_port}${realm_path}/protocol/openid-connect/token" \
    --data-urlencode grant_type=password --data-urlencode "client_id=$client_id" \
    --data-urlencode "username=$username" --data-urlencode password@- "$@" < <(printf '%s' "$password")
}

# Requests the tokens of the test user of a platform role from the API test client, with the password grant, the
# openid scope and the password from the Compose configuration, and sets STATUS, BODY (the token response) and
# ERROR; sets TOKEN_PROBLEM and fails when no token is issued. Extra arguments are passed to curl.
# Usage: request_test_user_tokens <ADMIN|EVENT_OWNER|CLIENT> [curl arguments...]
request_test_user_tokens() {
  local role=$1 username password
  shift
  username=$(test_username "$role")
  if ! password=$(identity_environment_value "TEST_USER_${role}_PASSWORD"); then
    TOKEN_PROBLEM=$password
    return 1
  fi
  password_grant "$REALM_PATH" "$API_TESTS_CLIENT_ID" "$username" "$password" --data-urlencode scope=openid "$@"
  if [[ $STATUS != 200 ]]; then
    TOKEN_PROBLEM="the password grant of $username at $API_TESTS_CLIENT_ID was refused, $(last_response)"
    return 1
  fi
}

# Prints an access token of the test user of a platform role, issued by the API test client (see
# request_test_user_tokens). Prints the reason and fails when no token is issued.
# Usage: api_test_token <ADMIN|EVENT_OWNER|CLIENT>
api_test_token() {
  local token
  if ! request_test_user_tokens "$1"; then
    printf '%s\n' "$TOKEN_PROBLEM"
    return 1
  fi
  if ! token=$(json_string_field access_token <<< "$BODY"); then
    printf 'the token response of %s has no access token: %s\n' "$(test_username "$1")" "$token"
    return 1
  fi
  printf '%s\n' "$token"
}

# Requests the administrator's tokens from admin-cli of the master realm, with the bootstrap administrator's
# credentials from the Compose configuration, and sets STATUS, BODY and ERROR; sets TOKEN_PROBLEM and fails when
# the credentials cannot be read.
request_admin_tokens() {
  local username password
  if ! username=$(identity_environment_value KC_BOOTSTRAP_ADMIN_USERNAME); then
    TOKEN_PROBLEM=$username
    return 1
  fi
  if ! password=$(identity_environment_value KC_BOOTSTRAP_ADMIN_PASSWORD); then
    TOKEN_PROBLEM=$password
    return 1
  fi
  password_grant "$MASTER_REALM_PATH" "$ADMIN_CLI_CLIENT_ID" "$username" "$password"
}

# Prints a fresh access token of the administrator, which lasts one minute; prints the reason and fails otherwise.
admin_access_token() {
  local token
  if ! request_admin_tokens; then
    printf '%s\n' "$TOKEN_PROBLEM"
    return 1
  fi
  if [[ $STATUS != 200 ]]; then
    printf 'the administrator got no token from the master realm, %s\n' "$(last_response)"
    return 1
  fi
  if ! token=$(json_string_field access_token <<< "$BODY"); then
    printf 'the administrator token response has no access token: %s\n' "$token"
    return 1
  fi
  printf '%s\n' "$token"
}

# Sends a GET request to the admin API of the ticketera realm and sets STATUS, BODY and ERROR. The administrator's
# access token reaches curl on its standard input.
# Usage: admin_get <administrator access token> <path under the realm, with its query string>
admin_get() {
  http_get "http://localhost:${gateway_port}${ADMIN_REALM_PATH}$2" --header @- \
    < <(printf 'Authorization: Bearer %s\n' "$1")
}

# Prints the id of the only result of an admin API search; prints the reason and fails otherwise.
# Usage: admin_resource_id <administrator access token> <search path>
admin_resource_id() {
  local id
  admin_get "$1" "$2"
  if [[ $STATUS != 200 ]]; then
    printf 'the admin API search %s failed, %s\n' "$2" "$(last_response)"
    return 1
  fi
  if ! id=$(run_python "$ONLY_ID_PROGRAM" <<< "$BODY"); then
    printf 'the admin API search %s: %s\n' "$2" "$id"
    return 1
  fi
  printf '%s\n' "$id"
}

# Reads the claims of a token, a JWT or a JSON object of claims, and sets CLAIM_SUB, CLAIM_SID and CLAIM_ROLES; sets
# CLAIMS_PROBLEM and fails when they cannot be read.
read_token_claims() {
  local output
  local -a lines
  if ! output=$(run_python "$TOKEN_CLAIMS_PROGRAM" <<< "$1"); then
    CLAIMS_PROBLEM="the claims of the token could not be read: $output"
    return 1
  fi
  mapfile -t lines <<< "$output"
  CLAIM_SUB=${lines[0]:-}
  CLAIM_SID=${lines[1]:-}
  CLAIM_ROLES=${lines[2]:-}
}

# Prints why a list of realm roles does not hold exactly one platform role, the expected one; prints nothing when
# it does. Other realm roles, such as the identity service's defaults, are ignored.
# Usage: platform_roles_problem <expected role> <space-separated realm roles>
platform_roles_problem() {
  local expected=$1 roles=" $2 " role
  if [[ $roles != *" $expected "* ]]; then
    printf 'realm_access.roles (%s) does not contain %s' "${2:-empty}" "$expected"
    return
  fi
  for role in "${PLATFORM_ROLES[@]}"; do
    if [[ $role != "$expected" && $roles == *" $role "* ]]; then
      printf 'realm_access.roles (%s) also contains %s' "$2" "$role"
      return
    fi
  done
}

# Checks that the last claims read have a non-empty sub and hold exactly one platform role, the expected one; fails
# when they do not.
# Usage: expect_sub_and_only_role <check name> <expected role>
expect_sub_and_only_role() {
  local check=$1 role=$2 problem
  if [[ -z $CLAIM_SUB ]]; then
    fail "$check" "the token has no sub claim"
    return 1
  fi
  problem=$(platform_roles_problem "$role" "$CLAIM_ROLES")
  if [[ -n $problem ]]; then
    fail "$check" "$problem"
    return 1
  fi
  pass "$check"
}

# Prints the addresses of the gateway container on its networks, separated by spaces; prints the reason and fails
# when it is not running.
gateway_container_addresses() {
  local container_id
  if ! container_id=$(docker compose ps --quiet gateway 2> /dev/null) || [[ -z $container_id ]]; then
    printf 'the gateway container is not running\n'
    return 1
  fi
  docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$container_id"
}

# Sends a request of the code flow to an endpoint of the realm (auth or registrations) and sets STATUS, BODY,
# LOCATION (the address of a redirect, empty when there is none) and ERROR. The redirect is not followed. Extra
# arguments are passed to curl, such as more query parameters with --data-urlencode. The redirect address is
# written before the status line because command substitution drops trailing newlines, and with them an empty
# last line.
# Usage: authorization_request <endpoint> <client id> <redirect URI> [curl arguments...]
authorization_request() {
  local endpoint=$1 client_id=$2 redirect_uri=$3 output status_line
  shift 3
  output=$(curl --silent --noproxy '*' --max-time "$REQUEST_TIMEOUT_SECONDS" --get \
    --data-urlencode response_type=code --data-urlencode scope=openid --data-urlencode state=smoke-test \
    --data-urlencode "client_id=$client_id" --data-urlencode "redirect_uri=$redirect_uri" "$@" \
    --write-out '\n%{redirect_url}\n%{http_code} %{errormsg}' \
    "http://localhost:${gateway_port}${REALM_PATH}/protocol/openid-connect/${endpoint}")
  status_line=${output##*$'\n'}
  output=${output%$'\n'*}
  LOCATION=${output##*$'\n'}
  BODY=${output%$'\n'*}
  STATUS=${status_line%% *}
  ERROR=${status_line#* }
}

# Sends an authorization request of the frontend client with a PKCE S256 challenge and the given redirect URI.
# Usage: frontend_authorization_request <endpoint> <redirect URI>
frontend_authorization_request() {
  authorization_request "$1" "$FRONTEND_CLIENT_ID" "$2" --data-urlencode "code_challenge=$PKCE_CHALLENGE" \
    --data-urlencode code_challenge_method=S256
}

# Describes the last authorization response for a failure message.
authorization_outcome() {
  if [[ $STATUS == 000 ]]; then
    printf 'no response (%s)' "$ERROR"
  elif [[ -n $LOCATION ]]; then
    printf 'got %s redirecting to %s' "$STATUS" "$LOCATION"
  elif [[ $BODY == *"$CLIENT_NOT_FOUND_MESSAGE"* ]]; then
    printf 'got %s: %s' "$STATUS" "$CLIENT_NOT_FOUND_MESSAGE"
  elif [[ $BODY == *"$SIGNIN_FORM_MARKER"* ]]; then
    printf 'got %s with the sign-in page' "$STATUS"
  else
    printf 'got %s' "$STATUS"
  fi
}

# Checks that the last authorization response was rejected on an error page of the identity service: a 4xx status,
# no redirect, no sign-in form, and not the page of an unknown client.
expect_rejected_page() {
  local check=$1
  if [[ $STATUS == 4?? && -z $LOCATION && $BODY != *"$SIGNIN_FORM_MARKER"* &&
    $BODY != *"$CLIENT_NOT_FOUND_MESSAGE"* ]]; then
    pass "$check"
  else
    fail "$check" "expected an error page of the identity service, $(authorization_outcome)"
  fi
}

# Checks that the last authorization response redirected back to the frontend's sign-in return address with
# error=invalid_request, instead of showing the sign-in page.
expect_invalid_request_redirect() {
  local check=$1 callback="${identity_frontend_origin}${SIGNIN_CALLBACK_PATH}"
  if [[ $STATUS == 302 && $LOCATION == "${callback}?"* &&
    ($LOCATION == *"?error=invalid_request"* || $LOCATION == *"&error=invalid_request"*) ]]; then
    pass "$check"
  else
    fail "$check" "expected a redirect to ${callback} with error=invalid_request, $(authorization_outcome)"
  fi
}

# Requests the sign-in page of the frontend client with a valid request and sets signin_page, or
# signin_page_problem when the identity service does not show it.
load_signin_page() {
  frontend_authorization_request auth "${identity_frontend_origin}${SIGNIN_CALLBACK_PATH}"
  if [[ $STATUS == 200 && $BODY == *"$SIGNIN_FORM_MARKER"* ]]; then
    signin_page=$BODY
  else
    signin_page_problem="a valid authorization request of $FRONTEND_CLIENT_ID did not show the sign-in page,"
    signin_page_problem+=" $(authorization_outcome)"
  fi
}

# Req identity-provisioning: The realm has a client for the frontend - Scenario: Password grant with the frontend
# client
# Req identity-provisioning: The built-in admin client of the realm allows no password grant - Scenario: Password
# grant with admin-cli in the ticketera realm
# Usage: expect_password_grant_refused <check name> <client id>
expect_password_grant_refused() {
  local check=$1 client_id=$2 password error
  if ! password=$(identity_environment_value TEST_USER_CLIENT_PASSWORD); then
    fail "$check" "$password"
    return
  fi
  password_grant "$REALM_PATH" "$client_id" "$(test_username CLIENT)" "$password"
  if [[ $STATUS == 000 ]]; then
    fail "$check" "$(last_response)"
  elif ! error=$(json_string_field error <<< "$BODY"); then
    fail "$check" "got $STATUS with no OAuth error: $error"
  elif [[ $error != unauthorized_client ]]; then
    fail "$check" "got $STATUS with error $error, expected unauthorized_client"
  else
    pass "$check"
  fi
}

# Req identity-provisioning: The built-in admin client of the realm allows no password grant - Scenario:
# Administrator of the master realm
check_master_admin_cli() {
  local check=$1 token
  if ! request_admin_tokens; then
    fail "$check" "$TOKEN_PROBLEM"
  elif [[ $STATUS != 200 ]]; then
    fail "$check" "expected 200 from the token endpoint of the master realm, $(last_response)"
  elif ! token=$(json_string_field access_token <<< "$BODY"); then
    fail "$check" "the token response has no access token: $token"
  else
    pass "$check"
  fi
}

# Req identity-provisioning: The realm has a client for the frontend - Scenarios: Token request from the frontend's
# address; Token request from another origin
# A token request with an unknown authorization code: the frontend client answers 400 (invalid_grant), with
# Access-Control-Allow-Origin for its web origin, and 403 (Invalid origin), with no such header, for another origin.
# Usage: token_request_from <origin>
token_request_from() {
  http_headers POST "http://localhost:${gateway_port}${REALM_PATH}/protocol/openid-connect/token" \
    --header "Origin: $1" --data-urlencode grant_type=authorization_code \
    --data-urlencode "client_id=$FRONTEND_CLIENT_ID" --data-urlencode code=smoke-test-unknown-code \
    --data-urlencode "redirect_uri=${identity_frontend_origin}${SIGNIN_CALLBACK_PATH}" \
    --data-urlencode "code_verifier=$PKCE_VERIFIER"
}

check_token_endpoint_cors() {
  local check_frontend=$1 check_other=$2
  local -a values
  token_request_from "$identity_frontend_origin"
  if [[ $STATUS != 400 ]]; then
    fail "$check_frontend" "expected 400 for an unknown code of $FRONTEND_CLIENT_ID, $(last_response)"
  else
    expect_allowed_origin "$check_frontend" "$identity_frontend_origin" "token request"
  fi

  token_request_from "$OTHER_ORIGIN"
  mapfile -t values < <(response_header_values Access-Control-Allow-Origin)
  if ((${#values[@]} > 0)); then
    fail "$check_other" "the response has Access-Control-Allow-Origin: ${values[*]}"
  elif [[ $STATUS != 403 ]]; then
    fail "$check_other" "expected 403 for the origin $OTHER_ORIGIN, $(last_response)"
  else
    pass "$check_other"
  fi
}

# Req identity-provisioning: The sign-in page carries the GoPass name - Scenario: Sign-in page title
check_signin_page_name() {
  local check=$1 title_pattern='<title>([^<]*)</title>' title=""
  if [[ -n $signin_page_problem ]]; then
    fail "$check" "$signin_page_problem"
    return
  fi
  if [[ $signin_page =~ $title_pattern ]]; then
    title=${BASH_REMATCH[1]}
  fi
  if [[ $title != *"$REALM_DISPLAY_NAME"* || $title == *"$REALM_NAME"* ]]; then
    fail "$check" "the title of the sign-in page is '$title'"
  else
    pass "$check"
  fi
}

# Req identity-provisioning: Users cannot register themselves - Scenario: Sign-in page
check_signin_page_registration() {
  local check=$1
  if [[ -n $signin_page_problem ]]; then
    fail "$check" "$signin_page_problem"
  elif [[ $signin_page == *"$REGISTRATION_LINK_MARKER"* ]]; then
    fail "$check" "the sign-in page links to $REGISTRATION_LINK_MARKER"
  else
    pass "$check"
  fi
}

# Req identity-provisioning: Users cannot register themselves - Scenario: Registration address
check_registration_address() {
  local check=$1
  frontend_authorization_request registrations "${identity_frontend_origin}${SIGNIN_CALLBACK_PATH}"
  if [[ $BODY == *"$REGISTRATION_FORM_MARKER"* ]]; then
    fail "$check" "got $STATUS with a registration form"
  else
    expect_rejected_page "$check"
  fi
}

# Req identity-provisioning: The realm has a client for the frontend - Scenarios: Redirect address outside the
# frontend; Authorization request without PKCE; Authorization request with the plain PKCE method
# Req identity-provisioning: The realm has a client for API tests - Scenario: Browser sign-in with the API test
# client
check_authorization_requests() {
  local check_signin=$1 check_no_pkce=$2 check_plain=$3 check_foreign=$4 check_api_tests=$5
  local callback="${identity_frontend_origin}${SIGNIN_CALLBACK_PATH}"

  # Control: a valid request shows the sign-in page, so the client exists and the rejections below are its own.
  load_signin_page
  if [[ -n $signin_page_problem ]]; then
    fail "$check_signin" "$signin_page_problem"
  else
    pass "$check_signin"
  fi

  authorization_request auth "$FRONTEND_CLIENT_ID" "$callback"
  expect_invalid_request_redirect "$check_no_pkce"

  authorization_request auth "$FRONTEND_CLIENT_ID" "$callback" --data-urlencode "code_challenge=$PKCE_CHALLENGE" \
    --data-urlencode code_challenge_method=plain
  expect_invalid_request_redirect "$check_plain"

  frontend_authorization_request auth "${OTHER_ORIGIN}${SIGNIN_CALLBACK_PATH}"
  expect_rejected_page "$check_foreign"

  authorization_request auth "$API_TESTS_CLIENT_ID" "$callback" --data-urlencode "code_challenge=$PKCE_CHALLENGE" \
    --data-urlencode code_challenge_method=S256
  expect_rejected_page "$check_api_tests"
}

# Req identity-provisioning: The realm has one test user per platform role - Scenarios: ADMIN test user;
# EVENT_OWNER test user; CLIENT test user; First sign-in needs no extra step
# Req identity-provisioning: The realm definition contains no secrets - Scenario: Imported test user password
# Req identity-provisioning: The realm has a client for API tests - Scenario: Token for an API test
# Req access-token: The access token identifies the user - Scenario: Token of a signed-in user
# Req access-token: The access token carries the user's platform roles - Scenarios: Token of the ADMIN test user;
# Token of the EVENT_OWNER test user; Token of the CLIENT test user
# A test user with a required action or an incomplete profile gets no token from the password grant, so a token
# also proves that the first sign-in needs no extra step. Sets test_user_subs[<role>] when the check passes.
# Usage: check_test_user_token <check name> <ADMIN|EVENT_OWNER|CLIENT>
check_test_user_token() {
  local check=$1 role=$2 token
  if ! token=$(api_test_token "$role"); then
    fail "$check" "$token"
  elif ! read_token_claims "$token"; then
    fail "$check" "$CLAIMS_PROBLEM"
  elif expect_sub_and_only_role "$check" "$role"; then
    test_user_subs[$role]=$CLAIM_SUB
  fi
}

# Req identity-provisioning: The realm has a client for API tests - Scenario: Wrong password
# Control: the same user got a token with its own password, so invalid_grant is about the password, not a missing
# user.
check_wrong_password() {
  local check=$1 error
  if [[ -z ${test_user_subs[CLIENT]:-} ]]; then
    fail "$check" "control failed: $(test_username CLIENT) got no token with its own password"
    return
  fi
  password_grant "$REALM_PATH" "$API_TESTS_CLIENT_ID" "$(test_username CLIENT)" "$WRONG_PASSWORD" \
    --data-urlencode scope=openid
  if [[ $STATUS == 200 ]]; then
    fail "$check" "a token was issued for the wrong password"
  elif ! error=$(json_string_field error <<< "$BODY"); then
    fail "$check" "$(last_response) with no OAuth error: $error"
  elif [[ $error != invalid_grant ]]; then
    fail "$check" "got $STATUS with error $error, expected invalid_grant"
  else
    pass "$check"
  fi
}

# Req access-token: The access token identifies the user - Scenario: Different users
check_different_subs() {
  local check=$1 client_sub=${test_user_subs[CLIENT]:-} owner_sub=${test_user_subs[EVENT_OWNER]:-}
  if [[ -z $client_sub || -z $owner_sub ]]; then
    fail "$check" "the sub of $(test_username CLIENT) or $(test_username EVENT_OWNER) was not read (see its check)"
  elif [[ $client_sub == "$owner_sub" ]]; then
    fail "$check" "both have the sub $client_sub"
  else
    pass "$check"
  fi
}

# Req access-token: The access token identifies the user - Scenario: Same user signs in twice
# Signs in, signs out with a form POST of the refresh token to the logout endpoint, and signs in again.
check_sub_after_sign_out() {
  local check=$1 token refresh_token first_sub
  if ! request_test_user_tokens CLIENT; then
    fail "$check" "$TOKEN_PROBLEM"
    return
  fi
  if ! token=$(json_string_field access_token <<< "$BODY") ||
    ! refresh_token=$(json_string_field refresh_token <<< "$BODY"); then
    fail "$check" "the token response has no access token or no refresh token"
    return
  fi
  if ! read_token_claims "$token"; then
    fail "$check" "$CLAIMS_PROBLEM"
    return
  fi
  first_sub=$CLAIM_SUB
  http_get "http://localhost:${gateway_port}${REALM_PATH}/protocol/openid-connect/logout" \
    --data-urlencode "client_id=$API_TESTS_CLIENT_ID" --data-urlencode refresh_token@- \
    < <(printf '%s' "$refresh_token")
  if [[ $STATUS != 204 ]]; then
    fail "$check" "expected 204 from the logout endpoint, $(last_response)"
  elif ! token=$(api_test_token CLIENT); then
    fail "$check" "signing in again failed: $token"
  elif ! read_token_claims "$token"; then
    fail "$check" "$CLAIMS_PROBLEM"
  elif [[ -z $first_sub || $CLAIM_SUB != "$first_sub" ]]; then
    fail "$check" "the sub was '$first_sub' before signing out and '$CLAIM_SUB' after signing in again"
  else
    pass "$check"
  fi
}

# Reads the claims of an example token that the admin API generates for the frontend client and a user, as the
# scope evaluation does, into CLAIM_SUB, CLAIM_SID and CLAIM_ROLES; sets CLAIMS_PROBLEM and fails otherwise.
# Usage: read_example_token_claims <administrator access token> <client id> <access|id> <user id>
read_example_token_claims() {
  admin_get "$1" "/clients/$2/evaluate-scopes/generate-example-$3-token?scope=openid&userId=$4"
  if [[ $STATUS != 200 ]]; then
    CLAIMS_PROBLEM="the admin API generated no example $3 token, $(last_response)"
    return 1
  fi
  read_token_claims "$BODY"
}

# Req access-token: The access token identifies the user - Scenario: Same user in two sessions at the same time
# Req identity-provisioning: Tokens of the frontend client carry the user's identity and roles - Scenarios: Access
# token of the frontend client; ID token of the frontend client
# The admin API's scope evaluation generates the tokens the frontend client would get, with no browser.
check_example_tokens() {
  local check_same_sub=$1 check_access=$2 check_id=$3 admin_token frontend_id client_id owner_id problem=""
  local api_test_sub=${test_user_subs[CLIENT]:-}
  if ! admin_token=$(admin_access_token); then
    problem=$admin_token
  elif ! frontend_id=$(admin_resource_id "$admin_token" "/clients?clientId=$FRONTEND_CLIENT_ID"); then
    problem=$frontend_id
  elif ! client_id=$(admin_resource_id "$admin_token" "/users?username=$(test_username CLIENT)&exact=true"); then
    problem=$client_id
  elif ! owner_id=$(admin_resource_id "$admin_token" "/users?username=$(test_username EVENT_OWNER)&exact=true"); then
    problem=$owner_id
  fi
  if [[ -n $problem ]]; then
    fail_each "$problem" "$check_same_sub" "$check_access" "$check_id"
    return
  fi

  if [[ -z $api_test_sub ]]; then
    fail "$check_same_sub" "the sub of the API test token of $(test_username CLIENT) was not read (see its check)"
  elif ! read_example_token_claims "$admin_token" "$frontend_id" access "$client_id"; then
    fail "$check_same_sub" "$CLAIMS_PROBLEM"
  elif [[ $CLAIM_SUB != "$api_test_sub" ]]; then
    fail "$check_same_sub" "the example access token has the sub '$CLAIM_SUB', the API test token '$api_test_sub'"
  else
    pass "$check_same_sub"
  fi

  if ! read_example_token_claims "$admin_token" "$frontend_id" access "$owner_id"; then
    fail "$check_access" "$CLAIMS_PROBLEM"
  else
    expect_sub_and_only_role "$check_access" EVENT_OWNER
  fi

  if ! read_example_token_claims "$admin_token" "$frontend_id" id "$owner_id"; then
    fail "$check_id" "$CLAIMS_PROBLEM"
  else
    expect_sub_and_only_role "$check_id" EVENT_OWNER
  fi
}

# Prints the address the identity service recorded for a session of a user; prints the reason and fails otherwise.
# Usage: session_address <administrator access token> <user id> <session id>
session_address() {
  admin_get "$1" "/users/$2/sessions"
  if [[ $STATUS != 200 ]]; then
    printf 'the admin API listed no sessions, %s\n' "$(last_response)"
    return 1
  fi
  run_python "$SESSION_ADDRESS_PROGRAM" "$3" <<< "$BODY"
}

# Prints why a recorded session address is not the client's address, or nothing when it is: it must be one IP
# address, not the forged value and not an address of the gateway container.
# Usage: session_address_problem <recorded address> <gateway addresses separated by spaces>
session_address_problem() {
  local address=$1 gateway_addresses=" $2 "
  if [[ ! $address =~ ^[0-9A-Fa-f.:]+$ ]]; then
    printf "the recorded address '%s' is not one IP address" "$address"
  elif [[ $address == "$FORGED_FOR" ]]; then
    printf 'the recorded address is the forged value %s' "$FORGED_FOR"
  elif [[ $gateway_addresses == *" $address "* ]]; then
    printf "the recorded address %s is the gateway's own address" "$address"
  fi
}

# Req identity-provisioning: The identity service sees the client's address - Scenarios: Sign-in recorded with the
# client's address; Forged forwarding header
# Two sign-ins of the CLIENT test user, the second with a forged X-Forwarded-For; the admin API lists the address
# recorded for each session, whose id is the session_state of the token response. With Docker port publishing the
# gateway sees a Docker bridge address, not 127.0.0.1, so the checks assert one address that is neither the forged
# value nor an address of the gateway container, and the same address for both sign-ins.
check_session_addresses() {
  local check_real=$1 check_forged=$2 real_session forged_session admin_token user_id gateway_addresses
  local real_address forged_address problem=""
  if ! request_test_user_tokens CLIENT; then
    problem=$TOKEN_PROBLEM
  elif ! real_session=$(json_string_field session_state <<< "$BODY"); then
    problem="the token response has no session_state: $real_session"
  elif ! request_test_user_tokens CLIENT --header "X-Forwarded-For: $FORGED_FOR"; then
    problem=$TOKEN_PROBLEM
  elif ! forged_session=$(json_string_field session_state <<< "$BODY"); then
    problem="the token response has no session_state: $forged_session"
  elif ! admin_token=$(admin_access_token); then
    problem=$admin_token
  elif ! user_id=$(admin_resource_id "$admin_token" "/users?username=$(test_username CLIENT)&exact=true"); then
    problem=$user_id
  elif ! real_address=$(session_address "$admin_token" "$user_id" "$real_session"); then
    problem=$real_address
  elif ! forged_address=$(session_address "$admin_token" "$user_id" "$forged_session"); then
    problem=$forged_address
  elif ! gateway_addresses=$(gateway_container_addresses); then
    problem=$gateway_addresses
  fi
  if [[ -n $problem ]]; then
    fail_each "$problem" "$check_real" "$check_forged"
    return
  fi

  problem=$(session_address_problem "$real_address" "$gateway_addresses")
  if [[ -n $problem ]]; then
    fail "$check_real" "$problem"
  else
    pass "$check_real"
  fi

  problem=$(session_address_problem "$forged_address" "$gateway_addresses")
  if [[ -n $problem ]]; then
    fail "$check_forged" "$problem"
  elif [[ $forged_address != "$real_address" ]]; then
    fail "$check_forged" "the sign-in with the forged header was recorded with $forged_address, not $real_address"
  else
    pass "$check_forged"
  fi
}

# Req identity-provisioning: The realm has one test user per platform role - Scenario: Test user password missing
# Each test user password in turn is set empty in the environment, which takes precedence over .env; Compose must
# stop before creating any container and name it.
check_missing_test_password() {
  local check=$1 role name output
  for role in "${PLATFORM_ROLES[@]}"; do
    name="TEST_USER_${role}_PASSWORD"
    if output=$(env "$name=" docker compose config --quiet 2>&1); then
      fail "$check" "docker compose config succeeded with $name empty"
      return
    fi
    if [[ $output != *"$name"* ]]; then
      fail "$check" "docker compose config failed with $name empty, but its error does not name it: $output"
      return
    fi
  done
  pass "$check"
}

# The checks of the realm's clients and settings (task 1.4).
check_identity_clients() {
  local check_frontend_grant="identity: $FRONTEND_CLIENT_ID refuses the password grant"
  local check_admin_cli_grant="identity: $ADMIN_CLI_CLIENT_ID of $REALM_NAME refuses the password grant"
  local check_master="identity: $ADMIN_CLI_CLIENT_ID of master still issues the administrator's token"
  local check_signin="identity: $FRONTEND_CLIENT_ID shows the sign-in page for a valid authorization request"
  local check_no_pkce="identity: $FRONTEND_CLIENT_ID rejects an authorization request without code_challenge"
  local check_plain="identity: $FRONTEND_CLIENT_ID rejects the plain PKCE method"
  local check_foreign="identity: $FRONTEND_CLIENT_ID rejects a redirect URI outside FRONTEND_ORIGIN"
  local check_api_tests="identity: $API_TESTS_CLIENT_ID rejects a browser authorization request"
  local check_cors_frontend="identity: token endpoint allows FRONTEND_ORIGIN for $FRONTEND_CLIENT_ID"
  local check_cors_other="identity: token endpoint gives no permission to another origin"
  local check_name="identity: sign-in page shows $REALM_DISPLAY_NAME, not $REALM_NAME"
  local check_signin_registration="identity: sign-in page offers no way to register"
  local check_registration="identity: registration address shows no registration form"
  local check

  if [[ -n $identity_problem ]]; then
    for check in "$check_frontend_grant" "$check_admin_cli_grant" "$check_master" "$check_signin" \
      "$check_no_pkce" "$check_plain" "$check_foreign" "$check_api_tests" "$check_cors_frontend" \
      "$check_cors_other" "$check_name" "$check_signin_registration" "$check_registration"; do
      fail "$check" "$identity_problem"
    done
    return
  fi

  expect_password_grant_refused "$check_frontend_grant" "$FRONTEND_CLIENT_ID"
  expect_password_grant_refused "$check_admin_cli_grant" "$ADMIN_CLI_CLIENT_ID"
  check_master_admin_cli "$check_master"
  check_authorization_requests "$check_signin" "$check_no_pkce" "$check_plain" "$check_foreign" "$check_api_tests"
  check_token_endpoint_cors "$check_cors_frontend" "$check_cors_other"
  check_signin_page_name "$check_name"
  check_signin_page_registration "$check_signin_registration"
  check_registration_address "$check_registration"
}

# The checks of the test users and their tokens (task 1.5).
check_identity_tokens() {
  local client_user owner_user role index
  local -a role_checks=()
  client_user=$(test_username CLIENT)
  owner_user=$(test_username EVENT_OWNER)
  local check_wrong="identity: a wrong password of $client_user gets invalid_grant"
  local check_different="identity: $client_user and $owner_user have different sub values"
  local check_sign_out="identity: $client_user keeps its sub after signing out and in again"
  local check_same_sub="identity: example access token of $FRONTEND_CLIENT_ID for $client_user has its API test sub"
  local check_access="identity: example access token of $FRONTEND_CLIENT_ID for $owner_user holds only EVENT_OWNER"
  local check_id="identity: example ID token of $FRONTEND_CLIENT_ID for $owner_user holds only EVENT_OWNER"
  local check_address="identity: a sign-in is recorded with the client's address, not the gateway's"
  local check_forged="identity: a forged X-Forwarded-For is not recorded as the client's address"
  local check_missing="identity: docker compose config fails and names an empty test user password"
  for role in "${PLATFORM_ROLES[@]}"; do
    role_checks+=("identity: $(test_username "$role") gets a token with its password and holds only $role")
  done

  if [[ -n $identity_problem ]]; then
    fail_each "$identity_problem" "${role_checks[@]}" "$check_wrong" "$check_different" "$check_sign_out" \
      "$check_same_sub" "$check_access" "$check_id" "$check_address" "$check_forged" "$check_missing"
    return
  fi

  for index in "${!PLATFORM_ROLES[@]}"; do
    check_test_user_token "${role_checks[index]}" "${PLATFORM_ROLES[index]}"
  done
  check_wrong_password "$check_wrong"
  check_different_subs "$check_different"
  check_sub_after_sign_out "$check_sign_out"
  check_example_tokens "$check_same_sub" "$check_access" "$check_id"
  check_session_addresses "$check_address" "$check_forged"
  check_missing_test_password "$check_missing"
}

# Runs every identity check; called by main of smoke-test.sh after the other checks.
run_identity_checks() {
  if [[ -n $gateway_port_problem ]]; then
    identity_problem=$gateway_port_problem
  elif ! identity_frontend_origin=$(config_value FRONTEND_ORIGIN); then
    identity_problem="FRONTEND_ORIGIN is not set in the environment or in .env"
  fi
  identity_compose_config=$(docker compose config --format json 2> /dev/null) || identity_compose_config=""
  check_identity_clients
  check_identity_tokens
}
