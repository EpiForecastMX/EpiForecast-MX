"""Genera el reporte HTML de seguimiento posterior al corte: Realidad vs Pronostico.

Desde la ronda W37 (version 2 de los campos de validacion) la pagina NO calcula sus propios
pares: los lee de ``seguimiento_post_corte.csv`` (``genera_seguimiento_post_corte.py``), que
empareja el pronostico guardado desde el corte con lo observado la MISMA semana del boletin,
con la asignacion congelada y la regla de observados de la galeria. Presenta cada semana
evaluada posterior al corte (W38 a horizonte 1, W39 a horizonte 2, ...) como seguimiento
diagnostico, con el numero de semanas evaluadas visible; no es una evaluacion independiente.

Antes comparaba la ultima semana con su propia regla de sexo (diferencia de acumulados recortada
a cero) y escribia en la tabla la realidad de la W39 junto al pronostico de la W38.

Salida: reports/ProdDetails/validacion_semanal.html y la COPIA de la tabla de produccion con
``pron_sem_previa``/``realidad_sem_previa`` de la misma semana (la ultima evaluada).
"""

from __future__ import annotations

import argparse
from datetime import datetime
import math
from pathlib import Path
import shutil
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from epiforecast.utils.semana_epi import fin_semana_boletin, inicio_semana_boletin

# ---------------------------------------------------------------------------
# Rutas y constantes
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
PROD_EXCEL = ROOT / "reports" / "ProdDetails" / "tabla_333_modelos_produccion.xlsx"
OUTPUT = ROOT / "reports" / "ProdDetails" / "validacion_semanal.html"

PADECIMIENTOS = ["Alzheimer", "Parkinson", "Depresion"]
PAD_DISPLAY: dict[str, str] = {
    "Alzheimer": "Alzheimer (G30)",
    "Parkinson": "Parkinson (G20)",
    "Depresion": "Depresion (F32)",
}
SEXO_MODES = ["general", "hombres", "mujeres"]
SEXO_DISPLAY: dict[str, str] = {
    "general": "General",
    "hombres": "Hombres",
    "mujeres": "Mujeres",
}

ENTITY_ORDER = [
    "Nacional",
    "Aguascalientes",
    "Baja California",
    "Baja California Sur",
    "Campeche",
    "Chiapas",
    "Chihuahua",
    "Ciudad de Mexico",
    "Coahuila",
    "Colima",
    "Durango",
    "Guanajuato",
    "Guerrero",
    "Hidalgo",
    "Jalisco",
    "Michoacan",
    "Mexico",
    "Morelos",
    "Nayarit",
    "Nuevo Leon",
    "Oaxaca",
    "Puebla",
    "Queretaro",
    "Quintana Roo",
    "San Luis Potosi",
    "Sinaloa",
    "Sonora",
    "Tabasco",
    "Tamaulipas",
    "Tlaxcala",
    "Veracruz",
    "Yucatan",
    "Zacatecas",
]

REGION_STATES: dict[str, list[str]] = {
    "Region Metropolitana alta": [
        "Ciudad de Mexico",
        "Mexico",
        "Nuevo Leon",
        "Jalisco",
    ],
    "Region Urbana media": [
        "Aguascalientes",
        "Baja California",
        "Baja California Sur",
        "Chihuahua",
        "Coahuila",
        "Colima",
        "Durango",
        "Guanajuato",
        "Morelos",
        "Queretaro",
        "San Luis Potosi",
        "Sinaloa",
        "Sonora",
        "Tamaulipas",
        "Zacatecas",
    ],
    "Region Rural / dispersa": [
        "Guerrero",
        "Hidalgo",
        "Michoacan",
        "Nayarit",
        "Puebla",
        "Tlaxcala",
        "Veracruz",
    ],
    "Region Sur-Sureste vulnerable": [
        "Campeche",
        "Chiapas",
        "Oaxaca",
        "Tabasco",
        "Yucatan",
        "Quintana Roo",
    ],
}
REGION_ORDER = list(REGION_STATES.keys())
REGION_DISPLAY: dict[str, str] = {
    "Region Metropolitana alta": "Metropolitana alta",
    "Region Urbana media": "Urbana media",
    "Region Rural / dispersa": "Rural / dispersa",
    "Region Sur-Sureste vulnerable": "Sur-Sureste vulnerable",
}
# Reverse lookup: state -> region
_STATE_TO_REGION: dict[str, str] = {}
for _reg, _states in REGION_STATES.items():
    for _st in _states:
        _STATE_TO_REGION[_st] = _reg

TZ_MX = ZoneInfo("America/Mexico_City")

# ---------------------------------------------------------------------------
# Normalizacion
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    """Quita acentos para hacer join entre fuentes."""
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _norm_prod_entidad(s: str) -> str:
    """Normaliza entidad del Excel de produccion (region_ -> Region )."""
    if s.startswith("region_"):
        s = "Region " + s[len("region_") :]
    return _normalize(s)


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------


def _epiweek_date_range(anio: int, semana: int) -> str:
    """Rango de fechas legible de la semana del boletin: de domingo a sabado (calendario v2).

    Antes se usaban el lunes y el domingo de la semana ISO con el mismo numero, que en 2026 caen
    casi una semana antes que la semana epidemiologica publicada (W39 ISO = 21-27 sep; boletin
    W39 = 27 sep - 3 oct).
    """
    monday = inicio_semana_boletin(anio, semana)  # domingo de inicio
    sunday = fin_semana_boletin(anio, semana)  # sabado de cierre
    meses = [
        "",
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    if monday.month == sunday.month:
        return f"{monday.day}-{sunday.day} {meses[monday.month]} {monday.year}"
    return f"{monday.day} {meses[monday.month]} - {sunday.day} {meses[sunday.month]} {sunday.year}"


def _registros(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(k): v for k, v in fila.items()} for fila in df.to_dict("records")]


