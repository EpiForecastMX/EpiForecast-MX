"""El orquestador semanal: bloqueado a propósito, y cableado de forma verificable.

El bloqueo del preflight sigue: correr el flujo real exige la autorización de P1 (red,
pull, dvc pull, sincronización aditiva y la decisión de publicar). Esta prueba existe para
que nadie retire el bloqueo por descuido. Y como el guion no se ejecuta, su cableado se
comprueba de forma ESTÁTICA: qué subórdenes invoca, con qué flags y en qué orden. Un guion
que sella sin `--destino-dashboard`, que corre los gates antes de subir la cadena de caché
o que usa `stat -f` (sólo BSD) es un guion que falla en la primera corrida real.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess

import pytest

RAIZ = Path(__file__).resolve().parents[3]
GUION = RAIZ / "scripts" / "actualiza_semanal.sh"
MAKEFILE = RAIZ / "Makefile"


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
    assert "autorización de P1" in resultado.stderr
    assert "opción C" in resultado.stderr
    # Aborta ANTES del preflight de repositorios, del pull, de DVC o de cualquier generación.
    assert "PREFLIGHT · archivos sin versionar" not in resultado.stdout
    assert "HEAD fijados" not in resultado.stdout
    assert "MATERIALIZAR CANDIDATO" not in resultado.stdout


def _invocaciones(texto: str) -> list[tuple[str, str]]:
    """(suborden, argv completo) de cada `refresh_staging` del guion, en orden de aparición."""
    salida: list[tuple[str, str]] = []
    for m in re.finditer(r"scripts\.refresh_staging (\S+)((?:[^\n]*\\\n)*[^\n]*)", texto):
        salida.append((m.group(1), m.group(2)))
    return salida


@pytest.mark.contract
def test_el_cableado_del_orquestador_es_el_del_flujo_sellado() -> None:
    texto = GUION.read_text(encoding="utf-8")
    assert subprocess.run(["bash", "-n", str(GUION)], capture_output=True).returncode == 0
    ordenes = [orden for orden, _ in _invocaciones(texto)]
    assert ordenes == ["materialize", "hydrate", "bump-cache", "run-gates", "seal"], ordenes
    argv = dict(_invocaciones(texto))

    for flag in ("--repo-backend", "--head-backend", "--repo-dashboard", "--head-dashboard"):
        assert flag in argv["materialize"]
    assert "--padecimientos" in argv["hydrate"] and "--boletin" in texto
    assert "--destino-dashboard" in argv["bump-cache"] and "--head-dashboard" in argv["bump-cache"]
    assert "--destino-backend" in argv["run-gates"] and "--destino-dashboard" in argv["run-gates"]
    for flag in (
        "--semilla",
        "--head-backend",
        "--head-dashboard",
        "--destino-backend",
        "--destino-dashboard",
        "--semana-anterior",
        "--semana-nueva",
        "--padecimientos",
    ):
        assert flag in argv["seal"], f"seal sin {flag}"
    assert "--resultados-pruebas" not in texto and "--operacion-dvc" not in texto

    # Portabilidad y repetibilidad.
    assert "stat -f" not in texto, "stat -f es sólo BSD"
    assert "wc -c" in texto
    assert '${BOLETINES_ARGS[@]+"${BOLETINES_ARGS[@]}"}' in texto, (
        "arreglo vacío seguro (bash 3.2)"
    )
    assert "ls -1 data/raw_PDFs" not in texto
    assert "${TRABAJO}.sandbox.previo" in texto, "el sandbox previo se aparta con el trabajo"
    assert "rag:build" in texto and "GEMINI_API_KEY" in texto
    assert 'make -C "$SANDBOX" PYTHON="$PYTHON" tabla-produccion' not in texto, (
        "rama RETRAIN muerta"
    )
    assert "RETRAIN=1 no cabe en el carril semanal" in texto


@pytest.mark.contract
def test_los_targets_de_apply_y_discard_llevan_el_manifiesto() -> None:
    texto = MAKEFILE.read_text(encoding="utf-8")
    discard = texto[texto.index("update-week-discard:") :]
    assert re.search(r"discard-worktrees \\\n\s+--manifiesto", discard)
    apply = texto[texto.index("update-week-apply:") : texto.index("update-week-discard")]
    assert "prepare-worktrees" in apply and "check-completeness" in apply
