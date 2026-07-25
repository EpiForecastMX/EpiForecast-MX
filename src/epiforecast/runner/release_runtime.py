"""C7.2-A/R15-C3 — insumos de EJECUCIÓN de un release: catálogo y exposición proyectada.

``inputs/exposure_<source_id>.csv`` es una PROYECCIÓN por ``cve_ent`` del snapshot INEGI, no el raw
que espera ``load_exposure_snapshot`` (que además leería ``config/exposicion.yaml`` del workspace).
Tratarlos como intercambiables dejaría al bundle dependiendo del equipo que lo construyó, así que
aquí vive un loader propio: puro, fail-closed y alimentado sólo por rutas relativas al bundle.

El contraste de esos valores contra las exposiciones SELLADAS del dataset lo hace el builder —es el
único que ve el dataset— y queda registrado en ``dataset_check``; el loader exige esa constancia y
que apunte al mismo dataset de la cadena. Además, reproducir el forecast con una exposición
distinta cambiaría los conteos de los perfiles en tasa: la comprobación de extremo a extremo la
cierra ``release_loader``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import pandas as pd

from epiforecast.data.epi_dataset_spec import BASE_SEXES, COL_CVE_ENT
from epiforecast.data.epi_geo_exposure import GeoCatalog, load_geo_catalog
from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    int_of,
    mapping_of,
    read_json,
    require,
    sha256_file,
    text_of,
)
from epiforecast.runner.release_contract import (
    RUNTIME_CONFIG_SCHEMA,
    check_bundle_path,
    check_digest,
)

RUNTIME_DIR = "runtime_inputs"
RUNTIME_CONFIG_FILE = "runtime_config.json"

SeriesId = tuple[str, str]


@dataclass(frozen=True, slots=True)
class RuntimeInputs:
    """Catálogo y exposición ya verificados, cargados EXCLUSIVAMENTE desde el bundle."""

    catalog: GeoCatalog
    exposure: dict[SeriesId, int]
    source_id: str
    reference: str
    cutoff: str
    columns_by_sex: dict[str, str]
    total_column: str | None
    catalog_digest: str
    exposure_digest: str
    exposure_source_digest: str


def _strict_positive_int(raw: object, label: str) -> int:
    """Entero de exposición: finito, entero exacto y estrictamente positivo (sin coerción laxa)."""
    if isinstance(raw, bool):
        raise ArtifactValidationError(f"{label}: se esperaba un entero, no {raw!r}")
    try:
        valor = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ArtifactValidationError(f"{label}: se esperaba un entero, no {raw!r}") from exc
    if not math.isfinite(valor) or not valor.is_integer():
        raise ArtifactValidationError(f"{label}: se esperaba un entero, no {raw!r}")
    entero = int(valor)
    require(entero > 0, f"{label}: exposición no positiva ({entero})")
    return entero


def read_projected_exposure(
    path: Path,
    columns_by_sex: Mapping[str, str],
    total_column: str | None,
    geography_ids: list[str],
    label: str,
) -> dict[SeriesId, int]:
    """``(cve_ent, sexo) -> exposición`` desde el CSV proyectado, con cobertura EXACTA del catálogo."""
    equal(f"{label}: sexos base declarados", sorted(columns_by_sex), sorted(BASE_SEXES))
    try:
        frame = pd.read_csv(path, dtype={COL_CVE_ENT: str})
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{label}: ilegible ({exc})") from exc
    columnas = [*columns_by_sex.values(), *([total_column] if total_column else [])]
    faltan = [c for c in (COL_CVE_ENT, *columnas) if c not in frame.columns]
    require(not faltan, f"{label}: faltan la(s) columna(s) {faltan}")

    exposicion: dict[SeriesId, int] = {}
    vistos: set[str] = set()
    for fila in frame.to_dict("records"):
        cve = text_of(fila[COL_CVE_ENT], f"{label}: cve_ent")
        require(cve not in vistos, f"{label}: {cve} está duplicado")
        vistos.add(cve)
        valores = {c: _strict_positive_int(fila[c], f"{label}: {cve}/{c}") for c in columnas}
        if total_column:
            equal(
                f"{label}: {cve}: {total_column} declarado",
                sum(valores[c] for c in columns_by_sex.values()),
                valores[total_column],
            )
        for sexo, columna in columns_by_sex.items():
            exposicion[(cve, sexo)] = valores[columna]
    esperado = sorted((geo, sexo) for geo in geography_ids for sexo in BASE_SEXES)
    equal(f"{label}: cobertura del catálogo", sorted(exposicion), esperado)
    return exposicion


def _payload_path(root: Path, raw: object, label: str) -> Path:
    path = root / check_bundle_path(raw, label)
    require(path.is_file(), f"{label}: ausente en el bundle")
    return path


def _checked_file(root: Path, spec: Mapping[str, Any], label: str) -> tuple[Path, str]:
    path = _payload_path(root, spec.get("path"), label)
    digest = check_digest(spec.get("sha256"), label)
    equal(f"{label}: digest", sha256_file(path, label), digest)
    return path, digest


def build_runtime_config(
    *,
    disease_id: str,
    dataset_config: Mapping[str, Any],
    catalog_path: str,
    catalog_digest: str,
    exposure_path: str,
    exposure_digest: str,
    dataset_id: str,
    dataset_digest: str,
    n_series: int,
) -> dict[str, Any]:
    """``runtime_config.v1``: contrato de EJECUCIÓN con rutas relativas al bundle.

    No se copia ``inputs/config_effective.json``: ese archivo lleva una ruta relativa al workspace
    (``config/geografia/…``) y describe cómo se construyó el dataset, no cómo se ejecuta el release.
    Su identidad viaja igualmente, como ``dataset_config_digest``.
    """
    who = "runtime_config"
    exposicion = mapping_of(dataset_config.get("exposure"), f"{who}: exposure del dataset")
    calendario = mapping_of(dataset_config.get("calendar"), f"{who}: calendar del dataset")
    columnas = mapping_of(exposicion.get("columns_by_sex"), f"{who}: columns_by_sex")
    equal(f"{who}: sexos base declarados", sorted(columnas), sorted(BASE_SEXES))
    total = exposicion.get("total_column")
    return {
        "schema": RUNTIME_CONFIG_SCHEMA,
        "disease_id": text_of(disease_id, f"{who}: disease_id"),
        "calendar": {
            "kind": text_of(calendario.get("kind"), f"{who}: calendar.kind"),
            "observation_lag_weeks": int_of(
                calendario.get("observation_lag_weeks"), f"{who}: observation_lag_weeks"
            ),
        },
        "expected_n_states": int_of(
            dataset_config.get("expected_n_states"), f"{who}: expected_n_states"
        ),
        "geo_catalog": {
            "path": check_bundle_path(catalog_path, f"{who}: geo_catalog"),
            "sha256": check_digest(catalog_digest, f"{who}: geo_catalog"),
        },
        "exposure": {
            "path": check_bundle_path(exposure_path, f"{who}: exposure"),
            "sha256": check_digest(exposure_digest, f"{who}: exposure"),
            "source_id": text_of(exposicion.get("source_id"), f"{who}: exposure.source_id"),
            "reference": text_of(exposicion.get("reference"), f"{who}: exposure.reference"),
            "cutoff": text_of(exposicion.get("cutoff"), f"{who}: exposure.cutoff"),
            "columns_by_sex": {str(k): str(v) for k, v in sorted(columnas.items())},
            "total_column": str(total) if total is not None else None,
            "source_digest": check_digest(
                exposicion.get("digest"), f"{who}: exposure.source_digest"
            ),
            # R15-C3: constancia SELLADA de que el builder contrastó el CSV proyectado contra las
            # exposiciones del dataset. El loader la exige; sin ella el bundle no es cargable.
            "dataset_check": {
                "dataset_id": text_of(dataset_id, f"{who}: dataset_id"),
                "dataset_digest": check_digest(dataset_digest, f"{who}: dataset_digest"),
                "series": int_of(n_series, f"{who}: series contrastadas"),
                "verified": True,
            },
        },
        "dataset_config_digest": check_digest(
            dataset_config.get("__digest__"), f"{who}: dataset_config_digest"
        ),
    }


def load_runtime_inputs(
    bundle_root: Path, *, expected_dataset_digest: str | None = None
) -> RuntimeInputs:
    """Catálogo + exposición del bundle, sin leer el workspace ni ``runs/``."""
    who = RUNTIME_CONFIG_FILE
    config_path = bundle_root / RUNTIME_DIR / RUNTIME_CONFIG_FILE
    require(config_path.is_file(), f"{who}: ausente en el bundle")
    config = read_json(config_path, who, RUNTIME_CONFIG_SCHEMA)
    text_of(config.get("disease_id"), f"{who}: disease_id")
    int_of(config.get("expected_n_states"), f"{who}: expected_n_states")
    mapping_of(config.get("calendar"), f"{who}: calendar")

    catalog_path, catalog_digest = _checked_file(
        bundle_root,
        mapping_of(config.get("geo_catalog"), f"{who}: geo_catalog"),
        f"{who}: catálogo",
    )
    exposicion = mapping_of(config.get("exposure"), f"{who}: exposure")
    exposure_path, exposure_digest = _checked_file(bundle_root, exposicion, f"{who}: exposición")
    try:
        catalogo = load_geo_catalog(catalog_path)
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{who}: catálogo ilegible ({exc})") from exc
    equal(f"{who}: entidades del catálogo", len(catalogo.cve_ents()), config["expected_n_states"])

    columnas = {
        str(k): str(v)
        for k, v in mapping_of(exposicion.get("columns_by_sex"), f"{who}: columns_by_sex").items()
    }
    total = exposicion.get("total_column")
    mapa = read_projected_exposure(
        exposure_path,
        columnas,
        str(total) if total is not None else None,
        catalogo.cve_ents(),
        f"{who}: exposición",
    )

    check = mapping_of(exposicion.get("dataset_check"), f"{who}: exposure.dataset_check")
    require(
        check.get("verified") is True,
        f"{who}: la exposición no se contrastó contra el dataset sellado",
    )
    equal(f"{who}: series contrastadas", int_of(check.get("series"), f"{who}: series"), len(mapa))
    digest_dataset = check_digest(check.get("dataset_digest"), f"{who}: dataset_digest")
    if expected_dataset_digest is not None:
        equal(f"{who}: dataset_digest contrastado", digest_dataset, expected_dataset_digest)

    return RuntimeInputs(
        catalog=catalogo,
        exposure=mapa,
        source_id=text_of(exposicion.get("source_id"), f"{who}: exposure.source_id"),
        reference=text_of(exposicion.get("reference"), f"{who}: exposure.reference"),
        cutoff=text_of(exposicion.get("cutoff"), f"{who}: exposure.cutoff"),
        columns_by_sex=columnas,
        total_column=str(total) if total is not None else None,
        catalog_digest=catalog_digest,
        exposure_digest=exposure_digest,
        exposure_source_digest=check_digest(
            exposicion.get("source_digest"), f"{who}: exposure.source_digest"
        ),
    )
