"""Genera knowledge.json para el sitio web estatico de EpiForecast-MX.

Reutiliza ProjectDataCache y KnowledgeBase del proyecto para exportar
todos los datos necesarios a un JSON consumible por el frontend.

Uso:
    python scripts/build_web_knowledge.py
"""

from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import Any
import unicodedata

import pandas as pd


def strip_accents(text: str) -> str:
    """Remueve acentos de un string (á→a, é→e, etc.)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Agregar src/ al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epi_modules.features.data_cache import ProjectDataCache  # noqa: E402
from epi_modules.features.knowledge_base import KnowledgeBase  # noqa: E402

from epiforecast.constants import ENTIDAD_DISPLAY  # noqa: E402
from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402
from epiforecast.utils.cohorts import filter_neuro  # noqa: E402
from epiforecast.utils.config import conf  # noqa: E402

OUTPUT = Path("web_dashboard/knowledge.json")


def _safe_int(v: Any) -> int | None:
    """Convierte a int si es numerico, None si no."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _safe_float(v: Any, decimals: int = 2) -> float | None:
    """Convierte a float redondeado si es numerico, None si no."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return round(float(v), decimals)
    except (ValueError, TypeError):
        return None


def _safe_str(v: Any) -> str | None:
    """Convierte a str sin acentos, None si NaN."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return strip_accents(str(v))


def _normalize_keys(obj: Any) -> Any:
    """Recursivamente normaliza claves de dicts (strip acentos)."""
    if isinstance(obj, dict):
        return {strip_accents(str(k)): _normalize_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_keys(item) for item in obj]
    if isinstance(obj, str):
        return strip_accents(obj)
    return obj


def build_prod_models(cache: ProjectDataCache) -> list[dict]:
    """Exporta los 333 modelos de produccion como lista de dicts."""
    prod = cache.prod_models
    if prod is None or prod.empty:
        return []

    cols = [
        "padecimiento",
        "entidad",
        "sexo",
        "modelo_produccion",
        "smape_prod",
        "mase_prod",
        "rmse_prod",
        "mae_prod",
        "casos_52_semanas_futuro",
        "overfitting",
        "leakage",
        "tipo_modelo",
        "pron_sem_previa",
        "realidad_sem_previa",
        "precision_historica",
    ]
    available = [c for c in cols if c in prod.columns]
    rows = []
    for _, r in prod[available].iterrows():
        row = {}
        for c in available:
            v = r[c]
            if c in ("smape_prod", "mase_prod", "rmse_prod", "mae_prod"):
                row[c] = _safe_float(v)
            elif c in ("casos_52_semanas_futuro", "pron_sem_previa", "realidad_sem_previa"):
                row[c] = _safe_int(v)
            elif c == "precision_historica":
                row[c] = _safe_str(v)
            else:
                row[c] = _safe_str(v)
        rows.append(row)
    return rows


