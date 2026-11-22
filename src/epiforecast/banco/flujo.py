"""Banco ampliado: pliegues de desarrollo, ejecución tolerante a fallos por serie y métricas.

Cada tarea es (padecimiento, motor). Por cada año de desarrollo de la política del release público
se pronostica el año completo con la historia estrictamente previa. Un fallo de una serie no aborta
la tarea: se registra, y ese pliegue queda fuera del nacional de ese motor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
from omegaconf import OmegaConf
import pandas as pd
import yaml

from epiforecast.banco import global_ml, motores, motores_extra
from epiforecast.publication.prospective import read_base_history
from epiforecast.runner.evaluation import smape_percent

_ROOT = Path(__file__).resolve().parents[3]
CONFIG = _ROOT / "config" / "banco" / "banco_ampliado_v1.yaml"
GLOBALES = {
    "lgbm_global_directo": global_ml.lgbm_global_directo,
    "topdown_ets_nacional": global_ml.topdown("ets_amortiguado_log1p"),
    "topdown_media52_nacional": global_ml.topdown("media_52s"),
}
LOCALES = {**motores.MOTORES, **motores_extra.MOTORES_EXTRA}


class BancoError(ValueError):
    """El banco violó una regla declarada (datos, pliegues o configuración)."""


def cargar_config(path: Path = CONFIG) -> dict[str, Any]:
    cfg = cast("dict[str, Any]", OmegaConf.to_container(OmegaConf.load(path), resolve=True))
    todos = [m for ms in cfg["clases"].values() for m in ms]
    faltan = [m for m in todos if m not in LOCALES and m not in GLOBALES]
    if faltan or len(set(todos)) != len(todos):
        raise BancoError(f"motores sin implementación o repetidos: {faltan}")
    cfg["motores"] = todos
    cfg["clase_de"] = {m: c for c, ms in cfg["clases"].items() for m in ms}
    return cfg


def _json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def anios(disease: str, root: Path = _ROOT) -> tuple[list[int], set[int]]:
    """Años de desarrollo y de prueba de la política del release público."""
    rel = _json(root / "config" / "publication" / disease / "public_release_pointer.json")
    (pol,) = sorted(
        (root / "artifacts/releases" / disease / rel["release_id"] / "policy").glob("*.yaml")
    )
    folds = yaml.safe_load(pol.read_text(encoding="utf-8"))["folds"]
    dev = sorted(int(f["epi_year"]) for f in folds["development"])
    prueba = {int(f["epi_year"]) for f in folds.get("test") or []}
    if set(dev) & prueba:
        raise BancoError(f"{disease}: desarrollo y prueba se traslapan")
    return dev, prueba


def historia(disease: str, root: Path = _ROOT) -> tuple[list[tuple[int, int]], dict[Any, Any]]:
    estado = _json(root / "config" / "publication" / disease / "prospective_status.json")
    csv = (
        root
        / "artifacts/observations"
        / disease
        / estado["observation_dataset_id"]
        / "epi_dataset_v2.csv"
    )
    h = read_base_history(csv)
    periodos = sorted(next(iter(h.values())))
    return periodos, {k: np.array([v[q] for q in periodos], dtype=float) for k, v in h.items()}


def correr(
    disease: str, motor: str, cfg: dict[str, Any], root: Path = _ROOT
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Pronósticos base de desarrollo de un motor; nunca toca años de prueba."""
    dev, prueba = anios(disease, root)
    periodos, series = historia(disease, root)
    p = cfg["parametros"]
    filas, fallos, recortes = [], [], 0
    for anio in dev:
        if anio in prueba:
            raise BancoError(f"{disease}: {anio} es año de prueba")
        n = next(i for i, q in enumerate(periodos) if q[0] >= anio)
        hold_idx = [i for i, q in enumerate(periodos) if q[0] == anio]
        train, hold = periodos[:n], [periodos[i] for i in hold_idx]
        if motor in GLOBALES:
            try:
                preds = GLOBALES[motor]({k: s[:n] for k, s in series.items()}, train, hold, p)
            except Exception as exc:  # noqa: BLE001 - se registra como fallo del pliegue
                fallos.append({"fold": anio, "serie": "*", "error": repr(exc)[:200]})
                continue
        else:
            preds = {}
            for k, s in series.items():
                try:
                    preds[k] = LOCALES[motor](s[:n], train, hold, p)
                except Exception as exc:  # noqa: BLE001
                    fallos.append({"fold": anio, "serie": "/".join(k), "error": repr(exc)[:200]})
        for (geo, sex), v in preds.items():
            v = np.asarray(v, dtype=float)
            if len(v) != len(hold) or not np.isfinite(v).all():
                fallos.append({"fold": anio, "serie": f"{geo}/{sex}", "error": "no finito"})
                continue
            recortes += int((v < 0).sum())
            v = np.maximum(v, 0.0)
            truth = series[(geo, sex)][hold_idx]
            for (yy, ww), yt, yp in zip(hold, truth, v, strict=True):
                filas.append((anio, geo, sex, yy, ww, yt, yp))
    df = pd.DataFrame(
        filas, columns=["fold", "geography_id", "sex", "epi_year", "epi_week", "y_true", "y_pred"]
    )
    return df, {"fallos": fallos, "recortes": recortes, "series": len(series), "folds": dev}


def metricas(df: pd.DataFrame, fallidos: set[int], n_series: int) -> pd.DataFrame:
    """Por pliegue: sMAPE nacional (si no faltan series), mediana por base, MAE y sesgo."""
    filas = []
    for fold, g in df.groupby("fold"):
        completo = (
            fold not in fallidos
            and g[["geography_id", "sex"]].drop_duplicates().shape[0] == n_series
        )
        nac = g.groupby(["epi_year", "epi_week"])[["y_true", "y_pred"]].sum()
        bases = [
            smape_percent(b["y_true"], b["y_pred"]) for _, b in g.groupby(["geography_id", "sex"])
        ]
        filas.append(
            {
                "fold": fold,
                "completo": completo,
                "smape_nacional": smape_percent(nac["y_true"], nac["y_pred"])
                if completo
                else np.nan,
                "mae_nacional": float((nac["y_pred"] - nac["y_true"]).abs().mean())
                if completo
                else np.nan,
                "sesgo_nacional_pct": float(
                    (nac["y_pred"].sum() - nac["y_true"].sum())
                    / max(nac["y_true"].sum(), 1e-9)
                    * 100
                )
                if completo
                else np.nan,
                "smape_bases": float(np.median(bases)),
            }
        )
    return pd.DataFrame(filas)
