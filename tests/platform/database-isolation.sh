#!/usr/bin/env bash
# Database isolation test, run against the running database container with "docker compose exec".
#
# Usage: tests/platform/database-isolation.sh
#
# Run it after "docker compose up --wait", from any directory; set COMPOSE_FILE when the system was started with
# more than one file.
#
# Output: one line per scenario of the database-isolation spec, "PASS <scenario>" or "FAIL <scenario>: <reason>",
# then a summary line. Exit status: 0 when every scenario passes, 1 when any scenario fails.
#
# Every connection uses the local socket inside the database container, where the PostgreSQL image trusts local
# connections, so a rejected connection is a privilege check (CONNECT), never a password check. Each service role
# has the name of its database (DS-02). Statements that a scenario expects to be rejected run inside a transaction
# that is rolled back, or are undone right after, so the test leaves no state behind.
#
# The host needs only bash and docker (D-12).
#
# Change project-bootstrap, task 2.3 (design: platform/database-isolation, DS-02).

set -uo pipefail

# Service databases, each accessed by a role of the same name; the identity service uses "keycloak" (task 2.8).
readonly SERVICE_DATABASES=(catalog sales payments keycloak)
readonly PROBE_ROLE="isolation_probe_role_$$"
readonly PROBE_DATABASE="isolation_probe_db_$$"

cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

passed=0
failed=0
admin_role=""
unreachable_reason=""

pass() {
  printf 'PASS %s\n' "$1"
  passed=$((passed + 1))
}

fail() {
  printf 'FAIL %s: %s\n' "$1" "${2//$'\n'/ }"
  failed=$((failed + 1))
}

# Reports a scenario as failed when the database container could not be reached; succeeds in that case.
database_unreachable() {
  if [[ -n $unreachable_reason ]]; then
    fail "$1" "$unreachable_reason"
    return 0
  fi
  return 1
}

# Prints the arguments separated by "; ".
join_problems() {
  local joined=$1 problem
  shift
  for problem in "$@"; do
    joined+="; $problem"
  done
  printf '%s' "$joined"
}

# Runs SQL as a role on a database through the container's local socket and prints psql's output, including error
# and warning messages. Usage: run_sql <role> <database> <sql>
run_sql() {
  docker compose exec -T database psql -X -q -A -t -v ON_ERROR_STOP=1 -U "$1" -d "$2" -c "$3" 2>&1
}

# Runs SQL as the database administrator on the maintenance database.
run_admin_sql() {
  run_sql "$admin_role" postgres "$1"
}

# Succeeds when the SQL is rejected with a permission error; otherwise prints what happened instead.
# Usage: rejected_with_permission_error <role> <database> <sql>
rejected_with_permission_error() {
  local output
  if output=$(run_sql "$1" "$2" "$3"); then
    printf 'it was accepted'
    return 1
  fi
  if [[ $output == *"permission denied"* ]]; then
    return 0
  fi
  printf 'it failed without a permission error: %s' "$output"
  return 1
}

# Removes what an interrupted or failed scenario may have left; it runs on exit.
cleanup() {
  if [[ -z $unreachable_reason ]]; then
    run_admin_sql "DROP DATABASE IF EXISTS $PROBE_DATABASE" > /dev/null
    run_admin_sql "DROP ROLE IF EXISTS $PROBE_ROLE" > /dev/null
  fi
}

