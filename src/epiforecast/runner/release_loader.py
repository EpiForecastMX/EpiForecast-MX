"""C7.2-A/R15.5 — verificación de un release bundle leyendo EXCLUSIVAMENTE el bundle.

Ni ``runs/``, ni ``config/``, ni el registry, ni una ruta absoluta del equipo: si el bundle no basta,
no es un release. Se comprueban, en este orden: manifest → inventario exacto → checksums →
identidad recomputada (el ``release_id`` tiene que volver a salir) → insumos de ejecución →
manifiestos de los runs de origen → selección y portafolio → capacidad de forecast de cada motor.

Todo fallo sale como ``ArtifactValidationError``; ningún traceback escapa (misma frontera de C7.1).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from epiforecast.runner import artifact_portfolio as portfolio
from epiforecast.runner.adapters import AdapterCapabilityError, final_forecaster
from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    int_of,
    mapping_of,
    read_json,
    require,
    sequence_of,
    sha256_file,
    text_of,
)
from epiforecast.runner.release_contract import MANIFEST_FILE, RELEASE_SCHEMA
from epiforecast.runner.release_runtime import RUNTIME_DIR, RuntimeInputs, load_runtime_inputs
from epiforecast.runner.release_sources import (
    ACCEPTANCE_FILE,
    ACCEPTANCE_MANIFEST,
    DIR_FORECAST,
    DIR_REFIT,
    DIR_SELECTION,
    FORECAST_PAYLOADS,
    MODEL_INDEX,
    RUN_MANIFEST,
    SELECTION_FILE,
    SUMMARY_FILE,
)
from epiforecast.runner.release_verify import (
    check_checksums,
    check_identity,
    check_inventory,
    check_manifest_shape,
    check_run_manifest,
    payload_inventory,
)

SeriesId = tuple[str, str]


@dataclass(frozen=True, slots=True)
class VerifiedRelease:
    """Bundle ya verificado: identidad, calendario, portafolio e insumos listos para pronosticar."""

    root: Path
    release_id: str
    disease_id: str
    chain: dict[str, str]
    origin: tuple[int, int]
    horizon: int
    engines: dict[str, int]
    counts: dict[str, int]
    payloads: dict[str, str]
    runtime: RuntimeInputs
    selection: dict[SeriesId, str]
    interval_method: str
    uncertainty_available: bool


def _check_selection(
    root: Path, runtime: RuntimeInputs, engines: Mapping[str, int]
) -> dict[SeriesId, str]:
    """La selección congelada del bundle describe el mismo portafolio que declara el manifest."""
    seleccion = portfolio.read_selection(
        root / DIR_SELECTION, sha256_file(root / DIR_SELECTION / SELECTION_FILE, SELECTION_FILE)
    )
    portfolio.check_universe(seleccion, runtime.catalog.cve_ents())
    equal("release: reparto por motor", portfolio.distribution(seleccion), dict(engines))
    return seleccion


def bootstrap_engines() -> None:
    """Puebla el registry de adapters (mismo bootstrap que usa el worker del runner).

    Importa SOFTWARE, no datos: la reproducción sólo consume el estado sellado del bundle y sus
    ``runtime_inputs``. Las YAML de los motores gobiernan el AJUSTE, que aquí no vuelve a ocurrir.
    """
    import epiforecast.runner.engines  # noqa: F401  (auto-registro por import)


def _check_models(root: Path, verified: VerifiedRelease) -> None:
    """Cada motor carga sus modelos DESDE el bundle y ofrece la capacidad de forecast final."""
    from epiforecast.runner import final_models as fm

    bootstrap_engines()
    identidades: dict[SeriesId, str] = {}
    for engine, esperados in verified.engines.items():
        who = f"release/refit/{engine}"
        try:
            final_forecaster(engine)
        except AdapterCapabilityError as exc:
            raise ArtifactValidationError(f"{who}: {exc}") from exc
        try:
            modelos = fm.load_models(root / DIR_REFIT, engine)  # re-verifica envelope y estado
        except IO_ERRORS as exc:
            raise ArtifactValidationError(f"{who}: modelos no cargables ({exc})") from exc
        equal(f"{who}: modelos cargados", len(modelos), esperados)
        for envelope, _estado in modelos:
            clave = mapping_of(envelope.get("series_key"), f"{who}: series_key")
            serie = (
                text_of(clave.get("geography_id"), f"{who}: geography_id"),
                text_of(clave.get("sex"), f"{who}: sex"),
            )
            require(serie not in identidades, f"{who}: {serie} tiene más de un modelo final")
            identidades[serie] = engine
            equal(f"{who}: motor de {serie}", engine, verified.selection.get(serie))
            equal(
                f"{who}: train_end de {serie}",
                tuple(envelope.get("train_end") or ()),
                verified.origin,
            )
    equal("release: modelos finales", sorted(identidades), sorted(verified.selection))


def verify_bundle(root: Path) -> VerifiedRelease:
    """Verifica el bundle ENTERO sin salir de él y devuelve lo necesario para reproducir."""
    require(root.is_dir(), f"release: no existe el bundle {root.name}")
    require((root / MANIFEST_FILE).is_file(), f"release: falta {MANIFEST_FILE}")
    manifest = read_json(root / MANIFEST_FILE, MANIFEST_FILE, RELEASE_SCHEMA)
    check_manifest_shape(manifest)
    inventario = payload_inventory(manifest)
    check_inventory(root, inventario)
    check_checksums(root, inventario)
    digests = {ruta: datos[0] for ruta, datos in inventario.items()}
    release_id, _ = check_identity(manifest, digests)

    cadena = {str(k): str(v) for k, v in manifest["chain"].items()}
    disease_id = text_of(manifest.get("disease_id"), f"{MANIFEST_FILE}: disease_id")
    equal(
        f"{MANIFEST_FILE}: runtime_inputs",
        sorted(sequence_of(manifest.get("runtime_inputs"), f"{MANIFEST_FILE}: runtime_inputs")),
        sorted(p for p in digests if p.startswith(f"{RUNTIME_DIR}/")),
    )
    runtime = load_runtime_inputs(root, expected_dataset_digest=cadena.get("dataset_digest"))

    calendario = mapping_of(manifest.get("calendar"), f"{MANIFEST_FILE}: calendar")
    origen = sequence_of(calendario.get("origin"), f"{MANIFEST_FILE}: calendar.origin")
    equal(f"{MANIFEST_FILE}: calendar.origin", len(origen), 2)
    engines = {
        text_of(k, f"{MANIFEST_FILE}: engines"): int_of(v, f"{MANIFEST_FILE}: engines[{k!r}]")
        for k, v in mapping_of(manifest.get("engines"), f"{MANIFEST_FILE}: engines").items()
    }
    require(engines, f"{MANIFEST_FILE}: el release no declara motores")

    check_run_manifest(
        root,
        DIR_SELECTION,
        ACCEPTANCE_MANIFEST,
        run_id=cadena["acceptance_run_id"],
        disease_id=disease_id,
        command="benchmark",
        required={ACCEPTANCE_FILE, SELECTION_FILE},
        digests={
            f"{DIR_SELECTION}/{ACCEPTANCE_FILE}": digests[f"{DIR_SELECTION}/{ACCEPTANCE_FILE}"],
            f"{DIR_SELECTION}/{SELECTION_FILE}": digests[f"{DIR_SELECTION}/{SELECTION_FILE}"],
        },
    )
    check_run_manifest(
        root,
        DIR_REFIT,
        RUN_MANIFEST,
        run_id=cadena["refit_run_id"],
        disease_id=disease_id,
        command="refit",
        required={SUMMARY_FILE, *(f"models/{e}/{MODEL_INDEX}" for e in engines)},
        digests=digests,
    )
    check_run_manifest(
        root,
        DIR_FORECAST,
        RUN_MANIFEST,
        run_id=cadena["forecast_run_id"],
        disease_id=disease_id,
        command="forecast",
        required=set(FORECAST_PAYLOADS),
        digests=digests,
    )

    intervalos = mapping_of(manifest.get("intervals"), f"{MANIFEST_FILE}: intervals")
    incertidumbre = intervalos.get("uncertainty_available")
    require(
        isinstance(incertidumbre, bool),
        f"{MANIFEST_FILE}: intervals.uncertainty_available debe ser booleano",
    )
    verified = VerifiedRelease(
        root=root,
        release_id=release_id,
        disease_id=disease_id,
        chain=cadena,
        origin=(int_of(origen[0], "origin"), int_of(origen[1], "origin")),
        horizon=int_of(calendario.get("horizon"), f"{MANIFEST_FILE}: calendar.horizon"),
        engines=dict(sorted(engines.items())),
        counts={
            str(k): int_of(v, f"{MANIFEST_FILE}: counts[{k!r}]")
            for k, v in mapping_of(manifest.get("counts"), f"{MANIFEST_FILE}: counts").items()
        },
        payloads=digests,
        runtime=runtime,
        selection=_check_selection(root, runtime, engines),
        interval_method=text_of(
            intervalos.get("interval_method"), f"{MANIFEST_FILE}: intervals.interval_method"
        ),
        uncertainty_available=bool(incertidumbre),
    )
    require(verified.horizon >= 1, f"release: horizonte inválido {verified.horizon}")
    _check_models(root, verified)
    return verified
