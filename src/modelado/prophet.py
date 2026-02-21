# src/modelado/prophet.py

import os
import itertools
import logging
import time


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
                 sexo: str = None,
                 entidad: str = None,
                 padecimiento: str = None):

        self.df = df.copy()
        self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])
        self.serie = pd.DataFrame
        self.sexo = sexo
        self.entidad = entidad
        self.padecimiento = padecimiento

        self.modelado_estados = conf['padecimiento']['modelado_estados']
        self.entrena = conf['padecimiento']['entrena_modelo']
        self.model_path = conf['paths']['models']
        self.model_save = conf['data']['model_train']

        _GRID_KEY = {
            "Alzheimer": "alzheimer",
            "Depresión": "depresion",
            "Parkinson": "parkinson",
        }
        tipo = self.df['Padecimiento'].iloc[0] if 'Padecimiento' in self.df.columns else None
        grid_key = _GRID_KEY.get(tipo)
        if grid_key is None:
            raise ValueError(
                f"param_grid_prophet no definido para padecimiento='{tipo}'. "
                f"Valores válidos: {list(_GRID_KEY)}"
            )
        self.param_grid = conf['param_grid_prophet'][grid_key]
        logger.info("Grid de hiperparámetros: {} ({})", tipo, grid_key)

        self.mapeo_columnas = conf['mapeo_columnas']
        self.FECHA_CORTE_ENTRENAMIENTO = conf['FECHA_CORTE_ENTRENAMIENTO']
        self.TRAIN_SPLIT = conf['TS_SPLITS']
        self.TEST_SIZE = conf['TEST_SIZE']
        self.regiones_INEGI = conf['regiones_INEGI']


        self.periodos_atipicos = conf['peridos_atipicos']
        self.fechas_atipicas = pd.DataFrame(self.periodos_atipicos)
        self.fechas_atipicas["ds"] = pd.to_datetime(self.fechas_atipicas["ds"])

        # Agregar cambios de régimen específicos de esta entidad/padecimiento
        cambios = conf.get('cambios_regimen', [])
        if cambios and entidad:
            filtrados = [
                c for c in cambios
                if c.get('entidad') == entidad
                and (not c.get('padecimiento') or c.get('padecimiento') == padecimiento)
            ]
            if filtrados:
                df_cambios = pd.DataFrame(filtrados)
                df_cambios["ds"] = pd.to_datetime(df_cambios["ds"])
                cols_prophet = ["holiday", "ds", "lower_window", "upper_window"]
                df_cambios = df_cambios[cols_prophet]
                self.fechas_atipicas = pd.concat(
                    [self.fechas_atipicas, df_cambios], ignore_index=True
                )
                logger.info(
                    "Cambios de régimen agregados para {}: {}",
                    entidad, [c['holiday'] for c in filtrados],
                )

        self.param_model = dict(conf['param_model'])

        # fourier_order_regional: se usa solo en modelos por estado (series más cortas)
        raw_seasonality = dict(conf['add_seasonality'])
        fourier_order_regional = raw_seasonality.pop('fourier_order_regional', None)
        if self.modelado_estados and fourier_order_regional is not None:
            raw_seasonality['fourier_order'] = fourier_order_regional
            logger.debug("fourier_order_regional={} aplicado (modelado por estado)", fourier_order_regional)
        self.add_seasonality_params = raw_seasonality

        # n_changepoints_regional: reduce overfitting en series estatales cortas
        n_cp_regional = conf.get('n_changepoints_regional', None)
        if self.modelado_estados and n_cp_regional is not None:
            self.param_model['n_changepoints'] = n_cp_regional
            logger.debug("n_changepoints_regional={} aplicado (modelado por estado)", n_cp_regional)

        self.cv_weights = conf.get('cv_weights', None)
        self.cv_timeout = conf.get('cv_timeout_por_combo', 0)

        self.normalizar_tasa = conf.get('normalizar_tasa', False)
        self.col_poblacion = conf.get('columna_poblacion', 'Total')
        self.tasa_por = conf.get('tasa_por', 100000)
        self.log_transform = conf.get('log_transform', False)
        self.poblacion_valor = None

        self.df_serie = pd.DataFrame
        self.train_data = pd.DataFrame
        self.test_data = pd.DataFrame


    def agrupa(self) -> None:
        agg_dict = {self.sexo: "sum"}
        if self.normalizar_tasa and self.col_poblacion in self.df.columns:
            # sum: para un estado es igual a first (1 fila/fecha),
            # para nacional suma las 32 poblaciones estatales = población nacional
            agg_dict[self.col_poblacion] = "sum"
        self.serie = self.df.groupby("Fecha").agg(agg_dict)

    def crea_train_test(self) -> None:
        self.serie = self.serie.rename_axis("ds").reset_index()

        if self.normalizar_tasa and self.col_poblacion in self.serie.columns:
            self.poblacion_valor = self.serie[self.col_poblacion].iloc[0]
            self.serie["y_original"] = self.serie[self.sexo]
            self.serie["y"] = (self.serie[self.sexo] / self.poblacion_valor) * self.tasa_por
            self.serie = self.serie.drop(columns=[self.sexo])
            logger.info(
                "Normalizado a tasa por {:,.0f} hab. (población: {:,.0f})",
                self.tasa_por, self.poblacion_valor,
            )
        else:
            self.serie = self.serie.rename(columns={self.sexo: "y"})

        if self.log_transform:
            self.serie["y"] = np.log1p(self.serie["y"])
            logger.info("Log-transform aplicado: y = log(1 + y)")

        self.train_data = self.serie[self.serie['ds'] < self.FECHA_CORTE_ENTRENAMIENTO]
        self.test_data = self.serie[self.serie['ds'] >= self.FECHA_CORTE_ENTRENAMIENTO]

        logger.info(f"Datos de entrenamiento: {len(self.train_data)} semanas (hasta {self.train_data['ds'].max().date()})")
        logger.info(f"Datos de prueba: {len(self.test_data)} semanas (desde {self.test_data['ds'].min().date()})")
        
    def promedio_semanal(self) -> float:
        """Retorna el promedio semanal del conteo original (antes de transformaciones)."""
        if "y_original" in self.train_data.columns:
            return float(self.train_data["y_original"].mean())
        return float(self.train_data["y"].mean())

    def prophet_cross_val(self) -> tuple[dict, dict]:

        parametros = [dict(zip(self.param_grid.keys(), v)) for v in itertools.product(*self.param_grid.values())]
        logger.info(f"Se probarán {len(parametros)} combinaciones de hiperparámetros.")

        if self.cv_weights:
            logger.info("CV con pesos progresivos: {}", list(self.cv_weights))

        # Mostrar eventos configurados
        for _, fila in self.fechas_atipicas.iterrows():
            logger.debug(
            f"Evento configurado:'{fila['holiday']}' con una ventana de afectación de {fila['upper_window']} días."
        )

        tscv = TimeSeriesSplit(n_splits=self.TRAIN_SPLIT,test_size=self.TEST_SIZE)
        best_rmse = float('inf')
        best_param = None
        best_metrics = {}

        for iteracion, parametro in enumerate(parametros):

            rmse_fold = []
            mae_fold = []
            mape_fold = []
            fold_indices = []
            timed_out = False

            resumen = ", ".join(f"{k}={v}" for k, v in parametro.items())
            t_combo = time.time()

            for fold_iteration, (train_idx, val_idx) in enumerate(tscv.split(self.train_data)):
                train_fold = self.train_data.iloc[train_idx]
                val_fold = self.train_data.iloc[val_idx]

                logger.debug(
                    f"Fold {fold_iteration+1}: "
                    f"Train hasta {train_fold['ds'].max().date()}, "
                    f"Val desde {val_fold['ds'].min().date()} "
                    f"hasta {val_fold['ds'].max().date()}"
                )

                try:
                    modelo_cv = Prophet(
                            holidays=self.fechas_atipicas,
                            **self.param_model,
                            **parametro
                    )

                    modelo_cv.add_seasonality(**self.add_seasonality_params)
                    modelo_cv.fit(train_fold)

                    forecast_cv = modelo_cv.predict(val_fold[['ds']])

                    merged = val_fold[['ds','y']].merge(forecast_cv[['ds','yhat']], on='ds')
                    rmse = np.sqrt(mean_squared_error(merged['y'], merged['yhat']))
                    mae = mean_absolute_error(merged['y'], merged['yhat'])
                    mape = min(mean_absolute_percentage_error(merged['y'], merged['yhat']) * 100, 999.0)
                    rmse_fold.append(rmse)
                    mae_fold.append(mae)
                    mape_fold.append(mape)
                    fold_indices.append(fold_iteration)

                except Exception as e:
                    logger.warning(f'Ocurrio excepcion {e}')
                    continue

                # Timeout: si esta combo excede el límite, saltar folds restantes
                if self.cv_timeout and (time.time() - t_combo) > self.cv_timeout:
                    logger.warning(
                        "Timeout CV: {:.0f}s > {}s en fold {}/{}. Skip combo: {}",
                        time.time() - t_combo, self.cv_timeout,
                        fold_iteration + 1, self.TRAIN_SPLIT, resumen,
                    )
                    timed_out = True
                    break

            if timed_out:
                # Combo descartada por timeout: no considerar como candidata
                mean_rmse = float('inf')
                mean_mae = float('inf')
                mean_mape = float('inf')
            elif rmse_fold:
                if self.cv_weights and len(self.cv_weights) >= self.TRAIN_SPLIT:
                    weights = [self.cv_weights[i] for i in fold_indices]
                    mean_rmse = float(np.average(rmse_fold, weights=weights))
                    mean_mae = float(np.average(mae_fold, weights=weights))
                    mean_mape = float(np.average(mape_fold, weights=weights))
                else:
                    mean_rmse = float(np.mean(rmse_fold))
                    mean_mae = float(np.mean(mae_fold))
                    mean_mape = float(np.mean(mape_fold))
                logger.debug(
                    f"Métricas CV: RMSE={mean_rmse:.4f}, MAE={mean_mae:.4f}, MAPE={mean_mape:.2f}%"
                )
            else:
                mean_rmse = float('inf')
                mean_mae = float('inf')
                mean_mape = float('inf')

            if mean_rmse < best_rmse:
                best_rmse = mean_rmse
                best_param = parametro
                best_metrics = {
                    "rmse": mean_rmse,
                    "mae": mean_mae,
                    "mape": mean_mape,
                }
                logger.info(
                    f"[CV] Iteración {iteracion + 1}/{len(parametros)} – "
                    f"Nuevo mejor RMSE: {best_rmse:.4f} | MAE: {mean_mae:.4f} | MAPE: {mean_mape:.2f}%"
                )

            else:
                logger.debug(f"[CV] Iteración {iteracion + 1}/{len(parametros)} - No se obtuvo ningún RMSE válido para {resumen}")

        logger.success(f"Mejor RMSE: {best_metrics.get('rmse', 0):.4f} | MAE: {best_metrics.get('mae', 0):.4f} | MAPE: {best_metrics.get('mape', 0):.2f}%")
        logger.success(f"Mejor conjunto de parámetros encontrado: {best_param}")

        return best_param, best_metrics
    
    def train(self, parametros) -> Prophet:

        modelo_final = Prophet(
                holidays=self.fechas_atipicas,
                **self.param_model,
                **parametros
            )

        modelo_final.add_seasonality(**self.add_seasonality_params)

        try:
            modelo_final.fit(self.train_data)
        except Exception as e:
            logger.warning("L-BFGS fallo, reintentando con changepoint_prior_scale=0.05: {}", e)
            parametros_fallback = {**parametros, "changepoint_prior_scale": 0.05}
            modelo_final = Prophet(
                holidays=self.fechas_atipicas,
                **self.param_model,
                **parametros_fallback
            )
            modelo_final.add_seasonality(**self.add_seasonality_params)
            modelo_final.fit(self.train_data)

        return modelo_final
    
    def train_test(self,parametros) -> pd.DataFrame:

        modelo_test = Prophet(
                holidays=self.fechas_atipicas,
                **self.param_model,
                **parametros
            )

        modelo_test.add_seasonality(**self.add_seasonality_params)
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

    def run(self) -> tuple[Prophet, dict, dict]:

        self.agrupa()
        self.crea_train_test()

        parametros, metrics = self.prophet_cross_val()
        modelo = self.train(parametros)

        return modelo, metrics, parametros
     
     

"""                    
                    #df_eval_2025 = df_eval[df_eval['ds'].dt.year == 2025]
                    #self.calcular_metricas(df_eval_2025, "2023 (Año 1 del Pronóstico)")
                    #self.graficar(df_eval_2025)
            
"""