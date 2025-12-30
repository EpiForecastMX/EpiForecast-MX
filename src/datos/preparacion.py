import pandas as pd
import matplotlib.pyplot as plt
from loguru import logger

from src.configuraciones.config_params import conf

class dataPreparation:
        
    def __init__(self, df: pd.DataFrame):
            self.df = df.copy()
            self.df_interim = pd.DataFrame

    
    def _agrupa_dataset(self):
         
        df_pivot = self.df.pivot_table(
            index=["Año", "Semana", "Entidad"],
            columns="Ax_003",
            values="Valor",
            aggfunc="first"
        ).reset_index()

        df_pivot = df_pivot.rename(columns={
            "Sem.": "Casos_Semanal_Total",
            "H": "Casos_Acum_Hombres",
            "M": "Casos_Acum_Mujeres"
        })

        self.df_interim = df_pivot

    def _valida_consistencia(self):
         
        logger.info(self.df_interim)
         
        


    def run(self) -> pd.DataFrame:
        
        self._agrupa_dataset()
        self._valida_consistencia()