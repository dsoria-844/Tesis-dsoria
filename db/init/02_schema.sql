-- =====================================================================
-- Esquema relacional del sistema de detección con honeypot (Cowrie) + ASI
-- PostgreSQL 16. Todas las marcas de tiempo se almacenan en UTC (TIMESTAMPTZ).
-- Se ejecuta como superusuario en el arranque inicial; los objetos
-- quedan a nombre de db_owner.
-- =====================================================================
CREATE SCHEMA honeypot AUTHORIZATION db_owner;
SET ROLE db_owner;
SET search_path = honeypot;

-- ---------------------------------------------------------------------
-- 1. sensores
-- ---------------------------------------------------------------------
CREATE TABLE sensores (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre            VARCHAR(50)  NOT NULL UNIQUE,
    ip_interna        INET         NOT NULL,
    protocolo_emulado VARCHAR(20)  NOT NULL DEFAULT 'HÍBRIDO'
                      CHECK (protocolo_emulado IN ('SSH', 'TELNET', 'HÍBRIDO')),
    estado            VARCHAR(15)  NOT NULL DEFAULT 'ACTIVO'
                      CHECK (estado IN ('ACTIVO', 'INACTIVO', 'MANTENIMIENTO')),
    fecha_creacion    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 2. sesiones (una conexión TCP por fila)
-- puerto_origen es NULL si la sesión se reconstruyó a partir de eventos
-- posteriores (el colector arrancó con la sesión ya abierta).
-- ---------------------------------------------------------------------
CREATE TABLE sesiones (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sensor_id          UUID        NOT NULL REFERENCES sensores(id),
    session_cowrie_id  VARCHAR(32) NOT NULL UNIQUE,
    ip_origen          INET        NOT NULL,
    puerto_origen      INTEGER     CHECK (puerto_origen BETWEEN 1 AND 65535),
    protocolo          VARCHAR(10) NOT NULL CHECK (protocolo IN ('SSH', 'TELNET')),
    fecha_inicio       TIMESTAMPTZ NOT NULL,
    fecha_fin          TIMESTAMPTZ,
    duracion_segundos  INTEGER     CHECK (duracion_segundos >= 0)
);
CREATE INDEX idx_sesiones_ip      ON sesiones (ip_origen);
CREATE INDEX idx_sesiones_inicio  ON sesiones (fecha_inicio DESC);

-- ---------------------------------------------------------------------
-- 3. intentos_login
-- evento_uid = SHA-256 de la línea JSON original: hace la ingesta idempotente.
-- ingresado_en = momento en que el colector insertó la fila (mide latencia).
-- ---------------------------------------------------------------------
CREATE TABLE intentos_login (
    id                BIGSERIAL PRIMARY KEY,
    sesion_id         UUID         NOT NULL REFERENCES sesiones(id),
    evento_uid        CHAR(64)     NOT NULL UNIQUE,
    timestamp_evento  TIMESTAMPTZ  NOT NULL,
    usuario_ensayado  VARCHAR(100) NOT NULL,
    password_ensayado VARCHAR(255),
    autenticado       BOOLEAN      NOT NULL,
    ingresado_en      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_intentos_ts     ON intentos_login (timestamp_evento DESC);
CREATE INDEX idx_intentos_sesion ON intentos_login (sesion_id);

-- ---------------------------------------------------------------------
-- 4. comandos_ejecutados (comandos tipeados y descargas/subidas de archivos)
-- ---------------------------------------------------------------------
CREATE TABLE comandos_ejecutados (
    id                   BIGSERIAL PRIMARY KEY,
    sesion_id            UUID        NOT NULL REFERENCES sesiones(id),
    evento_uid           CHAR(64)    NOT NULL UNIQUE,
    timestamp_evento     TIMESTAMPTZ NOT NULL,
    tipo_evento          VARCHAR(10) NOT NULL DEFAULT 'COMANDO'
                         CHECK (tipo_evento IN ('COMANDO', 'DESCARGA', 'SUBIDA')),
    comando_tipeado      TEXT        NOT NULL,
    url_descarga         TEXT,
    hash_descarga_sha256 VARCHAR(64),
    ingresado_en         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_comandos_sesion ON comandos_ejecutados (sesion_id);
CREATE INDEX idx_comandos_ts     ON comandos_ejecutados (timestamp_evento DESC);

-- ---------------------------------------------------------------------
-- 5. evaluaciones_asi
-- ---------------------------------------------------------------------
CREATE TABLE evaluaciones_asi (
    id                     BIGSERIAL PRIMARY KEY,
    ip_origen              INET         NOT NULL,
    fecha_calculo          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    ventana_temporal       INTERVAL     NOT NULL,
    n_intentos             INTEGER      NOT NULL,
    k_pares_distintos      INTEGER      NOT NULL,
    valor_frecuencia       NUMERIC(4,3) NOT NULL CHECK (valor_frecuencia BETWEEN 0 AND 1),
    valor_volumen          NUMERIC(4,3) NOT NULL CHECK (valor_volumen BETWEEN 0 AND 1),
    valor_diversidad       NUMERIC(4,3) NOT NULL CHECK (valor_diversidad BETWEEN 0 AND 1),
    valor_persistencia     NUMERIC(4,3) NOT NULL CHECK (valor_persistencia BETWEEN 0 AND 1),
    puntaje_asi            NUMERIC(4,3) NOT NULL CHECK (puntaje_asi BETWEEN 0 AND 1),
    clasificacion_severidad VARCHAR(15) NOT NULL
                           CHECK (clasificacion_severidad IN ('BAJA', 'MEDIA', 'CRITICA')),
    latencia_ms            INTEGER      -- desde la ingesta del último evento hasta el veredicto
);
CREATE INDEX idx_eval_ip_fecha ON evaluaciones_asi (ip_origen, fecha_calculo DESC);
CREATE INDEX idx_eval_fecha    ON evaluaciones_asi (fecha_calculo DESC);

-- ---------------------------------------------------------------------
-- 6. alertas_seguridad (solo se generan con ASI >= umbral crítico)
-- ---------------------------------------------------------------------
CREATE TABLE alertas_seguridad (
    id                  BIGSERIAL PRIMARY KEY,
    evaluacion_asi_id   BIGINT       NOT NULL REFERENCES evaluaciones_asi(id),
    ip_origen           INET         NOT NULL,
    fecha_disparo       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    nivel_criticidad    VARCHAR(15)  NOT NULL DEFAULT 'CRITICA' CHECK (nivel_criticidad = 'CRITICA'),
    puntaje_asi         NUMERIC(4,3) NOT NULL CHECK (puntaje_asi BETWEEN 0 AND 1),
    estado_alerta       VARCHAR(20)  NOT NULL DEFAULT 'NUEVA'
                        CHECK (estado_alerta IN ('NUEVA', 'EN_REVISION', 'ARCHIVADA')),
    observaciones_auditor TEXT
);
CREATE INDEX idx_alertas_estado ON alertas_seguridad (estado_alerta, fecha_disparo DESC);
CREATE INDEX idx_alertas_ip     ON alertas_seguridad (ip_origen, fecha_disparo DESC);

-- ---------------------------------------------------------------------
-- 7. alertas_historial (solo inserción; la escribe un trigger)
-- ---------------------------------------------------------------------
CREATE TABLE alertas_historial (
    id               BIGSERIAL PRIMARY KEY,
    alerta_id        BIGINT       NOT NULL REFERENCES alertas_seguridad(id),
    auditor          VARCHAR(255) NOT NULL,
    fecha            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    estado_anterior  VARCHAR(20),
    estado_nuevo     VARCHAR(20),
    observaciones_anterior TEXT,
    observaciones_nueva    TEXT
);
CREATE INDEX idx_historial_alerta ON alertas_historial (alerta_id, fecha DESC);

-- ---------------------------------------------------------------------
-- 8. usuarios y 9. accesos_log (autenticación del panel)
-- ---------------------------------------------------------------------
CREATE TABLE usuarios (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correo            VARCHAR(255) NOT NULL UNIQUE CHECK (correo = lower(correo)),
    hash_password     TEXT         NOT NULL,
    rol               VARCHAR(30)  NOT NULL
                      CHECK (rol IN ('RESPONSABLE_SEGURIDAD', 'AUDITOR', 'ADMIN_INFRA')),
    totp_secreto_cifrado TEXT,     -- reservado: TOTP queda como diseño para producción
    estado            VARCHAR(10)  NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'INACTIVO')),
    intentos_fallidos INTEGER      NOT NULL DEFAULT 0,
    bloqueado_hasta   TIMESTAMPTZ,
    fecha_creacion    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE accesos_log (
    id          BIGSERIAL PRIMARY KEY,
    usuario_id  UUID,
    correo      VARCHAR(255),
    ip_cliente  INET,
    evento      VARCHAR(30) NOT NULL,   -- LOGIN_OK, LOGIN_FAIL, LOCKOUT, USUARIO_CREADO, ...
    detalle     TEXT,
    fecha       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_accesos_fecha ON accesos_log (fecha DESC);

-- ---------------------------------------------------------------------
-- 10. ingesta_checkpoint (offset del archivo cowrie.json ya procesado)
-- ---------------------------------------------------------------------
CREATE TABLE ingesta_checkpoint (
    archivo       VARCHAR(255) PRIMARY KEY,
    inode         BIGINT       NOT NULL,
    offset_bytes  BIGINT       NOT NULL CHECK (offset_bytes >= 0),
    actualizado   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- =====================================================================
-- Triggers
-- =====================================================================

-- Historial de cambios de alertas. SECURITY DEFINER: api_app no necesita
-- (ni tiene) privilegio INSERT sobre alertas_historial.
CREATE FUNCTION fn_alertas_historial() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = honeypot, pg_temp AS $$
BEGIN
    IF NEW.estado_alerta IS DISTINCT FROM OLD.estado_alerta
       OR NEW.observaciones_auditor IS DISTINCT FROM OLD.observaciones_auditor THEN
        INSERT INTO alertas_historial
            (alerta_id, auditor, estado_anterior, estado_nuevo,
             observaciones_anterior, observaciones_nueva)
        VALUES
            (NEW.id,
             COALESCE(NULLIF(current_setting('app.current_user', true), ''), session_user::text),
             OLD.estado_alerta, NEW.estado_alerta,
             OLD.observaciones_auditor, NEW.observaciones_auditor);
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_alertas_historial
AFTER UPDATE ON alertas_seguridad
FOR EACH ROW EXECUTE FUNCTION fn_alertas_historial();

-- Tablas de solo inserción: rechazan UPDATE/DELETE incluso para el dueño.
CREATE FUNCTION fn_solo_insercion() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % es de solo inserción', TG_TABLE_NAME
        USING ERRCODE = 'insufficient_privilege';
END $$;

CREATE TRIGGER trg_historial_inmutable
BEFORE UPDATE OR DELETE ON alertas_historial
FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();

CREATE TRIGGER trg_accesos_inmutable
BEFORE UPDATE OR DELETE ON accesos_log
FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();

-- =====================================================================
-- Permisos por rol (mínimo privilegio). Ningún rol de aplicación tiene DELETE.
-- =====================================================================
REVOKE ALL ON ALL TABLES    IN SCHEMA honeypot FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA honeypot FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA honeypot FROM PUBLIC;

GRANT USAGE ON SCHEMA honeypot TO cowrie_ingest, asi_engine, api_app;

-- cowrie_ingest ------------------------------------------------------
GRANT SELECT, INSERT ON sensores, sesiones, intentos_login, comandos_ejecutados TO cowrie_ingest;
GRANT UPDATE (fecha_fin, duracion_segundos) ON sesiones TO cowrie_ingest;
GRANT SELECT, INSERT ON ingesta_checkpoint TO cowrie_ingest;
GRANT UPDATE (inode, offset_bytes, actualizado) ON ingesta_checkpoint TO cowrie_ingest;
GRANT USAGE ON SEQUENCE intentos_login_id_seq, comandos_ejecutados_id_seq TO cowrie_ingest;

-- asi_engine ---------------------------------------------------------
GRANT SELECT ON sensores, sesiones, intentos_login, comandos_ejecutados TO asi_engine;
GRANT SELECT, INSERT ON evaluaciones_asi, alertas_seguridad TO asi_engine;
GRANT USAGE ON SEQUENCE evaluaciones_asi_id_seq, alertas_seguridad_id_seq TO asi_engine;

-- api_app ------------------------------------------------------------
GRANT SELECT ON sensores, sesiones, intentos_login, comandos_ejecutados,
                evaluaciones_asi, alertas_seguridad, alertas_historial,
                usuarios, accesos_log TO api_app;
GRANT UPDATE (estado_alerta, observaciones_auditor) ON alertas_seguridad TO api_app;
GRANT INSERT ON accesos_log TO api_app;
GRANT USAGE ON SEQUENCE accesos_log_id_seq TO api_app;
GRANT INSERT ON usuarios TO api_app;
GRANT UPDATE (rol, estado, intentos_fallidos, bloqueado_hasta, hash_password) ON usuarios TO api_app;

RESET ROLE;
