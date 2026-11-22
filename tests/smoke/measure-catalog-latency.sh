#!/usr/bin/env bash
# Measures the response time of the public catalog through the gateway (change e1-event-catalog, task 6.2; Req
# event-browsing: The public catalog answers quickly).
#
# Usage: tests/smoke/measure-catalog-latency.sh       (with the system running: docker compose up -d --wait)
#
# Creates and publishes 100 events as a new test EVENT_OWNER, then sends 10 warm-up and 100 measured sequential
# requests of GET /api/catalog/events?limit=100 and prints the 50th and 95th percentiles. The spec asks for a p95 of
# 300 ms or less on a development machine; the result goes to the team log. Not a CI gate: shared runners are noisy.
#
# Test token: unsigned, as in tests/api/run.sh, until the test users of e1-identity-access exist (#30).
#
# Exit status: 0 when the p95 is within the limit, 1 when it is not or a request fails, 2 for a usage error.
set -uo pipefail

readonly EVENTS=100
readonly WARM_UP=10
readonly MEASURED=100
readonly LIMIT_MS=300

cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 2
port=${GATEWAY_PORT:-$(sed -n 's/^GATEWAY_PORT=//p' .env 2> /dev/null | tail -1 | tr -d '\r')}
[[ $port =~ ^[0-9]+$ ]] || { echo "GATEWAY_PORT is not set in the environment or in .env" >&2; exit 2; }
base="http://localhost:${port}/api/catalog"

base64url() { printf '%s' "$1" | base64 | tr -d '\n=' | tr '+/' '-_'; }
token="$(base64url '{"alg":"none","typ":"JWT"}').$(base64url \
  "{\"sub\":\"latency-owner-$(date +%s)-$RANDOM\",\"realm_access\":{\"roles\":[\"EVENT_OWNER\"]}}").$(base64url unsigned)"
starts_at=$(date -u -d '+30 days' +%Y-%m-%dT%H:%M:%SZ)

echo "Creating and publishing $EVENTS events..."
for ((n = 1; n <= EVENTS; n++)); do
  key=$(cat /proc/sys/kernel/random/uuid)
  body="{\"title\":\"Evento de medición $n\",\"type\":\"CONCERT\",\"organizer_name\":\"Medición\",\"starts_at\":\"$starts_at\",\"venue\":{\"name\":\"Sala\",\"city\":\"Rosario\"},\"zones\":[{\"code\":\"A\",\"name\":\"A\",\"modality\":\"UNNUMBERED\",\"capacity\":100}]}"
  id=$(curl -sf -X POST "$base/manage/events" -H "Authorization: Bearer $token" -H "Idempotency-Key: $key" \
    -H 'Content-Type: application/json' -d "$body" | sed -n 's/.*"id":"\([0-9a-f-]*\)".*/\1/p')
  if [[ -z $id ]] || ! curl -sf -o /dev/null -X POST "$base/manage/events/$id/publish" -H "Authorization: Bearer $token"; then
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
