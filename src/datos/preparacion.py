# src/datos/preparacion.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from loguru import logger

from src.utils.datos import OperacionesDatos

from src.configuraciones.config_params import conf


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


    def _convertir_negativos(self):

        columnas = ["Incremento_hombres","Incremento_mujeres"]

        for columna in columnas:
            mascara_negativos = self.df[columna] < 0
        
            anio_prev    = self.df["Anio"].shift(1)
            semana_prev  = self.df["Semana"].shift(1)
            entidad_prev = self.df["Entidad"].shift(1)
            valor_prev   = self.df[columna].shift(1)

            es_consecutivo = (
                (self.df["Anio"] == anio_prev) &
                (self.df["Entidad"] == entidad_prev) &
                (self.df["Semana"] == semana_prev + 1)
            )
        
            mascara_actualizar = mascara_negativos & es_consecutivo

            suma = valor_prev + self.df[columna]

            # --- Si la suma es positiva ---
            condicion_positiva = mascara_actualizar & (suma >= 0)

            self.df.loc[condicion_positiva.shift(-1, fill_value=False), columna] = suma[condicion_positiva].values
            self.df.loc[condicion_positiva, columna] = 0

            # --- Si la suma es negativa o cero ---
            condicion_negativa = mascara_actualizar & (suma < 0)
            self.df.loc[condicion_negativa, columna] = 0

            # --- convierte a cero los valores que no fueron afectados ---

            self.df.loc[self.df[columna] < 0,columna] = 0

    def _tratamiento_outliers(self):

        columnas = ["Incremento_hombres","Incremento_mujeres"]
        
        for columna in columnas:
            _ , metadatos = OperacionesDatos.outliers_iqr(self.df,columna)
            lim_inf = metadatos[0]
            lim_sup = metadatos[1]

            self.df.loc[self.df[columna] < lim_inf, columna] = lim_inf
            self.df.loc[self.df[columna] > lim_sup, columna] = lim_sup

            self.df[columna] = self.df[columna].round(0).astype(int)

            logger.info(metadatos)




        


         


    def pruebas(self):


        # Mostrar las primeras filas
        prueba = Path(conf["paths"]["interim"]) / "prueba.csv"
        self.df.to_csv(prueba, index=False)


        casos_hombres = self.df.groupby("Fecha")["Incremento_hombres"].sum()
        casos_mujeres = self.df.groupby("Fecha")["Incremento_mujeres"].sum()

        casos_totales = casos_hombres + casos_mujeres


        plt.figure(figsize=(16, 6))

        plt.plot(casos_hombres.index, casos_hombres.values, label='Casos Hombres', color='steelblue')
        plt.plot(casos_mujeres.index, casos_mujeres.values, label='Casos Mujeres', color='darkred')
        plt.plot(casos_totales.index, casos_totales.values, label='Total Nacional', color='navy', linewidth=2)

        plt.title('Casos Semanales de Alzheimer a Nivel Nacional (Evolución 2014-2024)')
        plt.xlabel('Año')
        plt.ylabel('Número de Nuevos Casos')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.legend()
        plt.show()


    def run(self) -> pd.DataFrame:
        

        self._ajusta_semanas()
        self._agrupa_dataset()
        self._convertir_negativos()
        self._tratamiento_outliers()
        
        self.pruebas()

