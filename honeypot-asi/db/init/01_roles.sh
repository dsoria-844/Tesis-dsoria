#!/bin/bash
# Crea los 4 roles de base de datos del principio de mínimo privilegio.
# Se ejecuta una sola vez, la primera vez que arranca el contenedor de PostgreSQL.
# Las contraseñas llegan por variables de entorno (ver .env.example).
set -euo pipefail

: "${DB_OWNER_PASSWORD:?falta DB_OWNER_PASSWORD}"
: "${DB_INGEST_PASSWORD:?falta DB_INGEST_PASSWORD}"
: "${DB_ENGINE_PASSWORD:?falta DB_ENGINE_PASSWORD}"
: "${DB_API_PASSWORD:?falta DB_API_PASSWORD}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v owner_pw="$DB_OWNER_PASSWORD" \
  -v ingest_pw="$DB_INGEST_PASSWORD" \
  -v engine_pw="$DB_ENGINE_PASSWORD" \
  -v api_pw="$DB_API_PASSWORD" <<'EOSQL'
-- db_owner: dueño de las tablas; solo se usa para migraciones y para crear usuarios iniciales.
CREATE ROLE db_owner     LOGIN PASSWORD :'owner_pw';
-- cowrie_ingest: colector. INSERT/SELECT sobre telemetría + cierre de sesión.
CREATE ROLE cowrie_ingest LOGIN PASSWORD :'ingest_pw';
-- asi_engine: motor ASI. SELECT telemetría, INSERT evaluaciones y alertas.
CREATE ROLE asi_engine   LOGIN PASSWORD :'engine_pw';
-- api_app: API REST. SELECT general + UPDATE restringido de alertas + autenticación.
CREATE ROLE api_app      LOGIN PASSWORD :'api_pw';

ALTER ROLE db_owner      SET search_path = honeypot;
ALTER ROLE cowrie_ingest SET search_path = honeypot;
ALTER ROLE asi_engine    SET search_path = honeypot;
ALTER ROLE api_app       SET search_path = honeypot;
EOSQL