def _comparacion(seg: pd.DataFrame) -> pd.DataFrame:
    """Filas de la pagina (neuro) a partir de los pares del seguimiento de UNA semana objetivo."""
    filas: list[dict[str, Any]] = []
    registros = _registros(seg[seg["cohorte"] == "neuro"])
    for r in registros:
        real = None if pd.isna(r["real"]) else int(r["real"])
        pron = None if pd.isna(r["pronostico"]) else int(r["pronostico"])
        error_pct, veredicto = _verdict(real, pron)
        filas.append(
            {
                "entidad_norm": _norm_prod_entidad(str(r["entidad"])),
                "pad_norm": _normalize(str(r["padecimiento"])),
                "sexo": str(r["sexo"]),
                "real": real,
                "pronostico": pron,
                "error_pct": error_pct,
                "veredicto": veredicto if r["estado"] == "par" else "N/A",
                "motor": str(r["motor"]).lower(),
                "nivel": str(r["nivel"]),
            }
        )
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# Calculos
# ---------------------------------------------------------------------------


def _verdict(real_val: Any, yhat: Any) -> tuple[float | None, str]:
    """Calcula SMAPE y veredicto.

    SMAPE = |F - A| / ((|A| + |F|) / 2) * 100
    Rango: 0-200%. Simetrico, no explota con incidencia baja.
    """
    if real_val is None or yhat is None:
        return None, "N/A"
    if isinstance(real_val, float) and math.isnan(real_val):
        return None, "N/A"
    if isinstance(yhat, float) and math.isnan(yhat):
        return None, "N/A"
    real_val = round(real_val)
    yhat = round(yhat)
    denom = (abs(real_val) + abs(yhat)) / 2
    if denom == 0:
        # Ambos cero: pronostico perfecto
        return 0.0, "EXCELENTE"
    if real_val == 0 and yhat <= 2:
        # Cero real con pronostico despreciable
        return None, "N/A"
    smape = abs(yhat - real_val) / denom * 100
    if smape <= 10:
        return smape, "EXCELENTE"
    if smape <= 25:
        return smape, "BUENO"
    if smape <= 50:
        return smape, "REGULAR"
    return smape, "FALLO"


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display'
    "&family=JetBrains+Mono:wght@400;600"
    "&family=Source+Sans+3:wght@300;400;600;700"
    '&display=swap" rel="stylesheet">'
)

VEREDICTO_COLORS: dict[str, str] = {
    "EXCELENTE": "#2DD4BF",
    "BUENO": "#0D9488",
    "REGULAR": "#F59E0B",
    "FALLO": "#EF4444",
    "N/A": "#97999B",
}
VEREDICTO_TEXT_COLOR: dict[str, str] = {
    "EXCELENTE": "#0B0F1A",
    "BUENO": "#fff",
    "REGULAR": "#0B0F1A",
    "FALLO": "#fff",
    "N/A": "#fff",
}
MOTOR_COLORS: dict[str, str] = {
    "prophet": "#5B8DEF",
    "deepar": "#BE185D",
    "ensemble": "#FF6F00",
    "stacking": "#1A237E",
}


def _badge(text: str, bg: str, fg: str = "#fff") -> str:
    return (
        f'<span style="display:inline-flex;align-items:center;padding:.25rem .85rem;'
        f"border-radius:100px;font-size:.78rem;font-weight:700;"
        f'color:{fg};background:{bg}">{text}</span>'
    )


def _veredicto_badge(v: str) -> str:
    return _badge(v, VEREDICTO_COLORS.get(v, "#97999B"), VEREDICTO_TEXT_COLOR.get(v, "#fff"))


def _motor_badge(m: str) -> str:
    return _badge(m.capitalize(), MOTOR_COLORS.get(m, "#97999B"))


def _semaforo_dot(v: str) -> str:
    color = VEREDICTO_COLORS.get(v, "#97999B")
    return (
        f'<span title="{v}" style="display:inline-block;width:22px;height:22px;'
        f"border-radius:50%;background:{color};border:2px solid #fff;"
        f'box-shadow:0 1px 4px rgba(0,0,0,.15)"></span>'
    )


def _fmt_error(val: float | None) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "—"
    return f"{val:.1f}%"


def _fmt_int(val: Any) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "N/A"
    return f"{int(val):,}"


def _err_class(error_pct: float | None) -> str:
    if error_pct is None or (isinstance(error_pct, float) and math.isnan(error_pct)):
        return ""
    if error_pct <= 25:
        return "err-good"
    return "err-bad"


def _fmt_mase(val: Any) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "N/A"
    return f"{val:.2f}"


def _mase_class(val: Any) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ""
    if val < 1.0:
        return "mase-good"
    return "mase-warn"


MASE_VERDICT_COLORS: dict[str, str] = {
    "EXCELENTE": "#2DD4BF",
    "BUENO": "#0D9488",
    "REGULAR": "#F59E0B",
    "FALLO": "#EF4444",
    "—": "#97999B",
}
MASE_VERDICT_TEXT: dict[str, str] = {
    "EXCELENTE": "#0B0F1A",
    "BUENO": "#fff",
    "REGULAR": "#0B0F1A",
    "FALLO": "#fff",
    "—": "#fff",
}


