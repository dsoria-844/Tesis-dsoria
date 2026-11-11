"""Integración de punta a punta: cowrie.json sintético -> colector -> BD -> motor ASI -> alertas."""
import subprocess
import sys

from hp.collector.ingest import Ingestor
from hp.collector.main import process_available
from hp.collector.tailer import LogTailer
from hp.engine.runner import AsiRunner


def test_demo_sintetico_genera_alertas_solo_para_los_ataques_sostenidos(db, tmp_path):
    log = tmp_path / "cowrie.json"
    subprocess.run([sys.executable, "-m", "hp.tools.gen_log", "--out", str(log), "--seed", "7"],
                   check=True, capture_output=True)
    with db("cowrie_ingest") as conn:
        _, n_lines, n_events, n_err = process_available(LogTailer(tmp_path, "cowrie.json"), Ingestor(conn), None)
        assert n_err == 0 and n_events > 5000
    with db("asi_engine") as conn:
        runner = AsiRunner(conn)
        r1 = runner.evaluate()
        r2 = runner.evaluate()          # segunda corrida inmediata: no duplica nada
    assert r1.alertas_creadas == 4 and r2.alertas_creadas == 0 and r2.evaluaciones_insertadas == 0
    with db.admin() as c:
        ips = sorted(str(r["ip_origen"]) for r in c.execute("SELECT ip_origen FROM alertas_seguridad"))
        hash_ = c.execute("SELECT count(*) c FROM comandos_ejecutados WHERE hash_descarga_sha256 IS NOT NULL").fetchone()["c"]
    assert ips == ["203.0.113.21", "203.0.113.22", "203.0.113.23", "203.0.113.24"]
    assert hash_ == 1
