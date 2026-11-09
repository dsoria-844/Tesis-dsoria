# Contexto del proyecto (leer primero)

Prototipo de un Trabajo Final de Grado (Lic. en Seguridad Informática, Univ. Siglo 21): "Sistema de detección y análisis de ataques automatizados mediante señuelos de seguridad". Honeypot Cowrie + Índice de Severidad de Ataque (ASI) + API FastAPI + panel React + PostgreSQL 16. El usuario habla español (Argentina): respondé en español.

**La entrega es hoy.** Prioridad: que el stack Docker levante y `scripts/smoke.sh` pase en macOS (Docker Desktop). Lo demás ya está hecho y probado.

## Qué ya está verificado (en un sandbox Linux, sin Docker)
- 63 tests de pytest pasan contra PostgreSQL 16 real (parser, ingesta idempotente, motor ASI, API, evaluación).
- Collector + engine + API + web corriendo juntos (sin Docker) generaron las 4 alertas esperadas con datos de demo.
- `npm run build` del frontend funciona.

## Qué NO se pudo probar y hay que verificar acá
Todo lo que depende de Docker y de la imagen real de Cowrie:
1. Que la imagen (`COWRIE_IMAGE` en `.env`) arranque y escriba `cowrie.json` en `/cowrie/cowrie-git/var/log/cowrie`.
2. Variable de entorno para habilitar Telnet (`COWRIE_TELNET_ENABLED`) y ruta de `userdb.txt` según la versión de la imagen.
3. Permisos del tmpfs de descargas y nombre del sensor (hostname → `sensores.nombre`).
4. Contenedores atacantes (`tools/attacker`, paramiko) y el proxy nginx del servicio `web`.
5. Una vez funcionando, **fijar la versión de la imagen de Cowrie** en `.env` (riesgo R5), no dejar `latest`.

Si falla algo, diagnosticá con `docker compose logs <servicio>` y corregí `docker-compose.yml`, `cowrie/` o los Dockerfile. Después volvé a correr `./scripts/smoke.sh`.

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
```
Panel: http://127.0.0.1:8080 · usuarios de demo `auditor@`, `responsable@`, `admin@salta-test.local` (clave = `DEMO_PASSWORD` del `.env`).

## Reglas al trabajar
- Cambios mínimos y localizados; no reescribir lo que ya pasa los tests.
- Después de tocar código, correr los tests (`docker compose --profile test run --rm tests`).
- No exponer el honeypot a Internet; es solo laboratorio.
- Al terminar, resumir qué se arregló y qué sigue pendiente.
