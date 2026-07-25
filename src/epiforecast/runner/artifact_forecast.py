"""C7.1/Acción 4 — el forecast PUBLICABLE, validado por contenido y no sólo por lineage.

Que ``lineage.json`` diga 64+47 no demuestra que ``forecast.csv`` tenga las filas correctas. Aquí
se abren los tres artefactos y se exige el contrato completo: universo de series, horizonte
contiguo desde el origen, ``ds`` del calendario MMWR, claves únicas, valores utilizables,
`point-only`, el origen por job y por modelo, y las derivadas **materializadas desde las bases** con
la reconciliación del propio runner.

Todas las cantidades se derivan de lo ya verificado (``VerifiedRunnerRuns``, ``lineage.json`` y el
catálogo geográfico): ni el padecimiento, ni 64/47/111, ni 52 ni 2026-W26 se escriben aquí.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from epiforecast.data.epi_calendar import ds_for, shift
from epiforecast.data.epi_dataset_spec import (
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
    GEO_LEVEL_ESTADO,
)
from epiforecast.data.epi_geo_exposure import GeoCatalog
from epiforecast.runner import contracts as ct
from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    int_of,
    read_json,
    require,
)
from epiforecast.runner.artifact_portfolio import ModelIdentity
from epiforecast.runner.evaluation import RECON_TOL, derive_forecast_products

if TYPE_CHECKING:  # sólo para tipar; en runtime lo pasa el llamador
    from epiforecast.runner.artifact_validation import VerifiedRunnerRuns

FORECAST_FILE = "forecast.csv"
BASE_FILE = "forecast_base.csv"
INVENTORY_FILE = "model_inventory.csv"
JOB_BASE = "artifacts/{engine}/forecast_base.csv"
PORTFOLIO_ENGINE = "portfolio"
FINAL_FOLD = "final_refit"
_KEY = [COL_GEO_LEVEL, COL_GEO_ID, COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK]
_INVENTORY_COLUMNS = (
    COL_GEO_ID,
    COL_SEX,
    "engine",
    "n_train",
    "train_end",
    "state_format",
    "state_digest",
)

Period = tuple[int, int]
SeriesId = tuple[str, str]


def _read_csv(path: Path, label: str, columns: tuple[str, ...]) -> pd.DataFrame:
    """CSV de un artefacto sellado, con sus columnas obligatorias y sin coerción de identidad."""
    try:
        frame = pd.read_csv(path, dtype={COL_GEO_ID: str}, low_memory=False)
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{label}: ilegible ({exc})") from exc
    faltan = [c for c in columns if c not in frame.columns]
    require(not faltan, f"{label}: faltan columnas {faltan}")
    return frame


def _validate_frame(frame: pd.DataFrame, label: str) -> None:
    """Contrato ``forecast.v1`` del runner: una sola implementación; aquí sólo se traduce."""
    try:
        ct.validate_forecast_frame(frame)
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{label}: {exc}") from exc


def _horizon_periods(origin: Period, horizon: int) -> list[tuple[int, int, int]]:
    """``(horizonte, año, semana)`` contiguos desde el periodo siguiente al origen."""
    salida, actual = [], origin
    for h in range(1, horizon + 1):
        actual = shift(actual[0], actual[1], 1)
        salida.append((h, actual[0], actual[1]))
    return salida


def _series_of(frame: pd.DataFrame) -> set[SeriesId]:
    return {(str(g), str(s)) for g, s in zip(frame[COL_GEO_ID], frame[COL_SEX], strict=True)}


def _check_invariants(
    frame: pd.DataFrame, label: str, run_id: str, disease_id: str, engine: str = PORTFOLIO_ENGINE
) -> None:
    """Procedencia constante: el portafolio no es la salida de un motor ni de un fold cualquiera."""
    for columna, esperado in (
        (ct.COL_RUN_ID, run_id),
        ("disease_id", disease_id),
        (ct.COL_ENGINE, engine),
        (ct.COL_FOLD, FINAL_FOLD),
    ):
        equal(f"{label}: {columna}", sorted(set(frame[columna])), [esperado])


def _check_calendar(frame: pd.DataFrame, label: str, origin: Period, horizon: int) -> None:
    """Origen constante, horizonte 1..H contiguo y ``ds`` coherente con el calendario MMWR."""
    equal(f"{label}: origin", sorted(set(frame[ct.COL_ORIGIN_EPI_YEAR])), [origin[0]])
    equal(f"{label}: origin_epi_week", sorted(set(frame[ct.COL_ORIGIN_EPI_WEEK])), [origin[1]])
    observados = sorted(
        {
            (
                int_of(h, f"{label}: horizon"),
                int_of(y, f"{label}: epi_year"),
                int_of(w, f"{label}: epi_week"),
            )
            for h, y, w in zip(
                frame[ct.COL_HORIZON], frame[COL_EPI_YEAR], frame[COL_EPI_WEEK], strict=True
            )
        }
    )
    equal(f"{label}: horizonte y periodos", observados, _horizon_periods(origin, horizon))
    esperado_ds = {(y, w): ds_for(y, w).isoformat() for _, y, w in observados}
    for year, week, ds in zip(frame[COL_EPI_YEAR], frame[COL_EPI_WEEK], frame["ds"], strict=True):
        clave = (int(year), int(week))
        if str(ds) != esperado_ds[clave]:
            raise ArtifactValidationError(
                f"{label}: ds {ds!r} no corresponde a {clave} ({esperado_ds[clave]})"
            )


def _check_base(base: pd.DataFrame, label: str, series: set[SeriesId], horizon: int) -> None:
    """Las series base seleccionadas, cada una con su horizonte completo y sin claves repetidas."""
    equal(f"{label}: nivel geográfico", sorted(set(base[COL_GEO_LEVEL])), [GEO_LEVEL_ESTADO])
    equal(f"{label}: universo de series", sorted(_series_of(base)), sorted(series))
    equal(f"{label}: filas", len(base), len(series) * horizon)
    require(not base.duplicated(_KEY).any(), f"{label}: claves duplicadas")


def _check_point_only(frame: pd.DataFrame, label: str) -> None:
    """El forecast C5 está declarado ``point-only``.

    El contrato genérico admite intervalos conjuntamente presentes —otros motores o padecimientos
    podrán tenerlos—, así que la restricción se impone AQUÍ, en el borde de este artefacto, y no
    endureciendo ``validate_forecast_frame`` para todos (R11.3).
    """
    for columna in (ct.COL_YHAT_LOWER, ct.COL_YHAT_UPPER):
        presentes = int(frame[columna].notna().sum())
        require(
            not presentes, f"{label}: {columna} tiene {presentes} valores; se declaró point-only"
        )


def _check_jobs(
    forecast_dir: Path,
    base: pd.DataFrame,
    engines: dict[SeriesId, str],
    run_id: str,
    disease_id: str,
    origin: Period,
    horizon: int,
) -> None:
    """Cada job cumple el contrato COMPLETO antes de consolidarse, y el consolidado es su unión.

    Comparar sólo la predicción numérica dejaba pasar metadata ajena (otro ``run_id``, otro
    padecimiento, un intervalo suelto) porque el número coincidía (R11.2).
    """
    trozos = []
    for engine in sorted(set(engines.values())):
        who = f"forecast/{engine}: {BASE_FILE}"
        parcial = _read_csv(
            forecast_dir / JOB_BASE.format(engine=engine), who, ct.FORECAST_COLUMNS
        )
        _validate_frame(parcial, who)
        _check_invariants(parcial, who, run_id, disease_id, engine)
        _check_calendar(parcial, who, origin, horizon)
        _check_point_only(parcial, who)
        equal(f"{who}: nivel geográfico", sorted(set(parcial[COL_GEO_LEVEL])), [GEO_LEVEL_ESTADO])
        suyas = sorted(k for k, e in engines.items() if e == engine)
        equal(f"{who}: series del motor", sorted(_series_of(parcial)), suyas)
        equal(f"{who}: filas", len(parcial), len(suyas) * horizon)
        require(not parcial.duplicated(_KEY).any(), f"{who}: claves duplicadas")
        # El consolidado atribuye el portafolio: es la ÚNICA columna que puede diferir.
        trozos.append(parcial.assign(**{ct.COL_ENGINE: PORTFOLIO_ENGINE}))
    unidos = pd.concat(trozos, ignore_index=True).sort_values(_KEY).reset_index(drop=True)
    consolidado = base.sort_values(_KEY).reset_index(drop=True)
    equal(f"forecast: filas de los jobs frente a {BASE_FILE}", len(unidos), len(consolidado))
    for columna in ct.FORECAST_COLUMNS:
        izq, der = unidos[columna], consolidado[columna]
        if not izq.equals(der) and not (izq.isna().all() and der.isna().all()):
            raise ArtifactValidationError(
                f"forecast: {BASE_FILE} no coincide con los jobs en {columna!r}"
            )


def _check_inventory(forecast_dir: Path, modelos: dict[SeriesId, ModelIdentity]) -> None:
    """``model_inventory.csv`` contra la identidad SELLADA de cada modelo final (R11.1).

    Que los digests fueran todos distintos no probaba identidad y además prohibía un caso legítimo:
    dos series pueden serializar estados byte-idénticos. El contrato es la igualdad por
    ``SeriesKey`` contra lo que ya verificó el portafolio.
    """
    who = f"forecast: {INVENTORY_FILE}"
    inventario = _read_csv(forecast_dir / INVENTORY_FILE, who, _INVENTORY_COLUMNS)
    require(not inventario.duplicated([COL_GEO_ID, COL_SEX]).any(), f"{who}: claves duplicadas")
    filas = {(str(f[COL_GEO_ID]), str(f[COL_SEX])): f for f in inventario.to_dict("records")}
    equal(f"{who}: universo de series", sorted(filas), sorted(modelos))
    for clave, fila in filas.items():
        sellado = modelos[clave]
        equal(f"{who}: motor de {clave}", fila["engine"], sellado.engine)
        equal(
            f"{who}: n_train de {clave}",
            int_of(fila["n_train"], f"{who}: n_train de {clave}"),
            sellado.n_train,
        )
        equal(f"{who}: train_end de {clave}", str(fila["train_end"]), str(list(sellado.train_end)))
        equal(f"{who}: state_format de {clave}", fila["state_format"], sellado.state_format)
        equal(f"{who}: state_digest de {clave}", fila["state_digest"], sellado.state_digest)


def _check_products(
    base: pd.DataFrame, full: pd.DataFrame, label: str, catalog: GeoCatalog
) -> None:
    """Las derivadas se MATERIALIZAN sumando las bases, con la reconciliación del runner."""
    try:
        esperado = derive_forecast_products(base[list(ct.FORECAST_COLUMNS)].copy(), catalog)
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{label}: los productos no reconcilian ({exc})") from exc
    izq = esperado.sort_values(_KEY).reset_index(drop=True)
    der = full[list(ct.FORECAST_COLUMNS)].sort_values(_KEY).reset_index(drop=True)
    equal(f"{label}: productos materializados", len(izq), len(der))
    for columna in _KEY:
        if not izq[columna].astype(str).equals(der[columna].astype(str)):
            raise ArtifactValidationError(f"{label}: los productos difieren en {columna!r}")
    peor = float((izq[ct.COL_Y_PRED] - der[ct.COL_Y_PRED]).abs().max())
    require(
        peor <= RECON_TOL, f"{label}: un producto no es la suma de sus bases (máx |Δ|={peor:.3g})"
    )


def validate_forecast(
    forecast_dir: Path, verified: VerifiedRunnerRuns, catalog: GeoCatalog
) -> None:
    """Valida por CONTENIDO los tres artefactos publicables del forecast (Acción 4)."""
    lineage = read_json(forecast_dir / "lineage.json", "forecast: lineage")
    horizon = int_of(lineage.get("horizon"), "forecast: lineage: horizon")
    require(horizon >= 1, f"forecast: horizonte inválido {horizon}")
    modelos = {m.series: m for m in verified.models}
    engines = {clave: m.engine for clave, m in modelos.items()}
    conteos = dict(verified.counts)

    quien = f"forecast: {BASE_FILE}"
    base = _read_csv(forecast_dir / BASE_FILE, quien, ct.FORECAST_COLUMNS)
    _validate_frame(base, quien)
    _check_invariants(base, quien, verified.forecast_run_id, verified.disease_id)
    _check_calendar(base, quien, verified.train_end, horizon)
    _check_base(base, quien, set(engines), horizon)
    _check_point_only(base, quien)
    _check_jobs(
        forecast_dir,
        base,
        engines,
        verified.forecast_run_id,
        verified.disease_id,
        verified.train_end,
        horizon,
    )
    _check_inventory(forecast_dir, modelos)

    quien = f"forecast: {FORECAST_FILE}"
    full = _read_csv(forecast_dir / FORECAST_FILE, quien, ct.FORECAST_COLUMNS)
    _validate_frame(full, quien)
    _check_invariants(full, quien, verified.forecast_run_id, verified.disease_id)
    _check_calendar(full, quien, verified.train_end, horizon)
    equal(f"{quien}: filas", len(full), conteos["products"] * horizon)
    require(not full.duplicated(_KEY).any(), f"{quien}: claves duplicadas")
    _check_point_only(full, quien)
    productos = {
        (str(n), str(g), str(s))
        for n, g, s in zip(full[COL_GEO_LEVEL], full[COL_GEO_ID], full[COL_SEX], strict=True)
    }
    equal(f"{quien}: productos", len(productos), conteos["products"])
    _check_products(base, full, quien, catalog)
