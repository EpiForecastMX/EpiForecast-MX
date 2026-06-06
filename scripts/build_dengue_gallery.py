#!/usr/bin/env python
"""build_dengue_gallery.py — Gráficos por entidad/sexo de Dengue para la galería pública.

Para cada serie (entidad × sexo) genera un PNG con la realidad del boletín (histórico)
y el pronóstico del MOTOR PRODUCTIVO seleccionado por `produccion_dengue.py`, en el tema
Clinical Indigo. Los escribe en la estructura que espera la galería del dashboard
(`Reports/dengue/{Entidad}/Dengue_{Entidad}_{sexo}.png`) y emite la lista de items JSON
para inyectar en `Reports/index.html`.

Uso:
    python scripts/build_dengue_gallery.py --out ../EpiForecast-IMSS-Dashboard/Reports/dengue
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

warnings.filterwarnings("ignore")

from epiforecast.constants import COVID_END, COVID_START, ENTIDAD_DISPLAY  # noqa: E402
from epiforecast.data import enso  # noqa: E402
from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402
from epiforecast.data.ingestion.inegi_constants import REGION_SALUD_MENTAL  # noqa: E402
from epiforecast.evaluation.metrics import compute_forecast_metrics  # noqa: E402
from epiforecast.utils.config import conf, logger  # noqa: E402
from epiforecast.visualization.web_theme import (  # noqa: E402
    AMBER,
    BG,
    GRID,
    MINT,
    MUTED,
    PINK,
    TEXT,
)

_NINO = "#E0833B"  # cálido: El Niño
_NINA = "#4F9BD9"  # frío: La Niña
_COVID = "#8892B0"

PROD = Path(conf["paths"]["reports"]) / "ProdDetails" / "produccion_dengue.csv"
FC_BASE = Path(conf["paths"]["reports"]) / "forecasts"
NEURO_BOLETIN = Path("data/processed/dataset_boletin_epidemiologico.csv")
SEXOS = {"general": "General", "hombres": "Hombres", "mujeres": "Mujeres"}
MOTOR_COLOR = {"DeepAR": PINK, "Prophet": MINT, "NBGLM": AMBER}
ZOOM_BACK = 52  # semanas reales hacia atrás en la vista zoom
ZOOM_FWD = 52  # semanas de pronóstico hacia adelante (más allá de la última real)

# Dengue no tiene modelo regional: las 4 regiones se agregan desde sus estados.
# (carpeta, nombre en la galería = igual que neuro, region_short de REGION_SALUD_MENTAL)
DENGUE_REGIONES = [
    ("Region_Metropolitana_alta", "Region Metropolitana alta", "Metropolitana alta"),
    ("Region_Rural_-_dispersa", "Region Rural - dispersa", "Rural / dispersa"),
    ("Region_Sur-Sureste_vulnerable", "Region Sur-Sureste vulnerable", "Sur-Sureste vulnerable"),
    ("Region_Urbana_media", "Region Urbana media", "Urbana media"),
]

# El boletín usa nombres cortos de entidad; REGION_SALUD_MENTAL usa los largos del INEGI.
_REGION_ENT_FIX = {
    "Coahuila de Zaragoza": "Coahuila",
    "Michoacán de Ocampo": "Michoacán",
    "Veracruz de Ignacio de la Llave": "Veracruz",
}
_FC_CACHE: dict[str, pd.DataFrame] = {}
_BOL_CACHE: list[pd.DataFrame] = []


def _safe(s: str) -> str:
    return s.replace(" ", "_").replace("/", "_")


def _load_fc(motor: str) -> pd.DataFrame:
    """Lee (y cachea) el all_forecast_<motor>.csv una sola vez por proceso."""
    if motor not in _FC_CACHE:
        path = FC_BASE / motor.lower() / f"all_forecast_{motor.lower()}.csv"
        if not path.exists():
            _FC_CACHE[motor] = pd.DataFrame()
        else:
            df = pd.read_csv(path, low_memory=False)
            df["ds"] = pd.to_datetime(df["ds"])
            _FC_CACHE[motor] = df
    return _FC_CACHE[motor]


def _fc_series(motor: str, pad_fc: str, entidad: str, sexo: str) -> pd.DataFrame:
    """Serie de pronóstico (ds, yhat, banda) para una combinación, ordenada por fecha."""
    df = _load_fc(motor)
    if df.empty:
        return pd.DataFrame()
    d = df[
        (df["meta_padecimiento"] == pad_fc)
        & (df["meta_entidad"].fillna("Nacional") == entidad)
        & (df["meta_modo"] == sexo)
    ]
    cols = [c for c in ["ds", "yhat", "yhat_lower", "yhat_upper"] if c in d.columns]
    return d[cols].sort_values("ds").reset_index(drop=True)


def forecast_future(
    motor: str, pad_fc: str, entidad: str, sexo: str, last_real: pd.Timestamp, n: int = 52
) -> pd.DataFrame:
    """Solo el tramo futuro (ds > última real), hasta ``n`` semanas. Para el histórico completo."""
    d = _fc_series(motor, pad_fc, entidad, sexo)
    return d[d["ds"] > last_real].head(n) if not d.empty else d


def forecast_window(
    motor: str, pad_fc: str, entidad: str, sexo: str, ds_min: pd.Timestamp, ds_max: pd.Timestamp
) -> pd.DataFrame:
    """Pronóstico dentro de [ds_min, ds_max]: SOLAPA la realidad reciente (para comparar) y se
    extiende al futuro. Es lo que hace al zoom un 'real vs pronóstico' como el del EpiBot."""
    d = _fc_series(motor, pad_fc, entidad, sexo)
    return (
        d[(d["ds"] >= ds_min) & (d["ds"] <= ds_max)].reset_index(drop=True) if not d.empty else d
    )


def _band_degenerate(fc: pd.DataFrame) -> bool:
    """True si el motor no aporta intervalo real (Ensemble/Stacking dan lower=upper=yhat)."""
    if fc.empty or not {"yhat_lower", "yhat_upper"} <= set(fc.columns):
        return True
    return float((fc["yhat_upper"] - fc["yhat_lower"]).abs().max()) < 1e-6


def _overlay_covid(ax: object) -> None:
    """Banda COVID super suavizada: sombra muy tenue del periodo COVID (si cae en el rango)."""
    import matplotlib.dates as _md

    x0, x1 = ax.get_xlim()  # type: ignore[attr-defined]
    cs, ce = _md.date2num(pd.Timestamp(COVID_START)), _md.date2num(pd.Timestamp(COVID_END))
    if ce < x0 or cs > x1:
        return
    a, b = max(cs, x0), min(ce, x1)
    ax.axvspan(a, b, color=_COVID, alpha=0.06, lw=0, zorder=0)  # type: ignore[attr-defined]
    ax.annotate(  # type: ignore[attr-defined]
        "COVID-19",
        xy=((a + b) / 2, 0.985),
        xycoords=("data", "axes fraction"),
        ha="center",
        va="top",
        color=MUTED,
        fontsize=6.5,
        alpha=0.45,
    )
    ax.set_xlim(x0, x1)  # type: ignore[attr-defined]


def _shade_runs(ax: object, dates: list, mask: np.ndarray[Any, Any], color: str) -> None:
    """Sombrea tramos contiguos donde ``mask`` es True (para bandas ENSO suaves)."""
    import matplotlib.dates as _md

    start = None
    for i, on in enumerate([*list(mask), False]):
        if on and start is None:
            start = dates[i]
        elif not on and start is not None:
            ax.axvspan(  # type: ignore[attr-defined]
                _md.date2num(start),
                _md.date2num(dates[i - 1]),
                color=color,
                alpha=0.07,
                lw=0,
                zorder=0,
            )
            start = None


def _overlay_enso(ax: object, dates: list) -> None:
    """Bandas El Niño/La Niña super suavizadas (ONI rezagado, media móvil 15 sem)."""
    if not dates:
        return
    uniq = sorted(pd.unique(pd.to_datetime(pd.Series(dates))))  # ONI no admite fechas duplicadas
    if not uniq:
        return
    x0, x1 = ax.get_xlim()  # type: ignore[attr-defined]
    oni = enso.oni_for_dates(pd.Series(uniq), lag_weeks=0)
    s = pd.Series(oni).rolling(15, center=True, min_periods=1).mean().to_numpy()
    _shade_runs(ax, uniq, s >= 0.5, _NINO)
    _shade_runs(ax, uniq, s <= -0.5, _NINA)
    ax.set_xlim(x0, x1)  # type: ignore[attr-defined]


def _metric_tag(ax: object, smape: float | None, mase: float | None) -> None:
    """Etiqueta discreta y elegante con SMAPE y MASE (abajo a la derecha)."""
    parts = []
    if smape is not None and np.isfinite(smape):
        parts.append(f"SMAPE {smape:.1f}%")
    if mase is not None and np.isfinite(mase):
        parts.append(f"MASE {mase:.2f}")
    if not parts:
        return
    ax.text(  # type: ignore[attr-defined]
        0.987,
        0.05,
        "   ·   ".join(parts),
        transform=ax.transAxes,  # type: ignore[attr-defined]
        ha="right",
        va="bottom",
        color=MUTED,
        fontsize=7.5,
        fontweight="bold",
        alpha=0.9,
        bbox={"boxstyle": "round,pad=0.32", "fc": BG, "ec": GRID, "lw": 0.6, "alpha": 0.85},
    )


def series_metrics(real: pd.DataFrame, fc: pd.DataFrame) -> tuple[float | None, float | None]:
    """SMAPE y MASE del solape reciente (real vs pronóstico), homogéneo para toda serie."""
    if real.empty or fc.empty:
        return (None, None)
    j = real.set_index("ds")[["y"]].join(fc.set_index("ds")[["yhat"]], how="inner").dropna()
    if len(j) < 4:
        return (None, None)
    train = real[real["ds"] < j.index.min()]["y"].to_numpy(dtype=float)
    if len(train) < 10:
        train = real["y"].to_numpy(dtype=float)
    m = compute_forecast_metrics(
        j["y"].to_numpy(dtype=float), j["yhat"].to_numpy(dtype=float), train
    )
    sm, ma = m.get("smape"), m.get("mase")
    return (
        float(sm) if sm is not None else None,
        float(ma) if ma is not None else None,
    )


def _resid_std(real: pd.DataFrame, fc: pd.DataFrame) -> float | None:
    """Desviación de los residuales (real - yhat) en las semanas que real y pronóstico comparten."""
    if real.empty or fc.empty:
        return None
    j = real.set_index("ds")[["y"]].join(fc.set_index("ds")[["yhat"]], how="inner").dropna()
    if len(j) < 4:
        return None
    s = float((j["y"] - j["yhat"]).std())
    return s if np.isfinite(s) and s > 0 else None


def empirical_band(
    fc: pd.DataFrame, std: float | None, last_real: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Banda empírica de incertidumbre, SIEMPRE (ignora el intervalo nativo del motor).

    ±1.96·σ de los residuales recientes (real - yhat del solape); si no hay solape, respaldo
    tipo Poisson (±1.96·√yhat), apropiado para conteos. Se usa en el ZOOM para uniformar el ancho
    entre motores: todas las series muestran la misma clase de banda (el error observado), sin que
    Prophet/DeepAR/NB-GLM se vean distintos de Ensemble/Stacking.

    Si se pasa ``last_real``, la banda SOLO se dibuja sobre el tramo futuro (ds > última real):
    sobre las semanas ya observadas no hay incertidumbre que mostrar (ahí va la realidad), así que
    la banda quedaría redundante. La línea de pronóstico sí se conserva sobre el solape (comparar).
    """
    if fc.empty:
        return fc
    fc = fc.copy()
    yhat = fc["yhat"].clip(lower=0)
    half = 1.96 * std if (std is not None and std > 0) else 1.96 * np.sqrt(yhat)
    lower = (yhat - half).clip(lower=0)
    upper = yhat + half
    if last_real is not None:
        observado = fc["ds"] <= pd.Timestamp(last_real)  # zona ya vista: sin banda
        lower = lower.mask(observado)
        upper = upper.mask(observado)
    fc["yhat_lower"] = lower
    fc["yhat_upper"] = upper
    return fc


