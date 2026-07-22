"""build_obesidad_zoom.py — Genera las entradas de zoom de Obesidad para el EpiBot.

Para cada serie (Nacional + 32 estados + 4 regiones × 3 sexos) arma el payload
``{motor,color,d,r,y,lo,hi,last_real,smape,mase}`` (real reciente + pronóstico del motor
GANADOR de ``produccion_obesidad.csv``) y lo mergea en ``zoom_series.json`` de las copias
del EpiBot, con la clave ``obesidad|<estado_norm>|<sexo>`` que resuelve el bot.

Uso: .venv/bin/python -m scripts.build_obesidad_zoom
"""

from __future__ import annotations

import json
from pathlib import Path
import unicodedata

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MOTOR_COLOR = {
    "Prophet": "#004d40",
    "DeepAR": "#880e4f",
    "Ensemble": "#FF6F00",
    "Stacking": "#1A237E",
}
SEXO_COL = {
    "general": "incrementos_total",
    "hombres": "incrementos_hombres",
    "mujeres": "incrementos_mujeres",
}
WIN_BEFORE, WIN_AFTER = 52, 52  # semanas de real / pronóstico en la ventana


def _norm(text: str) -> str:
    t = str(text).lower()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = "".join(c if (c.isalnum() and c.isascii()) or c == " " else " " for c in t)
    return " ".join(t.split())


def _forecasts() -> pd.DataFrame:
    frames = []
    for m in ("prophet", "ensemble", "stacking"):
        p = ROOT / "reports" / "forecasts" / m / f"all_forecast_{m}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        df = df[df["meta_padecimiento"].astype(str).str.contains("Obesidad", na=False)].copy()
        df["motor"] = m.capitalize()
        frames.append(df)
    fc = pd.concat(frames, ignore_index=True)
    fc["ds"] = pd.to_datetime(fc["ds"])
    return fc


def _real_series(real: pd.DataFrame, entidad: str, sexo: str) -> pd.Series:
    col = SEXO_COL[sexo]
    if entidad == "Nacional":
        s = real.groupby("Fecha")[col].sum()
    elif entidad.startswith("region_"):
        reg = entidad[len("region_") :]
        sub = real[real["region_salud_mental"] == reg]
        s = sub.groupby("Fecha")[col].sum()
    else:
        sub = real[real["Entidad"] == entidad]
        s = sub.groupby("Fecha")[col].sum()
    return s


def _fc_entidad(entidad: str) -> str:
    # produccion usa "region_X"; el forecast usa "Region X".
    if entidad.startswith("region_"):
        return "Region " + entidad[len("region_") :]
    return entidad


def main() -> int:
    prod = pd.read_csv(ROOT / "reports" / "ProdDetails" / "produccion_obesidad.csv")
    real = pd.read_csv(
        ROOT / "data" / "processed" / "data_inegi_Obesidad.csv", parse_dates=["Fecha"]
    )
    fc = _forecasts()
    last_real = real["Fecha"].max()
    lo_date = last_real - pd.Timedelta(weeks=WIN_BEFORE)
    hi_date = last_real + pd.Timedelta(weeks=WIN_AFTER)

    entries: dict[str, dict] = {}
    skipped = 0
    for _, row in prod.iterrows():
        entidad, sexo, motor = row["entidad"], row["sexo"], row["motor_productivo"]
        col = SEXO_COL.get(sexo)
        if col is None:
            continue
        fce = _fc_entidad(entidad)
        sel = fc[
            (fc["motor"] == motor)
            & (fc["meta_entidad"].astype(str) == fce)
            & (fc["meta_modo"] == sexo)
        ]
        if sel.empty:
            skipped += 1
            continue
        sel = sel[(sel["ds"] >= lo_date) & (sel["ds"] <= hi_date)].sort_values("ds")
        rs = _real_series(real, entidad, sexo)
        d, r, y, lo, hi = [], [], [], [], []
        for _, fr in sel.iterrows():
            ds = fr["ds"]
            d.append(ds.strftime("%Y-%m-%d"))
            rv = rs.get(ds)
            r.append(None if (ds > last_real or pd.isna(rv)) else int(round(float(rv))))
            y.append(int(round(float(fr["yhat"]))) if pd.notna(fr["yhat"]) else None)
            lo.append(
                int(round(float(fr["yhat_lower"]))) if pd.notna(fr.get("yhat_lower")) else None
            )
            hi.append(
                int(round(float(fr["yhat_upper"]))) if pd.notna(fr.get("yhat_upper")) else None
            )
        key = f"obesidad|{_norm(entidad.replace('region_', ''))}|{sexo}"
        entries[key] = {
            "motor": motor,
            "color": MOTOR_COLOR.get(motor, "#FF6F00"),
            "d": d,
            "r": r,
            "y": y,
            "lo": lo,
            "hi": hi,
            "last_real": last_real.strftime("%Y-%m-%d"),
            "smape": round(float(row.get(f"smape_{motor.lower()}", 0)) or 0, 1),
            "mase": round(float(row.get(f"mase_{motor.lower()}", 0)) or 0, 2),
        }

    copies = [
        ROOT.parent / "EpiForecast-IMSS-Dashboard" / "epibot" / "zoom_series.json",
        ROOT / "web_dashboard" / "zoom_series.json",
    ]
    for zp in copies:
        if not zp.exists():
            print(f"skip (no existe): {zp}")
            continue
        z = json.loads(zp.read_text(encoding="utf-8"))
        before = len(z)
        z.update(entries)
        zp.write_text(json.dumps(z, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{zp}: {before} -> {len(z)} series (+{len(entries)} obesidad)")
    print(f"entradas obesidad: {len(entries)} | series sin forecast (omitidas): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
