#!/usr/bin/env bash
# Runs one Bruno API test collection against the running system (D-24).
#
# Usage: tests/api/run.sh <collection>      for example: tests/api/run.sh catalog
#
# Start the system first ("docker compose up -d --wait"). Bruno CLI runs inside the pinned Node container of the CI,
# installed from tests/api/package-lock.json with "npm ci" (DS-25; nothing is installed on the host, D-12). The
# container shares the network namespace of the gateway, so the collections call http://localhost:8080, the host
# name and port the gateway serves, the same way on every machine and in CI.
#
# Test tokens: until the test users of e1-identity-access exist (#30, IA-10, IA-11), this script builds unsigned test
# tokens with a new `sub` for each role and run, so runs never see each other's data. The services only decode the
# payload (token-claims contract), and the gateway does not validate tokens yet. Once the access check of #30 is in
# place these tokens are rejected, and this script must get real ones from the ticketera-api-tests client instead.
#
# Exit status: Bruno's (0 when every request and assertion passes), 2 for a usage error or a stopped gateway.
set -euo pipefail

readonly NODE_IMAGE="node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5"

cd "$(dirname "${BASH_SOURCE[0]}")"
collection=${1:-}
if [[ -z $collection || ! -f "$collection/bruno.json" ]]; then
  collections=$(for dir in */; do [[ -f "$dir/bruno.json" ]] && printf '%s ' "${dir%/}"; done)
  echo "usage: tests/api/run.sh <collection>; collections: $collections" >&2
  exit 2
fi
gateway=$(docker compose ps --quiet gateway 2> /dev/null || true)
if [[ -z $gateway ]]; then
  echo "the gateway is not running: start the system with docker compose up -d --wait" >&2
  exit 2
fi

base64url() { printf '%s' "$1" | base64 | tr -d '\n=' | tr '+/' '-_'; }
test_token() {
  local sub=$1 role=$2
  printf '%s.%s.%s' "$(base64url '{"alg":"none","typ":"JWT"}')" \
    "$(base64url "{\"sub\":\"$sub\",\"realm_access\":{\"roles\":[\"$role\"]}}")" "$(base64url unsigned)"
}
run_id="$(date +%s)-$RANDOM"

docker run --rm --network "container:$gateway" --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --volume "$PWD:/work" --workdir /work "$NODE_IMAGE" sh -c '
    npm ci --no-audit --no-fund --loglevel=error && cd "$0" && ../node_modules/.bin/bru run --env local \
      --env-var "ownerToken=$1" --env-var "otherOwnerToken=$2" --env-var "adminToken=$3" --env-var "clientToken=$4"
  ' "$collection" \
  "$(test_token "bruno-owner-$run_id" EVENT_OWNER)" "$(test_token "bruno-other-owner-$run_id" EVENT_OWNER)" \
  "$(test_token "bruno-admin-$run_id" ADMIN)" "$(test_token "bruno-client-$run_id" CLIENT)"
