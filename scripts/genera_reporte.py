"""
Genera el reporte HTML interactivo "Resultados del Modelado" (multi-modelo + Dengue).

A diferencia de la version original (que leia solo el CSV de Prophet), este script reproduce
la pagina productiva en vivo a partir de las fuentes canonicas:

  * neuro (3 padecimientos): ``reports/ProdDetails/tabla_333_modelos_produccion.xlsx``
    -> metricas del MOTOR PRODUCTIVO por serie (smape_prod, mase_prod, rmse_prod, mae_prod) +
       distribucion de motores y modo de respaldo (propio / regional fallback).
  * Dengue (4.o padecimiento): ``reports/ProdDetails/produccion_dengue.csv``
    -> distribucion de motor productivo + backtest leave-one-epidemic-out.

El diseno (tema Clinical Indigo, hero, novedades, guia, secciones, Dengue) vive en la plantilla
``scripts/templates/reporte_resultados.tmpl.html`` (versionada). Este script solo inyecta los
datos dinamicos en los tokens ``__...__``, de modo que ``make report`` reproduce la pagina y NO
la regresa a la version Prophet-unica.

Salidas (ambas se sobrescriben):
    reports/forecasts/reporte_resultados.html              (copia local en el repo)
    <Dashboard>/reporte_resultados.html                   (la que se publica en epiforecast.mx)

Uso:
    python -m scripts.genera_reporte
    python -m scripts.genera_reporte --dashboard ../EpiForecast-IMSS-Dashboard
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import unicodedata

import pandas as pd

from epiforecast.utils.config import logger

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
TABLA_NEURO = Path("reports/ProdDetails/tabla_333_modelos_produccion.xlsx")
PROD_DENGUE = Path("reports/ProdDetails/produccion_dengue.csv")
TEMPLATE = Path("scripts/templates/reporte_resultados.tmpl.html")
OUTPUT_LOCAL = Path("reports/forecasts/reporte_resultados.html")
DEFAULT_DASHBOARD = Path("../EpiForecast-IMSS-Dashboard")

# ---------------------------------------------------------------------------
# Constantes de presentacion
# ---------------------------------------------------------------------------
COLORS_BY_SAFE = {
    "alzheimer": {"main": "#2DD4BF", "light": "#5EEAD4", "glow": "rgba(45,212,191,0.12)"},
    "depresion": {"main": "#F472B6", "light": "#F9A8D4", "glow": "rgba(244,114,182,0.12)"},
    "parkinson": {"main": "#5B8DEF", "light": "#93C5FD", "glow": "rgba(91,141,239,0.12)"},
}
# Orden de presentacion -> nombre con acento (como en la pagina)
PAD_ORDER = ["Alzheimer", "Depresión", "Parkinson"]
PAD_DISPLAY = {"Alzheimer": "Alzheimer", "Depresion": "Depresión", "Parkinson": "Parkinson"}
MODO_ORDER = ["general", "hombres", "mujeres"]
MODO_LABELS = {"general": "General", "hombres": "Hombres", "mujeres": "Mujeres"}
ENT_DISPLAY = {"México": "Estado de México"}  # homologado con la galeria

# Backtest leave-one-epidemic-out del Dengue (nacional, epidemia 2024). Ver CLAUDE.md /
# docs/research/hallazgos/DENGUE_*: Prophet 102 -> +El Nino 76 -> NB-GLM 52.
DENGUE_BACKTEST = {"prophet": 102, "prophet_enso": 76, "nbglm": 52}

REGIONES_INEGI = {
    "Metropolitana alta": [
        "Baja California",
        "Chihuahua",
        "Ciudad de México",
        "Coahuila",
        "Jalisco",
        "México",
        "Nuevo León",
        "Sinaloa",
        "Sonora",
        "Tamaulipas",
    ],
    "Urbana media": [
        "Aguascalientes",
        "Baja California Sur",
        "Colima",
        "Durango",
        "Guanajuato",
        "Morelos",
        "Querétaro",
        "San Luis Potosí",
        "Zacatecas",
    ],
    "Sur-Sureste vulnerable": [
        "Campeche",
        "Chiapas",
        "Oaxaca",
        "Quintana Roo",
        "Tabasco",
        "Veracruz",
        "Yucatán",
    ],
    "Rural / dispersa": ["Guerrero", "Hidalgo", "Michoacán", "Nayarit", "Puebla", "Tlaxcala"],
}


def _safe_key(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _clean(v):
    """Make value JSON-safe (no NaN/Inf)."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _round(v, nd):
    return _clean(round(float(v), nd)) if pd.notna(v) else None