# Req database-isolation: Each service has its own logical database - Scenario: Databases after the first start
check_databases_exist() {
  local scenario="Databases after the first start" output database
  local -a missing=()
  database_unreachable "$scenario" && return
  if ! output=$(run_admin_sql "SELECT datname FROM pg_database"); then
    fail "$scenario" "the databases could not be listed: $output"
    return
  fi
  for database in "${SERVICE_DATABASES[@]}"; do
    if [[ $'\n'$output$'\n' != *$'\n'$database$'\n'* ]]; then
      missing+=("$database")
    fi
  done
  if ((${#missing[@]} == 0)); then
    pass "$scenario"
  else
    fail "$scenario" "missing databases: ${missing[*]}"
  fi
}

# Req database-isolation: Each service connects with its own role - Scenario: Service connects to its own database
# Every service role, not only that of catalog, connects to its database and creates a table there.
check_roles_create_tables() {
  local scenario="Service connects to its own database" database output
  local -a problems=()
  database_unreachable "$scenario" && return
  for database in "${SERVICE_DATABASES[@]}"; do
    if ! output=$(run_sql "$database" "$database" "BEGIN; CREATE TABLE isolation_probe (id integer); ROLLBACK;"); then
      problems+=("$database: $output")
    fi
  done
  if ((${#problems[@]} == 0)); then
    pass "$scenario"
  else
    fail "$scenario" "$(join_problems "${problems[@]}")"
  fi
}

# Req database-isolation: Each service connects with its own role - Scenario: Services do not share credentials
# Each service has its own role, which logs in with a password and is neither the administrator role nor a
# superuser. The passwords themselves cannot be compared, because PostgreSQL stores salted hashes.
check_distinct_roles() {
  local scenario="Services do not share credentials" output database name can_login has_password is_superuser
  local -a problems=() found=()
  database_unreachable "$scenario" && return
  if ! output=$(run_admin_sql "SELECT rolname, rolcanlogin, rolpassword IS NOT NULL, rolsuper FROM pg_authid"); then
    fail "$scenario" "the roles could not be listed: $output"
    return
  fi
  while IFS='|' read -r name can_login has_password is_superuser; do
    [[ " ${SERVICE_DATABASES[*]} " == *" $name "* ]] || continue
    found+=("$name")
    [[ $name != "$admin_role" ]] || problems+=("$name is the administrator role")
    [[ $can_login == t ]] || problems+=("$name cannot log in")
    [[ $has_password == t ]] || problems+=("$name has no password")
    [[ $is_superuser == f ]] || problems+=("$name is a superuser")
  done <<< "$output"
  for database in "${SERVICE_DATABASES[@]}"; do
    [[ " ${found[*]} " == *" $database "* ]] || problems+=("role $database does not exist")
  done
  if ((${#problems[@]} == 0)); then
    pass "$scenario"
  else
    fail "$scenario" "$(join_problems "${problems[@]}")"
  fi
}

# Checks that a role cannot connect to a database. Usage: expect_connection_rejected <scenario> <role> <database>
expect_connection_rejected() {
  local scenario=$1 role=$2 database=$3 reason
  database_unreachable "$scenario" && return
  if reason=$(rejected_with_permission_error "$role" "$database" "SELECT 1"); then
    pass "$scenario"
  else
    fail "$scenario" "$role connecting to $database: $reason"
  fi
}

# Req database-isolation: A service cannot access another service's database - Scenario: Role with no explicit
# grant
check_role_without_grants() {
  local scenario="Role with no explicit grant" output database reason
  local -a problems=()
  database_unreachable "$scenario" && return
  if ! output=$(run_admin_sql "CREATE ROLE $PROBE_ROLE LOGIN"); then
    fail "$scenario" "the probe role could not be created: $output"
    return
  fi
  for database in "${SERVICE_DATABASES[@]}"; do
    if ! reason=$(rejected_with_permission_error "$PROBE_ROLE" "$database" "SELECT 1"); then
      problems+=("connecting to $database: $reason")
    fi
  done
  run_admin_sql "DROP ROLE $PROBE_ROLE" > /dev/null
  if ((${#problems[@]} == 0)); then
    pass "$scenario"
  else
    fail "$scenario" "$(join_problems "${problems[@]}")"
  fi
}

# Req database-isolation: A service role cannot grant access to its database - Scenario: Catalog role grants access
# to the sales role
check_grant_by_service_role() {
  local scenario="Catalog role grants access to the sales role" output privilege reason
  database_unreachable "$scenario" && return
  if ! output=$(run_sql catalog catalog "GRANT CONNECT ON DATABASE catalog TO sales") && [[ $output == *FATAL* ]]; then
    fail "$scenario" "the catalog role could not connect to run the grant: $output"
    return
  fi
  if ! privilege=$(run_admin_sql "SELECT has_database_privilege('sales', 'catalog', 'CONNECT')"); then
    fail "$scenario" "the privileges of sales could not be read: $privilege"
    return
  fi
  if [[ $privilege == t ]]; then
    run_admin_sql "REVOKE CONNECT ON DATABASE catalog FROM sales" > /dev/null
    fail "$scenario" "sales has CONNECT on catalog after the grant by catalog (revoked again by the test)"
    return
  fi
  if reason=$(rejected_with_permission_error sales catalog "SELECT 1"); then
    pass "$scenario"
  else
    fail "$scenario" "sales connecting to catalog after the grant: $reason"
  fi
}

# Checks that the sales role cannot run a statement. Usage: expect_sales_rejected <scenario> <sql>
expect_sales_rejected() {
  local scenario=$1 sql=$2 reason
  database_unreachable "$scenario" && return
  if reason=$(rejected_with_permission_error sales sales "$sql"); then
    pass "$scenario"
  else
    fail "$scenario" "sales running '$sql': $reason"
  fi
}

# Req database-isolation: Service roles have no administrative privileges - Scenario: Service role tries to install
# a cross-database extension
check_create_extensions() {
  local scenario="Service role tries to install a cross-database extension" extension reason
  local -a problems=()
  database_unreachable "$scenario" && return
  for extension in dblink postgres_fdw; do
    if ! reason=$(rejected_with_permission_error sales sales "BEGIN; CREATE EXTENSION $extension; ROLLBACK;"); then
      problems+=("sales installing $extension: $reason")
    fi
  done
  if ((${#problems[@]} == 0)); then
    pass "$scenario"
  else
    fail "$scenario" "$(join_problems "${problems[@]}")"
  fi
}

main() {
  if ! admin_role=$(docker compose exec -T database printenv POSTGRES_USER 2>&1) || [[ -z $admin_role ]]; then
    unreachable_reason="the database container is not reachable with docker compose exec: ${admin_role:-no output}"
  fi
  trap cleanup EXIT

  check_databases_exist
  check_roles_create_tables
  check_distinct_roles

  # Req database-isolation: A service cannot access another service's database - Scenario: Role of one service
  # connects to another service's database
  expect_connection_rejected "Role of one service connects to another service's database" catalog sales

  # Req database-isolation: A service cannot access another service's database - Scenario: Role of the identity
  # service connects to a backend service's database
  expect_connection_rejected "Role of the identity service connects to a backend service's database" \
    keycloak payments

  check_role_without_grants
  check_grant_by_service_role

  # Req database-isolation: Service roles have no administrative privileges - Scenario: Service role tries to
  # create a database
  expect_sales_rejected "Service role tries to create a database" "CREATE DATABASE $PROBE_DATABASE"

  # Req database-isolation: Service roles have no administrative privileges - Scenario: Service role tries to
  # create a role
  expect_sales_rejected "Service role tries to create a role" "BEGIN; CREATE ROLE $PROBE_ROLE; ROLLBACK;"

  check_create_extensions

  printf 'Database isolation: %d passed, %d failed\n' "$passed" "$failed"
  ((failed == 0))
}

main "$@"