def ensure_band(fc: pd.DataFrame, std: float | None) -> pd.DataFrame:
    """Banda SOLO si el motor da intervalo degenerado (Ensemble/Stacking: lower=upper=yhat).

    Respeta el intervalo nativo de Prophet/DeepAR/NB-GLM. Para el histórico completo, donde
    conviene conservar el intervalo de predicción propio del modelo."""
    if fc.empty or not _band_degenerate(fc):
        return fc
    return empirical_band(fc, std)


def _boletin_neuro() -> pd.DataFrame:
    """Boletín consolidado (2014→W20 2026), conteos por entidad. Reality CURRENTE para neuro."""
    if not _BOL_CACHE:
        df = pd.read_csv(NEURO_BOLETIN, low_memory=False)
        df["Entidad"] = df["Entidad"].replace({"Distrito Federal": "Ciudad de México"})
        _BOL_CACHE.append(df)
    return _BOL_CACHE[0]


def _region_members(region_short: str) -> set[str]:
    return {_REGION_ENT_FIX.get(e, e) for e, r in REGION_SALUD_MENTAL.items() if r == region_short}


def boletin_real(
    pad_fc: str, entidad: str, sexo: str, region_short: str | None = None
) -> pd.DataFrame:
    """Realidad semanal (ds, y) del boletín consolidado, en conteos, CURRENTE hasta W20 2026.

    Nacional = suma de entidades; región = suma de sus miembros; estado = la entidad. El sexo
    distinto de ``general`` se reparte proporcionalmente (H + M = general) como en Dengue, porque
    el boletín reporta el total semanal y el acumulado por sexo en columnas que no reconcilian.
    """
    df = _boletin_neuro()
    df = df[df["Padecimiento"] == pad_fc]
    if entidad == "Nacional":
        sub = df
    elif region_short is not None:
        sub = df[df["Entidad"].isin(_region_members(region_short))]
    else:
        sub = df[df["Entidad"] == entidad]
    if sub.empty:
        return pd.DataFrame(columns=["ds", "y"])
    g = sub.groupby(["Anio", "Semana"], as_index=False).agg(
        c=("Casos_semana", "sum"),
        ah=("Acumulado_hombres", "sum"),
        am=("Acumulado_mujeres", "sum"),
    )
    g = g.sort_values(["Anio", "Semana"])
    if sexo != "general":
        h = float(g.groupby("Anio")["ah"].diff().fillna(g["ah"]).clip(lower=0).sum())
        m = float(g.groupby("Anio")["am"].diff().fillna(g["am"]).clip(lower=0).sum())
        tot = h + m
        p = 0.5 if tot <= 0 else (h / tot if sexo == "hombres" else m / tot)
        g["c"] = g["c"] * p
    g["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(a), min(int(s), 52), 1))
        for a, s in zip(g["Anio"], g["Semana"], strict=False)
    ]
    out = g.groupby("ds", as_index=False)["c"].sum().rename(columns={"c": "y"})
    out["y"] = out["y"].clip(lower=0)
    return out.sort_values("ds").reset_index(drop=True)