def build_boletin(cache: ProjectDataCache) -> dict:
    """Pre-agrega datos del boletin para el frontend."""
    df = cache.boletin
    # Guard: el EpiBot público solo conoce la cohorte neuro de producción.
    # Excluye Dengue (en el consolidado pero sin respuestas/forecasts en el bot).
    if df is not None:
        df = filter_neuro(df)
    if df is None or df.empty:
        return {}

    result: dict[str, Any] = {}

    # Meta
    result["meta"] = {
        "total_registros": len(df),
        "min_anio": int(df["Anio"].min()),
        "max_anio": int(df["Anio"].max()),
        "max_semana": int(df[df["Anio"] == df["Anio"].max()]["Semana"].max()),
        "entidades": sorted(df["Entidad"].dropna().unique().tolist()),
        "padecimientos": sorted(df["Padecimiento"].dropna().unique().tolist()),
    }

    # Anual por padecimiento
    anual_pad: dict[str, dict[str, int]] = {}
    for pad in df["Padecimiento"].dropna().unique():
        sub = df[df["Padecimiento"] == pad]
        by_year = sub.groupby("Anio")["Casos_semana"].sum()
        anual_pad[str(pad)] = {str(int(y)): int(c) for y, c in by_year.items() if not pd.isna(c)}
    result["anual_por_pad"] = anual_pad

    # Anual por estado y padecimiento (top 10 estados por total)
    top_estados = (
        df.groupby("Entidad")["Casos_semana"]
        .sum()
        .sort_values(ascending=False)
        .head(15)
        .index.tolist()
    )
    anual_est: dict[str, dict[str, dict[str, int]]] = {}
    for est in top_estados:
        sub = df[df["Entidad"] == est]
        anual_est[str(est)] = {}
        for pad in sub["Padecimiento"].dropna().unique():
            pad_sub = sub[sub["Padecimiento"] == pad]
            by_year = pad_sub.groupby("Anio")["Casos_semana"].sum()
            anual_est[str(est)][str(pad)] = {
                str(int(y)): int(c) for y, c in by_year.items() if not pd.isna(c)
            }
    result["anual_por_estado_pad"] = anual_est

    # Ultima semana
    max_year = int(df["Anio"].max())
    max_week = int(df[df["Anio"] == max_year]["Semana"].max())
    latest = df[(df["Anio"] == max_year) & (df["Semana"] == max_week)]
    if not latest.empty:
        by_pad = latest.groupby("Padecimiento")["Casos_semana"].sum()
        result["ultima_semana"] = {
            "anio": max_year,
            "semana": max_week,
            "total": int(latest["Casos_semana"].sum()),
            "por_padecimiento": {str(p): int(c) for p, c in by_pad.items() if not pd.isna(c)},
        }

    # Ranking entidades (total historico)
    ranking = df.groupby("Entidad")["Casos_semana"].sum().sort_values(ascending=False)
    result["ranking_entidades"] = [
        {"entidad": str(e), "casos": int(c)} for e, c in ranking.head(20).items() if not pd.isna(c)
    ]

    # Semanal reciente (ultimas 12 semanas agregadas por padecimiento)
    recent = df[df["Anio"] == max_year].sort_values("Semana")
    last_weeks = sorted(recent["Semana"].unique())[-12:]
    semanal: list[dict] = []
    for w in last_weeks:
        w_data = recent[recent["Semana"] == w]
        entry: dict[str, Any] = {"semana": int(w), "total": int(w_data["Casos_semana"].sum())}
        for pad in df["Padecimiento"].dropna().unique():
            p_sub = w_data[w_data["Padecimiento"] == pad]
            entry[str(pad)] = int(p_sub["Casos_semana"].sum()) if not p_sub.empty else 0
        semanal.append(entry)
    result["semanal"] = semanal

    return result


