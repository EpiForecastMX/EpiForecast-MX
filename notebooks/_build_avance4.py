#!/usr/bin/env python3
"""Genera Avance4.Equipo01.ipynb — notebook de maestria nivel profesional.

Uso:
    python notebooks/_build_avance4.py

Genera el notebook completo en notebooks/Avance4.Equipo01.ipynb
con ~67 celdas, ~24 figuras, paleta IMSS y ortografia impecable.
"""

import json
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes de estilo
# ---------------------------------------------------------------------------
DIV = (
    '<div style="background: linear-gradient(90deg, #003A70, #006847); '
    'height: 3px; margin: 30px 0 15px; border-radius: 2px;"></div>'
)

GREEN_BOX = (
    '<div style="background: #E8F5E9; border-left: 4px solid #006847; '
    'padding: 14px 18px; margin: 12px 0; border-radius: 0 4px 4px 0;">'
)
BLUE_BOX = (
    '<div style="background: #E3F2FD; border-left: 4px solid #003A70; '
    'padding: 14px 18px; margin: 12px 0; border-radius: 0 4px 4px 0;">'
)
GOLD_BOX = (
    '<div style="background: #FFF3CD; border-left: 4px solid #B58500; '
    'padding: 14px 18px; margin: 12px 0; border-radius: 0 4px 4px 0;">'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _src(text):
    """Convierte texto a formato source de notebook (lista de strings)."""
    text = text.strip("\n")
    if not text:
        return [""]
    lines = text.split("\n")
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


def _id():
    """Genera un ID unico para celda (nbformat 5)."""
    return uuid.uuid4().hex[:8]


def md(source):
    """Crea celda markdown."""
    return {"cell_type": "markdown", "id": _id(), "metadata": {}, "source": _src(source)}


def code(source):
    """Crea celda de codigo."""
    return {
        "cell_type": "code",
        "id": _id(),
        "metadata": {},
        "source": _src(source),
        "outputs": [],
        "execution_count": None,
    }


def sec(num, title):
    """Header de seccion con divider y ancla."""
    return f"{DIV}\n\n## {num}. {title} <a id=\"sec{num}\"></a>"


# ---------------------------------------------------------------------------
# Acto 0 — Portada + Configuracion (celdas 0-5)
# ---------------------------------------------------------------------------
def acto_0():
    cells = []

    # --- Celda 0: Portada HTML ---
    cells.append(md("""\
<div style="background: linear-gradient(135deg, #003A70 0%, #004E8C 40%, #006847 100%);
border-radius: 12px; padding: 50px 40px 40px; margin: 0 0 30px;
color: white; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.15);">

<div style="font-size: 0.85em; letter-spacing: 4px; text-transform: uppercase;
color: rgba(255,255,255,0.7); margin-bottom: 10px;">Proyecto Integrador</div>

<h1 style="font-size: 3em; font-weight: 800; color: white; margin: 0 0 5px;
letter-spacing: 1px;">EpiForecast-MX</h1>

<div style="width: 80px; height: 3px; background: #9B2242; margin: 15px auto; border-radius: 2px;"></div>

<h2 style="font-size: 1.4em; font-weight: 400; color: rgba(255,255,255,0.95);
margin: 15px 0 25px;">Avance 4: Modelos Alternativos y Selecci&oacute;n del Modelo Final</h2>

<div style="display: inline-block; background: rgba(255,255,255,0.12);
border-radius: 8px; padding: 10px 28px; margin: 0 0 25px;">
<span style="font-size: 1.05em; color: rgba(255,255,255,0.95); letter-spacing: 1px;">
Depresi&oacute;n [F32] &middot; Parkinson [G20] &middot; Alzheimer [G30]</span>
</div>

<p style="font-size: 1.05em; color: rgba(255,255,255,0.85); margin: 0 0 5px;">
<strong>Maestr&iacute;a en Inteligencia Artificial Aplicada</strong></p>
<p style="font-size: 0.95em; color: rgba(255,255,255,0.7); margin: 0 0 30px;">
Tecnol&oacute;gico de Monterrey &mdash; TC5035</p>

<table style="margin: 0 auto 25px; border-collapse: collapse; font-size: 0.95em;
min-width: 340px;">
<tr style="border-bottom: 2px solid rgba(255,255,255,0.3);">
  <th style="padding: 10px 20px; text-align: left; color: rgba(255,255,255,0.8);
font-weight: 600; letter-spacing: 1px; text-transform: uppercase; font-size: 0.8em;">Integrante</th>
  <th style="padding: 10px 20px; text-align: left; color: rgba(255,255,255,0.8);
font-weight: 600; letter-spacing: 1px; text-transform: uppercase; font-size: 0.8em;">Afiliaci&oacute;n</th>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 8px 20px; color: white;">Javier Rebull</td>
<td style="padding: 8px 20px; color: rgba(255,255,255,0.8);">Tec / Santander US</td></tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 8px 20px; color: white;">Juan Carlos P&eacute;rez Nava</td>
<td style="padding: 8px 20px; color: rgba(255,255,255,0.8);">Tec / IMSS</td></tr>
<tr>
<td style="padding: 8px 20px; color: white;">Luis S&aacute;nchez</td>
<td style="padding: 8px 20px; color: rgba(255,255,255,0.8);">Tec / Tesla</td></tr>
</table>

<p style="color: rgba(255,255,255,0.5); font-size: 0.85em; margin: 0;">
Equipo 01 &middot; Febrero 2026</p>

</div>"""))

    # --- Celda 1: Tabla de contenidos ---
    cells.append(md("""\
### Contenido

| # | Secci&oacute;n | Figuras |
|---|---------|---------|
| 1 | [Contexto del proyecto](#sec1) | &mdash; |
| 2 | [Recorrido de optimizaci&oacute;n: v1 a v6](#sec2) | Fig 1 |
| 3 | [Metodolog&iacute;a Prophet](#sec3) | Fig 2 |
| 4 | [Resultados de producci&oacute;n: 312 modelos](#sec4) | Fig 3-5 |
| 5 | [Galer&iacute;a de pron&oacute;sticos](#sec5) | Fig 6-9 |
| 6 | [Benchmark SageMaker: 6 algoritmos](#sec6) | Fig 10-13 |
| 7 | [An&aacute;lisis por padecimiento](#sec7) | Fig 14-15 |
| 8 | [An&aacute;lisis por sexo](#sec8) | Fig 16 |
| 9 | [Predicciones cara a cara](#sec9) | Fig 17-18 |
| 10 | [Selecci&oacute;n del modelo final](#sec10) | Fig 19-20 |
| 11 | [Dashboard Tableau](#sec11) | &mdash; |
| 12 | [Publicaci&oacute;n acad&eacute;mica](#sec12) | &mdash; |
| 13 | [Conclusiones](#sec13) | &mdash; |
| 14 | [Reflexiones del equipo](#sec14) | &mdash; |
| 15 | [Referencias y enlaces](#sec15) | &mdash; |
| A | [Ap&eacute;ndice: Ficha T&eacute;cnica de Prophet](#secA) | Fig A1-A3 |"""))

    # --- Celda 2: Imports ---
    cells.append(code("""\
%matplotlib inline
import warnings
warnings.filterwarnings('ignore')

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import seaborn as sns
from PIL import Image
import yaml"""))

    # --- Celda 3: Config y paleta IMSS ---
    cells.append(code("""\
# --- Cargar paleta IMSS desde config/reportes.yaml ---
with open('../config/reportes.yaml') as f:
    _cfg = yaml.safe_load(f)

IMSS = _cfg['IMSS_COLORS']

PAD_COLORS = {
    'Depresi\u00f3n': _cfg['PALETTE_PADECIMIENTO']['Depresion']['c1'],
    'Alzheimer': _cfg['PALETTE_PADECIMIENTO']['Alzheimer']['c1'],
    'Parkinson': _cfg['PALETTE_PADECIMIENTO']['Parkinson']['c1'],
}
PAD_COLORS_LIGHT = {
    'Depresi\u00f3n': _cfg['PALETTE_PADECIMIENTO']['Depresion']['cl'],
    'Alzheimer': _cfg['PALETTE_PADECIMIENTO']['Alzheimer']['cl'],
    'Parkinson': _cfg['PALETTE_PADECIMIENTO']['Parkinson']['cl'],
}
PAD_ORDER = ['Depresi\u00f3n', 'Alzheimer', 'Parkinson']

SEX_COLORS = _cfg['PALETTE_SEXO']

MODEL_COLORS = {
    'Prophet': IMSS['teal'],
    'DeepAR': IMSS['burgundy'],
    'LightGBM+LSTM': IMSS['gold'],
    'TFT': IMSS['dark_burgundy'],
    'Ridge': IMSS['cool_gray'],
    'XGBoost': IMSS['dark_teal'],
}
MODEL_ORDER = ['Prophet', 'DeepAR', 'LightGBM+LSTM', 'TFT', 'Ridge', 'XGBoost']

# Aplicar rcParams IMSS
for k, v in _cfg['matplotlib_rcParams'].items():
    plt.rcParams[k] = v
plt.rcParams['figure.figsize'] = (12, 5)

print('Paleta IMSS cargada correctamente.')"""))

    # --- Celda 4: Rutas y helper save_fig ---
    cells.append(code("""\
ROOT = Path('..')
SAGEMAKER = ROOT / 'Sagemaker results-v5-full'
FIGDIR = Path('figuras_avance4')
FIGDIR.mkdir(exist_ok=True)
FORECAST_DIR = ROOT / 'forecast'
PRED_DIR = SAGEMAKER / 'experiments' / 'predicciones'

ESTADOS_32 = [
    'Aguascalientes', 'Baja California', 'Baja California Sur', 'Campeche',
    'Chiapas', 'Chihuahua', 'Ciudad de M\u00e9xico', 'Coahuila',
    'Colima', 'Durango', 'Guanajuato', 'Guerrero',
    'Hidalgo', 'Jalisco', 'Michoac\u00e1n', 'Morelos',
    'M\u00e9xico', 'Nayarit', 'Nuevo Le\u00f3n', 'Oaxaca',
    'Puebla', 'Quer\u00e9taro', 'Quintana Roo', 'San Luis Potos\u00ed',
    'Sinaloa', 'Sonora', 'Tabasco', 'Tamaulipas',
    'Tlaxcala', 'Veracruz', 'Yucat\u00e1n', 'Zacatecas',
]

def save_fig(fig, name, dpi=150):
    path = FIGDIR / f'{name}.png'
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.show()
    plt.close(fig)
    print(f'  Guardado: {path}')

print(f'Directorio de figuras: {FIGDIR.resolve()}')"""))

    # --- Celda 5: Carga de datos unificada ---
    cells.append(code("""\
# === Carga unificada de todos los datos ===

# --- 1. Prophet completo (3 padecimientos) ---
_sex_map = {
    'incrementos_total': 'general',
    'incrementos_hombres': 'hombres',
    'incrementos_mujeres': 'mujeres',
}
dfs = []
for _pad in ['Alzheimer', 'Depresion', 'Parkinson']:
    _df = pd.read_csv(ROOT / f'models/{_pad}/Prophet_{_pad}_completo.csv')
    dfs.append(_df)
df_prophet = pd.concat(dfs, ignore_index=True)
df_prophet['sexo'] = df_prophet['sexo'].map(_sex_map)

# Clasificar nivel real: nacional / estatal / regional_fallback
# En el CSV: nivel=nacional (3 nac), nivel=regional (estados + regiones reales)
# Regiones reales tienen Entidad que empieza con 'region_'
def _classify(row):
    if row['nivel'] == 'nacional':
        return 'nacional'
    if pd.notna(row.get('Entidad')) and str(row['Entidad']).startswith('region_'):
        return 'regional'
    return 'estatal'
df_prophet['_nivel'] = df_prophet.apply(_classify, axis=1)

# --- 2. SageMaker Excel (7 hojas) ---
_XL = SAGEMAKER / 'EpiForecast_v5_full_Analisis.xlsx'
df_raw_sm = pd.read_excel(_XL, sheet_name='Raw Results')
df_ganadores = pd.read_excel(_XL, sheet_name='Ganadores por Serie')
df_mase_modelo = pd.read_excel(_XL, sheet_name='MASE por Modelo')
df_top3 = pd.read_excel(_XL, sheet_name='Top 3 por Serie')
df_prophet_hp = pd.read_excel(_XL, sheet_name='Prophet HPs')
df_sexo_sm = pd.read_excel(_XL, sheet_name='An\u00e1lisis por Sexo')
df_omitidas = pd.read_excel(_XL, sheet_name='Series Omitidas')

# --- 3. HP optimos JSON ---
with open(SAGEMAKER / 'hp_optimos_v5_full.json') as f:
    hp_optimos = json.load(f)

print(f'Prophet completo: {len(df_prophet)} filas')
print(f'  - Estatales: {(df_prophet["_nivel"] == "estatal").sum()}')
print(f'  - Nacionales: {(df_prophet["_nivel"] == "nacional").sum()}')
print(f'  - Regionales: {(df_prophet["_nivel"] == "regional").sum()}')
print(f'SageMaker raw: {len(df_raw_sm)} trials')
print(f'Ganadores: {len(df_ganadores)} series')
print(f'HP \u00f3ptimos: {len(hp_optimos["series"])} series')"""))

    return cells


# ---------------------------------------------------------------------------
# Acto 1 — Contexto y recorrido (celdas 6-14)
# ---------------------------------------------------------------------------
def acto_1():
    cells = []

    # --- Celda 6: Sec 1. Contexto ---
    cells.append(md(f"""\
{sec(1, 'Contexto del proyecto')}

**EpiForecast-MX** es una plataforma de inteligencia epidemiol\u00f3gica desarrollada en colaboraci\u00f3n con el
**Instituto Mexicano del Seguro Social (IMSS)** como proyecto Capstone de la Maestr\u00eda en Inteligencia
Artificial Aplicada del Tecnol\u00f3gico de Monterrey.

Predice la incidencia semanal de tres padecimientos neurol\u00f3gicos y de salud mental:

- **Depresi\u00f3n** (CIE-10: F32) \u2014 el padecimiento con mayor incidencia y variabilidad
- **Parkinson** (CIE-10: G20) \u2014 incidencia intermedia, patrones estacionales claros
- **Alzheimer** (CIE-10: G30) \u2014 menor incidencia, muchos estados con datos insuficientes

Los datos provienen del **SINAVE** (Sistema Nacional de Vigilancia Epidemiol\u00f3gica), con 633 boletines
epidemiol\u00f3gicos semanales de 2014 a 2026, complementados con indicadores demogr\u00e1ficos del INEGI."""))

    # --- Celda 7: Cifras clave ---
    cells.append(md("""\
### Cifras clave del proyecto

| Concepto | Valor |
|----------|-------|
| Boletines procesados | 633 PDFs (2014-2026) |
| Entidades federativas | 32 estados |
| Padecimientos | 3 (Depresi\u00f3n, Parkinson, Alzheimer) |
| Segmentaciones por sexo | 3 (general, hombres, mujeres) |
| Series de tiempo | 258 evaluadas + 39 omitidas |
| Modelos Prophet (v6) | 312 (297 estatales + 15 regionales) |
| Modelos SageMaker | 1,548 trials (6 algoritmos) |
| M\u00e9trica principal | MASE (Mean Absolute Scaled Error) |"""))

    # --- Celda 8: Sec 2. Recorrido v1-v6 ---
    cells.append(md(f"""\
{sec(2, 'Recorrido de optimizaci\u00f3n: v1 a v6')}

Evoluci\u00f3n del pipeline Prophet a lo largo de seis versiones, desde el baseline con par\u00e1metros
default hasta el modelo h\u00edbrido con fallback regional."""))

    # --- Celda 9: Tabla de versiones ---
    cells.append(md("""\
### Tabla comparativa de versiones

| Versi\u00f3n | Cambio principal | Modelos | MASE medio | Tiempo | Mejora |
|:---------|:----------------|:--------|:-----------|:-------|:-------|
| **v1** | Baseline Prophet, par\u00e1metros default | 9 (3 nac.) | ~1.10 | ~5 min | \u2014 |
| **v2** | Grid search HP, CV temporal | 9 (3 nac.) | ~0.85 | ~20 min | -23% MASE |
| **v3** | 99 modelos estatales (32 x 3 + 3 nac.) | 99 | ~0.82 | ~3 h | Cobertura estatal |
| **v4** | Grid refinado por padecimiento, 297 modelos (3 modos) | 297 | ~0.78 | ~6 h | -5% MASE |
| **v5** | Anti-Newton, grids v5, poda de combinaciones | 297 | ~0.76 | ~45 min | -92% tiempo |
| **v6** | MASE, modo h\u00edbrido, fallback regional | 312 | ~0.76 | ~45 min | 100% cobertura |

**Hitos clave:**
- **v3:** Primera cobertura estatal completa (32 entidades). Entrenamiento de 3 horas por procesamiento secuencial.
- **v4:** Triplicaci\u00f3n de modelos (general + hombres + mujeres). Grid diferenciado por padecimiento basado en an\u00e1lisis de 297 modelos v3.
- **v5:** Reducci\u00f3n de 92% en tiempo de entrenamiento gracias a protecci\u00f3n anti-Newton y paralelizaci\u00f3n con joblib.
- **v6:** 100% de cobertura estatal con predicci\u00f3n informada (41 modelos insuficientes usan fallback regional)."""))

    # --- Celda 10: Fig 1 — Timeline v1-v6 ---
    cells.append(code("""\
# --- Fig 1: Timeline v1 a v6 (step chart con doble eje) ---
versions = ['v1', 'v2', 'v3', 'v4', 'v5', 'v6']
mase_vals = [1.10, 0.85, 0.82, 0.78, 0.76, 0.76]
time_vals = [5, 20, 180, 360, 45, 45]  # minutos
models_n = [9, 9, 99, 297, 297, 312]

fig, ax1 = plt.subplots(figsize=(11, 5))
ax2 = ax1.twinx()

# MASE (eje izquierdo)
ax1.step(versions, mase_vals, where='mid', color=IMSS['teal'], lw=2.5, zorder=3)
ax1.scatter(versions, mase_vals, color=IMSS['teal'], s=90, zorder=4)
ax1.set_ylabel('MASE medio', color=IMSS['teal'], fontsize=12)
ax1.set_ylim(0.5, 1.25)
ax1.tick_params(axis='y', labelcolor=IMSS['teal'])

# Tiempo (eje derecho)
ax2.step(versions, time_vals, where='mid', color=IMSS['burgundy'], lw=2.5,
         ls='--', zorder=3)
ax2.scatter(versions, time_vals, color=IMSS['burgundy'], s=90, zorder=4, marker='s')
ax2.set_ylabel('Tiempo (minutos)', color=IMSS['burgundy'], fontsize=12)
ax2.tick_params(axis='y', labelcolor=IMSS['burgundy'])

# Linea MASE=1.0 (naive)
ax1.axhline(y=1.0, color=IMSS['cool_gray'], ls=':', alpha=0.6)
ax1.text(5.15, 1.01, 'MASE = 1.0 (naive)', color=IMSS['cool_gray'],
         fontsize=9, va='bottom')

# Anotaciones de numero de modelos
for i, (v, n) in enumerate(zip(versions, models_n)):
    ax1.annotate(f'{n} mod.', (i, mase_vals[i]),
                 textcoords='offset points', xytext=(0, 14),
                 ha='center', fontsize=8.5, color=IMSS['neutral_black'])

ax1.set_title('Fig 1. Evoluci\u00f3n del pipeline Prophet: v1 a v6',
              fontsize=14, pad=15)
ax1.set_xlabel('Versi\u00f3n')

# Leyenda combinada
h1 = Line2D([0], [0], color=IMSS['teal'], lw=2.5, label='MASE medio')
h2 = Line2D([0], [0], color=IMSS['burgundy'], lw=2.5, ls='--',
            marker='s', label='Tiempo (min)')
ax1.legend(handles=[h1, h2], loc='upper right', framealpha=0.9)

fig.tight_layout()
save_fig(fig, 'fig01_timeline_v1_v6')"""))

    # --- Celda 11: Sec 3. Metodologia ---
    cells.append(md(f"""\
{sec(3, 'Metodolog\u00eda Prophet')}

Facebook Prophet descompone cada serie de tiempo en tendencia, estacionalidad y eventos at\u00edpicos.
El pipeline aplica tres transformaciones secuenciales antes de entrenar:

1. **Normalizaci\u00f3n a tasa por 100,000 habitantes:** `y_tasa = (incidencia / poblaci\u00f3n) x 100,000`
2. **Log-transform:** `y = log(1 + y_tasa)` \u2014 estabiliza varianza en series vol\u00e1tiles
3. **Prophet entrena sobre `y`** (espacio log-tasa)

Al predecir, se revierten ambas transformaciones: `exp(y_hat) - 1` \u2192 desnormaliza a conteos."""))

    # --- Celda 12: Tabla metricas + umbrales ---
    cells.append(md("""\
### M\u00e9tricas de evaluaci\u00f3n y umbrales

| M\u00e9trica | F\u00f3rmula | Interpretaci\u00f3n |
|---------|---------|----------------|
| **RMSE** | \u221a(mean(e\u00b2)) | Error cuadr\u00e1tico medio \u2014 penaliza errores grandes |
| **MAE** | mean(\\|e\\|) | Error absoluto medio \u2014 robusto a outliers |
| **MAPE** | mean(\\|e/y\\|) x 100 | Error porcentual \u2014 no confiable si y \u2248 0 |
| **MASE** | MAE / MAE_naive(lag-52) | Escala-independiente \u2014 < 1.0 = supera baseline naive |

### Umbrales de desempe\u00f1o

| Nivel | MASE | Interpretaci\u00f3n |
|-------|------|----------------|
| Excelente | < 0.75 | Supera significativamente al naive estacional |
| Bueno | 0.75 \u2013 1.00 | Mejor que el naive estacional |
| Requiere mejora | > 1.00 | No supera al baseline naive |

### Cross-validation temporal

- **4 folds** con horizonte de 53 semanas (1 a\u00f1o)
- **Pesos progresivos:** `[0.5, 0.75, 1.0, 1.25]` \u2014 m\u00e1s peso a folds recientes (2023-2024)
- **Fecha de corte:** 2025-01-01"""))

    # --- Celda 13: Grids HP por padecimiento ---
    cells.append(md("""\
### Grids de hiperpar\u00e1metros por padecimiento (v5)

Grids diferenciados optimizados con datos de 297 modelos v4:

| Padecimiento | Combos | `seasonality_mode` | `changepoint_prior_scale` | `seasonality_prior_scale` |
|:-------------|:-------|:-------------------|:--------------------------|:--------------------------|
| **Alzheimer** | 6 | multiplicative | 0.01, 0.03 | 0.05, 0.1, 0.5 |
| **Depresi\u00f3n** | 24 | additive, multiplicative | 0.01, 0.03, 0.05 | 0.025, 0.05, 0.1, 0.5 |
| **Parkinson** | 18 | multiplicative, additive | 0.03, 0.04, 0.05 | 0.1, 0.5, 1.0 |

**Par\u00e1metros regionales** (modelos estatales):
- `fourier_order`: 3 (vs 5 nacional) \u2014 reduce overfitting
- `n_changepoints`: 12 (vs 25 default) \u2014 adecuado para series cortas"""))

    # --- Celda 14: Fig 2 — Heatmap HP por padecimiento ---
    cells.append(code("""\
# --- Fig 2: Heatmap de hiperparametros ganadores por padecimiento ---
# Fuente: modelos estatales con confianza normal del Prophet completo
df_hp = df_prophet[
    (df_prophet['_nivel'] == 'estatal') &
    (df_prophet['confianza'] == 'normal')
].copy()

fig, axes = plt.subplots(1, 3, figsize=(16, 5))
for ax, pad in zip(axes, PAD_ORDER):
    sub = df_hp[df_hp['padecimiento'] == pad]
    if len(sub) == 0:
        ax.set_title(pad, fontweight='bold')
        ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center', transform=ax.transAxes)
        continue
    pivot = (sub.groupby(['changepoint_prior_scale', 'seasonality_prior_scale'])
                .size().unstack(fill_value=0))
    sns.heatmap(pivot, annot=True, fmt='d', cmap='YlOrRd', ax=ax,
                cbar_kws={'shrink': 0.8}, linewidths=0.5)
    ax.set_title(pad, fontweight='bold', color=PAD_COLORS.get(pad, '#333'))
    ax.set_xlabel('Seasonality Prior Scale')
    ax.set_ylabel('Changepoint Prior Scale')

fig.suptitle('Fig 2. Frecuencia de hiperpar\u00e1metros ganadores por padecimiento',
             fontsize=14, fontweight='bold', y=1.02)
fig.tight_layout()
save_fig(fig, 'fig02_heatmap_hp')"""))

    return cells


# ---------------------------------------------------------------------------
# Acto 2 — Resultados Prophet: 312 modelos (celdas 15-24)
# ---------------------------------------------------------------------------
def acto_2():
    cells = []

    # --- Celda 15: Sec 4 ---
    cells.append(md(f"""\
{sec(4, 'Resultados de producci\u00f3n: 312 modelos')}

El pipeline v6 entren\u00f3 312 modelos Prophet en ~45 minutos con paralelizaci\u00f3n joblib:
297 modelos estatales (32 estados x 3 sexos x 3 padecimientos) y 15 modelos regionales
de fallback para estados con datos insuficientes."""))

    # --- Celda 16: Tabla resumen ---
    cells.append(md("""\
### Resumen por padecimiento

| Padecimiento | Modelos | Insuficientes | Fallback regional | RMSE medio | MASE medio | Tiempo |
|:-------------|:--------|:--------------|:-------------------|:-----------|:-----------|:-------|
| **Alzheimer** | 99 | 36 | 36 | 0.027 | 0.74 | ~2 min |
| **Depresi\u00f3n** | 99 | 0 | 0 | 0.183 | 0.80 | ~28 min |
| **Parkinson** | 99 | 5 | 5 | 0.057 | 0.75 | ~14 min |
| **Total** | **297 + 15** | **41** | **41** | \u2014 | **0.76** | **~45 min** |"""))

    # --- Celda 17: Fig 3 — Histograma MASE ---
    cells.append(code("""\
# --- Fig 3: Histograma MASE de 312 modelos con zonas de umbral ---
df_est = df_prophet[
    (df_prophet['_nivel'].isin(['estatal', 'nacional'])) &
    (df_prophet['mase'].notna())
].copy()

fig, ax = plt.subplots(figsize=(11, 5))

# Zonas de color de fondo
ax.axvspan(0, 0.75, alpha=0.08, color='#006847', label='Excelente (< 0.75)')
ax.axvspan(0.75, 1.0, alpha=0.08, color='#B58500', label='Bueno (0.75-1.0)')
ax.axvspan(1.0, df_est['mase'].max() + 0.1, alpha=0.08, color='#9B2242',
           label='Requiere mejora (> 1.0)')

# Histograma por padecimiento
for pad in PAD_ORDER:
    sub = df_est[df_est['padecimiento'] == pad]
    ax.hist(sub['mase'], bins=25, alpha=0.6, color=PAD_COLORS[pad],
            edgecolor='white', label=pad)

# Linea MASE=1.0
ax.axvline(x=1.0, color=IMSS['neutral_black'], ls='--', lw=1.5, alpha=0.7)
ax.text(1.02, ax.get_ylim()[1] * 0.9, 'MASE = 1.0', fontsize=9,
        color=IMSS['neutral_black'])

# Mediana global
med = df_est['mase'].median()
ax.axvline(x=med, color=IMSS['teal'], ls='-', lw=2, alpha=0.8)
ax.text(med + 0.02, ax.get_ylim()[1] * 0.8, f'Mediana: {med:.3f}',
        fontsize=9, color=IMSS['teal'], fontweight='bold')

ax.set_xlabel('MASE')
ax.set_ylabel('Frecuencia')
ax.set_title('Fig 3. Distribuci\u00f3n de MASE en modelos Prophet (v6)',
             fontsize=13, pad=10)
ax.legend(loc='upper right', fontsize=9)
fig.tight_layout()
save_fig(fig, 'fig03_histograma_mase')"""))

    # --- Celda 18: Fig 4 — Heatmap estatal 32x3 ---
    cells.append(code("""\
# --- Fig 4: Heatmap MASE por estado x padecimiento ---
df_gen = df_prophet[
    (df_prophet['_nivel'] == 'estatal') &
    (df_prophet['sexo'] == 'general') &
    (df_prophet['mase'].notna())
].copy()

pivot = df_gen.pivot_table(index='Entidad', columns='padecimiento',
                           values='mase', aggfunc='first')
pivot = pivot.reindex(columns=PAD_ORDER)

# Ordenar por MASE promedio
pivot['_mean'] = pivot.mean(axis=1)
pivot = pivot.sort_values('_mean')
pivot = pivot.drop(columns='_mean')

fig, ax = plt.subplots(figsize=(8, 14))
sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn_r',
            center=1.0, vmin=0.3, vmax=1.5,
            linewidths=0.4, cbar_kws={'label': 'MASE', 'shrink': 0.6},
            ax=ax, mask=pivot.isna())
ax.set_title('Fig 4. MASE por entidad y padecimiento (modo general)',
             fontsize=13, pad=15)
ax.set_xlabel('')
ax.set_ylabel('')
fig.tight_layout()
save_fig(fig, 'fig04_heatmap_estatal')"""))

    # --- Celda 19: Fig 5 — Donut confianza ---
    cells.append(code("""\
# --- Fig 5: Donut de distribucion de confianza ---
df_est_all = df_prophet[df_prophet['_nivel'] == 'estatal'].copy()

n_normal = int((df_est_all['confianza'] == 'normal').sum())
n_insuf = int((df_est_all['confianza'] == 'insuficiente').sum())
n_fallback = int(df_est_all['usar_regional'].notna().sum()) if 'usar_regional' in df_est_all.columns else 0
n_insuf_sin_fb = max(0, n_insuf - n_fallback)

# Filtrar segmentos con tamanio 0
_labels = ['Confianza normal', 'Fallback regional', 'Insuficiente sin fallback']
_sizes = [n_normal, n_fallback, n_insuf_sin_fb]
_colors = [IMSS['teal'], IMSS['gold'], IMSS['burgundy']]
labels, sizes, colors_d = [], [], []
for lb, sz, co in zip(_labels, _sizes, _colors):
    if sz > 0:
        labels.append(lb)
        sizes.append(sz)
        colors_d.append(co)

fig, ax = plt.subplots(figsize=(7, 7))
total = sum(sizes)
wedges, texts, autotexts = ax.pie(
    sizes, labels=labels, colors=colors_d,
    autopct=lambda p: f'{p:.1f}%\\n({int(round(p * total / 100))})',
    startangle=90, pctdistance=0.75,
    wedgeprops=dict(width=0.4, edgecolor='white', linewidth=2))

for t in autotexts:
    t.set_fontsize(10)
    t.set_fontweight('bold')

ax.set_title('Fig 5. Clasificaci\u00f3n de confianza de los 297 modelos estatales',
             fontsize=13, pad=20)
fig.tight_layout()
save_fig(fig, 'fig05_donut_confianza')"""))

    # --- Celda 20: Sec 5 Galeria ---
    cells.append(md(f"""\
{sec(5, 'Galer\u00eda de pron\u00f3sticos')}

Cada modelo genera un gr\u00e1fico PNG con la serie hist\u00f3rica, la banda de predicci\u00f3n a 52 semanas
y las m\u00e9tricas de cross-validation. En total se generan 312 gr\u00e1ficos:
288 estatales + 9 nacionales + 15 regionales."""))

    # --- Celda 21: Fig 6 — Triptych nacional ---
    cells.append(code("""\
# --- Fig 6: Triptych de pronosticos nacionales ---
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
pad_dirs = {'Depresi\u00f3n': 'Depresi\u00f3n', 'Alzheimer': 'Alzheimer', 'Parkinson': 'Parkinson'}

for ax, pad in zip(axes, PAD_ORDER):
    png_path = FORECAST_DIR / pad_dirs[pad] / 'Nacional' / f'{pad_dirs[pad]}_Nacional_general.png'
    if png_path.exists():
        img = Image.open(png_path)
        ax.imshow(img)
    else:
        ax.text(0.5, 0.5, f'No encontrado:\\n{png_path.name}',
                ha='center', va='center', transform=ax.transAxes, fontsize=9)
    ax.set_title(pad, fontweight='bold', color=PAD_COLORS[pad], fontsize=13)
    ax.axis('off')

fig.suptitle('Fig 6. Pron\u00f3sticos nacionales (modo general)',
             fontsize=14, fontweight='bold', y=1.02)
fig.tight_layout()
save_fig(fig, 'fig06_triptych_nacional')"""))

    # --- Celdas 22-24: Grids 32 estados por padecimiento ---
    for fig_num, pad in [(7, 'Depresi\u00f3n'), (8, 'Alzheimer'), (9, 'Parkinson')]:
        pad_dir = pad  # directory name preserves tilde
        cells.append(code(f"""\
# --- Fig {fig_num}: Grid 32 estados - {pad} ---
fig, axes = plt.subplots(8, 4, figsize=(20, 40))
axes_flat = axes.flatten()
_pad_dir = '{pad_dir}'

for i, estado in enumerate(ESTADOS_32):
    ax = axes_flat[i]
    png = FORECAST_DIR / _pad_dir / estado / f'{{_pad_dir}}_{{estado}}_general.png'
    if png.exists():
        img = Image.open(png)
        ax.imshow(img)
    else:
        ax.text(0.5, 0.5, f'{{estado}}\\n(no disponible)',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=8, color='#999')
    ax.set_title(estado, fontsize=9, fontweight='bold', pad=2)
    ax.axis('off')

fig.suptitle('Fig {fig_num}. Pron\u00f3sticos estatales: {pad} (modo general)',
             fontsize=16, fontweight='bold', y=1.0)
fig.tight_layout()
save_fig(fig, 'fig{fig_num:02d}_grid_{pad_dir.lower().replace("\u00f3", "o").replace("\u00e9", "e")}')"""))

    return cells


# ---------------------------------------------------------------------------
# Acto 3 — Benchmark SageMaker (celdas 25-40)  [PLACEHOLDER]
# ---------------------------------------------------------------------------
def acto_3():
    """Benchmark SageMaker: 6 algoritmos, 1548 trials."""
    cells = []

    # --- Celda 25: Sec 6. Benchmark ---
    cells.append(md(f"""\
{sec(6, 'Benchmark SageMaker: 6 algoritmos')}

Para validar Prophet como modelo de producci\u00f3n, se ejecut\u00f3 un benchmark comparativo en
**AWS SageMaker** con 6 algoritmos representativos de distintas familias de modelos.

| Concepto | Valor |
|----------|-------|
| Trials totales | 1,548 (6 modelos x 258 series) |
| Infraestructura | ml.m5.xlarge (4 vCPU, 16 GB RAM) |
| Duraci\u00f3n total | 9.8 horas |
| Costo estimado | ~$9.80 USD |
| Series evaluadas | 258 de 297 (87%) \u2014 39 omitidas por incidencia < 0.5/semana |"""))

    # --- Celda 26: Tabla modelos ---
    cells.append(md("""\
### Los 6 modelos evaluados

| Modelo | Familia | Descripci\u00f3n |
|:-------|:--------|:------------|
| **Prophet** | Aditivo / bayesiano | Descomposici\u00f3n tendencia + estacionalidad + holidays (Taylor & Letham, 2018) |
| **DeepAR** | Deep learning (RNN) | Autoregresivo probabil\u00edstico con LSTM (Salinas et al., 2020) |
| **LightGBM+LSTM** | Ensemble h\u00edbrido | Gradient boosting + memoria temporal LSTM |
| **TFT** | Deep learning (Transformer) | Temporal Fusion Transformer con atenci\u00f3n (Lim et al., 2021) |
| **Ridge** | Regresi\u00f3n lineal | Regresi\u00f3n regularizada L2 con features temporales |
| **XGBoost** | Gradient boosting | \u00c1rboles de decisi\u00f3n con boosting (Chen & Guestrin, 2016) |"""))

    # --- Celda 27: Fig 10 — Bar horizontal ganadores globales ---
    cells.append(code("""\
# --- Fig 10: Ganadores globales por modelo ---
wins = df_ganadores['Modelo Ganador'].value_counts().reindex(MODEL_ORDER, fill_value=0)
colors = [MODEL_COLORS[m] for m in wins.index]

fig, ax = plt.subplots(figsize=(10, 5))
bars = ax.barh(wins.index, wins.values, color=colors, edgecolor='white', height=0.6)

for bar, val in zip(bars, wins.values):
    pct = val / wins.sum() * 100
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
            f'{val} ({pct:.1f}%)', va='center', fontsize=10, fontweight='bold')

ax.set_xlabel('Series ganadas')
ax.set_title('Fig 10. Modelo ganador por serie (258 series)',
             fontsize=13, pad=10)
ax.invert_yaxis()
ax.set_xlim(0, wins.max() * 1.25)
fig.tight_layout()
save_fig(fig, 'fig10_ganadores_global')"""))

    # --- Celda 28: Fig 11 — Grouped bar ganadores por padecimiento ---
    cells.append(code("""\
# --- Fig 11: Ganadores por modelo y padecimiento ---
ct = pd.crosstab(df_ganadores['Modelo Ganador'], df_ganadores['Padecimiento'])
ct = ct.reindex(index=MODEL_ORDER, columns=PAD_ORDER, fill_value=0)

fig, ax = plt.subplots(figsize=(11, 5))
x = np.arange(len(MODEL_ORDER))
w = 0.25
for i, pad in enumerate(PAD_ORDER):
    bars = ax.bar(x + i * w, ct[pad], w, label=pad,
                  color=PAD_COLORS[pad], edgecolor='white')
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3,
                    str(int(h)), ha='center', fontsize=8)

ax.set_xticks(x + w)
ax.set_xticklabels(MODEL_ORDER, fontsize=10)
ax.set_ylabel('Series ganadas')
ax.set_title('Fig 11. Modelo ganador por padecimiento', fontsize=13, pad=10)
ax.legend(title='Padecimiento')
fig.tight_layout()
save_fig(fig, 'fig11_ganadores_padecimiento')"""))

    # --- Celda 29: Fig 12 — Violin MASE por modelo ---
    cells.append(code("""\
# --- Fig 12: Violin de MASE por modelo ---
# Usar columna adecuada de MASE del raw results
_mase_col = 'test_mase'
df_v = df_raw_sm[['modelo', _mase_col]].dropna().copy()
df_v.columns = ['Modelo', 'MASE']
df_v = df_v[df_v['Modelo'].isin(MODEL_ORDER)]

fig, ax = plt.subplots(figsize=(11, 5))
palette = {m: MODEL_COLORS[m] for m in MODEL_ORDER}
sns.violinplot(data=df_v, x='Modelo', y='MASE', order=MODEL_ORDER,
               palette=palette, inner='box', cut=0, ax=ax)

ax.axhline(y=1.0, color=IMSS['neutral_black'], ls='--', lw=1, alpha=0.5)
ax.text(5.3, 1.01, 'Naive', fontsize=8, color=IMSS['cool_gray'])
ax.set_title('Fig 12. Distribuci\u00f3n de MASE por modelo (258 series)',
             fontsize=13, pad=10)
ax.set_xlabel('')
ax.set_ylabel('MASE')
fig.tight_layout()
save_fig(fig, 'fig12_violin_mase_modelo')"""))

    # --- Celda 30: Fig 13 — Heatmap MASE mediana modelo x padecimiento ---
    cells.append(code("""\
# --- Fig 13: Heatmap MASE mediana por modelo y padecimiento ---
pivot_sm = df_mase_modelo.pivot_table(
    index='Modelo', columns='Padecimiento', values='MASE Median', aggfunc='first')
pivot_sm = pivot_sm.reindex(index=MODEL_ORDER, columns=PAD_ORDER)

fig, ax = plt.subplots(figsize=(8, 5))
sns.heatmap(pivot_sm, annot=True, fmt='.3f', cmap='RdYlGn_r',
            center=1.0, vmin=0.5, vmax=1.3,
            linewidths=0.5, cbar_kws={'label': 'MASE mediana'}, ax=ax)
ax.set_title('Fig 13. MASE mediana por modelo y padecimiento',
             fontsize=13, pad=10)
ax.set_xlabel('')
ax.set_ylabel('')
fig.tight_layout()
save_fig(fig, 'fig13_heatmap_mase_modelo')"""))

    # --- Celda 31: Tabla resumen rendimiento ---
    cells.append(md("""\
### Resumen de rendimiento

| Modelo | Wins | Win % | MASE mediana | % MASE < 1.0 |
|:-------|:-----|:------|:-------------|:-------------|
| **Prophet** | 61 | 23.6% | 0.745 | \u2014 |
| **DeepAR** | 50 | 19.4% | 0.748 | \u2014 |
| **LightGBM+LSTM** | 49 | 19.0% | 0.748 | \u2014 |
| **TFT** | 37 | 14.3% | 0.773 | \u2014 |
| **Ridge** | 33 | 12.8% | 0.822 | \u2014 |
| **XGBoost** | 28 | 10.9% | 0.832 | \u2014 |

Deep learning (DeepAR + LightGBM+LSTM + TFT) colectivamente gana el 53% de las series.
Sin embargo, Prophet tiene la mejor MASE mediana global (0.745)."""))

    # --- Celda 32: Sec 7 ---
    cells.append(md(f"""\
{sec(7, 'An\u00e1lisis por padecimiento')}

El rendimiento var\u00eda significativamente entre padecimientos. Depresi\u00f3n es el m\u00e1s dif\u00edcil
de predecir (alta variabilidad post-COVID), mientras que Alzheimer muestra patrones m\u00e1s estables."""))

    # --- Celda 33: Fig 14 — Violin triptych ---
    cells.append(code("""\
# --- Fig 14: Violin triptych MASE por padecimiento ---
_mase_col = 'test_mase'
df_v2 = df_raw_sm[['modelo', 'padecimiento', _mase_col]].dropna().copy()
df_v2.columns = ['Modelo', 'Padecimiento', 'MASE']
df_v2 = df_v2[df_v2['Modelo'].isin(MODEL_ORDER)]

fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
palette = {m: MODEL_COLORS[m] for m in MODEL_ORDER}

for ax, pad in zip(axes, PAD_ORDER):
    sub = df_v2[df_v2['Padecimiento'] == pad]
    if len(sub) > 0:
        sns.violinplot(data=sub, x='Modelo', y='MASE', order=MODEL_ORDER,
                       palette=palette, inner='box', cut=0, ax=ax)
    ax.axhline(y=1.0, color=IMSS['neutral_black'], ls='--', lw=1, alpha=0.4)
    ax.set_title(pad, fontweight='bold', color=PAD_COLORS[pad], fontsize=13)
    ax.set_xlabel('')
    ax.tick_params(axis='x', rotation=30)
    if ax != axes[0]:
        ax.set_ylabel('')

fig.suptitle('Fig 14. Distribuci\u00f3n de MASE por modelo y padecimiento',
             fontsize=14, fontweight='bold', y=1.02)
fig.tight_layout()
save_fig(fig, 'fig14_violin_triptych')"""))

    # --- Celda 34: Fig 15 — % MASE<1.0 ---
    cells.append(code("""\
# --- Fig 15: % MASE<1.0 por modelo y padecimiento ---
pct = df_mase_modelo.pivot_table(
    index='Modelo', columns='Padecimiento', values='% MASE<1.0', aggfunc='first')
pct = pct.reindex(index=MODEL_ORDER, columns=PAD_ORDER)

fig, ax = plt.subplots(figsize=(11, 5))
x = np.arange(len(MODEL_ORDER))
w = 0.25
for i, pad in enumerate(PAD_ORDER):
    vals = pct[pad].fillna(0).values
    bars = ax.bar(x + i * w, vals, w, label=pad,
                  color=PAD_COLORS[pad], edgecolor='white')
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5,
                    f'{h:.0f}%', ha='center', fontsize=8)

ax.set_xticks(x + w)
ax.set_xticklabels(MODEL_ORDER, fontsize=10)
ax.set_ylabel('% de series con MASE < 1.0')
ax.set_title('Fig 15. Porcentaje de series que superan el baseline naive',
             fontsize=13, pad=10)
ax.legend(title='Padecimiento')
ax.set_ylim(0, 105)
fig.tight_layout()
save_fig(fig, 'fig15_pct_mase_bajo1')"""))

    # --- Celda 35: Outliers ---
    cells.append(md("""\
### Entidades con comportamiento at\u00edpico

- **Nayarit (Depresi\u00f3n):** RMSE = 0.39, el peor modelo del pipeline. Cambio de r\u00e9gimen abrupto en 2018 no absorbido completamente por Prophet.
- **Guanajuato:** Alta variabilidad en las tres series. Deep learning tiende a capturarlo mejor.
- **Baja California Sur y San Luis Potos\u00ed:** Series cortas con poca estacionalidad visible; modelos lineales (Ridge) compiten sorprendentemente bien."""))

    # --- Celda 36: Sec 8 ---
    cells.append(md(f"""\
{sec(8, 'An\u00e1lisis por sexo')}

Evaluaci\u00f3n de c\u00f3mo var\u00eda el rendimiento de los modelos seg\u00fan la segmentaci\u00f3n por sexo."""))

    # --- Celda 37: Fig 16 — Heatmap victorias sexo ---
    cells.append(code("""\
# --- Fig 16: Heatmap de victorias por padecimiento, sexo y modelo ---
# Construir pivot: padecimiento x sexo, valor = modelo ganador dominante
ct_sex = pd.crosstab(
    [df_ganadores['Padecimiento'], df_ganadores['Sexo']],
    df_ganadores['Modelo Ganador']
).reindex(columns=MODEL_ORDER, fill_value=0)

fig, ax = plt.subplots(figsize=(10, 6))
sns.heatmap(ct_sex, annot=True, fmt='d', cmap='YlOrRd',
            linewidths=0.5, cbar_kws={'label': 'Victorias'}, ax=ax)
ax.set_title('Fig 16. Victorias por padecimiento, sexo y modelo',
             fontsize=13, pad=10)
ax.set_xlabel('Modelo')
ax.set_ylabel('')
fig.tight_layout()
save_fig(fig, 'fig16_heatmap_sexo')"""))

    # --- Celda 38: Sec 9 ---
    cells.append(md(f"""\
{sec(9, 'Predicciones cara a cara')}

Comparaci\u00f3n visual de predicciones entre Prophet y los mejores modelos alternativos
en series representativas."""))

    # --- Celda 39: Fig 17 — 3x3 grid predicciones ---
    cells.append(code("""\
# --- Fig 17: Predicciones cara a cara (3 series showcase x 3 modelos) ---
# Seleccionar 3 series representativas:
# 1) Prophet gana claramente, 2) Prophet pierde, 3) competitiva
_showcase = [
    ('Alzheimer', 'general', 'Nacional'),       # Prophet suele ganar Alzheimer
    ('Depresi\u00f3n', 'general', 'Jalisco'),     # Depresion competitiva
    ('Parkinson', 'general', 'Nacional'),       # Comparacion directa
]
_top_models = ['Prophet', 'DeepAR', 'LightGBM+LSTM']

fig, axes = plt.subplots(3, 3, figsize=(18, 12))

for row, (pad, sexo, nivel) in enumerate(_showcase):
    for col, modelo in enumerate(_top_models):
        ax = axes[row, col]
        # Construir nombre de archivo de prediccion
        nivel_file = nivel.replace(' ', '_').replace('\u00e9', 'e').replace('\u00e1', 'a').replace('\u00f3', 'o').replace('\u00ed', 'i').replace('\u00fa', 'u')
        pad_file = pad.replace('\u00f3', '\u00f3')  # mantener tilde en nombre
        fname = PRED_DIR / f'{modelo}_{pad_file}_{nivel_file}_{sexo}.csv'
        if fname.exists():
            pred = pd.read_csv(fname)
            pred['ds'] = pd.to_datetime(pred['ds'])
            ax.plot(pred['ds'], pred['y_true_original'], color=IMSS['neutral_black'],
                    lw=1.5, label='Real', alpha=0.8)
            color = MODEL_COLORS.get(modelo, '#333')
            ax.plot(pred['ds'], pred['y_pred_original'], color=color,
                    lw=2, label=modelo, ls='--')
        else:
            ax.text(0.5, 0.5, f'No encontrado:\\n{fname.name}',
                    ha='center', va='center', transform=ax.transAxes, fontsize=7)

        if row == 0:
            ax.set_title(modelo, fontweight='bold', color=MODEL_COLORS.get(modelo, '#333'))
        if col == 0:
            ax.set_ylabel(f'{pad}\\n{nivel}', fontsize=10)
        ax.tick_params(axis='x', rotation=30, labelsize=8)
        if row == 0 and col == 0:
            ax.legend(fontsize=8, loc='upper left')

fig.suptitle('Fig 17. Predicciones cara a cara: real vs modelo (escala original)',
             fontsize=14, fontweight='bold', y=1.01)
fig.tight_layout()
save_fig(fig, 'fig17_cara_a_cara')"""))

    # --- Celda 40: Fig 18 — Scatter gap Prophet ---
    cells.append(code("""\
# --- Fig 18: Scatter gap de Prophet vs mejor modelo por serie ---
df_gap = df_ganadores[['Padecimiento', 'Gap vs Best (%)']].dropna().copy()
# Convertir a numerico si es string
df_gap['Gap vs Best (%)'] = pd.to_numeric(df_gap['Gap vs Best (%)'], errors='coerce')
df_gap = df_gap.dropna()

fig, ax = plt.subplots(figsize=(11, 5))
for pad in PAD_ORDER:
    sub = df_gap[df_gap['Padecimiento'] == pad]
    ax.scatter(range(len(sub)), sorted(sub['Gap vs Best (%)']),
               color=PAD_COLORS[pad], alpha=0.6, s=30, label=pad)

ax.axhline(y=0, color=IMSS['teal'], lw=2, ls='-', alpha=0.8)
ax.axhline(y=5, color=IMSS['cool_gray'], ls='--', lw=1, alpha=0.5)
ax.axhline(y=10, color=IMSS['cool_gray'], ls='--', lw=1, alpha=0.5)
ax.axhline(y=20, color=IMSS['cool_gray'], ls='--', lw=1, alpha=0.5)

ax.text(len(df_gap) * 0.85, 0.5, 'Prophet es el ganador', fontsize=8,
        color=IMSS['teal'])
ax.text(len(df_gap) * 0.85, 5.5, '< 5% del ganador', fontsize=8,
        color=IMSS['cool_gray'])
ax.text(len(df_gap) * 0.85, 10.5, '< 10% del ganador', fontsize=8,
        color=IMSS['cool_gray'])
ax.text(len(df_gap) * 0.85, 20.5, '< 20% del ganador', fontsize=8,
        color=IMSS['cool_gray'])

ax.set_xlabel('Series (ordenadas por gap)')
ax.set_ylabel('Gap vs mejor modelo (%)')
ax.set_title('Fig 18. Proximidad de Prophet al modelo ganador por serie',
             fontsize=13, pad=10)
ax.legend(title='Padecimiento', loc='upper left')
fig.tight_layout()
save_fig(fig, 'fig18_scatter_gap')"""))

    return cells


# ---------------------------------------------------------------------------
# Acto 4 — El veredicto (celdas 41-48)  [PLACEHOLDER]
# ---------------------------------------------------------------------------
def acto_4():
    """Seleccion del modelo final + Dashboard."""
    cells = []

    # --- Celda 41: Sec 10 ---
    cells.append(md(f"""\
{sec(10, 'Selecci\u00f3n del modelo final')}

Con 1,548 trials evaluados en SageMaker, la selecci\u00f3n del modelo de producci\u00f3n se basa
en m\u00faltiples criterios cuantitativos y cualitativos."""))

    # --- Celda 42: Fig 19 — Proximidad Prophet al ganador ---
    cells.append(code("""\
# --- Fig 19: Proximidad de Prophet al ganador (% dentro de umbral) ---
df_gap2 = df_ganadores['Gap vs Best (%)'].dropna()
df_gap2 = pd.to_numeric(df_gap2, errors='coerce').dropna()

thresholds = [0, 5, 10, 20]
labels_th = ['Ganador\\n(gap = 0%)', 'Dentro\\ndel 5%', 'Dentro\\ndel 10%', 'Dentro\\ndel 20%']
pcts = [((df_gap2 <= t).sum() / len(df_gap2) * 100) for t in thresholds]
colors_th = [IMSS['teal'], IMSS['gold'], IMSS['burgundy'], IMSS['cool_gray']]

fig, ax = plt.subplots(figsize=(9, 5))
bars = ax.bar(labels_th, pcts, color=colors_th, edgecolor='white', width=0.6)
for bar, p in zip(bars, pcts):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            f'{p:.1f}%', ha='center', fontweight='bold', fontsize=11)

ax.set_ylabel('% de series')
ax.set_title('Fig 19. Proximidad de Prophet al modelo ganador',
             fontsize=13, pad=10)
ax.set_ylim(0, 100)
fig.tight_layout()
save_fig(fig, 'fig19_proximidad_prophet')"""))

    # --- Celda 43: Fig 20 — Radar comparativo ---
    cells.append(code("""\
# --- Fig 20: Radar comparativo multi-metrica ---
categories = ['Wins', 'MASE\\n(inv.)', 'Velocidad', 'Interpretab.', 'Cobertura', 'Consistencia']
n_cats = len(categories)
angles = np.linspace(0, 2 * np.pi, n_cats, endpoint=False).tolist()
angles += angles[:1]

# Valores normalizados 0-1 (1 = mejor)
radar_data = {
    'Prophet':        [0.85, 0.95, 0.30, 1.00, 1.00, 0.90],
    'DeepAR':         [0.70, 0.94, 0.50, 0.40, 0.87, 0.80],
    'LightGBM+LSTM':  [0.68, 0.94, 0.60, 0.50, 0.87, 0.75],
    'TFT':            [0.55, 0.88, 0.55, 0.60, 0.87, 0.70],
    'Ridge':          [0.45, 0.78, 0.95, 0.80, 0.87, 0.55],
    'XGBoost':        [0.40, 0.76, 0.90, 0.70, 0.87, 0.50],
}

fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
for modelo in ['Prophet', 'DeepAR', 'TFT']:
    vals = radar_data[modelo] + [radar_data[modelo][0]]
    ax.plot(angles, vals, 'o-', lw=2, label=modelo,
            color=MODEL_COLORS[modelo], markersize=5)
    ax.fill(angles, vals, alpha=0.1, color=MODEL_COLORS[modelo])

ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=10)
ax.set_ylim(0, 1.1)
ax.set_title('Fig 20. Comparativo multi-m\u00e9trica (top 3 modelos)',
             fontsize=13, pad=25)
ax.legend(loc='lower right', bbox_to_anchor=(1.2, -0.05), fontsize=10)
fig.tight_layout()
save_fig(fig, 'fig20_radar_comparativo')"""))

    # --- Celda 44: 7 argumentos ---
    cells.append(md(f"""\
### Argumentos para la selecci\u00f3n de Prophet

{GREEN_BOX}
<strong>1. Mejor MASE mediana global (0.745)</strong> \u2014 supera a los 5 modelos alternativos
en la m\u00e9trica principal del benchmark.
</div>

{GREEN_BOX}
<strong>2. Consistencia:</strong> 78% de las series dentro del 20% del modelo ganador.
Ning\u00fan otro modelo tiene esta estabilidad.
</div>

{GREEN_BOX}
<strong>3. Interpretabilidad:</strong> descomposici\u00f3n expl\u00edcita en tendencia, estacionalidad
y holidays. Esencial para comunicaci\u00f3n con el equipo cl\u00ednico del IMSS.
</div>

{BLUE_BOX}
<strong>4. Cobertura 100%:</strong> el modo h\u00edbrido (v6) garantiza predicci\u00f3n informada
para las 32 entidades, incluyendo estados con datos insuficientes.
</div>

{BLUE_BOX}
<strong>5. Costo operativo m\u00ednimo:</strong> no requiere GPU ni infraestructura cloud para
inferencia. Entrenamiento completo en ~45 minutos en CPU.
</div>

{BLUE_BOX}
<strong>6. Mantenibilidad:</strong> configuraci\u00f3n declarativa en YAML, pipeline reproducible
con Makefile, versionado de modelos con DVC.
</div>

{GOLD_BOX}
<strong>7. Dominio en Alzheimer:</strong> Prophet gana el 33% de las series de Alzheimer,
el padecimiento prioritario para el IMSS por subdiagn\u00f3stico.
</div>"""))

    # --- Celda 45: Limitaciones ---
    cells.append(md("""\
### Limitaciones y compromisos reconocidos

- **Prophet no domina:** gana solo el 23.6% de las series. Deep learning colectivamente supera a Prophet en el 53% de los casos.
- **Depresi\u00f3n es vulnerable:** MASE mediana de 0.935, cercana al umbral naive. Un ensemble con DeepAR podr\u00eda mejorar este padecimiento.
- **Tiempo de entrenamiento:** Prophet consume el 68% del tiempo total del benchmark (6.7h de 9.8h). Los modelos lineales son 10-50x m\u00e1s r\u00e1pidos.
- **Sin variables ex\u00f3genas din\u00e1micas:** el pipeline actual no incorpora covariables externas (clima, movilidad, vacunaci\u00f3n). TFT podr\u00eda aprovecharlas mejor.
- **Evaluaci\u00f3n en escala log:** las m\u00e9tricas de CV se calculan en espacio log-tasa. Las m\u00e9tricas en escala original (conteos) pueden diferir."""))

    # --- Celda 46: Sec 11 Dashboard ---
    cells.append(md(f"""\
{sec(11, 'Dashboard Tableau')}

Integraci\u00f3n con Tableau Public para la visualizaci\u00f3n interactiva de los resultados
del modelado, accesible al equipo cl\u00ednico del IMSS sin necesidad de ejecutar c\u00f3digo.

{BLUE_BOX}
<strong>Contribuci\u00f3n de Luis S\u00e1nchez:</strong> Diagn\u00f3stico post-entrenamiento,
reconstrucci\u00f3n del pipeline de datos para Tableau, migraci\u00f3n del workbook
y experimento de automatizaci\u00f3n con GitHub Actions + Google Sheets.
</div>"""))

    # --- Celda 47: Dashboard contenido ---
    cells.append(md("""\
### Pipeline de datos y migraci\u00f3n

La arquitectura se migr\u00f3 de dos fuentes separadas (hist\u00f3ricos + pron\u00f3sticos) a un
**\u00fanico dataset integrado** (`tableau.csv`) generado por `make tableau`. Esto resolvi\u00f3
el problema de fechas futuras que desaparec\u00edan al filtrar por entidad.

**Funcionalidades del dashboard:**
- Series de tiempo con banda de pron\u00f3stico y l\u00ednea de referencia COVID-19
- Mapa coropl\u00e9tico de incidencia por entidad federativa
- Tabla de m\u00e9tricas por modelo (RMSE, MAE, MAPE, MASE, confianza)
- Vista normalizada: tasas por 100,000 habitantes con doble escala
- Tooltips informativos con m\u00e9tricas y modelo utilizado
- MASE categ\u00f3rico: excelente / bueno / requiere mejora

### Automatizaci\u00f3n

Se valid\u00f3 un principio de automatizaci\u00f3n: GitHub Actions \u2192 Google Sheets \u2192 Tableau Public.
La escritura a Google Sheets funciona correctamente; el refresh de Tableau Public (~24h) es la
principal incertidumbre.

| Licencia | Costo aprox. | Refresh programado |
|:---------|:-------------|:-------------------|
| Tableau Public | Gratis | Solo Google Sheets (~1x/d\u00eda) |
| Tableau Cloud (Creator) | ~75 USD/mes | S\u00ed |
| Tableau Cloud (Viewer) | ~15 USD/mes | S\u00ed |"""))

    # --- Celda 48: Galeria dashboard ---
    cells.append(md("""\
### Galer\u00eda del dashboard

<table style="width:100%; border-collapse: collapse; margin: 20px 0;">
<tr>
<td style="width:50%; padding:8px; vertical-align:top;">
<p align="center">
  <img src="https://luisgss10.com/images/dash/dash1.png" width="100%" alt="Dashboard principal" />
</p>
<p align="center" style="color: #666; font-size: 0.85em;"><em>Vista principal: series de tiempo con banda de pron\u00f3stico y filtros interactivos.</em></p>
</td>
<td style="width:50%; padding:8px; vertical-align:top;">
<p align="center">
  <img src="https://luisgss10.com/images/dash/predict.png" width="100%" alt="Vista de predicciones" />
</p>
<p align="center" style="color: #666; font-size: 0.85em;"><em>Predicciones por entidad con intervalos de confianza y m\u00e9tricas del modelo.</em></p>
</td>
</tr>
<tr>
<td style="width:50%; padding:8px; vertical-align:top;">
<p align="center">
  <img src="https://luisgss10.com/images/dash/mapa2.png" width="100%" alt="Mapa de incidencia" />
</p>
<p align="center" style="color: #666; font-size: 0.85em;"><em>Mapa coropl\u00e9tico de incidencia por entidad federativa.</em></p>
</td>
<td style="width:50%; padding:8px; vertical-align:top;">
<p align="center">
  <img src="https://luisgss10.com/images/dash/tabla2.png" width="100%" alt="Tabla de m\u00e9tricas" />
</p>
<p align="center" style="color: #666; font-size: 0.85em;"><em>Tabla de m\u00e9tricas por modelo: RMSE, MAE, MAPE, MASE y nivel de confianza.</em></p>
</td>
</tr>
<tr>
<td style="width:50%; padding:8px; vertical-align:top;">
<p align="center">
  <img src="https://luisgss10.com/images/dash/semana.png" width="100%" alt="Vista semanal" />
</p>
<p align="center" style="color: #666; font-size: 0.85em;"><em>Detalle semanal con l\u00ednea de referencia COVID-19 y tooltips enriquecidos.</em></p>
</td>
<td style="width:50%; padding:8px; vertical-align:top;">
<p align="center">
  <img src="https://luisgss10.com/images/dash/year.png" width="100%" alt="Vista anual" />
</p>
<p align="center" style="color: #666; font-size: 0.85em;"><em>Agregaci\u00f3n anual: tendencias de largo plazo por padecimiento.</em></p>
</td>
</tr>
</table>"""))

    return cells


# ---------------------------------------------------------------------------
# Acto 5 — Cierre (celdas 49-54)  [PLACEHOLDER]
# ---------------------------------------------------------------------------
def acto_5():
    """Publicacion, conclusiones, reflexiones, referencias."""
    cells = []

    # --- Celda 49: Sec 12 Publicacion ---
    cells.append(md(f"""\
{sec(12, 'Publicaci\u00f3n acad\u00e9mica')}

### Art\u00edculo en preparaci\u00f3n

| Campo | Detalle |
|-------|---------|
| **T\u00edtulo** | *EpiForecast-MX: Pron\u00f3stico de Incidencia Epidemiol\u00f3gica de Padecimientos Neurol\u00f3gicos mediante Facebook Prophet* |
| **Autores** | Equipo 01 (Javier Rebull, Juan Carlos P\u00e9rez Nava, Luis S\u00e1nchez) + Dra. Ruth P\u00e9rez (IMSS) + Dra. Lina D\u00edaz Castro (IMSS) |
| **Estado** | Draft en preparaci\u00f3n |
| **\u00c1mbito** | Epidemiolog\u00eda computacional aplicada a salud mental y padecimientos neurol\u00f3gicos en M\u00e9xico |

**Contenido previsto:**

1. Metodolog\u00eda de extracci\u00f3n automatizada de boletines epidemiol\u00f3gicos del SINAVE (633 PDFs, 2014-2026).
2. Pipeline de preprocesamiento con normalizaci\u00f3n a tasas por 100,000 habitantes y detecci\u00f3n de outliers parametrizada.
3. Resultados de 312 modelos Prophet (v6) con cross-validation temporal ponderada y modo h\u00edbrido.
4. Comparativa rigurosa con 6 modelos alternativos (1,548 trials en AWS SageMaker).
5. Discusi\u00f3n de trade-offs entre interpretabilidad, rendimiento y costo operativo.

La publicaci\u00f3n busca contribuir al campo de la epidemiolog\u00eda computacional en M\u00e9xico, proporcionando una metodolog\u00eda reproducible para el pron\u00f3stico de padecimientos neurol\u00f3gicos con datos p\u00fablicos del sistema de vigilancia epidemiol\u00f3gica."""))

    # --- Celda 50: Sec 13 Conclusiones ---
    cells.append(md(f"""\
{sec(13, 'Conclusiones y Siguientes Pasos')}

### Hallazgos principales

{GREEN_BOX}
<strong>1. Prophet es competitivo y consistente.</strong>
MASE mediana de 0.745 \u2014 la mejor entre los 6 modelos evaluados. Top 3 en el 59.3% de las 258 series.
La diferencia respecto a DeepAR (0.748) y LightGBM+LSTM (0.748) no es estad\u00edsticamente significativa.
</div>

{GREEN_BOX}
<strong>2. El modo h\u00edbrido (v6) logra 100% de cobertura estatal.</strong>
Los 41 estados con incidencia insuficiente ahora utilizan modelos regionales de fallback basados en las 4 regiones INEGI de salud mental,
eliminando las predicciones planas de v5. Cobertura: 72% (v3) \u2192 87% (v5) \u2192 100% (v6).
</div>

{BLUE_BOX}
<strong>3. El log-transform fue el cambio m\u00e1s impactante.</strong>
La transformaci\u00f3n log(1+y) redujo la mediana de RMSE en Depresi\u00f3n un 64% (v1\u2192v2).
La varianza de la serie se estabiliz\u00f3 dram\u00e1ticamente, permitiendo que Prophet capture cambios relativos en lugar de absolutos.
</div>

{BLUE_BOX}
<strong>4. Grids diferenciados por padecimiento reducen MASE y tiempo.</strong>
Alzheimer: 6 combinaciones (multiplicative only, additive eliminado por +51% RMSE).
Depresi\u00f3n: 24 combinaciones (sp=0.025 nuevo ganador en 29%).
Parkinson: 18 combinaciones (cp=0.04 nuevo ganador en 20%).
</div>

{GOLD_BOX}
<strong>5. Deep learning es colectivamente superior pero ning\u00fan modelo domina.</strong>
TFT + DeepAR + LightGBM+LSTM ganan el 54.7% de las series.
Sin embargo, Prophet tiene la mejor mediana global y el menor porcentaje de \u00faltimos lugares (12.8% vs 27% de Ridge/XGBoost).
</div>

{GOLD_BOX}
<strong>6. Depresi\u00f3n es el padecimiento m\u00e1s dif\u00edcil de predecir.</strong>
MASE mediana de 0.935 (cercana a 1.0). Alta variabilidad post-COVID y heterogeneidad regional.
El 36% de los modelos XGBoost/Ridge no superan la baseline naive en Depresi\u00f3n.
</div>

### Siguientes pasos

1. **Ensemble jer\u00e1rquico**: combinar Prophet con TFT/DeepAR para series donde Prophet pierde consistentemente.
2. **Actualizaci\u00f3n incremental**: integrar nuevos boletines SINAVE v\u00eda CI/CD para reentrenar modelos trimestralmente.
3. **Dashboard ejecutivo**: vista gerencial en Tableau para el equipo cl\u00ednico del IMSS.
4. **Publicaci\u00f3n acad\u00e9mica**: art\u00edculo con Dra. Ruth P\u00e9rez y Dra. Lina D\u00edaz Castro del IMSS."""))

    # --- Celda 51: Sec 14 Reflexiones ---
    cells.append(md(f"""\
{sec(14, 'Reflexiones del Equipo')}

### Reflexiones individuales

**Javier Rebull** \u2014 Desarrollo de pipeline y modelado Prophet

(Pendiente)

---

**Juan Carlos P\u00e9rez Nava** \u2014 Integraci\u00f3n IMSS y validaci\u00f3n cl\u00ednica

(Pendiente)

---

**Luis S\u00e1nchez** \u2014 Dashboard Tableau y visualizaci\u00f3n

(Pendiente)"""))

    # --- Celda 52: Sec 15 Referencias ---
    cells.append(md(f"""\
{sec(15, 'Referencias y Enlaces')}"""))

    # --- Celda 53: Referencias academicas ---
    cells.append(md("""\
### Referencias acad\u00e9micas

1. Taylor, S. J., & Letham, B. (2018). Forecasting at scale. *The American Statistician*, 72(1), 37\u201345. https://doi.org/10.1080/00031305.2017.1380080

2. Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting*, 22(4), 679\u2013688. https://doi.org/10.1016/j.ijforecast.2006.03.001

3. Salinas, D., Flunkert, V., Gasthaus, J., & Januschowski, T. (2020). DeepAR: Probabilistic forecasting with autoregressive recurrent networks. *International Journal of Forecasting*, 36(3), 1181\u20131191. https://doi.org/10.1016/j.ijforecast.2019.07.001

4. Lim, B., Ar\u0131k, S. \u00d6., Loeff, N., & Pfister, T. (2021). Temporal Fusion Transformers for interpretable multi-horizon time series forecasting. *International Journal of Forecasting*, 37(4), 1748\u20131764. https://doi.org/10.1016/j.ijforecast.2021.01.012

5. Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*, 785\u2013794. https://doi.org/10.1145/2939672.2939785

6. G\u00e9ron, A. (2022). *Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow* (3.a ed.). O'Reilly Media."""))

    # --- Celda 54: Tabla de enlaces ---
    cells.append(md("""\
### Recursos y enlaces del proyecto

| Recurso | Enlace |
|---------|--------|
| Repositorio GitHub | https://github.com/Memory-of-Hermes/EpiForecast-MX |
| Repositorio SageMaker (fork) | https://github.com/claude/EpiForecast-MX |
| Dashboard Tableau Public | (enlace pendiente de publicaci\u00f3n) |
| Reporte de Resultados | `forecast/reporte_resultados.html` |
| Bit\u00e1cora del Modelado | `forecast/bitacora_modelado.html` |
| Comparaci\u00f3n de Modelos | `forecast/comparacion_modelos.html` |
| Galer\u00eda de Pron\u00f3sticos | `forecast/index.html` |
| Ficha T\u00e9cnica Prophet | `forecast/ficha_tecnica_prophet.html` |
| Hiperpar\u00e1metros | `forecast/hiperparametros_modelos.html` |
| Conclusiones | `forecast/conclusiones.html` |
| Dashboard T\u00e9cnico | `forecast/construccion_dashboard.html` |
| Datos S3 | `s3://epiforecast-mx-data/latest/` |
| Art\u00edculo (draft) | En preparaci\u00f3n |"""))

    return cells


# ---------------------------------------------------------------------------
# Apendice — Ficha Tecnica Prophet (celdas 55-66)  [PLACEHOLDER]
# ---------------------------------------------------------------------------
def apendice():
    """Ficha Tecnica de Prophet (colapsable)."""
    cells = []

    # --- Celda 55: Header apendice ---
    cells.append(md(f"""\
{DIV}

## Ap\u00e9ndice A: Ficha T\u00e9cnica de Prophet <a id="secA"></a>

<details open>
<summary style="cursor: pointer; font-size: 1.1em; font-weight: bold; color: #003A70;
padding: 10px; background: #f0f4f8; border-radius: 4px; margin: 10px 0;">
Expandir / Contraer ficha t\u00e9cnica completa
</summary>"""))

    # --- Celda 56: FT.1 Transformaciones del target ---
    cells.append(md("""\
### FT.1 Transformaciones del target

El pipeline aplica dos transformaciones secuenciales antes de entrenar Prophet:

| Paso | Transformaci\u00f3n | F\u00f3rmula | Prop\u00f3sito |
|:-----|:---------------|:---------|:----------|
| 1 | Normalizaci\u00f3n a tasa | `y_tasa = (incidencia / poblaci\u00f3n) x 100,000` | Comparabilidad entre estados |
| 2 | Log-transform | `y = log(1 + y_tasa)` | Estabilizar varianza |

Al predecir, se invierte: `exp(y_hat) - 1` \u2192 desnormaliza con poblaci\u00f3n estatal \u2192 conteos."""))

    # --- Celda 57: Fig A1 — Log-transform ---
    cells.append(code("""\
# --- Fig A1: Efecto del log-transform ---
# Simular una serie tipo Depresion para ilustrar
np.random.seed(42)
n = 200
t = np.arange(n)
trend = 50 + 0.3 * t
seasonal = 15 * np.sin(2 * np.pi * t / 52)
noise = np.random.normal(0, 8, n)
y_raw = np.maximum(trend + seasonal + noise, 1)
y_tasa = y_raw / 5_000_000 * 100_000
y_log = np.log1p(y_tasa)

fig, axes = plt.subplots(1, 3, figsize=(16, 4))
titles = ['Conteos crudos', 'Tasa por 100K hab.', 'log(1 + tasa)']
series = [y_raw, y_tasa, y_log]
colors = [IMSS['burgundy'], IMSS['gold'], IMSS['teal']]

for ax, title, y, c in zip(axes, titles, series, colors):
    ax.plot(t, y, color=c, lw=1.5)
    ax.set_title(title, fontweight='bold')
    ax.set_xlabel('Semana')
    std_text = f'\u03c3 = {np.std(y):.2f}'
    ax.text(0.95, 0.95, std_text, transform=ax.transAxes, ha='right', va='top',
            fontsize=10, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

fig.suptitle('Fig A1. Efecto de las transformaciones sobre la varianza',
             fontsize=13, fontweight='bold', y=1.03)
fig.tight_layout()
save_fig(fig, 'figA1_log_transform')"""))

    # --- Celda 58: FT.2 Estacionalidad y Fourier ---
    cells.append(md("""\
### FT.2 Estacionalidad y series de Fourier

Prophet modela la estacionalidad anual como una suma de arm\u00f3nicos de Fourier:

`s(t) = \u2211 [a_n * cos(2\u03c0nt/P) + b_n * sin(2\u03c0nt/P)]`

donde `P = 365.25` d\u00edas y `n` va de 1 hasta `fourier_order`.

| Par\u00e1metro | Nacional | Estatal/Regional |
|:----------|:---------|:-----------------|
| `fourier_order` | 5 | 3 |
| `n_changepoints` | 25 (default) | 12 |

El `fourier_order` reducido para modelos estatales previene el sobreajuste
en series m\u00e1s cortas y con menor se\u00f1al estacional."""))

    # --- Celda 59: Fig A2 — Armonicos Fourier ---
    cells.append(code("""\
# --- Fig A2: Armonicos de Fourier ---
t = np.linspace(0, 365.25 * 2, 1000)
P = 365.25

fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

# fourier_order = 5
ax = axes[0]
signal_5 = np.zeros_like(t)
for n in range(1, 6):
    comp = np.sin(2 * np.pi * n * t / P) + 0.5 * np.cos(2 * np.pi * n * t / P)
    signal_5 += comp
    ax.plot(t / 365.25, comp, alpha=0.3, lw=1)
ax.plot(t / 365.25, signal_5, color=IMSS['teal'], lw=2.5, label='Suma (order=5)')
ax.set_title('fourier_order = 5 (modelos nacionales)', fontweight='bold')
ax.legend(loc='upper right')
ax.set_ylabel('Amplitud')

# fourier_order = 3
ax = axes[1]
signal_3 = np.zeros_like(t)
for n in range(1, 4):
    comp = np.sin(2 * np.pi * n * t / P) + 0.5 * np.cos(2 * np.pi * n * t / P)
    signal_3 += comp
    ax.plot(t / 365.25, comp, alpha=0.3, lw=1)
ax.plot(t / 365.25, signal_3, color=IMSS['burgundy'], lw=2.5, label='Suma (order=3)')
ax.set_title('fourier_order = 3 (modelos estatales)', fontweight='bold')
ax.legend(loc='upper right')
ax.set_xlabel('A\u00f1os')
ax.set_ylabel('Amplitud')

fig.suptitle('Fig A2. Arm\u00f3nicos de Fourier para estacionalidad anual',
             fontsize=13, fontweight='bold', y=1.02)
fig.tight_layout()
save_fig(fig, 'figA2_fourier')"""))

    # --- Celda 60: FT.3 Cross-validation temporal ---
    cells.append(md("""\
### FT.3 Cross-validation temporal con pesos progresivos

El pipeline utiliza 4 folds de validaci\u00f3n cruzada temporal (**expanding window**),
donde cada fold avanza el punto de corte y eval\u00faa las siguientes 53 semanas.

Los folds se ponderan con pesos progresivos `[0.5, 0.75, 1.0, 1.25]`, dando
m\u00e1s importancia a los periodos recientes (2023-2024) y menos al periodo
post-COVID (2020-2021).

La m\u00e9trica final es `np.average(rmse_folds, weights=cv_weights)` en vez de
`np.mean()`, lo que sesga la selecci\u00f3n de hiperpar\u00e1metros hacia combos que
funcionan bien en datos recientes."""))

    # --- Celda 61: Fig A3 — Diagrama de folds ---
    cells.append(code("""\
# --- Fig A3: Diagrama de folds de cross-validation ---
fig, ax = plt.subplots(figsize=(14, 4))

# Simular folds
folds = [
    ('Fold 1', 2014, 2020, 2021, 0.50),
    ('Fold 2', 2014, 2021, 2022, 0.75),
    ('Fold 3', 2014, 2022, 2023, 1.00),
    ('Fold 4', 2014, 2023, 2024, 1.25),
]

for i, (name, train_start, train_end, test_end, weight) in enumerate(folds):
    y = 3 - i
    # Train
    ax.barh(y, train_end - train_start, left=train_start, height=0.5,
            color=IMSS['teal'], alpha=0.7, edgecolor='white')
    # Test
    ax.barh(y, test_end - train_end, left=train_end, height=0.5,
            color=IMSS['burgundy'], alpha=0.7, edgecolor='white')
    # Label
    ax.text(train_start - 0.3, y, f'{name}\\n(w={weight})', ha='right', va='center',
            fontsize=9, fontweight='bold')

# COVID zone
ax.axvspan(2020.2, 2022.7, alpha=0.08, color='red')
ax.text(2021.4, 4, 'COVID-19', ha='center', fontsize=8, color='red', alpha=0.6)

# Leyenda
ax.barh([], 0, color=IMSS['teal'], alpha=0.7, label='Entrenamiento')
ax.barh([], 0, color=IMSS['burgundy'], alpha=0.7, label='Evaluaci\u00f3n (53 sem)')
ax.legend(loc='upper right')

ax.set_xlabel('A\u00f1o')
ax.set_yticks([])
ax.set_xlim(2013.5, 2025.5)
ax.set_title('Fig A3. Cross-validation temporal con pesos progresivos',
             fontsize=13, pad=10)
fig.tight_layout()
save_fig(fig, 'figA3_cv_folds')"""))

    # --- Celda 62: FT.4 Anti-Newton ---
    cells.append(md("""\
### FT.4 Protecci\u00f3n anti-Newton

Prophet puede caer al optimizador Newton (~100-500x m\u00e1s lento) cuando L-BFGS no converge.
Tres mecanismos lo mitigan:

| Capa | Mecanismo | Efecto |
|:-----|:----------|:-------|
| 1 | Sort CP descendente | Combos con CP alto (r\u00e1pido) se prueban primero |
| 2 | Timeout por fold (35s) | `ThreadPoolExecutor` corta un fold que exceda 35s |
| 3 | Newton-prone threshold | Si combo con CP=X timeout, skip combos con CP < X |

**Resultado:** Chihuahua-Depresi\u00f3n pas\u00f3 de 39 min (v4) a 4 min (v5)."""))

    # --- Celda 63: FT.5 Modo hibrido ---
    cells.append(md("""\
### FT.5 Modo h\u00edbrido y clasificaci\u00f3n de confianza

Series con promedio < 0.5 casos/semana se clasifican como `confianza: insuficiente`.
Con `modelado_hibrido: true` (v6):

1. Se entrenan modelos regionales (4 regiones INEGI de salud mental)
2. Cada estado insuficiente se mapea a su regi\u00f3n
3. En predicci\u00f3n, se usa el modelo regional pero se desnormaliza con la **poblaci\u00f3n estatal individual**

**Regiones INEGI de salud mental:**
- Urbana media
- Sur-Sureste vulnerable
- Metropolitana alta
- Rural / dispersa"""))

    # --- Celda 64: FT.6 Periodos atipicos ---
    cells.append(md("""\
### FT.6 Periodos at\u00edpicos configurados

| Evento | Fecha inicio | Ventana | Efecto |
|:-------|:-------------|:--------|:-------|
| Pandemia COVID-19 | 2020-03-23 | 913 d\u00edas (~2.5 a\u00f1os) | Holiday global en Prophet |
| Cambio de r\u00e9gimen Tabasco (Depresi\u00f3n) | 2023-01-09 | 365 d\u00edas | Holiday filtrado por entidad (-6.2% RMSE) |

Los cambios de r\u00e9gimen permanentes (Nayarit, Colima, Durango, BCS) no se modelan
como holidays porque Prophet los trata como eventos temporales, empeorando el RMSE."""))

    # --- Celda 65: FT.7 Mapa de parametros ---
    cells.append(md("""\
### FT.7 Mapa completo de par\u00e1metros

| Par\u00e1metro | Valor | Fuente |
|:----------|:------|:-------|
| `normalizar_tasa` | `true` | `config/modelado.yaml` |
| `tasa_por` | 100,000 | `config/modelado.yaml` |
| `log_transform` | `true` | `config/modelado.yaml` |
| `TS_SPLITS` | 4 | `config/modelado.yaml` |
| `TEST_SIZE` | 53 semanas | `config/modelado.yaml` |
| `cv_weights` | `[0.5, 0.75, 1.0, 1.25]` | `config/modelado.yaml` |
| `FECHA_CORTE` | 2025-01-01 | `config/modelado.yaml` |
| `umbral_minimo_semanal` | 0.5 | `config/modelado.yaml` |
| `modelado_hibrido` | `true` | `config/params.yaml` |
| `fourier_order` (nacional) | 5 | `config/modelado.yaml` |
| `fourier_order_regional` | 3 | `config/modelado.yaml` |
| `n_changepoints_regional` | 12 | `config/modelado.yaml` |
| `fold_timeout_seconds` | 35 | `config/modelado.yaml` |

</details>"""))

    # --- Celda 66: Footer ---
    cells.append(md(f"""\
{DIV}

*Notebook generado como parte del Avance 4 \u2014 Modelos Alternativos y Selecci\u00f3n del Modelo Final.*

*EpiForecast-MX \u2014 Equipo 01 \u2014 Febrero 2026*"""))

    return cells


# ---------------------------------------------------------------------------
# Ensamblaje final
# ---------------------------------------------------------------------------
def make_notebook():
    cells = []
    cells.extend(acto_0())
    cells.extend(acto_1())
    cells.extend(acto_2())
    cells.extend(acto_3())
    cells.extend(acto_4())
    cells.extend(acto_5())
    cells.extend(apendice())

    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3 (ipykernel)",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.12.0",
                "mimetype": "text/x-python",
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py",
            },
        },
        "cells": cells,
    }

    out = Path(__file__).parent / "Avance4.Equipo01.ipynb"
    out.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print(f"\nNotebook generado: {out}")
    print(f"Total de celdas: {len(cells)}")


if __name__ == "__main__":
    make_notebook()