def _real_general(df: pd.DataFrame) -> pd.DataFrame:
    """Serie real general (ds, y) = Casos_semana (la cantidad que modela el motor general)."""
    g = df.groupby(["Anio", "Semana"], as_index=False).agg(Casos_semana=("Casos_semana", "sum"))
    g = g.sort_values(["Anio", "Semana"])
    g["y"] = g["Casos_semana"]
    g["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(a), min(int(s), 52), 1))
        for a, s in zip(g["Anio"], g["Semana"], strict=False)
    ]
    return g[["ds", "y"]].reset_index(drop=True)


def _sex_prop(df: pd.DataFrame) -> tuple[float, float]:
    """Proporción (hombres, mujeres) de la entidad, del acumulado por sexo.

    El boletín reporta el total semanal (``Casos_semana``) y el acumulado por sexo en columnas
    distintas que NO reconcilian (sumar H+M del acumulado no da el total). Para que la galería sea
    consistente, hombres/mujeres se muestran como un REPARTO proporcional del total general por la
    razón de sexo observada: así H + M = general, exacto, en realidad y pronóstico.
    """
    g = df.groupby(["Anio", "Semana"], as_index=False).agg(
        ah=("Acumulado_hombres", "sum"), am=("Acumulado_mujeres", "sum")
    )
    g = g.sort_values(["Anio", "Semana"])
    h = float(g.groupby("Anio")["ah"].diff().fillna(g["ah"]).clip(lower=0).sum())
    m = float(g.groupby("Anio")["am"].diff().fillna(g["am"]).clip(lower=0).sum())
    tot = h + m
    return (0.5, 0.5) if tot <= 0 else (h / tot, m / tot)