# ---------------------------------------------------------------------------
# Carga y normalizacion de neuro (tabla_333 -> shape uniforme)
# ---------------------------------------------------------------------------
def load_neuro() -> pd.DataFrame:
    """Lee tabla_333 y la normaliza al esquema que consumen las estadisticas.

    Cada fila representa una serie con su MOTOR PRODUCTIVO ya elegido; las metricas
    ``*_prod`` son las de ese motor. Las regiones agregadas vienen como ``region_<nombre>``.
    """
    df = pd.read_excel(TABLA_NEURO)
    out = pd.DataFrame()
    out["meta_padecimiento"] = df["padecimiento"].map(lambda p: PAD_DISPLAY.get(str(p), str(p)))
    out["meta_modo"] = df["sexo"].astype(str)
    out["modelo_produccion"] = df["modelo_produccion"].astype(str)
    out["tipo_modelo"] = df["tipo_modelo"].astype(str)

    def _entidad(e: str) -> str:
        e = str(e)
        if e.startswith("region_"):
            return "Region " + e[len("region_") :]
        return ENT_DISPLAY.get(e, e)

    out["meta_entidad"] = df["entidad"].map(_entidad)
    out["mase_usado"] = df["mase_prod"]
    out["rmse_usado"] = df["rmse_prod"]
    out["mae_usado"] = df["mae_prod"]
    out["smape_usado"] = df["smape_prod"]
    # fallback regional -> "insuficiente"; propio -> "normal"
    out["es_fallback"] = out["tipo_modelo"].str.lower().eq("regional")
    out["confianza_original"] = out["es_fallback"].map({True: "insuficiente", False: "normal"})
    return out