def build_dengue_section() -> dict[str, Any]:
    """Sección de Dengue para el EpiBot, derivada de los artefactos de producción.

    Dengue es el 4.o padecimiento con pipeline propio (cohorte de conteos-log, no neuro):
    sus métricas y selección de motor NO comparten estructura con la neuro (333 modelos por
    tasa). Por eso se expone en su propia sección y NO se mezcla en ``stats.por_pad`` (evita
    que los handlers de comparación neuro la incluyan con métricas incompatibles).
    Fuente: ``produccion_dengue.csv`` (selector DeepAR/Prophet) + boletín consolidado + forecast.
    """
    reports = Path(conf["paths"]["reports"])
    prod_path = reports / "ProdDetails" / "produccion_dengue.csv"
    if not prod_path.exists():
        return {}
    prod = pd.read_csv(prod_path)
    dist = {str(k): int(v) for k, v in prod["motor_productivo"].value_counts().items()}
    nac = prod[(prod["entidad"] == "Nacional") & (prod["sexo"] == "general")]
    motor_nac = str(nac["motor_productivo"].iloc[0]) if len(nac) else "Prophet"
    # smape_ganador puede ser NaN si la serie cayó al criterio mae_real_casi_cero (imposible
    # para Nacional, pero el guard evita un TypeError si algún día ocurre).
    smape_nac = (
        round(float(nac["smape_ganador"].iloc[0]), 2)
        if len(nac) and pd.notna(nac["smape_ganador"].iloc[0])
        else None
    )

    df = cargar_boletin_dengue()
    ann = df.groupby("Anio")["Casos_semana"].sum()
    anual = {str(int(y)): int(c) for y, c in ann.items()}
    # Contexto 2014-2017 (esquema viejo A90/A91) para la gráfica de evolución del EpiBot:
    # prepende los años previos a la serie de modelado (otra clasificación, solo display).
    a9091 = Path(conf["paths"]["interim"]) / "dengue_a90a91_nacional.csv"
    if a9091.exists():
        old = pd.read_csv(a9091)
        old["tot"] = old["Acumulado_hombres"] + old["Acumulado_mujeres"]
        for y, c in old.groupby("Anio")["tot"].max().items():
            anual.setdefault(str(int(y)), int(c))
        anual = {y: anual[y] for y in sorted(anual)}
    pico_anio, pico_casos = int(ann.idxmax()), int(ann.max())
    total = df.groupby("Entidad")["Casos_semana"].sum().sort_values(ascending=False)
    top_ent = [
        {"entidad": ENTIDAD_DISPLAY.get(str(e), str(e)), "casos": int(c)}
        for e, c in total.head(6).items()
        if c > 0
    ]
    sin_casos = [ENTIDAD_DISPLAY.get(str(e), str(e)) for e, c in total.items() if c == 0]

    # Última semana real + pronóstico productivo nacional a 52 sem (motor productivo nacional).
    last = df[df["Anio"] == df["Anio"].max()]
    last_sem = int(last["Semana"].astype(int).max())
    last_real = pd.Timestamp(date.fromisocalendar(int(df["Anio"].max()), min(last_sem, 52), 1))

    # Forecast CSV por motor (cache) -> pronóstico 52 sem de una serie (entidad, general).
    _fc_cache: dict[str, pd.DataFrame] = {}

    def _fc_52sem(entidad: str, motor: str) -> int:
        key = motor.lower()
        if key not in _fc_cache:
            p = reports / "forecasts" / key / f"all_forecast_{key}.csv"
            _fc_cache[key] = pd.read_csv(p, low_memory=False) if p.exists() else pd.DataFrame()
        fc = _fc_cache[key]
        if fc.empty:
            return 0
        d = fc[
            (fc["meta_padecimiento"] == "Dengue")
            & (fc["meta_entidad"] == entidad)
            & (fc["meta_modo"] == "general")
        ].copy()
        if d.empty:
            return 0
        d["ds"] = pd.to_datetime(d["ds"])
        fut = d[d["ds"] > last_real].sort_values("ds").head(52)
        return int(fut["yhat"].clip(lower=0).sum())

    casos_fut: int | None = _fc_52sem("Nacional", motor_nac) or None

    # Pronóstico 52 sem POR ENTIDAD (motor productivo de cada serie general) — consistente con
    # el mapa neuro, que muestra casos pronosticados a 52 sem (no histórico).
    prod_gen = prod[
        (prod["sexo"] == "general")
        & (~prod["entidad"].isin(["Nacional"]))
        & (~prod["entidad"].astype(str).str.startswith("Region"))
    ]
    por_entidad_fc: dict[str, int] = {}
    for _, r in prod_gen.iterrows():
        ent_raw = str(r["entidad"])
        val = _fc_52sem(ent_raw, str(r["motor_productivo"]))
        if val > 0:
            por_entidad_fc[ENTIDAD_DISPLAY.get(ent_raw, ent_raw)] = val

    return {
        "cie": "A97",
        "cobertura": f"{int(df['Anio'].min())}-{int(df['Anio'].max())}",
        "n_boletines": int(df.groupby(["Anio", "Semana"]).ngroups),
        "n_entidades": int(df["Entidad"].nunique()),
        "n_series": int(len(prod)),
        "horizonte_semanas": 52,
        "proyeccion_anios": 5,
        "motores_entrenados": ["Prophet", "DeepAR", "Ensemble", "Stacking", "NBGLM"],
        "motores_productivos": ["DeepAR", "Prophet", "NBGLM"],
        "dist_motor": dist,
        "motor_nacional": motor_nac,
        "smape_nacional": smape_nac,
        "casos_futuro_nacional_52sem": casos_fut,
        "ultima_real": last_real.strftime("%Y-%m-%d"),
        "anual": anual,
        "anio_pico": pico_anio,
        "casos_pico": pico_casos,
        "anios_epidemicos": [2014, 2019, 2024],
        "ciclo_anios": "cuatro a cinco",
        "top_entidades": top_ent,
        "sin_casos": sin_casos,
        # Pronóstico 52 sem por entidad (motor productivo) para el mapa coroplético del EpiBot,
        # consistente con el mapa neuro (casos pronosticados a 52 sem, NO histórico).
        "por_entidad": por_entidad_fc,
        "unidad": "conteos absolutos (no tasa por 100 mil)",
        "notas": [
            "Serie de producción 2018-2026 (Cuadro 7.2 SINAVE, dengue confirmado A97.x agregado).",
            "La serie histórica 2014-2017 (taxonomía vieja A90/A91) es solo contexto/EDA, no entrena.",
            "5 motores entrenados; productivos DeepAR, Prophet y NBGLM (Negative-Binomial GLM "
            "con estacionalidad de Fourier y regresor El Niño/ONI). Los árboles (Ensemble, "
            "Stacking) no extrapolan la dinámica epidémica y quedan fuera de producción.",
            "Pronóstico preciso a 1 año (52 sem); además una proyección a 5 años ILUSTRATIVA que "
            "muestra el patrón estacional esperado, no la magnitud de la próxima epidemia.",
            "Los picos (2014, 2019, 2024) coinciden con años de El Niño; 2024 fue la mayor "
            "epidemia de dengue registrada en las Américas.",
        ],
    }


