#!/usr/bin/env bash
# Smoke test of the running system, verified from the host through the gateway.
#
# Usage: tests/smoke/smoke-test.sh [--require-echo]
#
# Run it after "docker compose up --wait", from any directory. GATEWAY_PORT is read from the environment or, when
# it is not set there, from .env at the repository root. The services to verify are derived from
# "docker compose config", which reads the compose files as every "docker compose" command does: set COMPOSE_FILE
# when the system was started with more than one file.
#
# The forwarding checks need the echo service of tests/smoke/compose.echo.yml. Without it they are skipped, unless
# --require-echo is given (CI and task 2.14), which makes them fail instead. The echo route is protected by the
# access check of the gateway, so they send the access token of the CLIENT test user (e1-identity-access).
#
# Output: one line per check, "PASS <check>", "FAIL <check>: <reason>" or "SKIP <check>: <reason>", then a summary
# line. Exit status: 0 when no check fails, 1 when any check fails, 2 for an unknown argument or when curl is
# missing or older than 8.1 (no check runs).
#
# The host needs only bash, curl (8.1 or later, for %{errormsg} in --write-out) and docker (D-12). JSON is parsed
# inside a Python container pinned by digest (DS-25); only its standard output is read as data (see run_python).
#
# Change project-bootstrap, task group 2 (design: platform/continuous-integration, platform/api-gateway), and the
# CORS checks of task 3.6. The identity checks of change e1-identity-access are in tests/smoke/identity-checks.sh,
# sourced below (IA-17).

set -uo pipefail

readonly PYTHON_IMAGE="python:3.13-alpine@sha256:1e1f6334529d1fb26a2ef619d7cffb30a7c7d7cc1cc7338ebee283a58d1aeaca"
readonly REQUEST_TIMEOUT_SECONDS=10
readonly REQUIRED_CURL_MAJOR=8
readonly REQUIRED_CURL_MINOR=1
readonly HEALTH_PATH_LABEL="ticketera.health-path"
# Services allowed to publish ports (Req local-environment: Only the gateway and the frontend publish ports).
readonly PUBLISHING_SERVICES=" gateway frontend "
# Test-only echo service and gateway route (tests/smoke/compose.echo.yml), and the forged values the forwarding
# checks send; 203.0.113.7 is a documentation address (RFC 5737).
readonly ECHO_SERVICE="echo"
readonly ECHO_PATH="/smoke-test/echo/"
readonly FORGED_FOR="203.0.113.7"
readonly FORGED_HOST="forged.example"
# CORS checks (task 3.6): the service and path of the spec scenarios, and an origin that is not the frontend's.
readonly CORS_SERVICE="catalog"
readonly CORS_PATH="/api/catalog/health"
readonly OTHER_ORIGIN="http://other.example"
# How long the CORS checks wait for a request to show up in the access log of the service.
readonly LOG_WAIT_SECONDS=5
readonly FORGED_PROTO="https"

# Reads "docker compose config --format json" on standard input and prints one tab-separated line per service:
# name, kind ("backend" when built from ./services/<name>, "other" otherwise), the health path label and the first
# published port, with "-" for an empty field (DS-19). Argument: the repository root.
readonly COMPOSE_SERVICES_PROGRAM='
import json, os, sys

root = sys.argv[1]
for name, service in sorted(json.load(sys.stdin).get("services", {}).items()):
    build = service.get("build") or {}
    context = build.get("context", "") if isinstance(build, dict) else str(build)
    parts = os.path.relpath(context, root).split(os.sep) if context else []
    kind = "backend" if len(parts) == 2 and parts[0] == "services" else "other"
    health_path = (service.get("labels") or {}).get(sys.argv[2]) or "-"
    published = [str(port["published"]) for port in service.get("ports", []) if port.get("published")]
    print(name, kind, health_path, published[0] if published else "-", sep="\t")
'