def compute_neuro_stats(df: pd.DataFrame) -> dict:
    stats: dict = {}
    estados_df = df[
        ~df["meta_entidad"].str.startswith("Region", na=False) & (df["meta_entidad"] != "Nacional")
    ]

    stats["total_modelos"] = len(df)
    stats["cobertura_estatal"] = round(estados_df["meta_entidad"].nunique() / 32 * 100)
    stats["mase_global"] = _round(df["mase_usado"].mean(), 2)
    stats["smape_global"] = _round(df["smape_usado"].median(), 1)
    stats["fecha"] = datetime.now().strftime("%d/%m/%Y")
    stats["modelos_excelentes"] = int((df["mase_usado"] < 0.7).sum())
    stats["modelos_deficientes"] = int((df["mase_usado"] > 1).sum())

    stats["conteo_tipo"] = {
        "nacional": int((df["meta_entidad"] == "Nacional").sum()),
        "regional": int(df["meta_entidad"].str.startswith("Region", na=False).sum()),
        "estatal": len(estados_df),
    }

    # Distribucion de motores productivos (para los badges de Novedades)
    stats["dist_neuro"] = df["modelo_produccion"].value_counts().to_dict()

    # --- Por padecimiento ---
    pad_stats = []
    for pad in PAD_ORDER:
        sub = df[df["meta_padecimiento"] == pad]
        sub_est = estados_df[estados_df["meta_padecimiento"] == pad]
        fallback = int(sub["es_fallback"].sum())
        n_reg = int(sub["meta_entidad"].str.startswith("Region", na=False).sum())
        pad_stats.append(
            {
                "padecimiento": pad,
                "total": len(sub),
                "estatales": len(sub_est),
                "nacionales": int((sub["meta_entidad"] == "Nacional").sum()),
                "regionales": n_reg,
                "mase": _round(sub["mase_usado"].mean(), 2),
                "rmse": _round(sub["rmse_usado"].mean(), 2),
                "mae": _round(sub["mae_usado"].mean(), 2),
                "smape": _round(sub["smape_usado"].mean(), 1),
                "smape_median": _round(sub["smape_usado"].median(), 1),
                "insuficientes": fallback,
                "fallback": fallback,
                "mase_min": _round(sub["mase_usado"].min(), 2),
                "mase_max": _round(sub["mase_usado"].max(), 2),
                "mase_median": _round(sub["mase_usado"].median(), 2),
            }
        )
    stats["por_padecimiento"] = pad_stats

    # --- MASE histogram ---
    bins = [0, 0.5, 0.7, 0.85, 1.0, 999]
    bin_labels = ["< 0.5", "0.5–0.7", "0.7–0.85", "0.85–1.0", "> 1.0"]
    histo = []
    for pad in PAD_ORDER:
        sub = df[df["meta_padecimiento"] == pad]["mase_usado"].dropna()
        counts = pd.cut(sub, bins=bins, labels=bin_labels, right=False).value_counts()
        histo.append({"padecimiento": pad, "bins": [int(counts.get(b, 0)) for b in bin_labels]})
    stats["mase_histo"] = histo
    stats["mase_bin_labels"] = bin_labels

    # --- Por sexo x padecimiento ---
    sexo_stats = []
    for pad in PAD_ORDER:
        for modo in MODO_ORDER:
            sub = df[(df["meta_padecimiento"] == pad) & (df["meta_modo"] == modo)]
            if len(sub) == 0:
                continue
            sexo_stats.append(
                {
                    "padecimiento": pad,
                    "modo": modo,
                    "modo_label": MODO_LABELS[modo],
                    "count": len(sub),
                    "mase": _round(sub["mase_usado"].mean(), 2),
                    "rmse": _round(sub["rmse_usado"].mean(), 2),
                    "smape": _round(sub["smape_usado"].mean(), 1),
                }
            )
    stats["por_sexo"] = sexo_stats

    # --- Ranking ---
    ranking = []
    for _, row in df.iterrows():
        ent = row["meta_entidad"]
        if ent == "Nacional":
            grupo, orden = "Nacional", 0
        elif str(ent).startswith("Region"):
            grupo, orden = "Regional", 1
        else:
            grupo, orden = "Estatal", 2
        ranking.append(
            {
                "entidad": ent,
                "padecimiento": row["meta_padecimiento"],
                "modo": MODO_LABELS.get(row["meta_modo"], row["meta_modo"]),
                "mase": _round(row["mase_usado"], 2),
                "rmse": _round(row["rmse_usado"], 2),
                "mae": _round(row["mae_usado"], 2),
                "smape": _round(row["smape_usado"], 1),
                "confianza": row["confianza_original"],
                "tipo": "Regional (fallback)" if row["es_fallback"] else "Propio",
                "grupo": grupo,
                "orden": orden,
            }
        )
    stats["ranking"] = ranking

    # --- Cobertura (estado x padecimiento) ---
    cobertura = []
    for estado in sorted(estados_df["meta_entidad"].unique()):
        entry = {"estado": estado}
        for pad in PAD_ORDER:
            sub = estados_df[
                (estados_df["meta_entidad"] == estado) & (estados_df["meta_padecimiento"] == pad)
            ]
            key = _safe_key(pad)
            if len(sub) == 0:
                entry[key] = "sin_modelo"
            else:
                entry[key] = "fallback" if bool(sub["es_fallback"].any()) else "propio"
        cobertura.append(entry)
    cob_resumen = {}
    for pad in PAD_ORDER:
        key = _safe_key(pad)
        cob_resumen[key] = {
            "propios": sum(1 for c in cobertura if c[key] == "propio"),
            "fallback": sum(1 for c in cobertura if c[key] == "fallback"),
        }
    stats["cobertura"] = cobertura
    stats["cobertura_resumen"] = cob_resumen

    # --- Top / Bottom 10 (por MASE) ---
    valid = df[df["mase_usado"].notna()].copy()
    valid["_label"] = (
        valid["meta_entidad"]
        + " — "
        + valid["meta_padecimiento"]
        + " ("
        + valid["meta_modo"]
        + ")"
    )
    for name, method in [("top10", "nsmallest"), ("bottom10", "nlargest")]:
        sel = getattr(valid, method)(10, "mase_usado")
        stats[name] = [
            {
                "label": r["_label"],
                "mase": round(r["mase_usado"], 2),
                "padecimiento": r["meta_padecimiento"],
            }
            for _, r in sel.iterrows()
        ]

    stats["pad_meta"] = [
        {"name": pad, "key": _safe_key(pad), **COLORS_BY_SAFE[_safe_key(pad)]} for pad in PAD_ORDER
    ]
    stats["regiones_inegi"] = REGIONES_INEGI
    return stats


