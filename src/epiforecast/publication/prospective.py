"""C7.4 — gate prospectivo CONGELADO de un release.

La única forma de que una validación prospectiva signifique algo es congelar antes de mirar. Aquí se
sella, en un solo acto y antes de que exista una sola semana de verdad:

1. el forecast candidato (el del release, ya sellado e inmutable);
2. un control ``seasonal_naive_lag52`` con el MISMO origen, horizonte, dataset y SeriesKeys;
3. los digests de ambos;
4. la regla de aceptación y las semanas objetivo.

El control no se guarda como un CSV suelto que alguien podría regenerar distinto: se congela por
**digest + receta determinista** sobre el dataset sellado. Reproducirlo da el mismo digest o el gate
falla; cambiarlo sin que se note es imposible.

Después, evaluar sólo puede leer semanas de verdad; nunca reajustar, re-seleccionar ni mover
umbrales. Si faltan semanas válidas el veredicto es ``INCOMPLETE`` y se espera: una semana ausente
NO se convierte en cero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from epiforecast.data.epi_dataset_spec import (
    BASE_SEXES,
    COL_CVE_ENT,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_SEXO,
    COL_Y_CASES,
)
from epiforecast.runner import contracts as ct
from epiforecast.runner.artifact_identity import IO_ERRORS, ArtifactValidationError, equal, require
from epiforecast.runner.evaluation import smape_percent
from epiforecast.runner.release_contract import canonical_json, sha256_bytes
from epiforecast.runner.release_reproduce import horizon_periods

GATE_SCHEMA = "prospective_gate.v1"
CONTROL_ENGINE = "seasonal_naive_lag52"
GATE_WEEKS = 4

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_INCOMPLETE = "INCOMPLETE"

# Degradación máxima frente al control, por ámbito. Es la regla ya aprobada; se congela con el
# gate para que no pueda "ajustarse" después de ver los resultados.
ACCEPTANCE_RULE: dict[str, float] = {
    "smape_base": 5.0,
    "smape_products": 5.0,
    "smape_national_general": 10.0,
}

Period = tuple[int, int]
SeriesId = tuple[str, str]


@dataclass(frozen=True, slots=True)
class FrozenGate:
    """Lo que queda congelado ANTES de ver una sola semana de verdad."""

    disease_id: str
    release_id: str
    origin: Period
    horizon: int
    target_weeks: tuple[Period, ...]
    candidate_digest: str
    control_digest: str
    dataset_digest: str
    rule: dict[str, float]

    def payload(self) -> dict[str, Any]:
        return {
            "schema": GATE_SCHEMA,
            "disease_id": self.disease_id,
            "release_id": self.release_id,
            "origin": list(self.origin),
            "horizon": self.horizon,
            "target_weeks": [list(p) for p in self.target_weeks],
            "candidate_forecast_digest": self.candidate_digest,
            "control_engine": CONTROL_ENGINE,
            "control_forecast_digest": self.control_digest,
            "dataset_digest": self.dataset_digest,
            "acceptance_rule_max_degradation_pct": dict(sorted(self.rule.items())),
        }

    def digest(self) -> str:
        return sha256_bytes(canonical_json(self.payload()))


def check_dataset_frame(dataset_csv: Path, *, expected_series: int | None = None) -> None:
    """Valida el EpiDatasetV2 TABULAR antes de convertirlo a mappings.

    ``read_base_history`` construye un ``dict`` por serie: una fila duplicada con la misma serie y
    periodo se sobrescribe en silencio y el gate posterior nunca la ve (R80-P0-3). La unicidad hay
    que probarla sobre el frame, no sobre el diccionario que ya la perdió.
    """
    from epiforecast.data.epi_calendar import weeks_in_year

    try:
        frame = pd.read_csv(
            dataset_csv,
            usecols=[COL_CVE_ENT, COL_SEXO, COL_EPI_YEAR, COL_EPI_WEEK, COL_Y_CASES],
            dtype={COL_CVE_ENT: str},
            low_memory=False,
        )
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"dataset: ilegible ({exc})") from exc
    except ValueError as exc:
        raise ArtifactValidationError(f"dataset: columnas requeridas ausentes ({exc})") from exc

    base = frame[frame[COL_SEXO].isin(BASE_SEXES)]
    require(len(base) > 0, "dataset: no hay filas de series base")

    claves = list(
        zip(
            base[COL_CVE_ENT],
            base[COL_SEXO],
            base[COL_EPI_YEAR],
            base[COL_EPI_WEEK],
            strict=True,
        )
    )
    require(
        len(claves) == len(set(claves)),
        f"dataset: hay {len(claves) - len(set(claves))} filas duplicadas (serie × periodo)",
    )

    series = sorted({(str(c), str(x)) for c, x, _, _ in claves})
    if expected_series is not None:
        equal("dataset: número de SeriesKeys base", len(series), expected_series)

    for año, semana in {(int(a), int(w)) for _, _, a, w in claves}:
        tope = weeks_in_year(año)
        require(
            1 <= semana <= tope,
            f"dataset: semana {semana} fuera del calendario MMWR de {año} (1..{tope})",
        )

    valores = base[COL_Y_CASES].to_numpy(dtype=float)
    require(bool(np.isfinite(valores).all()), "dataset: hay valores no finitos")
    require(bool((valores >= 0.0).all()), "dataset: hay valores negativos")

    por_serie: dict[SeriesId, set[Period]] = {}
    for cve, sexo, año, semana in claves:
        por_serie.setdefault((str(cve), str(sexo)), set()).add((int(año), int(semana)))
    referencia = por_serie[series[0]]
    distintas = [k for k, v in por_serie.items() if v != referencia]
    require(
        not distintas,
        f"dataset: {len(distintas)} series con un conjunto de periodos distinto al resto"
        + (f" (p. ej. {distintas[0]})" if distintas else ""),
    )


def read_base_history(dataset_csv: Path) -> dict[SeriesId, dict[Period, float]]:
    """Historia observada por serie base, desde el dataset SELLADO."""
    try:
        frame = pd.read_csv(
            dataset_csv,
            usecols=[COL_CVE_ENT, COL_SEXO, COL_EPI_YEAR, COL_EPI_WEEK, COL_Y_CASES],
            dtype={COL_CVE_ENT: str},
            low_memory=False,
        )
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"dataset: ilegible ({exc})") from exc
    frame = frame[frame[COL_SEXO].isin(BASE_SEXES)]
    historia: dict[SeriesId, dict[Period, float]] = {}
    for (cve, sexo), grupo in frame.groupby([COL_CVE_ENT, COL_SEXO], sort=True):
        historia[(str(cve), str(sexo))] = {
            (int(y), int(w)): float(v)
            for y, w, v in zip(
                grupo[COL_EPI_YEAR], grupo[COL_EPI_WEEK], grupo[COL_Y_CASES], strict=True
            )
        }
    return historia


def build_control(
    historia: Mapping[SeriesId, dict[Period, float]], origin: Period, horizon: int
) -> pd.DataFrame:
    """Control ``seasonal_naive_lag52``: mismo origen, horizonte y SeriesKeys que el candidato.

    No ajusta nada —el baseline es la observación de 52 semanas antes—, así que congelarlo no es
    entrenar: es fijar una referencia derivada del dataset ya sellado.
    """
    from epiforecast.runner.engines.seasonal_naive import predict_series

    periodos = horizon_periods(origin, horizon)
    filas = []
    for serie in sorted(historia):
        try:
            preds = predict_series(dict(historia[serie]), list(periodos))
        except KeyError as exc:
            raise ArtifactValidationError(
                f"control {serie}: la historia sellada no cubre el lag-52 de {exc}"
            ) from exc
        for (year, week), valor in preds.items():
            filas.append(
                {
                    "geography_id": serie[0],
                    "sex": serie[1],
                    "epi_year": year,
                    "epi_week": week,
                    "y_pred_cases": float(valor),
                }
            )
    control = (
        pd.DataFrame(filas)
        .sort_values(["geography_id", "sex", "epi_year", "epi_week"])
        .reset_index(drop=True)
    )
    equal("control: filas", len(control), len(historia) * horizon)
    return control


def frame_digest(frame: pd.DataFrame) -> str:
    """Digest determinista de un frame: mismo contenido → mismo digest, en cualquier máquina."""
    texto: str = frame.to_csv(index=False)
    return sha256_bytes(texto.encode("utf-8"))


def available_weeks(
    historia: Mapping[SeriesId, dict[Period, float]], target_weeks: tuple[Period, ...]
) -> list[Period]:
    """Semanas objetivo con verdad COMPLETA. Una semana parcial no cuenta; una ausente no es cero."""
    disponibles = []
    for periodo in target_weeks:
        if all(periodo in serie for serie in historia.values()):
            disponibles.append(periodo)
    return disponibles


def _smape_of(verdad: list[float], pred: list[float]) -> float:
    return float(smape_percent(verdad, pred))


SCOPE_BASE = "smape_base"
SCOPE_PRODUCTS = "smape_products"
SCOPE_NATIONAL = "smape_national_general"
SCOPES: tuple[str, ...] = (SCOPE_BASE, SCOPE_PRODUCTS, SCOPE_NATIONAL)

WEEK_COMPLETE = "completa"
WEEK_PARTIAL = "parcial"
WEEK_MISSING = "ausente"
# Enum CERRADO de motivos de omisión: nada más puede aparecer en la evidencia.
SKIP_REASONS: tuple[str, ...] = (WEEK_PARTIAL, WEEK_MISSING)


@dataclass(frozen=True, slots=True)
class WeekSelection:
    """Qué semanas se programaron, cuáles contaron y cuáles se omitieron, con motivo."""

    scheduled: tuple[Period, ...]
    completed: tuple[Period, ...]
    skipped: tuple[tuple[Period, str], ...]

    def payload(self) -> dict[str, Any]:
        return {
            "scheduled_weeks": [list(p) for p in self.scheduled],
            "completed_weeks": [list(p) for p in self.completed],
            "skipped_weeks": [{"week": list(p), "reason": r} for p, r in self.skipped],
        }


def week_state(historia: Mapping[SeriesId, dict[Period, float]], periodo: Period) -> str:
    """``completa`` sólo si TODAS las series base tienen verdad; nunca se rellena con cero."""
    presentes = sum(1 for serie in historia.values() if periodo in serie)
    if presentes == len(historia) and historia:
        return WEEK_COMPLETE
    return WEEK_MISSING if presentes == 0 else WEEK_PARTIAL


def observation_cutoff(historia: Mapping[SeriesId, dict[Period, float]]) -> Period | None:
    """Último periodo que el snapshot pudo observar. Sin él, el futuro parece verdad ausente."""
    periodos = {p for serie in historia.values() for p in serie}
    return max(periodos) if periodos else None


def select_weeks(
    historia: Mapping[SeriesId, dict[Period, float]],
    gate: FrozenGate,
    cutoff: Period | None = None,
) -> WeekSelection:
    """Primeras ``GATE_WEEKS`` semanas COMPLETAS desde la primera objetivo, dentro del horizonte.

    ``target_weeks`` es la ventana inicialmente programada, no una lista cerrada: una semana parcial
    o ausente no cuenta, se registra con su motivo y se **reemplaza por la siguiente válida**. Sin
    esto, un boletín incompleto dejaría el gate atascado en 3/4 para siempre (R76-P0-3). El
    candidato y el control siguen siendo los mismos forecasts congelados, así que esto no mueve el
    ``gate_digest``: sólo dice qué semanas se pudieron observar.

    La ventana termina en el CORTE observado. Una semana futura no es una semana ausente: recorrer
    las 52 del horizonte hacía que el artefacto registrara 52 omisiones inventadas (R80-P0-1).
    """
    corte = cutoff if cutoff is not None else observation_cutoff(historia)
    ventana = [
        p
        for p in horizon_periods(gate.origin, gate.horizon)
        if p >= gate.target_weeks[0] and (corte is None or p <= corte)
    ]
    completas: list[Period] = []
    omitidas: list[tuple[Period, str]] = []
    for periodo in ventana:
        if len(completas) == GATE_WEEKS:
            break
        estado = week_state(historia, periodo)
        if estado == WEEK_COMPLETE:
            completas.append(periodo)
        else:
            omitidas.append((periodo, estado))
    return WeekSelection(
        scheduled=gate.target_weeks, completed=tuple(completas), skipped=tuple(omitidas)
    )


def _forecast_shape(
    frame: pd.DataFrame, *, disease_id: str, origin: Period, horizon: int, engine: str
) -> pd.DataFrame:
    """Frame base (geo, sexo, periodo, valor) con la forma que exige la derivación del runner."""
    from epiforecast.data.epi_calendar import ds_for
    from epiforecast.data.epi_dataset_spec import GEO_LEVEL_ESTADO

    out = frame.rename(columns={"y_cases": "y_pred_cases"}).copy()
    out["run_id"] = f"prospective_{engine}"
    out["engine"] = engine
    out["fold"] = "prospective"
    out["origin_epi_year"], out["origin_epi_week"] = origin[0], origin[1]
    out["horizon"] = horizon
    out["disease_id"] = disease_id
    out["geography_level"] = GEO_LEVEL_ESTADO
    out["ds"] = [
        ds_for(int(y), int(w)) for y, w in zip(out["epi_year"], out["epi_week"], strict=True)
    ]
    out["yhat_lower"] = pd.NA
    out["yhat_upper"] = pd.NA
    return out[list(ct.FORECAST_COLUMNS)]


def _truth_frame(
    historia: Mapping[SeriesId, dict[Period, float]], semanas: tuple[Period, ...]
) -> pd.DataFrame:
    filas = [
        {
            "geography_id": geo,
            "sex": sexo,
            "epi_year": p[0],
            "epi_week": p[1],
            "y_cases": historia[(geo, sexo)][p],
        }
        for (geo, sexo) in sorted(historia)
        for p in semanas
    ]
    return pd.DataFrame(filas)


def _scope_rows(products: pd.DataFrame, scope: str) -> pd.DataFrame:
    """Filas del ámbito: 64 bases, los 111 productos completos o sólo Nacional General."""
    from epiforecast.data.epi_dataset_spec import (
        GEO_LEVEL_ESTADO,
        GEO_LEVEL_NACIONAL,
        NATIONAL_GEO_ID,
        SEX_GENERAL,
    )

    if scope == SCOPE_PRODUCTS:
        return products
    if scope == SCOPE_NATIONAL:
        return products[
            (products["geography_level"] == GEO_LEVEL_NACIONAL)
            & (products["geography_id"] == NATIONAL_GEO_ID)
            & (products["sex"] == SEX_GENERAL)
        ]
    return products[
        (products["geography_level"] == GEO_LEVEL_ESTADO) & (products["sex"].isin(BASE_SEXES))
    ]


def check_series_frame(frame: pd.DataFrame, etiqueta: str, esperadas: set[SeriesId]) -> None:
    """Antes de agregar nada: claves exactas, sin duplicados y valores utilizables.

    Comparar sólo el NÚMERO de filas dejaba pasar un frame con las claves cambiadas y el mismo
    tamaño. Aquí se exige el conjunto exacto de SeriesKeys y que ningún valor sea NaN, infinito o
    negativo: agregarlos produciría un total que parece un dato (R78-P1).
    """
    faltan = {"geography_id", "sex", "epi_year", "epi_week", "y_pred_cases"} - set(frame.columns)
    require(not faltan, f"{etiqueta}: faltan columnas {sorted(faltan)}")
    claves = list(
        zip(frame["geography_id"], frame["sex"], frame["epi_year"], frame["epi_week"], strict=True)
    )
    require(len(claves) == len(set(claves)), f"{etiqueta}: hay claves serie×periodo duplicadas")
    series = {(str(g), str(x)) for g, x, _, _ in claves}
    require(
        series == esperadas,
        f"{etiqueta}: SeriesKeys distintas de las esperadas "
        f"(+{sorted(series - esperadas)[:3]} −{sorted(esperadas - series)[:3]})",
    )
    valores = frame["y_pred_cases"].to_numpy(dtype=float)
    require(bool(np.isfinite(valores).all()), f"{etiqueta}: hay valores no finitos (NaN o inf)")
    require(bool((valores >= 0.0).all()), f"{etiqueta}: hay valores negativos")


def seasonal_denominators(
    training: Mapping[SeriesId, dict[Period, float]], lag: int = 52
) -> dict[SeriesId, float]:
    """Denominador MASE por serie, desde la historia de ENTRENAMIENTO congelada.

    Calcularlo con ``train_true=[]`` dejaba MASE en NaN siempre (R78-P1): no era el MASE del runner,
    era un hueco con bandera.
    """
    denominadores: dict[SeriesId, float] = {}
    for serie, historia in training.items():
        valores = [historia[p] for p in sorted(historia)]
        if len(valores) > lag:
            difs = [abs(valores[i] - valores[i - lag]) for i in range(lag, len(valores))]
            denominadores[serie] = float(sum(difs) / len(difs)) if difs else 0.0
        else:
            denominadores[serie] = 0.0
    return denominadores


def _degradation_pct(candidate: float, control: float) -> float:
    """Degradación relativa del candidato frente al control. Zero-safe y nunca ``inf``."""
    if control == 0.0:
        return 0.0 if candidate == 0.0 else float("inf")
    return (candidate - control) / control * 100.0


def evaluate(
    gate: FrozenGate,
    candidate: pd.DataFrame,
    control: pd.DataFrame,
    historia: Mapping[SeriesId, dict[Period, float]],
    *,
    catalog: Any | None = None,
    training: Mapping[SeriesId, dict[Period, float]] | None = None,
    cutoff: Period | None = None,
) -> dict[str, Any]:
    """Aplica la REGLA congelada sobre las semanas observadas. Nunca reajusta ni mueve umbrales.

    Hasta A.1 esto devolvía ``PASS`` con sólo tener cuatro semanas, sin comparar contra el control
    (R76-P0-1): el FAIL documentado no podía ocurrir. Ahora se derivan los 111 productos desde las
    64 bases con la MISMA función del runner —para verdad, candidato y control—, y se compara sMAPE
    por ámbito contra el umbral del gate.

    ``historia`` es la verdad OBSERVADA (el boletín vigente) y decide ``n/4``; ``training`` es la
    historia congelada del dataset de entrenamiento y sólo aporta los denominadores del MASE. Son
    dos identidades distintas y mezclarlas es lo que impedía avanzar de 0/4 (R78-P0-1).
    """
    from epiforecast.data.epi_geo_exposure import load_geo_catalog
    from epiforecast.runner.evaluation import derive_forecast_products

    catalogo = catalog if catalog is not None else load_geo_catalog()
    entrenamiento = training if training is not None else historia
    corte = cutoff if cutoff is not None else observation_cutoff(historia)
    seleccion = select_weeks(historia, gate, corte)
    semanas = seleccion.completed
    esperadas = set(historia)
    if semanas:
        check_series_frame(_restrict(candidate, semanas), "candidato", esperadas)
        check_series_frame(_restrict(control, semanas), "control", esperadas)

    detalle: list[dict[str, Any]] = []
    for periodo in semanas:
        verdad, cand, ctrl = [], [], []
        for serie in sorted(historia):
            verdad.append(historia[serie][periodo])
            cand.append(_lookup(candidate, serie, periodo))
            ctrl.append(_lookup(control, serie, periodo))
        detalle.append(
            {
                "week": list(periodo),
                "series": len(verdad),
                "smape_candidate": _smape_of(verdad, cand),
                "smape_control": _smape_of(verdad, ctrl),
            }
        )

    completo = len(semanas) >= GATE_WEEKS
    scopes: dict[str, Any] = {}
    metricas: dict[str, Any] = {}
    if semanas:
        disease_id, origen, horizonte = gate.disease_id, gate.origin, gate.horizon
        truth_base = _truth_frame(historia, semanas)
        productos = {
            "truth": derive_forecast_products(
                _forecast_shape(
                    truth_base,
                    disease_id=disease_id,
                    origin=origen,
                    horizon=horizonte,
                    engine="truth",
                ),
                catalogo,
            ),
            "candidate": derive_forecast_products(
                _forecast_shape(
                    _restrict(candidate, semanas).rename(columns={"y_pred_cases": "y_cases"}),
                    disease_id=disease_id,
                    origin=origen,
                    horizon=horizonte,
                    engine="candidate",
                ),
                catalogo,
            ),
            "control": derive_forecast_products(
                _forecast_shape(
                    _restrict(control, semanas).rename(columns={"y_pred_cases": "y_cases"}),
                    disease_id=disease_id,
                    origin=origen,
                    horizon=horizonte,
                    engine=CONTROL_ENGINE,
                ),
                catalogo,
            ),
        }
        historia_productos = product_history(entrenamiento, catalogo, gate.disease_id)
        clave = ["geography_level", "geography_id", "sex", "epi_year", "epi_week"]
        base_ordenada = {
            nombre: frame.sort_values(clave).reset_index(drop=True)
            for nombre, frame in productos.items()
        }
        for scope in SCOPES:
            filas = {n: _scope_rows(f, scope) for n, f in base_ordenada.items()}
            equal(f"{scope}: cobertura candidato", len(filas["candidate"]), len(filas["truth"]))
            equal(f"{scope}: cobertura control", len(filas["control"]), len(filas["truth"]))
            yt = list(filas["truth"]["y_pred_cases"])
            yc = list(filas["candidate"]["y_pred_cases"])
            yk = list(filas["control"]["y_pred_cases"])
            smape_c, smape_k = _smape_of(yt, yc), _smape_of(yt, yk)
            umbral = float(gate.rule[scope])
            degradacion = _degradation_pct(smape_c, smape_k)
            scopes[scope] = {
                "rows": int(len(filas["truth"])),
                "smape_candidate": smape_c,
                "smape_control": smape_k,
                "degradation_pct": degradacion,
                "max_degradation_pct": umbral,
                "passes": bool(degradacion <= umbral),
            }
            # Reportadas, NO usadas para el veredicto: el gate se decide con sMAPE. Cada producto
            # con SU historia previa; el ámbito se resume por mediana.
            metricas[scope] = scope_metrics(filas, historia_productos)

    if not completo:
        veredicto = VERDICT_INCOMPLETE
    elif all(scopes[s]["passes"] for s in SCOPES):
        veredicto = VERDICT_PASS
    else:
        veredicto = VERDICT_FAIL

    return {
        "verdict": veredicto,
        "weeks_required": GATE_WEEKS,
        "weeks_available": len(semanas),
        "weeks": [list(p) for p in semanas],
        "per_week": detalle,
        "scopes": scopes,
        "metrics": metricas,
        "selection": seleccion.payload(),
        "observation_cutoff": list(corte) if corte is not None else None,
        "gate_digest": gate.digest(),
    }


def product_history(
    training: Mapping[SeriesId, dict[Period, float]], catalog: Any, disease_id: str
) -> dict[tuple[str, str, str], dict[Period, float]]:
    """Historia de entrenamiento de los 111 PRODUCTOS, derivada de las 64 bases.

    El MASE del runner es por producto: cada SeriesKey usa su propio denominador estacional sobre su
    propia historia. Concatenar las 64 historias hacía que el lag-52 cruzara fronteras entre
    entidades y sexos y midiera diferencias que nunca existieron (R80-P0-2).
    """
    from epiforecast.runner.evaluation import derive_forecast_products

    periodos = sorted({p for serie in training.values() for p in serie})
    filas = [
        {
            "geography_id": geo,
            "sex": sexo,
            "epi_year": p[0],
            "epi_week": p[1],
            "y_cases": training[(geo, sexo)][p],
        }
        for (geo, sexo) in sorted(training)
        for p in periodos
        if p in training[(geo, sexo)]
    ]
    base = pd.DataFrame(filas)
    origen = periodos[-1] if periodos else (0, 0)
    productos = derive_forecast_products(
        _forecast_shape(
            base, disease_id=disease_id, origin=origen, horizon=len(periodos), engine="training"
        ),
        catalog,
    )
    historia: dict[tuple[str, str, str], dict[Period, float]] = {}
    for nivel, geo, sexo, año, semana, valor in zip(
        productos["geography_level"],
        productos["geography_id"],
        productos["sex"],
        productos["epi_year"],
        productos["epi_week"],
        productos["y_pred_cases"],
        strict=True,
    ):
        historia.setdefault((str(nivel), str(geo), str(sexo)), {})[(int(año), int(semana))] = (
            float(valor)
        )
    return historia


def _finite_or_none(valor: float) -> float | None:
    """``NaN``/``inf`` no son un número en JSON: viajan como ``null`` con su bandera."""
    return float(valor) if math.isfinite(float(valor)) else None


def scope_metrics(
    filas: dict[str, pd.DataFrame],
    training_products: Mapping[tuple[str, str, str], dict[Period, float]],
    *,
    mase_lag: int = 52,
) -> dict[str, Any]:
    """Métricas por PRODUCTO y su resumen por ámbito, para candidato y control.

    Cada producto se mide con su propia historia previa; el ámbito se resume con la MEDIANA de los
    productos finitos, igual que los reportes del runner. MASE no decide el veredicto, pero
    publicarlo con un denominador contaminado sería un reporte falso.
    """
    from epiforecast.runner.evaluation import series_metrics

    clave = ["geography_level", "geography_id", "sex"]
    resumen: dict[str, Any] = {}
    for nombre in ("candidate", "control"):
        acumulado: dict[str, list[float]] = {}
        banderas: dict[str, int] = {}
        verdad = filas["truth"].sort_values([*clave, "epi_year", "epi_week"])
        pred = filas[nombre].sort_values([*clave, "epi_year", "epi_week"])
        for llave, grupo in verdad.groupby(clave, sort=True):
            producto = (str(llave[0]), str(llave[1]), str(llave[2]))
            sub = pred[
                (pred["geography_level"] == producto[0])
                & (pred["geography_id"] == producto[1])
                & (pred["sex"] == producto[2])
            ]
            historia = training_products.get(producto, {})
            previa = [historia[p] for p in sorted(historia)]
            metricas, flags = series_metrics(
                list(grupo["y_pred_cases"]), list(sub["y_pred_cases"]), previa, mase_lag=mase_lag
            )
            for k, v in metricas.items():
                if math.isfinite(float(v)):
                    acumulado.setdefault(k, []).append(float(v))
            for f in flags:
                banderas[f] = banderas.get(f, 0) + 1
        resumen[nombre] = {
            "products": int(len(acumulado.get("smape", []))),
            "median": {
                k: _finite_or_none(float(np.median(v))) if v else None
                for k, v in sorted(acumulado.items())
            },
            "flags": dict(sorted(banderas.items())),
        }
    return resumen


def _restrict(frame: pd.DataFrame, semanas: tuple[Period, ...]) -> pd.DataFrame:
    pares = {(int(y), int(w)) for y, w in semanas}
    mascara = [
        (int(y), int(w)) in pares
        for y, w in zip(frame["epi_year"], frame["epi_week"], strict=True)
    ]
    return frame[mascara].reset_index(drop=True)


def _lookup(frame: pd.DataFrame, serie: SeriesId, periodo: Period) -> float:
    fila = frame[
        (frame["geography_id"] == serie[0])
        & (frame["sex"] == serie[1])
        & (frame["epi_year"] == periodo[0])
        & (frame["epi_week"] == periodo[1])
    ]
    require(len(fila) == 1, f"cobertura incompleta para {serie} en {periodo}")
    return float(fila["y_pred_cases"].iloc[0])
