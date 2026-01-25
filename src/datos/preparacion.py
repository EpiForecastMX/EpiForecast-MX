# src/datos/preparacion.py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from loguru import logger

from src.configuraciones.config_params import conf
from src.utils.datos import OperacionesDatos

class dataTransformation:
        
    def __init__(self, df: pd.DataFrame):
            self.df = df.copy()
            self.df_agrupado = pd.DataFrame 
            self.opciones = conf.get("opciones_FE")
            self.regiones = conf.get("regiones")

            self.raw_data_filter = conf.get("data", {}).get("data_prepare")
            self.agrupamiento = str(self.get_opcion("agrupa").get("valor", "")).strip().lower()

    
    def get_opcion(self, nombre: str):
        for item in self.opciones:
            if nombre in item:
                return item[nombre]
        return None

    def _ajusta_semanas(self):
                 
        if not self.df['Semana'].between(1, 52).all():
            raise ValueError("Se encontraron semanas fuera del rango")

        # Identifica las filas donde la semana es 1. 
        # En esos casos, se hará un ajuste especial.
        filas_semana_1 = self.df['Semana'] == 1
        logger.debug(f"{len(filas_semana_1)} registros identificados con semana = 1.")
        
        # Si la semana es 1, se cambia a 52.  
        # Para el resto, simplemente se resta 1 a la sema
        logger.info("Aplicando desplazamiento en las semanas.")
        self.df['Semana'] = np.where(filas_semana_1, 52, self.df['Semana'] - 1)
        
        # Para las filas donde la semana era 1, también se resta 1 al año
        # porque la nueva semana 52 pertenece al año anterior.
        self.df.loc[filas_semana_1, 'Anio'] = self.df.loc[filas_semana_1, 'Anio'] - 1

        # Ordena el Dataframe de acuerdo con el año, entidad y semana
        logger.info("Ordenando el dataset.")
        self.df = self.df.sort_values(by=["Anio", "Entidad", "Semana"]).reset_index(drop=True)

    
    def _prepara_series_tiempo(self):

        logger.info("Inicializando preparación de series temporales.")

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


    def _ajusta_incrementos(self):

        columnas = ["Incremento_hombres","Incremento_mujeres"]

        for columna in columnas:
            logger.info(f"Iniciando ajuste de incrementos en columna '{columna}'.")
            
            mascara_negativos = self.df[columna] < 0
            num_negativos = mascara_negativos.sum()
            logger.info(f"Detectados {num_negativos} valores negativos en '{columna}'.")

        
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
            num_actualizar = mascara_actualizar.sum()
            logger.info(f"{num_actualizar} registros consecutivos serán evaluados para ajuste en '{columna}'.")

            suma = valor_prev + self.df[columna]

            # --- Si la suma es positiva ---
            condicion_positiva = mascara_actualizar & (suma >= 0)

            self.df.loc[condicion_positiva.shift(-1, fill_value=False), columna] = suma[condicion_positiva].values
            self.df.loc[condicion_positiva, columna] = 0

            # --- Si la suma es negativa o cero ---
            condicion_negativa = mascara_actualizar & (suma < 0)
            self.df.loc[condicion_negativa, columna] = 0

            # --- convierte a cero los valores que no fueron afectados ---
            restantes = (self.df[columna] < 0).sum()
            if restantes > 0:
                logger.info(f"Normalizando {restantes} valor(es) normalizado(s) a cero en '{columna}'.")
            
            self.df.loc[self.df[columna] < 0,columna] = 0

    def _ajusta_outliers(self,columnas: list):

        for columna in columnas:
            _ , metadatos = OperacionesDatos.outliers_iqr(self.df,columna)
            lim_inf = metadatos[0]
            lim_sup = metadatos[1]
            q1 = metadatos[2]
            q3 = metadatos[3]
            iqr = metadatos[4]

            mascara_inf = self.df[columna] < lim_inf
            total_inf = mascara_inf.sum()

            mascara_sup = self.df[columna] > lim_sup
            total_sup = mascara_sup.sum()
  
            logger.info(
                f"Rangos intercuartiles para '{columna}': IQR={iqr}, Q1={q1}, Q3={q3}"
            )
            logger.info(
                f"Límite inferior: {lim_inf} | Registros por debajo del límite: {total_inf}"
            )
            logger.info(
                f"Límite superior: {lim_sup} | Registros por encima del límite: {total_sup}"
            )

            self.df.loc[self.df[columna] < lim_inf, columna] = lim_inf
            self.df.loc[self.df[columna] > lim_sup, columna] = lim_sup

            self.df[columna] = self.df[columna].round(0).astype(int)
    
    def agrupar_incrementos(self):
        
        """
        Genera agrupaciones dinámicas dependiendo de la opción seleccionada en el YAML.

        agrupamiento puede ser:
        - 'Sexo'
        - 'Entidad'
        - 'Ambos'
        """
        logger.info(f"Aplicando agrupamiento configurado: {self.agrupamiento}")
      
        # =====================================
        # AGRUPACIÓN POR SEXO
        # =====================================
        
        if self.agrupamiento == "sexo":
            
            self.df_agrupado = (
                self.df.groupby("Fecha")
                .agg(
                    incrementos_hombres=("Incremento_hombres", "sum"),
                    incrementos_mujeres=("Incremento_mujeres", "sum")
                )
                .reset_index()
                .sort_values(["Fecha"])
            )
            logger.info(f"Se obtuvieron {len(self.df_agrupado)} registros agrupados.")

        elif self.agrupamiento == "region":

            self.df_agrupado = (
                self.df.groupby(["Fecha", "Entidad"])
                .agg(
                    incrementos_hombres=("Incremento_hombres", "sum"),
                    incrementos_mujeres=("Incremento_mujeres", "sum")
                )
                .reset_index()
                .sort_values(["Fecha", "Entidad"])
            )

            mapa_regiones = {
                estado: r["nombre"]
                for r in self.regiones
                for estado in r.get("estados", [])
            }

            self.df_agrupado["Region"] = self.df_agrupado["Entidad"].map(mapa_regiones)
                    
            logger.info(f"Se obtuvieron {len(self.df_agrupado)} registros agrupados.")
   
        else:
            logger.warning(f"Agrupamiento desconocido: {self.agrupamiento}. No se generará agrupación.")


    def pruebas(self):

        padecimiento = conf.get("padecimiento")
        plt.figure(figsize=(16, 6))

        if self.agrupamiento == "sexo":
            anio_min = self.df_agrupado['Fecha'].min().year
            anio_max = self.df_agrupado['Fecha'].max().year
            plt.plot(self.df_agrupado["Fecha"],self.df_agrupado["incrementos_hombres"] , label='Casos Hombres', color='steelblue')
            plt.plot(self.df_agrupado["Fecha"],self.df_agrupado["incrementos_mujeres"] , label='Casos Mujeres', color='darkred')
            plt.title(f'Casos Semanales de {padecimiento["tipo"]} a Nivel Nacional (Evolución {anio_min}-{anio_max})')

        
        elif self.agrupamiento == "region":

            agrupamiento_cfg = self.get_opcion("agrupa")
            region_objetivo = agrupamiento_cfg["region"]
           
            df_region_resumen = (
                self.df_agrupado.dropna(subset=["Region"])
                .groupby(["Fecha", "Region"])
                .agg(
                    incrementos_hombres=("incrementos_hombres", "sum"),
                    incrementos_mujeres=("incrementos_mujeres", "sum")
                )
                .reset_index()
                .sort_values(["Region", "Fecha"])
            )

            df_r = (df_region_resumen[df_region_resumen["Region"] == region_objetivo].sort_values("Fecha"))

            anio_min = df_r['Fecha'].min().year
            anio_max = df_r['Fecha'].max().year

            plt.plot(df_r["Fecha"], df_r["incrementos_hombres"], label="Hombres", color="steelblue")
            plt.plot(df_r["Fecha"], df_r["incrementos_mujeres"], label="Mujeres", color="darkred")
            plt.title(f'Casos Semanales de {padecimiento["tipo"]} region {region_objetivo} (Evolución {anio_min}-{anio_max})')
  
        plt.xlabel('Año')
        plt.ylabel('Número de Nuevos Casos')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.legend()
        plt.show()


    def run(self) -> pd.DataFrame:       

        outlier_cfg = self.get_opcion("tratamiento_outliers")

        self._ajusta_semanas()
        self._prepara_series_tiempo()
        self._ajusta_incrementos()

        if outlier_cfg['IQR']:
            logger.info(f"Imputación por IQR habilitada ({outlier_cfg['IQR']}) | Columnas: '{outlier_cfg['columnas']}'")
            self._ajusta_outliers(outlier_cfg['columnas'])

        self.agrupar_incrementos()


        if not self.df_agrupado.empty:
            self.pruebas()
        
        return self.df_agrupado