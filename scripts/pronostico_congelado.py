#!/usr/bin/env python
"""pronostico_congelado.py — Congela el pronostico productivo y lo valida prospectivo (OOS).

Motiva: la metrica `smape_real_2026` con la que se elige el motor productivo es
IN-SAMPLE (el modelo se entrena sobre la serie completa, incluyendo 2026 H1, y se
puntua su ajuste in-sample). Para medir desempeno honesto out-of-sample se congela
el pronostico vigente HOY (solo la cola futura, ds > ultima semana real = no vista) y
se confronta contra los boletines que lleguen DESPUES, antes de que el re-entrenamiento
semanal sobreescriba el modelo. Ver docs/research/hallazgos/DENGUE_AUDITORIA_LEAKAGE.md.

Modos:
  freeze  : crea reports/ProdDetails/congelado/forecast_congelado_<YYYYMMDD>.csv con el
            pronostico del motor productivo por serie para ds > corte, y actualiza el
            puntero forecast_congelado_latest.txt.
  validar : lee el congelado mas reciente, construye el real semanal del boletin actual
            y reporta SMAPE/MAE OOS por serie y agregado (HTML + CSV). Solo puntua
            semanas posteriores al corte (genuinamente no vistas al congelar).

Cubre los 4 padecimientos: neuro (motor en tabla_333) y Dengue (motor en produccion_dengue.csv).

Uso:
    python scripts/pronostico_congelado.py freeze
    python scripts/pronostico_congelado.py validar
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
import unicodedata
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from epiforecast.evaluation.real_eval import build_real, eval_year
from epiforecast.utils.config import conf, logger

REPORTS = Path(conf["paths"]["reports"])
FC_BASE = REPORTS / "forecasts"
CONG_DIR = REPORTS / "ProdDetails" / "congelado"
PTR = CONG_DIR / "forecast_congelado_latest.txt"
TABLA_333 = REPORTS / "ProdDetails" / "tabla_333_modelos_produccion.xlsx"
PROD_DENGUE = REPORTS / "ProdDetails" / "produccion_dengue.csv"
TZ = ZoneInfo("America/Mexico_City")

# Solo semana ISO -> fecha (lunes) para alinear forecast (ds, W-MON) con boletin (Semana).
SEXOS = ("general", "hombres", "mujeres")


def _norm(s: str) -> str:
    """Normaliza padecimiento para joins (sin acentos, minuscula)."""
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


def _smape(y: np.ndarray, yh: np.ndarray) -> float:
    y, yh = np.asarray(y, float), np.asarray(yh, float)
    den = np.abs(y) + np.abs(yh)
    m = den > 0
    return float(100 * np.mean(2 * np.abs(yh - y)[m] / den[m])) if m.any() else float("nan")


# ---------------------------------------------------------------------------
# Mapa de motor productivo por serie (neuro + Dengue)
# ---------------------------------------------------------------------------


def _load_prod_map() -> pd.DataFrame:
    """DataFrame [pad_norm, pad_disp, entidad, sexo, motor_key] con el motor productivo."""
    frames = []
    if TABLA_333.exists():
        t = pd.read_excel(
            TABLA_333, usecols=["padecimiento", "entidad", "sexo", "modelo_produccion"]
        )
        t = t.rename(columns={"modelo_produccion": "motor"})
        frames.append(t)
    if PROD_DENGUE.exists():
        d = pd.read_csv(
            PROD_DENGUE, usecols=["padecimiento", "entidad", "sexo", "motor_productivo"]
        )
        d = d.rename(columns={"motor_productivo": "motor"})
        frames.append(d)
    prod = pd.concat(frames, ignore_index=True)
    prod = prod.dropna(subset=["motor"])
    prod["pad_norm"] = prod["padecimiento"].map(_norm)
    prod["pad_disp"] = prod["padecimiento"]
    prod["motor_key"] = prod["motor"].str.lower()
    return prod[["pad_norm", "pad_disp", "entidad", "sexo", "motor_key"]]


def _cutoffs() -> dict[str, tuple[int, int, pd.Timestamp]]:
    """Por pad_norm: (anio, ultima_semana_real, fecha_corte) del boletin vigente."""
    bol = pd.read_csv(conf["data"]["boletin"], usecols=["Padecimiento", "Anio", "Semana"])
    out = {}
    for pad, sub in bol.groupby("Padecimiento"):
        anio = int(sub["Anio"].max())
        wk = int(sub[sub["Anio"] == anio]["Semana"].max())
        corte = pd.Timestamp(date.fromisocalendar(anio, min(wk, 52), 1))
        out[_norm(pad)] = (anio, wk, corte)
    return out


# ---------------------------------------------------------------------------
# FREEZE
# ---------------------------------------------------------------------------


def freeze() -> int:
    prod = _load_prod_map()
    cutoffs = _cutoffs()
    hoy = datetime.now(TZ).strftime("%Y%m%d")
    rows = []
    for motor_key in sorted(prod["motor_key"].unique()):
        fpath = FC_BASE / motor_key / f"all_forecast_{motor_key}.csv"
        if not fpath.exists():
            logger.warning("Sin forecast para motor '{}' ({}), se omite", motor_key, fpath)
            continue
        fc = pd.read_csv(fpath, low_memory=False)
        fc["pad_norm"] = fc["meta_padecimiento"].map(_norm)
        fc["meta_entidad"] = fc["meta_entidad"].fillna("Nacional")
        sub_prod = prod[prod["motor_key"] == motor_key]
        merged = fc.merge(
            sub_prod,
            left_on=["pad_norm", "meta_entidad", "meta_modo"],
            right_on=["pad_norm", "entidad", "sexo"],
            how="inner",
        )
        merged["ds"] = pd.to_datetime(merged["ds"])
        merged["corte"] = merged["pad_norm"].map(lambda p: cutoffs.get(p, (0, 0, pd.NaT))[2])
        merged = merged[merged["ds"] > merged["corte"]]  # solo cola futura no vista
        for _, r in merged.iterrows():
            iso = r["ds"].isocalendar()
            rows.append(
                {
                    "padecimiento": r["pad_disp"],
                    "entidad": r["entidad"],
                    "sexo": r["sexo"],
                    "motor": motor_key,
                    "fecha_corte": r["corte"].date().isoformat(),
                    "ds": r["ds"].date().isoformat(),
                    "iso_anio": int(iso.year),
                    "iso_semana": int(iso.week),
                    "yhat": round(float(r["yhat"]), 2),
                    "yhat_lower": round(float(r.get("yhat_lower", np.nan)), 2),
                    "yhat_upper": round(float(r.get("yhat_upper", np.nan)), 2),
                }
            )
    snap = pd.DataFrame(rows).sort_values(["padecimiento", "entidad", "sexo", "ds"])
    CONG_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"forecast_congelado_{hoy}.csv"
    snap.to_csv(CONG_DIR / fname, index=False)
    PTR.write_text(fname + "\n", encoding="utf-8")
    n_series = snap.groupby(["padecimiento", "entidad", "sexo"]).ngroups
    cortes_txt = ", ".join(f"{p}=W{c[1]}" for p, c in sorted(cutoffs.items()))
    logger.success(
        "Congelado {} | {} series, {} filas futuras | cortes: {} | puntero -> {}",
        fname,
        n_series,
        len(snap),
        cortes_txt,
        PTR.name,
    )
    logger.info("Aun no habra semanas que validar hasta que llegue un boletin posterior al corte.")
    return 0


# ---------------------------------------------------------------------------
# VALIDAR: desempeno out-of-sample
# ---------------------------------------------------------------------------


def _real_actual() -> pd.DataFrame:
    """Real semanal por (pad_norm, entidad, sexo, semana) del boletin vigente, 4 pads."""
    bol_path = conf["data"]["boletin"]
    bol = pd.read_csv(bol_path, usecols=["Padecimiento", "Anio", "Semana"])
    pads = sorted(bol["Padecimiento"].unique())
    anio = eval_year(bol_path, pads)
    wlim = int(bol.query("Anio == @anio")["Semana"].max())
    real = build_real(bol_path, pads, anio, wlim)
    real["pad_norm"] = real["padecimiento"].map(_norm)
    real = real.rename(columns={"Semana": "iso_semana"})
    real["iso_anio"] = anio
    return real[["pad_norm", "entidad", "sexo", "iso_anio", "iso_semana", "real"]]


def validar() -> int:
    if not PTR.exists():
        logger.error(
            "No hay congelado. Corre primero: python scripts/pronostico_congelado.py freeze"
        )
        return 1
    fname = PTR.read_text(encoding="utf-8").strip()
    snap = pd.read_csv(CONG_DIR / fname)
    snap["pad_norm"] = snap["padecimiento"].map(_norm)
    real = _real_actual()

    merged = snap.merge(
        real, on=["pad_norm", "entidad", "sexo", "iso_anio", "iso_semana"], how="inner"
    )
    # Solo semanas posteriores al corte (build_real ya da <= wlim; el congelado es > corte).
    if merged.empty:
        cortes = snap.groupby("padecimiento")["fecha_corte"].first().to_dict()
        logger.warning(
            "0 semanas nuevas que validar todavia. El congelado ({}) cubre ds > corte "
            "y el boletin aun no trae semanas posteriores. Cortes: {}. "
            "Vuelve a correr 'validar' tras el proximo boletin.",
            fname,
            cortes,
        )
        _escribe_html(pd.DataFrame(), fname, snap)
        return 0

    # Metricas por serie
    def _agg(g: pd.DataFrame) -> pd.Series:
        return pd.Series(
            {
                "n_sem_oos": len(g),
                "smape_oos": round(_smape(g["real"], g["yhat"]), 2),
                "mae_oos": round(float(np.mean(np.abs(g["yhat"] - g["real"]))), 1),
                "real_acum": int(g["real"].sum()),
                "pron_acum": int(round(g["yhat"].sum())),
            }
        )

    por_serie = (
        merged.groupby(["padecimiento", "entidad", "sexo", "motor"])
        .apply(_agg, include_groups=False)
        .reset_index()
    )
    por_serie.to_csv(CONG_DIR / "validacion_prospectiva.csv", index=False)
    _escribe_html(por_serie, fname, snap)
    nac = por_serie[(por_serie["entidad"] == "Nacional") & (por_serie["sexo"] == "general")]
    for _, r in nac.iterrows():
        logger.success(
            "{} Nacional: SMAPE OOS {}% sobre {} sem ({} motor)",
            r["padecimiento"],
            r["smape_oos"],
            int(r["n_sem_oos"]),
            r["motor"],
        )
    return 0


def _escribe_html(por_serie: pd.DataFrame, fname: str, snap: pd.DataFrame) -> None:
    out = REPORTS / "ProdDetails" / "validacion_prospectiva.html"
    gen = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    cortes = snap.groupby("padecimiento")["fecha_corte"].first().to_dict()
    cortes_txt = " · ".join(f"{p}: corte {c}" for p, c in cortes.items())
    css = (
        "body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#131C30;"
        "color:#E7ECF5;margin:0;padding:24px}h1{color:#2DD4BF}table{border-collapse:collapse;"
        "width:100%;margin-top:12px;font-size:13px}th,td{padding:6px 10px;border-bottom:"
        "1px solid #243150;text-align:right}th{color:#9FB0CE;text-align:right}td:first-child,"
        "th:first-child,td:nth-child(2),td:nth-child(3){text-align:left}tr:hover{background:#1C2740}"
        ".good{color:#2DD4BF}.warn{color:#F59E0B}.bad{color:#EF4444}.muted{color:#6E82A6}"
    )
    if por_serie.empty:
        body = (
            "<p class='muted'>Aun no hay semanas posteriores al corte para validar. "
            "El pronostico esta congelado y esperando el proximo boletin. "
            "Vuelve a correr <code>validar</code> tras la siguiente actualizacion semanal.</p>"
        )
    else:
        nac = por_serie[(por_serie["entidad"] == "Nacional") & (por_serie["sexo"] == "general")]
        cards = ""
        for _, r in nac.iterrows():
            sm = r["smape_oos"]
            cls = "good" if sm < 15 else "warn" if sm < 30 else "bad"
            cards += (
                f"<div style='display:inline-block;margin:8px 16px 8px 0;padding:12px 18px;"
                f"background:#1C2740;border-radius:10px'>"
                f"<div class='muted' style='font-size:12px'>{r['padecimiento']} Nacional "
                f"({r['motor']})</div>"
                f"<div class='{cls}' style='font-size:26px;font-weight:700'>{sm}%</div>"
                f"<div class='muted' style='font-size:11px'>SMAPE OOS · {int(r['n_sem_oos'])} sem</div>"
                f"</div>"
            )
        rows_html = ""
        for _, r in por_serie.sort_values(["padecimiento", "smape_oos"]).iterrows():
            sm = r["smape_oos"]
            cls = "good" if sm < 15 else "warn" if sm < 30 else "bad"
            rows_html += (
                f"<tr><td>{r['padecimiento']}</td><td>{r['entidad']}</td><td>{r['sexo']}</td>"
                f"<td>{r['motor']}</td><td>{int(r['n_sem_oos'])}</td>"
                f"<td class='{cls}'>{sm}</td><td>{r['mae_oos']}</td>"
                f"<td>{r['real_acum']}</td><td>{r['pron_acum']}</td></tr>"
            )
        body = (
            f"<h2>Resumen nacional (general)</h2>{cards}"
            "<h2>Detalle por serie</h2><table><tr><th>Padecimiento</th><th>Entidad</th>"
            "<th>Sexo</th><th>Motor</th><th>Sem OOS</th><th>SMAPE</th><th>MAE</th>"
            "<th>Real acum</th><th>Pron acum</th></tr>" + rows_html + "</table>"
        )
    html = (
        f"<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        f"<title>Validacion prospectiva OOS</title><style>{css}</style></head><body>"
        f"<h1>Validacion prospectiva out-of-sample</h1>"
        f"<p class='muted'>Congelado: <code>{fname}</code> · Generado: {gen}<br>{cortes_txt}</p>"
        f"<p class='muted'>Solo se puntuan semanas posteriores al corte (no vistas al congelar). "
        f"Mide desempeno honesto, a diferencia de <code>smape_real_2026</code> (in-sample).</p>"
        f"{body}</body></html>"
    )
    out.write_text(html, encoding="utf-8")
    logger.success("Reporte -> {}", out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("modo", choices=["freeze", "validar"], help="Accion a ejecutar")
    args = ap.parse_args()
    return freeze() if args.modo == "freeze" else validar()


if __name__ == "__main__":
    raise SystemExit(main())
