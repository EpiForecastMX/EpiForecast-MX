"""Guards de plausibilidad para pronósticos (cohort-aware).

Los modelos de árboles (XGBoost de Ensemble, LightGBM de Stacking) no extrapolan
la dinámica epidémica del Dengue y divergen al alza en el horizonte (predicen
niveles de temporada alta durante la temporada baja). Un clamp por máximo GLOBAL
es inútil (el overshoot queda por debajo del pico histórico anual), así que se
acota con una ENVOLVENTE ESTACIONAL: cada semana del pronóstico se limita al
máximo histórico observado para esa misma semana epidemiológica del año, con un
margen. Es un guard de seguridad: para motores sanos (DeepAR/Prophet) casi nunca
se activa; para los divergentes evita pronósticos absurdos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Margen sobre el máximo histórico por semana-del-año. 1.5 = se permite hasta 50%
# por encima del peor valor jamás visto en esa semana (deja espacio a un brote
# récord sin dejar pasar la divergencia 10-100x de los árboles).
SEASONAL_CLAMP_FACTOR = 1.5


def clamp_seasonal_envelope(
    out: pd.DataFrame,
    history: pd.DataFrame,
    factor: float = SEASONAL_CLAMP_FACTOR,
    cols: tuple[str, ...] = ("yhat", "yhat_lower", "yhat_upper"),
) -> pd.DataFrame:
    """Acota las columnas de pronóstico a la envolvente estacional histórica.

    Args:
        out:     Pronóstico con columna ``ds`` y columnas en ``cols`` (escala conteos).
        history: Serie histórica con ``ds`` y ``y`` (conteos) para derivar el techo
                 por semana epidemiológica.
        factor:  Margen sobre el máximo histórico por semana.
        cols:    Columnas de pronóstico a acotar.

    Returns:
        ``out`` con las columnas acotadas (no muta el original).
    """
    if out.empty or history.empty or "y" not in history.columns:
        return out

    hist = history.copy()
    hist["ds"] = pd.to_datetime(hist["ds"])
    hist["woy"] = hist["ds"].dt.isocalendar().week.astype(int)
    per_week_max = hist.groupby("woy")["y"].max()
    global_max = float(hist["y"].max())
    # Techo por semana del año (fallback al máximo global si falta la semana).
    ceil_by_week = (per_week_max * factor).to_dict()
    global_ceil = global_max * factor

    out = out.copy()
    woy = pd.to_datetime(out["ds"]).dt.isocalendar().week.astype(int)
    ceil = woy.map(lambda w: ceil_by_week.get(int(w), global_ceil)).to_numpy(dtype=float)
    for col in cols:
        if col in out.columns:
            out[col] = np.minimum(out[col].to_numpy(dtype=float), ceil)
    return out