def build_dengue_weekly() -> dict[str, Any]:
    """Comparación semanal Real vs Pronóstico para Dengue (Nacional, general), para el
    'zoom semanal' del EpiBot. Misma forma que build_weekly_comparison (clave 'Dengue')."""
    prod_path = Path(conf["paths"]["reports"]) / "ProdDetails" / "produccion_dengue.csv"
    if not prod_path.exists():
        return {}
    prod = pd.read_csv(prod_path)
    nac = prod[(prod["entidad"] == "Nacional") & (prod["sexo"] == "general")]
    motor = str(nac["motor_productivo"].iloc[0]) if len(nac) else "DeepAR"

    df = cargar_boletin_dengue()
    anio = int(df["Anio"].max())
    real = df[df["Anio"] == anio].groupby("Semana")["Casos_semana"].sum().to_dict()

    base = Path(conf["paths"]["reports"]) / "forecasts"
    fc_motor: dict[str, dict[int, int]] = {}
    for m in ["Prophet", "DeepAR", "NBGLM"]:
        p = base / m.lower() / f"all_forecast_{m.lower()}.csv"
        if not p.exists():
            continue
        fdf = pd.read_csv(p, low_memory=False)
        fdf = fdf[
            (fdf["meta_padecimiento"] == "Dengue")
            & (fdf["meta_entidad"].fillna("Nacional") == "Nacional")
            & (fdf["meta_modo"] == "general")
        ].copy()
        fdf["ds"] = pd.to_datetime(fdf["ds"])
        fdf = fdf[fdf["ds"].dt.isocalendar().year == anio]
        fdf["wk"] = fdf["ds"].dt.isocalendar().week.astype(int)
        fc_motor[m.lower()] = {
            int(w): int(round(y)) for w, y in zip(fdf["wk"], fdf["yhat"], strict=False)
        }

    base_motor = motor.lower()
    semanas = []
    for wk in sorted(fc_motor.get(base_motor, {})):
        fecha = date.fromisocalendar(anio, min(wk, 52), 1).isoformat()
        entry: dict[str, Any] = {
            "semana": wk,
            "fecha": fecha,
            "pronostico": fc_motor[base_motor].get(wk),
        }
        if wk in real:
            entry["real"] = int(real[wk])
        for m, vals in fc_motor.items():
            if wk in vals:
                entry[m] = vals[wk]
        semanas.append(entry)
    return {
        "Dengue": {
            "modelo_productivo": base_motor,
            "anio": anio,
            "semanas_reales": len(real),
            "semanas_pronostico": len(semanas),
            "semanas": semanas,
        }
    }


