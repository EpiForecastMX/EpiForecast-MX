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
