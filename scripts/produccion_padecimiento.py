"""Selector productivo genérico por padecimiento (EPIC 3).

Despacha por ``selection_policy`` del registry y aplica la regla canónica
(``epiforecast.selection.select_engine``: sMAPE→MASE→RMSE + banda 5% + orden estable)
sobre los motores ELEGIBLES del padecimiento, usando las métricas CV por serie de cada
``{Motor}_{Padecimiento}_completo.csv``. Escribe ``reports/ProdDetails/produccion_<slug>.csv``.

Nota: los motores no entrenados se omiten (se registra cuáles se usaron). Para Obesidad,
DeepAR puede faltar (gate de compute). La política ``rolling_cv_v1`` OOS-honesta refina
estas métricas CV en una fase posterior; este selector ya produce la asignación por serie.

Uso: .venv/bin/python -m scripts.produccion_padecimiento --disease Obesidad
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from epiforecast import registry
from epiforecast.selection import Candidate, select_engine
from epiforecast.utils.config import logger

ROOT = Path(__file__).resolve().parent.parent
_ENGINE_CAP = {
    "prophet": "Prophet",
    "deepar": "DeepAR",
    "ensemble": "Ensemble",
    "stacking": "Stacking",
    "nbglm": "NBGLM",
}
_SEXO_MAP = {
    "incrementos_hombres": "hombres",
    "incrementos_mujeres": "mujeres",
    "incrementos_total": "general",
}


def _load_engine_metrics(artifact_key: str, engine: str) -> pd.DataFrame | None:
    cap = _ENGINE_CAP.get(engine, engine.capitalize())
    path = ROOT / "models" / engine / artifact_key / f"{cap}_{artifact_key}_completo.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["entidad"] = df["Entidad"].fillna("Nacional").astype(str) if "Entidad" in df else "Nacional"
    df["sexo"] = df["sexo"].map(lambda s: _SEXO_MAP.get(str(s), str(s)))
    out = df[["entidad", "sexo", "smape", "mase", "rmse"]].copy()
    out["motor"] = engine
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disease", required=True)
    args = ap.parse_args()

    d = registry.require(args.disease)
    logger.info(
        "Selector {} | política={} | motores elegibles={}",
        d.data_name,
        d.selection_policy,
        list(d.eligible_engines),
    )

    metricas: dict[str, pd.DataFrame] = {}
    for engine in d.eligible_engines:
        m = _load_engine_metrics(d.artifact_key, engine)
        if m is not None:
            metricas[engine] = m
    if not metricas:
        logger.error("Ningún motor entrenado para {} — corre entrena primero.", d.data_name)
        return 1
    faltantes = [e for e in d.eligible_engines if e not in metricas]
    if faltantes:
        logger.warning("Motores elegibles SIN entrenar (omitidos): {}", faltantes)

    # Series = unión de (entidad, sexo) de todos los motores disponibles.
    todas = pd.concat(metricas.values(), ignore_index=True)
    series = todas[["entidad", "sexo"]].drop_duplicates().itertuples(index=False)

    rows: list[dict] = []
    for entidad, sexo in series:
        cands: list[Candidate] = []
        detalle: dict[str, float] = {}
        for engine, mdf in metricas.items():
            sel = mdf[(mdf.entidad == entidad) & (mdf.sexo == sexo)]
            if sel.empty:
                continue
            r = sel.iloc[0]
            cands.append(
                Candidate(engine, smape=_num(r.smape), mase=_num(r.mase), rmse=_num(r.rmse))
            )
            detalle[f"smape_{engine}"] = _num(r.smape)
            detalle[f"mase_{engine}"] = _num(r.mase)
        ganador = select_engine(cands)
        rows.append(
            {
                "padecimiento": d.data_name,
                "entidad": entidad,
                "sexo": sexo,
                "motor_productivo": _ENGINE_CAP.get(ganador, ganador) if ganador else None,
                "criterio_seleccion": d.selection_policy,
                "motores_evaluados": ",".join(sorted(metricas)),
                **detalle,
            }
        )

    prod = pd.DataFrame(rows).sort_values(["entidad", "sexo"]).reset_index(drop=True)
    out_dir = ROOT / "reports" / "ProdDetails"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"produccion_{d.slug}.csv"
    prod.to_csv(out_path, index=False, encoding="utf-8")

    dist = prod["motor_productivo"].value_counts().to_dict()
    logger.success(
        "Producción {}: {} series | distribución motor {} -> {}",
        d.data_name,
        len(prod),
        dist,
        out_path,
    )
    return 0


def _num(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
