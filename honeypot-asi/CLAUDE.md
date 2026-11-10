# Contexto del proyecto (leer primero)

Prototipo de un Trabajo Final de Grado (Lic. en Seguridad Informática, Univ. Siglo 21): "Sistema de detección y análisis de ataques automatizados mediante señuelos de seguridad". Honeypot Cowrie + Índice de Severidad de Ataque (ASI) + API FastAPI + panel React + PostgreSQL 16. El usuario habla español (Argentina): respondé en español.

## Estado actual
- El TFG ya se entregó (noviembre de 2026). Ahora se mejora el sistema de forma incremental, sin cambiar su comportamiento salvo pedido explícito.
- Stack verificado en macOS (Docker Desktop): `scripts/smoke.sh` pasa. Cowrie fijado por digest (v3.1.5) en `docker-compose.yml`.
- Backend: 131 tests de pytest contra una base de prueba efímera (`test-db`), separada de la base real.
- Frontend (`services/web`): organizado por funcionalidad (`src/app`, `src/shared`, `src/features/<nombre>` con su página, `api.ts` y `types.ts`), con ESLint, Prettier y 65 tests de Vitest.
- Laboratorio de ataques: perfil `lab` (`lab-runner` en la red interna `labctl`, con token). Nunca montar el socket de Docker.

Si algo falla, diagnosticá con `docker compose logs <servicio>` y volvé a correr `./scripts/smoke.sh`.

## Decisiones de diseño que NO hay que cambiar
- ASI(IP) = 0,25·F + 0,30·V + 0,20·D + 0,25·P; normalización por saturación con N_ref=100, r_ref=1/s, K_ref=20; F=0 si hay menos de 5 intentos; ventanas de 15 y 60 min (se conserva el máximo). Umbrales: BAJA < 0,40; MEDIA 0,40–0,69; CRITICA ≥ 0,70 (se clasifica con el valor redondeado a 3 decimales).
- Alertas solo con ASI ≥ 0,70; enfriamiento de 3600 s por IP mientras la alerta esté NUEVA/EN_REVISION; re-alerta si el ASI sube ≥ 0,10.
- Base: esquema `honeypot`, 4 roles de mínimo privilegio (db_owner, cowrie_ingest, asi_engine, api_app) con GRANT por columna; tablas de telemetría de solo inserción; historial de alertas por trigger.
- Ingesta idempotente: `evento_uid` = SHA-256 de la línea + `ON CONFLICT DO NOTHING`; checkpoint (archivo, inode, offset) en la misma transacción.
- Red Docker `honeynet` interna sin salida a Internet para Cowrie, sinkhole y atacantes. Los atacantes de prueba son contenedores propios (en Docker Desktop macOS las conexiones desde el host pierden la IP de origen).
- Severidad en la base: `CRITICA` sin tilde. Puertos de Cowrie en el host: 2222 (SSH) y 2223 (Telnet).

## Limitaciones honestas (no maquillar)
- La evaluación (`resultados/`) usa datos sintéticos separables; el F1 casi perfecto no demuestra desempeño con tráfico real.
- No implementado: TOTP, VPN, backups automáticos (solo diseño).

## Comandos útiles
```
./scripts/init-env.sh                       # genera .env con contraseñas aleatorias
docker compose up -d --build
docker compose --profile tools run --rm seed
./scripts/demo.sh                           # reproduce un log de demo
./scripts/smoke.sh                          # prueba de humo del stack
docker compose --profile test run --rm tests
docker compose --profile tools run --rm evaluate
docker compose --profile lab up -d          # laboratorio de ataques (lab-runner)

cd services/web                             # frontend
npm test && npm run lint && npm run typecheck && npm run format:check && npm run build
```
Panel: http://127.0.0.1:8080 · usuarios de demo `auditor@`, `responsable@`, `admin@salta-test.local` (clave = `DEMO_PASSWORD` del `.env`).

## Reglas al trabajar
- Cambios mínimos y localizados; no reescribir lo que ya pasa los tests.
- Después de tocar código, correr los tests (`docker compose --profile test run --rm tests` y, si cambió el frontend, los comandos de `services/web`).
- Trabajar en una rama y abrir PR contra `main`; commits convencionales, sin líneas de atribución de IA.
- Nunca commitear `.env` (tiene secretos).
- No exponer el honeypot a Internet; es solo laboratorio.
- Al terminar, resumir qué se arregló y qué sigue pendiente.
