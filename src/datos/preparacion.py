# src/datos/preparacion.py
import pandas as pd
import matplotlib.pyplot as plt
from loguru import logger

from src.configuraciones.config_params import conf
from src.utils.datos import OperacionesDatos

from pathlib import Path

class dataPreparation:
        
    def __init__(self, df: pd.DataFrame):
            self.df = df.copy()
            self.df_interim = pd.DataFrame

    
    def _agrupa_dataset(self):
        
        self.df = self.df.sort_values(by=["Anio", "Entidad", "Semana"]).reset_index(drop=True)

        self.df["Prev_hombres"] = self.df.groupby("Entidad")["Acumulado_hombres"].shift()
        self.df["Prev_mujeres"] = self.df.groupby("Entidad")["Acumulado_mujeres"].shift()

        # Calcular incrementos usando el valor anterior
        self.df["Incremento_hombres"] = self.df["Acumulado_hombres"] - self.df["Prev_hombres"]
        self.df["Incremento_mujeres"] = self.df["Acumulado_mujeres"] - self.df["Prev_mujeres"]

        # Regla especial: Semana 2 diferencia = valor acumulado
        mask_semana2 = self.df["Semana"] == 2
        self.df.loc[mask_semana2, "Incremento_hombres"] = self.df.loc[mask_semana2, "Acumulado_hombres"]
        self.df.loc[mask_semana2, "Incremento_mujeres"] = self.df.loc[mask_semana2, "Acumulado_mujeres"]






        # Mostrar las primeras filas
        prueba = Path(conf["paths"]["interim"]) / "prueba.csv"

        self.df.to_csv(prueba, index=False)

        """
        por limpiar, eliminar semana 53, como la primer semana considera la ultima
        semana del año pasado, mejor lo consideramos como semana 52
        """





         
        #self.df_interim = self.df.pivot_table(
        #    index=["Año", "Semana", "Entidad"],
        #    columns="Ax_003",
        #    values="Valor",
        #    aggfunc="first"
        #).reset_index()

        #self.df_interim = self.df_interim.rename(columns={
        #    "H": "Casos_Hombres",
        #    "M": "Casos_Mujeres"
        #})

        #self.df_interim  = self.df_interim .sort_values(["Entidad", "Año", "Semana"])

        #logger.info(f'\n{self.df_interim}')

        #self.df_interim["Fecha"] = pd.to_datetime(
        #self.df_interim["Año"].astype(str) + self.df_interim["Semana"].astype(str).str.zfill(2) + "1",
        #format="%G%V%u"
        #)
        
        #self.df_interim["casos_semanales_acum"] = self.df_interim["Casos_Hombres_acum"] + self.df_interim["Casos_Mujeres_acum"]
        #self.df_interim["casos_semanales_dif"] = self.df_interim["casos_semanales_acum"].diff()

        #iqr, rango = OperacionesDatos.outliers_iqr(self.df_interim,"casos_semanales_acum", factor=1.5)
        #logger.info(f"\n{iqr}")
        #logger.info(f"\n{rango}")
        

        
        

        #casos_nacionales = self.df_interim.groupby("Fecha")["casos_semanales_dif"].sum()
        #clip limita los valores de una Serie o DataFrame dentro de un rango.
        #casos_nacionales = casos_nacionales.clip(lower=0)


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
