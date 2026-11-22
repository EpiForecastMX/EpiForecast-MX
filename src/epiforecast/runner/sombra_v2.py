"""Política v2 en sombra: selección consciente del nacional e intervalos empíricos (lógica pura).

No publica, no reentrena y no lee archivos: recibe marcos ya cargados por ``sombra_v2_io``. Toda
regla sale de ``config/sombra/sombra_v2.yaml``. Las bases son las series estado×sexo (o estado
general sin desglose por sexo); los demás productos se derivan sumándolas, como en el runner.

- ``seleccionar``: un motor por padecimiento, por el sMAPE del nacional General en desarrollo; un
  motor distinto del control sólo gana con mejora material y en la mayoría de los pliegues.
- ``cuantiles``: cuantiles del residuo log1p del motor elegido en desarrollo, por producto.
- ``pronostico``: el motor elegido y el control sobre la historia observada, con intervalos.
- ``evaluar``: sombra, publicado y control frente a la verdad de semanas posteriores al origen.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
from omegaconf import OmegaConf
import pandas as pd

from epiforecast.data.epi_dataset_spec import NATIONAL_GEO_ID, SEX_GENERAL
from epiforecast.data.epi_geo_exposure import GeoCatalog
from epiforecast.data.sex_scheme import base_sexes_of
from epiforecast.runner.evaluation import smape_percent
from epiforecast.runner.forecasting import horizon_periods
from epiforecast.runner.sombra_predictores import SombraError as SombraError
from epiforecast.runner.sombra_predictores import predicciones_base

_ROOT = Path(__file__).resolve().parents[3]
CONFIG = _ROOT / "config" / "sombra" / "sombra_v2.yaml"
Period = tuple[int, int]
Predictor = Callable[[dict[Period, float], list[Period]], dict[Period, float]]
LLAVE = ["geography_level", "geography_id", "sex"]
PERIODO = ["epi_year", "epi_week"]


@dataclass(frozen=True)
class Reglas:
    candidatos: tuple[str, ...]
    control: str
    margen_minimo_pct: float
    mayoria_pliegues: bool
    niveles: tuple[int, ...]
    min_residuos: int
    horizonte: int
    nombre: str = "sombra_v2"
    fuente: str = "benchmark"  # de dónde salen las predicciones de desarrollo: benchmark | banco
    ruta: str = ""  # archivo de configuración (su SHA-256 viaja en el índice de la emisión)
    cuantil_de: tuple[float, ...] = ()  # nivel de cuantil usado por banda; vacío = el nominal


def cargar_reglas(path: Path = CONFIG) -> Reglas:
    raw = cast("dict[str, Any]", OmegaConf.to_container(OmegaConf.load(path), resolve=True))
    sel, itv = raw["seleccion"], raw["intervalos"]
    if sel["metrica"] != "smape_nacional_general" or sel["agregado"] != "mean":
        raise SombraError(f"selección no soportada: {sel['metrica']}/{sel['agregado']}")
    if itv["metodo"] != "cuantil_residuo_log1p":
        raise SombraError(f"método de intervalos no soportado: {itv['metodo']}")
    if raw.get("fuente_desarrollo", "benchmark") not in {"benchmark", "banco"}:
        raise SombraError(f"fuente de desarrollo no soportada: {raw['fuente_desarrollo']}")
    if raw["control"] not in raw["candidatos"]:
        raise SombraError("el control debe estar entre los candidatos")
    return Reglas(
        candidatos=tuple(raw["candidatos"]),
        control=str(raw["control"]),
        margen_minimo_pct=float(sel["margen_minimo_pct"]),
        mayoria_pliegues=bool(sel["mayoria_pliegues"]),
        niveles=tuple(int(n) for n in itv["niveles"]),
        min_residuos=int(itv["min_residuos"]),
        horizonte=int(raw["horizonte"]),
        nombre=str(raw["name"]),
        fuente=str(raw.get("fuente_desarrollo", "benchmark")),
        ruta=str(path),
        cuantil_de=tuple(
            float(itv.get("cuantil_por_nivel", {}).get(n, n)) for n in itv["niveles"]
        ),
    )


def productos(base: pd.DataFrame, catalog: GeoCatalog, valores: list[str]) -> pd.DataFrame:
    """Bases → productos (estatal general, regionales y nacionales) sumando por periodo."""
    sexed = set(base_sexes_of(base["sex"].unique())) != {SEX_GENERAL}
    b = base.assign(geography_level="estado", geography_id=base["geography_id"].astype(str))
    b["_mr"] = b["geography_id"].map(catalog.macroregion_of)
    extra = [c for c in b.columns if c not in {*LLAVE, *PERIODO, *valores, "_mr"}]
    grupos = PERIODO + extra

    def nivel(por: list[str], level: str) -> pd.DataFrame:
        out = b.groupby(por + grupos, sort=False)[valores].sum().reset_index()
        out["geography_level"] = level
        if "_mr" in por:
            out["geography_id"] = out.pop("_mr")
        elif "geography_id" not in por:
            out["geography_id"] = NATIONAL_GEO_ID
        if "sex" not in por:
            out["sex"] = SEX_GENERAL
        return out

    tiers = [b.drop(columns="_mr")]
    if sexed:
        tiers += [nivel(["geography_id"], "estado"), nivel(["_mr", "sex"], "region")]
        tiers.append(nivel(["sex"], "nacional"))
    tiers += [nivel(["_mr"], "region"), nivel([], "nacional")]
    return pd.concat(tiers, ignore_index=True)[[*LLAVE, *grupos, *valores]]


def _mediana_bases(frame: pd.DataFrame, col: str) -> float:
    """Mediana, sobre las bases, del sMAPE de cada serie estado×sexo."""
    valores = [
        smape_percent(g["y_true_cases"], g[col])
        for _, g in frame.groupby(["geography_id", "sex"], sort=True)
    ]
    return float(np.median(valores))


def metricas_desarrollo(ev: pd.DataFrame) -> pd.DataFrame:
    """Por motor y pliegue: sMAPE del nacional General (suma de bases) y mediana del de las bases."""
    filas = []
    for (engine, fold), g in ev.groupby(["engine", "fold"], sort=True):
        nac = g.groupby(PERIODO)[["y_true_cases", "y_pred_cases"]].sum()
        filas.append(
            {
                "engine": engine,
                "fold": fold,
                "smape_nacional_general": smape_percent(nac["y_true_cases"], nac["y_pred_cases"]),
                "smape_bases": _mediana_bases(g, "y_pred_cases"),
            }
        )
    return pd.DataFrame(filas)


def seleccionar(met: pd.DataFrame, reglas: Reglas) -> dict[str, Any]:
    """Motor único del padecimiento. Sólo desplaza al control con mejora material y mayoritaria."""
    met = met[met["engine"].isin(reglas.candidatos)]
    if reglas.control not in set(met["engine"]):
        raise SombraError("el benchmark de desarrollo no evaluó el control")
    media = met.groupby("engine")[["smape_nacional_general", "smape_bases"]].mean().astype(float)
    nac_media = {str(k): float(v) for k, v in media["smape_nacional_general"].items()}
    nac = met.pivot(index="fold", columns="engine", values="smape_nacional_general")
    ctrl = nac_media[reglas.control]
    elegibles = [reglas.control]
    for e in media.index:
        if e == reglas.control:
            continue
        mejora = (ctrl - nac_media[e]) / max(ctrl, 1e-12) * 100
        gana = int((nac[e] < nac[reglas.control]).sum())
        mayoria = gana * 2 > len(nac) or not reglas.mayoria_pliegues
        if mejora >= reglas.margen_minimo_pct and mayoria:
            elegibles.append(e)
    orden = (
        media.loc[elegibles]
        .reset_index()
        .sort_values(["smape_nacional_general", "smape_bases", "engine"])
    )
    engine = str(orden["engine"].iloc[0])
    return {
        "engine": engine,
        "dev_smape_nacional": nac_media[engine],
        "dev_smape_nacional_control": ctrl,
        "dev_vs_control_pct": (nac_media[engine] - ctrl) / max(ctrl, 1e-12) * 100,
        "elegibles": sorted(elegibles),
        "pliegues": int(len(nac)),
    }


def cuantiles(ev_motor: pd.DataFrame, catalog: GeoCatalog, reglas: Reglas) -> pd.DataFrame:
    """Cuantiles del residuo log1p por producto, con todos los pliegues de desarrollo."""
    prod = productos(
        ev_motor[["geography_id", "sex", "fold", *PERIODO, "y_true_cases", "y_pred_cases"]],
        catalog,
        ["y_true_cases", "y_pred_cases"],
    )
    prod["r"] = np.log1p(prod["y_true_cases"]) - np.log1p(prod["y_pred_cases"])
    filas = []
    for llave, g in prod.groupby(LLAVE, sort=True):
        if len(g) < reglas.min_residuos:
            raise SombraError(f"{llave}: {len(g)} residuos < {reglas.min_residuos}")
        fila = dict(zip(LLAVE, llave, strict=True)) | {"n_residuos": len(g)}
        for i, n in enumerate(reglas.niveles):
            a = (100 - (reglas.cuantil_de[i] if reglas.cuantil_de else n)) / 200
            fila[f"q_lo_{n}"], fila[f"q_hi_{n}"] = np.quantile(g["r"], [a, 1 - a])
        filas.append(fila)
    return pd.DataFrame(filas)


def pronostico(
    historia: Mapping[tuple[str, str], dict[Period, float]],
    engine: str,
    reglas: Reglas,
    q: pd.DataFrame,
    catalog: GeoCatalog,
) -> pd.DataFrame:
    """Motor elegido y control desde el último periodo observado común, con intervalos."""
    origen = min(max(h) for h in historia.values())
    periodos = horizon_periods(origen, reglas.horizonte)
    trains = {k: {p: v for p, v in h.items() if p <= origen} for k, h in historia.items()}
    pv = predicciones_base(trains, engine, periodos, reglas.fuente)
    pc = predicciones_base(trains, reglas.control, periodos, reglas.fuente)
    filas = []
    for geo, sex in sorted(historia):
        for i, p in enumerate(periodos, 1):
            filas.append(
                {
                    "geography_id": geo,
                    "sex": sex,
                    "epi_year": p[0],
                    "epi_week": p[1],
                    "horizon": i,
                    "y_pred_cases": pv[(geo, sex)][p],
                    "control_cases": pc[(geo, sex)][p],
                }
            )
    prod = productos(pd.DataFrame(filas), catalog, ["y_pred_cases", "control_cases"])
    prod = prod.merge(q, on=LLAVE, how="left", validate="many_to_one")
    if prod["n_residuos"].isna().any():
        raise SombraError("hay productos sin cuantiles de desarrollo")
    base = np.log1p(prod["y_pred_cases"])
    for n in reglas.niveles:
        prod[f"lower_{n}"] = np.maximum(np.expm1(base + prod.pop(f"q_lo_{n}")), 0.0)
        prod[f"upper_{n}"] = np.maximum(np.expm1(base + prod.pop(f"q_hi_{n}")), 0.0)
    prod = prod.drop(columns="n_residuos")
    prod.insert(0, "engine", engine)
    prod.attrs["origen"] = origen
    return prod.sort_values([*LLAVE, *PERIODO]).reset_index(drop=True)


def evaluar(
    emision: pd.DataFrame, verdad: pd.DataFrame, publicado: pd.DataFrame, niveles: tuple[int, ...]
) -> dict[str, Any]:
    """Sombra, publicado y control sobre las semanas de la emisión con verdad completa."""
    m = emision.merge(verdad, on=[*LLAVE, *PERIODO], validate="one_to_one")
    m = m.merge(
        publicado.rename(columns={"y_pred_cases": "publicado_cases"}),
        on=[*LLAVE, *PERIODO],
        validate="one_to_one",
    )
    if m.empty:
        return {"semanas": 0}
    nac = m[(m["geography_level"] == "nacional") & (m["sex"] == "general")]
    bases = m[m["geography_level"] == "estado"]
    sexos = set(base_sexes_of(bases["sex"].unique()))
    bases = bases[bases["sex"].isin(sexos)]
    out: dict[str, Any] = {"semanas": int(nac[PERIODO].drop_duplicates().shape[0])}
    for col, nombre in [
        ("y_pred_cases", "sombra"),
        ("publicado_cases", "publicado"),
        ("control_cases", "control"),
    ]:
        out[f"smape_nacional_{nombre}"] = smape_percent(nac["y_true_cases"], nac[col])
        out[f"smape_bases_{nombre}"] = _mediana_bases(bases, col)
    for n in niveles:
        dentro = (m["y_true_cases"] >= m[f"lower_{n}"]) & (m["y_true_cases"] <= m[f"upper_{n}"])
        en_nac = (nac["y_true_cases"] >= nac[f"lower_{n}"]) & (
            nac["y_true_cases"] <= nac[f"upper_{n}"]
        )
        out[f"cobertura_{n}_productos"] = float(dentro.mean() * 100)
        out[f"cobertura_{n}_nacional"] = float(en_nac.mean() * 100)
    return out
