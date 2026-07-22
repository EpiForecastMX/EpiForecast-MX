"""Doctor del registry: reporta qué falta para que un padecimiento esté completo.

Convierte el ``raise ValueError`` en runtime (tuner.py, al no encontrar el grid a media
CV) en un check fail-fast. ``--config-only`` (CI) valida config; ``--artifacts`` valida
también los artefactos en disco (modelos/forecasts), para las fases post-entrenamiento.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from omegaconf import OmegaConf

from epiforecast import registry


@dataclass(frozen=True)
class Problem:
    disease: str
    severity: str  # "error" | "warn"
    message: str


def _config_dir() -> Path:
    packaged = Path(__file__).resolve().parents[2] / "config"
    return packaged if packaged.exists() else Path("config")


def _grid_keys(model_file: str, grid_key_name: str) -> set[str]:
    p = _config_dir() / "models" / model_file
    if not p.exists():
        return set()
    data = cast("dict[str, Any]", OmegaConf.to_container(OmegaConf.load(p), resolve=True)) or {}
    return set((data.get(grid_key_name) or {}).keys())


def _models_dir() -> Path:
    root = Path(__file__).resolve().parents[2]
    return (root / "models") if (root / "models").exists() else Path("models")


def diagnose(name: str | None = None, check_artifacts: bool = False) -> list[Problem]:
    """Lista de problemas (vacía = OK). ``name=None`` diagnostica todos los padecimientos."""
    problems: list[Problem] = []
    targets = [registry.require(name)] if name else list(registry.get_registry().diseases)
    prophet_grids = _grid_keys("prophet.yaml", "param_grid_prophet")
    deepar_grids = _grid_keys("deepar.yaml", "param_grid_deepar")

    for d in targets:
        # Prophet grid: obligatorio si entrena Prophet.
        if "prophet" in d.training_engines:
            if not d.prophet_grid_key:
                problems.append(Problem(d.id, "error", "prophet_grid_key ausente"))
            elif d.prophet_grid_key not in prophet_grids:
                problems.append(
                    Problem(d.id, "error", f"param_grid_prophet.{d.prophet_grid_key} no existe")
                )
        # DeepAR grid: null = usa escalares long-series (OK); si se fija, debe existir.
        if d.deepar_grid_key and d.deepar_grid_key not in deepar_grids:
            problems.append(
                Problem(d.id, "error", f"param_grid_deepar.{d.deepar_grid_key} no existe")
            )
        # Web mínimos.
        for field in ("color", "label"):
            if not d.web.get(field):
                problems.append(Problem(d.id, "error", f"web.{field} ausente"))
        if not d.cie_codes:
            problems.append(Problem(d.id, "error", "cie_codes vacío"))
        # Elegibles ⊆ entrenables.
        for e in d.eligible_engines:
            if e not in d.training_engines:
                problems.append(
                    Problem(d.id, "error", f"motor elegible '{e}' no está en training_engines")
                )
        # Artefactos (solo si se pide y el padecimiento debería tener modelos).
        if check_artifacts and d.lifecycle in ("trained", "published"):
            for e in d.training_engines:
                mdir = _models_dir() / e / d.artifact_key
                if not mdir.exists():
                    problems.append(
                        Problem(d.id, "error", f"models/{e}/{d.artifact_key}/ no existe")
                    )
    return problems
