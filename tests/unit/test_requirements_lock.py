"""Contrato entre pyproject.toml, requirements.lock y requirements.txt.

El lock es el cierre transitivo con el que se reproduce el entorno validado. Si queda
fuera de los rangos que declara pyproject.toml (como el omegaconf 2.4 que rompió el
CI), reproducir con el lock instala un entorno que el proyecto no admite.
"""

from __future__ import annotations

from pathlib import Path
import re
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[2]
_PIN = re.compile(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]+\])?==(\S+)$")
_GROUPS = ("dev", "dvc", "mlflow", "scraping", "gsheets")


def _pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _PIN.match(line.strip())
        if match:
            pins[canonicalize_name(match.group(1))] = match.group(2)
    return pins


def _declared() -> list[tuple[str, Requirement]]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    reqs = [("core", Requirement(r)) for r in project["dependencies"]]
    for group in _GROUPS:
        reqs += [(group, Requirement(r)) for r in project["optional-dependencies"][group]]
    return reqs


def test_lock_sin_duplicados() -> None:
    names = [
        canonicalize_name(m.group(1))
        for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()
        if (m := _PIN.match(line.strip()))
    ]
    assert len(names) == len(set(names))


def test_lock_respeta_los_rangos_de_pyproject() -> None:
    lock = _pins(ROOT / "requirements.lock")
    faltan: list[str] = []
    fuera: list[str] = []
    for group, req in _declared():
        version = lock.get(canonicalize_name(req.name))
        if version is None:
            faltan.append(f"{group}:{req.name}")
        elif not req.specifier.contains(version, prereleases=True):
            fuera.append(f"{group}:{req.name}=={version} fuera de {req.specifier}")
    assert not fuera, fuera
    assert not faltan, faltan


def test_requirements_txt_coincide_con_el_lock() -> None:
    lock = _pins(ROOT / "requirements.lock")
    directas = _pins(ROOT / "requirements.txt")
    assert directas
    distintas = {n: (v, lock.get(n)) for n, v in directas.items() if lock.get(n) != v}
    assert not distintas, distintas
