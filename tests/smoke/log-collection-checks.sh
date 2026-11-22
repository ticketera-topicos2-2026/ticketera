# Log collection checks of the smoke test: Alloy, Loki and Grafana (change e1-request-log, task 4.1).
#
# Sourced by tests/smoke/smoke-test.sh after tests/smoke/request-log-checks.sh, whose helpers it uses
# (last_correlation_id, CORRELATION_ID_PATTERN). main calls check_log_collection, and check_collection_is_optional
# last, because it stops and starts the three containers.
#
# Loki publishes no port (Req local-environment: Only the gateway and the frontend publish ports), so Loki is queried
# through Grafana's data source proxy with the administrator credentials from .env, which also proves that Grafana
# reaches Loki.
#
# shellcheck shell=bash

readonly COLLECTION_SERVICES="loki alloy grafana"
readonly LOKI_DATASOURCE_UID="loki"
readonly REQUEST_LOG_DASHBOARD_UID="request-log"
# Req log-collection: The logs of every container are collected and queryable - Scenario: Request found by its
# correlation id.
readonly LOKI_WAIT_SECONDS=15
# Req log-collection: Log collection does not affect the application - Scenario: Memory limits.
readonly COLLECTION_MEMORY_LIMIT_BYTES=$((768 * 1024 * 1024))

grafana_port=""
grafana_user=""
grafana_password=""
grafana_problem=""

# Reads the Grafana settings from the environment or .env; sets grafana_problem when one is missing.
read_grafana_settings() {
  if ! grafana_port=$(config_value GRAFANA_PORT); then
    grafana_problem="GRAFANA_PORT is not set in the environment or in .env"
  elif ! grafana_user=$(config_value GRAFANA_ADMIN_USER); then
    grafana_problem="GRAFANA_ADMIN_USER is not set in the environment or in .env"
  elif ! grafana_password=$(config_value GRAFANA_ADMIN_PASSWORD); then
    grafana_problem="GRAFANA_ADMIN_PASSWORD is not set in the environment or in .env"
  fi
}

# Sends a GET request to a Grafana path with the administrator credentials and sets STATUS, BODY and ERROR.
grafana_get() {
  http_get "http://localhost:${grafana_port}$1" --user "${grafana_user}:${grafana_password}" "${@:2}"
}

# Prints the log lines that a LogQL query returns over the last 10 minutes, one per line, or fails with the reason.
# The response is parsed in the pinned Python container (see run_python).
loki_lines() {
  local query=$1 now start
  now=$(date +%s)
  start=$((now - 600))
  grafana_get "/api/datasources/proxy/uid/${LOKI_DATASOURCE_UID}/loki/api/v1/query_range" --get \
    --data-urlencode "query=${query}" --data-urlencode "start=${start}000000000" \
    --data-urlencode "end=$((now + 60))000000000" --data-urlencode "limit=1000"
  if [[ $STATUS != 200 ]]; then
    printf 'the Loki query through Grafana failed: %s\n' "$(last_response)"
    return 1
  fi
  run_python '
import json, sys
for stream in json.load(sys.stdin)["data"]["result"]:
    for _, line in stream["values"]:
        print(stream["stream"].get("service", "-"), line.replace("\n", " "), sep="\t")
' <<< "$BODY"
}

