"""C7.2-A/R15.5 — reproducción del forecast publicable USANDO SÓLO el bundle.

Que los archivos existan y sus digests cuadren no demuestra que el release sirva: hay que cargar los
modelos finales, pronosticar el horizonte declarado con la exposición y el catálogo del propio
bundle, derivar los productos y obtener EL MISMO frame que viaja dentro. Eso es lo que convierte un
directorio verificado en un release restaurable.

Reutiliza las piezas del runner (``final_models``, la capacidad ``forecast_state`` de cada adapter y
``derive_forecast_products``): no hay un segundo camino de pronóstico ni un ``if engine == ...``.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path

import pandas as pd

from epiforecast.artifacts.transforms import TransformContract
from epiforecast.data.epi_calendar import ds_for, shift
from epiforecast.data.epi_dataset_spec import (
    COL_DS,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
    GEO_LEVEL_ESTADO,
)
from epiforecast.runner import contracts as ct
from epiforecast.runner import final_models as fm
from epiforecast.runner.adapters import AdapterCapabilityError, final_forecaster
from epiforecast.runner.artifact_forecast import BASE_FILE, FORECAST_FILE, PORTFOLIO_ENGINE
from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    mapping_of,
    require,
    text_of,
)
from epiforecast.runner.evaluation import derive_forecast_products
from epiforecast.runner.release_contract import INTERVAL_METHOD_NONE
from epiforecast.runner.release_loader import VerifiedRelease, bootstrap_engines
from epiforecast.runner.release_sources import DIR_FORECAST, DIR_REFIT

Period = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Reproduction:
    """Frames reproducidos desde el bundle y su desviación máxima frente a los que viajan dentro."""

    base: pd.DataFrame
    products: pd.DataFrame
    max_delta_base: float
    max_delta_products: float


def horizon_periods(origin: Period, horizon: int) -> list[Period]:
    """Los ``horizon`` periodos MMWR posteriores al origen (nunca incluye el origen)."""
    periodos: list[Period] = []
    actual = origin
    for _ in range(horizon):
        actual = shift(actual[0], actual[1], 1)
        periodos.append(actual)
    return periodos


def _rows(
    envelope: dict[str, object],
    preds: dict[Period, float],
    periods: list[Period],
    origin: Period,
    run_id: str,
) -> list[dict[str, object]]:
    clave = mapping_of(envelope.get("series_key"), "release: series_key")
    geo = text_of(clave.get("geography_id"), "release: geography_id")
    sexo = text_of(clave.get("sex"), "release: sex")
    equal(
        f"release: nivel geográfico de {geo}/{sexo}",
        clave.get("geography_level"),
        GEO_LEVEL_ESTADO,
    )
    equal(f"release: cobertura del horizonte de {geo}/{sexo}", sorted(preds), sorted(periods))
    filas = []
    for h, periodo in enumerate(periods, start=1):
        valor = float(preds[periodo])
        require(
            valor == valor and abs(valor) != float("inf") and valor >= 0,
            f"release: predicción inválida en {geo}/{sexo} {periodo}: {valor!r}",
        )
        filas.append(
            {
                ct.COL_RUN_ID: run_id,
                ct.COL_ENGINE: PORTFOLIO_ENGINE,
                ct.COL_FOLD: fm.FINAL_FOLD_ID,
                ct.COL_ORIGIN_EPI_YEAR: origin[0],
                ct.COL_ORIGIN_EPI_WEEK: origin[1],
                ct.COL_HORIZON: h,
                "disease_id": envelope.get("disease_id"),
                COL_GEO_LEVEL: GEO_LEVEL_ESTADO,
                COL_GEO_ID: geo,
                COL_SEX: sexo,
                COL_EPI_YEAR: periodo[0],
                COL_EPI_WEEK: periodo[1],
                COL_DS: ds_for(*periodo).isoformat(),
                ct.COL_Y_PRED: valor,
                ct.COL_YHAT_LOWER: None,  # point-only: el release lo declara y aquí se respeta
                ct.COL_YHAT_UPPER: None,
            }
        )
    return filas


def reproduce_forecast(verified: VerifiedRelease) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carga los 64 modelos del bundle, pronostica y deriva los productos. Sin tocar ``runs/``."""
    bootstrap_engines()
    periodos = horizon_periods(verified.origin, verified.horizon)
    run_id = verified.chain["forecast_run_id"]
    filas: list[dict[str, object]] = []
    for engine in verified.engines:
        who = f"release/refit/{engine}"
        try:
            adapter = final_forecaster(engine)
            modelos = fm.load_models(verified.root / DIR_REFIT, engine)
        except (AdapterCapabilityError, *IO_ERRORS) as exc:
            raise ArtifactValidationError(f"{who}: no reproducible ({exc})") from exc
        for envelope, estado in modelos:
            clave = mapping_of(envelope.get("series_key"), f"{who}: series_key")
            geo = text_of(clave.get("geography_id"), f"{who}: geography_id")
            sexo = text_of(clave.get("sex"), f"{who}: sex")
            try:
                transform = TransformContract.from_dict(dict(envelope["transform"]))
                exposicion = {p: float(verified.runtime.exposure[(geo, sexo)]) for p in periodos}
                preds = adapter.forecast_state(
                    estado, fm.ForecastRequest(transform, tuple(periodos), exposicion)
                )
            except IO_ERRORS as exc:
                raise ArtifactValidationError(f"{who}/{geo}/{sexo}: {exc}") from exc
            filas.extend(_rows(envelope, preds, periodos, verified.origin, run_id))

    base = _through_csv(pd.DataFrame(filas, columns=list(ct.FORECAST_COLUMNS)))
    try:
        ct.validate_forecast_frame(base)
        productos = derive_forecast_products(base.copy(), verified.runtime.catalog)
        ct.validate_forecast_frame(productos)
    except IO_ERRORS as exc:
        raise ArtifactValidationError(
            f"release: el forecast reproducido no valida ({exc})"
        ) from exc
    return base, productos


