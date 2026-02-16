# src/datos/preparacion.py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from loguru import logger
from datetime import date

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
                 
        if not self.df['Semana'].between(1, 53).all():
            raise ValueError("Se encontraron semanas fuera del rango")
        
        filas_semana_1 = self.df['Semana'] == 1
        filas_no_semana_1 = ~filas_semana_1

        logger.debug(f"{filas_semana_1.sum()} registros identificados con semana = 1.")
        filas_semana_53 = self.df['Semana'] == 53
        logger.debug(f"{filas_semana_53.sum()} registros identificados con semana = 53.")

        #Para los que NO son semana 1: restar 1
        self.df.loc[filas_no_semana_1, 'Semana'] = self.df.loc[filas_no_semana_1, 'Semana'] - 1

        #Preparar el máximo de semana por año 
        agg_por_anio = (
            self.df
            .groupby('Anio', as_index=False)
            .agg(max_semana=('Semana', 'max'))
        )

        #Construir mapa: año -> max_semana observado
        mapa_max_semana = dict(zip(agg_por_anio['Anio'], agg_por_anio['max_semana']))

        #Calcular el año anterior para las filas con semana 1
        anio_prev = self.df.loc[filas_semana_1, 'Anio'] - 1

        #Obtener el máximo del año anterior y sumarle +1
        max_global_sem = self.df['Semana'].max()
        max_prev_anio = anio_prev.map(mapa_max_semana)

        #Si el año anterior no existe en los datos (NaN), usar el máximo global
        max_prev_anio = max_prev_anio.fillna(max_global_sem)

        #La nueva semana para las filas de semana 1 será (max_prev_anio + 1)
        nueva_semana_para_sem1 = (max_prev_anio + 1).astype(int)

        #Asignar
        self.df.loc[filas_semana_1, 'Anio'] = anio_prev.values
        self.df.loc[filas_semana_1, 'Semana'] = nueva_semana_para_sem1.values

        #Ordenar
        self.df = self.df.sort_values(by=["Padecimiento","Anio", "Entidad", "Semana"]).reset_index(drop=True)

        logger.info("Ordenando el dataset.")
                 
    def _prepara_series_tiempo(self):

        logger.info("Inicializando preparación de series temporales.")

        self.df["Prev_hombres"] = self.df.groupby(["Padecimiento", "Entidad"])["Acumulado_hombres"].shift()
        self.df["Prev_mujeres"] = self.df.groupby(["Padecimiento", "Entidad"])["Acumulado_mujeres"].shift()

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
        #filas_anio = (self.df['Semana'] == 1) & (self.df['Fecha'].dt.year < self.df['Anio'])
        #self.df.loc[filas_anio, 'Fecha'] = pd.to_datetime(self.df.loc[filas_anio, 'Anio'].astype(str) + '-01-01')
        #self.df.loc[filas_anio, 'Fecha'] = (pd.to_datetime(self.df.loc[filas_anio, 'Anio'].astype(str) + '-01-01')+ pd.offsets.Week(weekday=0))  # primer lunes

    def _ajusta_incrementos(self):
        
        for columna in ["Incremento_hombres", "Incremento_mujeres"]:
            # 1) Identificar negativos
            mascara_neg = self.df[columna] < 0

            # 2) Consecutividad con la fila previa (misma Entidad, mismo Año, y Semana == Semana_prev + 1)
            padecimiento = self.df["Padecimiento"].shift(1)
            anio_prev    = self.df["Anio"].shift(1)
            semana_prev  = self.df["Semana"].shift(1)
            entidad_prev = self.df["Entidad"].shift(1)
            valor_prev   = self.df[columna].shift(1)

            es_consec = (
                (self.df["Padecimiento"] == padecimiento) &
                (self.df["Entidad"] == entidad_prev) &
                (self.df["Anio"]    == anio_prev) &
                (self.df["Semana"]  == semana_prev + 1)
            )

            # Negativo actual + previo positivo + consecutivo
            mascara_act = mascara_neg & es_consec & (valor_prev > 0)

            # 3) AJUSTAR EL PREVIO (t-1) con "previo + actual_negativo"
            #    - Recorte a >= 0
            #    - Redondeo a entero
            nuevo_prev = (valor_prev + self.df[columna]).where(mascara_act).clip(lower=0)

            # Índices del previo (t-1) donde escribir
            prev_index = self.df.index.to_series().shift(1)
            targets_prev = prev_index[mascara_act].dropna().astype(int)

            # Escribir en el PREVIO (solo en las filas válidas)
            self.df.loc[targets_prev, columna] = nuevo_prev[mascara_act].astype(int).values

            # 4) EXTRAPOLACIÓN CON 3 SEMANAS PREVIAS (t-1, t-2, t-3) usando la COLUMNA YA ACTUALIZADA
            #    shift(1): excluye la semana actual
            #    rolling(3): últimas 3 semanas previas dentro del mismo (Entidad, Anio)
            prev3_mean = (
                self.df.groupby(["Padecimiento","Entidad", "Anio"])[columna]
                    .transform(lambda s: s.shift(1).rolling(window=3, min_periods=1).mean())
            )

            # Redondear el promedio a entero y reemplazar NaN por 0 (si no hay historial)
            prev3_mean = np.rint(prev3_mean).astype("Int64").fillna(0).astype(int)

            # 5) Escribir la EXTRAPOLACIÓN en la fila ACTUAL (negativa + consecutiva + previo>0)
            self.df.loc[mascara_act, columna] = prev3_mean[mascara_act].values

            # 6) Asegurar que TODA la columna quede en enteros (por si quedan floats por mezclas pandas)
            self.df[columna] = np.rint(self.df[columna]).astype(int)

    def _ajusta_negativos(self):

        for columna in ["Incremento_hombres", "Incremento_mujeres"]:
            # 1) Máscara de negativos
            neg = self.df[columna] < 0

            # 2) Vecinos anterior y siguiente
            prev_val = self.df[columna].shift(1)
            next_val = self.df[columna].shift(-1)

            # 3) Tratar NaN/inf como 0 en vecinos
            prev_val = prev_val.replace([np.inf, -np.inf], np.nan).fillna(0)
            next_val = next_val.replace([np.inf, -np.inf], np.nan).fillna(0)

            # 4) Candidatos: cuando el actual sea negativo (si quieres exigir que existan ambos vecinos,
            #    puedes usar: neg & prev_val.notna() & next_val.notna() ; pero aquí ya tratamos NaN como 0)
            candidatos = neg

            # 5) Extrapolado = promedio simple (t-1, t+1), con manejo robusto de NaN/inf
            extrap = (prev_val + next_val) / 2.0
            
            # Si hay valores negativos, se ponen en cero
            extrap = extrap.clip(lower=0)


            # 6) Tratar NaN/inf del extrapolado como 0, redondear y castear a entero
            extrap = extrap.replace([np.inf, -np.inf], np.nan).fillna(0)
            extrap = np.rint(extrap).astype(int)

            # 7) Sustituir SOLO el valor negativo actual por el extrapolado
            self.df.loc[candidatos, columna] = extrap[candidatos].values

            # 8) Como toque final, asegurar que la columna quede en enteros,
            #    tratando cualquier NaN/inf residual como 0 antes de castear
            self.df[columna] = (
                pd.Series(self.df[columna], index=self.df.index)
                .replace([np.inf, -np.inf], np.nan)
                .fillna(0)
                .round()
                .astype(int)
            )

    def _ajusta_outliers(self,columnas: list, agrupacion:list):

        for columna in columnas:

            stats = (
                self.df.groupby(agrupacion, sort=False)
                    .apply(lambda g: pd.Series(
                        (lambda met: {
                            "q1":  met[2],
                            "q3":  met[3],
                            "iqr": met[4],
                            "lim_inf": met[0],
                            "lim_sup": met[1],
                        })(OperacionesDatos.outliers_iqr(g, columna)[1])
                    ), include_groups=False 
                    )
                    .reset_index()
            )
            self.df = self.df.merge(
                stats[["Padecimiento", "q1", "q3", "iqr", "lim_inf", "lim_sup"]],
                on="Padecimiento", how="left"
            )

            for pade, sub in self.df.groupby("Padecimiento", sort=False):
                # Evita NaN al loggear
                iqr     = sub["iqr"].iloc[0]
                q1      = sub["q1"].iloc[0]
                q3      = sub["q3"].iloc[0]
                lim_inf = sub["lim_inf"].iloc[0]
                lim_sup = sub["lim_sup"].iloc[0]

                mascara_inf = sub[columna] < lim_inf
                mascara_sup = sub[columna] > lim_sup
                total_inf = int(mascara_inf.sum())
                total_sup = int(mascara_sup.sum())

                logger.info(f"[{pade}] Rangos intercuartiles para '{columna}': IQR={iqr}, Q1={q1}, Q3={q3}")
                logger.info(f"[{pade}] Límite inferior: {lim_inf} | Registros por debajo del límite: {total_inf}")
                logger.info(f"[{pade}] Límite superior: {lim_sup} | Registros por encima del límite: {total_sup}")

            x = self.df[columna].to_numpy()
            lo = self.df["lim_inf"].to_numpy()
            hi = self.df["lim_sup"].to_numpy()

            x_clipped = np.clip(x, lo, hi)

            self.df[columna] = pd.Series(x_clipped, index=self.df.index).round(0).astype("Int64")

            self.df = self.df.drop(columns=["q1", "q3", "iqr", "lim_inf", "lim_sup"])
    
    def _ajusta_outliers_zscore(self,columnas: list,agrupacion: list, umbral: int, reemplazo: str):
        
        for col in columnas:
            self.df = OperacionesDatos.zscore(self.df, col, agrupacion,umbral, reemplazo)

    def agrupar(self):

        logger.info(f"Aplicando agrupamiento")
                   
        self.df_agrupado = (
            self.df.groupby(["Padecimiento","Semana","Fecha","Entidad"])
            .agg(
                incrementos_hombres=("Incremento_hombres", "sum"),
                incrementos_mujeres=("Incremento_mujeres", "sum")
                )
            .reset_index()
            .sort_values(["Padecimiento","Fecha","Entidad"])
        )
        logger.info(f"Se obtuvieron {len(self.df_agrupado)} registros agrupados.")

        mapa_regiones = {
            estado: r["nombre"]
            for r in self.regiones
            for estado in r.get("estados", [])
            }

        self.df_agrupado["Region"] = self.df_agrupado["Entidad"].map(mapa_regiones)

    def genera_todos(self):

        self.df_agrupado["incrementos_total"] = self.df_agrupado["incrementos_hombres"] + self.df_agrupado["incrementos_mujeres"]

    def run(self) -> pd.DataFrame:       

        outlier_cfg = self.get_opcion("tratamiento_outliers")
        
        self._ajusta_semanas()
        self._prepara_series_tiempo()
        #self._ajusta_incrementos()  Procedimiento para el tratamiento de datos semana 20 2016
        #                            Se retira este ajuste               
        self._ajusta_negativos()
        
        if outlier_cfg['IQR']:
            
            if outlier_cfg['metodo'].lower() == 'iqr': # Se recomienda no usar este metodo, agrega muchos datos no validos
                logger.info(
                    f"Imputación habilitada: método: '{outlier_cfg['metodo']}' | "
                    f"columnas: {outlier_cfg['columnas']}, | "
                    f"umbral: {outlier_cfg['umbral']}"
                )
                self._ajusta_outliers(outlier_cfg['columnas'],outlier_cfg['agrupacion']) 

            elif outlier_cfg['metodo'].lower() == 'zscore':
                logger.info(
                    f"Imputación habilitada: método: '{outlier_cfg['metodo']}' | "
                    f"columnas: {outlier_cfg['columnas']} | "
                    f"umbral: {outlier_cfg['umbral']} | "
                    f"reemplazo: {outlier_cfg['reemplazo']}"
                )
                self._ajusta_outliers_zscore(outlier_cfg['columnas'],outlier_cfg['agrupacion'],outlier_cfg['umbral'],outlier_cfg['reemplazo'])
            else:
                logger.error(f"Opcion no válida: {outlier_cfg.get('metodo')}")
                raise ValueError(f"Opcion no válida: {outlier_cfg.get('metodo')}")


        self.agrupar()
        self.genera_todos()

        return self.df_agrupado