def build_static_data() -> dict[str, Any]:
    """Datos estaticos del proyecto."""
    equipo = [
        {
            "nombre": "Javier Augusto Rebull Saucedo",
            "apodo": "JARS",
            "matricula": "A01795838",
            "rol": "Líder técnico y arquitecto principal del pipeline MLOps",
            "empleo": "Senior Associate Developer en Santander Bank US",
            "commits": 820,
            "aliases": [
                "javier",
                "javi",
                "jar",
                "jars",
                "rebull",
                "rebull saucedo",
                "javier rebull",
                "javier augusto",
            ],
        },
        {
            "nombre": "Juan Carlos Perez Nava",
            "apodo": "Jarcos",
            "matricula": "A01795941",
            "rol": "EDA, feature engineering y modelo Prophet base",
            "empleo": "Jefe de Área en el Instituto Mexicano del Seguro Social (IMSS)",
            "commits": 288,
            "aliases": [
                "juan",
                "juan carlos",
                "jarcos",
                "perez nava",
                "perez",
                "nava",
                "juan perez",
            ],
        },
        {
            "nombre": "Luis Gerardo Sanchez Salazar",
            "apodo": "Jerry",
            "matricula": "A01232963",
            "rol": "Diseño, desarrollo y optimización del dashboard",
            "empleo": "Senior Controls Engineer en Tesla",
            "commits": 201,
            "aliases": [
                "luis",
                "luis gerardo",
                "jerry",
                "sanchez salazar",
                "sanchez",
                "salazar",
                "luis sanchez",
                "gerardo",
            ],
        },
    ]

    padecimiento_info = {
        "Depresion": {
            "cie": "F32",
            "nombre_completo": "Episodio depresivo",
            "descripcion": (
                "Trastorno del estado de ánimo caracterizado por tristeza persistente, "
                "pérdida de interés, fatiga y alteraciones del sueño. Principal causa "
                "de discapacidad a nivel mundial según la OMS."
            ),
            "efectos": [
                "Deterioro cognitivo",
                "Alteraciones del apetito",
                "Insomnio o hipersomnia",
                "Mayor riesgo cardiovascular",
                "Debilitamiento del sistema inmunológico",
            ],
            "nota_mexico": (
                "Padecimiento con mayor incidencia de los tres. Afecta predominantemente "
                "a mujeres (proporción ~3:1) con estacionalidad marcada post-vacacional."
            ),
        },
        "Parkinson": {
            "cie": "G20",
            "nombre_completo": "Enfermedad de Parkinson",
            "descripcion": (
                "Trastorno neurodegenerativo progresivo por pérdida de neuronas "
                "dopaminérgicas. Temblor en reposo, rigidez muscular, bradicinesia "
                "e inestabilidad postural."
            ),
            "efectos": [
                "Temblores involuntarios",
                "Rigidez muscular",
                "Dificultad para caminar",
                "Problemas de deglución",
                "Trastornos del sueño",
                "Deterioro cognitivo avanzado",
            ],
            "nota_mexico": (
                "Incidencia moderada. Afecta ligeramente más a hombres, prevalencia "
                "crece con la edad. Estados del norte con tasas más elevadas."
            ),
        },
        "Alzheimer": {
            "cie": "G30",
            "nombre_completo": "Enfermedad de Alzheimer",
            "descripcion": (
                "Forma más común de demencia. Enfermedad neurodegenerativa progresiva que "
                "destruye neuronas, afectando memoria, pensamiento y comportamiento."
            ),
            "efectos": [
                "Pérdida progresiva de memoria",
                "Desorientación temporal y espacial",
                "Dificultad para planificar",
                "Cambios de personalidad",
                "Pérdida de autonomía",
                "Deterioro del lenguaje",
            ],
            "nota_mexico": (
                "Menor incidencia de los tres, tendencia creciente por envejecimiento "
                "poblacional. Jalisco, Chihuahua y Sinaloa con tasas más altas. "
                "SMAPE de predicción más elevado (>100%) por baja frecuencia."
            ),
        },
        "Dengue": {
            "cie": "A97",
            "nombre_completo": "Dengue",
            "descripcion": (
                "Arbovirosis transmitida por el mosquito Aedes aegypti, con estacionalidad "
                "climática anual (la carga vive en las semanas 27-52, época de lluvias) y "
                "grandes brotes epidémicos cada cuatro a cinco años. Puede evolucionar a "
                "dengue grave (hemorrágico)."
            ),
            "efectos": [
                "Fiebre alta súbita",
                "Dolor articular y muscular intenso",
                "Cefalea y dolor retroocular",
                "Erupción cutánea",
                "Hemorragias y choque en el dengue grave",
            ],
            "nota_mexico": (
                "Endémico en el sureste tropical y las costas (Jalisco, Veracruz, Chiapas y "
                "Guerrero concentran la carga); el centro-altiplano (Ciudad de México, Tlaxcala) "
                "no registra transmisión confirmada. 2024 fue la mayor epidemia en las Américas. "
                "Se modela como conteos absolutos (no tasa), con DeepAR y Prophet en producción."
            ),
        },
    }

    training_config = {
        "fecha_corte": "2025-01-01",
        "horizonte": 52,
        "series_totales": 333,
        "geografias": 37,
        "modelos": {
            "Prophet": {
                "cv_folds": 4,
                "test_size": 53,
                "cv_weights": [0.5, 0.75, 1.0, 1.25],
                "estacionalidad": "multiplicativa (Depresion, Parkinson), aditiva (Alzheimer)",
                "grid": {
                    "Depresion": "changepoint_prior_scale=[0.05,0.1,0.5], seasonality_prior_scale=[1,5,10]",
                    "Parkinson": "changepoint_prior_scale=[0.01,0.05,0.1], seasonality_prior_scale=[0.5,1,5]",
                    "Alzheimer": "changepoint_prior_scale=[0.01,0.05,0.1], seasonality_prior_scale=[0.5,1,5]",
                },
            },
            "DeepAR": {
                "context_length": 104,
                "prediction_length": 52,
                "epochs": 300,
                "early_stopping_patience": 15,
                "capas": "2 LSTM, 40 celdas",
                "dropout": 0.1,
                "learning_rate": 0.001,
                "batch_size": 32,
            },
            "Ensemble": {
                "componentes": "Prophet + XGBoost",
                "oof_cutoff": "2024-01-01",
                "xgb_cv_splits": 4,
                "xgb_test_size": 26,
                "xgb_params": "n_estimators=500, max_depth=4, lr=0.05, subsample=0.8",
            },
            "Stacking": {
                "componentes": "Prophet + ETS + LightGBM + Ridge",
                "oof_cutoff": "2024-01-01",
                "oof_folds": 4,
                "min_train": 104,
                "meta_learner": "Ridge con pesos no negativos",
                "expertos": ["ProphetExpert", "ETSExpert", "LGBMExpert"],
            },
        },
        "eventos": {
            "covid": {
                "inicio": "2020-03-23",
                "fin": "2022-09-22",
                "duracion_semanas": 130,
            },
            "tabasco_regimen": {
                "fecha": "2023-01-09",
                "duracion_dias": 365,
                "padecimiento": "Depresion",
            },
        },
    }

    definiciones = {
        "SMAPE": "Symmetric Mean Absolute Percentage Error. Métrica primaria de selección (0-200%). Menor es mejor.",
        "MASE": "Mean Absolute Scaled Error. Métrica de desempate (umbral 5%). Menor es mejor. <1 supera naive.",
        "RMSE": "Root Mean Squared Error. Segundo desempate. Sensible a errores grandes.",
        "MAE": "Mean Absolute Error. Error promedio absoluto en unidades de casos.",
        "Overfitting": "Ratio smape_test/smape_train. Alto (>2×), Moderado (>1.3×), OK.",
        "Leakage": "smape_train < 0.5% indica posible fuga de datos del test al train.",
        "Fallback regional": "Serie con incidencia insuficiente (<5 casos/52sem) usa el modelo de su región INEGI.",
        "Cross Validation": "Validación cruzada temporal con ventanas deslizantes (time series split).",
        "Horizonte": "Período de pronóstico: 52 semanas hacia adelante desde la fecha de corte.",
        "CIE-10": "Clasificación Internacional de Enfermedades, 10a revisión (OMS).",
    }

    regiones = {
        "Metropolitana alta": [
            "Ciudad de México",
            "Jalisco",
            "México",
            "Nuevo León",
        ],
        "Urbana media": [
            "Aguascalientes",
            "Baja California",
            "Baja California Sur",
            "Chihuahua",
            "Coahuila",
            "Colima",
            "Durango",
            "Guanajuato",
            "Morelos",
            "Querétaro",
            "San Luis Potosí",
            "Sinaloa",
            "Sonora",
            "Tamaulipas",
            "Zacatecas",
        ],
        "Rural / dispersa": [
            "Guerrero",
            "Hidalgo",
            "Michoacán",
            "Nayarit",
            "Puebla",
            "Tlaxcala",
            "Veracruz",
        ],
        "Sur-Sureste vulnerable": [
            "Campeche",
            "Chiapas",
            "Oaxaca",
            "Quintana Roo",
            "Tabasco",
            "Yucatán",
        ],
    }

    infra = {
        "tests": 855,
        "lineas_codigo": 13000,
        "cobertura": 92,
        "archivos_test": 46,
        "evaluaciones_totales": 1332,
        "ci_cd": "GitHub Actions (lint + typecheck + tests)",
        "sagemaker": "ml.g4dn.xlarge (NVIDIA T4), cuenta 564141855321",
        "bucket_s3": "s3://epiforecast-mx-data",
    }

    return {
        "equipo": equipo,
        "padecimiento_info": padecimiento_info,
        "training_config": training_config,
        "definiciones": definiciones,
        "regiones": regiones,
        "infra": infra,
    }


