"""Realidad y forecast por serie para la selección de motor productivo.

Compartido por ``scripts/produccion_dengue.py`` (cohorte Dengue) y
``scripts/reselect_motor_2026.py`` (cohorte neuro). Centraliza la mecánica común que
antes estaba duplicada (y divergía):

- ``smape`` — SMAPE simétrico seguro ante denominador cero.
- ``eval_year`` — año de evaluación DERIVADO del boletín (último año con datos), no
  hardcodeado.
- ``build_real`` — incidencia semanal real por (padecimiento, entidad, sexo, semana)
  desde el boletín, con desglose por sexo vía diff de acumulados.
- ``build_forecasts`` — yhat semanal por (motor, padecimiento, entidad, sexo, semana)
  desde los ``all_forecast_*.csv``, **ALINEADO POR SEMANA EPIDEMIOLÓGICA (ISO)** derivada
  de la fecha, no por posición (``cumcount``), que desalineaba 1 semana contra el boletín
  cuando el forecast del año arranca en la semana 2.

Las REGLAS de selección de motor NO viven aquí (difieren por cohorte): cada script aplica
las suyas sobre estas tablas.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd


def smape(y: npt.ArrayLike, yhat: npt.ArrayLike) -> float:
    """SMAPE en %, seguro: devuelve NaN si todos los denominadores son 0."""
    ya = np.asarray(y, dtype=float)
    yha = np.asarray(yhat, dtype=float)
    denom = (np.abs(ya) + np.abs(yha)) / 2
    mask = denom > 0
    if not bool(mask.any()):
        return float("nan")
    err = np.abs(ya[mask] - yha[mask]) / denom[mask]
    return float(np.mean(err)) * 100


def eval_year(boletin: Path | str, padecimientos: Iterable[str]) -> int:
    """Año de evaluación = último año con datos de la cohorte en el boletín."""
    pads = set(padecimientos)
    df = pd.read_csv(boletin, usecols=["Padecimiento", "Anio"])
    return int(df[df["Padecimiento"].isin(pads)]["Anio"].max())


def build_real(
    boletin: Path | str, padecimientos: Iterable[str], anio: int, weeks_limit: int
) -> pd.DataFrame:
    """Real semanal por (padecimiento, entidad, sexo, Semana) del año dado.

    ``general`` = suma de ``Casos_semana``; ``hombres``/``mujeres`` = incremento semanal
    del acumulado por sexo (diff, primer valor = acumulado, recortado a >=0). Agrega además
    la serie ``Nacional`` por (padecimiento, semana, sexo).
    """
    pads = set(padecimientos)
    df = pd.read_csv(boletin)
    df = df[df["Padecimiento"].isin(pads)].copy()
    sub = df[(df["Anio"] == anio) & (df["Semana"] <= weeks_limit)].copy()
    sub = sub.sort_values(["Padecimiento", "Entidad", "Semana"])

    gen = sub.groupby(["Padecimiento", "Entidad", "Semana"])["Casos_semana"].sum().reset_index()
    gen["sexo"] = "general"
    gen = gen.rename(columns={"Casos_semana": "real"})

    def _diff(col: str, sexo: str) -> pd.DataFrame:
        rows = []
        for (pad, ent), grp in sub.groupby(["Padecimiento", "Entidad"]):
            grp = grp.sort_values("Semana")
            diffs = grp[col].diff().fillna(grp[col]).clip(lower=0)
            for sem, val in zip(grp["Semana"], diffs, strict=False):
                rows.append(
                    {
                        "Padecimiento": pad,
                        "Entidad": ent,
                        "Semana": int(sem),
                        "real": float(val),
                        "sexo": sexo,
                    }
                )
        return pd.DataFrame(rows)

    hom = _diff("Acumulado_hombres", "hombres")
    muj = _diff("Acumulado_mujeres", "mujeres")
    long_df = pd.concat(
        [gen[["Padecimiento", "Entidad", "Semana", "sexo", "real"]], hom, muj],
        ignore_index=True,
    )

    nac = long_df.groupby(["Padecimiento", "Semana", "sexo"])["real"].sum().reset_index()
    nac["Entidad"] = "Nacional"
    full = pd.concat(
        [long_df, nac[["Padecimiento", "Entidad", "Semana", "sexo", "real"]]],
        ignore_index=True,
    )
    return full.rename(columns={"Padecimiento": "padecimiento", "Entidad": "entidad"})[
        ["padecimiento", "entidad", "sexo", "Semana", "real"]
    ]


def build_forecasts(
    forecast_paths: Mapping[str, Path | str],
    padecimientos: Iterable[str],
    anio: int,
    weeks_limit: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """yhat y CV-SMAPE por serie/motor del año dado, alineados por semana ISO.

    Returns:
        (fc, cv): ``fc`` con (motor, padecimiento, entidad, sexo, Semana, yhat); ``cv`` con
        (motor, padecimiento, entidad, sexo, cv_smape) = ``smape_usado`` por serie.
    """
    pads = set(padecimientos)
    pieces, cv_rows = [], []
    for motor, path in forecast_paths.items():
        raw = pd.read_csv(path, low_memory=False)
        raw = raw[raw["meta_padecimiento"].isin(pads)].copy()

        cv = (
            raw.groupby(["meta_padecimiento", "meta_entidad", "meta_modo"])["smape_usado"]
            .first()
            .reset_index()
        )
        cv = cv.rename(
            columns={
                "meta_padecimiento": "padecimiento",
                "meta_entidad": "entidad",
                "meta_modo": "sexo",
                "smape_usado": "cv_smape",
            }
        )
        cv["motor"] = motor
        cv_rows.append(cv)

        df = raw[["ds", "yhat", "meta_padecimiento", "meta_entidad", "meta_modo"]].copy()
        df["ds"] = pd.to_datetime(df["ds"])
        df = df[df["ds"].dt.year == anio]
        # Semana epidemiológica (ISO) derivada de la fecha, NO por posición (cumcount):
        # el forecast del año puede arrancar en la semana 2 (p.ej. 2026-01-05) y cumcount
        # lo etiquetaría como 1 → desfase de 1 semana contra el real del boletín.
        df["Semana"] = df["ds"].dt.isocalendar().week.astype(int)
        df = df[df["Semana"] <= weeks_limit]
        df = df.rename(
            columns={
                "meta_padecimiento": "padecimiento",
                "meta_entidad": "entidad",
                "meta_modo": "sexo",
            }
        )
        df["motor"] = motor
        pieces.append(df[["motor", "padecimiento", "entidad", "sexo", "Semana", "yhat"]])
    return (
        pd.concat(pieces, ignore_index=True),
        pd.concat(cv_rows, ignore_index=True),
    )
