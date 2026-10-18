#!/usr/bin/env bash
# Runs the Flyway CLI from its Docker image against the database in DB_* env vars.
# Usage: scripts/flyway.sh migrate | info | validate | migrate -target=2
# Extra migration folders (comma separated, relative to the repo) can be added with
# FLYWAY_EXTRA_LOCATIONS; only the break-it drill uses this.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-shop}"
DB_USER="${DB_USER:-app}"
DB_PASSWORD="${DB_PASSWORD:-apppw}"
FLYWAY_IMAGE="${FLYWAY_IMAGE:-flyway/flyway:10}"
# The Flyway container reaches MySQL over the host network by default (Linux, CI).
# On Docker Desktop use the compose network instead:
#   FLYWAY_NETWORK=mysql-release-pipeline_default FLYWAY_DB_HOST=mysql make migrate
FLYWAY_NETWORK="${FLYWAY_NETWORK:-host}"
FLYWAY_DB_HOST="${FLYWAY_DB_HOST:-$DB_HOST}"

locations="filesystem:/flyway/sql"
mounts=(-v "$ROOT/db/migrations:/flyway/sql:ro")
IFS=',' read -ra extra <<< "${FLYWAY_EXTRA_LOCATIONS:-}"
for i in "${!extra[@]}"; do
  mounts+=(-v "$ROOT/${extra[$i]}:/flyway/extra$i:ro")
  locations="$locations,filesystem:/flyway/extra$i"
done

exec docker run --rm --network "$FLYWAY_NETWORK" "${mounts[@]}" "$FLYWAY_IMAGE" \
  -url="jdbc:mysql://${FLYWAY_DB_HOST}:${DB_PORT}/${DB_NAME}?allowPublicKeyRetrieval=true&useSSL=false" \
  -user="$DB_USER" -password="$DB_PASSWORD" \
  -locations="$locations" \
  -validateMigrationNaming=true \
  "$@"