# docker inspect format: "<container id>|<service>|<main process PID>|<published ports>", where published ports are
# space-separated "<container port>=<host IP>:<host port>" items.
# shellcheck disable=SC2016 # Go template for docker inspect, not shell expansion
readonly CONTAINER_FORMAT='{{.Id}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.State.Pid}}|{{range $port, $bindings := .NetworkSettings.Ports}}{{range $bindings}}{{$port}}={{.HostIp}}:{{.HostPort}} {{end}}{{end}}'

cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

passed=0
failed=0
skipped=0
require_echo=false
gateway_port=""
gateway_port_problem=""
compose_service_lines=""
compose_problem=""
# Directory for the standard error of docker run (see run_python); created by main and removed on exit.
temp_dir=""
STATUS=""
BODY=""
ERROR=""

pass() {
  printf 'PASS %s\n' "$1"
  passed=$((passed + 1))
}

fail() {
  printf 'FAIL %s: %s\n' "$1" "${2//$'\n'/ }"
  failed=$((failed + 1))
}

skip() {
  printf 'SKIP %s: %s\n' "$1" "${2//$'\n'/ }"
  skipped=$((skipped + 1))
}

# Reads the command-line options; exits with status 2 on an unknown argument.
parse_arguments() {
  local argument
  for argument in "$@"; do
    case $argument in
      --require-echo)
        require_echo=true
        ;;
      *)
        printf 'smoke-test: unknown argument %s\nUsage: tests/smoke/smoke-test.sh [--require-echo]\n' \
          "$argument" >&2
        exit 2
        ;;
    esac
  done
}

# Exits with status 2, before any check runs, when curl is missing or older than the required version.
require_curl() {
  local required="${REQUIRED_CURL_MAJOR}.${REQUIRED_CURL_MINOR}" version_line
  if ! version_line=$(curl --version 2> /dev/null); then
    printf 'smoke-test: curl %s or later is required, but curl was not found\n' "$required" >&2
    exit 2
  fi
  version_line=${version_line%%$'\n'*}
  if [[ ! $version_line =~ ^curl\ ([0-9]+)\.([0-9]+) ]]; then
    printf "smoke-test: curl %s or later is required, but its version could not be read from '%s'\n" \
      "$required" "$version_line" >&2
    exit 2
  fi
  if ((BASH_REMATCH[1] < REQUIRED_CURL_MAJOR ||
    (BASH_REMATCH[1] == REQUIRED_CURL_MAJOR && BASH_REMATCH[2] < REQUIRED_CURL_MINOR))); then
    printf 'smoke-test: curl %s or later is required, found curl %s.%s\n' \
      "$required" "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" >&2
    exit 2
  fi
}

