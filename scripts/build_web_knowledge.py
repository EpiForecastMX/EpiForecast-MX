"""Genera knowledge.json para el sitio web estatico de EpiForecast-MX.

Reutiliza ProjectDataCache y KnowledgeBase del proyecto para exportar
todos los datos necesarios a un JSON consumible por el frontend.

Uso:
    python scripts/build_web_knowledge.py
"""

from datetime import datetime
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


def build_static_data() -> dict[str, Any]:
    """Datos estaticos del proyecto."""
    equipo = [
        {
            "nombre": "Javier Augusto Rebull Saucedo",
            "apodo": "JAR",
            "matricula": "A01795838",
            "rol": "Líder técnico y arquitecto principal del pipeline MLOps",
            "empleo": "Senior Associate Developer en Santander Bank US",
            "commits": 820,
            "aliases": [
                "javier",
                "javi",
                "jar",
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
        **build_static_data(),
    }

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