# ---------------------------------------------------------------------------
# Dengue
# ---------------------------------------------------------------------------
DENGUE_MOTORS = [
    ("deepar", "DeepAR", True),
    ("nbglm", "NB-GLM", True),
    ("prophet", "Prophet", True),
    ("ensemble", "Ensemble", False),
    ("stacking", "Stacking", False),
]
DENGUE_MOTOR_NOTE = {
    "Ensemble": "Fuera: los árboles no extrapolan la dinámica epidémica a 52 sem.",
    "Stacking": "Fuera: los árboles no extrapolan la dinámica epidémica a 52 sem.",
}


def compute_dengue_stats() -> dict:
    d = pd.read_csv(PROD_DENGUE)
    dist_all = d["motor_productivo"].value_counts().to_dict()
    dg = d[d["sexo"] == "general"]
    dist_general = dg["motor_productivo"].value_counts().to_dict()
    nac = d[(d["entidad"] == "Nacional") & (d["sexo"] == "general")]
    nacional_motor = str(nac["motor_productivo"].iloc[0]) if len(nac) else "DeepAR"

    # --- Tabla de motores (honesta: series ganadas + en produccion) ---
    motor_table = []
    for key, label, in_prod in DENGUE_MOTORS:
        ganadas = int((d["motor_productivo"].str.lower() == key).sum())
        motor_table.append(
            {
                "motor": label,
                "ganadas": ganadas,
                "en_produccion": in_prod,
                "nota": DENGUE_MOTOR_NOTE.get(label, "En producción"),
            }
        )

    # --- Ranking de las 99 series (entidad x sexo) ---
    ranking = []
    for _, r in d.iterrows():
        ent = str(r["entidad"])
        motor = str(r["motor_productivo"])
        mae_col = f"mae_real_{motor.lower().replace('-', '')}"
        mae = _round(r[mae_col], 1) if mae_col in d.columns else None
        ranking.append(
            {
                "entidad": ent,
                "modo": MODO_LABELS.get(str(r["sexo"]), str(r["sexo"])),
                "motor": "NB-GLM" if motor == "NBGLM" else motor,
                "smape": _round(r["smape_ganador"], 1),
                "mae": mae,
                "casos": int(r["total_real"]) if pd.notna(r["total_real"]) else None,
                "grupo": "Nacional" if ent == "Nacional" else "Estatal",
                "orden": 0 if ent == "Nacional" else 1,
            }
        )

    return {
        "n_series": int(len(d)),
        "n_semanas_real": int(nac["n_semanas_real"].iloc[0]) if len(nac) else None,
        "casos_2026": int(nac["total_real"].iloc[0]) if len(nac) else None,
        "dist_all": {str(k): int(v) for k, v in dist_all.items()},
        "dist_general": {str(k): int(v) for k, v in dist_general.items()},
        "nacional_motor": nacional_motor,
        "nacional_smape": _round(nac["smape_ganador"].iloc[0], 1) if len(nac) else None,
        "backtest": DENGUE_BACKTEST,
        "smape_ganador_median": _round(d["smape_ganador"].median(), 1),
        "motor_table": motor_table,
        "ranking": ranking,
    }


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def _badge(name: str, count: int) -> str:
    cls = {"DeepAR": "badge-green", "Prophet": "badge-green"}.get(name, "badge-yellow")
    label = "NB-GLM" if name == "NBGLM" else name
    return f'<span class="badge {cls}">{label} {count}</span>'