def build_weekly_comparison(cache: ProjectDataCache) -> dict[str, list[dict]]:
    """Genera comparacion semanal Real vs Pronostico para 2026.

    Para cada padecimiento (Nacional, general), alinea semanas del boletin
    con el pronostico del modelo productivo (tableau.csv).
    """
    result: dict[str, list[dict]] = {}

    # Boletin: actual cases (solo cohorte neuro; Dengue tiene su propio pipeline)
    bol = cache.boletin
    if bol is not None:
        bol = filter_neuro(bol)
    if bol is None or bol.empty:
        return result

    max_year = int(bol["Anio"].max())
    bol_year = bol[bol["Anio"] == max_year]
    if bol_year.empty:
        return result

    # Aggregate Nacional by week + padecimiento
    nac_actual = bol_year.groupby(["Semana", "Padecimiento"])["Casos_semana"].sum().reset_index()

    # Modelo productivo canónico desde la tabla productiva (no desde tableau.csv,
    # que puede quedar stale). Usa el motor productivo del par (Nacional, general).
    prod = cache.prod_models
    if prod is None or prod.empty:
        return result
    prod_lookup: dict[str, str] = {}
    nac_general = prod[(prod["entidad"] == "Nacional") & (prod["sexo"] == "general")]
    for _, r in nac_general.iterrows():
        pad_key = strip_accents(str(r["padecimiento"]))
        prod_lookup[pad_key] = str(r.get("modelo_produccion") or "?")

    # Cargar los 4 forecasts directamente para construir las series semanales
    forecast_paths = {
        "prophet": Path("reports/forecasts/prophet/all_forecast_prophet.csv"),
        "deepar": Path("reports/forecasts/deepar/all_forecast_deepar.csv"),
        "ensemble": Path("reports/forecasts/ensemble/all_forecast_ensemble.csv"),
        "stacking": Path("reports/forecasts/stacking/all_forecast_stacking.csv"),
    }
    fc_per_motor: dict[str, pd.DataFrame] = {}
    for motor, p in forecast_paths.items():
        if not p.exists():
            continue
        df = pd.read_csv(
            p,
            usecols=["ds", "yhat", "meta_padecimiento", "meta_entidad", "meta_modo"],
            low_memory=False,
        )
        df["ds"] = pd.to_datetime(df["ds"])
        iso_cal = df["ds"].dt.isocalendar()
        df = df[
            (df["meta_entidad"] == "Nacional")
            & (df["meta_modo"] == "general")
            & (iso_cal.year == max_year)
        ].copy()
        df["iso_week"] = df["ds"].dt.isocalendar().week.astype(int)
        fc_per_motor[motor] = df.rename(columns={"meta_padecimiento": "padecimiento"})

    for pad_raw in nac_actual["Padecimiento"].unique():
        pad = strip_accents(str(pad_raw))
        modelo_prod_raw = prod_lookup.get(pad, "?")
        modelo_prod = strip_accents(str(modelo_prod_raw)).lower()

        # Actual weeks
        actual_weeks = (
            nac_actual[nac_actual["Padecimiento"] == pad_raw]
            .set_index("Semana")["Casos_semana"]
            .to_dict()
        )

        # Tomar las semanas del motor productivo como base
        base_motor = modelo_prod if modelo_prod in fc_per_motor else next(iter(fc_per_motor))
        base_df = fc_per_motor[base_motor]
        base_df = base_df[base_df["padecimiento"] == pad_raw].sort_values("ds")
        if base_df.empty:
            # Algunos forecasts usan padecimientos sin acentos
            alt = strip_accents(str(pad_raw))
            base_df = fc_per_motor[base_motor]
            base_df = base_df[base_df["padecimiento"] == alt].sort_values("ds")
        if base_df.empty:
            continue

        weeks: list[dict] = []
        for _, row in base_df.iterrows():
            w = int(row["iso_week"])
            forecast = int(round(row["yhat"]))
            actual = int(actual_weeks.get(w, 0)) if w in actual_weeks else None
            entry: dict[str, Any] = {
                "semana": w,
                "fecha": row["ds"].strftime("%Y-%m-%d"),
                "pronostico": forecast,
            }
            if actual is not None:
                entry["real"] = actual
                if actual > 0:
                    error_pct = round(abs(forecast - actual) / actual * 100, 1)
                    entry["error_pct"] = error_pct
            # Forecast de cada motor para esa semana (mismo padecimiento, Nacional, general)
            for motor, mdf in fc_per_motor.items():
                m_pad = mdf[(mdf["padecimiento"].isin([pad_raw, pad])) & (mdf["iso_week"] == w)]
                if not m_pad.empty:
                    entry[motor] = int(round(m_pad["yhat"].iloc[0]))
            weeks.append(entry)

        result[pad] = {
            "modelo_productivo": modelo_prod,
            "anio": max_year,
            "semanas_reales": len(actual_weeks),
            "semanas_pronostico": len(weeks),
            "semanas": weeks,
        }

    return result


