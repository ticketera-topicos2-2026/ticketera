# shellcheck shell=bash
# Identity checks of the smoke test: the clients and settings of the ticketera realm, verified through the gateway
# (IA-17). Sourced by tests/smoke/smoke-test.sh, whose helpers it uses (pass, fail, http_get, http_headers,
# last_response, expect_allowed_origin, response_header_values, run_python, json_string_field, config_value) and
# whose main calls run_identity_checks; it is not run on its own.
#
# Test user passwords and the bootstrap administrator's credentials are read from the environment of the identity
# service in "docker compose config", so the checks use the values the running system was started with. Passwords
# reach curl on its standard input, never on its command line.
#
# A rejection check must not pass because a client or the realm is missing. The identity service answers an
# unknown client with "Client not found." on its error page, with invalid_client (401) at its token endpoint, and
# with an Access-Control-Allow-Origin header that echoes any origin, so each check asserts the answer of an
# existing client. The markers below come from the pages of Keycloak 26.8 and its login theme.
#
# Change e1-identity-access, task 1.4 (design: Test Strategy, platform/identity-provisioning).

readonly REALM_PATH="/auth/realms/ticketera"
readonly MASTER_REALM_PATH="/auth/realms/master"
readonly FRONTEND_CLIENT_ID="ticketera-frontend"
readonly API_TESTS_CLIENT_ID="ticketera-api-tests"
readonly ADMIN_CLI_CLIENT_ID="admin-cli"
readonly SIGNIN_CALLBACK_PATH="/signin-callback"
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

# Set by run_identity_checks: a reason that makes every identity check fail, the frontend's address and the
# Compose configuration.
identity_problem=""
identity_frontend_origin=""
identity_compose_config=""
# Set by load_signin_page: the sign-in page of the frontend client, or the reason it was not shown.
signin_page=""
signin_page_problem=""
LOCATION=""

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

# Prints an access token of the test user of a platform role, issued by the API test client with the password
# grant and the openid scope, with the password from the Compose configuration. Prints the reason and fails when no
# token is issued.
# Usage: api_test_token <ADMIN|EVENT_OWNER|CLIENT>
api_test_token() {
  local role=$1 username password token
  username=$(test_username "$role")
  if ! password=$(identity_environment_value "TEST_USER_${role}_PASSWORD"); then
    printf '%s\n' "$password"
    return 1
  fi
  password_grant "$REALM_PATH" "$API_TESTS_CLIENT_ID" "$username" "$password" --data-urlencode scope=openid
  if [[ $STATUS != 200 ]]; then
    printf 'the password grant of %s at %s was refused, %s\n' "$username" "$API_TESTS_CLIENT_ID" "$(last_response)"
    return 1
  fi
  if ! token=$(json_string_field access_token <<< "$BODY"); then
    printf 'the token response of %s has no access token: %s\n' "$username" "$token"
    return 1
  fi
  printf '%s\n' "$token"
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
  local check=$1 username password token
  if ! username=$(identity_environment_value KC_BOOTSTRAP_ADMIN_USERNAME); then
    fail "$check" "$username"
    return
  fi
  if ! password=$(identity_environment_value KC_BOOTSTRAP_ADMIN_PASSWORD); then
    fail "$check" "$password"
    return
  fi
  password_grant "$MASTER_REALM_PATH" "$ADMIN_CLI_CLIENT_ID" "$username" "$password"
  if [[ $STATUS != 200 ]]; then
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

# Runs every identity check; called by main of smoke-test.sh after the other checks.
run_identity_checks() {
  if [[ -n $gateway_port_problem ]]; then
    identity_problem=$gateway_port_problem
  elif ! identity_frontend_origin=$(config_value FRONTEND_ORIGIN); then
    identity_problem="FRONTEND_ORIGIN is not set in the environment or in .env"
  fi
  identity_compose_config=$(docker compose config --format json 2> /dev/null) || identity_compose_config=""
  check_identity_clients
}
