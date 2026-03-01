"""HTML template functions for the model comparison report.

Extracted from comparison_report.py for SRP compliance (max 300 lines).
"""

from pathlib import Path

import numpy as np
import pandas as pd

_METRICS = ["rmse", "mae", "smape", "mase"]

_MODELS: dict[str, dict[str, str]] = {
    "prophet": {"label": "Prophet", "color": "#004d40", "css": "prophet"},
    "deepar": {"label": "DeepAR", "color": "#880e4f", "css": "deepar"},
    "ensemble": {"label": "Ensemble", "color": "#FF6F00", "css": "ensemble"},
    "stacking": {"label": "Stacking", "color": "#1A237E", "css": "stacking"},
}


def fmt(val: object, decimals: int = 4) -> str:
    """Formatea un valor numerico o devuelve N/A."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    try:
        return f"{float(str(val)):.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def winner_among(row: pd.Series, metric: str, model_keys: list[str]) -> str:  # type: ignore[type-arg]
    """Devuelve el model_key con el menor valor para la metrica dada."""
    best_key = ""
    best_val = float("inf")
    for mk in model_keys:
        col = f"{metric}_{mk}"
        v = row.get(col)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            try:
                fv = float(v)
                if fv < best_val:
                    best_val = fv
                    best_key = mk
            except (ValueError, TypeError):
                pass
    return best_key


def html_head(ahora: str, model_keys: list[str]) -> str:
    """Genera el <head> y header del reporte HTML."""
    model_css = "\n".join(
        f"  .{_MODELS[mk]['css']} {{ color: {_MODELS[mk]['color']}; font-weight: 600; }}"
        for mk in model_keys
    )
    n_models = len(model_keys)
    labels = ", ".join(_MODELS[mk]["label"] for mk in model_keys)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparaci\u00f3n de Modelos - EpiForecast-MX</title>
<style>
  :root {{
    --teal: #004d40; --vino: #880e4f; --orange: #FF6F00; --indigo: #1A237E;
    --bg: #fafafa; --card-bg: #ffffff; --border: #e0e0e0;
    --text: #212121; --text-light: #757575; --green: #c8e6c9; --red: #ffcdd2;
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
  .card h2 {{ font-size: 20px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid var(--border); }}
  .card h3 {{ font-size: 16px; margin: 16px 0 8px; color: var(--text-light); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 12px; }}
  th, td {{ padding: 8px 10px; text-align: right; border-bottom: 1px solid var(--border); }}
  th {{ background: #f5f5f5; font-weight: 600; text-align: center; position: sticky; top: 0; }}
  td:first-child, th:first-child {{ text-align: left; }}
  tr:hover td {{ background: #f9f9f9; }}
{model_css}
  .winner {{ background: var(--green) !important; font-weight: 700; }}
  .insuf {{ background: var(--red); }}
  .prod-badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 700; color: white; }}
  .prod-prophet {{ background: var(--teal); }}
  .prod-deepar {{ background: var(--vino); }}
  .prod-ensemble {{ background: var(--orange); }}
  .prod-stacking {{ background: var(--indigo); }}
  .thumbs {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; margin-top: 12px; }}
  .thumbs a {{ display: block; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; transition: box-shadow 0.2s; }}
  .thumbs a:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
  .thumbs img {{ width: 100%; height: auto; display: block; }}
  .thumbs .caption {{ padding: 6px 8px; font-size: 11px; color: var(--text-light); text-align: center; background: #fafafa; }}
  footer {{ text-align: center; padding: 16px; color: var(--text-light); font-size: 12px; border-top: 1px solid var(--border); margin-top: 24px; }}
  .scroll-wrap {{ overflow-x: auto; }}
</style>
</head>
<body>
<header>
  <h1>Comparaci\u00f3n de Modelos: {labels}</h1>
  <p>EpiForecast-MX | IMSS | {n_models} modelos | Generado: {ahora} CDMX</p>
</header>
<div class="container">
"""


