"""El orquestador semanal está bloqueado a propósito, y tiene que seguir estándolo.

El cableado —materialize → generadores → run-gates → seal, y prepare-worktrees → apply →
check-completeness— está probado con repositorios sintéticos, no contra datos reales, y
faltan P0.1 (hidratación por allowlist), P0.2 (inputs bajo el staging) y P0.8 (Dengue
fail-closed). La puesta al día es P1 y exige autorización aparte. Sin este bloqueo el
flujo haría toda la preparación —descargas, DVC, generación, decenas de minutos— para
morir al final o, peor, para producir un candidato plausible con entradas incompletas.

Esta prueba existe para que nadie retire el bloqueo por descuido. Se sustituye por la del
flujo real cuando P1 se autorice; no se borra sin más.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

RAIZ = Path(__file__).resolve().parents[3]
GUION = RAIZ / "scripts" / "actualiza_semanal.sh"


@pytest.mark.contract
def test_el_orquestador_semanal_aborta_antes_de_hacer_nada() -> None:
    resultado = subprocess.run(
        ["bash", str(GUION)],
        capture_output=True,
        text=True,
        cwd=RAIZ,
        timeout=60,
    )

    assert resultado.returncode == 1, resultado.stdout + resultado.stderr
    assert "ABORTA" in resultado.stderr
    assert "sigue BLOQUEADO" in resultado.stderr
    assert "P0.2" in resultado.stderr
    assert "opción C" in resultado.stderr
    # Aborta ANTES del preflight de repositorios, del pull, de DVC o de cualquier generación.
    assert "PREFLIGHT · archivos sin versionar" not in resultado.stdout
    assert "HEAD fijados" not in resultado.stdout
    assert "MATERIALIZAR CANDIDATO" not in resultado.stdout