def _mase_verdict(val: Any) -> str:
    """Veredicto basado en MASE: < 1 supera al naive."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "—"
    if val < 0.5:
        return "EXCELENTE"
    if val < 1.0:
        return "BUENO"
    if val < 1.5:
        return "REGULAR"
    return "FALLO"


def _mase_dot(val: Any) -> str:
    """Dot de color segun veredicto MASE, sin etiqueta."""
    v = _mase_verdict(val)
    color = MASE_VERDICT_COLORS.get(v, "#97999B")
    return (
        f'<span title="MASE {v}" style="display:inline-block;width:10px;height:10px;'
        f"border-radius:50%;background:{color};vertical-align:middle;"
        f'margin-left:.4rem"></span>'
    )


# ---------------------------------------------------------------------------
# Tabla reutilizable con desglose por sexo
# ---------------------------------------------------------------------------


def _build_sexo_table(data: pd.DataFrame) -> str:
    """Tabla con filas agrupadas: padecimiento (rowspan=3) x sexo."""
    rows_html = ""
    for pad in PADECIMIENTOS:
        pad_rows = data[data["pad_norm"] == pad]
        if pad_rows.empty:
            continue
        n_sexos = sum(1 for s in SEXO_MODES if not pad_rows[pad_rows["sexo"] == s].empty)
        first = True
        for sexo in SEXO_MODES:
            sr = pad_rows[pad_rows["sexo"] == sexo]
            if sr.empty:
                continue
            r = sr.iloc[0]
            is_last = sexo == SEXO_MODES[-1]
            row_cls = ' class="row-group-last"' if is_last else ""
            pad_cell = ""
            if first:
                pad_cell = (
                    f'<td rowspan="{n_sexos}" style="font-family:var(--font-body);'
                    f'font-weight:600;vertical-align:middle">'
                    f"{PAD_DISPLAY.get(pad, pad)}</td>"
                )
                first = False
            rows_html += (
                f"<tr{row_cls}>"
                f"  {pad_cell}"
                f'  <td style="font-family:var(--font-body)">{SEXO_DISPLAY.get(sexo, sexo)}</td>'
                f"  <td>{_fmt_int(r['real'])}</td>"
                f"  <td>{_fmt_int(r['pronostico'])}</td>"
                f'  <td class="{_err_class(r["error_pct"])}">'
                f"{_fmt_error(r['error_pct'])}</td>"
                f"  <td>{_motor_badge(r['motor'])}</td>"
                f"  <td>{_veredicto_badge(r['veredicto'])}</td>"
                f"</tr>\n"
            )

    return f"""<div class="table-wrapper">
  <table>
    <thead><tr>
      <th>Padecimiento</th><th>Sexo</th><th>Real</th><th>Pronostico</th>
      <th>SMAPE</th><th>Motor</th><th>Veredicto</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>"""


# ---------------------------------------------------------------------------
# Secciones HTML
# ---------------------------------------------------------------------------


def _section_dashboard(comp: pd.DataFrame, anio: int, semana: int, horizonte: int) -> str:
    """Panel premium con gauges SVG animados: SMAPE + MASE por padecimiento."""
    nac_gen = comp[(comp["nivel"] == "nacional") & (comp["sexo"] == "general")]

    # Sin MASE: el de la tabla de produccion es el error de la ventana de seleccion W28-W37
    # (diagnostico de seleccion, no evaluacion independiente) y no se publica.

    date_range = _epiweek_date_range(anio, semana)
    panels = ""
    for pad in PADECIMIENTOS:
        row = nac_gen[nac_gen["pad_norm"] == pad]
        if row.empty:
            continue
        r = row.iloc[0]
        smape = r["error_pct"] if pd.notna(r["error_pct"]) else 0.0
        real = int(r["real"]) if pd.notna(r["real"]) else 0
        pron = int(r["pronostico"]) if pd.notna(r["pronostico"]) else 0
        motor = r["motor"]
        veredicto = r["veredicto"]
        panels += _dashboard_panel(pad, smape, real, pron, motor, veredicto, float("nan"))

    return f"""
<section class="reveal animate">
  <div class="dashboard">
    <div class="dashboard-header">
      <h2>Seguimiento nacional: semana {semana} de {anio}</h2>
      <p>{date_range} | Horizonte {horizonte} semana{"s" if horizonte != 1 else ""} desde el corte | Modo general</p>
    </div>
    <div class="dashboard-grid">{panels}</div>
  </div>
</section>"""


# Gauge constants
_GAUGE_SIZE = 160
_GAUGE_R = 65
_GAUGE_CIRC = 2 * math.pi * _GAUGE_R  # 408.41


def _dashboard_panel(
    pad: str,
    smape: float,
    real: int,
    pron: int,
    motor: str,
    veredicto: str,
    mase: float,
) -> str:
    """Panel individual de un padecimiento con gauge SVG + MASE bar."""
    cx = cy = _GAUGE_SIZE / 2
    precision = max(0.0, min(100.0, 100.0 - smape))
    target_offset = _GAUGE_CIRC * (1 - precision / 100)
    gauge_color = VEREDICTO_COLORS.get(veredicto, "#97999B")

    # MASE bar
    mase_html = ""
    if not math.isnan(mase):
        mase_pct = min(mase / 2 * 100, 100)
        if mase < 0.8:
            mase_color, mase_lbl = "#2DD4BF", "Excelente"
        elif mase < 1.0:
            mase_color, mase_lbl = "#0D9488", "Superior al naive"
        elif mase < 1.3:
            mase_color, mase_lbl = "#F59E0B", "Comparable al naive"
        else:
            mase_color, mase_lbl = "#EF4444", "Inferior al naive"
        mase_html = f"""
      <div class="mase-box">
        <div class="mase-head">
          <span class="mase-title">MASE</span>
          <span class="mase-val" style="color:{mase_color}">{mase:.2f}</span>
        </div>
        <div class="mase-track">
          <div class="mase-fill" style="--mw:{mase_pct}%;background:{mase_color}"></div>
          <div class="mase-ref"></div>
        </div>
        <div class="mase-ticks">
          <span>0</span>
          <span style="position:absolute;left:50%;transform:translateX(-50%)">1.0</span>
          <span>2.0</span>
        </div>
        <div class="mase-lbl" style="color:{mase_color}">{mase_lbl}</div>
      </div>"""

    # Flecha SVG entre Real y Pronostico
    arrow = (
        '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" '
        'stroke="rgba(232,213,181,.35)" stroke-width="2" stroke-linecap="round">'
        '<path d="M5 12h14M13 6l6 6-6 6"/></svg>'
    )

    return f"""
    <div class="dash-panel">
      <h3>{PAD_DISPLAY.get(pad, pad)}</h3>
      <div class="gauge-wrap">
        <svg width="{_GAUGE_SIZE}" height="{_GAUGE_SIZE}"
             viewBox="0 0 {_GAUGE_SIZE} {_GAUGE_SIZE}">
          <defs>
            <filter id="glow-{pad}" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur"/>
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>
          <circle cx="{cx}" cy="{cy}" r="{_GAUGE_R}"
            fill="none" stroke="rgba(255,255,255,.07)" stroke-width="11"/>
          <circle cx="{cx}" cy="{cy}" r="{_GAUGE_R}"
            fill="none" stroke="{gauge_color}" stroke-width="11"
            stroke-dasharray="{_GAUGE_CIRC:.2f}"
            stroke-linecap="round"
            transform="rotate(-90 {cx} {cy})"
            filter="url(#glow-{pad})"
            class="gauge-arc"
            style="--to:{target_offset:.2f}"/>
          <text x="{cx}" y="{cy - 10}" text-anchor="middle"
            fill="#fff" style="font-family:var(--font-display);font-size:28px">
            {smape:.1f}%</text>
          <text x="{cx}" y="{cy + 14}" text-anchor="middle"
            fill="rgba(232,213,181,.55)" style="font-family:var(--font-body);font-size:12px">
            SMAPE</text>
        </svg>
      </div>
      <div class="dash-nums">
        <div class="dash-n">
          <span class="dash-v" data-target="{real}">{real:,}</span>
          <span class="dash-l">Real</span>
        </div>
        {arrow}
        <div class="dash-n">
          <span class="dash-v" data-target="{pron}">{pron:,}</span>
          <span class="dash-l">Pronostico</span>
        </div>
      </div>
      {mase_html}
      <div class="dash-badges">
        {_motor_badge(motor)} {_veredicto_badge(veredicto)}
      </div>
    </div>"""


def _section_nacional(comp: pd.DataFrame) -> str:
    nac = comp[comp["nivel"] == "nacional"]
    table = _build_sexo_table(nac)
    return f"""
