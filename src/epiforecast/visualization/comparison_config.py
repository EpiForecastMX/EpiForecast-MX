# src/epiforecast/visualization/comparison_config.py
"""Visual configuration for model comparison charts (OCP-friendly)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelStyle:
    """Visual style definition for a forecast model."""

    key: str
    label: str
    color: str
    grid_pos: tuple[int, int]


MODEL_STYLES: dict[str, ModelStyle] = {
    "prophet": ModelStyle("prophet", "Prophet", "#2E7D32", (0, 0)),
    "deepar": ModelStyle("deepar", "DeepAR", "#6A1B9A", (0, 1)),
    "ensemble": ModelStyle("ensemble", "Ensemble", "#E65100", (1, 0)),
    "stacking": ModelStyle("stacking", "Stacking", "#1A237E", (1, 1)),
}

COLOR_REAL = "#D3D3D3"
COLOR_REAL_OVERLAY = "#616161"
COLOR_CUTOFF = "#B71C1C"
COVID_FILL = "#E0E0E0"
