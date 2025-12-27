import pandas as pd
from src.configuraciones.config_params import conf, logger

class CleanDataset:
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.columas_a_eliminar = conf["columnas_eliminar"]

    def elimina_columnas(self) -> pd.DataFrame:
        """Elimina columnas indicadas en el archivo de configuración."""

        logger.info(f'Eliminando columnas : {self.columas_a_eliminar}')
        self.df.drop(columns=self.columas_a_eliminar, inplace=True, errors='ignore')

        return self.df

    def run(self) -> pd.DataFrame:
        
        self.elimina_columnas()
        
        return self.df