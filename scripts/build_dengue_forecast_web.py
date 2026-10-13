"""Construye el JSON de pronóstico de Dengue para la página pública.

Emite ``dengue_forecast.json`` con dos capas para el gráfico nacional:

1. ``historico``  — incidencia semanal real nacional (conteos), desde el boletín.
2. ``pronostico`` — pronóstico PRODUCTIVO a 1 año (52 sem) del motor ganador para la
   serie nacional general, leído del forecast de liberación (no se reajusta nada aquí).

La antigua capa ``proyeccion`` (NB-GLM nacional ajustado durante el build y proyectado a 5 años
con ``freeze_trend``) se RETIRÓ en la ronda W37 (ENMIENDA_DENGUE_NBGLM_W37, 13-oct-2026): es el
mismo predictor recursivo suspendido, congelar la tendencia no elimina su realimentación y la
proyección no tiene validación propia. Ninguna capa del JSON se extiende más allá de 52 semanas.

Más metadatos de producción: motor nacional y distribución de motores, derivados de la
asignación congelada (``produccion_dengue.csv``).

Uso:
    python -m scripts.build_dengue_forecast_web --out <dir> --generado 2026-06-04
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import warnings

import pandas as pd

from epiforecast.data.boletin import cargar_boletin_dengue
from epiforecast.utils.config import conf
from epiforecast.utils.semana_epi import (
    ds_de_semana_boletin,
    fin_semana_boletin,
    inicio_semana_boletin,
    semana_boletin_de_ds,
)

warnings.filterwarnings("ignore")
logging.getLogger("cmdstanpy").disabled = True

# Rutas derivadas de config (no hardcodeadas).
_REPORTS = Path(conf["paths"]["reports"])
PROD = _REPORTS / "ProdDetails" / "produccion_dengue.csv"
# Forecast por motor: la ruta se deriva del motor asignado; un motor sin archivo aborta en vez
# de caer silenciosamente a otro (meta.motor_nacional mentiría).
HORIZONTE_SEMANAS = 52


def _forecast_path(motor: str) -> Path:
    return _REPORTS / "forecasts" / motor.lower() / f"all_forecast_{motor.lower()}.csv"


def _con_ds_legado(g: pd.DataFrame) -> pd.DataFrame:
    """Fecha cada (Anio, Semana) con el ``ds`` legado del calendario canónico (``semana_epi``).

    Antes se usaba el lunes ISO de la semana ``min(semana, 52)``: lo real quedaba una semana
    después del pronóstico (el ``ds`` legado de la semana N es el lunes ISO de la N-1) y la
    semana 53 (2014, 2025) se fundía con la 52 en el mismo ``ds``. La semana 1 no es evaluable en
    el calendario legado y se descarta; la 53 conserva su identidad.
    """
    g = g[g["Semana"].astype(int) != 1].copy()
    g["ds"] = [
        ds_de_semana_boletin(int(a), int(s)) for a, s in zip(g["Anio"], g["Semana"], strict=True)
    ]
    return g


def serie_nacional() -> pd.DataFrame:
    """Serie nacional general semanal (conteos) en la rejilla de ``ds`` legado del pronóstico.

    Fuente única: el consolidado de producción (``cargar_boletin_dengue``).
    """
    df = cargar_boletin_dengue()
    g = df.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    g = _con_ds_legado(g.sort_values(["Anio", "Semana"]))
    return g.rename(columns={"Casos_semana": "y"})[["ds", "y"]].reset_index(drop=True)


def serie_contexto_a9091() -> pd.DataFrame:
    """Serie nacional semanal 2014-2018W26 del esquema viejo A90/A91 (CONTEXTO, no modelado).

    Otra clasificación y definición de caso; se muestra solo como contexto histórico en el
    gráfico (segmento atenuado) para que la vista de pronóstico arranque desde 2014. Cuentas
    semanales = diff del acumulado nacional dentro de cada año.
    """
    path = Path(conf["paths"]["interim"]) / "dengue_a90a91_nacional.csv"
    if not path.exists():
        return pd.DataFrame(columns=["ds", "y"])
    old = pd.read_csv(path).sort_values(["Anio", "Semana"])
    old["y"] = (
        old.groupby("Anio")["confirmado_acum_nacional"]
        .diff()
        .fillna(old["confirmado_acum_nacional"])
        .clip(lower=0)
    )
    old = _con_ds_legado(old)
    return old[["ds", "y"]].reset_index(drop=True)


def motor_nacional() -> tuple[str, dict[str, int]]:
    """Motor productivo de la serie nacional general + distribución global (asignación congelada)."""
    prod = pd.read_csv(PROD)
    dist = {k: int(v) for k, v in prod["motor_productivo"].value_counts().items()}
    nac = prod[(prod["entidad"] == "Nacional") & (prod["sexo"] == "general")]
    if len(nac) != 1:
        raise SystemExit(f"produccion_dengue: {len(nac)} filas Nacional/general (se espera 1)")
    return str(nac["motor_productivo"].iloc[0]), dist


def pronostico_productivo(motor: str, last_real: pd.Timestamp) -> pd.DataFrame:
    """Pronóstico futuro (1 año) del motor ganador para nacional general."""
    df = pd.read_csv(_forecast_path(motor), low_memory=False)
    d = df[
        (df["meta_padecimiento"] == "Dengue")
        & (df["meta_entidad"] == "Nacional")
        & (df["meta_modo"] == "general")
    ].copy()
    d["ds"] = pd.to_datetime(d["ds"])
    cols = [
        c
        for c in [
            "ds",
            "yhat",
            "yhat_lower",
            "yhat_upper",
            "anio_boletin_corte",
            "semana_boletin_corte",
        ]
        if c in d.columns
    ]
    d = d[d["ds"] > last_real][cols].sort_values("ds")
    if len(d) > HORIZONTE_SEMANAS:
        raise SystemExit(
            f"pronóstico nacional con {len(d)} semanas futuras (> {HORIZONTE_SEMANAS})"
        )
    return d


def _semana_publicada(sem: tuple[int, int]) -> dict[str, object]:
    anio, semana = int(sem[0]), int(sem[1])
    return {
        "anio": anio,
        "semana": semana,
        "inicio": inicio_semana_boletin(anio, semana).isoformat(),
        "fin": fin_semana_boletin(anio, semana).isoformat(),
    }


def _corte_modelo(pron: pd.DataFrame) -> dict[str, object] | None:
    """Semana de corte que el pronóstico declara (``anio/semana_boletin_corte``), si la trae."""
    cols = {"anio_boletin_corte", "semana_boletin_corte"}
    if pron.empty or not cols <= set(pron.columns):
        return None
    pares = pron[list(sorted(cols))].dropna().drop_duplicates()
    if len(pares) != 1:
        raise SystemExit(f"pronóstico nacional con {len(pares)} cortes distintos (se espera 1)")
    return _semana_publicada(
        (int(pares["anio_boletin_corte"].iloc[0]), int(pares["semana_boletin_corte"].iloc[0]))
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Directorio de salida (Reports/dengue)")
    ap.add_argument("--generado", required=True, help="Fecha de generación YYYY-MM-DD")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    serie = serie_nacional()
    contexto = serie_contexto_a9091()
    last_real = serie["ds"].max()
    motor, dist = motor_nacional()
    pron = pronostico_productivo(motor, last_real)

    def _pts(df: pd.DataFrame, *cols: str) -> list[dict[str, object]]:
        rows = []
        for _, r in df.iterrows():
            d = {"ds": pd.Timestamp(r["ds"]).strftime("%Y-%m-%d")}
            for c in cols:
                if c in df.columns:
                    d[c] = round(float(r[c]), 1)
            rows.append(d)
        return rows

    data = {
        "meta": {
            "generado": args.generado,
            "ultima_real": last_real.strftime("%Y-%m-%d"),
            # Identidad publicada de la última semana real y de la semana de corte del modelo:
            # el ``ds`` legado no es la fecha del boletín (calendario v2, ``semana_epi``).
            "ultima_semana_boletin": _semana_publicada(semana_boletin_de_ds(last_real)),
            "corte_modelo": _corte_modelo(pron),
            "motor_nacional": motor,
            "distribucion": dist,
            "horizonte_semanas": HORIZONTE_SEMANAS,
            # Eje del gráfico: desde 2014 (historia completa con los ciclos epidémicos reales).
            # El chart usa escala logarítmica para que el pico de 2024 (~10 mil/sem) y los años
            # bajos + el pronóstico (~cientos-miles/sem) sean todos visibles y proporcionados.
            "chart_from_year": 2014,
            "escala": "log",
        },
        "historico_contexto": _pts(contexto, "y"),
        "historico": _pts(serie, "y"),
        "pronostico": _pts(pron, "yhat", "yhat_lower", "yhat_upper"),
    }
    (out / "dengue_forecast.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"dengue_forecast.json: motor nacional={motor} | "
        f"hist={len(data['historico'])} pron={len(data['pronostico'])} | dist={dist}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
