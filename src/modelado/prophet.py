# src/modelado/prophet.py

import os
import itertools
import logging


import cmdstanpy
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    mean_absolute_percentage_error,
)
from sklearn.model_selection import TimeSeriesSplit

from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager

logging.getLogger("cmdstanpy").disabled = True



class SerieTiempoProphet:
    def __init__(self, 
                 df: pd.DataFrame,
                 sexo: str = None):
        
        self.df = df.copy()
        self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])
        self.serie = pd.DataFrame
        self.sexo = sexo

        self.modelado_estados = conf['padecimiento']['modelado_estados']
        self.entrena = conf['padecimiento']['entrena_modelo']
        self.model_path = conf['paths']['models']
        self.model_save = conf['data']['model_train']

        self.param_grid = conf['param_grid_prophet']
        self.mapeo_columnas = conf['mapeo_columnas']
        self.FECHA_CORTE_ENTRENAMIENTO = conf['FECHA_CORTE_ENTRENAMIENTO']
        self.TRAIN_SPLIT = conf['TS_SPLITS']
        self.regiones_INEGI = conf['regiones_INEGI']

        
        self.periodos_atipicos = conf['peridos_atipicos']
        self.fechas_atipicas = pd.DataFrame(self.periodos_atipicos)
        self.fechas_atipicas["ds"] = pd.to_datetime(self.fechas_atipicas["ds"])

        self.df_serie = pd.DataFrame
        self.train_data = pd.DataFrame
        self.test_data = pd.DataFrame


    def agrupa(self) -> bool:
        
        base = (
            self.df
            .groupby("Fecha")[self.sexo]
            .sum()
        )
        self.serie = base

    def crea_train_test(self) -> None:
        self.serie = self.serie.rename_axis("ds").reset_index()
        self.serie = self.serie.rename(columns = {self.sexo:"y"})
        self.train_data = self.serie[self.serie['ds'] < self.FECHA_CORTE_ENTRENAMIENTO]
        self.test_data = self.serie[self.serie['ds'] >= self.FECHA_CORTE_ENTRENAMIENTO]

        logger.info(f"Datos de entrenamiento: {len(self.train_data)} semanas (hasta {self.train_data['ds'].max().date()})")
        logger.info(f"Datos de prueba: {len(self.test_data)} semanas (desde {self.test_data['ds'].min().date()})")
        
    def prophet_cross_val(self) -> tuple [dict, float]:

        parametros = [dict(zip(self.param_grid.keys(), v)) for v in itertools.product(*self.param_grid.values())]
        logger.info(f"Se probarán {len(parametros)} combinaciones de hiperparámetros.")
        
        # Mostrar eventos configurados
        for _, fila in self.fechas_atipicas.iterrows():
            logger.debug(
            f"Evento configurado:'{fila['holiday']}' con una ventana de afectación de {fila['upper_window']} días."
        )

        tscv = TimeSeriesSplit(n_splits=self.TRAIN_SPLIT)
        best_rmse = float('inf')
        best_param = None

        for iteracion, parametro in enumerate(parametros):
            
            rmse_fold = []

            resumen = ", ".join(f"{k}={v}" for k, v in parametro.items())

            for train_idx, val_idx in tscv.split(self.train_data):
                train_fold = self.train_data.iloc[train_idx]
                val_fold = self.train_data.iloc[val_idx]
                
                try:
                    modelo_cv = Prophet(
                            yearly_seasonality=True,
                            weekly_seasonality=True,
                            daily_seasonality=False,
                            holidays=self.fechas_atipicas,
                            **parametro
                    )

                    modelo_cv.add_seasonality(name='monthly', period=30.5,fourier_order=3)
                    modelo_cv.fit(train_fold)

                    
                    future_cv = modelo_cv.make_future_dataframe(
                                        periods=len(val_fold), freq='W-MON'
                                    )
                    forecast_cv = modelo_cv.predict(future_cv)

                    y_pred_cv = forecast_cv.iloc[-len(val_fold):]['yhat']
                    rmse = np.sqrt(mean_squared_error(val_fold['y'], y_pred_cv))
                    rmse_fold.append(rmse)

                except Exception as e:
                    logger.warning(f'Ocurrio excepcion {e}')
                    continue

                if rmse_fold:
                    mean_rmse = float(np.mean(rmse_fold))
                    logger.debug(f"RMSE promedio: {mean_rmse:.4f}")

            if mean_rmse < best_rmse:
                best_rmse = mean_rmse
                best_param = parametro
                logger.info(f"[CV] Iteración {iteracion + 1}/{len(parametros)} – Nuevo mejor RMSE: {best_rmse:.4f}")
                        
            else:
                logger.debug(f"[CV] Iteración {iteracion + 1}/{len(parametros)} - No se obtuvo ningún RMSE válido para {resumen}")

        logger.success(f"Mejor RMSE promedio: {best_rmse:.4f}")
        logger.success(f"Mejor conjunto de parámetros encontrado: {best_param}")

        return best_param, best_rmse
    
    def train(self,parametros) -> Prophet:
        
        modelo_final = Prophet(
                yearly_seasonality=30,
                weekly_seasonality=True,
                daily_seasonality=False,
                holidays=self.fechas_atipicas,
                **parametros
            )
        
        modelo_final.add_seasonality(name='monthly', period=30.5, fourier_order=5)
        modelo_final.fit(self.train_data)

        return modelo_final
    
    def train_test(self,parametros) -> pd.DataFrame:

        modelo_test = Prophet(
                yearly_seasonality=30,
                weekly_seasonality=True,
                daily_seasonality=False,
                holidays=self.fechas_atipicas,
                **parametros
            )
        
        modelo_test.add_seasonality(name='monthly', period=30.5, fourier_order=5)
        modelo_test.fit(self.train_data)

        # --- Generación del Pronóstico ---
        horizonte_total = len(self.test_data)
        future_final = modelo_test.make_future_dataframe(periods=horizonte_total, freq="W-MON")
        forecast_final = modelo_test.predict(future_final)

        df_eval = pd.merge(
            self.test_data,
            forecast_final[['ds', 'yhat']],
            on='ds',
            how='left'
        )

        df_eval = df_eval.dropna(subset=["yhat"])

        return df_eval
    
    def calcular_metricas(self,df_eval_periodo, nombre_periodo):
        y_true = df_eval_periodo['y']
        y_pred = df_eval_periodo['yhat']
        
        mape = mean_absolute_percentage_error(y_true, y_pred) * 100
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mae = mean_absolute_error(y_true, y_pred)
        
        print(f"\n--- Métricas para el período: {nombre_periodo} ---")
        print(f"MAPE: {mape:.2f}%")
        print(f"RMSE: {rmse:.2f}")
        print(f"MAE:  {mae:.2f}")

    def graficar(self, df_eval):

        plt.figure(figsize=(15, 5))
        plt.plot(df_eval['ds'], df_eval['y'], 'o-', label='Datos Reales')
        plt.plot(df_eval['ds'], df_eval['yhat'], 'x--', label='Pronóstico')
        plt.title(f'Pronóstico vs Realidad — Región: {self.region}, Agrupado por {self.sexo.capitalize()}')
        plt.legend()
        plt.grid(alpha=0.3)
        plt.show()

    def run(self) -> tuple[Prophet, float, dict]:

        self.agrupa()
        self.crea_train_test()

        parametros, rmse = self.prophet_cross_val()
        modelo = self.train(parametros)

        return modelo, rmse, parametros
     
     

"""                    
                    #df_eval_2025 = df_eval[df_eval['ds'].dt.year == 2025]
                    #self.calcular_metricas(df_eval_2025, "2023 (Año 1 del Pronóstico)")
                    #self.graficar(df_eval_2025)
            
"""