# Prints the value of the variable named $1 from the environment or, when it is unset or empty there, from .env.
# .env is a copy of .env.example, so only plain NAME=value lines are read (comment lines never match) and a trailing
# carriage return is removed; the last assignment wins. Fails when there is no value.
config_value() {
  local name=$1 line value=""
  if [[ -n ${!name:-} ]]; then
    printf '%s\n' "${!name}"
    return 0
  fi
  [[ -r .env ]] || return 1
  while IFS= read -r line || [[ -n $line ]]; do
    line=${line%$'\r'}
    if [[ $line == "${name}="* ]]; then
      value=${line#"${name}="}
    fi
  done < .env
  [[ -n $value ]] || return 1
  printf '%s\n' "$value"
}

# Sends a GET request to a URL and sets STATUS (000 when no HTTP response arrived), BODY and ERROR (curl's error
# message, empty when a response arrived). Extra arguments are passed to curl.
http_get() {
  local url=$1 output last_line
  shift
  output=$(curl --silent --noproxy '*' --max-time "$REQUEST_TIMEOUT_SECONDS" \
    --write-out '\n%{http_code} %{errormsg}' "$@" "$url")
  last_line=${output##*$'\n'}
  BODY=${output%$'\n'*}
  STATUS=${last_line%% *}
  ERROR=${last_line#* }
}

# Describes the last response for a failure message.
last_response() {
  if [[ $STATUS == 000 ]]; then
    printf 'no response (%s)' "$ERROR"
  else
    printf 'got %s' "$STATUS"
  fi
}

# Prints the error message of a failed "docker compose" command run with the given arguments.
compose_error() {
  { docker compose "$@" > /dev/null; } 2>&1
}

# Creates the temporary directory and removes it when the script exits. Bash runs the EXIT trap also when a check
# fails, on "exit", and when the script is ended by SIGINT or SIGTERM. Run it in the main shell, never in a
# command substitution, whose traps and variables are lost when it ends. When the directory cannot be created,
# temp_dir stays empty and run_python reports it as the reason of each check that needs it.
create_temp_dir() {
  trap remove_temp_dir EXIT
  temp_dir=$(mktemp -d) || temp_dir=""
}

remove_temp_dir() {
  if [[ -n $temp_dir ]]; then
    rm -rf "$temp_dir"
  fi
}

# Runs a Python program inside the container pinned by PYTHON_IMAGE, with no network and with standard input passed
# on. Only the container's standard output is data: on success it is printed, and anything on its standard error is
# copied to the script's standard error. On failure the container's standard error is printed instead, as the
# reason, and the function fails. --quiet keeps a pull of the image silent. The standard error goes to a file in
# temp_dir, the only way to capture it apart from standard output.
# Usage: run_python <program> [arguments...]
run_python() {
  local program=$1 errors_file="${temp_dir}/docker-run-stderr" output errors status
  shift
  if [[ -z $temp_dir ]]; then
    printf 'mktemp could not create a directory for the standard error of docker run\n'
    return 1
  fi
  output=$(docker run --rm -i --quiet --network none "$PYTHON_IMAGE" python -I -c "$program" "$@" \
    2> "$errors_file")
  status=$?
  errors=$(< "$errors_file")
  if ((status != 0)); then
    printf '%s\n' "${errors:-docker run exited with status $status and printed no error}"
    return 1
  fi
  if [[ -n $errors ]]; then
    printf '%s\n' "$errors" >&2
  fi
  printf '%s\n' "$output"
}

# Prints the string field named $1 of the JSON document read from standard input; when the input is not a JSON
# object with that string field, or the container fails, prints the reason and fails.
json_string_field() {
  run_python '
import json, sys
try:
    document = json.load(sys.stdin)
except ValueError:
    sys.exit("it is not JSON")
if not isinstance(document, dict) or not isinstance(document.get(sys.argv[1]), str):
    sys.exit(f"it is not a JSON object with a string field {sys.argv[1]}")
print(document[sys.argv[1]])
' "$1"
}

# Checks that a GET request to a URL answers the expected status code.
# Usage: expect_url_status <check name> <expected status> <url> [curl arguments...]
expect_url_status() {
  local check=$1 expected=$2 url=$3
  shift 3
  http_get "$url" "$@"
  if [[ $STATUS == "$expected" ]]; then
    pass "$check"
  else
    fail "$check" "expected $expected from $url, $(last_response)"
  fi
}

# Checks that a GET request to a gateway path answers the expected status code.
# Usage: expect_status <check name> <expected status> <path> [curl arguments...]
expect_status() {
  local check=$1 expected=$2 path=$3
  shift 3
  if [[ -n $gateway_port_problem ]]; then
    fail "$check" "$gateway_port_problem"
    return
  fi
  expect_url_status "$check" "$expected" "http://localhost:${gateway_port}${path}" "$@"
}

# Req api-gateway: The identity service is served under /auth - Scenario: Discovery document of the ticketera realm
# Req continuous-integration: The smoke-test check verifies the running system through the gateway - Scenario: The
# realm is missing
# Req api-gateway: Public paths skip the access check - Scenario: Identity service path without a token (the request
# carries no token; e1-identity-access, task 1.9)
check_realm_discovery() {
  local check="identity: realm discovery document" path="/auth/realms/ticketera/.well-known/openid-configuration"
  local expected_issuer="http://localhost:${gateway_port}/auth/realms/ticketera" issuer
  if [[ -n $gateway_port_problem ]]; then
    fail "$check" "$gateway_port_problem"
    return
  fi
  http_get "http://localhost:${gateway_port}${path}"
  if [[ $STATUS != 200 ]]; then
    fail "$check" "expected 200 for $path, $(last_response)"
    return
  fi
  if ! issuer=$(json_string_field issuer <<< "$BODY"); then
    fail "$check" "the issuer could not be read from the response to $path: $issuer"
    return
  fi
  if [[ $issuer == "$expected_issuer" ]]; then
    pass "$check"
  else
    fail "$check" "issuer is '$issuer', expected '$expected_issuer'"
  fi
}

# Prints the services of the Compose configuration, one line each (see COMPOSE_SERVICES_PROGRAM), or the reason
# when the configuration cannot be read.
compose_services() {
  local config services
  if ! config=$(docker compose config --format json 2> /dev/null); then
    printf 'docker compose config failed: %s\n' "$(compose_error config --format json)"
    return 1
  fi
  if ! services=$(run_python "$COMPOSE_SERVICES_PROGRAM" "$PWD" "$HEALTH_PATH_LABEL" <<< "$config"); then
    printf 'the services could not be read from docker compose config: %s\n' "$services"
    return 1
  fi
  printf '%s\n' "$services"
}

# Req continuous-integration: The smoke test covers every backend service the system starts - Scenario: Service
# added without smoke-test coverage
# Req continuous-integration: The smoke-test check verifies the running system through the gateway - Scenarios:
# Every endpoint answers; A backend service is unhealthy
check_labeled_services() {
  local service kind health_path published_port backend_count=0
  if [[ -n $compose_problem ]]; then
    fail "compose: services derived from docker compose config" "$compose_problem"
    return
  fi
  while IFS=$'\t' read -r service kind health_path published_port; do
    if [[ $kind == backend ]]; then
      backend_count=$((backend_count + 1))
    fi
    if [[ -z $service || ($kind != backend && $health_path == -) ]]; then
      continue
    elif [[ $kind == backend && $health_path == - ]]; then
      fail "service $service: health check" "it is built from ./services/ but has no $HEALTH_PATH_LABEL label"
    elif [[ $kind == backend ]]; then
      expect_status "service $service: GET /api/${service}${health_path} answers 200" 200 \
        "/api/${service}${health_path}"
    elif [[ $published_port == - ]]; then
      fail "service $service: health check" "it has the $HEALTH_PATH_LABEL label but publishes no port"
    else
      expect_url_status "service $service: GET ${health_path} on its port ${published_port} answers 200" 200 \
        "http://localhost:${published_port}${health_path}"
    fi
  done <<< "$compose_service_lines"
  if ((backend_count == 0)); then
    pass "backend coverage: no backend services found"
  fi
}

# Prints the running containers of the Compose project, one line each in CONTAINER_FORMAT, or the reason when
# there are none.
running_containers() {
  local output
  local -a ids
  if ! output=$(docker compose ps --quiet 2> /dev/null); then
    printf 'docker compose ps failed: %s\n' "$(compose_error ps --quiet)"
    return 1
  fi
  if [[ -z $output ]]; then
    printf 'no container of the project is running\n'
    return 1
  fi
  mapfile -t ids <<< "$output"
  docker inspect --format "$CONTAINER_FORMAT" "${ids[@]}" 2>&1
}

# Req local-environment: Containers run as a non-root user - Scenario: Process user of a project container
# The user of the main process (PID 1 inside the container) is checked, not that of "docker compose exec", because
# some entrypoints, such as PostgreSQL's, start as root and then switch user (DS-13).
check_non_root() {
  local container_id=$1 service=$2 pid=$3
  local check="container $service: main process runs as non-root" processes process_pid process_uid uid=""
  if ! processes=$(docker top "$container_id" -o pid,uid 2>&1); then
    fail "$check" "docker top failed: $processes"
    return
  fi
  while read -r process_pid process_uid; do
    if [[ $process_pid == "$pid" ]]; then
      uid=$process_uid
    fi
  done <<< "$processes"
  if [[ -z $uid ]]; then
    fail "$check" "its main process (PID $pid) is not listed by docker top"
  elif [[ $uid == 0 ]]; then
    fail "$check" "its main process runs as UID 0 (root)"
  else
    pass "$check"
  fi
}

check_running_containers() {
  local containers container_id service pid ports binding host_address check
  local -a bindings publishing_services=() exposed_bindings=()
  local gateway_binding_found=false expected_gateway_address="127.0.0.1:${gateway_port}"
  local check_publishers="ports: only the gateway and the frontend publish ports"
  local check_local="ports: every published port is bound to 127.0.0.1"
  local check_gateway="ports: the gateway publishes GATEWAY_PORT on 127.0.0.1"

  if ! containers=$(running_containers); then
    # Req local-environment: Containers run as a non-root user - Scenario: Process user of a project container
    for check in "containers: every main process runs as non-root" "$check_publishers" "$check_local" \
      "$check_gateway"; do
      fail "$check" "$containers"
    done
    return
  fi

  while IFS='|' read -r container_id service pid ports; do
    read -r -a bindings <<< "$ports"
    for binding in "${bindings[@]}"; do
      host_address=${binding#*=}
      if [[ $PUBLISHING_SERVICES != *" $service "* && " ${publishing_services[*]} " != *" $service "* ]]; then
        publishing_services+=("$service")
      fi
      if [[ ${host_address%:*} != 127.0.0.1 ]]; then
        exposed_bindings+=("$service on $host_address")
      fi
      if [[ $service == gateway && $host_address == "$expected_gateway_address" ]]; then
        gateway_binding_found=true
      fi
    done
    check_non_root "$container_id" "$service" "$pid"
  done <<< "$containers"

  # Req local-environment: Only the gateway and the frontend publish ports - Scenarios: Published ports of a
  # running system; Connection from the host to the database or the identity service
  if ((${#publishing_services[@]} == 0)); then
    pass "$check_publishers"
  else
    fail "$check_publishers" "ports are also published by: ${publishing_services[*]}"
  fi

  # Req local-environment: Published ports are reachable only from the local machine - Scenario: Connection from
  # another machine on the network
  if ((${#exposed_bindings[@]} == 0)); then
    pass "$check_local"
  else
    fail "$check_local" "published on another address: ${exposed_bindings[*]}"
  fi

  # Req local-environment: Published ports are reachable only from the local machine - Scenario: Connection from
  # the local machine
  if [[ -n $gateway_port_problem ]]; then
    fail "$check_gateway" "$gateway_port_problem"
  elif [[ $gateway_binding_found == true ]]; then
    pass "$check_gateway"
  else
    fail "$check_gateway" "the gateway container has no port published on $expected_gateway_address"
  fi
}

# Prints the values of the header named $1 that the echo service received, one per line, from the last response
# body (traefik/whoami prints one "Name: value" line per header value).
echoed_header_values() {
  local name=$1 line
  while IFS= read -r line; do
    line=${line%$'\r'}
    if [[ $line == "$name: "* ]]; then
      printf '%s\n' "${line#"$name: "}"
    fi
  done <<< "$BODY"
}

# Checks that the echo service received exactly one value of a header, equal to the expected one.
# Usage: expect_echoed_header <check name> <header> <expected value>
expect_echoed_header() {
  local check=$1 header=$2 expected=$3
  local -a values
  mapfile -t values < <(echoed_header_values "$header")
  if ((${#values[@]} != 1)); then
    fail "$check" "expected one $header header, got ${#values[@]}: ${values[*]}"
  elif [[ ${values[0]} != "$expected" ]]; then
    fail "$check" "$header is '${values[0]}', expected '$expected'"
  else
    pass "$check"
  fi
}

# Reports every forwarding check as skipped, or as failed when --require-echo was given.
# Usage: skip_or_fail_forwarding <reason> <check name>...
skip_or_fail_forwarding() {
  local reason=$1 check
  shift
  for check in "$@"; do
    if [[ $require_echo == true ]]; then
      fail "$check" "$reason (required by --require-echo)"
    else
      skip "$check" "$reason"
    fi
  done
}

# Req api-gateway: The gateway forwards the original client information - Scenarios: Service receives the real
# client address; Forged forwarding header; Service receives the original host and scheme (DS-08)
# The request goes through the test-only route to the echo service, with forged X-Forwarded-* headers. With Docker
# port publishing the gateway sees the Docker bridge address as the client, not 127.0.0.1, so the check asserts
# exactly one address that is not the forged one.
check_forwarding() {
  local check_for="forwarding: X-Forwarded-For holds one real address, not the forged one"
  local check_host="forwarding: X-Forwarded-Host is the host used"
  local check_proto="forwarding: X-Forwarded-Proto is the scheme used"
  local -a checks=("$check_for" "$check_host" "$check_proto") for_values
  local check no_echo="the $ECHO_SERVICE service is not in the compose configuration (add tests/smoke/compose.echo.yml)"
  local token

  if [[ -n $compose_problem ]]; then
    skip_or_fail_forwarding "the compose configuration could not be read" "${checks[@]}"
    return
  fi
  if [[ $'\n'$compose_service_lines != *$'\n'"$ECHO_SERVICE"$'\t'* ]]; then
    skip_or_fail_forwarding "$no_echo" "${checks[@]}"
    return
  fi
  if [[ -n $gateway_port_problem ]]; then
    for check in "${checks[@]}"; do
      fail "$check" "$gateway_port_problem"
    done
    return
  fi

  # The token reaches curl on its standard input (api_test_token, tests/smoke/identity-checks.sh).
  if ! token=$(api_test_token CLIENT); then
    for check in "${checks[@]}"; do
      fail "$check" "no access token for the echo route: $token"
    done
    return
  fi
  http_get "http://localhost:${gateway_port}${ECHO_PATH}" --header @- --header "X-Forwarded-For: $FORGED_FOR" \
    --header "X-Forwarded-Host: $FORGED_HOST" --header "X-Forwarded-Proto: $FORGED_PROTO" \
    < <(printf 'Authorization: Bearer %s\n' "$token")
  if [[ $STATUS != 200 ]]; then
    for check in "${checks[@]}"; do
      fail "$check" "expected 200 from the echo route $ECHO_PATH, $(last_response)"
    done
    return
  fi

  # Scenarios: Service receives the real client address; Forged forwarding header
  mapfile -t for_values < <(echoed_header_values X-Forwarded-For)
  if ((${#for_values[@]} != 1)); then
    fail "$check_for" "expected one X-Forwarded-For header, got ${#for_values[@]}: ${for_values[*]}"
  elif [[ ${for_values[0]} == *"$FORGED_FOR"* ]]; then
    fail "$check_for" "X-Forwarded-For '${for_values[0]}' contains the forged value $FORGED_FOR"
  elif [[ ! ${for_values[0]} =~ ^[0-9A-Fa-f.:]+$ ]]; then
    fail "$check_for" "X-Forwarded-For '${for_values[0]}' is not one IP address"
  else
    pass "$check_for"
  fi

  # Scenario: Service receives the original host and scheme
  expect_echoed_header "$check_host" X-Forwarded-Host "localhost:${gateway_port}"
  expect_echoed_header "$check_proto" X-Forwarded-Proto http
}

# Sends a request to a URL and sets STATUS (000 when no HTTP response arrived), HEADERS (the response headers, one
# per line, with no carriage return) and ERROR (curl's error message, empty when a response arrived). The body is
# discarded. Extra arguments are passed to curl.
# Usage: http_headers <method> <url> [curl arguments...]
http_headers() {
  local method=$1 url=$2 output last_line
  shift 2
  output=$(curl --silent --noproxy '*' --max-time "$REQUEST_TIMEOUT_SECONDS" --request "$method" \
    --output /dev/null --dump-header - --write-out '\n%{http_code} %{errormsg}' "$@" "$url")
  last_line=${output##*$'\n'}
  HEADERS=${output%$'\n'*}
  HEADERS=${HEADERS//$'\r'/}
  STATUS=${last_line%% *}
  ERROR=${last_line#* }
}

# Prints the values of the response header named $1 (case-insensitive) from HEADERS, one per line.
response_header_values() {
  local name=${1,,} line
  while IFS= read -r line; do
    if [[ ${line,,} == "$name:"* ]]; then
      line=${line#*:}
      line=${line#"${line%%[![:space:]]*}"}
      printf '%s\n' "$line"
    fi
  done <<< "$HEADERS"
}

# Checks that the last response allowed exactly the expected origin, with one Access-Control-Allow-Origin header.
# Usage: expect_allowed_origin <check name> <expected origin> <description of the request>
expect_allowed_origin() {
  local check=$1 expected=$2 request=$3
  local -a values
  mapfile -t values < <(response_header_values Access-Control-Allow-Origin)
  if ((${#values[@]} != 1)); then
    fail "$check" "$request: expected one Access-Control-Allow-Origin header, got ${#values[@]}: ${values[*]}"
  elif [[ ${values[0]} != "$expected" ]]; then
    fail "$check" "$request: Access-Control-Allow-Origin is '${values[0]}', expected '$expected'"
  else
    pass "$check"
  fi
}

# Succeeds when the log of a Compose service contains a text, waiting up to LOG_WAIT_SECONDS for it to appear.
# Usage: service_log_contains <service> <text>
service_log_contains() {
  local service=$1 text=$2 attempt
  for ((attempt = 0; attempt <= LOG_WAIT_SECONDS; attempt++)); do
    if docker compose logs --no-color "$service" 2> /dev/null | grep --quiet --fixed-strings -- "$text"; then
      return 0
    fi
    if ((attempt < LOG_WAIT_SECONDS)); then
      sleep 1
    fi
  done
  return 1
}

# Req api-gateway: The frontend can call the API from the browser - Scenarios: CORS preflight from the frontend's
# address; CORS preflight from another origin; Status page loads the health of every service (DS-09)
# The gateway answers every preflight under /api/ itself, so the two preflight scenarios hold even without the route
# of the service; the cross-origin GET and the access-log control need the route. Each request carries a unique
# marker in its query string, which the access log of the service shows only when the request reached it: the GET
# marker must appear, which proves the log is observed, and the preflight marker must not.
check_cors() {
  local check_allowed="cors: preflight from FRONTEND_ORIGIN is answered and allows that origin"
  local check_not_forwarded="cors: the preflight does not reach $CORS_SERVICE"
  local check_other="cors: preflight from another origin gets no permission"
  local check_get="cors: GET $CORS_PATH from FRONTEND_ORIGIN answers 200 and allows that origin"
  local -a checks=("$check_allowed" "$check_not_forwarded" "$check_other" "$check_get") values
  local check frontend_origin base_url preflight_marker get_marker get_reached=false
  local problem=""

  if [[ -n $gateway_port_problem ]]; then
    problem=$gateway_port_problem
  elif ! frontend_origin=$(config_value FRONTEND_ORIGIN); then
    problem="FRONTEND_ORIGIN is not set in the environment or in .env"
  elif [[ -n $compose_problem ]]; then
    problem="the compose configuration could not be read: $compose_problem"
  elif [[ $'\n'$compose_service_lines != *$'\n'"$CORS_SERVICE"$'\t'* ]]; then
    problem="the $CORS_SERVICE service is not in the compose configuration"
  fi
  if [[ -n $problem ]]; then
    for check in "${checks[@]}"; do
      fail "$check" "$problem"
    done
    return
  fi

  base_url="http://localhost:${gateway_port}${CORS_PATH}"
  preflight_marker="smoke-cors-preflight-$$-${RANDOM}${RANDOM}"
  get_marker="smoke-cors-get-$$-${RANDOM}${RANDOM}"

  # Scenario: CORS preflight from the frontend's address
  http_headers OPTIONS "${base_url}?marker=${preflight_marker}" --header "Origin: $frontend_origin" \
    --header "Access-Control-Request-Method: GET"
  if [[ $STATUS != 2?? ]]; then
    fail "$check_allowed" "expected a 2xx answer to the preflight, $(last_response)"
  else
    expect_allowed_origin "$check_allowed" "$frontend_origin" "preflight"
  fi

  # Scenario: Status page loads the health of every service (the cross-origin request itself)
  http_headers GET "${base_url}?marker=${get_marker}" --header "Origin: $frontend_origin"
  if [[ $STATUS != 200 ]]; then
    fail "$check_get" "expected 200 from $base_url, $(last_response)"
  else
    expect_allowed_origin "$check_get" "$frontend_origin" "GET"
  fi

  # Scenario: CORS preflight from the frontend's address (the service does not receive the request)
  if service_log_contains "$CORS_SERVICE" "$get_marker"; then
    get_reached=true
  fi
  if [[ $get_reached != true ]]; then
    fail "$check_not_forwarded" "the access log of $CORS_SERVICE cannot be observed: the GET with marker $get_marker did not show up in it within $LOG_WAIT_SECONDS s"
  elif docker compose logs --no-color "$CORS_SERVICE" 2> /dev/null |
    grep --quiet --fixed-strings -- "$preflight_marker"; then
    fail "$check_not_forwarded" "the preflight with marker $preflight_marker shows up in the access log of $CORS_SERVICE"
  else
    pass "$check_not_forwarded"
  fi

  # Scenario: CORS preflight from another origin
  http_headers OPTIONS "$base_url" --header "Origin: $OTHER_ORIGIN" --header "Access-Control-Request-Method: GET"
  mapfile -t values < <(response_header_values Access-Control-Allow-Origin)
  if [[ $STATUS == 000 ]]; then
    fail "$check_other" "$(last_response)"
  elif ((${#values[@]} > 0)); then
    fail "$check_other" "the response has Access-Control-Allow-Origin: ${values[*]}"
  else
    pass "$check_other"
  fi
}

# The identity checks of change e1-identity-access (IA-17), which use the helpers above.
# shellcheck source=tests/smoke/identity-checks.sh
source tests/smoke/identity-checks.sh

main() {
  parse_arguments "$@"
  require_curl
  create_temp_dir

  if ! gateway_port=$(config_value GATEWAY_PORT); then
    gateway_port_problem="GATEWAY_PORT is not set in the environment or in .env"
  elif [[ ! $gateway_port =~ ^[0-9]+$ ]]; then
    gateway_port_problem="GATEWAY_PORT '$gateway_port' is not a port number"
  fi
  if ! compose_service_lines=$(compose_services); then
    compose_problem=$compose_service_lines
    compose_service_lines=""
  fi
  prepare_identity_checks

  # Req api-gateway: The gateway reports its own health - Scenario: Gateway running
  # Req continuous-integration: The smoke-test check verifies the running system through the gateway - Scenario:
  # Every endpoint answers
  expect_status "gateway: /healthz answers 200" 200 /healthz

  check_realm_discovery

  # Req api-gateway: The gateway serves only the expected host names - Scenario: Request with an unexpected host name
  expect_status "gateway: Host evil.example gets 421" 421 /api/catalog/health --header "Host: evil.example"

  # Req api-gateway: Identity service health and metrics are never exposed - Scenario: Identity service health
  # through the gateway
  expect_status "route /auth/health answers 404" 404 /auth/health
  expect_status "route /auth/health/ready answers 404" 404 /auth/health/ready

  # Req api-gateway: Identity service health and metrics are never exposed - Scenario: Identity service metrics
  # through the gateway
  expect_status "route /auth/metrics answers 404" 404 /auth/metrics

  # Req api-gateway: Requests that match no route are rejected - Scenario: Unknown backend service
  expect_status "route /api/unknown/health answers 404" 404 /api/unknown/health

  # Req api-gateway: Requests that match no route are rejected - Scenario: Path outside every route
  expect_status "route /internal/status answers 404" 404 /internal/status

  check_labeled_services
  check_running_containers
  check_forwarding
  check_cors
  run_identity_checks

  printf 'Smoke test: %d passed, %d failed, %d skipped\n' "$passed" "$failed" "$skipped"
  ((failed == 0))
}

main "$@"