def _neuro_dist_badges(dist: dict) -> str:
    order = ["DeepAR", "Prophet", "Ensemble", "Stacking"]
    items = sorted(dist.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)
    return "\n        ".join(_badge(k, v) for k, v in items)


def _pad_explain(pad_stats: list[dict]) -> str:
    parts = []
    for p in pad_stats:
        n_reg = p["regionales"] // 3
        if p["fallback"] == 0:
            parts.append(
                f"<strong>{p['padecimiento']}</strong>: {p['total']} modelos "
                f"(99 base + {p['regionales']} regionales de respaldo). "
                f"Todos los estados tienen su propio modelo."
            )
        else:
            parts.append(
                f"<strong>{p['padecimiento']}</strong>: {p['total']} modelos "
                f"(99 base + {p['regionales']} regionales de respaldo). "
                f"{p['fallback']} series estatales usan el modelo de su region "
                f"({n_reg} regiones activas)."
            )
    return "<br>".join(parts)


def _dengue_chart_cap(dg: dict) -> str:
    g = dg["dist_general"]
    parts = ", ".join(
        f"{'NB-GLM' if k == 'NBGLM' else k} {g[k]}" for k in sorted(g, key=lambda k: -g[k])
    )
    return (
        f"Izquierda: motor productivo por serie ({dg['nacional_motor']} a nivel nacional; "
        f"a nivel general {parts}). Derecha: backtest fuera de muestra sobre la epidemia 2024 "
        f"(leave-one-epidemic-out); agregar El Niño y el motor NB-GLM reducen el SMAPE de "
        f"102 a 52."
    )


def build_html(stats: dict, dengue: dict) -> str:
    stats = {**stats, "dengue": dengue}
    html = TEMPLATE.read_text(encoding="utf-8")
    repl = {
        "__DATA_JSON__": json.dumps(stats, ensure_ascii=False),
        "__FECHA__": stats["fecha"],
        "__TOTAL__": str(stats["total_modelos"]),
        "__NEURO_DIST_BADGES__": _neuro_dist_badges(stats["dist_neuro"]),
        "__PAD_EXPLAIN__": _pad_explain(stats["por_padecimiento"]),
        "__DENGUE_CHART_CAP__": _dengue_chart_cap(dengue),
    }
    for tok, val in repl.items():
        html = html.replace(tok, val)
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dashboard",
        default=str(DEFAULT_DASHBOARD),
        help="Ruta al repo del dashboard (se publica ahi reporte_resultados.html)",
    )
    args = ap.parse_args()

    logger.info("Leyendo neuro: {}", TABLA_NEURO)
    neuro = load_neuro()
    logger.info("{} series neuro.", len(neuro))
    stats = compute_neuro_stats(neuro)

    logger.info("Leyendo Dengue: {}", PROD_DENGUE)
    dengue = compute_dengue_stats()
    logger.info("Dengue: {} series, motores {}", dengue["n_series"], dengue["dist_all"])

    logger.info("Generando HTML desde plantilla {}", TEMPLATE)
    html = build_html(stats, dengue)

    outputs = [OUTPUT_LOCAL]
    dash = Path(args.dashboard)
    if dash.exists():
        outputs.append(dash / "reporte_resultados.html")
    else:
        logger.warning("Dashboard no encontrado en {}; solo se escribe la copia local.", dash)

    for out in outputs:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        logger.success("Reporte escrito: {}", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