def _through_csv(frame: pd.DataFrame) -> pd.DataFrame:
    """Pasa las bases por la MISMA frontera de precisión que usa el runner al materializarlas.

    El runner escribe la base de cada motor en CSV y DERIVA los 47 productos releyendo ese archivo
    con el parser por defecto de pandas, que no es correctamente redondeado: reparsear
    ``1271.6760897744061`` devuelve el double vecino. Esa pérdida forma parte del artefacto
    publicado, así que reproducirlo exige reproducirla; saltársela obligaría a comparar con
    tolerancia y a llamar "igual" a lo que no lo es.
    """
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    return pd.read_csv(io.StringIO(buffer.getvalue()), dtype={COL_GEO_ID: str}, low_memory=False)


def read_bundled_frame(path: Path, label: str) -> pd.DataFrame:
    """CSV del bundle SIN pérdida: ``round_trip`` devuelve el double exacto que se escribió."""
    try:
        return pd.read_csv(
            path, dtype={COL_GEO_ID: str}, low_memory=False, float_precision="round_trip"
        )
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{label}: ilegible ({exc})") from exc


def _compare(reproducido: pd.DataFrame, sellado: pd.DataFrame, label: str, tol: float) -> float:
    """Mismas claves, misma procedencia y mismos valores; devuelve la desviación máxima."""
    orden = [COL_GEO_LEVEL, COL_GEO_ID, COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK]
    izq = reproducido.sort_values(orden).reset_index(drop=True)
    der = sellado[list(ct.FORECAST_COLUMNS)].sort_values(orden).reset_index(drop=True)
    equal(f"{label}: filas", len(izq), len(der))
    for columna in ct.FORECAST_COLUMNS:
        if columna == ct.COL_Y_PRED:
            continue
        uno, otro = izq[columna], der[columna]
        # Los intervalos viajan conjuntamente nulos (point-only); `None` y `NaN` son el mismo
        # ausente, y compararlos como texto ("None" vs "nan") sería un falso rojo.
        if uno.isna().all() and otro.isna().all():
            continue
        if not uno.astype(str).equals(otro.astype(str)):
            raise ArtifactValidationError(f"{label}: difiere en {columna!r}")
    peor = float((izq[ct.COL_Y_PRED] - der[ct.COL_Y_PRED]).abs().max())
    require(
        peor <= tol, f"{label}: el forecast reproducido difiere (máx |Δ|={peor:.6g} > {tol:g})"
    )
    return peor


def _check_point_only(frames: dict[str, pd.DataFrame], interval_method: str) -> None:
    """Si el release declara ``interval_method=none``, NADIE puede llevar intervalos."""
    if interval_method != INTERVAL_METHOD_NONE:
        return
    for etiqueta, frame in frames.items():
        for columna in (ct.COL_YHAT_LOWER, ct.COL_YHAT_UPPER):
            presentes = int(frame[columna].notna().sum())
            require(
                not presentes,
                f"{etiqueta}: {columna} tiene {presentes} valores y el release es point-only",
            )


def check_reproduction(verified: VerifiedRelease, *, tol: float = 0.0) -> Reproduction:
    """Reproduce y contrasta contra los frames que el propio bundle transporta (tolerancia 0)."""
    base, productos = reproduce_forecast(verified)
    carpeta = verified.root / DIR_FORECAST
    sellado_base = read_bundled_frame(carpeta / BASE_FILE, BASE_FILE)
    sellado_full = read_bundled_frame(carpeta / FORECAST_FILE, FORECAST_FILE)
    _check_point_only(
        {
            f"release: {BASE_FILE}": sellado_base,
            f"release: {FORECAST_FILE}": sellado_full,
            "release: base reproducida": base,
            "release: productos reproducidos": productos,
        },
        verified.interval_method,
    )
    peor_base = _compare(base, sellado_base, f"release: {BASE_FILE}", tol)
    peor_full = _compare(productos, sellado_full, f"release: {FORECAST_FILE}", tol)
    return Reproduction(base, productos, peor_base, peor_full)
