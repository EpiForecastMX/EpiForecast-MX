"""C7.3a — compilador GENÉRICO de un release a filas de consumo.

Dos modos, y la diferencia no es cosmética:

- ``candidate``: escribe sólo bajo un output root de staging EXPLÍCITO. Admite cualquier
  padecimiento con release verificable, incluido uno ``trained``, porque compilar no es publicar.
- ``public``: exige ``lifecycle=published`` **y** que el puntero público activo apunte a ESE
  ``release_id``. Mientras el puntero no exista (C7.5), este modo no puede usarse: falla cerrado.

El contrato de salida conserva identidad completa y procedencia por fila, así que ningún consumidor
necesita re-inferir nada —ni por nombre de archivo, ni por listas escritas a mano—. Los 47 productos
derivados se atribuyen al PORTAFOLIO; inventarles un motor sería mentir sobre quién los produjo.

Ni un padecimiento, motor o conteo aparece escrito aquí: todo sale del registry y del bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from epiforecast import registry
from epiforecast.data.epi_dataset_spec import (
    BASE_SEXES,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
    FREQ_EPI_WEEK,
    GEO_LEVEL_ESTADO,
)
from epiforecast.runner import contracts as ct
from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    require,
    text_of,
)
from epiforecast.runner.release_contract import INTERVAL_METHOD_NONE
from epiforecast.runner.release_loader import VerifiedRelease, verify_bundle
from epiforecast.runner.release_store import release_path

from .status import ProspectiveStatus

MODE_CANDIDATE = "candidate"
MODE_PUBLIC = "public"
MODES: tuple[str, str] = (MODE_CANDIDATE, MODE_PUBLIC)

LIFECYCLE_PUBLISHED = "published"
PORTFOLIO = "portfolio"
# Etiqueta VISIBLE, no un comentario: el consumidor final tiene que poder leerla.
UNCERTAINTY_LABEL = "Pronóstico puntual; sin intervalo de incertidumbre"
# Cola de la etiqueta pública cuando el release no trae intervalos. Se AÑADE al estado prospectivo
# porque son dos advertencias distintas: una dice qué tan validado está, la otra qué no contiene.
POINT_ONLY_SUFFIX = "pronóstico puntual sin intervalos"
LABEL_SEPARATOR = " · "

# Rutas del repo donde vive lo PÚBLICO. `candidate` no puede escribir dentro de ninguna.
PUBLIC_DIRS: tuple[str, ...] = ("reports", "data", "models", "epibot", "web", "artifacts")

PUBLICATION_COLUMNS: tuple[str, ...] = (
    "release_id",
    "disease_id",
    COL_GEO_LEVEL,
    COL_GEO_ID,
    COL_SEX,
    "frequency",
    COL_EPI_YEAR,
    COL_EPI_WEEK,
    "ds",
    "yhat_cases",
    "engine",
    "derived",
    "origin_epi_year",
    "origin_epi_week",
    "horizon",
    "forecast_run_id",
    "refit_digest",
    "interval_method",
    "yhat_lower",
    "yhat_upper",
    "uncertainty_label",
)


@dataclass(frozen=True, slots=True)
class Compilation:
    """Filas compiladas de un release, con su modo, padecimiento y estado prospectivo."""

    mode: str
    disease_id: str
    release_id: str
    rows: pd.DataFrame
    verified: VerifiedRelease
    disease: registry.Disease
    status: ProspectiveStatus | None = None

    @property
    def base_rows(self) -> pd.DataFrame:
        return self.rows[~self.rows["derived"]]

    @property
    def derived_rows(self) -> pd.DataFrame:
        return self.rows[self.rows["derived"]]

    @property
    def label(self) -> str:
        """Etiqueta pública derivada: estado prospectivo + advertencia de incertidumbre."""
        require(
            self.status is not None, f"{self.disease_id}: no hay estado prospectivo que mostrar"
        )
        assert self.status is not None  # noqa: S101 — para mypy; `require` ya falló si era None
        return publication_label(self.status, self.verified)


def publication_label(status: ProspectiveStatus, verified: VerifiedRelease) -> str:
    """Una sola fuente para la etiqueta que verán los cuatro canales.

    Se compone de DATOS: los conteos salen del estado validado y la cola point-only del propio
    release. Ni el texto del avance ni el ``n/4`` se escriben a mano en ningún puente.
    """
    partes = [status.progress_label()]
    if not verified.uncertainty_available:
        partes.append(POINT_ONLY_SUFFIX)
    return LABEL_SEPARATOR.join(partes)


def check_mode(mode: str) -> str:
    require(mode in MODES, f"modo de compilación desconocido: {mode!r} (esperado {list(MODES)})")
    return mode


def repo_root() -> Path:
    """Raíz del repo desde ``src/epiforecast/publication/``."""
    return Path(__file__).resolve().parents[3]


def check_staging_root(output_root: Path, repo_root_path: Path | None = None) -> Path:
    """Un output de ``candidate`` NUNCA cae dentro de una ruta pública del repo."""
    repo_root_path = repo_root_path if repo_root_path is not None else repo_root()
    destino = output_root.resolve()
    raiz = repo_root_path.resolve()
    if destino == raiz or raiz in destino.parents:
        relativa = destino.relative_to(raiz)
        primera = relativa.parts[0] if relativa.parts else ""
        require(
            primera not in PUBLIC_DIRS,
            f"candidate: {relativa.as_posix()} está dentro de una ruta pública del repo "
            f"({primera}/); el modo candidate sólo escribe en staging",
        )
    return destino


def _check_status(
    disease: registry.Disease, release_id: str, mode: str, status: ProspectiveStatus | None
) -> None:
    """El estado prospectivo es parte del contrato de publicación, no un adorno.

    En ``candidate`` se acepta inyectado y, si viene, tiene que ser el de ESTE release. En ``public``
    es obligatorio: publicar sin poder mostrar bajo qué condición se autorizó es justo el fallo que
    R74-P0 describe. Un ``FAIL`` no habilita el modo público en ninguna circunstancia.
    """
    if status is not None:
        equal(f"{disease.id}: disease_id del estado prospectivo", status.disease_id, disease.id)
        equal(f"{disease.id}: release_id del estado prospectivo", status.release_id, release_id)
    if mode == MODE_CANDIDATE:
        return
    require(
        status is not None,
        f"{disease.id}: el modo public exige un estado prospectivo validado para {release_id}",
    )
    assert status is not None  # noqa: S101 — para mypy; `require` ya falló si era None
    require(
        status.publishable,
        f"{disease.id}: veredicto {status.verdict} del gate prospectivo; no habilita publicación",
    )


def _check_lifecycle(disease: registry.Disease, mode: str, pointer_release_id: str | None) -> None:
    """El gate que separa compilar de publicar."""
    if mode == MODE_CANDIDATE:
        return
    equal(f"{disease.id}: lifecycle para publicar", disease.lifecycle, LIFECYCLE_PUBLISHED)
    require(
        pointer_release_id is not None,
        f"{disease.id}: el modo public exige un puntero público activo "
        "(public_release_pointer.v1, C7.5); sin él no se publica nada",
    )
    equal(
        f"{disease.id}: el puntero público apunta a otro release",
        pointer_release_id,
        str(disease.artifact_source.release_id),
    )


def _release_id_of(disease: registry.Disease) -> str:
    require(
        disease.artifact_backend == registry.BACKEND_RUNNER_RELEASE,
        f"{disease.id}: compilar exige backend {registry.BACKEND_RUNNER_RELEASE!r}, "
        f"no {disease.artifact_backend!r}",
    )
    return text_of(disease.artifact_source.release_id, f"{disease.id}: release_id")


def _rows(verified: VerifiedRelease, disease_id: str) -> pd.DataFrame:
    """El ``forecast.csv`` sellado + identidad y procedencia por fila."""
    from epiforecast.runner.release_reproduce import read_bundled_frame  # lectura sin pérdida
    from epiforecast.runner.release_sources import DIR_FORECAST

    frame = read_bundled_frame(
        verified.root / DIR_FORECAST / "forecast.csv", f"{disease_id}: forecast.csv"
    )
    try:
        ct.validate_forecast_frame(frame)
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{disease_id}: forecast sellado inválido ({exc})") from exc

    seleccion = verified.selection
    es_base = (frame[COL_GEO_LEVEL] == GEO_LEVEL_ESTADO) & frame[COL_SEX].isin(BASE_SEXES)
    motores = [
        seleccion[(str(g), str(s))] if base else PORTFOLIO
        for g, s, base in zip(frame[COL_GEO_ID], frame[COL_SEX], es_base, strict=True)
    ]
    salida = pd.DataFrame(
        {
            "release_id": verified.release_id,
            "disease_id": disease_id,
            COL_GEO_LEVEL: frame[COL_GEO_LEVEL].astype(str),
            COL_GEO_ID: frame[COL_GEO_ID].astype(str),
            COL_SEX: frame[COL_SEX].astype(str),
            "frequency": FREQ_EPI_WEEK,
            COL_EPI_YEAR: frame[COL_EPI_YEAR].astype(int),
            COL_EPI_WEEK: frame[COL_EPI_WEEK].astype(int),
            "ds": frame["ds"].astype(str),
            "yhat_cases": frame[ct.COL_Y_PRED].astype(float),
            "engine": motores,
            "derived": ~es_base,
            "origin_epi_year": verified.origin[0],
            "origin_epi_week": verified.origin[1],
            "horizon": frame[ct.COL_HORIZON].astype(int),
            "forecast_run_id": verified.chain["forecast_run_id"],
            "refit_digest": verified.chain["refit_digest"],
            "interval_method": INTERVAL_METHOD_NONE,
            "yhat_lower": pd.NA,
            "yhat_upper": pd.NA,
            "uncertainty_label": UNCERTAINTY_LABEL,
        },
        columns=list(PUBLICATION_COLUMNS),
    )
    # Orden canónico: dos compilaciones del mismo release dan los MISMOS bytes.
    orden = [COL_GEO_LEVEL, COL_GEO_ID, COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK]
    salida = salida.sort_values(orden).reset_index(drop=True)

    equal(f"{disease_id}: filas compiladas", len(salida), len(frame))
    equal(
        f"{disease_id}: series base",
        int((~salida["derived"]).sum()),
        len(seleccion) * verified.horizon,
    )
    require(
        salida.loc[salida["derived"], "engine"].eq(PORTFOLIO).all(),
        f"{disease_id}: un producto derivado no puede atribuirse a un motor concreto",
    )
    return salida


def compile_release(
    *,
    disease_id: str,
    mode: str,
    releases_root: Path,
    pointer_release_id: str | None = None,
    status: ProspectiveStatus | None = None,
) -> Compilation:
    """Compila el release DECLARADO del padecimiento. No escribe nada: sólo produce las filas."""
    check_mode(mode)
    try:
        disease = registry.require(disease_id)
    except (KeyError, ValueError) as exc:
        raise ArtifactValidationError(f"padecimiento desconocido: {disease_id!r}") from exc
    release_id = _release_id_of(disease)
    _check_lifecycle(disease, mode, pointer_release_id)
    _check_status(disease, release_id, mode, status)

    destino = release_path(releases_root, disease.id, release_id)
    require(
        destino.is_dir(), f"{disease.id}: el release declarado no está en la sede: {release_id}"
    )
    verified = verify_bundle(destino)
    equal(f"{disease.id}: release_id de la sede", verified.release_id, release_id)
    equal(f"{disease.id}: disease_id del release", verified.disease_id, disease.id)

    return Compilation(
        mode=mode,
        disease_id=disease.id,
        release_id=release_id,
        rows=_rows(verified, disease.id),
        verified=verified,
        disease=disease,
        status=status,
    )
