"""F2/C3 — política de evaluación declarativa (``config/evaluation/<name>.yaml``).

C3.0: lo mínimo para el runner — ruta, digest reproducible del archivo, candidatos por defecto
del benchmark (NO los training_engines legacy) y seed. El loader completo de folds/ventanas y su
validación (disjuntos, 52 sem, ≥260 previas) se añade en C3.1 sobre este mismo módulo.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

from omegaconf import OmegaConf

_ROOT = Path(__file__).resolve().parents[3]


class PolicyError(ValueError):
    """Política de evaluación ausente o inválida."""


def policy_path(name: str) -> Path:
    path = _ROOT / "config" / "evaluation" / f"{name}.yaml"
    if not path.exists():
        raise PolicyError(f"política de evaluación desconocida: {name!r} ({path})")
    return path


def policy_digest(name: str) -> str:
    """sha256 del archivo de política (entra en el ``run_id`` → cambios de política = nuevo run)."""
    return hashlib.sha256(policy_path(name).read_bytes()).hexdigest()


def _load_raw(name: str) -> dict[str, Any]:
    return cast(
        "dict[str, Any]", OmegaConf.to_container(OmegaConf.load(policy_path(name)), resolve=True)
    )


def candidate_engines(name: str) -> list[str]:
    """Motores candidatos declarados en la política (default del benchmark)."""
    raw = _load_raw(name)
    engines = [str(e) for e in raw.get("candidate_engines", [])]
    if not engines:
        raise PolicyError(f"política {name!r} sin candidate_engines")
    return engines


def policy_seed(name: str) -> int:
    return int(_load_raw(name)["seed"])
