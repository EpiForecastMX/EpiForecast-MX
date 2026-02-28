# src/epiforecast/visualization/comparison_plots.py
"""Comparison visualization: Real vs Prophet vs DeepAR.

Professional styling with high-contrast line differentiation.
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from epiforecast.constants import VIZ_DPI_SCREEN
from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger
from epiforecast.visualization.forecast_plots import _normalizar_nombre

# ── Layout constants ─────────────────────────────────────────────────
_FIGSIZE = (16, 8)
_Y_MARGIN_BOTTOM = 0.85
_Y_MARGIN_TOP = 1.15

# ── Colors ───────────────────────────────────────────────────────────
_COLOR_REAL = "lightgray"
_COLOR_PROPHET = "#004d40"  # teal
_COLOR_DEEPAR = "#880e4f"  # vino / burgundy
_COLOR_DIVIDER = "#555555"

# ── Font sizes ───────────────────────────────────────────────────────
_FS_TITLE = 16
_FS_YLABEL = 12
_FS_LEGEND = 10
_FS_TIMESTAMP = 8.5

# ── Model display names ─────────────────────────────────────────────
_MODEL_DISPLAY = {"prophet": "Prophet", "deepar": "DeepAR"}

# ── Timezone ─────────────────────────────────────────────────────────
_TZ_CDMX = ZoneInfo("America/Mexico_City")


def generar_graficos_comparativos(config: dict | None = None) -> None:
    """Genera graficos con alta diferenciacion visual entre modelos."""
    _conf = config if config is not None else conf

    forecast_base = Path(_conf["paths"]["reports"]) / "forecasts"
    output_dir = forecast_base / "comparacion_modelos"
    directory_manager.asegurar_ruta(output_dir)

    path_prophet = forecast_base / "prophet" / "all_forecast_prophet.csv"
    path_deepar = forecast_base / "deepar" / "all_forecast_deepar.csv"

    if not path_prophet.exists() or not path_deepar.exists():
        logger.error("No se pueden comparar modelos: faltan archivos CSV.")
        return

    df_p = pd.read_csv(path_prophet, low_memory=False)
    df_d = pd.read_csv(path_deepar, low_memory=False)

    df_p["ds"] = pd.to_datetime(df_p["ds"])
    df_d["ds"] = pd.to_datetime(df_d["ds"])

    logger.info("Generando comparativas de alto contraste en {}...", output_dir)

    grupos = df_p.groupby(["meta_padecimiento", "meta_entidad", "meta_modo"])

    count = 0
    for (pad_, ent_, modo_), group_p in grupos:
        pad = str(pad_)
        ent = "" if ent_ is None or (isinstance(ent_, float) and np.isnan(ent_)) else str(ent_)
        modo = str(modo_)
        ent_val = ent

        mask_d = (
            (df_d["meta_padecimiento"] == pad)
            & (df_d["meta_entidad"].fillna("") == ent_val)
            & (df_d["meta_modo"] == modo)
        )
        group_d = df_d[mask_d]

        if group_d.empty:
            continue

        pad_norm = _normalizar_nombre(pad)
        ent_norm = _normalizar_nombre(ent_val if ent_val and ent_val.lower() != "nacional" else "")
        csv_name = f"Prophet_{pad_norm}_{ent_norm + '_' if ent_norm else ''}{modo}.csv"
        csv_path = Path(_conf["paths"]["models"]).parent / "prophet" / pad_norm / csv_name

        if not csv_path.exists():
            continue

        serie_real = pd.read_csv(csv_path)
        serie_real["ds"] = pd.to_datetime(serie_real["ds"])
        target_y = (
            serie_real["y_original"] if "y_original" in serie_real.columns else serie_real["y"]
        )

        fig, ax = _render_comparison(serie_real, target_y, group_p, group_d, pad, ent_val, modo)

        safe_ent = _normalizar_nombre(ent_val if ent_val else "Nacional")
        nombre = f"CMP_{pad}_{safe_ent}_{modo}.png"
        pad_dir = output_dir / pad_norm
        directory_manager.asegurar_ruta(pad_dir)
        plt.savefig(pad_dir / nombre, dpi=VIZ_DPI_SCREEN, bbox_inches="tight")
        plt.close(fig)
        count += 1

    logger.success("Se generaron {} comparativas de alto contraste en: {}", count, output_dir)


def _render_comparison(
    serie_real: pd.DataFrame,
    target_y: pd.Series,
    group_p: pd.DataFrame,
    group_d: pd.DataFrame,
    pad: str,
    ent_val: str,
    modo: str,
) -> tuple[plt.Figure, plt.Axes]:
    """Renderiza un grafico comparativo individual."""
    fig, ax = plt.subplots(figsize=_FIGSIZE)

    # 1. Historial Real
    ax.plot(
        serie_real["ds"],
        target_y,
        color=_COLOR_REAL,
        alpha=1.0,
        linewidth=3.0,
        label="Historial Real",
        zorder=1,
    )

    # 2. Prophet
    ax.plot(
        group_p["ds"],
        group_p["yhat"],
        color=_COLOR_PROPHET,
        linestyle="-.",
        linewidth=1.5,
        alpha=0.8,
        label="Prophet",
        zorder=3,
    )

    # 3. DeepAR
    ax.plot(
        group_d["ds"],
        group_d["yhat"],
        color=_COLOR_DEEPAR,
        linestyle="--",
        linewidth=1.0,
        alpha=0.8,
        label="DeepAR",
        zorder=4,
    )

    # Linea divisoria de inicio de pronostico
    fecha_max_real = serie_real["ds"].max()
    ax.axvline(fecha_max_real, color=_COLOR_DIVIDER, linestyle=":", alpha=0.4, zorder=2)

    # Limites dinamicos de Eje Y
    y_real_vals = np.asarray(target_y.dropna().values).ravel()
    y_p_vals = np.asarray(group_p["yhat"].dropna().values).ravel()
    y_d_vals = np.asarray(group_d["yhat"].dropna().values).ravel()
    all_y = np.concatenate([y_real_vals, y_p_vals, y_d_vals])
    if len(all_y) > 0:
        ax.set_ylim(bottom=np.min(all_y) * _Y_MARGIN_BOTTOM, top=np.max(all_y) * _Y_MARGIN_TOP)

    # Estetica
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(True, color="lightgrey", linestyle="--", linewidth=0.5, alpha=0.5)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Leyenda
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles, strict=False))
    ax.legend(
        by_label.values(),
        by_label.keys(),
        loc="upper left",
        frameon=True,
        shadow=True,
        fontsize=_FS_LEGEND,
    )

    # Titulos
    ent_display = ent_val if ent_val else "Nacional"
    ax.set_title(
        f"Diferenciación de Modelos: {pad} - {ent_display} ({modo})",
        fontsize=_FS_TITLE,
        fontweight="bold",
        pad=20,
    )
    ax.set_ylabel("Casos Semanales", fontsize=_FS_YLABEL)

    # Marca de tiempo CDMX
    ahora = datetime.now(_TZ_CDMX).strftime("%Y-%m-%d %H:%M")
    fig.text(
        0.5,
        0.02,
        f"Generado: {ahora} CDMX  |  EpiForecast-MX",
        ha="center",
        fontsize=_FS_TIMESTAMP,
        color="#808080",
        style="italic",
    )

    return fig, ax


# ── HTML Report ──────────────────────────────────────────────────────────


def generar_reporte_html(config: dict | None = None) -> Path | None:
    """Genera un reporte HTML comparativo Prophet vs DeepAR."""
    _conf = config if config is not None else conf
    models_dir = Path("models")
    output_dir = Path(_conf["paths"]["reports"]) / "forecasts" / "comparacion_modelos"
    output_html = output_dir / "comparacion_modelos.html"
    directory_manager.asegurar_ruta(output_dir)

    # Leer CSVs completos
    prophet_frames: list[pd.DataFrame] = []
    deepar_frames: list[pd.DataFrame] = []
    for csv in sorted((models_dir / "prophet").rglob("*_completo.csv")):
        prophet_frames.append(pd.read_csv(csv))
    for csv in sorted((models_dir / "deepar").rglob("*_completo.csv")):
        deepar_frames.append(pd.read_csv(csv))

    if not prophet_frames and not deepar_frames:
        logger.warning("No se encontraron CSVs completos para el reporte HTML.")
        return None

    df_p = pd.concat(prophet_frames, ignore_index=True) if prophet_frames else pd.DataFrame()
    df_d = pd.concat(deepar_frames, ignore_index=True) if deepar_frames else pd.DataFrame()

    for df in (df_p, df_d):
        if "Entidad" not in df.columns:
            df["Entidad"] = ""
        df["Entidad"] = df["Entidad"].fillna("")

    metrics = ["rmse", "mae", "smape", "mase"]
    merge_keys = ["padecimiento", "sexo", "nivel", "Entidad"]

    # Merge
    p_cols = (
        merge_keys
        + [c for c in metrics if c in df_p.columns]
        + [c for c in ("confianza", "promedio_semanal", "tiempo_total_seg") if c in df_p.columns]
    )
    d_cols = (
        merge_keys
        + [c for c in metrics if c in df_d.columns]
        + [c for c in ("confianza", "promedio_semanal", "tiempo_total_seg") if c in df_d.columns]
    )
    merged = df_p[[c for c in p_cols if c in df_p.columns]].merge(
        df_d[[c for c in d_cols if c in df_d.columns]],
        on=merge_keys,
        how="outer",
        suffixes=("_p", "_d"),
    )

    ahora = datetime.now(_TZ_CDMX).strftime("%Y-%m-%d %H:%M")
    padecimientos = sorted(merged["padecimiento"].dropna().unique())

    html_parts: list[str] = [_html_head(ahora)]

    # Resumen por padecimiento
    html_parts.append(_html_resumen(merged, padecimientos, metrics))

    # Detalle por padecimiento
    for pad in padecimientos:
        pad_data = merged[merged["padecimiento"] == pad].copy()
        pad_norm = _normalizar_nombre(pad)
        html_parts.append(_html_detalle_padecimiento(pad, pad_norm, pad_data, metrics))

    html_parts.append(_html_footer(ahora))

    output_html.write_text("\n".join(html_parts), encoding="utf-8")
    logger.success("Reporte HTML generado: {}", output_html)
    return output_html


def _fmt(val: object, decimals: int = 4) -> str:
    """Formatea un valor numerico o devuelve N/A."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    try:
        return f"{float(str(val)):.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def _ganador_class(p_val: object, d_val: object) -> tuple[str, str]:
    """Devuelve clases CSS para Prophet y DeepAR segun quien gana (menor es mejor)."""
    try:
        pv, dv = float(p_val), float(d_val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "", ""
    if np.isnan(pv) or np.isnan(dv):
        return "", ""
    if pv < dv:
        return "winner", ""
    if dv < pv:
        return "", "winner"
    return "", ""


def _html_head(ahora: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparación de Modelos - EpiForecast-MX</title>
<style>
  :root {{
    --teal: #004d40;
    --vino: #880e4f;
    --bg: #fafafa;
    --card-bg: #ffffff;
    --border: #e0e0e0;
    --text: #212121;
    --text-light: #757575;
    --green: #c8e6c9;
    --red: #ffcdd2;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.5;
  }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
  header {{
    background: linear-gradient(135deg, var(--teal), var(--vino));
    color: white; padding: 32px 24px; text-align: center; margin-bottom: 24px;
  }}
  header h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; }}
  header p {{ font-size: 14px; opacity: 0.85; }}
  .card {{
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 8px; padding: 20px; margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }}
  .card h2 {{
    font-size: 20px; margin-bottom: 16px; padding-bottom: 8px;
    border-bottom: 2px solid var(--border);
  }}
  .card h3 {{ font-size: 16px; margin: 16px 0 8px; color: var(--text-light); }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 12px;
  }}
  th, td {{ padding: 8px 10px; text-align: right; border-bottom: 1px solid var(--border); }}
  th {{ background: #f5f5f5; font-weight: 600; text-align: center; position: sticky; top: 0; }}
  td:first-child, th:first-child {{ text-align: left; }}
  tr:hover td {{ background: #f9f9f9; }}
  .prophet {{ color: var(--teal); font-weight: 600; }}
  .deepar {{ color: var(--vino); font-weight: 600; }}
  .winner {{ background: var(--green) !important; font-weight: 700; }}
  .insuf {{ background: var(--red); }}
  .thumbs {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px; margin-top: 12px;
  }}
  .thumbs a {{
    display: block; border: 1px solid var(--border); border-radius: 6px;
    overflow: hidden; transition: box-shadow 0.2s;
  }}
  .thumbs a:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
  .thumbs img {{ width: 100%; height: auto; display: block; }}
  .thumbs .caption {{
    padding: 6px 8px; font-size: 11px; color: var(--text-light);
    text-align: center; background: #fafafa;
  }}
  footer {{
    text-align: center; padding: 16px; color: var(--text-light);
    font-size: 12px; border-top: 1px solid var(--border); margin-top: 24px;
  }}
  .scroll-wrap {{ overflow-x: auto; }}
</style>
</head>
<body>
<header>
  <h1>Comparación de Modelos: Prophet vs DeepAR</h1>
  <p>EpiForecast-MX | IMSS | Generado: {ahora} CDMX</p>
</header>
<div class="container">
"""


def _html_resumen(
    merged: pd.DataFrame,
    padecimientos: list[str],
    metrics: list[str],
) -> str:
    rows: list[str] = []
    for pad in padecimientos:
        grp = merged[merged["padecimiento"] == pad]
        cells = [f"<td><strong>{pad}</strong></td>"]
        for m in metrics:
            pc, dc = f"{m}_p", f"{m}_d"
            p_val = grp[pc].mean(skipna=True) if pc in grp.columns else float("nan")
            d_val = grp[dc].mean(skipna=True) if dc in grp.columns else float("nan")
            p_cls, d_cls = _ganador_class(p_val, d_val)
            dec = 2 if m in ("smape", "mape") else 4
            cells.append(f'<td class="{p_cls}">{_fmt(p_val, dec)}</td>')
            cells.append(f'<td class="{d_cls}">{_fmt(d_val, dec)}</td>')
        rows.append(f"<tr>{''.join(cells)}</tr>")

    header_cells = "<th>Padecimiento</th>"
    for m in metrics:
        label = m.upper()
        header_cells += (
            f'<th class="prophet">{label} Prophet</th><th class="deepar">{label} DeepAR</th>'
        )

    return f"""<div class="card">
<h2>Resumen por Padecimiento</h2>
<p style="color:var(--text-light);font-size:13px;margin-bottom:12px">
Promedio de métricas. Menor es mejor. Celda verde = ganador.</p>
<div class="scroll-wrap">
<table>
<thead><tr>{header_cells}</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</div>
</div>
"""


def _html_detalle_padecimiento(
    pad: str,
    pad_norm: str,
    data: pd.DataFrame,
    metrics: list[str],
) -> str:
    # Separar nacionales y estatales
    nac = data[data["nivel"] == "nacional"].sort_values("sexo")
    est = data[data["nivel"] == "regional"].sort_values(["Entidad", "sexo"])

    parts: list[str] = [f'<div class="card"><h2>{pad}</h2>']

    # Tabla nacional
    if not nac.empty:
        parts.append("<h3>Nacional</h3>")
        parts.append(_html_metric_table(nac, metrics))

    # Tabla estatal
    if not est.empty:
        parts.append(f"<h3>Estatal ({len(est)} modelos)</h3>")
        parts.append(_html_metric_table(est, metrics))

    # Thumbnails
    parts.append("<h3>Gráficos Comparativos</h3>")
    parts.append('<div class="thumbs">')
    pngs = sorted((Path("reports/forecasts/comparacion_modelos") / pad_norm).glob("CMP_*.png"))
    for png in pngs:
        rel = f"{pad_norm}/{png.name}"
        caption = png.stem.replace("CMP_", "").replace("_", " ")
        parts.append(
            f'<a href="{rel}" target="_blank">'
            f'<img src="{rel}" alt="{caption}" loading="lazy">'
            f'<div class="caption">{caption}</div></a>'
        )
    parts.append("</div></div>")
    return "\n".join(parts)


def _html_metric_table(data: pd.DataFrame, metrics: list[str]) -> str:
    header = "<th>Entidad</th><th>Sexo</th>"
    for m in metrics:
        label = m.upper()
        header += f'<th class="prophet">{label} P</th><th class="deepar">{label} D</th>'
    header += "<th>Confianza</th>"

    rows: list[str] = []
    for _, row in data.iterrows():
        ent = row.get("Entidad", "") or "Nacional"
        sexo = str(row.get("sexo", "")).replace("incrementos_", "")
        conf_val = row.get("confianza_p", row.get("confianza_d", ""))
        conf_cls = "insuf" if conf_val == "insuficiente" else ""

        cells = [f"<td>{ent}</td>", f"<td>{sexo}</td>"]
        for m in metrics:
            pc, dc = f"{m}_p", f"{m}_d"
            p_val = row.get(pc)
            d_val = row.get(dc)
            p_cls, d_cls = _ganador_class(p_val, d_val)
            dec = 2 if m in ("smape", "mape") else 4
            cells.append(f'<td class="{p_cls}">{_fmt(p_val, dec)}</td>')
            cells.append(f'<td class="{d_cls}">{_fmt(d_val, dec)}</td>')
        cells.append(f'<td class="{conf_cls}">{conf_val}</td>')
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""<div class="scroll-wrap"><table>
<thead><tr>{header}</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table></div>"""


def _html_footer(ahora: str) -> str:
    return f"""</div>
<footer>
Generado: {ahora} CDMX | EpiForecast-MX v2.0 | IMSS 2026
</footer>
</body>
</html>"""
