# Guía técnica del prototipo

Sistema de detección y análisis de ataques automatizados con señuelos (Cowrie) e Índice de Severidad de Ataque (ASI).
Stack: Cowrie · PostgreSQL 16 · Python/FastAPI · React + TypeScript.

> **Solo laboratorio.** Todo corre en una red Docker interna sin salida a Internet. No exponer el honeypot a Internet.

## Estado de verificación

| Parte | Estado |
|---|---|
| Parser, ingesta idempotente, motor ASI, API, evaluación, laboratorio, perfil | 131 tests OK contra PostgreSQL 16 real (base efímera propia, `test-db`) |
| Stack Docker completo en macOS (Cowrie real, red aislada, nginx, atacantes) | Verificado: `scripts/smoke.sh` → PASS (incluye una alerta CRÍTICA generada por un ataque real contra Cowrie) |
| Imagen de Cowrie | Fijada por digest (v3.1.5) en `.env.example`, `init-env.sh` y `docker-compose.yml` (riesgo R5) |
| Frontend | Organizado por funcionalidad; ESLint + Prettier sin errores y 65 tests de Vitest OK; `npm run build` verificado dentro de la imagen `web` |

## Requisitos (macOS)

- Docker Desktop (4 GB de RAM o más asignados).
- Puertos libres: 8080 (web), 2222 y 2223 (Cowrie, solo en 127.0.0.1).

## Puesta en marcha

```bash
git clone https://github.com/dsoria-844/Tesis-dsoria.git
cd Tesis-dsoria
./scripts/init-env.sh              # genera .env con contraseñas aleatorias
docker compose up -d --build
docker compose --profile tools run --rm seed     # crea usuarios de demo
```

Abrí http://127.0.0.1:8080. Usuarios de demo (clave = `DEMO_PASSWORD` del `.env`):

- `auditor@salta-test.local`
- `responsable@salta-test.local`
- `admin@salta-test.local`

Documentación de la API: http://127.0.0.1:8080/docs.

Si en lugar de clonar descargaste un zip, antes de `init-env.sh` corré `xattr -dr com.apple.quarantine .` y `chmod +x scripts/*.sh db/init/01_roles.sh` (ver Notas de macOS).

## Demo rápida (reproducción de un log de ejemplo)

```bash
./scripts/demo.sh
```

Genera un log con 4 IPs de comportamiento crítico y otras de fondo, y lo reproduce. En 1–2 minutos aparecen 4 alertas en el panel.

## Ataques reales contra el honeypot

Los atacantes son contenedores propios dentro de la red interna (en Docker Desktop macOS las conexiones desde el host pierden la IP de origen).

```bash
docker compose --profile attack run --rm attacker banner
docker compose --profile attack run --rm attacker rafaga
docker compose --profile attack run --rm attacker stuffing
docker compose --profile attack run --rm attacker persistente
docker compose --profile attack run --rm attacker sigilosa   # low and slow, ~1 h
```

Con Hydra o Nmap, usá la misma red (`honeynet`) y apuntá al servicio `cowrie`, puerto 2222 (SSH) o 2223 (Telnet).

## Laboratorio de ataques desde el panel

Pestaña "Laboratorio" (solo perfil Administrador de Infraestructura): lanza y detiene los escenarios de ataque (script propio `attack.py`, Nmap y Hydra) sin usar la terminal. Está **apagada por defecto**; para habilitarla:

```bash
docker compose --profile lab up -d --build lab-runner
```

Escenarios disponibles y su relación con el trabajo:

| Escenario | Herramienta | Parámetros | Tesis | ASI esperado |
|---|---|---|---|---|
| `banner`, `manual` | `attack.py` (paramiko) | intentos, tasa | Casos de uso de baja actividad | BAJA |
| `rafaga`, `persistente` | `attack.py` | intentos, tasa | Casos de uso de actividad media/sostenida | MEDIA / CRÍTICA |
| `stuffing` | `attack.py` | intentos, tasa | Credential stuffing | CRÍTICA |
| `sigilosa` | `attack.py` | intentos (ritmo fijo 20–40 s) | Low and slow | MEDIA (15 min) / CRÍTICA (60 min) |
| `nmap-reconocimiento` | `nmap -n -sT -sV -Pn -p 2222,2223 cowrie` | ninguno | Escenario 1: Nmap + banner grabbing en SSH y Telnet | BAJA |
| `hydra-stuffing` | `hydra -t N -C combos.txt ssh://cowrie:2222` | intentos, tareas (1–8) | Escenario 3: stuffing de alta velocidad con diccionario tipo filtración | CRÍTICA |
| `hydra-sigilosa` | `hydra -t 1 -c 30 -C combos.txt ssh://cowrie:2222` | intentos (ritmo fijo ~30 s) | Escenario 2: fuerza bruta lenta (20–40 s entre intentos) | MEDIA (15 min) / CRÍTICA (60 min) |
| `telnet-fuerza-bruta` | `hydra -t N -C combos.txt telnet://cowrie:2223` | intentos, tareas (1–8) | Cobertura de Telnet | CRÍTICA con suficientes intentos |