def _forecast(motor: str, entidad: str, sexo: str, last_real: pd.Timestamp) -> pd.DataFrame:
    path = FC_BASE / motor.lower() / f"all_forecast_{motor.lower()}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    d = df[
        (df["meta_padecimiento"] == "Dengue")
        & (df["meta_entidad"].fillna("Nacional") == entidad)
        & (df["meta_modo"] == sexo)
    ].copy()
    d["ds"] = pd.to_datetime(d["ds"])
    cols = [c for c in ["ds", "yhat", "yhat_lower", "yhat_upper"] if c in d.columns]
    return d[d["ds"] > last_real][cols].sort_values("ds").head(52)


def _chart(
    real: pd.DataFrame,
    fc: pd.DataFrame,
    motor: str,
    titulo: str,
    out: Path,
    metrics: tuple[float | None, float | None] = (None, None),
    enso_overlay: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=130)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    color = MOTOR_COLOR.get(motor, AMBER)
    ax.plot(real["ds"], real["y"], color=MUTED, linewidth=1.6, label="Real (boletín SINAVE)")
    if not fc.empty:
        if {"yhat_lower", "yhat_upper"} <= set(fc.columns):
            ax.fill_between(
                fc["ds"], fc["yhat_lower"].clip(lower=0), fc["yhat_upper"], color=color, alpha=0.15
            )
        ax.plot(
            fc["ds"],
            fc["yhat"].clip(lower=0),
            color=color,
            linewidth=2.2,
            label=f"Pronóstico ({motor})",
        )
    if enso_overlay:  # Dengue: bandas El Niño/La Niña super suavizadas
        _overlay_enso(ax, list(real["ds"]))
    _overlay_covid(ax)  # banda COVID super suavizada (si cae en el rango)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.5, alpha=0.4)
    ax.set_ylabel("Casos por semana", color=MUTED, fontsize=9)
    ax.set_title(titulo, color=TEXT, fontsize=12, pad=10, fontweight="bold")
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=TEXT, fontsize=8.5, loc="upper left")
    _metric_tag(ax, metrics[0], metrics[1])
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=BG, bbox_inches="tight")
    plt.close(fig)


