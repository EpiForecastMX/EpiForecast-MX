"""Disease filter: select rows by ICD-10 code or condition name."""

# src/datos/filtro_padecimiento.py
from loguru import logger
import pandas as pd

from epiforecast.constants import NEURO_CONDITIONS
from epiforecast.utils.cohorts import filter_neuro


class FiltraPadecimiento:
    """Filtra un DataFrame epidemiológico por tipo de padecimiento configurado."""

    def __init__(self, df: pd.DataFrame, padecimiento: dict[str, str]):
        """Inicializa el filtro con el DataFrame y configuración de padecimiento.

        Args:
            df:            DataFrame de datos epidemiológicos crudos.
            padecimiento:  Dict con claves ``columna`` (nombre de columna) y ``tipo`` (valor a filtrar).
        """
        self.df_raw = df.copy()
        self.columna = padecimiento.get("columna")
        self.padecimiento = padecimiento.get("tipo")
        self.df_raw_filtrado = pd.DataFrame()

    def _filtrar_padecimiento(self) -> bool:
        if self.df_raw.empty:
            logger.error("No se puede filtrar: DataFrame vacío.")
            return False

        if self.columna not in self.df_raw.columns:
            logger.error(
                "No se puede filtrar: la columna '{}' no existe en el DataFrame.", self.columna
            )
            return False

        if not self.padecimiento:
            logger.error("No se puede filtrar: el tipo de padecimiento no está definido.")
            return False

        if self.padecimiento.lower() == "general":
            # Guard: 'General' = cohorte neurológica de producción (Depresión/Parkinson/
            # Alzheimer). Excluye Dengue (presente en el consolidado pero con su propio
            # pipeline); evita contaminar data_inegi_General/tableau/tabla_produccion.
            self.df_raw_filtrado = filter_neuro(self.df_raw, self.columna or "Padecimiento").copy()
            logger.info(
                "Tipo 'General': cohorte neuro {} | retenidos={} de {} (no-neuro excluidos)",
                NEURO_CONDITIONS,
                len(self.df_raw_filtrado),
                len(self.df_raw),
            )
            return True

        logger.info("Filtrando por '{}' en columna '{}'", self.padecimiento, self.columna)

        self.df_raw_filtrado = self.df_raw[
            self.df_raw[self.columna]
            .astype(str)
            .str.contains(self.padecimiento, case=False, na=False)
        ]

        return True

    def run(self) -> pd.DataFrame | None:
        """Ejecuta el filtrado y retorna el DataFrame filtrado, o None si falla."""

        if not self._filtrar_padecimiento():
            return None

        total_registros = len(self.df_raw)
        filtrados = len(self.df_raw_filtrado)

        if filtrados == 0:
            logger.error("Sin resultados: ningún registro coincide con '{}'.", self.padecimiento)
            return None

        if filtrados < total_registros:
            logger.success(
                "Filtrado completado | registros={:,} de {:,} ({:.2f}%)",
                filtrados,
                total_registros,
                (filtrados / total_registros) * 100,
            )

        return self.df_raw_filtrado
