"""Contrato de endurecimiento de los workflows de GitHub Actions."""

from pathlib import Path
import re

import pytest
import yaml

pytestmark = pytest.mark.contract

WORKFLOWS = sorted((Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml"))
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)(.*)$")
SHA_PIN = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def test_hay_workflows() -> None:
    assert WORKFLOWS


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_acciones_fijadas_por_sha_con_etiqueta(workflow: Path) -> None:
    malos = []
    for n, linea in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
        m = USES.match(linea)
        if m and not (SHA_PIN.match(m.group(1)) and re.search(r"#\s*v\d", m.group(2))):
            malos.append(f"{workflow.name}:{n}: {linea.strip()}")
    assert not malos, "acción sin SHA de 40 caracteres y etiqueta comentada:\n" + "\n".join(malos)


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_permisos_y_timeouts_declarados(workflow: Path) -> None:
    doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    assert "permissions" in doc, f"{workflow.name} sin permissions de nivel raíz"
    sin_timeout = [j for j, cfg in doc["jobs"].items() if "timeout-minutes" not in cfg]
    assert not sin_timeout, f"{workflow.name}: jobs sin timeout-minutes {sin_timeout}"


def _workflow(nombre: str) -> dict:
    ruta = next(p for p in WORKFLOWS if p.name == nombre)
    doc: dict = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return doc


def test_ci_solo_cancela_pull_requests() -> None:
    """Cada push a main conserva su CI: sólo una PR superada se cancela."""
    regla = _workflow("ci.yml")["concurrency"]["cancel-in-progress"]
    assert regla == "${{ github.event_name == 'pull_request' }}"


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_secretos_nunca_interpolados_en_run(workflow: Path) -> None:
    """Los secretos y salidas de pasos llegan a los scripts por env, no por ${{ }}."""
    doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    malos = [
        f"{workflow.name}:{job}:{paso.get('name', '?')}"
        for job, cfg in doc["jobs"].items()
        for paso in cfg.get("steps", [])
        if re.search(r"\$\{\{\s*(secrets|steps)\.", str(paso.get("run", "")))
    ]
    assert not malos, "secretos o salidas interpolados en run:\n" + "\n".join(malos)


def test_procesamiento_solo_desde_scraper_en_main() -> None:
    """Un dispatch del scraper en otra rama no dispara el procesamiento que empuja a main."""
    doc = _workflow("process_boletines.yml")
    disparadores = doc.get("on", doc.get(True))  # PyYAML lee la clave `on` como True
    assert disparadores["workflow_run"]["branches"] == ["main"]
    assert "head_branch == 'main'" in doc["jobs"]["process"]["if"]
