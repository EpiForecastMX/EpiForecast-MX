"""Project-wide constants for EpiForecast-MX."""

from typing import Final

# ICD-10 condition codes
CONDITIONS: Final[dict[str, str]] = {
    "F32": "Depresión",
    "G20": "Parkinson",
    "G30": "Alzheimer",
}

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
