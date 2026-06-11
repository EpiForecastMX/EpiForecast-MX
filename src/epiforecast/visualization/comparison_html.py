"""HTML template functions for the model comparison report.

Matches the Clinical Indigo design system (DM Serif Display, Source Sans 3, etc.).
Extracted from comparison_report.py for SRP compliance (max 300 lines).
"""

from pathlib import Path

import numpy as np
import pandas as pd

from epiforecast.visualization.comparison_css import CSS

_METRICS = ["rmse", "mae", "smape", "mase"]

_MODELS: dict[str, dict[str, str]] = {
    "prophet": {"label": "Prophet", "color": "#5B8DEF", "css": "prophet"},
    "deepar": {"label": "DeepAR", "color": "#BE185D", "css": "deepar"},
    "ensemble": {"label": "Ensemble", "color": "#FF6F00", "css": "ensemble"},
    "stacking": {"label": "Stacking", "color": "#1A237E", "css": "stacking"},
}

_REVEAL_JS = """\
<script>
document.querySelectorAll('.reveal').forEach(el=>{
const r=el.getBoundingClientRect();
if(r.top>window.innerHeight){el.classList.add('animate')}
else{el.classList.add('visible')}
});
const obs=new IntersectionObserver(es=>{
es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');obs.unobserve(e.target)}})
},{threshold:0,rootMargin:'200px 0px'});
document.querySelectorAll('.reveal.animate').forEach(el=>obs.observe(el));
</script>"""


def _overfitting_badge(smape_test: float | None, smape_train: float | None) -> str:
    """Ratio smape_test/smape_train > 2 = Alto, > 1.3 = Moderado, else OK."""
    if (
        smape_test is None
        or smape_train is None
        or (isinstance(smape_test, float) and np.isnan(smape_test))
        or (isinstance(smape_train, float) and np.isnan(smape_train))
        or smape_train == 0
    ):
        return '<span class="diag-badge badge-green">N/D</span>'
    ratio = smape_test / smape_train
    if ratio > 2:
        return f'<span class="diag-badge badge-red">Alto ({ratio:.1f}x)</span>'
    if ratio > 1.3:
        return f'<span class="diag-badge badge-yellow">Moderado ({ratio:.1f}x)</span>'
    return f'<span class="diag-badge badge-green">OK ({ratio:.1f}x)</span>'


def _leakage_badge(smape_train: float | None) -> str:
    """smape_train < 0.5 = Sospechoso (fit casi perfecto), else OK."""
    if smape_train is None or (isinstance(smape_train, float) and np.isnan(smape_train)):
        return '<span class="diag-badge badge-green">N/D</span>'
    if smape_train < 0.5:
        return f'<span class="diag-badge badge-red">Sospechoso ({smape_train:.2f}%)</span>'
    return f'<span class="diag-badge badge-green">OK ({smape_train:.1f}%)</span>'


def _get_prod_metrics(
    row: pd.Series,
    model_keys: list[str],
) -> tuple[float | None, float | None]:
    """Obtiene smape test y smape_train del modelo productivo de la fila."""
    prod = row.get("modelo_productivo", "")
    if not prod:
        return None, None
    smape_test = row.get(f"smape_{prod}")
    smape_train = row.get(f"smape_train_{prod}")
    try:
        st = float(smape_test) if smape_test is not None else None
    except (ValueError, TypeError):
        st = None
    try:
        str_val = float(smape_train) if smape_train is not None else None
    except (ValueError, TypeError):
        str_val = None
    return st, str_val


def fmt(val: object, decimals: int = 4) -> str:
    """Formatea un valor numerico o devuelve N/A."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    try:
        return f"{float(str(val)):.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def winner_among(row: pd.Series, metric: str, model_keys: list[str]) -> str:
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


# ---------------------------------------------------------------------------
# HTML sections
# ---------------------------------------------------------------------------

_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display'
    "&family=JetBrains+Mono:wght@400;600"
    '&family=Source+Sans+3:wght@300;400;600;700&display=swap" rel="stylesheet">'
)


def html_head(
    ahora: str,
    model_keys: list[str],
    *,
    n_series: int = 0,
    best_smape: float = 0.0,
    best_model: str = "",
    n_padecimientos: int = 0,
) -> str:
    """Genera <head>, hero con KPI cards y apertura del container."""
    n = len(model_keys)
    labels = " / ".join(_MODELS[mk]["label"] for mk in model_keys)

    kpi = (
        f'<div class="hero-kpi"><span class="value">{n}</span>'
        f'<span class="label">Modelos</span></div>'
        f'<div class="hero-kpi"><span class="value">{n_padecimientos or "\u2014"}</span>'
        f'<span class="label">Padecimientos</span></div>'
    )
    if n_series:
        kpi += (
            f'<div class="hero-kpi"><span class="value">{n_series:,}</span>'
            f'<span class="label">Series evaluadas</span></div>'
        )
    if best_smape > 0 and best_model:
        bl = _MODELS.get(best_model, {}).get("label", best_model)
        kpi += (
            f'<div class="hero-kpi"><span class="value">{best_smape:.1f}%</span>'
            f'<span class="label">Mejor SMAPE ({bl})</span></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparaci\u00f3n de Modelos \u2014 EpiForecast-MX</title>
{_FONTS_LINK}
<style>{CSS}</style>
<link rel="stylesheet" href="editorial.css?v=1">
</head>
<body>
<div class="hero">
  <h1>{labels}</h1>
  <p class="subtitle">Comparativa de {n} modelos | EpiForecast-MX | IMSS 2026 | {ahora} CDMX</p>
  <div class="hero-kpis">{kpi}</div>
</div>
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
        # Overfitting/Leakage promedio del modelo productivo
        smape_test_col = f"smape_{prod_winner}" if prod_winner else ""
        smape_train_col = f"smape_train_{prod_winner}" if prod_winner else ""
        avg_smape_test = (
            grp[smape_test_col].mean(skipna=True) if smape_test_col in grp.columns else None
        )
        avg_smape_train = (
            grp[smape_train_col].mean(skipna=True) if smape_train_col in grp.columns else None
        )
        cells.append(f"<td>{_overfitting_badge(avg_smape_test, avg_smape_train)}</td>")
        cells.append(f"<td>{_leakage_badge(avg_smape_train)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    hdr = "<th>Padecimiento</th>"
    for m in _METRICS:
        for mk in model_keys:
            hdr += f'<th class="c-{mk}">{m.upper()} {_MODELS[mk]["label"]}</th>'
    hdr += "<th>Productivo</th><th>Overfitting</th><th>Leakage</th>"

    return f"""<section class="reveal">
