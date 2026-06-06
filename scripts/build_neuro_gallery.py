#!/usr/bin/env python
"""build_neuro_gallery.py — Regenera la galería neuro en estilo LIMPIO (igual que Dengue).

Los gráficos neuro originales superponen los 4 motores (Prophet/DeepAR/Ensemble/Stacking),
lo que se ve ruidoso. Este script los reemplaza con el mismo estilo de la galería de Dengue:
serie real (gris) + pronóstico del SOLO motor productivo (con su banda), tema Clinical Indigo.

Por cada serie genera DOS PNG: el histórico completo (``X.png``) y la vista de acercamiento
``X_zoom.png`` (últimas 52 semanas reales + las 52 del pronóstico), que la galería alterna con
el toggle de vista. Cubre Nacional, las 32 entidades y las 4 regiones agregadas.

Sobrescribe los PNG existentes en sus rutas exactas (no toca index.html).

Uso:
    python scripts/build_neuro_gallery.py --out ../EpiForecast-IMSS-Dashboard/Reports
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import pandas as pd  # noqa: E402

warnings.filterwarnings("ignore")

from scripts.build_dengue_gallery import (  # noqa: E402
    _chart,
    _chart_zoom,
    _zoom_path,
    zoom_payload,
)

from epiforecast.utils.config import conf, logger  # noqa: E402
from epiforecast.visualization.comparison_plots import _load_serie_real  # noqa: E402

REPORTS = Path(conf["paths"]["reports"])
TABLA = REPORTS / "ProdDetails" / "tabla_333_modelos_produccion.xlsx"
FC_BASE = REPORTS / "forecasts"
PADS = ["Depresion", "Parkinson", "Alzheimer"]
FC_PAD = {"Depresion": "Depresión", "Parkinson": "Parkinson", "Alzheimer": "Alzheimer"}
SEXOS = {"general": "General", "hombres": "Hombres", "mujeres": "Mujeres"}
ENT_DISPLAY = {"México": "Estado de México"}  # homologado en la galería

# Las 4 regiones agregadas se nombran distinto en cada capa: carpeta (índice de DATA),
# meta_entidad del forecast y entidad de tabla_333. Este mapa concilia las tres.
REGIONS = {
    "Region_Metropolitana_alta": ("Region Metropolitana alta", "region_Metropolitana alta"),
    "Region_Rural_-_dispersa": ("Region Rural / dispersa", "region_Rural / dispersa"),
    "Region_Sur-Sureste_vulnerable": (
        "Region Sur-Sureste vulnerable",
        "region_Sur-Sureste vulnerable",
    ),
    "Region_Urbana_media": ("Region Urbana media", "region_Urbana media"),
}


def _region_display(ent: str) -> str:
    """``Region Metropolitana alta`` -> ``Región Metropolitana alta`` para el título."""
    return ent.replace("Region ", "Región ", 1)


def _real(pad: str, ent: str, modo: str) -> pd.DataFrame:
    df = _load_serie_real(conf, pad, ent, modo)
    if df is None or "y_original" not in df.columns:
        return pd.DataFrame(columns=["ds", "y"])
    out = df[["ds"]].copy()
    out["y"] = pd.to_numeric(df["y_original"], errors="coerce").clip(lower=0)
    return out.dropna().reset_index(drop=True)


def _forecast(
    motor: str, pad_fc: str, ent: str, modo: str, last_real: pd.Timestamp
) -> pd.DataFrame:
    path = FC_BASE / motor.lower() / f"all_forecast_{motor.lower()}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    d = df[
        (df["meta_padecimiento"] == pad_fc)
        & (df["meta_entidad"].fillna("Nacional") == ent)
        & (df["meta_modo"] == modo)
    ].copy()
    d["ds"] = pd.to_datetime(d["ds"])
    cols = [c for c in ["ds", "yhat", "yhat_lower", "yhat_upper"] if c in d.columns]
    return d[d["ds"] > last_real][cols].sort_values("ds").head(52)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Directorio Reports/ del dashboard")
    args = ap.parse_args()
    out_base = Path(args.out)

    tabla = pd.read_excel(TABLA, usecols=["padecimiento", "entidad", "sexo", "modelo_produccion"])
    motor_map = {
        (str(r.padecimiento), str(r.entidad), str(r.sexo)): str(r.modelo_produccion)
        for r in tabla.itertuples(index=False)
    }

    n = skip = 0
    zoom: dict[str, object] = {}
    for pad in PADS:
        pad_disp = FC_PAD[pad]  # nombre en carpeta/archivo (con acento: 'Depresión')
        pad_dir = out_base / pad_disp
        if not pad_dir.exists():
            continue
        for folder in sorted(p for p in pad_dir.iterdir() if p.is_dir()):
            fname = folder.name
            if fname in REGIONS:  # región agregada: concilia los 3 nombres
                real_ent, tabla_ent = REGIONS[fname]
                ent_label = _region_display(real_ent)
            else:  # estado o Nacional: carpeta -> entidad directa
                real_ent = tabla_ent = fname.replace("_", " ")
                ent_label = ENT_DISPLAY.get(real_ent, real_ent)
            for sexo in ("general", "hombres", "mujeres"):
                img = folder / f"{pad_disp}_{fname}_{sexo}.png"
                if not img.exists():
                    continue
                motor = motor_map.get((pad, tabla_ent, sexo))
                if not motor:
                    skip += 1
                    continue
                real = _real(pad, real_ent, sexo)
                if real.empty:
                    skip += 1
                    continue
                last_real = real["ds"].max()
                fc = _forecast(motor, FC_PAD[pad], real_ent, sexo, last_real)
                titulo = f"{FC_PAD[pad]} — {ent_label} ({SEXOS[sexo]})"
                _chart(real, fc, motor, titulo, img)  # sobrescribe en su ruta exacta
                _chart_zoom(real, fc, motor, titulo, _zoom_path(img))
                rel = f"{pad_disp}/{fname}/{pad_disp}_{fname}_{sexo}.png"
                zp = zoom_payload(real, fc, motor)
                if zp:
                    zoom[rel] = zp
                n += 1
    (out_base / "zoom_data_neuro.json").write_text(
        json.dumps(zoom, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    logger.success(
        "Galería neuro (estilo limpio): {} gráficos ({} series con zoom) | {} omitidos",
        n,
        len(zoom),
        skip,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