<section class="reveal animate">
  <h2 class="section-title">Resumen Nacional</h2>
  <p class="section-sub">Comparacion agregada por padecimiento y sexo</p>
  <div class="card card-gold">{table}</div>
</section>"""


def _section_regional(comp: pd.DataFrame) -> str:
    reg = comp[comp["nivel"] == "regional"]
    parts = [
        """
<section class="reveal animate">
  <h2 class="section-title">Seguimiento regional</h2>
  <p class="section-sub">4 regiones sociales con desglose por sexo</p>"""
    ]
    for region in REGION_ORDER:
        rd = reg[reg["entidad_norm"] == region]
        if rd.empty:
            continue
        display = REGION_DISPLAY.get(region, region)
        n_states = len(REGION_STATES.get(region, []))
        table = _build_sexo_table(rd)
        parts.append(
            f"""
  <div class="card reveal animate">
    <h2>{display} <span style="font-size:.85rem;color:var(--cool-gray);
      font-family:var(--font-body);font-weight:400">({n_states} entidades)</span></h2>
    {table}
  </div>"""
        )
    parts.append("</section>")
    return "".join(parts)


def _section_detalle(comp: pd.DataFrame) -> str:
    """Detalle por padecimiento: solo modo general, 33 geos."""
    general = comp[(comp["nivel"] == "estatal") & (comp["sexo"] == "general")]
    parts = [
        """
<section class="reveal animate">
  <h2 class="section-title">Detalle por Entidad Federativa</h2>
  <p class="section-sub">Modo general &mdash; 32 entidades + Nacional</p>"""
    ]

    # Agregar Nacional general al inicio
    nac_general = comp[(comp["nivel"] == "nacional") & (comp["sexo"] == "general")]
    combined = pd.concat([nac_general, general], ignore_index=True)

    for pad in PADECIMIENTOS:
        pad_data = combined[combined["pad_norm"] == pad].copy()
        if pad_data.empty:
            continue

        order_map = {e: i for i, e in enumerate(ENTITY_ORDER)}
        pad_data = pad_data.assign(
            _order=pad_data["entidad_norm"].map(lambda x, om=order_map: om.get(x, 999))
        )
        pad_data = pad_data.sort_values("_order")

        rows_html = ""
        total_real = 0.0
        total_prod = 0.0
        for _, r in pad_data.iterrows():
            is_nac = r["entidad_norm"] == "Nacional"
            row_class = ' class="row-nacional"' if is_nac else ""
            real_v = r["real"] if r["real"] is not None and not _isnan(r["real"]) else 0
            prod_v = (
                r["pronostico"]
                if r["pronostico"] is not None and not _isnan(r["pronostico"])
                else 0
            )
            if not is_nac:
                total_real += real_v
                total_prod += prod_v
            rows_html += (
                f"<tr{row_class}>"
                f'  <td style="font-family:var(--font-body)">{r["entidad_norm"]}</td>'
                f"  <td>{_fmt_int(r['real'])}</td>"
                f"  <td>{_fmt_int(r['pronostico'])}</td>"
                f'  <td class="{_err_class(r["error_pct"])}">'
                f"{_fmt_error(r['error_pct'])}</td>"
                f"  <td>{_motor_badge(r['motor'])}</td>"
                f"  <td>{_veredicto_badge(r['veredicto'])}</td>"
                f"</tr>\n"
            )

        # Conteo de veredictos
        n_exc = len(pad_data[pad_data["veredicto"] == "EXCELENTE"])
        n_good = len(pad_data[pad_data["veredicto"] == "BUENO"])
        n_reg = len(pad_data[pad_data["veredicto"] == "REGULAR"])
        n_fail = len(pad_data[pad_data["veredicto"] == "FALLO"])
        n_na = len(pad_data[pad_data["veredicto"] == "N/A"])

        precision_total = ""
        if total_real > 0:
            prec = abs(total_prod - total_real) / total_real * 100
            precision_total = f" | Error acumulado: {prec:.1f}%"

        parts.append(f"""
  <div class="card reveal animate">
    <h2>{PAD_DISPLAY.get(pad, pad)}</h2>
    <div class="table-wrapper">
      <table><thead><tr>
        <th>Entidad</th><th>Real</th><th>Pronostico</th>
        <th>SMAPE</th><th>Motor</th><th>Veredicto</th>
      </tr></thead>
      <tbody>{rows_html}</tbody></table>
    </div>
    <div class="card-footer">
      <span>{_veredicto_badge("EXCELENTE")} {n_exc}</span>
      <span>{_veredicto_badge("BUENO")} {n_good}</span>
      <span>{_veredicto_badge("REGULAR")} {n_reg}</span>
      <span>{_veredicto_badge("FALLO")} {n_fail}</span>
      <span>{_veredicto_badge("N/A")} {n_na}</span>
      <span style="margin-left:auto;font-size:.85rem;color:var(--cool-gray)">
        Total: {_fmt_int(total_real)} real / {_fmt_int(total_prod)} pron{precision_total}
      </span>
    </div>
  </div>""")

    parts.append("</section>")
    return "".join(parts)


def _section_semaforo(comp: pd.DataFrame) -> str:
    """Grid 32x3 solo modo general."""
    general = comp[(comp["nivel"] == "estatal") & (comp["sexo"] == "general")]
    states = [e for e in ENTITY_ORDER if e != "Nacional"]
    header = "<tr><th>Entidad</th>"
    for pad in PADECIMIENTOS:
        header += f"<th>{PAD_DISPLAY.get(pad, pad)}</th>"
    header += "</tr>"

    rows = ""
    for state in states:
        rows += f'<tr><td style="font-family:var(--font-body);font-weight:500">{state}</td>'
        for pad in PADECIMIENTOS:
            match = general[(general["entidad_norm"] == state) & (general["pad_norm"] == pad)]
            if match.empty:
                rows += f"<td>{_semaforo_dot('N/A')}</td>"
            else:
                v = match.iloc[0]["veredicto"]
                err_str = _fmt_error(match.iloc[0]["error_pct"])
                rows += (
                    f'<td style="text-align:center">{_semaforo_dot(v)}'
                    f'<br><span style="font-size:.7rem;color:var(--cool-gray)">'
                    f"{err_str}</span></td>"
                )
        rows += "</tr>"

    leyenda = '<div class="leyenda">'
    for label, color in VEREDICTO_COLORS.items():
        desc = {
            "EXCELENTE": "SMAPE &le;10%",
            "BUENO": "SMAPE &le;25%",
            "REGULAR": "SMAPE &le;50%",
            "FALLO": "SMAPE &gt;50%",
            "N/A": "Sin datos / cero real",
        }[label]
        leyenda += (
            f'<span class="leyenda-item">'
            f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;'
            f'background:{color};vertical-align:middle;margin-right:.3rem"></span>'
            f"{label}: {desc}</span>"
        )
    leyenda += "</div>"

    return f"""
