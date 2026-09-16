# src/epiforecast/models/prediction.py
"""Model loader and predictor (Polymorphic via ModelFactory).

Delegates loading and prediction to the specific model implementation.
"""

from pathlib import Path
from typing import Any

import pandas as pd

from epiforecast.models import create_model
from epiforecast.utils.config import conf
from epiforecast.utils.semana_epi import semana_boletin_de_ds


def _banda_degenerada(df: pd.DataFrame) -> bool:
    """True si faltan los límites, vienen vacíos o su ancho es nulo."""
    if not {"yhat_lower", "yhat_upper"} <= set(df.columns):
        return True
    ancho = (
        pd.to_numeric(df["yhat_upper"], errors="coerce")
        - pd.to_numeric(df["yhat_lower"], errors="coerce")
    ).abs()
    if not bool(ancho.notna().any()):
        return True
    return float(ancho.max(skipna=True)) < 1e-6


def _como_fecha(valor: Any) -> "pd.Timestamp | None":
    """Convierte el corte declarado por el motor a fecha, o ``None`` si no es utilizable.

    Un motor puede no declarar su corte, o declararlo en un tipo que no es una fecha. En ese caso
    la procedencia queda ausente: es preferible una columna vacía a una fase inventada que luego
    alguien lea como cierta.
    """
    if valor is None:
        return None
    try:
        fecha = pd.Timestamp(valor)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(fecha) else fecha


class ForecastModelLoader:
    """Unified model loader that works with any registered model type."""

    def __init__(
        self,
        periodo: int,
        model_path: Path,
        config: dict[str, Any] | None = None,
        padecimiento: str | None = None,
    ):
        """Inicializa el cargador de modelos.

        Args:
            periodo:      Horizonte de predicción en semanas.
            model_path:   Ruta al archivo del modelo serializado.
            config:       Dict de configuración (default: conf global de YAML).
            padecimiento: Padecimiento del modelo. Determina la inversión de
                transformaciones (log1p / tasa) en predict, que deben coincidir con
                las usadas al entrenar. Se pasa SOLO para cohortes no-neuro (Dengue):
                la cohorte neuro conserva su path histórico (padecimiento=None), cuya
                salida productiva está validada/publicada. Sin esto, un modelo Dengue
                (entrenado en log1p de conteos) saldría en escala log.
        """
        self._conf = config if config is not None else conf
        self.model_path = Path(model_path)
        self.periodo = periodo

        # Determinar modelo_activo de la configuración
        self.modelo_activo = self._conf.get("modelo_activo", "prophet")

        # Instanciar el forecaster correspondiente
        self.forecaster = create_model(
            self.modelo_activo, config=self._conf, padecimiento=padecimiento
        )

    def load(self) -> None:
        """Delegate loading to the forecaster implementation."""
        self.forecaster.load(self.model_path)

    def predict(self) -> pd.DataFrame:
        """Delegate prediction to the forecaster implementation."""
        return self.forecaster.predict(self.periodo)

    def run(self) -> pd.DataFrame:
        """Load model and generate predictions in one call."""
        self.load()
        return self._sella_procedencia(self.predict())

    def _sella_procedencia(self, df: pd.DataFrame) -> pd.DataFrame:
        """Marca cada fila con el corte de ajuste, su fase y su adelanto.

        ``predict`` devuelve el ajuste histórico y el futuro en un solo marco, sin nada que los
        distinga. Esa ausencia es la que permitió comparar como pronóstico lo que era ajuste
        dentro de la muestra. Aquí se sella, en el único punto por donde pasan los cuatro
        motores, para que la distinción viaje con el dato y no dependa de quien lo lea.

        - ``ultimo_ds_ajustado``: última fecha que consumió el ajuste final.
        - ``anio_boletin_corte`` y ``semana_boletin_corte``: ese corte en el calendario del
          boletín, con la regla canónica.
        - ``fase_modelo``: ``ajuste`` o ``pronostico``.
        - ``adelanto_semanas``: semanas transcurridas desde el corte; 0 en el tramo ajustado.
        """
        df = df.copy()
        corte = _como_fecha(self.forecaster.ultimo_ds_ajustado)
        if corte is None or "ds" not in df.columns:
            for col in ("ultimo_ds_ajustado", "anio_boletin_corte", "semana_boletin_corte"):
                df[col] = pd.NA
            df["fase_modelo"] = pd.NA
            df["adelanto_semanas"] = pd.NA
            return df
        ds = pd.to_datetime(df["ds"])
        semana = semana_boletin_de_ds(corte)
        df["ultimo_ds_ajustado"] = corte
        df["anio_boletin_corte"] = semana.anio
        df["semana_boletin_corte"] = semana.semana
        df["fase_modelo"] = ["pronostico" if f else "ajuste" for f in ds > corte]
        df["adelanto_semanas"] = ((ds - corte).dt.days // 7).clip(lower=0)
        return self._sella_intervalo(df)

    def _sella_intervalo(self, df: pd.DataFrame) -> pd.DataFrame:
        """Declara si el motor aporta intervalo propio y retira la banda degenerada.

        Ensemble y Stacking emiten ``lower = upper = yhat``. Eso no es un intervalo angosto: es la
        ausencia de intervalo, y quien lo lea puede dibujarlo como certeza. Aquí se vacía y se
        declara, para que la falta viaje explícita junto al dato.
        """
        nominal = getattr(self.forecaster, "intervalo_nominal", None)
        metodo = getattr(self.forecaster, "intervalo_metodo", None)
        disponible = nominal is not None and not _banda_degenerada(df)
        if not disponible:
            for col in ("yhat_lower", "yhat_upper"):
                if col in df.columns:
                    df[col] = pd.NA
        df["intervalo_disponible"] = disponible
        df["intervalo_nivel_nominal"] = nominal if disponible else pd.NA
        df["intervalo_metodo"] = metodo if disponible else pd.NA
        return df