def _fill_horizon_dates(knowledge: dict[str, Any], cache: ProjectDataCache) -> None:
    """Rellena horizonte_inicio/horizonte_fin/ultimo_entrenamiento en training_config.

    kb.js (forecastDateRange) los lee para mostrar las fechas reales del
    horizonte de pronostico; sin ellos el bot degrada a "52 semanas" sin fechas.
    """
    tc = knowledge.get("training_config")
    if not isinstance(tc, dict):
        return
    p = Path("reports/forecasts/prophet/all_forecast_prophet.csv")
    if not p.exists():
        return
    df = pd.read_csv(p, usecols=["ds"], low_memory=False)
    df["ds"] = pd.to_datetime(df["ds"])
    fin = df["ds"].max()
    inicio = None
    bol = cache.boletin
    if bol is not None and not bol.empty:
        bol = filter_neuro(bol)
        anio = int(bol["Anio"].max())
        sem = int(bol.loc[bol["Anio"] == anio, "Semana"].max())
        last_real = pd.Timestamp.fromisocalendar(anio, sem, 1)
        fut = df.loc[df["ds"] > last_real, "ds"]
        if not fut.empty:
            inicio = fut.min()
    if inicio is not None:
        tc["horizonte_inicio"] = inicio.date().isoformat()
    if pd.notna(fin):
        tc["horizonte_fin"] = fin.date().isoformat()
    tc["ultimo_entrenamiento"] = datetime.fromtimestamp(p.stat().st_mtime).date().isoformat()


