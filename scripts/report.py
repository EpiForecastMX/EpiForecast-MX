"""
Genera reporte HTML interactivo con los resultados del modelado Prophet.

Uso:
    python -m scripts.genera_reporte

Salida:
    forecast/reporte_resultados.html
"""

from datetime import datetime
import json
import math
from pathlib import Path
import unicodedata

import pandas as pd

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
FORECAST_CSV = Path("forecast/all_forecast.csv")
OUTPUT_HTML = Path("forecast/reporte_resultados.html")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
COLORS_BY_SAFE = {
    "alzheimer": {"main": "#B58500", "light": "#D4B24A", "glow": "rgba(181,133,0,0.10)"},
    "depresion": {"main": "#9B2242", "light": "#D4758B", "glow": "rgba(155,34,66,0.06)"},
    "parkinson": {"main": "#00524E", "light": "#4A9E9A", "glow": "rgba(0,82,78,0.08)"},
}
PAD_ORDER = ["Alzheimer", "Depresión", "Parkinson"]
MODO_ORDER = ["general", "hombres", "mujeres"]
MODO_LABELS = {"general": "General", "hombres": "Hombres", "mujeres": "Mujeres"}

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
    "Rural / dispersa": [
        "Guerrero",
        "Hidalgo",
        "Michoacán",
        "Nayarit",
        "Puebla",
        "Tlaxcala",
    ],
}