# Req log-collection: The logs of every container are collected and queryable - Scenarios: Request found by its
# correlation id; Lines of one service
# Req log-collection: Grafana opens with the request log ready to use - Scenario: First start
# Req log-collection: Grafana requires the credentials from local configuration - Scenarios: Anonymous visit;
# Sign-in with the configured credentials
# Req log-collection: Log collection does not affect the application - Scenario: Memory limits
check_log_collection() {
  local check id lines attempt services other

  read_grafana_settings
  if [[ -n $grafana_problem ]]; then
    for check in "grafana: anonymous visit is refused" "grafana: data source and dashboard are provisioned" \
      "loki: a request is found by its correlation id" "loki: a service query returns only that service"; do
      fail "$check" "$grafana_problem"
    done
  else
    check="grafana: anonymous visit is refused"
    http_get "http://localhost:${grafana_port}/api/search"
    if [[ $STATUS == 401 ]]; then pass "$check"; else fail "$check" "expected 401 from /api/search, $(last_response)"; fi

    check="grafana: data source and dashboard are provisioned"
    grafana_get "/api/datasources/uid/${LOKI_DATASOURCE_UID}"
    if [[ $STATUS != 200 ]]; then
      fail "$check" "the Loki data source ${LOKI_DATASOURCE_UID} is missing, $(last_response)"
    else
      grafana_get "/api/dashboards/uid/${REQUEST_LOG_DASHBOARD_UID}"
      if [[ $STATUS == 200 ]]; then pass "$check"; else fail "$check" "the dashboard ${REQUEST_LOG_DASHBOARD_UID} is missing, $(last_response)"; fi
    fi

    check="loki: a request is found by its correlation id"
    http_headers GET "http://localhost:${gateway_port}/api/catalog/health"
    id=$(last_correlation_id)
    if [[ ! $id =~ $CORRELATION_ID_PATTERN ]]; then
      fail "$check" "the gateway answer has no correlation id, $(last_response)"
    else
      services=""
      for ((attempt = 0; attempt <= LOKI_WAIT_SECONDS; attempt++)); do
        if lines=$(loki_lines "{service=~\".+\"} |= \"${id}\""); then
          services=$(cut -f1 <<< "$lines" | sort -u | tr '\n' ' ')
          [[ $services == "catalog gateway " ]] && break
        fi
        ((attempt < LOKI_WAIT_SECONDS)) && sleep 1
      done
      if [[ $services == "catalog gateway " ]]; then
        pass "$check"
      else
        fail "$check" "within ${LOKI_WAIT_SECONDS} s Loki returned lines of: '${services}' (expected catalog and gateway); last answer: ${lines:0:300}"
      fi
    fi

    check="loki: a service query returns only that service"
    http_headers GET "http://localhost:${gateway_port}/api/sales/health"
    if ! lines=$(loki_lines '{service="sales"}'); then
      fail "$check" "$lines"
    elif [[ -z $lines ]]; then
      fail "$check" "the query on service sales returned no line"
    elif other=$(cut -f1 <<< "$lines" | grep -v -x sales | sort -u | tr '\n' ' ') && [[ -n $other ]]; then
      fail "$check" "the query on service sales returned lines of: $other"
    else
      pass "$check"
    fi
  fi

  check_collection_memory_limits
}

check_collection_memory_limits() {
  local check="collection: each container has a memory limit, 768 MiB in total at most" service id limit total=0
  local -a missing=()
  for service in $COLLECTION_SERVICES; do
    id=$(docker compose ps --quiet "$service" 2> /dev/null)
    limit=$( [[ -n $id ]] && docker inspect --format '{{.HostConfig.Memory}}' "$id" 2> /dev/null)
    if [[ -z $limit || $limit == 0 ]]; then
      missing+=("$service")
    else
      total=$((total + limit))
    fi
  done
  if ((${#missing[@]} > 0)); then
    fail "$check" "no running container or no memory limit for: ${missing[*]}"
  elif ((total > COLLECTION_MEMORY_LIMIT_BYTES)); then
    fail "$check" "the limits add up to $((total / 1024 / 1024)) MiB"
  else
    pass "$check"
  fi
}

# Req log-collection: Log collection does not affect the application - Scenario: Log collection stopped
# Stops the three containers, checks every backend route and the realm through the gateway, and starts them again,
# waiting until they are healthy, so the smoke test leaves no state behind.
check_collection_is_optional() {
  local check="collection: with Loki, Alloy and Grafana stopped, the gateway routes keep answering" service
  local -a failures=() services
  read -r -a services <<< "$COLLECTION_SERVICES"
  if [[ -n $gateway_port_problem ]]; then
    fail "$check" "$gateway_port_problem"
    return
  fi
  if ! docker compose stop "${services[@]}" > /dev/null 2>&1; then
    fail "$check" "docker compose stop failed: $(compose_error stop "${services[@]}")"
    return
  fi
  for service in catalog sales payments; do
    http_get "http://localhost:${gateway_port}/api/${service}/health"
    [[ $STATUS == 200 ]] || failures+=("/api/${service}/health $(last_response)")
  done
  http_get "http://localhost:${gateway_port}/auth/realms/ticketera/.well-known/openid-configuration"
  [[ $STATUS == 200 ]] || failures+=("realm discovery $(last_response)")
  if ! docker compose up --detach --wait --wait-timeout 300 "${services[@]}" > /dev/null 2>&1; then
    failures+=("the containers did not become healthy again: $(compose_error up --detach --wait "${services[@]}")")
  fi
  if ((${#failures[@]} == 0)); then
    pass "$check"
  else
    fail "$check" "${failures[*]}"
  fi
}
