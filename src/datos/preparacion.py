# src/datos/preparacion.py
import pandas as pd
import matplotlib.pyplot as plt
from loguru import logger

from src.configuraciones.config_params import conf
from src.utils.datos import OperacionesDatos

class dataPreparation:
        
    def __init__(self, df: pd.DataFrame):
            self.df = df.copy()
            self.df_interim = pd.DataFrame

    
    def _agrupa_dataset(self):
         
        self.df_interim = self.df.pivot_table(
            index=["Año", "Semana", "Entidad"],
            columns="Ax_003",
            values="Valor",
            aggfunc="first"
        ).reset_index()

        self.df_interim = self.df_interim.rename(columns={
            "H": "Casos_Hombres_acum",
            "M": "Casos_Mujeres_acum"
        })

        self.df_interim  = self.df_interim .sort_values(["Entidad", "Año", "Semana"])

        self.df_interim["Fecha"] = pd.to_datetime(
        self.df_interim["Año"].astype(str) + self.df_interim["Semana"].astype(str).str.zfill(2) + "1",
        format="%G%V%u"
        )
        
        self.df_interim["casos_semanales_acum"] = self.df_interim["Casos_Hombres_acum"] + self.df_interim["Casos_Mujeres_acum"]
        self.df_interim["casos_semanales_dif"] = self.df_interim["casos_semanales_acum"].diff()

        iqr, rango = OperacionesDatos.outliers_iqr(self.df_interim,"casos_semanales_acum", factor=1.5)
        logger.info(f"\n{iqr}")
        logger.info(f"\n{rango}")
        

        
        

        casos_nacionales = self.df_interim.groupby("Fecha")["casos_semanales_dif"].sum()
        #clip limita los valores de una Serie o DataFrame dentro de un rango.
        casos_nacionales = casos_nacionales.clip(lower=0)


        """
        #esto da una grafica muy parecida ...
        casos_nacionales = casos_nacionales.drop("2016-05-16")
        casos_nacionales = casos_nacionales[casos_nacionales != 0 ]

        plt.figure(figsize=(16, 6))
        plt.plot(casos_nacionales.index, casos_nacionales.values, label='Total de Casos Nacionales', color='navy')

        plt.title('Casos Semanales de Alzheimer a Nivel Nacional (Evolución 2014-2024)')
        plt.xlabel('Año')
        plt.ylabel('Número de Nuevos Casos')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.legend()
        plt.show()

        """



         
    def run(self) -> pd.DataFrame:
        
        self._agrupa_dataset()
