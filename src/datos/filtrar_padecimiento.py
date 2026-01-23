# src/datos/filtrar_padecimiento.py
import pandas as pd
from loguru import logger

class FiltraPadecimiento:

    def __init__(self,
                 df: pd.DataFrame,
                 padecimiento : dict
                 ):
        
        self.df_raw = df.copy()
        self.columna = padecimiento.get("columna")
        self.padecimiento = padecimiento.get("tipo")
        self.df_raw_filtrado = pd.DataFrame
    

    def _filtrar_padecimiento(self) -> bool:

        if self.df_raw.empty:
            logger.error("No se puede filtrar: DataFrame vacío.")
            return False

        if self.columna not in self.df_raw.columns:
            logger.error(f"No se puede filtrar: la columna '{self.columna}' no existe en el DataFrame.")
            return False

        if not self.padecimiento:
            logger.error("No se puede filtrar: el tipo de padecimiento no está definido.")
            return False

        logger.info(f"Filtrando datos por padecimiento '{self.padecimiento}' en columna '{self.columna}'")

        self.df_raw_filtrado = self.df_raw[
            self.df_raw[self.columna]
            .astype(str)
            .str.contains(self.padecimiento, case=False, na=False)
        ]

        return True

    def run(self) -> pd.DataFrame:

        if self._filtrar_padecimiento():
            total_registros = len(self.df_raw)
            filtrados = len(self.df_raw_filtrado)

            if filtrados == 0:
                logger.error(
                    f"No se encontraron registros para el padecimiento {self.padecimiento}."
                )
                return None

            logger.success(
                f"Registros filtrados: {filtrados} de {total_registros} "
                f"({(filtrados/total_registros)*100:.2f}% del total)"
            )
            return self.df_raw_filtrado

        else:
            return None
