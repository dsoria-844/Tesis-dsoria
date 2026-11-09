# Tesis-dsoria

Trabajo Final de Grado — Licenciatura en Seguridad Informática, Universidad Siglo 21.

**Sistema de detección y análisis de ataques automatizados mediante señuelos de seguridad.**

Un honeypot ([Cowrie](https://github.com/cowrie/cowrie)) registra los ataques automatizados contra SSH y Telnet; un motor calcula para cada IP de origen el **Índice de Severidad de Ataque (ASI)** y genera alertas solo para la actividad crítica, para reducir la fatiga de alertas del analista.

```
ASI(IP) = 0,25·F + 0,30·V + 0,20·D + 0,25·P      (frecuencia, volumen, diversidad, persistencia)
BAJA < 0,40 · MEDIA 0,40–0,69 · CRÍTICA ≥ 0,70   (ventanas de 15 y 60 min, se conserva el máximo)
```

## Contenido

| Carpeta | Qué es |
|---|---|
| [`honeypot-asi/`](honeypot-asi/) | Prototipo funcional: Cowrie · PostgreSQL 16 · FastAPI · React + TypeScript, desplegado con Docker Compose en una red de laboratorio aislada. |

## Prototipo en una mirada

- **Captura:** Cowrie (SSH 2222, Telnet 2223) en una red Docker interna sin salida a Internet.
- **Ingesta idempotente:** cada línea del log se identifica por SHA-256 y se guarda una sola vez, con checkpoint.
- **Base de datos:** esquema `honeypot` con 4 roles de mínimo privilegio y tablas de telemetría de solo inserción.
- **Motor ASI:** recalcula cada 30 s, alerta con ASI ≥ 0,70 y no repite alertas de la misma IP durante 1 h.
- **Panel web:** actividad reciente, detalle por IP con el ASI desglosado, sesiones con reproducción, alertas y su historial, perfil de usuario.
- **Laboratorio de ataques:** escenarios de la tesis (script propio, Nmap, Hydra, Telnet) lanzables desde el panel, sin acceso al socket de Docker.
- **Calidad:** 131 tests contra PostgreSQL real y una prueba de humo de punta a punta (`scripts/smoke.sh`).

## Inicio rápido

Requisitos: Docker Desktop (4 GB de RAM o más) y los puertos 8080, 2222 y 2223 libres.

```bash
cd honeypot-asi
./scripts/init-env.sh                              # genera .env con contraseñas aleatorias
docker compose up -d --build
docker compose --profile tools run --rm seed       # usuarios de demostración
docker compose --profile lab up -d lab-runner      # opcional: laboratorio de ataques
```

Panel: http://127.0.0.1:8080 · Documentación detallada, escenarios de ataque, tests y limitaciones en [`honeypot-asi/README.md`](honeypot-asi/README.md).

> **Solo laboratorio.** No exponer el honeypot a Internet.

## Limitaciones

- La evaluación usa datos sintéticos: el F1 casi perfecto no demuestra el desempeño con tráfico real.
- No implementado (solo diseño): TOTP, VPN y copias de seguridad automáticas.