def _zoom_path(out: Path) -> Path:
    """Ruta del PNG zoom: inserta ``_zoom`` antes de la extensión (misma carpeta)."""
    return out.with_name(f"{out.stem}_zoom{out.suffix}")


def _chart_zoom(
    real: pd.DataFrame,
    fc: pd.DataFrame,
    motor: str,
    titulo: str,
    out: Path,
    weeks_back: int = 52,
    metrics: tuple[float | None, float | None] = (None, None),
    enso_overlay: bool = False,
) -> None:
    """Zoom 'real vs pronóstico' (estilo EpiBot): últimas ``weeks_back`` semanas de realidad
    (hasta la semana vigente del boletín) con el pronóstico SOLAPADO sobre esas mismas semanas
    para comparar, y extendido al futuro. El divisor marca la última semana real (presente).

    ``fc`` ya viene acotado por el llamador a la ventana [inicio_real, última_real + 52 sem],
    así que solapa la realidad reciente y continúa hacia adelante.
    """
    r = real.dropna().sort_values("ds").tail(weeks_back)
    if r.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=130)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    color = MOTOR_COLOR.get(motor, AMBER)
    last_real = pd.Timestamp(r["ds"].max())
    wk = int(last_real.isocalendar().week)

    if not fc.empty:
        ax.axvspan(last_real, pd.Timestamp(fc["ds"].max()), color=color, alpha=0.06, zorder=0)
        if {"yhat_lower", "yhat_upper"} <= set(fc.columns):
            ax.fill_between(
                fc["ds"], fc["yhat_lower"].clip(lower=0), fc["yhat_upper"], color=color, alpha=0.16
            )
        ax.plot(
            fc["ds"],
            fc["yhat"].clip(lower=0),
            color=color,
            linewidth=2.4,
            label=f"Pronóstico ({motor})",
        )
    ax.plot(
        r["ds"],
        r["y"].clip(lower=0),
        color=MUTED,
        linewidth=2.0,
        marker="o",
        markersize=2.6,
        markerfacecolor=MUTED,
        markeredgecolor="none",
        label="Real (boletín SINAVE)",
        zorder=5,
    )
    if not fc.empty:
        ax.axvline(last_real, color=TEXT, linewidth=1.0, linestyle=(0, (4, 3)), alpha=0.55)
        ax.annotate(
            f"Semana {wk} · presente",
            xy=(last_real, 1.0),
            xycoords=("data", "axes fraction"),
            xytext=(4, -12),
            textcoords="offset points",
            color=TEXT,
            fontsize=8,
            fontweight="bold",
            ha="left",
            va="top",
            alpha=0.85,
        )

    if enso_overlay:  # Dengue: bandas El Niño/La Niña super suavizadas
        win_dates = sorted({*list(r["ds"]), *(list(fc["ds"]) if not fc.empty else [])})
        _overlay_enso(ax, win_dates)
    _overlay_covid(ax)  # banda COVID (fuera de rango en el zoom reciente, se omite sola)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.5, alpha=0.4)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Casos por semana", color=MUTED, fontsize=9)
    ax.set_title(titulo, color=TEXT, fontsize=12, pad=10, fontweight="bold")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(0)
        lbl.set_fontsize(7.5)
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=TEXT, fontsize=8.5, loc="upper left")
    _metric_tag(ax, metrics[0], metrics[1])
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=BG, bbox_inches="tight")
    plt.close(fig)


