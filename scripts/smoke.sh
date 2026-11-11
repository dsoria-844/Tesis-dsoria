#!/usr/bin/env bash
# Prueba de humo de punta a punta (requiere Docker). Resultado: PASS / FALLO.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || ./scripts/init-env.sh
PASS="$(grep '^DEMO_PASSWORD=' .env | cut -d= -f2)"
echo "[1/5] Construyendo y levantando servicios…"
docker compose up -d --build
echo "[2/5] Esperando a la API…"
for i in $(seq 1 40); do
  docker compose exec -T api python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')" >/dev/null 2>&1 && break
  sleep 3
done
echo "[3/5] Creando usuarios de demostración…"
docker compose --profile tools run --rm seed
echo "[4/5] Cargando tráfico sintético y atacando de verdad al honeypot Cowrie (ráfaga + stuffing)…"
docker compose --profile demo run --rm replay
docker compose --profile attack run --rm attacker banner
docker compose --profile attack run --rm attacker rafaga
docker compose --profile attack run --rm attacker stuffing
echo "[5/5] Verificando alertas y sesiones por la API…"
docker compose exec -T api python -m hp.tools.smoke_check --user auditor@salta-test.local \
  --password "$PASS" --min-alertas 4 --min-sesiones 20 --timeout 180 && echo "PASS" || { echo "FALLO"; docker compose logs --tail=40 collector engine cowrie; exit 1; }
