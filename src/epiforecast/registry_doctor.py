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


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _models_dir() -> Path:
    root = _project_root()
    return (root / "models") if (root / "models").exists() else Path("models")


def diagnose(
    name: str | None = None,
    check_artifacts: bool = False,
    *,
    runs_root: Path | None = None,
    models_root: Path | None = None,
    releases_root: Path | None = None,
) -> list[Problem]:
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
        # Artefactos (solo si se pide y el padecimiento debería tener modelos). El backend decide
        # QUÉ es evidencia: existir un directorio no lo es (C7.1).
        if check_artifacts and d.lifecycle in ("trained", "published"):
            problems.extend(_diagnose_artifacts(d, runs_root, models_root, releases_root))
    return problems


# ── Verificación de artefactos por backend (C7.1) ──────────────────────────────────────────────
def _runs_root() -> Path:
    return _project_root() / "runs"


def _diagnose_artifacts(
    d: registry.Disease,
    runs_root: Path | None = None,
    models_root: Path | None = None,
    releases_root: Path | None = None,
) -> list[Problem]:
    """Despacha al backend declarado. Un backend del runner NUNCA acepta models/<motor>/."""
    backend = d.artifact_backend
    if backend == registry.BACKEND_LEGACY:
        base = models_root or _models_dir()
        return [
            Problem(d.id, "error", f"models/{e}/{d.artifact_key}/ no existe")
            for e in d.training_engines
            if not (base / e / d.artifact_key).exists()
        ]
    if backend == registry.BACKEND_RUNNER_RUNS:
        return _diagnose_runner_runs(d, runs_root or _runs_root())
    if backend == registry.BACKEND_RUNNER_RELEASE:
        from epiforecast.runner.release_store import default_releases_root

        return _diagnose_runner_release(d, releases_root or default_releases_root())
    return [  # pragma: no cover — ARTIFACT_BACKENDS no admite otro valor
        Problem(d.id, "error", f"backend {backend!r}: verificación no implementada")
    ]


def _policy_path(d: registry.Disease) -> Path:
    return _project_root() / "config" / "evaluation" / f"{d.selection_policy}.yaml"


def _diagnose_runner_runs(d: registry.Disease, runs_root: Path) -> list[Problem]:
    """Adaptador: delega TODO el contrato en el validador del runner y traduce su error.

    El doctor no vuelve a implementar la identidad de los runs sellados (Acción 3): existe una
    sola implementación —``runner.artifact_validation``— y aquí solo se convierte
    ``ArtifactValidationError`` en ``Problem``, para que un artefacto roto nunca escape como
    traceback.
    """
    from epiforecast.runner.artifact_identity import ArtifactValidationError
    from epiforecast.runner.artifact_validation import validate_runner_runs

    problems: list[Problem] = []
    src = d.artifact_source
    try:
        validate_runner_runs(
            disease_id=d.id,
            refit_run_id=str(src.refit_run_id),
            forecast_run_id=str(src.forecast_run_id),
            policy_digest=str(src.policy_digest),
            final_selection_digest=str(src.final_selection_digest),
            runs_root=runs_root,
            policy_path=_policy_path(d),
        )
    except ArtifactValidationError as exc:
        problems.append(Problem(d.id, "error", str(exc)))

    # Los PKL preliminares del carril viejo no son evidencia y no deben mirarse siquiera.
    if d.training_engines or d.eligible_engines:
        problems.append(
            Problem(d.id, "warning", "declara motores legacy pese a usar un backend del runner")
        )
    return problems


def _diagnose_runner_release(d: registry.Disease, releases_root: Path) -> list[Problem]:
    """Adaptador: el release DECLARADO existe en su sede, verifica entero y REPRODUCE.

    Que el directorio exista no es evidencia —ése fue el falso verde de C7.1— y que sus digests
    cuadren tampoco: un bundle sólo es evidencia si sus 64 modelos cargan y vuelven a producir el
    forecast que transporta. Por eso el doctor reproduce, y por eso tarda unos segundos.

    ``releases_root`` se inyecta; aquí no se resuelve ninguna ruta por cwd ni por convención.
    """
    from epiforecast.runner.artifact_identity import ArtifactValidationError
    from epiforecast.runner.release_loader import verify_bundle
    from epiforecast.runner.release_reproduce import check_reproduction
    from epiforecast.runner.release_store import release_path

    problems: list[Problem] = []
    release_id = str(d.artifact_source.release_id)
    try:
        destino = release_path(releases_root, d.id, release_id)
        if not destino.is_dir():
            raise ArtifactValidationError(f"el release declarado no está en la sede: {release_id}")
        verificado = verify_bundle(destino)
        # El release que se carga tiene que ser EL que el registry declara, no otro que valide.
        if verificado.release_id != release_id:
            raise ArtifactValidationError(
                f"la sede contiene {verificado.release_id!r} donde el registry declara {release_id!r}"
            )
        if verificado.disease_id != d.id:
            raise ArtifactValidationError(
                f"el release es de {verificado.disease_id!r}, no de {d.id!r}"
            )
        check_reproduction(verificado, tol=0.0)
    except ArtifactValidationError as exc:
        problems.append(Problem(d.id, "error", str(exc)))

    if d.training_engines or d.eligible_engines:
        problems.append(
            Problem(d.id, "warning", "declara motores legacy pese a usar un backend del runner")
        )
    return problems