Notas: Nmap usa escaneo TCP connect (`-sT`) porque el contenedor no tiene capacidad de sockets raw y `-Pn` evita el descubrimiento ARP; un escaneo SYN que no completa el handshake no llega a Cowrie (corrección de la tesis). Hydra no usa `-f`: si Cowrie acepta alguna credencial de `cowrie/userdb.txt` se informa pero la corrida continúa. Hydra y Nmap no emiten progreso propio: el panel muestra el avance de Hydra a partir de las líneas `[ATTEMPT]` (intentos iniciados) y "En ejecución" para Nmap.

Por qué es seguro:

- **Sin socket de Docker**: la API no controla contenedores. Habla con un servicio propio (`lab-runner`) que solo ejecuta una lista cerrada de escenarios contra `cowrie` (2222 SSH, 2223 Telnet); el cliente nunca envía comandos ni hosts, solo enteros acotados.
- **Red de control separada**: `labctl` es interna y la comparten únicamente `api` y `lab-runner`. El runner no está en `backend` y su puerto de control escucha solo en la dirección de `labctl`, por lo que Cowrie (en `honeynet`) no lo alcanza.
- **Secreto compartido**: cada pedido lleva `X-Lab-Token` (`LAB_RUNNER_TOKEN` en `.env`, generado por `init-env.sh`).
- **Un solo perfil y una sola ejecución**: solo `ADMIN_INFRA`; un único ataque a la vez, con parámetros acotados (intentos 1–2000, tasa 0,1–20/s, tareas Hydra 1–8), con tope de 2 h por ejecución. Al detener se mata todo el grupo de procesos (Hydra/Nmap incluidos). Cada inicio/detención queda en `accesos_log`.
- Si el servicio no está levantado, el panel lo indica y no ocurre nada más.

## Mi perfil, limpiar vista y reiniciar laboratorio

En la barra superior, el avatar abre **Mi perfil** (todos los roles), el ícono de salida cierra la sesión y el botón de tema alterna entre modo claro y oscuro (se recuerda en el navegador). Allí se ven los datos de la cuenta, los últimos 10 accesos propios (`GET /api/v1/me/accesos`) y:

- **Limpiar mi vista de actividad reciente**: oculta, solo para ese usuario y en ese navegador (`localStorage`), la actividad anterior a ese momento en el panel y en `/actividad` (parámetro `desde` de `GET /api/v1/metrics/live`). **No borra datos**; "Restablecer vista" la revierte.
- **Reiniciar laboratorio** (solo `ADMIN_INFRA`, solo laboratorio): borra de verdad sesiones, intentos, comandos, evaluaciones ASI, alertas y su historial para una demo limpia. Conserva usuarios, `accesos_log`, sensores y `ingesta_checkpoint` (si no, el colector reimportaría todo `cowrie.json`). Exige escribir `REINICIAR` y deja una fila `LAB_REINICIO` en `accesos_log`. Se implementa con la función SQL `honeypot.reiniciar_laboratorio` (`db/init/03_lab_reset.sql`, `SECURITY DEFINER`, ejecutable solo por `api_app`), sin darle DELETE/TRUNCATE a ningún rol. Al terminar emite `pg_notify('hp_lab_reset')` y el colector, que escucha ese canal, vacía sus cachés en el momento: no hace falta reiniciar el contenedor (la API no tiene acceso al socket de Docker, a propósito). El `TRUNCATE` no dispara los triggers de solo inserción, por eso queda documentado y auditado. La API lo habilita con `LAB_RESET_ENABLED` (por defecto `true` en este `docker-compose.yml`; **en producción debe ser `false`**, valor por defecto de la aplicación). En un volumen de PostgreSQL ya creado, aplicar el script una vez: `docker compose exec -T db psql -U postgres -d honeypot -f - < db/init/03_lab_reset.sql`.

El gráfico "Ataques en el tiempo" tiene su propio selector (Minuto, Hora, Día, 3 días, 5 días) y usa `GET /api/v1/metrics/serie?vista=...&tz=...`, que devuelve todos los intervalos, también los vacíos.

## Verificación automática

```bash
./scripts/smoke.sh        # levanta el stack, ataca y comprueba que se generan sesiones y alertas
```

