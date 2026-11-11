#!/usr/bin/env bash
# Levanta todo, crea los usuarios de demostración y carga tráfico sintético reciente.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || ./scripts/init-env.sh
docker compose up -d --build
docker compose --profile tools run --rm seed
docker compose --profile demo run --rm replay
echo
echo "Listo. Abrí http://localhost:8080  (el motor ASI procesa cada 30 s; esperá ~1 minuto)."
echo "Usuarios: auditor@salta-test.local | responsable@salta-test.local | admin@salta-test.local"
echo "Contraseña: $(grep DEMO_PASSWORD .env | cut -d= -f2)"
