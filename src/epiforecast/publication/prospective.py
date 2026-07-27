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
from pathlib import Path
from typing import Any

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


def select_weeks(
    historia: Mapping[SeriesId, dict[Period, float]], gate: FrozenGate
) -> WeekSelection:
    """Primeras ``GATE_WEEKS`` semanas COMPLETAS desde la primera objetivo, dentro del horizonte.

    ``target_weeks`` es la ventana inicialmente programada, no una lista cerrada: una semana parcial
    o ausente no cuenta, se registra con su motivo y se **reemplaza por la siguiente válida**. Sin
    esto, un boletín incompleto dejaría el gate atascado en 3/4 para siempre (R76-P0-3). El
    candidato y el control siguen siendo los mismos forecasts congelados, así que esto no mueve el
    ``gate_digest``: sólo dice qué semanas se pudieron observar.
    """
    ventana = [p for p in horizon_periods(gate.origin, gate.horizon) if p >= gate.target_weeks[0]]
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
) -> dict[str, Any]:
    """Aplica la REGLA congelada sobre las semanas observadas. Nunca reajusta ni mueve umbrales.

    Hasta A.1 esto devolvía ``PASS`` con sólo tener cuatro semanas, sin comparar contra el control
    (R76-P0-1): el FAIL documentado no podía ocurrir. Ahora se derivan los 111 productos desde las
    64 bases con la MISMA función del runner —para verdad, candidato y control—, y se compara sMAPE
    por ámbito contra el umbral del gate.
    """
    from epiforecast.data.epi_geo_exposure import load_geo_catalog
    from epiforecast.runner.evaluation import derive_forecast_products, series_metrics

    catalogo = catalog if catalog is not None else load_geo_catalog()
    seleccion = select_weeks(historia, gate)
    semanas = seleccion.completed

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
            # Reportadas, NO usadas para el veredicto: el gate se decide con sMAPE.
            m, flags = series_metrics(yt, yc, [], mase_lag=52)
            metricas[scope] = {**{k: float(v) for k, v in m.items()}, "flags": flags}

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
        "gate_digest": gate.digest(),
    }


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
