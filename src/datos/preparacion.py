# src/datos/preparacion.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from loguru import logger

from src.utils.datos import OperacionesDatos

from src.configuraciones.config_params import conf
from src.datos.EDA import EDAReportBuilder
from src.utils.reporte_PDF import PDFReportGenerator

from pathlib import Path

class dataTransformation:
        
    def __init__(self, df: pd.DataFrame):
            self.df = df.copy()
            self.df_interim = pd.DataFrame
            self.opciones_reporte = conf['reporte_interim_stage_transformed']

    def _ajusta_semanas(self):
                 
        if not self.df['Semana'].between(1, 52).all():
            raise ValueError("Se encontraron semanas fuera del rango")

        # Identifica las filas donde la semana es 1. 
        # En esos casos, se hará un ajuste especial.
        filas_semana_1 = self.df['Semana'] == 1

        
        # Si la semana es 1, se cambia a 52.  
        # Para el resto, simplemente se resta 1 a la sema
        self.df['Semana'] = np.where(filas_semana_1, 52, self.df['Semana'] - 1)

        
        # Para las filas donde la semana era 1, también se resta 1 al año
        # porque la nueva semana 52 pertenece al año anterior.
        self.df.loc[filas_semana_1, 'Anio'] = self.df.loc[filas_semana_1, 'Anio'] - 1

        # Ordena el Dataframe de acuerdo con el año, entidad y semana
        self.df = self.df.sort_values(by=["Anio", "Entidad", "Semana"]).reset_index(drop=True)

    
    def _agrupa_dataset(self):

        self.df["Prev_hombres"] = self.df.groupby("Entidad")["Acumulado_hombres"].shift()
        self.df["Prev_mujeres"] = self.df.groupby("Entidad")["Acumulado_mujeres"].shift()

        # Calcular incrementos usando el valor anterior
        self.df["Incremento_hombres"] = self.df["Acumulado_hombres"] - self.df["Prev_hombres"]
        self.df["Incremento_mujeres"] = self.df["Acumulado_mujeres"] - self.df["Prev_mujeres"]

        # Regla especial: Semana 1 diferencia = valor acumulado
        semana_1 = self.df["Semana"] == 1
        self.df.loc[semana_1, "Incremento_hombres"] = self.df.loc[semana_1, "Acumulado_hombres"]
        self.df.loc[semana_1, "Incremento_mujeres"] = self.df.loc[semana_1, "Acumulado_mujeres"]

        #incluye fecha para poder realizar serie de tiempo
        self.df["Fecha"] = pd.to_datetime(
        self.df["Anio"].astype(str) + self.df["Semana"].astype(str).str.zfill(2) + "1",
        format="%G%V%u"
        )

        # Ajusta el año a aquellas fechas de la semana 1 que caen en año anterior
        filas_anio = (self.df['Semana'] == 1) & (self.df['Fecha'].dt.year < self.df['Anio'])
        self.df.loc[filas_anio, 'Fecha'] = pd.to_datetime(self.df.loc[filas_anio, 'Anio'].astype(str) + '-01-01')


    def _identifica_atipicos(self):
         
        df_outliers_hombres ,cuartiles_hombres = OperacionesDatos.outliers_iqr(self.df,'Incremento_hombres')
        df_outliers_mujeres ,cuartiles_mujeres = OperacionesDatos.outliers_iqr(self.df,'Incremento_mujeres')

        df_outliers_hombres = df_outliers_hombres.sort_values(by=["Anio", "Entidad", "Semana"]).reset_index(drop=True)
        
        mask_neg = df_outliers_hombres["Incremento_hombres"] < 0
        
        anio_prev    = df_outliers_hombres["Anio"].shift(1)
        semana_prev  = df_outliers_hombres["Semana"].shift(1)
        entidad_prev = df_outliers_hombres["Entidad"].shift(1)

        
        es_consecutivo = (
        (df_outliers_hombres["Anio"] == anio_prev) &
        (df_outliers_hombres["Entidad"] == entidad_prev) &
        (df_outliers_hombres["Semana"] == semana_prev + 1)
        )

        mask_validos = mask_neg & es_consecutivo
        
        df_outliers_hombres.loc[mask_validos.shift(-1, fill_value=False), "Incremento_hombres"] += df_outliers_hombres.loc[mask_validos, "Incremento_hombres"].values
        
        logger.info(df_outliers_hombres)


        


        #prueba = Path(conf["paths"]["interim"]) / "prueba.csv"
        #df_outliers_hombres.to_csv(prueba, index=False)

         


    def pruebas(self):


        # Mostrar las primeras filas
        prueba = Path(conf["paths"]["interim"]) / "prueba.csv"
        self.df.to_csv(prueba, index=False)


        casos_nacionales = self.df.groupby("Fecha")["Incremento_mujeres"].sum()
        #clip limita los valores de una Serie o DataFrame dentro de un rango.
        #casos_nacionales = casos_nacionales.clip(lower=0)


        plt.figure(figsize=(16, 6))
        plt.plot(casos_nacionales.index, casos_nacionales.values, label='Total de Casos Nacionales', color='navy')

        plt.title('Casos Semanales de Alzheimer a Nivel Nacional (Evolución 2014-2024)')
        plt.xlabel('Año')
        plt.ylabel('Número de Nuevos Casos')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.legend()
        plt.show()




         
    def run(self) -> pd.DataFrame:
        

        self._ajusta_semanas()
        self._agrupa_dataset()
        self._identifica_atipicos()






        #self.pruebas()