def zoom_payload(
    real: pd.DataFrame, fc: pd.DataFrame, motor: str, weeks_back: int = 52
) -> dict[str, object] | None:
    """Datos compactos para el zoom interactivo (Chart.js): real vs pronóstico SOLAPADOS.

    Construye una rejilla de fechas = unión de las semanas reales (últimas ``weeks_back``) y las
    del pronóstico (que el llamador ya acotó a la ventana). En cada fecha alinea real, pronóstico
    y banda (``null`` donde no aplica), de modo que real y pronóstico coexisten en las semanas que
    comparten y el lightbox los compara semana a semana, como el EpiBot. ``last_real`` marca la
    semana vigente del boletín. Enteros. ``None`` si no hay realidad.
    """
    r = real.dropna().sort_values("ds").tail(weeks_back)
    if r.empty:
        return None
    rmap = {
        pd.Timestamp(d).strftime("%Y-%m-%d"): int(round(max(0.0, float(v))))
        for d, v in zip(r["ds"], r["y"], strict=False)
    }
    ymap: dict[str, int] = {}
    lomap: dict[str, int] = {}
    himap: dict[str, int] = {}
    if not fc.empty:
        band = {"yhat_lower", "yhat_upper"} <= set(fc.columns)
        for row in fc.sort_values("ds").itertuples(index=False):
            k = pd.Timestamp(row.ds).strftime("%Y-%m-%d")
            ymap[k] = int(round(max(0.0, float(row.yhat))))
            # banda solo donde existe (tramo futuro; sobre lo observado va enmascarada a NaN)
            if band and pd.notna(row.yhat_lower) and pd.notna(row.yhat_upper):
                lomap[k] = int(round(max(0.0, float(row.yhat_lower))))
                himap[k] = int(round(max(0.0, float(row.yhat_upper))))
    dates = sorted(set(rmap) | set(ymap))
    return {
        "motor": motor,
        "d": dates,
        "r": [rmap.get(k) for k in dates],
        "y": [ymap.get(k) for k in dates],
        "lo": [lomap.get(k) for k in dates],
        "hi": [himap.get(k) for k in dates],
        "last_real": max(rmap),  # semana vigente del boletín (presente)
    }