<section class="reveal animate">
  <h2 class="section-title">Semaforo por Entidad</h2>
  <p class="section-sub">Vista rapida (modo general) del desempeno de los modelos</p>
  <div class="card">
    {leyenda}
    <div class="table-wrapper">
      <table class="table-semaforo">
        <thead>{header}</thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>
</section>"""


def _isnan(v: Any) -> bool:
    return isinstance(v, float) and math.isnan(v)


# ---------------------------------------------------------------------------
# Generacion HTML completa
# ---------------------------------------------------------------------------


def _corte_declarado(forecasts: pd.DataFrame) -> tuple[int, int] | None:
    """(anio, semana) del corte que declaran los pronosticos; None si no lo declaran.

    Falla si declaran cortes distintos: el pie de la pagina no puede resumirlos en uno.
    """
    cols = ["anio_boletin_corte", "semana_boletin_corte"]
    if not set(cols) <= set(forecasts.columns):
        return None
    pares = forecasts[cols].dropna().drop_duplicates()
    if pares.empty:
        return None
    if len(pares) > 1:
        raise SystemExit(f"Los pronosticos declaran {len(pares)} cortes distintos")
    return int(pares.iloc[0, 0]), int(pares.iloc[0, 1])


def _semana(etiqueta: str) -> tuple[int, int]:
    anio, semana = etiqueta.split("-W")
    return int(anio), int(semana)


def _resumen_semanas(seg: pd.DataFrame) -> str:
    """Tabla con cada semana evaluada: horizonte, pares validos y ausentes (neuro)."""
    filas = ""
    for etiqueta, g in seg[seg["cohorte"] == "neuro"].groupby("semana_objetivo", sort=True):
        anio, semana = _semana(str(etiqueta))
        pares = int((g["estado"] == "par").sum())
        filas += (
            f"<tr><td>Semana {semana} de {anio}</td><td>{_epiweek_date_range(anio, semana)}</td>"
            f"<td>{int(g['horizonte'].to_numpy()[0])}</td><td>{pares}</td>"
            f"<td>{len(g) - pares}</td></tr>\n"
        )
    return f"""
<section class="reveal">
  <h2 class="section-title">Semanas evaluadas despues del corte</h2>
  <p class="section-sub">Cada fila compara el pronostico guardado desde el corte con lo observado
  esa misma semana del boletin. Un par ausente (falta el pronostico o la observacion desagregable)
  no se rellena ni se desplaza.</p>
  <div class="table-wrapper"><table>
    <thead><tr><th>Semana objetivo</th><th>Fechas del boletin</th><th>Horizonte (semanas)</th>
    <th>Pares validos</th><th>Ausentes</th></tr></thead>
    <tbody>{filas}</tbody>
  </table></div>
