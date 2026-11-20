# Correlation id and gateway access log checks of the smoke test (change e1-request-log, task 1.2).
#
# Sourced by tests/smoke/smoke-test.sh, which provides pass, fail, skip, http_headers, response_header_values,
# skip_or_fail_forwarding, the gateway port and the compose service lines; it runs from the repository root. This
# file defines only constants and functions; main calls check_correlation_ids and then check_gateway_access_log.
#
# Each request records its correlation id; the access log checks then look for the gateway lines that carry that id
# (design RL-01) and check them against tests/platform/gateway-log.schema.json with scripts/check_log_lines.py, run
# in the pinned Python container with the repository mounted read-only.
#
# shellcheck shell=bash

readonly CORRELATION_HEADER="X-Correlation-ID"
readonly CORRELATION_ID_PATTERN='^[0-9a-f]{32}$'
readonly FORGED_CORRELATION_ID="00000000000000000000000000000000"
readonly CONCURRENT_REQUESTS=50
readonly UNAVAILABLE_PATH="/smoke-test/unavailable/"
readonly ACCESS_CHECK_PATH="/api/sales/example"
readonly GATEWAY_LOG_SCHEMA="tests/platform/gateway-log.schema.json"
readonly SERVICE_LOG_SCHEMA="tests/platform/request-log.schema.json"
# Backend services that already write the request log (task group 2); sales joins in task group 3.
readonly REQUEST_LOG_SERVICES="catalog payments"
# A Uvicorn access line: client address, then the quoted request line and the status code.
readonly UVICORN_ACCESS_LINE='"[A-Z]+ [^"]* HTTP/[0-9.]+" [0-9]{3}'

# Requests whose gateway lines check_gateway_access_log verifies: "<description>|<correlation id>|<status>".
logged_requests=()
# Correlation id of a /healthz request, which must have no access log line.
healthz_correlation_id=""
# Random markers that must never appear in the gateway log: a token in the query string and a forged header.
query_token_marker=""
forged_header_marker=""

