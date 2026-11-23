#!/usr/bin/env bash
# Measures the response time of the public catalog through the gateway (change e1-event-catalog, task 6.2; Req
# event-browsing: The public catalog answers quickly).
#
# Usage: tests/smoke/measure-catalog-latency.sh       (with the system running: docker compose up -d --wait)
#
# Creates and publishes 100 events as the EVENT_OWNER test user, then sends 10 warm-up and 100 measured sequential
# requests of GET /api/catalog/events?limit=100 and prints the 50th and 95th percentiles. The spec asks for a p95 of
# 300 ms or less on a development machine; the result goes to the team log. Not a CI gate: shared runners are noisy.
#
# Test token (change e1-identity-access, task 1.27; IA-11, IA-18): a real access token of test-event-owner from the
# ticketera-api-tests client, with the password grant and the openid scope. The password comes from the environment
# of the identity service in "docker compose config" and reaches curl on its standard input; the token reaches curl
# in a header file, so neither is on a command line. A token lasts 60 s, so a new one is requested before any
# request made with less than 15 s of it left. When a token request fails, the script stops with a message that
# names the username, and never prints the password or the token. The 110 measured requests are public.
#
# Exit status: 0 when the p95 is within the limit, 1 when it is not or a request fails, 2 for a usage error.
set -uo pipefail

readonly EVENTS=100
readonly WARM_UP=10
readonly MEASURED=100
readonly LIMIT_MS=300
readonly PYTHON_IMAGE="python:3.13-alpine@sha256:1e1f6334529d1fb26a2ef619d7cffb30a7c7d7cc1cc7338ebee283a58d1aeaca"
readonly OWNER_USERNAME="test-event-owner"
readonly OWNER_PASSWORD_VARIABLE="TEST_USER_EVENT_OWNER_PASSWORD"
readonly TOKEN_MARGIN_SECONDS=15

cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 2
port=${GATEWAY_PORT:-$(sed -n 's/^GATEWAY_PORT=//p' .env 2> /dev/null | tail -1 | tr -d '\r')}
[[ $port =~ ^[0-9]+$ ]] || { echo "GATEWAY_PORT is not set in the environment or in .env" >&2; exit 2; }
base="http://localhost:${port}/api/catalog"
token_url="http://localhost:${port}/auth/realms/ticketera/protocol/openid-connect/token"

owner_token=""
owner_token_renew_at=0

# Prints the value of an environment variable of the identity service in the Compose configuration, read in the
# pinned Python container; fails when it is not set.
identity_environment_value() {
  docker compose config --format json 2> /dev/null | docker run --rm -i --network none "$PYTHON_IMAGE" python -I -c '
import json, sys
try:
    services = json.load(sys.stdin).get("services", {})
except ValueError:
    sys.exit(1)
value = ((services.get("identity") or {}).get("environment") or {}).get(sys.argv[1])
if not value:
    sys.exit(1)
print(value)' "$1"
}

# Stops the script because no token of the EVENT_OWNER test user could be obtained; names the username, never the
# password or the token.
stop_without_token() {
  echo "no access token for $OWNER_USERNAME: $1" >&2
  exit 1
}

# Makes sure owner_token holds an access token of the EVENT_OWNER test user with at least TOKEN_MARGIN_SECONDS of
# it left, requesting a new one when needed. Run it in the main shell, before each request that needs the token.
ensure_owner_token() {
  local password response expires_in
  (($(date +%s) < owner_token_renew_at)) && return
  if ! password=$(identity_environment_value "$OWNER_PASSWORD_VARIABLE"); then
    stop_without_token "$OWNER_PASSWORD_VARIABLE is not set for the identity service in docker compose config"
  fi
  if ! response=$(printf '%s' "$password" | curl -sf --data-urlencode grant_type=password \
    --data-urlencode client_id=ticketera-api-tests --data-urlencode "username=$OWNER_USERNAME" \
    --data-urlencode password@- --data-urlencode scope=openid "$token_url"); then
    stop_without_token "the token request failed"
  fi
  owner_token=$(sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p' <<< "$response")
  expires_in=$(sed -n 's/.*"expires_in":\([0-9]*\).*/\1/p' <<< "$response")
  if [[ -z $owner_token || -z $expires_in ]]; then
    stop_without_token "the token response has no access token"
  fi
  owner_token_renew_at=$(($(date +%s) + expires_in - TOKEN_MARGIN_SECONDS))
}

# Sends a request with the EVENT_OWNER test user's token, which reaches curl in a header file. Arguments are passed
# to curl. Call ensure_owner_token first, in the main shell: this function also runs inside command substitutions,
# where a new token would be lost.
curl_as_owner() {
  curl --header @<(printf 'Authorization: Bearer %s\n' "$owner_token") "$@"
}

starts_at=$(date -u -d '+30 days' +%Y-%m-%dT%H:%M:%SZ)

echo "Creating and publishing $EVENTS events..."
for ((n = 1; n <= EVENTS; n++)); do
  key=$(cat /proc/sys/kernel/random/uuid)
  body="{\"title\":\"Evento de medición $n\",\"type\":\"CONCERT\",\"organizer_name\":\"Medición\",\"starts_at\":\"$starts_at\",\"venue\":{\"name\":\"Sala\",\"city\":\"Rosario\"},\"zones\":[{\"code\":\"A\",\"name\":\"A\",\"modality\":\"UNNUMBERED\",\"capacity\":100}]}"
  ensure_owner_token
  id=$(curl_as_owner -sf -X POST "$base/manage/events" -H "Idempotency-Key: $key" \
    -H 'Content-Type: application/json' -d "$body" | sed -n 's/.*"id":"\([0-9a-f-]*\)".*/\1/p')
  ensure_owner_token
  if [[ -z $id ]] || ! curl_as_owner -sf -o /dev/null -X POST "$base/manage/events/$id/publish"; then
    echo "event $n could not be created and published" >&2
    exit 1
  fi
done

measure() {
  curl -s -o /dev/null -w '%{http_code} %{time_total}\n' "$base/events?limit=100"
}
for ((n = 0; n < WARM_UP; n++)); do measure > /dev/null; done
times=()
for ((n = 0; n < MEASURED; n++)); do
  read -r status seconds < <(measure)
  [[ $status == 200 ]] || { echo "request $n answered $status" >&2; exit 1; }
  times+=("$seconds")
done

read -r p50 p95 < <(printf '%s\n' "${times[@]}" | sort -n | awk -v n="$MEASURED" '
  { value[NR] = $1 * 1000 }
  END { printf "%d %d\n", value[int(n * 0.50 + 0.5)], value[int(n * 0.95 + 0.5)] }')
echo "GET /api/catalog/events?limit=100 with $EVENTS published events: p50 ${p50} ms, p95 ${p95} ms (limit ${LIMIT_MS} ms)"
((p95 <= LIMIT_MS))
