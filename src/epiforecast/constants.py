"""Project-wide constants for EpiForecast-MX."""

from typing import Final

# Reproducibility
RANDOM_SEED: Final[int] = 42

# COVID-19 pandemic period (aligned with config/visualization/plots.yaml)
COVID_START: Final[str] = "2020-03-15"
COVID_END: Final[str] = "2022-09-22"

# COVID-19 visualization colors
COVID_SPAN_COLOR: Final[str] = "#E53935"
COVID_TEXT_COLOR: Final[str] = "#C62828"
COVID_BADGE_FC: Final[str] = "#FFEBEE"
COVID_BADGE_EC: Final[str] = "#EF9A9A"

# Default visualization DPI
VIZ_DPI_SCREEN: Final[int] = 200
VIZ_DPI_PRINT: Final[int] = 300

# Percentage multiplier (avoids magic `* 100` scattered in code)
PCT_MULTIPLIER: Final[int] = 100

# ICD-10 condition codes
CONDITIONS: Final[dict[str, str]] = {
    "F32": "Depresión",
    "G20": "Parkinson",
    "G30": "Alzheimer",
}

# Cohorte neurológica / salud mental en producción (333 modelos). Distinta de Dengue,
# que se incorpora con su propio pipeline. Los flujos neuro (entrenamiento en modo
# "General", re-selección de motor) deben filtrar a esta lista para NO procesar Dengue
# antes de que tenga su configuración, modelos y forecasts propios.
NEURO_CONDITIONS: Final[list[str]] = ["Depresión", "Parkinson", "Alzheimer"]

# Nombres de entidad para DISPLAY (gráficos, tablas, reportes). El dato se almacena con
# el nombre canónico INEGI ("México"), pero al mostrarse debe distinguirse del país:
# "México" (entidad) → "Estado de México".
ENTIDAD_DISPLAY: Final[dict[str, str]] = {"México": "Estado de México"}

# Mexican states (32 entities)
STATES: Final[list[str]] = [
    "Aguascalientes",
    "Baja California",
    "Baja California Sur",
    "Campeche",
    "Chiapas",
    "Chihuahua",
    "Ciudad de México",
    "Coahuila",
    "Colima",
    "Durango",
    "Guanajuato",
    "Guerrero",
    "Hidalgo",
    "Jalisco",
    "México",
    "Michoacán",
    "Morelos",
    "Nayarit",
    "Nuevo León",
    "Oaxaca",
    "Puebla",
    "Querétaro",
    "Quintana Roo",
    "San Luis Potosí",
    "Sinaloa",
    "Sonora",
    "Tabasco",
    "Tamaulipas",
    "Tlaxcala",
    "Veracruz",
    "Yucatán",
    "Zacatecas",
]

# INEGI mental health regions
INEGI_REGIONS: Final[list[str]] = [
    "Urbana media",
    "Sur-Sureste vulnerable",
    "Metropolitana alta",
    "Rural / dispersa",
]

# Sex categories
SEX_MODES: Final[list[str]] = ["general", "hombres", "mujeres"]

# Rate normalization
RATE_PER: Final[int] = 100_000

# Cross-validation defaults
CV_INITIAL_DAYS: Final[int] = 730
CV_PERIOD_DAYS: Final[int] = 56
CV_HORIZON_DAYS: Final[int] = 168
