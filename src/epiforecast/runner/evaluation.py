"""F2/C3.3 — evaluación OOS 64→111: derivación de pronósticos, alineación verdad↔pred y métricas.

- Los motores predicen SOLO las 64 bases (estado×sexo). Aquí se derivan los 32 generales estatales,
  12 regionales y 3 nacionales con el MISMO lineage de C2 (suma de contribuyentes por periodo).
- Reconciliación de pronósticos con tolerancia numérica absoluta 1e-9 (float); el histórico entero
  conserva tolerancia cero (lo valida epi_aggregate).
- Verdad y predicción se alinean por SeriesKey + periodo. Se evalúan los 111 productos.
- Métricas en casos: sMAPE (principal), MASE (denominador naive lag-52 SOLO sobre train), MAE, RMSE,
  WAPE y bias medio firmado. MASE/WAPE con denominador cero → NaN + flag explícito; NUNCA inf.

Sin train real: consume ForecastFrame (de un adapter) + la verdad de los 111 productos.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from epiforecast.data.epi_dataset_spec import (
    COL_DS,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
    COL_Y_CASES,
    GEO_LEVEL_ESTADO,
    GEO_LEVEL_NACIONAL,
    GEO_LEVEL_REGION,
    NATIONAL_GEO_ID,
    SEX_GENERAL,
)
from epiforecast.data.epi_geo_exposure import GeoCatalog
from epiforecast.runner import contracts as ct
from epiforecast.runner.contracts import (
    COL_BIAS,
    COL_ENGINE,
    COL_FLAGS,
    COL_FOLD,
    COL_HORIZON,
    COL_MAE,
    COL_MASE,
    COL_N_OBS,
    COL_ORIGIN_EPI_WEEK,
    COL_ORIGIN_EPI_YEAR,
    COL_RMSE,
    COL_RUN_ID,
    COL_SMAPE,
    COL_SPLIT,
    COL_WAPE,
    COL_Y_PRED,
    COL_Y_TRUE,
    COL_YHAT_LOWER,
    COL_YHAT_UPPER,
)

RECON_TOL = 1e-9  # tolerancia absoluta de reconciliación de pronósticos (float)
_MR = "macroregion_id"
_DISEASE = "disease_id"
# Columnas invariantes dentro de un grupo de agregación de pronóstico.
_INVARIANT: list[str] = [
    COL_RUN_ID,
    COL_ENGINE,
    COL_FOLD,
    COL_ORIGIN_EPI_YEAR,
    COL_ORIGIN_EPI_WEEK,
    COL_HORIZON,
    _DISEASE,
    COL_EPI_YEAR,
    COL_EPI_WEEK,
    COL_DS,
]


class EvaluationError(ValueError):
    """Fallo de derivación/reconciliación/alineación en la evaluación OOS."""


# ── Derivación 64→111 de pronósticos (mismo lineage de C2) ──
def _combine_fc(df: pd.DataFrame, id_cols: list[str]) -> pd.DataFrame:
    out = df.groupby([*id_cols, *_INVARIANT], sort=False)[COL_Y_PRED].sum().reset_index()
    out[COL_YHAT_LOWER] = np.nan  # los derivados no propagan intervalos
    out[COL_YHAT_UPPER] = np.nan
    return out


def _tier_fc(
    df: pd.DataFrame,
    id_cols: list[str],
    level: str,
    geo_id: Any,
    sex: Any,
) -> pd.DataFrame:
    out = _combine_fc(df, id_cols)
    out[COL_GEO_LEVEL] = level
    out[COL_GEO_ID] = geo_id(out)
    out[COL_SEX] = sex(out)
    return out[list(ct.FORECAST_COLUMNS)]


def derive_forecast_products(base_fc: pd.DataFrame, catalog: GeoCatalog) -> pd.DataFrame:
    """64 bases (estado×sexo) → 111 productos de pronóstico (suma de contribuyentes por periodo)."""
    if not (base_fc[COL_GEO_LEVEL] == GEO_LEVEL_ESTADO).all():
        raise EvaluationError("derive_forecast_products exige SOLO filas base (estado×sexo)")
    base_r = base_fc.copy()
    base_r[_MR] = base_fc[COL_GEO_ID].map(catalog.macroregion_of)

    tiers = [
        base_fc[list(ct.FORECAST_COLUMNS)],  # 64 bases (conservan sus intervalos)
        _tier_fc(
            base_fc, [COL_GEO_ID], GEO_LEVEL_ESTADO, lambda o: o[COL_GEO_ID], lambda o: SEX_GENERAL
        ),
        _tier_fc(base_r, [_MR, COL_SEX], GEO_LEVEL_REGION, lambda o: o[_MR], lambda o: o[COL_SEX]),
        _tier_fc(base_r, [_MR], GEO_LEVEL_REGION, lambda o: o[_MR], lambda o: SEX_GENERAL),
        _tier_fc(
            base_fc, [COL_SEX], GEO_LEVEL_NACIONAL, lambda o: NATIONAL_GEO_ID, lambda o: o[COL_SEX]
        ),
        _tier_fc(
            base_fc, [], GEO_LEVEL_NACIONAL, lambda o: NATIONAL_GEO_ID, lambda o: SEX_GENERAL
        ),
    ]
    products = pd.concat(tiers, ignore_index=True)
    _reconcile(products)
    return products


def _reconcile(products: pd.DataFrame) -> None:
    """Verifica (tol 1e-9) general==H+M en todo nivel y Σ regiones == nacional, por periodo."""
    piv = products.pivot_table(
        index=[COL_GEO_LEVEL, COL_GEO_ID, COL_EPI_YEAR, COL_EPI_WEEK],
        columns=COL_SEX,
        values=COL_Y_PRED,
        aggfunc="sum",
    )
    if not np.allclose(piv[SEX_GENERAL], piv["hombres"] + piv["mujeres"], atol=RECON_TOL):
        raise EvaluationError("reconciliación de pronóstico: general != H+M")
    reg = products[products[COL_GEO_LEVEL] == GEO_LEVEL_REGION]
    nat = products[products[COL_GEO_LEVEL] == GEO_LEVEL_NACIONAL]
    rk = [COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK]
    reg_sum = reg.groupby(rk, sort=True)[COL_Y_PRED].sum()
    nat_sum = nat.groupby(rk, sort=True)[COL_Y_PRED].sum()
    if not np.allclose(
        reg_sum.to_numpy(), nat_sum.reindex(reg_sum.index).to_numpy(), atol=RECON_TOL
    ):
        raise EvaluationError("reconciliación de pronóstico: Σ regiones != nacional")


# ── Alineación verdad ↔ predicción (EvaluationFrame fila a fila) ──
def build_evaluation_frame(full_fc: pd.DataFrame, truth: pd.DataFrame, split: str) -> pd.DataFrame:
    """Une los 111 productos de pronóstico con la verdad (products) por SeriesKey + periodo."""
    key = [_DISEASE, COL_GEO_LEVEL, COL_GEO_ID, COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK]
    t = truth[[*key, COL_Y_CASES]].rename(columns={COL_Y_CASES: COL_Y_TRUE})
    merged = full_fc.merge(t, on=key, how="left", validate="one_to_one")
    if merged[COL_Y_TRUE].isna().any():
        raise EvaluationError("alineación incompleta: predicción sin verdad correspondiente")
    merged[COL_SPLIT] = split
    return merged[list(ct.EVALUATION_COLUMNS)]


# ── Métricas por serie (casos), zero-safe, nunca inf ──
def series_metrics(
    y_true: Any, y_pred: Any, train_true: Any, mase_lag: int
) -> tuple[dict[str, float], list[str]]:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    err = yp - yt
    abs_err = np.abs(err)
    mae = float(abs_err.mean())
    rmse = float(np.sqrt((err**2).mean()))
    bias = float(err.mean())

    denom_s = np.abs(yt) + np.abs(yp)
    term = np.zeros_like(abs_err, dtype=float)  # denom_s==0 (ambos cero) → 0, sin warning 0/0
    np.divide(2.0 * abs_err, denom_s, out=term, where=denom_s != 0.0)
    smape = float(term.mean() * 100.0)

    flags: list[str] = []
    sum_true = float(np.abs(yt).sum())
    if sum_true > 0.0:
        wape = float(abs_err.sum() / sum_true)
    else:
        wape = float("nan")
        flags.append("wape_zero_denom")

    tt = np.asarray(train_true, dtype=float)
    denom_m = 0.0
    if tt.size > mase_lag:
        sdiff = np.abs(tt[mase_lag:] - tt[:-mase_lag])
        denom_m = float(sdiff.mean()) if sdiff.size else 0.0
    if denom_m > 0.0:
        mase = float(mae / denom_m)
    else:
        mase = float("nan")
        flags.append("mase_zero_denom")

    return (
        {
            COL_SMAPE: smape,
            COL_MASE: mase,
            COL_MAE: mae,
            COL_RMSE: rmse,
            COL_WAPE: wape,
            COL_BIAS: bias,
        },
        flags,
    )


def build_metric_frame(
    eval_frame: pd.DataFrame,
    truth_full: pd.DataFrame,
    mase_lag: int,
) -> pd.DataFrame:
    """MetricFrame por (motor, fold, producto). MASE usa la verdad de TRAIN (previa al holdout)."""
    key = [_DISEASE, COL_GEO_LEVEL, COL_GEO_ID, COL_SEX]
    rows: list[dict[str, Any]] = []
    for (engine, fold, split, *ident), grp in eval_frame.groupby(
        [COL_ENGINE, COL_FOLD, COL_SPLIT, *key], sort=False
    ):
        grp = grp.sort_values([COL_EPI_YEAR, COL_EPI_WEEK])
        # Clave entera de periodo (semanas <= 53 → year*100+week es monótona).
        holdout_start = int(grp[COL_EPI_YEAR].iloc[0]) * 100 + int(grp[COL_EPI_WEEK].iloc[0])
        # Verdad de TRAIN del producto: periodos estrictamente anteriores al holdout.
        prod_truth = truth_full[
            (truth_full[_DISEASE] == ident[0])
            & (truth_full[COL_GEO_LEVEL] == ident[1])
            & (truth_full[COL_GEO_ID] == ident[2])
            & (truth_full[COL_SEX] == ident[3])
        ].sort_values([COL_EPI_YEAR, COL_EPI_WEEK])
        pkey = prod_truth[COL_EPI_YEAR] * 100 + prod_truth[COL_EPI_WEEK]
        train_true = prod_truth[pkey < holdout_start][COL_Y_CASES].to_numpy()
        metrics, flags = series_metrics(
            grp[COL_Y_TRUE].to_numpy(), grp[COL_Y_PRED].to_numpy(), train_true, mase_lag
        )
        rows.append(
            {
                COL_ENGINE: engine,
                COL_FOLD: fold,
                COL_SPLIT: split,
                _DISEASE: ident[0],
                COL_GEO_LEVEL: ident[1],
                COL_GEO_ID: ident[2],
                COL_SEX: ident[3],
                COL_N_OBS: int(len(grp)),
                **metrics,
                COL_FLAGS: "|".join(flags),
            }
        )
    return pd.DataFrame(rows, columns=list(ct.METRIC_COLUMNS))