def _safe_key(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _clean(v):
    """Make value JSON-safe (no NaN/Inf)."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------
def load_and_deduplicate(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    return (
        df.groupby(["meta_padecimiento", "meta_entidad", "meta_modo"], dropna=False)
        .first()
        .reset_index()
    )


def compute_stats(df: pd.DataFrame) -> dict:
    stats: dict = {}

    # --- Global ---
    stats["total_modelos"] = len(df)
    estados_df = df[
        ~df["meta_entidad"].str.startswith("Region", na=False) & (df["meta_entidad"] != "Nacional")
    ]
    stats["cobertura_estatal"] = round(estados_df["meta_entidad"].nunique() / 32 * 100)
    stats["mase_global"] = _clean(round(df["mase_usado"].mean(), 2))
    stats["fecha"] = datetime.now().strftime("%d/%m/%Y")
    mase_gt1 = int((df["mase_usado"] > 1).sum())
    mase_lt07 = int((df["mase_usado"] < 0.7).sum())
    stats["modelos_excelentes"] = mase_lt07
    stats["modelos_deficientes"] = mase_gt1

    # --- Counts by type ---
    n_nacional = len(df[df["meta_entidad"] == "Nacional"])
    n_regional = len(df[df["meta_entidad"].str.startswith("Region", na=False)])
    n_estatal = len(estados_df)
    stats["conteo_tipo"] = {"nacional": n_nacional, "regional": n_regional, "estatal": n_estatal}

    # --- Por padecimiento ---
    pad_stats = []
    for pad in PAD_ORDER:
        sub = df[df["meta_padecimiento"] == pad]
        sub_est = estados_df[estados_df["meta_padecimiento"] == pad]
        insuf = int((sub["confianza_original"] == "insuficiente").sum())
        fallback = int((sub["archivo_modelo_original"] != sub["archivo_modelo_usado"]).sum())
        n_reg = int(sub["meta_entidad"].str.startswith("Region", na=False).sum())
        pad_stats.append(
            {
                "padecimiento": pad,
                "total": len(sub),
                "estatales": len(sub_est),
                "nacionales": int((sub["meta_entidad"] == "Nacional").sum()),
                "regionales": n_reg,
                "mase": _clean(round(sub["mase_usado"].mean(), 2)),
                "rmse": _clean(round(sub["rmse_usado"].mean(), 3)),
                "mae": _clean(round(sub["mae_usado"].mean(), 3)),
                "mape": _clean(round(sub["mape_usado"].mean(), 2)),
                "insuficientes": insuf,
                "fallback": fallback,
                "mase_min": _clean(round(sub["mase_usado"].min(), 2)),
                "mase_max": _clean(round(sub["mase_usado"].max(), 2)),
                "mase_median": _clean(round(sub["mase_usado"].median(), 2)),
            }
        )
    stats["por_padecimiento"] = pad_stats

    # --- MASE histogram bins ---
    bins = [0, 0.5, 0.7, 0.85, 1.0, 999]
    bin_labels = ["< 0.5", "0.5–0.7", "0.7–0.85", "0.85–1.0", "> 1.0"]
    histo = []
    for pad in PAD_ORDER:
        sub = df[df["meta_padecimiento"] == pad]["mase_usado"].dropna()
        counts = pd.cut(sub, bins=bins, labels=bin_labels, right=False).value_counts()
        histo.append(
            {
                "padecimiento": pad,
                "bins": [int(counts.get(b, 0)) for b in bin_labels],
            }
        )
    stats["mase_histo"] = histo
    stats["mase_bin_labels"] = bin_labels

    # --- Por sexo × padecimiento ---
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
                    "mase": _clean(round(sub["mase_usado"].mean(), 2)),
                    "rmse": _clean(round(sub["rmse_usado"].mean(), 3)),
                }
            )
    stats["por_sexo"] = sexo_stats

    # --- Ranking (with group) ---
    ranking = []
    for _, row in df.iterrows():
        ent = row["meta_entidad"]
        if ent == "Nacional":
            grupo = "Nacional"
            orden = 0
        elif str(ent).startswith("Region"):
            grupo = "Regional"
            orden = 1
        else:
            grupo = "Estatal"
            orden = 2
        es_fallback = row["archivo_modelo_original"] != row["archivo_modelo_usado"]
        ranking.append(
            {
                "entidad": ent,
                "padecimiento": row["meta_padecimiento"],
                "modo": MODO_LABELS.get(row["meta_modo"], row["meta_modo"]),
                "mase": _clean(round(row["mase_usado"], 2))
                if pd.notna(row["mase_usado"])
                else None,
                "rmse": _clean(round(row["rmse_usado"], 3))
                if pd.notna(row["rmse_usado"])
                else None,
                "mae": _clean(round(row["mae_usado"], 3)) if pd.notna(row["mae_usado"]) else None,
                "confianza": row.get("confianza_original", "normal"),
                "tipo": "Regional (fallback)" if es_fallback else "Propio",
                "grupo": grupo,
                "orden": orden,
            }
        )
    stats["ranking"] = ranking

    # --- Cobertura (estado × padecimiento) ---
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
                es_fb = (
                    sub.iloc[0]["archivo_modelo_original"] != sub.iloc[0]["archivo_modelo_usado"]
                )
                entry[key] = "fallback" if es_fb else "propio"
        cobertura.append(entry)

    cob_resumen = {}
    for pad in PAD_ORDER:
        key = _safe_key(pad)
        propios = sum(1 for c in cobertura if c[key] == "propio")
        fallbacks = sum(1 for c in cobertura if c[key] == "fallback")
        cob_resumen[key] = {"propios": propios, "fallback": fallbacks}
    stats["cobertura"] = cobertura
    stats["cobertura_resumen"] = cob_resumen

    # --- Top / Bottom 10 ---
    valid = df[df["mase_usado"].notna()].copy()
    valid["_label"] = (
        valid["meta_entidad"]
        + " — "
        + valid["meta_padecimiento"]
        + " ("
        + valid["meta_modo"]
        + ")"
    )
    for name, method, n in [("top10", "nsmallest", 10), ("bottom10", "nlargest", 10)]:
        sel = getattr(valid, method)(n, "mase_usado")
        stats[name] = [
            {
                "label": r["_label"],
                "mase": round(r["mase_usado"], 2),
                "padecimiento": r["meta_padecimiento"],
            }
            for _, r in sel.iterrows()
        ]

    # --- Pad meta for JS ---
    stats["pad_meta"] = [
        {"name": pad, "key": _safe_key(pad), **COLORS_BY_SAFE[_safe_key(pad)]} for pad in PAD_ORDER
    ]

    # --- Regiones INEGI info ---
    stats["regiones_inegi"] = {name: estados for name, estados in REGIONES_INEGI.items()}

    return stats


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
def build_html(stats: dict) -> str:
    data_json = json.dumps(stats, ensure_ascii=False)

    # Pre-compute padecimiento explanation
    pad_explain = []
    for p in stats["por_padecimiento"]:
        base = 99
        extra = p["regionales"]
        if extra == 0:
            pad_explain.append(
                f"<strong>{p['padecimiento']}</strong>: {p['total']} modelos "
                f"(32 estados x 3 modos + 3 nacionales). "
                f"Todos los estados tienen datos suficientes."
            )
        else:
            n_reg = extra // 3
            pad_explain.append(
                f"<strong>{p['padecimiento']}</strong>: {p['total']} modelos "
                f"({base} base + {extra} regionales de respaldo). "
                f"{p['insuficientes']} modelos estatales no tienen datos suficientes "
                f"y usan el modelo de su region ({n_reg} regiones activas)."
            )
    pad_explain_html = "<br>".join(pad_explain)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Resultados del Modelado — EpiForecast-MX</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Source+Sans+3:ital,wght@0,300;0,400;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --burgundy:#9B2242;--dark-burgundy:#6F1D46;--teal:#00524E;--dark-teal:#173F35;
  --gold:#B58500;--cream:#E8D5B5;--cream-light:#F5EDE0;--cream-pale:#FAF6F0;
  --cool-gray:#97999B;--neutral-black:#231F20;
  --burgundy-light:#D4758B;--teal-light:#4A9E9A;--gold-light:#D4B24A;
  --font-display:'DM Serif Display',Georgia,serif;
  --font-body:'Source Sans 3','Source Sans Pro',sans-serif;
  --font-mono:'JetBrains Mono','Fira Code',monospace;
  --shadow-sm:0 2px 8px rgba(0,0,0,.06);--shadow-md:0 8px 24px rgba(0,0,0,.06);
  --shadow-lg:0 16px 48px rgba(0,0,0,.06);--radius:16px;--radius-sm:10px;
}}
body{{font-family:var(--font-body);background:var(--cream-pale);color:var(--neutral-black);line-height:1.7;-webkit-font-smoothing:antialiased}}
body::before{{content:'';position:fixed;inset:0;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");opacity:.025;pointer-events:none;z-index:0}}

nav{{position:fixed;top:0;left:0;right:0;z-index:1000;background:rgba(23,63,53,.96);backdrop-filter:blur(16px);border-bottom:1px solid rgba(232,213,181,.1);padding:0 2rem;height:64px;display:flex;align-items:center;justify-content:space-between}}
nav .logo{{color:var(--cream);font-family:var(--font-display);font-size:1.3rem;letter-spacing:.02em}}
nav .nav-links{{display:flex;gap:1.5rem}}
nav .nav-links a{{color:rgba(232,213,181,.7);text-decoration:none;font-size:.85rem;font-weight:600;text-transform:uppercase;letter-spacing:.5px;transition:color .2s}}
nav .nav-links a:hover{{color:var(--cream)}}
nav .nav-links a.sep{{margin-left:1rem;padding-left:1.25rem;border-left:1px solid rgba(232,213,181,.25)}}
nav .nav-links a.ext{{color:var(--gold-light)}}

.container{{max-width:1200px;margin:0 auto;padding:0 2rem;position:relative;z-index:1}}
section{{padding:4rem 0}}
.section-title{{font-family:var(--font-display);font-size:clamp(1.8rem,4vw,2.5rem);margin-bottom:.5rem;color:var(--dark-teal)}}
.section-sub{{color:var(--cool-gray);font-size:1rem;margin-bottom:2.5rem}}

.hero{{padding:10rem 2rem 6rem;text-align:center;background:linear-gradient(170deg,var(--dark-teal) 0%,var(--teal) 60%,rgba(0,82,78,.85) 100%);color:var(--cream-pale);position:relative;overflow:hidden}}
.hero::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 800px 600px at 30% 20%,rgba(181,133,0,.12),transparent),radial-gradient(ellipse 600px 500px at 70% 80%,rgba(155,34,66,.08),transparent);pointer-events:none}}
.hero h1{{font-family:var(--font-display);font-size:clamp(2.5rem,6vw,4.5rem);line-height:1.1;margin-bottom:1rem;position:relative}}
.hero .subtitle{{font-size:clamp(1rem,2vw,1.25rem);opacity:.8;font-weight:300;margin-bottom:3rem;position:relative}}
.hero-kpis{{display:flex;justify-content:center;gap:2rem;flex-wrap:wrap;position:relative}}
.hero-kpi{{background:rgba(255,255,255,.08);border:1px solid rgba(232,213,181,.15);border-radius:var(--radius);padding:2rem 2.5rem;backdrop-filter:blur(8px);min-width:180px;transition:transform .3s,box-shadow .3s}}
.hero-kpi:hover{{transform:translateY(-4px);box-shadow:0 12px 32px rgba(0,0,0,.2)}}
.hero-kpi .value{{font-family:var(--font-display);font-size:3rem;display:block;background:linear-gradient(135deg,var(--cream),var(--gold-light));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.hero-kpi .label{{font-size:.85rem;text-transform:uppercase;letter-spacing:1px;opacity:.7}}

.card-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:2rem}}
.card{{background:#fff;border-radius:var(--radius);padding:2rem;box-shadow:var(--shadow-md);border:1px solid rgba(0,0,0,.04);transition:transform .3s,box-shadow .3s}}
.card:hover{{transform:translateY(-3px);box-shadow:var(--shadow-lg)}}
.card-header{{display:flex;align-items:center;gap:.75rem;margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:2px solid var(--cream-light)}}
.card-dot{{width:14px;height:14px;border-radius:50%;flex-shrink:0;box-shadow:0 0 8px currentColor}}
.card-title{{font-family:var(--font-display);font-size:1.4rem}}
.card-metrics{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}
.metric{{background:var(--cream-pale);border-radius:var(--radius-sm);padding:.75rem 1rem}}
.metric-value{{font-family:var(--font-mono);font-size:1.4rem;font-weight:500}}
.metric-label{{font-size:.75rem;text-transform:uppercase;letter-spacing:.5px;color:var(--cool-gray)}}

.chart-wrap{{background:#fff;border-radius:var(--radius);padding:2rem;box-shadow:var(--shadow-md);border:1px solid rgba(0,0,0,.04)}}
.chart-wrap canvas{{max-height:400px}}
.charts-row{{display:grid;grid-template-columns:1fr 1fr;gap:2rem;margin-top:2rem}}

/* guide cards */
.guide-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1.5rem;margin-top:1.5rem}}
.guide-card{{background:#fff;border-radius:var(--radius);padding:1.5rem 1.75rem;box-shadow:var(--shadow-sm);border-left:4px solid var(--teal)}}
.guide-card h3{{font-family:var(--font-display);font-size:1.15rem;margin-bottom:.5rem;color:var(--dark-teal)}}
.guide-card p{{font-size:.92rem;color:#555;line-height:1.7}}
.guide-card .badge{{margin:0 2px}}

/* region map */
.region-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:1rem;margin-top:1rem}}
.region-card{{background:var(--cream-pale);border-radius:var(--radius-sm);padding:1rem 1.25rem;border:1px solid var(--cream)}}
.region-card h4{{font-size:.95rem;font-weight:700;margin-bottom:.4rem;color:var(--dark-teal)}}
.region-card p{{font-size:.82rem;color:var(--cool-gray);line-height:1.5}}

/* table */
.table-wrapper{{background:#fff;border-radius:var(--radius);box-shadow:var(--shadow-md);border:1px solid rgba(0,0,0,.04);overflow:hidden}}
.table-controls{{display:flex;gap:1rem;padding:1.5rem 2rem;flex-wrap:wrap;border-bottom:1px solid var(--cream-light);align-items:center}}
.table-controls input,.table-controls select{{font-family:var(--font-body);font-size:.9rem;padding:.5rem 1rem;border:1px solid var(--cream);border-radius:6px;background:var(--cream-pale);color:var(--neutral-black);outline:none;transition:border-color .2s}}
.table-controls input:focus,.table-controls select:focus{{border-color:var(--teal)}}
.table-controls input{{flex:1;min-width:180px}}
table{{width:100%;border-collapse:collapse;font-size:.9rem}}
thead th{{padding:1rem 1.25rem;text-align:left;font-weight:600;text-transform:uppercase;font-size:.75rem;letter-spacing:.5px;color:var(--cool-gray);border-bottom:2px solid var(--cream-light);cursor:pointer;user-select:none;white-space:nowrap;transition:color .2s}}
thead th:hover{{color:var(--teal)}}
thead th.sorted-asc::after{{content:' \\25B2';font-size:.65rem}}
thead th.sorted-desc::after{{content:' \\25BC';font-size:.65rem}}
tbody td{{padding:.85rem 1.25rem;border-bottom:1px solid var(--cream-light);vertical-align:middle}}
tbody tr{{transition:background .15s}}
tbody tr:hover{{background:var(--cream-pale)}}
.group-header td{{background:var(--dark-teal);color:var(--cream);font-weight:700;font-size:.8rem;text-transform:uppercase;letter-spacing:1px;padding:.6rem 1.25rem;border:none}}

.badge{{display:inline-block;padding:.2rem .7rem;border-radius:100px;font-family:var(--font-mono);font-size:.8rem;font-weight:500}}
.badge-green{{background:#e6f4ea;color:#1a7431}}
.badge-yellow{{background:#fef7e0;color:#8a6d00}}
.badge-red{{background:#fde8e8;color:#b91c1c}}
.badge-tipo{{font-family:var(--font-body);font-size:.78rem;font-weight:600;padding:.25rem .8rem;border-radius:100px}}
.badge-propio{{background:#e6f4ea;color:#1a7431}}
.badge-fallback{{background:#fef0e6;color:#c2590a}}

.cob-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.75rem}}
.cob-item{{display:flex;align-items:center;gap:.75rem;background:#fff;border-radius:var(--radius-sm);padding:.6rem 1rem;box-shadow:var(--shadow-sm);border:1px solid rgba(0,0,0,.04);font-size:.88rem}}
.cob-item .estado-name{{flex:1;font-weight:600;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.cob-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.cob-dot.propio{{background:#1a7431;box-shadow:0 0 4px rgba(26,116,49,.4)}}
.cob-dot.fallback{{background:#c2590a;box-shadow:0 0 4px rgba(194,89,10,.4)}}
.cob-dot.sin_modelo{{background:var(--cool-gray);opacity:.4}}
.cob-summary{{display:flex;gap:2rem;margin-bottom:1.5rem;flex-wrap:wrap}}
.cob-summary-item{{display:flex;align-items:center;gap:.5rem;font-size:.85rem}}

.reveal{{opacity:0;transform:translateY(30px);transition:opacity .6s ease,transform .6s ease}}
.reveal.visible{{opacity:1;transform:translateY(0)}}

footer{{background:var(--dark-teal);color:rgba(232,213,181,.7);padding:3rem 2rem;text-align:center;font-size:.85rem;position:relative;z-index:1}}
footer a{{color:var(--gold-light);text-decoration:none}}
footer a:hover{{color:var(--cream)}}
footer .footer-title{{font-family:var(--font-display);color:var(--cream);font-size:1.2rem;margin-bottom:.5rem}}

@media(max-width:768px){{
  nav .nav-links{{display:none}}
  .hero{{padding:8rem 1.5rem 4rem}}.hero-kpis{{gap:1rem}}.hero-kpi{{min-width:140px;padding:1.25rem}}.hero-kpi .value{{font-size:2.2rem}}
  .card-grid,.charts-row,.guide-grid,.region-grid{{grid-template-columns:1fr}}
  .table-controls{{flex-direction:column}}section{{padding:2.5rem 0}}.container{{padding:0 1rem}}
}}
</style>
</head>
<body>

<nav>
  <a href="index.html" class="logo" style="text-decoration:none;color:inherit">EpiForecast-MX</a>
  <div class="nav-links">
    <a href="index.html" class="ext">Inicio</a>
    <a href="EpiDashboard.html" class="ext">Dashboard</a>
    <a href="Reports/index.html" class="ext">Pronosticos</a>
    <a href="#guia" class="sep">Guia</a>
    <a href="#resumen">Resumen</a>
    <a href="#calidad">Calidad</a>
    <a href="#ranking">Ranking</a>
    <a href="#cobertura">Cobertura</a>
  </div>
</nav>

<!-- ═══ HERO ═══ -->
<section class="hero">
  <h1>Resultados del Modelado</h1>
  <p class="subtitle">EpiForecast-MX &middot; IMSS &times; Tec de Monterrey &middot; {stats["fecha"]}</p>
  <div class="hero-kpis">
    <div class="hero-kpi"><span class="value">{stats["total_modelos"]}</span><span class="label">Modelos Prophet</span></div>
    <div class="hero-kpi"><span class="value">{stats["cobertura_estatal"]}%</span><span class="label">Cobertura Estatal</span></div>
    <div class="hero-kpi"><span class="value">{stats["mase_global"]}</span><span class="label">MASE Promedio</span></div>
    <div class="hero-kpi"><span class="value">{stats["modelos_excelentes"]}</span><span class="label">Excelentes (MASE&lt;0.7)</span></div>
  </div>
</section>

<!-- ═══ GUIA ═══ -->
<section id="guia" style="background:#fff;padding:4rem 0">
  <div class="container">
    <h2 class="section-title reveal">Antes de empezar: guia rapida</h2>
    <p class="section-sub reveal">Todo lo que necesitas saber para entender este reporte, explicado de forma sencilla</p>
    <div class="guide-grid">
      <div class="guide-card" style="border-left-color:var(--teal)">
        <h3>Que mide el MASE</h3>
        <p>El MASE es como una <strong>calificacion</strong> del modelo. Lo compara contra el metodo mas simple posible: repetir lo que paso hace exactamente un ano.
        <br><br><span class="badge badge-green">&lt; 0.7 Excelente</span> <span class="badge badge-yellow">0.7 – 1.0 Bueno</span> <span class="badge badge-red">&gt; 1.0 Necesita mejora</span>
        <br><br>Si el MASE es menor a 1, <strong>nuestro modelo es mejor que solo copiar el pasado</strong>. Entre mas bajo, mejor.</p>
      </div>
      <div class="guide-card" style="border-left-color:var(--gold)">
        <h3>Las 4 regiones INEGI de salud mental</h3>
        <p>El INEGI agrupa los 32 estados en <strong>4 zonas</strong> segun sus patrones de salud mental. Esto importa porque estados de la misma zona se comportan de forma similar:</p>
        <div class="region-grid" style="margin-top:.75rem">
          <div class="region-card"><h4>Metropolitana alta</h4><p>CDMX, Edo. Mex, Jalisco, Nuevo Leon, Chihuahua, Baja California, Coahuila, Sinaloa, Sonora, Tamaulipas</p></div>
          <div class="region-card"><h4>Urbana media</h4><p>Aguascalientes, BCS, Colima, Durango, Guanajuato, Morelos, Queretaro, San Luis Potosi, Zacatecas</p></div>
          <div class="region-card"><h4>Sur-Sureste vulnerable</h4><p>Campeche, Chiapas, Oaxaca, Quintana Roo, Tabasco, Veracruz, Yucatan</p></div>
          <div class="region-card"><h4>Rural / dispersa</h4><p>Guerrero, Hidalgo, Michoacan, Nayarit, Puebla, Tlaxcala</p></div>
        </div>
      </div>
      <div class="guide-card" style="border-left-color:var(--burgundy)">
        <h3>Que es un modelo &laquo;fallback&raquo; regional</h3>
        <p>Algunos estados tienen <strong>tan pocos casos</strong> (menos de 0.5 por semana) que no hay datos suficientes para entrenar un modelo confiable solo para ese estado.
        <br><br>En lugar de dar un pronostico malo, <strong>usamos el modelo de toda su region INEGI</strong>, que tiene muchos mas datos. El pronostico final se ajusta con la poblacion individual de cada estado.
        <br><br>Es como pedir prestada la experiencia de los vecinos para hacer una mejor prediccion.</p>
      </div>
      <div class="guide-card" style="border-left-color:var(--cool-gray)">
        <h3>Por que hay diferente numero de modelos</h3>
        <p>Cada padecimiento tiene una base de <strong>99 modelos</strong> (32 estados &times; 3 modos de sexo + 3 nacionales). La diferencia viene de cuantos modelos regionales de respaldo se necesitan:
        <br><br>{pad_explain_html}</p>
      </div>
      <div class="guide-card" style="border-left-color:var(--teal)">
        <h3>Las 4 metricas del modelo</h3>
        <p>Cada modelo se evalua con cuatro metricas complementarias:
        <br><br><strong>MASE</strong> &mdash; Compara el error del modelo contra un baseline naive (repetir el valor de hace 1 ano). Menor a 1 = mejor que el baseline. <em>Metrica principal.</em>
        <br><strong>RMSE</strong> &mdash; Error cuadratico medio. Penaliza errores grandes. Esta en espacio log-tasa, por eso son numeros pequenos (~0.05&ndash;0.2).
        <br><strong>MAE</strong> &mdash; Error absoluto medio. Similar al RMSE pero sin penalizar extremos. Tambien en espacio log-tasa.
        <br><strong>MAPE</strong> &mdash; Error porcentual. Intuitivo (&laquo;el modelo se equivoca X%&raquo;), pero problematico cuando la incidencia es cercana a cero.
        <br><br><em>Nota: RMSE y MAE estan en escala log-tasa (no en casos), por eso sus valores son pequenos.</em></p>
      </div>
      <div class="guide-card" style="border-left-color:var(--burgundy)">
        <h3>Por que MAPE muestra 999%</h3>
        <p>El MAPE se calcula como <strong>|error| / |valor real| &times; 100</strong>. Cuando la incidencia semanal es cercana a cero (comun en Alzheimer y Parkinson estatales), el denominador se acerca a cero y el MAPE explota hacia infinito.
        <br><br>Para evitar valores infinitos, se <strong>capea a 999%</strong>. Esto ocurre en <strong>~44% de los modelos</strong> (138 de 312), principalmente en padecimientos de baja incidencia.
        <br><br>Por esta razon, <strong>MASE es la metrica principal</strong>: no sufre este problema porque compara contra un baseline en vez de dividir por el valor real.</p>
      </div>
    </div>
  </div>
</section>

<!-- ═══ RESUMEN ═══ -->
<section id="resumen">
  <div class="container">
    <h2 class="section-title reveal">Resumen por Padecimiento</h2>
    <p class="section-sub reveal">Desempeno agregado de los modelos Prophet por enfermedad</p>
    <div class="card-grid" id="pad-cards"></div>
    <div class="charts-row">
      <div class="chart-wrap"><canvas id="maseCompareChart"></canvas></div>
      <div class="chart-wrap"><canvas id="doughnutChart"></canvas></div>
    </div>
  </div>
</section>

<!-- ═══ CALIDAD ═══ -->
<section id="calidad" style="background:#fff;padding:4rem 0">
  <div class="container">
    <h2 class="section-title reveal">Distribucion de Calidad</h2>
    <p class="section-sub reveal">Como se distribuyen los modelos segun su MASE — la mayoria estan en rango bueno o excelente</p>
    <div class="chart-wrap"><canvas id="histoChart"></canvas></div>
  </div>
</section>

<!-- ═══ SEXO ═══ -->
<section id="sexo">
  <div class="container">
    <h2 class="section-title reveal">Desglose por Sexo</h2>
    <p class="section-sub reveal">Comparacion de MASE entre modelos generales, masculinos y femeninos. Los modelos &laquo;general&raquo; suelen ser mejores porque tienen mas datos.</p>
    <div class="chart-wrap"><canvas id="sexoChart"></canvas></div>
  </div>
</section>

<!-- ═══ TOP/BOTTOM ═══ -->
<section id="topbottom" style="background:#fff;padding:4rem 0">
  <div class="container">
    <h2 class="section-title reveal">Los 10 Mejores y 10 Peores</h2>
    <p class="section-sub reveal">Modelos con el MASE mas bajo (mejor) y mas alto (peor). CDMX domina los mejores; Estado de Mexico domina los peores.</p>
    <div class="charts-row">
      <div class="chart-wrap"><canvas id="topChart"></canvas></div>
      <div class="chart-wrap"><canvas id="bottomChart"></canvas></div>
    </div>
  </div>
</section>

<!-- ═══ RANKING ═══ -->
<section id="ranking">
  <div class="container">
    <h2 class="section-title reveal">Ranking Completo</h2>
    <p class="section-sub reveal">Los {stats["total_modelos"]} modelos agrupados por nivel: Nacional, Regional y Estatal</p>
    <div class="table-wrapper">
      <div class="table-controls">
        <input type="text" id="searchBox" placeholder="Buscar estado...">
        <select id="filterPad"><option value="">Todos los padecimientos</option></select>
        <select id="filterModo">
          <option value="">Todos los modos</option>
          <option value="General">General</option>
          <option value="Hombres">Hombres</option>
          <option value="Mujeres">Mujeres</option>
        </select>
        <select id="filterGrupo">
          <option value="">Todos los niveles</option>
          <option value="Nacional">Nacional</option>
          <option value="Regional">Regional</option>
          <option value="Estatal">Estatal</option>
        </select>
      </div>
      <div style="overflow-x:auto">
        <table id="rankingTable">
          <thead><tr>
            <th data-col="entidad">Entidad</th>
            <th data-col="padecimiento">Padecimiento</th>
            <th data-col="modo">Modo</th>
            <th data-col="mase">MASE</th>
            <th data-col="rmse">RMSE</th>
            <th data-col="mae">MAE</th>
            <th data-col="tipo">Tipo</th>
            <th data-col="confianza">Confianza</th>
          </tr></thead>
          <tbody id="rankingBody"></tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<!-- ═══ COBERTURA ═══ -->
<section id="cobertura" style="background:#fff;padding:4rem 0">
  <div class="container">
    <h2 class="section-title reveal">Cobertura Geografica</h2>
    <p class="section-sub reveal">Tipo de modelo por estado: <span class="cob-dot propio" style="display:inline-block;vertical-align:middle"></span> Propio (datos suficientes) &nbsp; <span class="cob-dot fallback" style="display:inline-block;vertical-align:middle"></span> Fallback regional (usa modelo de su zona). Orden: Alzheimer, Depresion, Parkinson.</p>
    <div class="cob-summary" id="cobSummary"></div>
    <div class="cob-grid" id="cobGrid"></div>
  </div>
</section>

<!-- ═══ FOOTER ═══ -->
<footer>
  <div class="footer-title">EpiForecast-MX</div>
  <p>Plataforma de inteligencia epidemiologica &middot; IMSS &times; Tec de Monterrey</p>
  <p style="margin-top:.5rem"><a href="index.html">Galeria de Pronosticos (312 graficos)</a></p>
  <p style="margin-top:1rem;opacity:.5">Generado el {stats["fecha"]} con datos 2014-2026</p>
</footer>

<script>
const D = {data_json};

const PC = {{}};
D.pad_meta.forEach(p => {{ PC[p.name] = {{main:p.main,light:p.light,glow:p.glow}}; }});

// Populate filter
const fp = document.getElementById('filterPad');
D.pad_meta.forEach(p => {{ const o=document.createElement('option');o.value=p.name;o.textContent=p.name;fp.appendChild(o); }});

// Reveal
const obs = new IntersectionObserver(es => {{ es.forEach(e => {{ if(e.isIntersecting) e.target.classList.add('visible'); }}); }}, {{threshold:.08}});
document.querySelectorAll('.reveal').forEach(el => obs.observe(el));

/* ── Pad cards ── */
try {{
  const ct = document.getElementById('pad-cards');
  D.por_padecimiento.forEach(p => {{
    const c = PC[p.padecimiento] || {{main:'#333',glow:'rgba(0,0,0,.05)'}};
    const card = document.createElement('div');
    card.className = 'card reveal';
    card.innerHTML = `
      <div class="card-header">
        <span class="card-dot" style="color:${{c.main}};background:${{c.main}}"></span>
        <span class="card-title">${{p.padecimiento}}</span>
      </div>
      <div class="card-metrics">
        <div class="metric"><div class="metric-value">${{p.total}}</div><div class="metric-label">Modelos</div></div>
        <div class="metric" style="background:${{c.glow}}"><div class="metric-value" style="color:${{c.main}}">${{p.mase}}</div><div class="metric-label">MASE Medio</div></div>
        <div class="metric"><div class="metric-value">${{p.mase_min}} – ${{p.mase_max}}</div><div class="metric-label">MASE Rango</div></div>
        <div class="metric"><div class="metric-value">${{p.rmse}}</div><div class="metric-label">RMSE Medio</div></div>
        <div class="metric"><div class="metric-value">${{p.mae}}</div><div class="metric-label">MAE Medio</div></div>
        <div class="metric"><div class="metric-value">${{p.mape != null && p.mape >= 999 ? p.mape + '% \\u26A0' : (p.mape != null ? p.mape + '%' : '—')}}</div><div class="metric-label">${{p.mape != null && p.mape >= 999 ? '<span title="Capeado por incidencia cercana a cero">MAPE Medio \\u26A0</span>' : 'MAPE Medio'}}</div></div>
        <div class="metric"><div class="metric-value">${{p.insuficientes}}</div><div class="metric-label">Insuficientes</div></div>
        <div class="metric"><div class="metric-value">${{p.fallback}}</div><div class="metric-label">Fallback Regional</div></div>
      </div>`;
    ct.appendChild(card);
    obs.observe(card);
  }});
}} catch(e) {{ console.warn('cards:', e); }}

/* ── MASE comparison bar ── */
try {{
  const pads = D.por_padecimiento;
  new Chart(document.getElementById('maseCompareChart'), {{
    type: 'bar',
    data: {{
      labels: pads.map(p => p.padecimiento),
      datasets: [
        {{ label:'MASE Medio', data:pads.map(p=>p.mase), backgroundColor:pads.map(p=>PC[p.padecimiento].main), borderRadius:6, borderSkipped:false }},
        {{ label:'MASE Mediana', data:pads.map(p=>p.mase_median), backgroundColor:pads.map(p=>PC[p.padecimiento].light), borderRadius:6, borderSkipped:false }}
      ]
    }},
    options: {{
      responsive:true, indexAxis:'y',
      plugins: {{
        title: {{ display:true, text:'MASE por Padecimiento (media vs mediana)', font:{{ family:"'Source Sans 3'", size:14 }} }},
        legend: {{ position:'bottom', labels:{{ font:{{ family:"'Source Sans 3'" }} }} }}
      }},
      scales: {{
        x: {{ beginAtZero:true, max:1.2, grid:{{ color:'rgba(0,0,0,.06)' }},
          title:{{ display:true, text:'MASE (menor = mejor)', font:{{ family:"'Source Sans 3'" }} }} }},
        y: {{ grid:{{ display:false }} }}
      }}
    }}
  }});
}} catch(e) {{ console.warn('maseCompare:', e); }}

/* ── Doughnut: propio vs fallback ── */
try {{
  const pads = D.por_padecimiento;
  const propios = pads.map(p => p.estatales - p.fallback);
  const fallbacks = pads.map(p => p.fallback);
  new Chart(document.getElementById('doughnutChart'), {{
    type: 'doughnut',
    data: {{
      labels: ['Modelo propio', 'Fallback regional'],
      datasets: pads.map((p, i) => ({{
        label: p.padecimiento,
        data: [propios[i], fallbacks[i]],
        backgroundColor: ['#1a7431', '#c2590a'],
        borderWidth: 2, borderColor: '#fff'
      }}))
    }},
    options: {{
      responsive: true,
      plugins: {{
        title: {{ display:true, text:'Modelos Propios vs Fallback (estatales)', font:{{ family:"'Source Sans 3'", size:14 }} }},
        legend: {{ position:'bottom', labels:{{ font:{{ family:"'Source Sans 3'" }} }} }},
        tooltip: {{ callbacks: {{ label: ctx => {{
          const ds = ctx.dataset;
          const total = ds.data.reduce((a,b)=>a+b,0);
          const pct = total ? Math.round(ctx.parsed / total * 100) : 0;
          return `${{ctx.label}}: ${{ctx.parsed}} (${{pct}}%)`;
        }} }} }}
      }}
    }}
  }});
}} catch(e) {{ console.warn('doughnut:', e); }}

/* ── MASE histogram ── */
try {{
  const binColors = ['#1a7431','#4ade80','#facc15','#f97316','#b91c1c'];
  new Chart(document.getElementById('histoChart'), {{
    type: 'bar',
    data: {{
      labels: D.mase_bin_labels,
      datasets: D.mase_histo.map(h => ({{
        label: h.padecimiento,
        data: h.bins,
        backgroundColor: PC[h.padecimiento].main,
        borderRadius: 4, borderSkipped: false
      }}))
    }},
    options: {{
      responsive: true,
      plugins: {{
        title: {{ display:true, text:'Cuantos modelos hay en cada rango de MASE', font:{{ family:"'Source Sans 3'", size:14 }} }},
        legend: {{ position:'bottom', labels:{{ font:{{ family:"'Source Sans 3'" }} }} }}
      }},
      scales: {{
        y: {{ beginAtZero:true, title:{{ display:true, text:'Numero de modelos', font:{{ family:"'Source Sans 3'" }} }}, grid:{{ color:'rgba(0,0,0,.06)' }} }},
        x: {{ grid:{{ display:false }}, title:{{ display:true, text:'Rango de MASE', font:{{ family:"'Source Sans 3'" }} }} }}
      }}
    }}
  }});
}} catch(e) {{ console.warn('histo:', e); }}

/* ── Sexo chart ── */
try {{
  const pads = D.pad_meta.map(p=>p.name);
  const modos = ['general','hombres','mujeres'];
  const ml = {{general:'General',hombres:'Hombres',mujeres:'Mujeres'}};
  const mc = {{general:'#97999B',hombres:'#00524E',mujeres:'#9B2242'}};
  const ds = modos.map(m => ({{
    label: ml[m],
    data: pads.map(pad => {{ const f=D.por_sexo.find(s=>s.padecimiento===pad&&s.modo===m); return f?f.mase:0; }}),
    backgroundColor: mc[m], borderRadius:6, borderSkipped:false
  }}));
  new Chart(document.getElementById('sexoChart'), {{
    type:'bar', data:{{labels:pads,datasets:ds}},
    options: {{
      responsive:true,
      plugins: {{
        title:{{ display:true, text:'MASE por Sexo y Padecimiento', font:{{ family:"'Source Sans 3'", size:14 }} }},
        legend:{{ position:'bottom', labels:{{ font:{{ family:"'Source Sans 3'" }} }} }},
        tooltip:{{ callbacks:{{ label: ctx=>`${{ctx.dataset.label}}: MASE ${{ctx.parsed.y}}` }} }}
      }},
      scales: {{
        y:{{ beginAtZero:true, title:{{ display:true, text:'MASE', font:{{ family:"'Source Sans 3'" }} }}, grid:{{ color:'rgba(0,0,0,.06)' }} }},
        x:{{ grid:{{ display:false }} }}
      }}
    }}
  }});
}} catch(e) {{ console.warn('sexo:', e); }}

/* ── Top/Bottom horizontal bars ── */
try {{
  function hbar(id, items, title, colorFn) {{
    const labels = items.map(i=>i.label.length>35 ? i.label.substring(0,35)+'...' : i.label);
    new Chart(document.getElementById(id), {{
      type:'bar',
      data: {{
        labels,
        datasets: [{{ data:items.map(i=>i.mase), backgroundColor:items.map(i => {{
          const c = PC[i.padecimiento]; return c ? c.main : '#999';
        }}), borderRadius:4, borderSkipped:false }}]
      }},
      options: {{
        indexAxis:'y', responsive:true,
        plugins: {{
          title:{{ display:true, text:title, font:{{ family:"'Source Sans 3'", size:14 }} }},
          legend:{{ display:false }},
          tooltip:{{ callbacks:{{ label:ctx=>'MASE: '+ctx.parsed.x }} }}
        }},
        scales: {{
          x: {{ beginAtZero:true, grid:{{ color:'rgba(0,0,0,.06)' }} }},
          y: {{ grid:{{ display:false }}, ticks:{{ font:{{ size:11, family:"'Source Sans 3'" }} }} }}
        }}
      }}
    }});
  }}
  hbar('topChart', D.top10, 'Top 10 — Mejor MASE');
  hbar('bottomChart', D.bottom10, 'Bottom 10 — Mayor MASE');
}} catch(e) {{ console.warn('topbottom:', e); }}

/* ── Ranking table ── */
try {{
  const tbody = document.getElementById('rankingBody');
  let rows = D.ranking;
  let sortCol = 'orden'; let sortAsc = true;

  function maseBadge(v) {{
    if(v==null) return '<span class="badge badge-yellow">N/A</span>';
    const cls = v<0.7?'badge-green':v<=1.0?'badge-yellow':'badge-red';
    return `<span class="badge ${{cls}}">${{v}}</span>`;
  }}
  function tipoBadge(t) {{
    return `<span class="badge-tipo ${{t==='Propio'?'badge-propio':'badge-fallback'}}">${{t}}</span>`;
  }}

  function render(data) {{
    // Group by grupo
    const groups = {{}};
    const groupOrder = ['Nacional','Regional','Estatal'];
    const groupLabels = {{
      'Nacional': 'Nacional (modelos con todos los datos del pais)',
      'Regional': 'Regional (modelos por region INEGI de salud mental)',
      'Estatal': 'Estatal (modelos por estado — 32 entidades)'
    }};
    data.forEach(r => {{
      if(!groups[r.grupo]) groups[r.grupo] = [];
      groups[r.grupo].push(r);
    }});

    let html = '';
    groupOrder.forEach(g => {{
      const items = groups[g];
      if(!items || items.length===0) return;
      html += `<tr class="group-header"><td colspan="8">${{groupLabels[g] || g}} (${{items.length}})</td></tr>`;
      items.forEach(r => {{
        html += `<tr>
          <td style="font-weight:600">${{r.entidad}}</td>
          <td><span style="color:${{PC[r.padecimiento]?.main||'#333'}}">${{r.padecimiento}}</span></td>
          <td>${{r.modo}}</td>
          <td>${{maseBadge(r.mase)}}</td>
          <td style="font-family:var(--font-mono)">${{r.rmse ?? '—'}}</td>
          <td style="font-family:var(--font-mono)">${{r.mae ?? '—'}}</td>
          <td>${{tipoBadge(r.tipo)}}</td>
          <td>${{r.confianza}}</td>
        </tr>`;
      }});
    }});
    tbody.innerHTML = html;
  }}

  function filterAndSort() {{
    const q = document.getElementById('searchBox').value.toLowerCase();
    const padF = document.getElementById('filterPad').value;
    const modoF = document.getElementById('filterModo').value;
    const grupoF = document.getElementById('filterGrupo').value;
    let filtered = rows.filter(r => {{
      if(q && !r.entidad.toLowerCase().includes(q)) return false;
      if(padF && r.padecimiento!==padF) return false;
      if(modoF && r.modo!==modoF) return false;
      if(grupoF && r.grupo!==grupoF) return false;
      return true;
    }});
    filtered.sort((a,b) => {{
      let va=a[sortCol],vb=b[sortCol];
      if(va==null)va=999;if(vb==null)vb=999;
      if(typeof va==='string'){{va=va.toLowerCase();vb=(vb||'').toLowerCase();}}
      return sortAsc?(va<vb?-1:va>vb?1:0):(va>vb?-1:va<vb?1:0);
    }});
    render(filtered);
  }}

  document.getElementById('searchBox').addEventListener('input', filterAndSort);
  document.getElementById('filterPad').addEventListener('change', filterAndSort);
  document.getElementById('filterModo').addEventListener('change', filterAndSort);
  document.getElementById('filterGrupo').addEventListener('change', filterAndSort);

  document.querySelectorAll('#rankingTable thead th').forEach(th => {{
    th.addEventListener('click', () => {{
      const col = th.dataset.col;
      if(sortCol===col) sortAsc=!sortAsc; else {{ sortCol=col; sortAsc=true; }}
      document.querySelectorAll('#rankingTable thead th').forEach(t=>t.classList.remove('sorted-asc','sorted-desc'));
      th.classList.add(sortAsc?'sorted-asc':'sorted-desc');
      filterAndSort();
    }});
  }});
  filterAndSort();
}} catch(e) {{ console.warn('ranking:', e); }}

/* ── Cobertura ── */
try {{
  const grid = document.getElementById('cobGrid');
  const summary = document.getElementById('cobSummary');
  const padKeys = D.pad_meta.map(p=>p.key);
  const padLabels = {{}}; D.pad_meta.forEach(p=>{{padLabels[p.key]=p.name;}});

  padKeys.forEach(pk => {{
    const res = D.cobertura_resumen[pk];
    const c = PC[padLabels[pk]];
    summary.innerHTML += `<div class="cob-summary-item">
      <span class="cob-dot propio"></span>
      <span style="color:${{c.main}};font-weight:600">${{padLabels[pk]}}</span>
      ${{res.propios}} propios, ${{res.fallback}} fallback
    </div>`;
  }});

  D.cobertura.forEach(item => {{
    const div = document.createElement('div');
    div.className = 'cob-item';
    const dots = padKeys.map(pk=>`<span class="cob-dot ${{item[pk]}}" title="${{padLabels[pk]}}: ${{item[pk]}}"></span>`).join('');
    div.innerHTML = `<span class="estado-name">${{item.estado}}</span>${{dots}}`;
    grid.appendChild(div);
  }});
}} catch(e) {{ console.warn('cobertura:', e); }}

/* ── Smooth scroll ── */
document.querySelectorAll('nav a[href^="#"]').forEach(a => {{
  a.addEventListener('click', e => {{
    e.preventDefault();
    const el = document.querySelector(a.getAttribute('href'));
    if(el) el.scrollIntoView({{ behavior:'smooth' }});
  }});
}});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f">>> Leyendo {FORECAST_CSV}...")
    df = load_and_deduplicate(FORECAST_CSV)
    print(f"    {len(df)} modelos unicos encontrados.")

    print(">>> Calculando estadisticas...")
    stats = compute_stats(df)

    print(">>> Generando reporte HTML...")
    html = build_html(stats)

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f">>> Reporte generado: {OUTPUT_HTML}")
    print(f"    Abrir con: open {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
