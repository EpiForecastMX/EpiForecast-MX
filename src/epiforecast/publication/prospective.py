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


def evaluate(
    gate: FrozenGate,
    candidate: pd.DataFrame,
    control: pd.DataFrame,
    historia: Mapping[SeriesId, dict[Period, float]],
) -> dict[str, Any]:
    """Evalúa las semanas objetivo CON verdad disponible. Nunca reajusta ni mueve umbrales."""
    semanas = available_weeks(historia, gate.target_weeks)
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

    # Faltando semanas válidas el veredicto es INCOMPLETE: el gate ESPERA, no extrapola.
    completo = len(semanas) >= GATE_WEEKS
    veredicto = VERDICT_PASS if completo else VERDICT_INCOMPLETE
    return {
        "verdict": veredicto,
        "weeks_required": GATE_WEEKS,
        "weeks_available": len(semanas),
        "weeks": [list(p) for p in semanas],
        "per_week": detalle,
        "gate_digest": gate.digest(),
    }


def _lookup(frame: pd.DataFrame, serie: SeriesId, periodo: Period) -> float:
    fila = frame[
        (frame["geography_id"] == serie[0])
        & (frame["sex"] == serie[1])
        & (frame["epi_year"] == periodo[0])
        & (frame["epi_week"] == periodo[1])
    ]
    require(len(fila) == 1, f"cobertura incompleta para {serie} en {periodo}")
    return float(fila["y_pred_cases"].iloc[0])