# Prints the correlation id of the last response (see http_headers), or nothing when it has none or more than one.
last_correlation_id() {
  local -a values
  mapfile -t values < <(response_header_values "$CORRELATION_HEADER")
  if ((${#values[@]} == 1)); then
    printf '%s\n' "${values[0]}"
  fi
}

# Sends a request through the gateway and checks that the answer has the expected status and one well-formed
# correlation id; on success records the request for the access log checks.
# Usage: expect_correlated_answer <check name> <expected status> <path> [curl arguments...]
expect_correlated_answer() {
  local check=$1 expected=$2 path=$3 id
  shift 3
  http_headers GET "http://localhost:${gateway_port}${path}" "$@"
  id=$(last_correlation_id)
  if [[ $STATUS != "$expected" ]]; then
    fail "$check" "expected $expected from $path, $(last_response)"
  elif [[ ! $id =~ $CORRELATION_ID_PATTERN ]]; then
    fail "$check" "the $STATUS answer to $path has no single $CORRELATION_HEADER of 32 lowercase hex characters: '$(response_header_values "$CORRELATION_HEADER" | tr '\n' ' ')'"
  else
    pass "$check"
    logged_requests+=("$expected answer to $path|$id|$expected")
  fi
}

# Req request-correlation: The gateway gives every request a correlation id - Scenarios: Forwarded request; Request
# rejected by the access check; Path that matches no route; Service stopped; Two consecutive requests; Concurrent
# requests
# Req request-correlation: The correlation id is never taken from the client - both scenarios
# Req request-correlation: The gateway forwards the correlation id to the service - Scenario: Correlation id seen
# by the service (through the echo route, which includes the same forwarding snippet as every real route)
check_correlation_ids() {
  local first second check

  if [[ -n $gateway_port_problem ]]; then
    fail "correlation: the gateway answers with correlation ids" "$gateway_port_problem"
    return
  fi

  expect_correlated_answer "correlation: 200 answer has an $CORRELATION_HEADER" 200 /api/catalog/health
  expect_correlated_answer "correlation: 404 answer has an $CORRELATION_HEADER" 404 /api/unknown/health
  expect_correlated_answer "correlation: 421 answer has an $CORRELATION_HEADER" 421 /api/catalog/health \
    --header "Host: evil.example"

  # The access check of e1-identity-access answers 401 here; before it is merged the path is not protected.
  check="correlation: 401 answer of the access check has an $CORRELATION_HEADER"
  http_headers GET "http://localhost:${gateway_port}${ACCESS_CHECK_PATH}"
  if [[ $STATUS == 401 ]]; then
    expect_correlated_answer "$check" 401 "$ACCESS_CHECK_PATH"
  else
    skip "$check" "$ACCESS_CHECK_PATH answers $STATUS without a token: the access check of e1-identity-access is not in place yet"
  fi

  if [[ $'\n'$compose_service_lines == *$'\n'"$ECHO_SERVICE"$'\t'* ]]; then
    expect_correlated_answer "correlation: 502 answer has an $CORRELATION_HEADER" 502 "$UNAVAILABLE_PATH"
  else
    skip_or_fail_forwarding "the $ECHO_SERVICE service is not in the compose configuration (add tests/smoke/compose.echo.yml)" \
      "correlation: 502 answer has an $CORRELATION_HEADER"
  fi

  # Scenario: Two consecutive requests
  check="correlation: two consecutive requests get different ids"
  http_headers GET "http://localhost:${gateway_port}/api/catalog/health"
  first=$(last_correlation_id)
  http_headers GET "http://localhost:${gateway_port}/api/catalog/health"
  second=$(last_correlation_id)
  if [[ -z $first || -z $second ]]; then
    fail "$check" "a response had no single $CORRELATION_HEADER"
  elif [[ $first == "$second" ]]; then
    fail "$check" "both responses carry $first"
  else
    pass "$check"
  fi

  check_concurrent_correlation_ids
  check_forged_correlation_id
  check_healthz_correlation_id
  check_logged_values_markers
}

# Scenario: Concurrent requests. curl sends them in parallel and prints the header of each response.
check_concurrent_correlation_ids() {
  local check="correlation: $CONCURRENT_REQUESTS concurrent requests get $CONCURRENT_REQUESTS different ids"
  local url="http://localhost:${gateway_port}/api/catalog/health" output index valid_count unique_count
  local -a arguments=() ids
  for ((index = 0; index < CONCURRENT_REQUESTS; index++)); do
    arguments+=(--output /dev/null "$url")
  done
  output=$(curl --silent --noproxy '*' --max-time "$REQUEST_TIMEOUT_SECONDS" --parallel \
    --parallel-max "$CONCURRENT_REQUESTS" --write-out '%header{x-correlation-id}\n' "${arguments[@]}")
  mapfile -t ids < <(grep -E "$CORRELATION_ID_PATTERN" <<< "$output")
  valid_count=${#ids[@]}
  unique_count=$(printf '%s\n' "${ids[@]}" | sort -u | grep -c .)
  if ((valid_count != CONCURRENT_REQUESTS)); then
    fail "$check" "$valid_count of $CONCURRENT_REQUESTS responses carried a well-formed $CORRELATION_HEADER"
  elif ((unique_count != CONCURRENT_REQUESTS)); then
    fail "$check" "only $unique_count of the $CONCURRENT_REQUESTS ids are different"
  else
    pass "$check"
  fi
}

# Req request-correlation: The correlation id is never taken from the client - Scenario: Client sends its own
# correlation id; Req request-correlation: The gateway forwards the correlation id to the service - Scenario:
# Correlation id seen by the service
check_forged_correlation_id() {
  local check_replaced="correlation: a forged $CORRELATION_HEADER is replaced in the response"
  local check_forwarded="correlation: the service receives the gateway's id, not the forged one"
  local id

  http_headers GET "http://localhost:${gateway_port}/api/catalog/health" \
    --header "$CORRELATION_HEADER: $FORGED_CORRELATION_ID"
  id=$(last_correlation_id)
  if [[ ! $id =~ $CORRELATION_ID_PATTERN ]]; then
    fail "$check_replaced" "the response has no single well-formed $CORRELATION_HEADER, $(last_response)"
  elif [[ $id == "$FORGED_CORRELATION_ID" ]]; then
    fail "$check_replaced" "the response returns the forged id"
  else
    pass "$check_replaced"
  fi

  if [[ $'\n'$compose_service_lines != *$'\n'"$ECHO_SERVICE"$'\t'* ]]; then
    skip_or_fail_forwarding "the $ECHO_SERVICE service is not in the compose configuration (add tests/smoke/compose.echo.yml)" \
      "$check_forwarded"
    return
  fi
  # http_get keeps the body, where the echo service lists the headers it received; the response header is read
  # with --dump-header into the temporary directory.
  http_get "http://localhost:${gateway_port}${ECHO_PATH}" --header "$CORRELATION_HEADER: $FORGED_CORRELATION_ID" \
    --dump-header "$temp_dir/echo-headers"
  HEADERS=$(tr -d '\r' < "$temp_dir/echo-headers" 2> /dev/null)
  id=$(last_correlation_id)
  if [[ $STATUS != 200 ]]; then
    fail "$check_forwarded" "expected 200 from the echo route $ECHO_PATH, $(last_response)"
  elif [[ ! $id =~ $CORRELATION_ID_PATTERN ]]; then
    fail "$check_forwarded" "the echo response has no single well-formed $CORRELATION_HEADER"
  else
    # traefik/whoami is written in Go, which prints header names in canonical form: X-Correlation-Id.
    expect_echoed_header "$check_forwarded" "X-Correlation-Id" "$id"
  fi
}

# Records the id of a /healthz request, whose access log is off (Req api-gateway: The gateway writes one JSON access
# log line per request - Scenario: Gateway healthcheck).
check_healthz_correlation_id() {
  http_headers GET "http://localhost:${gateway_port}/healthz"
  healthz_correlation_id=$(last_correlation_id)
}

# Sends the requests whose values must never reach the gateway log, and one whose path needs JSON escaping.
# Req request-correlation: The correlation id is never taken from the client - Scenario: Client sends a malicious
# correlation id; Req api-gateway: The gateway access log keeps tokens and the query string out - both scenarios
check_logged_values_markers() {
  query_token_marker="smoke-query-token-$$-${RANDOM}${RANDOM}"
  forged_header_marker="smoke-forged-id-$$-${RANDOM}${RANDOM}"
  http_headers GET "http://localhost:${gateway_port}/api/catalog/health?access_token=${query_token_marker}"
  http_headers GET "http://localhost:${gateway_port}/api/catalog/health" \
    --header "$CORRELATION_HEADER: \"${forged_header_marker}\"0123456789abcdef0123456789abcdef"
  expect_correlated_answer "correlation: 404 answer to a path with a quote and a line break has an $CORRELATION_HEADER" \
    404 "/api/unknown/smoke%22quote%0Aline"
}

# Prints the gateway log lines that contain a text, waiting up to LOG_WAIT_SECONDS for at least one to appear.
gateway_log_lines_with() {
  compose_log_lines_with gateway "$1"
}

# Prints the log lines of a Compose service that contain a text, waiting up to LOG_WAIT_SECONDS for at least one.
# Usage: compose_log_lines_with <service> <text>
compose_log_lines_with() {
  local service=$1 text=$2 attempt lines
  for ((attempt = 0; attempt <= LOG_WAIT_SECONDS; attempt++)); do
    lines=$(docker compose logs --no-color --no-log-prefix "$service" 2> /dev/null | grep --fixed-strings -- "$text")
    if [[ -n $lines ]]; then
      printf '%s\n' "$lines"
      return 0
    fi
    if ((attempt < LOG_WAIT_SECONDS)); then
      sleep 1
    fi
  done
  return 1
}

# Checks lines read on standard input against a schema; prints the checker's report and fails when any line fails.
# Usage: check_against_schema <schema path>
check_against_schema() {
  docker run --rm -i --network none --read-only --user "$(id -u):$(id -g)" --volume "$PWD:/repo:ro" \
    --workdir /repo "$PYTHON_IMAGE" python -I -B scripts/check_log_lines.py "$1" 2>&1
}

# Req api-gateway: The gateway writes one JSON access log line per request - Scenarios: Forwarded request; Request
# rejected by the access check; Request to a stopped service; Unexpected host name; Gateway healthcheck
# Req api-gateway: The gateway access log line has a fixed set of fields - Scenario: Fields of a gateway line
# Req api-gateway: The gateway access log keeps tokens and the query string out - both scenarios
# Req request-correlation: The correlation id is never taken from the client - Scenario: Client sends a malicious
# correlation id
check_gateway_access_log() {
  local entry description id status lines count report check log

  for entry in "${logged_requests[@]}"; do
    IFS='|' read -r description id status <<< "$entry"
    check="gateway log: one valid JSON line for the $description"
    if ! lines=$(gateway_log_lines_with "$id"); then
      fail "$check" "no gateway log line carries its correlation id $id within $LOG_WAIT_SECONDS s"
      continue
    fi
    count=$(grep -c . <<< "$lines")
    if ((count != 1)); then
      fail "$check" "$count gateway log lines carry its correlation id $id"
    elif ! report=$(check_against_schema "$GATEWAY_LOG_SCHEMA" <<< "$lines"); then
      fail "$check" "the line does not match $GATEWAY_LOG_SCHEMA: $report"
    elif [[ $lines != *"\"status\":${status},"* ]]; then
      fail "$check" "the line does not record status $status: $lines"
    else
      pass "$check"
    fi
  done

  check="gateway log: no line for /healthz"
  if [[ ! $healthz_correlation_id =~ $CORRELATION_ID_PATTERN ]]; then
    fail "$check" "the /healthz answer has no single well-formed $CORRELATION_HEADER"
  elif gateway_log_lines_with "$healthz_correlation_id" > /dev/null; then
    fail "$check" "a gateway log line carries the correlation id $healthz_correlation_id of /healthz"
  else
    pass "$check"
  fi

  log=$(docker compose logs --no-color --no-log-prefix gateway 2> /dev/null)
  check="gateway log: a token in the query string is never logged"
  if [[ -z $query_token_marker ]]; then
    fail "$check" "the request with the marker was not sent"
  elif grep --quiet --fixed-strings -- "$query_token_marker" <<< "$log"; then
    fail "$check" "the gateway log contains the query string token $query_token_marker"
  else
    pass "$check"
  fi

  check="gateway log: a forged $CORRELATION_HEADER is never logged"
  if [[ -z $forged_header_marker ]]; then
    fail "$check" "the request with the marker was not sent"
  elif grep --quiet --fixed-strings -- "$forged_header_marker" <<< "$log"; then
    fail "$check" "the gateway log contains the forged value $forged_header_marker"
  else
    pass "$check"
  fi
}

# Req request-log: The request log line has a fixed set of fields - Scenarios: Fields of a request log line; Same
# schema in every service
# Req request-log: The server writes no other access log - Scenario: One line per request
# Req request-correlation: The same correlation id ties the gateway line to the service line - Scenario: Request
# followed from the gateway to the service
check_service_request_logs() {
  local service id lines count report check check_tie check_uvicorn log

  if [[ -n $gateway_port_problem ]]; then
    fail "service request log: lines of every service" "$gateway_port_problem"
    return
  fi

  for service in $REQUEST_LOG_SERVICES; do
    check="service request log: $service writes one valid line for a request through the gateway"
    check_tie="service request log: the $service line and the gateway line share the correlation id"
    check_uvicorn="service request log: $service writes no Uvicorn access line"

    http_headers GET "http://localhost:${gateway_port}/api/${service}/health"
    id=$(last_correlation_id)
    if [[ $STATUS != 200 || ! $id =~ $CORRELATION_ID_PATTERN ]]; then
      fail "$check" "expected 200 with a correlation id from /api/${service}/health, $(last_response)"
      fail "$check_tie" "no request to follow"
    elif ! lines=$(compose_log_lines_with "$service" "$id"); then
      fail "$check" "no $service log line carries the correlation id $id within $LOG_WAIT_SECONDS s"
      fail "$check_tie" "no $service line to compare"
    else
      count=$(grep -c . <<< "$lines")
      if ((count != 1)); then
        fail "$check" "$count $service log lines carry the correlation id $id"
      elif ! report=$(check_against_schema "$SERVICE_LOG_SCHEMA" <<< "$lines"); then
        fail "$check" "the line does not match $SERVICE_LOG_SCHEMA: $report"
      elif [[ $lines != *'"route":"/health"'* || $lines != *'"status":200'* ]]; then
        fail "$check" "the line does not record route /health and status 200: $lines"
      else
        pass "$check"
      fi
      if [[ $(gateway_log_lines_with "$id" | grep -c .) == 1 ]]; then
        pass "$check_tie"
      else
        fail "$check_tie" "expected exactly one gateway line with the correlation id $id"
      fi
    fi

    # The log is read first: with pipefail, grep --quiet ending the pipe early would make it fail when it matches.
    log=$(docker compose logs --no-color --no-log-prefix "$service" 2> /dev/null)
    if grep --quiet --extended-regexp -- "$UVICORN_ACCESS_LINE" <<< "$log"; then
      fail "$check_uvicorn" "the $service log has Uvicorn access lines (start Uvicorn with --no-access-log)"
    else
      pass "$check_uvicorn"
    fi
  done
}