def _sum_member_forecast(
    short_members: list[str],
    gen_motor: dict[str, str],
    kind: str,
    last_real: pd.Timestamp | None = None,
    ds_min: pd.Timestamp | None = None,
    ds_max: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Suma el pronóstico productivo (general) de los estados de una región, alineado por semana."""
    frames = []
    for m in short_members:
        motor = gen_motor.get(m)
        if not motor:
            continue
        if kind == "future":
            d = forecast_future(motor, "Dengue", m, "general", last_real)  # type: ignore[arg-type]
        else:
            d = forecast_window(motor, "Dengue", m, "general", ds_min, ds_max)  # type: ignore[arg-type]
        if not d.empty:
            frames.append(d[["ds", "yhat"]])
    if not frames:
        return pd.DataFrame(columns=["ds", "yhat"])
    return pd.concat(frames).groupby("ds", as_index=False)["yhat"].sum()


def _dengue_regiones(
    bol: pd.DataFrame,
    gen_motor: dict[str, str],
    out_base: Path,
    items: list[dict[str, str]],
    zoom: dict[str, object],
) -> int:
    """Calcula las 4 regiones de Dengue agregando sus estados (Dengue no tiene modelo regional):
    real = suma del boletín de los miembros; pronóstico = suma del pronóstico productivo de cada
    estado. Misma estética que el resto (banda futura, COVID/ENSO, SMAPE/MASE)."""
    made = 0
    for folder, data_n, region_short in DENGUE_REGIONES:
        members = {ENTIDAD_DISPLAY.get(x, x): x for x in _region_members(region_short)}
        sub = bol[bol["Entidad"].isin(members.keys())]
        if sub.empty:
            continue
        short_members = list(members.values())
        real_gen = _real_general(sub)
        last_real = real_gen["ds"].max()
        win_start = pd.Timestamp(real_gen.sort_values("ds").tail(ZOOM_BACK)["ds"].min())
        ds_max = pd.Timestamp(last_real) + pd.Timedelta(weeks=ZOOM_FWD)
        fc_gen = _sum_member_forecast(short_members, gen_motor, "future", last_real=last_real)
        fcz_gen = _sum_member_forecast(
            short_members, gen_motor, "window", ds_min=win_start, ds_max=ds_max
        )
        region_disp = data_n.replace("Region ", "Región ")
        for sexo in ("general", "hombres", "mujeres"):
            real, fc, fc_zoom = real_gen, fc_gen.copy(), fcz_gen.copy()
            if sexo != "general":
                p_h, p_m = _sex_prop(sub)
                p = p_h if sexo == "hombres" else p_m
                real = real_gen.assign(y=real_gen["y"] * p)
                for d in (fc, fc_zoom):
                    if "yhat" in d.columns:
                        d["yhat"] = d["yhat"] * p
            std = _resid_std(real, fc_zoom)
            fc = ensure_band(fc, std)  # sumado: sin banda nativa -> empírica (futuro)
            fc_zoom = empirical_band(fc_zoom, std, last_real=last_real)
            rel = f"dengue/{folder}/Dengue_{folder}_{sexo}.png"
            titulo = f"Dengue — {region_disp} ({SEXOS[sexo]})"
            met = series_metrics(real, fc_zoom)
            _chart(
                real,
                fc,
                "Agregado estatal",
                titulo,
                out_base.parent / rel,
                metrics=met,
                enso_overlay=True,
            )
            _chart_zoom(
                real,
                fc_zoom,
                "Agregado estatal",
                titulo,
                _zoom_path(out_base.parent / rel),
                metrics=met,
                enso_overlay=True,
            )
            zp = zoom_payload(real, fc_zoom, "Agregado estatal")
            if zp:
                zoom[rel] = zp
            items.append({"p": "Dengue", "n": data_n, "c": "Regional", "s": SEXOS[sexo], "f": rel})
            made += 1
    return made


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Directorio de salida (Reports/dengue)")
    args = ap.parse_args()
    out_base = Path(args.out)

    prod = pd.read_csv(PROD)
    bol = cargar_boletin_dengue()
    bol["Entidad"] = bol["Entidad"].replace(ENTIDAD_DISPLAY)
    # Motor productivo de la serie GENERAL por entidad (hombres/mujeres se derivan del general).
    gen_motor = {
        str(row["entidad"]): str(row["motor_productivo"])
        for _, row in prod[prod["sexo"] == "general"].iterrows()
    }
    items = []
    zoom: dict[str, object] = {}
    n = 0
    for _, r in prod.iterrows():
        ent, sexo = str(r["entidad"]), str(r["sexo"])
        ent_disp = ENTIDAD_DISPLAY.get(ent, ent)
        sub = bol if ent == "Nacional" else bol[bol["Entidad"] == ent_disp]
        if sub.empty:
            continue
        # General real (Casos_semana) + su pronóstico; hombres/mujeres = general × proporción de
        # sexo, para que H + M = general (exacto) en realidad y pronóstico.
        motor = gen_motor.get(ent, str(r["motor_productivo"]))
        real = _real_general(sub)
        last_real = real["ds"].max()
        win_start = pd.Timestamp(real.sort_values("ds").tail(ZOOM_BACK)["ds"].min())
        ds_max = pd.Timestamp(last_real) + pd.Timedelta(weeks=ZOOM_FWD)
        fc = _forecast(motor, ent, "general", last_real)  # futuro: histórico completo
        fc_zoom = forecast_window(motor, "Dengue", ent, "general", win_start, ds_max)  # solapado
        if sexo != "general":
            p_h, p_m = _sex_prop(sub)
            p = p_h if sexo == "hombres" else p_m
            real = real.assign(y=real["y"] * p)
            fc, fc_zoom = fc.copy(), fc_zoom.copy()
            for d in (fc, fc_zoom):
                for c in ("yhat", "yhat_lower", "yhat_upper"):
                    if c in d.columns:
                        d[c] = d[c] * p
        std = _resid_std(real, fc_zoom)  # error reciente del motor (banda homogénea)
        fc = ensure_band(fc, std)  # histórico: respeta banda nativa
        # zoom: banda empírica uniforme entre motores, SOLO sobre el futuro (no sobre lo real)
        fc_zoom = empirical_band(fc_zoom, std, last_real=last_real)
        safe_ent = _safe(ent_disp)
        # Carpeta en MINÚSCULA 'dengue/' (coincide con los assets de dengue.html ya
        # committeados; Netlify es case-sensitive, no usar 'Dengue/').
        rel = f"dengue/{safe_ent}/Dengue_{safe_ent}_{sexo}.png"
        titulo = f"Dengue — {ent_disp} ({SEXOS[sexo]})"
        met = series_metrics(real, fc_zoom)
        _chart(real, fc, motor, titulo, out_base.parent / rel, metrics=met, enso_overlay=True)
        _chart_zoom(
            real,
            fc_zoom,
            motor,
            titulo,
            _zoom_path(out_base.parent / rel),
            metrics=met,
            enso_overlay=True,
        )
        zp = zoom_payload(real, fc_zoom, motor)
        if zp:
            zoom[rel] = zp
        items.append(
            {
                "p": "Dengue",
                "n": ent_disp,
                "c": "Nacional" if ent == "Nacional" else "Estatal",
                "s": SEXOS[sexo],
                "f": rel,
            }
        )
        n += 1

    n += _dengue_regiones(bol, gen_motor, out_base, items, zoom)
    (out_base / "_gallery_items.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )
    (out_base.parent / "zoom_data_dengue.json").write_text(
        json.dumps(zoom, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    logger.success(
        "Galería Dengue: {} gráficos en {} | items + zoom_data_dengue.json", n, out_base
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
