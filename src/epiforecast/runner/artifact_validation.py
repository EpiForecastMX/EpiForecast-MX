"""C7.1/Acción 3 — validador reutilizable de un padecimiento entrenado por el runner (P0.2).

Comprueba que refit y forecast SELLADOS son los que el registry declara y que toda la cadena de
identidad cierra: run IDs, dataset, política, selección, aceptación, digest del refit, los motores
realmente presentes, un modelo final por serie y la misma ventana de entrenamiento en todas partes.

Es la única implementación del contrato: ``registry_doctor`` lo invoca y traduce su error a
``Problem``; no vuelve a comprobar nada por su cuenta. Ajeno al CLI y sin globals del proyecto —
recibe ``runs_root``, la ruta de la política y (opcionalmente) el catálogo geográfico, así que se
puede probar entero sobre artefactos sintéticos, sin tocar los runs canónicos.

Fuera de alcance en la Acción 3: el contenido tabular de ``forecast.csv``, ``forecast_base.csv`` y
``model_inventory.csv`` (Acción 4).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from epiforecast.data.epi_geo_exposure import GeoCatalog
from epiforecast.runner import artifact_portfolio as portfolio
from epiforecast.runner.artifact_acceptance import validate_acceptance
from epiforecast.runner.artifact_dataset import dataset_window
from epiforecast.runner.artifact_forecast import validate_forecast
from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    input_digest,
    read_manifest,
    require,
    require_artifacts,
    require_job_artifacts,
    sha256_file,
    text_of,
)
from epiforecast.runner.artifact_refit import (
    CHAIN_DIGESTS,
    SCHEMA_LINEAGE,
    SCHEMA_REFIT_SUMMARY,
    SUMMARY_FILE,
    check_lineage,
    read_summary,
)
from epiforecast.runner.final_models import SCHEMA_MODEL_INDEX

CMD_REFIT = "refit"
CMD_FORECAST = "forecast"
_INDEX_PATH = "models/{engine}/model_index.json"
# Inventario EXACTO del forecast. Su contenido tabular es de la Acción 4; la identidad del run
# —qué salidas declara y con qué schema— se cierra aquí (R7.4).
_FORECAST_ARTIFACTS = {
    "forecast_base.csv": "forecast_base.v1",
    "forecast.csv": "forecast.v1",
    "model_inventory.csv": "model_inventory.v1",
    "lineage.json": SCHEMA_LINEAGE,
    "preliminary_report.md": "preliminary_report.v1",
}
_FORECAST_JOB_ARTIFACTS = {"artifacts/{engine}/forecast_base.csv": "forecast_base.v1"}
# Digests que refit y forecast DEBEN compartir: describen las mismas entradas inmutables.
_SHARED_DIGESTS = ("raw", "exposure", "config", "dataset")


@dataclass(frozen=True, slots=True)
class VerifiedRunnerRuns:
    """Identidades ya verificadas de un padecimiento con backend ``runner_runs`` (inmutable)."""

    disease_id: str
    refit_run_id: str
    forecast_run_id: str
    dataset_id: str
    policy_digest: str
    selection_digest: str
    final_selection_digest: str
    acceptance_run_id: str
    acceptance_digest: str
    acceptance_scopes: tuple[str, ...]
    refit_digest: str
    distribution: tuple[tuple[str, int], ...]
    models: tuple[portfolio.ModelIdentity, ...]
    n_train: int
    train_end: tuple[int, int]
    counts: tuple[tuple[str, int], ...]

    @property
    def engines(self) -> tuple[str, ...]:
        return tuple(engine for engine, _ in self.distribution)

    @property
    def series(self) -> tuple[portfolio.SeriesId, ...]:
        return tuple(modelo.series for modelo in self.models)

    @property
    def n_models(self) -> int:
        return len(self.models)


def _catalog(geo_catalog: GeoCatalog | None) -> GeoCatalog:
    """El catálogo geográfico trackeado, inyectable: el validador no decide el universo."""
    if geo_catalog is not None:
        return geo_catalog
    from epiforecast.data.epi_geo_exposure import load_geo_catalog

    try:
        return load_geo_catalog()
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"catálogo geográfico ilegible ({exc})") from exc


def _check_counts(raw: Mapping[str, int], expected: Mapping[str, int], label: str) -> None:
    for clave, valor in expected.items():
        equal(f"{label}: counts[{clave!r}]", raw.get(clave), valor)


def validate_runner_runs(
    *,
    disease_id: str,
    refit_run_id: str,
    forecast_run_id: str,
    policy_digest: str,
    final_selection_digest: str,
    runs_root: Path,
    policy_path: Path,
    geo_catalog: GeoCatalog | None = None,
) -> VerifiedRunnerRuns:
    """Valida la cadena completa o levanta ``ArtifactValidationError`` en el primer incumplimiento."""
    catalogo = _catalog(geo_catalog)
    geography_ids = catalogo.cve_ents()
    require(policy_path.exists(), f"política {policy_path.stem!r} inexistente")
    equal(
        "policy_digest declarado por el registry",
        sha256_file(policy_path, policy_path.name),
        policy_digest,
    )

    refit_dir, forecast_dir = runs_root / refit_run_id, runs_root / forecast_run_id
    refit = read_manifest(refit_dir, refit_run_id, disease_id, CMD_REFIT)
    forecast = read_manifest(forecast_dir, forecast_run_id, disease_id, CMD_FORECAST)
    for etiqueta, man in ((CMD_REFIT, refit), (CMD_FORECAST, forecast)):
        equal(f"{etiqueta}: policy_digest", man.policy_digest, policy_digest)
    equal("forecast: dataset_id", forecast.dataset_id, refit.dataset_id)
    for clave in (*_SHARED_DIGESTS, *CHAIN_DIGESTS):
        equal(
            f"forecast: input_digests[{clave!r}]",
            forecast.input_digests.get(clave),
            input_digest(refit, clave, CMD_REFIT),
        )
    equal(
        "refit: final_selection_digest declarado por el registry",
        input_digest(refit, "final_selection_digest", CMD_REFIT),
        final_selection_digest,
    )

    seleccion = portfolio.read_selection(refit_dir, final_selection_digest)
    portfolio.check_universe(seleccion, geography_ids)
    reparto = portfolio.distribution(seleccion)
    for etiqueta, man in ((CMD_REFIT, refit), (CMD_FORECAST, forecast)):
        equal(f"{etiqueta}: motores", sorted(man.engines), sorted(reparto))
        equal(f"{etiqueta}: jobs", sorted(man.jobs), sorted(reparto))
    # Un artefacto obligatorio fuera del manifiesto dejaría de estar sellado por el run (R5.3).
    require_artifacts(refit, {SUMMARY_FILE: SCHEMA_REFIT_SUMMARY}, CMD_REFIT, exact=True)
    require_job_artifacts(refit, {_INDEX_PATH: SCHEMA_MODEL_INDEX}, CMD_REFIT)
    require_artifacts(forecast, _FORECAST_ARTIFACTS, CMD_FORECAST, exact=True)
    require_job_artifacts(forecast, _FORECAST_JOB_ARTIFACTS, CMD_FORECAST)

    resumen = read_summary(refit_dir, refit, reparto)
    refit_digest = sha256_file(refit_dir / SUMMARY_FILE, SUMMARY_FILE)
    equal(
        "forecast: refit_digest",
        input_digest(forecast, "refit_digest", CMD_FORECAST),
        refit_digest,
    )

    dataset_id = text_of(refit.dataset_id, "refit: dataset_id")
    dataset_digest = input_digest(refit, "dataset", CMD_REFIT)
    n_train, train_end, conteos = dataset_window(
        runs_root / dataset_id, disease_id, dataset_digest, geography_ids
    )
    for etiqueta, man in ((CMD_REFIT, refit), (CMD_FORECAST, forecast)):
        _check_counts(man.counts, conteos, etiqueta)
    # La ventana la fija el DATASET sellado; el resumen y los envelopes solo pueden repetirla.
    equal("refit: refit_summary: train_end", resumen.train_end, train_end)
    equal("refit: refit_summary: n_train_values", resumen.n_train_values, (n_train,))

    acceptance_digest = input_digest(refit, "acceptance_digest", CMD_REFIT)
    selection_digest = input_digest(refit, "selection_digest", CMD_REFIT)
    identidades = portfolio.validate_models(
        refit_dir,
        seleccion,
        reparto,
        portfolio.ModelExpectations(
            disease_id=disease_id,
            n_train=n_train,
            train_end=train_end,
            provenance={
                "acceptance_digest": acceptance_digest,
                "acceptance_run_id": resumen.acceptance_run_id,
                "code_commit": text_of(refit.code_commit, "refit: code_commit"),
                "dataset_digest": dataset_digest,
                "dataset_id": dataset_id,
                "policy_digest": policy_digest,
                "policy_name": policy_path.stem,
                "selection_digest": selection_digest,
                "selection_run_id": resumen.selection_run_id,
            },
        ),
    )
    check_lineage(forecast_dir, refit_run_id, refit_digest, reparto, conteos, train_end)
    # El veredicto de aceptación se ABRE y se verifica; enlazarlo por digest no demuestra que
    # exista, que sea del mismo dataset ni que haya salido positivo (R5.1).
    veredicto = validate_acceptance(
        runs_root / resumen.acceptance_run_id,
        run_id=resumen.acceptance_run_id,
        disease_id=disease_id,
        dataset_id=dataset_id,
        policy_digest=policy_digest,
        acceptance_digest=acceptance_digest,
        selection_digest=selection_digest,
        selection_run_id=resumen.selection_run_id,
        final_selection_digest=final_selection_digest,
    )

    resultado = VerifiedRunnerRuns(
        disease_id=disease_id,
        refit_run_id=refit_run_id,
        forecast_run_id=forecast_run_id,
        dataset_id=dataset_id,
        policy_digest=policy_digest,
        selection_digest=selection_digest,
        final_selection_digest=final_selection_digest,
        acceptance_run_id=veredicto.run_id,
        acceptance_digest=acceptance_digest,
        acceptance_scopes=veredicto.scopes,
        refit_digest=refit_digest,
        distribution=tuple(reparto.items()),
        models=tuple(identidades[clave] for clave in sorted(identidades)),
        n_train=n_train,
        train_end=train_end,
        counts=tuple(sorted(conteos.items())),
    )
    # Acción 4: el forecast publicable se valida por CONTENIDO, no sólo por su lineage.
    validate_forecast(forecast_dir, resultado, catalogo)
    return resultado