def main() -> None:
    """Entry point: genera knowledge.json."""
    print("Cargando datos del proyecto...")
    cache = ProjectDataCache()
    kb = KnowledgeBase(cache)

    # Forzar calculo de stats
    stats = kb._ensure_stats()

    knowledge: dict[str, Any] = {
        "_generated": datetime.now().isoformat(),
        "_version": "1.0",
        "stats": _normalize_keys(stats),
        "prod_models": _normalize_keys(build_prod_models(cache)),
        "boletin": _normalize_keys(build_boletin(cache)),
        "weekly_comparison": _normalize_keys(
            {**build_weekly_comparison(cache), **build_dengue_weekly()}
        ),
        # Dengue: sección propia SIN normalizar (preserva tildes/eñes en estados y notas).
        "dengue": build_dengue_section(),
        **build_static_data(),
    }
    _fill_horizon_dates(knowledge, cache)

    # Serializar con NaN -> null
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    class NaNEncoder(json.JSONEncoder):
        def default(self, obj: Any) -> Any:
            if isinstance(obj, float) and pd.isna(obj):
                return None
            return super().default(obj)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(knowledge, f, ensure_ascii=False, indent=None, cls=NaNEncoder)

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Generado: {OUTPUT} ({size_kb:.0f} KB)")
    print(f"  - {len(knowledge.get('prod_models', []))} modelos de produccion")
    print(f"  - Stats: {len(stats)} claves")
    print(f"  - Boletin: {len(knowledge.get('boletin', {}))} secciones")


if __name__ == "__main__":
    main()
