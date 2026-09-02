"""El orquestador semanal está bloqueado a propósito, y tiene que seguir estándolo.

`seal` calcula ya la composición del árbol administrado y exige que los gates se hayan
corrido sobre ella, contra una política de censo versionada. Este guion no puede
satisfacerlo todavía: su siembra es **parcial** —18 de las 41 superficies publicadas—, así
que la composición no cubriría el censo, y sus gates no declaran contra qué árbol
corrieron. Sin este bloqueo el flujo haría toda la preparación —descargas, DVC, generación,
decenas de minutos— para morir al final, con el trabajo tirado.

Esta prueba existe para que nadie retire el bloqueo por descuido. Cuando la siembra sea
completa y los gates declaren su composición, se sustituye por la del flujo real; no se
borra sin más.
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
    assert "siembra es parcial" in resultado.stderr
    assert "P0.6" in resultado.stderr
    # Aborta ANTES del preflight de repositorios, DVC o cualquier generación.
    assert "PREFLIGHT · archivos sin versionar" not in resultado.stdout
    assert "SEMBRAR STAGING" not in resultado.stdout
