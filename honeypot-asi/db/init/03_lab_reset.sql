-- =====================================================================
-- Lab-only reset of telemetry for clean demos (ADMIN_INFRA, via the API).
--
-- No application role gets DELETE/TRUNCATE: the only path is this SECURITY
-- DEFINER function, owned by db_owner (the table owner), executable by api_app.
--
-- Deleted : comandos_ejecutados, intentos_login, sesiones, evaluaciones_asi,
--           alertas_historial, alertas_seguridad.
-- Kept    : usuarios, accesos_log (audit trail), sensores, and
--           ingesta_checkpoint (otherwise the collector would re-ingest the
--           whole cowrie.json and recreate everything).
--
-- Note on immutability: trg_historial_inmutable / trg_accesos_inmutable are
-- ROW-level BEFORE UPDATE OR DELETE triggers. TRUNCATE does not fire them and
-- there are no statement-level TRUNCATE triggers, so alertas_historial (an
-- insert-only table) CAN be emptied here. That is deliberate and visible: the
-- function records a LAB_REINICIO row in accesos_log (which is never
-- truncated) with the actor and the deleted counts.
-- Do not deploy to production: set LAB_RESET_ENABLED=false in the API.
-- =====================================================================
SET ROLE db_owner;
SET search_path = honeypot;

CREATE OR REPLACE FUNCTION reiniciar_laboratorio(p_actor uuid, p_ip inet DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = honeypot, pg_temp AS $$
DECLARE
    v_correo  text;
    v_counts  jsonb;
BEGIN
    -- Defense in depth: the API already checks the role, the function checks it again.
    SELECT correo INTO v_correo FROM usuarios
     WHERE id = p_actor AND rol = 'ADMIN_INFRA' AND estado = 'ACTIVO';
    IF v_correo IS NULL THEN
        RAISE EXCEPTION 'Solo un ADMIN_INFRA activo puede reiniciar el laboratorio'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    -- Exclusive lock first so the counts match what is deleted (collector/engine wait briefly).
    LOCK TABLE comandos_ejecutados, intentos_login, sesiones, evaluaciones_asi,
               alertas_historial, alertas_seguridad IN ACCESS EXCLUSIVE MODE;

    SELECT jsonb_build_object(
        'comandos_ejecutados', (SELECT count(*) FROM comandos_ejecutados),
        'intentos_login',      (SELECT count(*) FROM intentos_login),
        'sesiones',            (SELECT count(*) FROM sesiones),
        'evaluaciones_asi',    (SELECT count(*) FROM evaluaciones_asi),
        'alertas_historial',   (SELECT count(*) FROM alertas_historial),
        'alertas_seguridad',   (SELECT count(*) FROM alertas_seguridad))
      INTO v_counts;

    TRUNCATE comandos_ejecutados, intentos_login, sesiones, evaluaciones_asi,
             alertas_historial, alertas_seguridad RESTART IDENTITY;

    INSERT INTO accesos_log (usuario_id, correo, ip_cliente, evento, detalle)
    VALUES (p_actor, v_correo, p_ip, 'LAB_REINICIO', v_counts::text);

    -- Tell the collector to drop its in-memory caches (session/sensor ids) so it does not
    -- reference the truncated rows; delivered only if this transaction commits.
    PERFORM pg_notify('hp_lab_reset', v_correo);

    RETURN v_counts;
END $$;

REVOKE ALL ON FUNCTION reiniciar_laboratorio(uuid, inet) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION reiniciar_laboratorio(uuid, inet) TO api_app;

RESET ROLE;