def html_resumen(
    merged: pd.DataFrame,
    padecimientos: list[str],
    model_keys: list[str],
) -> str:
    """Tabla resumen con promedios por padecimiento y modelo productivo."""
    rows: list[str] = []
    for pad in padecimientos:
        grp = merged[merged["padecimiento"] == pad]
        cells = [f"<td><strong>{pad}</strong></td>"]
        for m in _METRICS:
            dec = 2 if m in ("smape", "mape") else 4
            best_val = float("inf")
            best_mk = ""
            vals: dict[str, float] = {}
            for mk in model_keys:
                col = f"{m}_{mk}"
                v = grp[col].mean(skipna=True) if col in grp.columns else float("nan")
                vals[mk] = v
                if not np.isnan(v) and v < best_val:
                    best_val = v
                    best_mk = mk
            for mk in model_keys:
                cls = "winner" if mk == best_mk and not np.isnan(vals[mk]) else ""
                cells.append(f'<td class="{cls}">{fmt(vals[mk], dec)}</td>')
        prod_counts = grp["modelo_productivo"].value_counts()
        prod_winner = prod_counts.index[0] if not prod_counts.empty else ""
        prod_label = _MODELS.get(prod_winner, {}).get("label", prod_winner)
        prod_css = f"prod-{prod_winner}" if prod_winner else ""
        cells.append(f'<td><span class="prod-badge {prod_css}">{prod_label}</span></td>')
        rows.append(f"<tr>{''.join(cells)}</tr>")

    header_cells = "<th>Padecimiento</th>"
    for m in _METRICS:
        label = m.upper()
        for mk in model_keys:
            css = _MODELS[mk]["css"]
            short = _MODELS[mk]["label"]
            header_cells += f'<th class="{css}">{label} {short}</th>'
    header_cells += "<th>Productivo</th>"

    return f"""<div class="card">
<h2>Resumen por Padecimiento</h2>
<p style="color:var(--text-light);font-size:13px;margin-bottom:12px">
Promedio de m\u00e9tricas. Menor es mejor. Celda verde = ganador.
Modelo productivo = mayor\u00eda de series ganadas por SMAPE.</p>
<div class="scroll-wrap">
<table>
<thead><tr>{header_cells}</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</div>
</div>
"""


def html_detalle_padecimiento(
    pad: str,
    pad_norm: str,
    data: pd.DataFrame,
    model_keys: list[str],
) -> str:
    """Seccion de detalle por padecimiento: tablas nacionales/estatales + thumbnails."""
    nac = data[data["nivel"] == "nacional"].sort_values("sexo")
    est = data[data["nivel"] == "regional"].sort_values(["Entidad", "sexo"])

    parts: list[str] = [f'<div class="card"><h2>{pad}</h2>']

    if not nac.empty:
        parts.append("<h3>Nacional</h3>")
        parts.append(_html_metric_table(nac, model_keys))

    if not est.empty:
        parts.append(f"<h3>Estatal ({len(est)} modelos)</h3>")
        parts.append(_html_metric_table(est, model_keys))

    parts.append("<h3>Gr\u00e1ficos Comparativos</h3>")
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


def _html_metric_table(data: pd.DataFrame, model_keys: list[str]) -> str:
    """Genera tabla HTML de metricas por fila con colores de ganador."""
    header = "<th>Entidad</th><th>Sexo</th>"
    for m in _METRICS:
        label = m.upper()
        for mk in model_keys:
            css = _MODELS[mk]["css"]
            short = _MODELS[mk]["label"][0]
            header += f'<th class="{css}">{label} {short}</th>'
    header += "<th>Productivo</th>"

    rows: list[str] = []
    for _, row in data.iterrows():
        ent = row.get("Entidad", "") or "Nacional"
        sexo = str(row.get("sexo", "")).replace("incrementos_", "")

        cells = [f"<td>{ent}</td>", f"<td>{sexo}</td>"]
        for m in _METRICS:
            dec = 2 if m in ("smape", "mape") else 4
            winner_mk = winner_among(row, m, model_keys)
            for mk in model_keys:
                col = f"{m}_{mk}"
                v = row.get(col)
                cls = "winner" if mk == winner_mk and v is not None else ""
                cells.append(f'<td class="{cls}">{fmt(v, dec)}</td>')

        prod = row.get("modelo_productivo", "")
        prod_label = _MODELS.get(prod, {}).get("label", prod) if prod else ""
        prod_css = f"prod-{prod}" if prod else ""
        cells.append(f'<td><span class="prod-badge {prod_css}">{prod_label}</span></td>')
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""<div class="scroll-wrap"><table>
<thead><tr>{header}</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table></div>"""


def html_footer(ahora: str) -> str:
    """Genera el footer del reporte HTML."""
    return f"""</div>
<footer>
Generado: {ahora} CDMX | EpiForecast-MX v2.0 | IMSS 2026
</footer>
</body>
</html>"""