</section>"""


def _generate_html(seg: pd.DataFrame, corte: tuple[int, int]) -> str:
    """Pagina de seguimiento: resumen de las semanas evaluadas y el detalle de cada una."""
    ahora = datetime.now(tz=TZ_MX).strftime("%d/%m/%Y %H:%M hrs")
    etiquetas = sorted(seg["semana_objetivo"].unique(), key=_semana)
    n_semanas = len(etiquetas)
    ultima = _semana(etiquetas[-1])
    neuro = seg[seg["cohorte"] == "neuro"]
    n_series = int(neuro[["padecimiento", "entidad", "sexo"]].drop_duplicates().shape[0])
    pie_corte = (
        f"Modelos entrenados con datos hasta la semana {corte[1]}/{corte[0]}; "
        f"realidad observada hasta la semana {ultima[1]}/{ultima[0]}"
    )
    rango = (
        f"semanas {_semana(etiquetas[0])[1]} a {ultima[1]}"
        if n_semanas > 1
        else f"semana {ultima[1]}"
    )

    css = _build_css()
    parts: list[str] = []
    parts.append(f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Seguimiento posterior al corte - Semana {ultima[1]}/{ultima[0]}</title>
{_FONTS_LINK}
<style>{css}</style>
<link rel="stylesheet" href="editorial.css?v=1">
</head>
<body>
<div class="hero">
  <h1>Seguimiento posterior al corte: Realidad vs Pronostico</h1>
  <p class="subtitle">Seguimiento diagnostico posterior al corte de la semana {corte[1]} de {corte[0]};
  no es una evaluacion independiente</p>
  <div class="hero-kpis">
    <div class="hero-kpi">
      <span class="value">{n_semanas}</span>
      <span class="label">Semanas evaluadas ({rango} de {ultima[0]})</span>
    </div>
    <div class="hero-kpi">
      <span class="value">{corte[1]}/{corte[0]}</span>
      <span class="label">Corte de los modelos</span>
    </div>
    <div class="hero-kpi">
      <span class="value">{n_series}</span>
      <span class="label">Series neuro de la asignacion</span>
    </div>
  </div>
</div>
<div class="container">
""")
    parts.append(_resumen_semanas(seg))
    for etiqueta in reversed(etiquetas):  # la mas reciente primero
        anio, semana = _semana(etiqueta)
        g = seg[seg["semana_objetivo"] == etiqueta]
        h = int(g["horizonte"].to_numpy()[0])
        comp = _comparacion(g)
        parts.append(
            f'\n<h2 class="section-title" style="margin-top:3rem">Semana {semana} de {anio} '
            f"(horizonte {h} desde el corte)</h2>\n"
        )
        parts.append(_section_dashboard(comp, anio, semana, h))
        parts.append(_section_nacional(comp))
        parts.append(_section_regional(comp))
        parts.append(_section_detalle(comp))
        parts.append(_section_semaforo(comp))

    parts.append(f"""
</div>
<footer>
  <p class="footer-title">EpiForecast-MX | IMSS 2026</p>
  <p>Datos: Boletin Epidemiologico SINAVE | Generado: {ahora}</p>
  <p>{pie_corte}</p>
  <p>{n_semanas} semana{"s" if n_semanas != 1 else ""} evaluada{"s" if n_semanas != 1 else ""} despues del corte; seguimiento diagnostico, no evaluacion independiente</p>
</footer>
<script>
document.addEventListener('DOMContentLoaded',function(){{
  var els=document.querySelectorAll('.reveal');
  if(!els.length) return;
  var io=new IntersectionObserver(function(entries){{
    entries.forEach(function(e){{if(e.isIntersecting){{e.target.classList.add('visible');io.unobserve(e.target)}}}})
  }},{{threshold:0.1}});
  els.forEach(function(el){{io.observe(el)}});
}});
</script>
</body>
</html>""")

    return "".join(parts)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------


