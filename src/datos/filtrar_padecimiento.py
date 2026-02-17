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
        self.df_raw_filtrado = pd.DataFrame()
    

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

        if self.padecimiento.lower() == 'general':
            logger.info("Tipo 'General' configurado: se retornan todos los registros sin filtrar.")
            self.df_raw_filtrado = self.df_raw.copy()
            return True

        logger.info(f"Filtrando por '{self.padecimiento}' en columna '{self.columna}'")

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
                    f"Sin resultados: ningún registro coincide con '{self.padecimiento}'."
                )
                return None

            if filtrados == total_registros:
                logger.info(f"Sin filtrado aplicado. Total de registros: {filtrados:,}")
                return self.df_raw_filtrado

            logger.success(
                f"Filtrado completado: {filtrados:,} de {total_registros:,} registros "
                f"({(filtrados/total_registros)*100:.2f}%)"
            )
            return self.df_raw_filtrado

        else:
            return None