<h2 class="section-title">Resumen por Padecimiento</h2>
<p class="section-sub">Promedio de m\u00e9tricas. Menor es mejor. Celda verde = ganador.</p>
<div class="card">
<div class="table-wrapper">
<table>
<thead><tr>{hdr}</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</div>
</div>
</section>
"""


def html_detalle_padecimiento(
    pad: str,
    pad_norm: str,
    data: pd.DataFrame,
    model_keys: list[str],
) -> str:
    """Secci\u00f3n de detalle: tablas nacionales/estatales + miniaturas de gr\u00e1ficos."""
    nac = data[data["nivel"] == "nacional"].sort_values("sexo")
    est = data[data["nivel"] == "regional"].sort_values(["Entidad", "sexo"])

    parts: list[str] = [
        '<section class="reveal">',
        f'<h2 class="section-title">{pad}</h2>',
        '<p class="section-sub">Detalle de m\u00e9tricas a nivel nacional y estatal</p>',
    ]

    if not nac.empty:
        parts.append('<div class="card"><h2>Nacional</h2>')
        parts.append(_html_metric_table(nac, model_keys))
        parts.append("</div>")

    if not est.empty:
        parts.append(f'<div class="card"><h2>Estatal ({len(est)} series)</h2>')
        parts.append(_html_metric_table(est, model_keys))
        parts.append("</div>")

    pngs = sorted((Path("reports/forecasts/comparacion_modelos") / pad_norm).glob("CMP_*.png"))
    if pngs:
        parts.append('<div class="card"><h2>Gr\u00e1ficos Comparativos</h2>')
        parts.append('<div class="thumbs">')
        for png in pngs:
            rel = f"{pad_norm}/{png.name}"
            caption = png.stem.replace("CMP_", "").replace("_", " ")
            parts.append(
                f'<a href="{rel}" target="_blank">'
                f'<img src="{rel}" alt="{caption}" loading="lazy">'
                f'<div class="caption">{caption}</div></a>'
            )
        parts.append("</div></div>")

    parts.append("</section>")
    return "\n".join(parts)


def _html_metric_table(data: pd.DataFrame, model_keys: list[str]) -> str:
    """Genera tabla HTML de m\u00e9tricas por fila con colores de ganador."""
    hdr = "<th>Entidad</th><th>Sexo</th>"
    for m in _METRICS:
        for mk in model_keys:
            hdr += f'<th class="c-{mk}">{m.upper()} {_MODELS[mk]["label"][0]}</th>'
    hdr += "<th>Productivo</th><th>Overfitting</th><th>Leakage</th>"

    rows: list[str] = []
    for _, row in data.iterrows():
        ent = row.get("Entidad", "") or "Nacional"
        sexo = str(row.get("sexo", "")).replace("incrementos_", "")
        cells = [f"<td>{ent}</td>", f"<td>{sexo}</td>"]
        for m in _METRICS:
            dec = 2 if m in ("smape", "mape") else 4
            w_mk = winner_among(row, m, model_keys)
            for mk in model_keys:
                v = row.get(f"{m}_{mk}")
                cls = "winner" if mk == w_mk and v is not None else ""
                cells.append(f'<td class="{cls}">{fmt(v, dec)}</td>')
        prod = row.get("modelo_productivo", "")
        prod_label = _MODELS.get(prod, {}).get("label", prod) if prod else ""
        prod_css = f"prod-{prod}" if prod else ""
        cells.append(f'<td><span class="prod-badge {prod_css}">{prod_label}</span></td>')
        smape_t, smape_tr = _get_prod_metrics(row, model_keys)
        cells.append(f"<td>{_overfitting_badge(smape_t, smape_tr)}</td>")
        cells.append(f"<td>{_leakage_badge(smape_tr)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""<div class="table-wrapper"><table>
<thead><tr>{hdr}</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table></div>"""


def html_footer(ahora: str) -> str:
    """Genera el footer con animaciones de scroll."""
    return f"""</div>
<footer>
<p class="footer-title">EpiForecast-MX</p>
<p>Inteligencia Epidemiol\u00f3gica Multi-Modelo | IMSS 2026</p>
<p style="margin-top:.5rem">Generado: {ahora} CDMX</p>
</footer>
{_REVEAL_JS}
</body>
</html>"""