Si falla, revisá `docker compose logs collector engine cowrie`.

## Evaluación del motor ASI

```bash
docker compose --profile tools run --rm evaluate
```

Genera `informe.md`, `resultados.json` y `barrido_umbral.csv` en `resultados/` (semilla 42). La carpeta está versionada junto con las capturas del panel usadas en el documento (`resultados/capturas/`, Figuras 4 a 9).

## Tests

```bash
docker compose --profile test run --rm tests     # backend: 131 tests contra una base efímera (test-db)
```

## Frontend

`services/web/src` está organizado por funcionalidad:

```
app/        estructura general, navegación, autenticación y tema
shared/     cliente HTTP, componentes visuales, formateo, hooks
features/   una carpeta por pantalla (dashboard, actividad, sesiones, alertas, ips,
            laboratorio, usuarios, perfil, login), cada una con su página, api.ts y types.ts
```

Comandos (requieren Node 22 o superior, dentro de `services/web`):

```bash
npm ci
npm test                 # Vitest + Testing Library
npm run lint             # ESLint
npm run typecheck        # tsc --noEmit
npm run format:check     # Prettier (npm run format para aplicar)
npm run build
```

## Cómo contribuir

- Trabajar en una rama y abrir un PR contra `main`; commits con formato convencional (`feat:`, `fix:`, `docs:`...).
- Antes del PR, correr los tests del backend y, si cambió el frontend, los comandos de la sección anterior.
- Nunca commitear `.env` (contiene contraseñas y el token del laboratorio).

## Correspondencia con el documento

| Historia / tarea | Código |
|---|---|
| Ingesta de eventos Cowrie | `services/app/hp/collector/` |
| Modelo de datos y roles | `db/init/01_roles.sh`, `db/init/02_schema.sql` |
| Cálculo del ASI y alertas | `services/app/hp/engine/` |
| API REST, autenticación, RBAC | `services/app/hp/api/` |
| Dashboard, sesiones, alertas, usuarios | `services/web/src/features/` |
| Evaluación (matriz de confusión, pesos, umbral) | `services/app/hp/evaluation/` |
| Despliegue aislado | `docker-compose.yml` |

## Desvíos respecto del documento (reflejar en el texto)

- Marcas de tiempo en `TIMESTAMPTZ`.
- Nivel de severidad `CRITICA` en ASCII (sin tilde) en la base.
- `puerto_origen` admite NULL.
- Columnas adicionales: `evento_uid`, `ingresado_en`, `tipo_evento`, `url_descarga`, `hash_descarga_sha256`, `n_intentos`, `k_pares_distintos`, `latencia_ms`.
- Puertos de Cowrie 2222/2223 en el host.
- El corpus de evaluación tiene ~203 mil intentos (el documento menciona 30–50 mil).
- Escenario 1: Nmap usa escaneo por conexión completa (`-sT`); un escaneo SYN sin handshake no llega a Cowrie y el contenedor no tiene sockets raw.
- Escenario 2: Hydra espera 30 s fijos entre intentos (no permite intervalos aleatorios); el script propio (`sigilosa`) usa 20–40 s.
- Escenario 3: se usa el diccionario propio del proyecto (estilo filtración), no RockYou.
- El historial de alertas es inmutable para los roles de la aplicación; la única excepción es el reinicio del laboratorio (auditado, `LAB_RESET_ENABLED=false` en producción).

## Limitaciones (decirlas en la defensa)

- La evaluación usa **datos sintéticos separables**: el F1 casi perfecto no demuestra desempeño con tráfico real de Internet.
- **No implementado:** TOTP, VPN, copias de seguridad automáticas (la política de backups es solo diseño).
- La latencia "log → base" excluye reproducciones históricas; solo mide ingesta en vivo.

## Notas de macOS

- Al descomprimir un zip (no al clonar con git), macOS quita el permiso de ejecución y agrega cuarentena: por eso los comandos `xattr` y `chmod` indicados en la puesta en marcha. Sin ellos `db/init/01_roles.sh` no corre y la base queda sin roles.
- Si la base se inicializó mal, hay que recrear el volumen (`docker compose down && docker volume rm honeypot-asi_pgdata`): los scripts de `db/init/` solo corren con el volumen vacío.
- Docker Desktop hace que todas las conexiones desde el host lleguen con la misma IP (`172.18.0.1`): el bloqueo por IP del login (5 fallos en 15 min) afecta a todos los usuarios del navegador a la vez.
- Si `git` responde que falta aceptar la licencia de Xcode, correr una vez `sudo xcodebuild -license accept` (o usar el git de Homebrew).
