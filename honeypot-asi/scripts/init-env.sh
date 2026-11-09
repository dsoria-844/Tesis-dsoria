#!/usr/bin/env bash
# Genera .env con contraseñas aleatorias (no pisa un .env existente).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then echo ".env ya existe; no se modifica."; exit 0; fi
rnd() { openssl rand -hex 18; }
cat > .env <<EOT
POSTGRES_DB=honeypot
POSTGRES_PASSWORD=$(rnd)
DB_OWNER_PASSWORD=$(rnd)
DB_INGEST_PASSWORD=$(rnd)
DB_ENGINE_PASSWORD=$(rnd)
DB_API_PASSWORD=$(rnd)
JWT_SECRET=$(openssl rand -hex 32)
LAB_RUNNER_TOKEN=$(openssl rand -hex 32)
DEMO_PASSWORD=Demo-$(openssl rand -hex 8)-asi
COWRIE_IMAGE=cowrie/cowrie@sha256:797d45ca8823d313bec0994232b982f3b99412d4e68e234608d6c1f78d32e3fe
EOT
chmod 600 .env
echo ".env creado. Contraseña de los usuarios de demostración: $(grep DEMO_PASSWORD .env | cut -d= -f2)"
