"""C7.2-A/R15.3 — entry point IMPURO del release: registry + cadena sellada → rutas + builder.

Es la única capa que mira el registry y los runs. Abre la cadena con ``validate_runner_runs`` (la
misma implementación que usa el doctor: no hay una segunda), resuelve las rutas fuente explícitas y
se las entrega al builder puro junto con la activación DECLARADA —qué haría falta para publicar—,
que aquí nunca se aplica.

Construir un bundle no publica nada: no toca `runs/`, ni el lifecycle, ni canales, ni DVC. El
destino lo decide quien llama; C7.2-A sólo autoriza temporales.
"""

from __future__ import annotations

from pathlib import Path

from epiforecast import registry
from epiforecast.data.epi_geo_exposure import GeoCatalog
from epiforecast.runner.artifact_identity import ArtifactValidationError, require, text_of
from epiforecast.runner.artifact_validation import VerifiedRunnerRuns, validate_runner_runs
from epiforecast.runner.release_builder import BuiltRelease, ReleaseActivation, build_release
from epiforecast.runner.release_sources import ReleaseSources, resolve_sources

# Publicar exige `runner_release`: la matriz lifecycle × backend del registry ya lo impone. El
# bundle lo DECLARA para que su activación sea auditable, y nunca lo aplica.
LIFECYCLE_FOR_ACTIVATION = "published"


def activation_for(disease: registry.Disease) -> ReleaseActivation:
    """Canales candidatos y lifecycle requerido, tomados del registry tal cual están declarados."""
    return ReleaseActivation(
        backend=registry.BACKEND_RUNNER_RELEASE,
        lifecycle_required=LIFECYCLE_FOR_ACTIVATION,
        channels_candidate=tuple(str(c) for c in disease.channels),
        activated=False,
    )


def verify_chain(
    disease: registry.Disease,
    *,
    runs_root: Path,
    policy_path: Path,
    geo_catalog: GeoCatalog | None = None,
) -> VerifiedRunnerRuns:
    """Cadena sellada del padecimiento, validada con la ÚNICA implementación del contrato."""
    src = disease.artifact_source
    require(
        src.backend == registry.BACKEND_RUNNER_RUNS,
        f"{disease.id}: promover a release exige backend {registry.BACKEND_RUNNER_RUNS!r}, "
        f"no {src.backend!r}",
    )
    return validate_runner_runs(
        disease_id=disease.id,
        refit_run_id=text_of(src.refit_run_id, f"{disease.id}: refit_run_id"),
        forecast_run_id=text_of(src.forecast_run_id, f"{disease.id}: forecast_run_id"),
        policy_digest=text_of(src.policy_digest, f"{disease.id}: policy_digest"),
        final_selection_digest=text_of(
            src.final_selection_digest, f"{disease.id}: final_selection_digest"
        ),
        runs_root=runs_root,
        policy_path=policy_path,
        geo_catalog=geo_catalog,
    )


def sources_for(
    verified: VerifiedRunnerRuns, *, runs_root: Path, policy_path: Path
) -> ReleaseSources:
    return resolve_sources(verified, runs_root=runs_root, policy_path=policy_path)


def build_release_for_disease(
    disease_id: str,
    *,
    runs_root: Path,
    policy_path: Path,
    output_root: Path,
    geo_catalog: GeoCatalog | None = None,
) -> BuiltRelease:
    """Valida la cadena y construye el bundle bajo ``output_root``. Nunca escribe fuera de ahí."""
    try:
        disease = registry.require(disease_id)
    except (KeyError, ValueError) as exc:
        raise ArtifactValidationError(f"padecimiento desconocido: {disease_id!r} ({exc})") from exc
    verified = verify_chain(
        disease, runs_root=runs_root, policy_path=policy_path, geo_catalog=geo_catalog
    )
    return build_release(
        verified=verified,
        sources=sources_for(verified, runs_root=runs_root, policy_path=policy_path),
        activation=activation_for(disease),
        output_root=output_root,
    )