def _build_css() -> str:
    return """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --burgundy:#F472B6;--dark-burgundy:#8E2A63;--teal:#5B8DEF;--dark-teal:#16203A;
  --gold:#2DD4BF;--cream:#E7ECF5;--cream-light:#1C2740;--cream-pale:#131C30;
  --cool-gray:#9FB0CE;--neutral-black:#0B0F1A;
  --burgundy-light:#F472B6;--teal-light:#5B8DEF;--gold-light:#2DD4BF;
  --orange:#FF6F00;--indigo:#5B8DEF;
  --font-display:'DM Serif Display',Georgia,serif;
  --font-body:'Source Sans 3','Source Sans Pro',sans-serif;
  --font-mono:'JetBrains Mono','Fira Code',monospace;
  --shadow-sm:0 2px 8px rgba(0,0,0,.06);--shadow-md:0 8px 24px rgba(0,0,0,.06);
  --shadow-lg:0 16px 48px rgba(0,0,0,.06);--radius:16px;--radius-sm:10px;
}
body{font-family:var(--font-body);background:var(--cream-pale);color:var(--neutral-black);
  line-height:1.7;-webkit-font-smoothing:antialiased}
body::before{content:'';position:fixed;inset:0;
  background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  opacity:.025;pointer-events:none;z-index:0}
.container{max-width:1200px;margin:0 auto;padding:0 2rem;position:relative;z-index:1}
section{padding:3rem 0}
.section-title{font-family:var(--font-display);font-size:clamp(1.8rem,4vw,2.5rem);
  margin-bottom:.5rem;color:var(--dark-teal)}
.section-sub{color:var(--cool-gray);font-size:1rem;margin-bottom:2rem}
.hero{padding:6rem 2rem 4rem;text-align:center;
  background:linear-gradient(170deg,var(--dark-teal) 0%,var(--teal) 60%,rgba(0,82,78,.85) 100%);
  color:var(--cream-pale);position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 800px 600px at 30% 20%,rgba(181,133,0,.12),transparent),
  radial-gradient(ellipse 600px 500px at 70% 80%,rgba(155,34,66,.08),transparent);pointer-events:none}
.hero h1{font-family:var(--font-display);font-size:clamp(2rem,5vw,3.2rem);line-height:1.15;
  margin-bottom:.75rem;position:relative}
.hero .subtitle{font-size:clamp(.95rem,1.8vw,1.15rem);opacity:.8;font-weight:300;
  margin-bottom:2.5rem;position:relative}
.hero-kpis{display:flex;justify-content:center;gap:1.5rem;flex-wrap:wrap;position:relative}
.hero-kpi{background:rgba(255,255,255,.08);border:1px solid rgba(232,213,181,.15);
  border-radius:var(--radius);padding:1.5rem 2rem;backdrop-filter:blur(8px);min-width:160px;
  transition:transform .3s,box-shadow .3s}
.hero-kpi:hover{transform:translateY(-4px);box-shadow:0 12px 32px rgba(0,0,0,.2)}
.hero-kpi .value{font-family:var(--font-display);font-size:2.5rem;display:block;
  background:linear-gradient(135deg,var(--cream),var(--gold-light));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.hero-kpi .label{font-size:.8rem;text-transform:uppercase;letter-spacing:1px;opacity:.7}
.card{background:rgba(255,255,255,0.03);color:var(--text-primary,#EAEFF8);border-radius:var(--radius);padding:2rem;box-shadow:var(--shadow-md);
  border:1px solid rgba(0,0,0,.04);transition:transform .3s,box-shadow .3s;margin-bottom:2rem}
.card:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}
.card h2{font-family:var(--font-display);font-size:1.5rem;margin-bottom:1rem;
  padding-bottom:.75rem;border-bottom:2px solid var(--cream-light);color:var(--dark-teal)}
.card-gold{border-left:4px solid var(--gold)}
.card-footer{display:flex;align-items:center;flex-wrap:wrap;gap:.75rem;
  margin-top:1rem;padding-top:1rem;border-top:1px solid var(--cream-light)}
.table-wrapper{overflow-x:auto;margin-top:.5rem}
table{width:100%;border-collapse:collapse;font-size:.88rem}
thead th{padding:.85rem 1rem;text-align:center;font-weight:600;text-transform:uppercase;
  font-size:.72rem;letter-spacing:.5px;color:var(--cool-gray);
  border-bottom:2px solid var(--cream-light);white-space:nowrap;
  position:sticky;top:0;background:#0E1424;z-index:2}
td:first-child,th:first-child{text-align:left}
tbody td{padding:.7rem 1rem;border-bottom:1px solid var(--cream-light);vertical-align:middle;
  font-family:var(--font-mono);font-size:.82rem;text-align:center}
tbody td:first-child{font-family:var(--font-body);font-size:.88rem;text-align:left}
tbody tr{transition:background .15s}
tbody tr:hover{background:rgba(255,255,255,0.05)}
.row-nacional{background:rgba(181,133,0,.06);font-weight:700}
.row-nacional td{border-bottom:2px solid var(--gold)}
.row-group-last td{border-bottom:2px solid var(--cream)}
.err-good{color:#2DD4BF;font-weight:600}
.err-bad{color:#EF4444;font-weight:600}
.mase-good{color:#2DD4BF;font-weight:600}
.mase-warn{color:#EF4444;font-weight:600}
.table-semaforo td{text-align:center;padding:.5rem .75rem}
.table-semaforo th{min-width:140px}
.leyenda{display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:1.5rem;
  padding:1rem;background:var(--cream-pale);border-radius:var(--radius-sm)}
.leyenda-item{display:inline-flex;align-items:center;gap:.3rem;font-size:.85rem}
.reveal.animate{opacity:0;transform:translateY(30px);transition:opacity .6s ease,transform .6s ease}
.reveal.visible{opacity:1;transform:translateY(0)}

.dashboard{background:linear-gradient(170deg,#0a1628 0%,var(--dark-teal) 50%,#0d2b28 100%);
  border-radius:var(--radius);padding:3rem 2rem;margin-bottom:2rem;position:relative;overflow:hidden}
.dashboard::before{content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 600px 400px at 20% 30%,rgba(181,133,0,.08),transparent),
  radial-gradient(ellipse 400px 300px at 80% 70%,rgba(155,34,66,.06),transparent);pointer-events:none}
.dashboard::after{content:'';position:absolute;inset:0;
  background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  opacity:.03;pointer-events:none}
.dashboard-header{text-align:center;margin-bottom:2.5rem;position:relative;z-index:1}
.dashboard-header h2{font-family:var(--font-display);font-size:clamp(1.6rem,3.5vw,2.2rem);
  color:var(--cream);margin-bottom:.4rem}
.dashboard-header p{color:rgba(232,213,181,.5);font-size:.95rem}
.dashboard-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;position:relative;z-index:1}
.dash-panel{background:rgba(255,255,255,.05);border:1px solid rgba(232,213,181,.1);
  border-radius:var(--radius);padding:2rem 1.5rem;text-align:center;
  backdrop-filter:blur(12px);transition:transform .3s,box-shadow .3s}
.dash-panel:hover{transform:translateY(-5px);box-shadow:0 20px 50px rgba(0,0,0,.35)}
.dash-panel h3{font-family:var(--font-display);color:var(--cream);font-size:1.1rem;
  margin-bottom:1.2rem;letter-spacing:.3px}
.gauge-wrap{display:flex;justify-content:center;margin-bottom:1.2rem}
.gauge-arc{stroke-dashoffset:408.41;transition:stroke-dashoffset 2s cubic-bezier(.4,0,.2,1) .6s}
.visible .gauge-arc{stroke-dashoffset:var(--to)}
.dash-nums{display:flex;align-items:center;justify-content:center;gap:.8rem;margin-bottom:1.2rem}
.dash-n{text-align:center}
.dash-v{font-family:var(--font-display);font-size:1.4rem;color:var(--cream);display:block}
.dash-l{font-size:.7rem;color:rgba(232,213,181,.45);text-transform:uppercase;letter-spacing:.5px}
.dash-badges{display:flex;justify-content:center;gap:.5rem;margin-top:1rem}
.mase-box{margin:0 0 .5rem;padding:1rem;background:rgba(0,0,0,.18);border-radius:var(--radius-sm)}
.mase-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem}
.mase-title{color:rgba(232,213,181,.5);font-size:.75rem;text-transform:uppercase;letter-spacing:.5px}
.mase-val{font-family:var(--font-display);font-size:1.15rem}
.mase-track{height:6px;background:rgba(255,255,255,.07);border-radius:3px;position:relative;
  margin-bottom:.3rem}
.mase-fill{height:100%;border-radius:3px;width:0;
  transition:width 1.8s cubic-bezier(.4,0,.2,1) 1.2s}
.visible .mase-fill{width:var(--mw)}
.mase-ref{position:absolute;left:50%;top:-4px;width:2px;height:14px;
  background:rgba(232,213,181,.35);border-radius:1px}
.mase-ticks{display:flex;justify-content:space-between;position:relative;
  font-size:.6rem;color:rgba(232,213,181,.25);font-family:var(--font-mono)}
.mase-lbl{font-size:.78rem;font-weight:600;margin-top:.3rem}

footer{background:var(--dark-teal);color:rgba(232,213,181,.7);padding:3rem 2rem;
  text-align:center;font-size:.85rem;position:relative;z-index:1;margin-top:2rem}
footer .footer-title{font-family:var(--font-display);color:var(--cream);font-size:1.2rem;
  margin-bottom:.5rem}
@media(max-width:768px){
  .hero{padding:4rem 1.5rem 3rem}.hero-kpis{gap:.75rem}
  .hero-kpi{min-width:130px;padding:1rem 1.25rem}.hero-kpi .value{font-size:1.8rem}
  .container{padding:0 1rem}section{padding:2rem 0}
  .card-footer{flex-direction:column;align-items:flex-start}
  .leyenda{flex-direction:column;gap:.5rem}
  .dashboard-grid{grid-template-columns:1fr}.dashboard{padding:2rem 1rem}
}
"""


# ---------------------------------------------------------------------------
# Actualizacion del Excel de produccion
# ---------------------------------------------------------------------------


COLUMNAS_VALIDACION = (
    "semana_validacion",
    "corte_validacion",
    "horizonte_validacion",
    "estado_validacion",
)


