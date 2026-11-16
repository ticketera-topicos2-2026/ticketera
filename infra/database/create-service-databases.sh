#!/usr/bin/env bash
# Creates one database and one role for each bootstrap service (Req database-isolation; DS-02, DS-03).
#
# The PostgreSQL image entrypoint runs it as the postgres user, only when the data volume is empty; a change to
# this script reaches an existing environment only after "docker compose down -v".
#
# The database and the role of each service have the service's name, and the role's password comes from the
# environment variable <SERVICE>_DB_PASSWORD (for example CATALOG_DB_PASSWORD), set in .env. Each service connects
# with DATABASE_URL=postgresql+psycopg://<service>:<password>@database:5432/<service>.
#
# Each database is owned by the administrator (POSTGRES_USER), not by its service role, so the role cannot grant
# access to it. The role gets CONNECT and TEMPORARY on its database, owns its public schema (so it can run
# migrations) and has no administrative privilege. CONNECT is revoked from PUBLIC, so no other role connects.
#
# psql reads the password from the environment (\getenv) and quotes it as a literal (:'password'): it never
# appears on a command line and is never concatenated into the SQL text.
#
# Change project-bootstrap, task 2.8 (tests: tests/platform/database-isolation.sh, task 2.3).

set -euo pipefail

# Services that store data; the identity service uses "keycloak".
readonly SERVICES=(catalog sales payments keycloak)

# Prints the name of the environment variable that holds the password of a service role.
password_variable() {
  printf '%s_DB_PASSWORD' "${1^^}"
}

# Exits with an error naming the variable when the password of a service role is missing or empty.
require_password() {
  local variable=$1
  if [[ -z ${!variable:-} ]]; then
    printf 'create-service-databases: %s is missing or empty; set it in .env\n' "$variable" >&2
    exit 1
  fi
}

# Creates the role and the database of one service and grants the role access to its database only.
create_service_database() {
  local service=$1 variable
  variable=$(password_variable "$service")
  require_password "$variable"
  psql --no-psqlrc --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    --set=service="$service" --set=password_variable="$variable" <<'SQL'
\getenv password :password_variable
CREATE ROLE :"service" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'password';
CREATE DATABASE :"service";
REVOKE ALL ON DATABASE :"service" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"service" TO :"service";
\connect :"service"
ALTER SCHEMA public OWNER TO :"service";
SQL
}

main() {
  local service
  for service in "${SERVICES[@]}"; do
    create_service_database "$service"
    printf 'create-service-databases: created the database and the role %s\n' "$service"
  done
}

main
