#!/usr/bin/env bash
# Runs one Bruno API test collection against the running system (D-24).
#
# Usage: tests/api/run.sh <collection>      for example: tests/api/run.sh catalog
#
# Start the system first ("docker compose up -d --wait"). Bruno CLI runs inside the pinned Node container of the CI,
# installed from tests/api/package-lock.json with "npm ci" (DS-25; nothing is installed on the host, D-12). The
# container shares the network namespace of the gateway, so the collections call http://localhost:8080, the host
# name and port the gateway serves, the same way on every machine and in CI. The docker compose commands run from
# the repository root, so a relative COMPOSE_FILE, such as that of the echo overlay of the smoke test, is found.
#
# Test tokens (change e1-identity-access, task 1.27; IA-10, IA-11, IA-18): after npm ci, right before Bruno starts,
# the container gets real access tokens from the ticketera-api-tests client, with the password grant and the openid
# scope, and passes them to Bruno as ownerToken (test-event-owner), otherOwnerToken (test-other-event-owner),
# adminToken (test-admin) and clientToken (test-client). The passwords come from the environment of the identity
# service in "docker compose config", which reaches the container on its standard input, so no password or token
# is on a command line of the host. A token lasts 60 s, far more than a collection takes. When a token request
# fails, the script stops with a message that names the username, and never prints a password or a token.
#
# Exit status: Bruno's (0 when every request and assertion passes), 2 for a usage error, a stopped gateway, an
# unreadable Compose configuration or a token that could not be obtained.
set -euo pipefail

readonly NODE_IMAGE="node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5"

# Reads "docker compose config --format json" on standard input, gets the access token of each test user from the
# API test client and runs Bruno in the collection named by its first argument, with the tokens as environment
# variables of the collection. It exits with Bruno's status, or with 2 and a message naming the username when a
# token cannot be obtained.
# shellcheck disable=SC2016 # JavaScript for node, not shell expansion
readonly RUN_WITH_TOKENS_PROGRAM='
const { spawnSync } = require("node:child_process");
const { readFileSync } = require("node:fs");

const TOKEN_URL = "http://localhost:8080/auth/realms/ticketera/protocol/openid-connect/token";
const TEST_USERS = [
  ["ownerToken", "test-event-owner", "TEST_USER_EVENT_OWNER_PASSWORD"],
  ["otherOwnerToken", "test-other-event-owner", "TEST_USER_OTHER_EVENT_OWNER_PASSWORD"],
  ["adminToken", "test-admin", "TEST_USER_ADMIN_PASSWORD"],
  ["clientToken", "test-client", "TEST_USER_CLIENT_PASSWORD"],
];

function stop(message) {
  console.error(`run.sh: ${message}`);
  process.exit(2);
}

async function accessToken(username, password) {
  const body = new URLSearchParams({
    grant_type: "password", client_id: "ticketera-api-tests", username, password, scope: "openid",
  });
  let response;
  try {
    response = await fetch(TOKEN_URL, { method: "POST", body });
  } catch (error) {
    stop(`no access token for ${username}: the token request failed (${error.cause?.code ?? error.message})`);
  }
  if (!response.ok) {
    stop(`no access token for ${username}: the identity service answered ${response.status}`);
  }
  const token = (await response.json()).access_token;
  if (typeof token !== "string" || token === "") {
    stop(`no access token for ${username}: the token response has none`);
  }
  return token;
}

async function main() {
  const environment = JSON.parse(readFileSync(0, "utf8")).services?.identity?.environment ?? {};
  const variables = [];
  for (const [variable, username, passwordVariable] of TEST_USERS) {
    const password = environment[passwordVariable];
    if (!password) {
      stop(`no access token for ${username}: ${passwordVariable} is not set for the identity service`);
    }
    variables.push("--env-var", `${variable}=${await accessToken(username, password)}`);
  }
  const bruno = spawnSync("../node_modules/.bin/bru", ["run", "--env", "local", ...variables],
    { cwd: process.argv[1], stdio: ["ignore", "inherit", "inherit"] });
  process.exit(bruno.status ?? 2);
}

main();
'

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repository_root=$(dirname "$(dirname "$script_dir")")
cd "$script_dir"
collection=${1:-}
if [[ -z $collection || ! -f "$collection/bruno.json" ]]; then
  collections=$(for dir in */; do [[ -f "$dir/bruno.json" ]] && printf '%s ' "${dir%/}"; done)
  echo "usage: tests/api/run.sh <collection>; collections: $collections" >&2
  exit 2
fi
gateway=$(cd "$repository_root" && docker compose ps --quiet gateway 2> /dev/null || true)
if [[ -z $gateway ]]; then
  echo "the gateway is not running: start the system with docker compose up -d --wait" >&2
  exit 2
fi
if ! compose_config=$(cd "$repository_root" && docker compose config --format json 2> /dev/null); then
  echo "docker compose config failed: run it from the repository root to see why" >&2
  exit 2
fi

printf '%s' "$compose_config" | docker run --rm -i --network "container:$gateway" --user "$(id -u):$(id -g)" \
  --env HOME=/tmp --volume "$PWD:/work" --workdir /work "$NODE_IMAGE" sh -c '
    npm ci --no-audit --no-fund --loglevel=error < /dev/null && node -e "$1" "$0"
  ' "$collection" "$RUN_WITH_TOKENS_PROGRAM"