def _update_excel(seg_ultima: pd.DataFrame, ruta_excel: Path = PROD_EXCEL) -> int:
    """Escribe en la tabla (`ruta_excel`) el par de la ULTIMA semana evaluada, ambos lados juntos.

    ``pron_sem_previa`` y ``realidad_sem_previa`` quedan de la misma semana objetivo, y cuatro
    columnas declaran cual (semana, corte, horizonte y estado del par). Un par ausente deja ambas
    celdas vacias: nunca se conserva el pronostico de otra semana junto a una realidad nueva.
    Devuelve cuantas filas se escribieron.
    """
    from openpyxl import load_workbook

    etiquetas = set(seg_ultima["semana_objetivo"])
    if len(etiquetas) != 1:
        raise ValueError(f"se esperaba UNA semana objetivo, hay {sorted(etiquetas)}")
    wb = load_workbook(ruta_excel)
    ws = wb["Produccion"] if "Produccion" in wb.sheetnames else wb.active
    if ws is None:
        raise ValueError(f"{ruta_excel}: sin hoja de produccion")
    headers = [cell.value for cell in ws[1]]
    for nombre in COLUMNAS_VALIDACION:
        if nombre not in headers:
            ws.cell(row=1, column=len(headers) + 1).value = nombre
            headers.append(nombre)
    col = {h: i + 1 for i, h in enumerate(headers) if h}
    for requerida in ("padecimiento", "entidad", "sexo", "pron_sem_previa", "realidad_sem_previa"):
        if requerida not in col:
            raise ValueError(f"{ruta_excel}: falta la columna {requerida}")

    registros = _registros(seg_ultima[seg_ultima["cohorte"] == "neuro"])
    pares = {
        (
            _normalize(str(r["padecimiento"])),
            _norm_prod_entidad(str(r["entidad"])),
            str(r["sexo"]),
        ): r
        for r in registros
    }
    escritas = 0
    for fila in range(2, ws.max_row + 1):
        clave = (
            _normalize(str(ws.cell(row=fila, column=col["padecimiento"]).value or "")),
            _norm_prod_entidad(str(ws.cell(row=fila, column=col["entidad"]).value or "")),
            str(ws.cell(row=fila, column=col["sexo"]).value or ""),
        )
        r = pares.get(clave)
        if r is None:
            continue
        es_par = r["estado"] == "par"
        celdas = {
            "pron_sem_previa": int(r["pronostico"]) if es_par else None,
            "realidad_sem_previa": int(r["real"]) if es_par else None,
            "semana_validacion": str(r["semana_objetivo"]),
            "corte_validacion": str(r["corte"]),
            "horizonte_validacion": int(r["horizonte"]),
            "estado_validacion": "par" if es_par else f"ausente: {r['motivo']}",
        }
        for nombre, valor in celdas.items():
            ws.cell(row=fila, column=col[nombre]).value = valor
        escritas += 1
    if escritas != len(pares):
        raise ValueError(f"la tabla emparejo {escritas} de {len(pares)} series del seguimiento")
    wb.save(ruta_excel)
    print(f"  Excel actualizado: {escritas} filas con el par de la semana {next(iter(etiquetas))}")
    return escritas


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validacion semanal Real vs Forecast.")
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT.parent,
        help="directorio de salida para validacion_semanal.html y la COPIA actualizada de "
        "tabla_333_modelos_produccion.xlsx (por defecto reports/ProdDetails, en el sitio). "
        "Con otro directorio el Excel del arbol real no se toca.",
    )
    parser.add_argument(
        "--seguimiento",
        type=Path,
        required=True,
        help="seguimiento_post_corte.csv (genera_seguimiento_post_corte.py): los pares de cada "
        "semana evaluada despues del corte",
    )
    return parser.parse_args(argv)


def _destino_excel(out_dir: Path) -> Path:
    """Dónde actualizar el Excel: en su sitio (legacy) o una copia bajo `--out`.

    Con `--out` distinto del directorio canónico, el Excel real se copia y se actualiza
    la copia: el generador deja de escribir en el árbol real, que es lo que ensuciaba el
    repositorio en cada refresh y obligaba a sellar un artefacto que ya había mutado.
    """
    if out_dir.resolve() == PROD_EXCEL.parent.resolve():
        return PROD_EXCEL
    destino = out_dir / PROD_EXCEL.name
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PROD_EXCEL, destino)
    return destino


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _normaliza_para_hooks(html: str) -> str:
    """Deja el HTML en la forma que exigen los hooks del repositorio.

    Este informe se versiona en git, y los hooks `trailing-whitespace` y
    `end-of-file-fixer` lo reescribian al confirmarlo. Con el refresh semanal sellado eso
    era un problema real y no cosmetico: el archivo publicado dejaba de ser byte a byte el
    que se habia revisado, porque el hook lo modificaba entre el sello y el commit.

    Emitirlo ya normalizado hace que el hook no tenga nada que cambiar, de modo que lo
    sellado y lo publicado coincidan sin intervencion.
    """
    lineas = [linea.rstrip() for linea in html.split("\n")]
    return "\n".join(lineas).rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    out_dir = args.out
    salida_html = out_dir / OUTPUT.name
    seg = pd.read_csv(args.seguimiento)
    if seg.empty:
        raise SystemExit("seguimiento sin filas: no hay semana evaluada despues del corte")
    cortes = seg["corte"].unique()
    if len(cortes) != 1:
        raise SystemExit(f"el seguimiento mezcla cortes: {sorted(cortes)}")
    corte = _semana(str(cortes[0]))
    etiquetas = sorted(seg["semana_objetivo"].unique(), key=_semana)
    print(f"Seguimiento posterior al corte {cortes[0]}: {len(etiquetas)} semana(s) {etiquetas}")

    print("Generando HTML...")
    html = _generate_html(seg, corte)
    salida_html.parent.mkdir(parents=True, exist_ok=True)
    salida_html.write_text(_normaliza_para_hooks(html), encoding="utf-8")
    print(f"  {salida_html} ({len(html):,} bytes)")

    print("Actualizando la copia de la tabla de produccion (ultima semana evaluada)...")
    _update_excel(seg[seg["semana_objetivo"] == etiquetas[-1]], _destino_excel(out_dir))
    print("Listo.")


if __name__ == "__main__":
    main()
