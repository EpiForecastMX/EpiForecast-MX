# src/utils/datos.py
import pandas as pd
import numpy as np
import itertools

from prophet import Prophet
from src.configuraciones.config_params import conf, logger
from prophet.diagnostics import cross_validation, performance_metrics
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error


import logging
import cmdstanpy

logging.getLogger("cmdstanpy").disabled = True


import matplotlib.pyplot as plt



class SerieTiempoProphet:
    def __init__(self, df: pd.DataFrame):
        
        self.df = df.copy()
        self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])
        self.serie = pd.DataFrame
        self.region = str
        self.sexo = str

        self.mapa_col = {
                "hombres": "incrementos_hombres",
                "mujeres": "incrementos_mujeres",
                "todos": "todos",
            }

    def filtrar_region(self) -> bool:
        region_validos = {"Urbana media","Sur-Sureste vulnerable","Metropolitana alta","Rural / dispersa"}

        if self.region in region_validos:
            self.df = self.df[self.df['region_salud_mental'] == self.region]
            return True
        
        else:
            logger.error(f'Opción inválida: {self.region}. Valores permitidos: {sorted(region_validos)}')
            return False
    

    def agrupa(self) -> bool:
        sexo_validos = {"todos","hombres","mujeres"}
        logger.info(self.df.info())

        if self.sexo.lower() in sexo_validos:
            logger.info(f'Filtrando por {self.sexo}')

            base = (
                self.df
                .groupby("Fecha")[["incrementos_hombres", "incrementos_mujeres"]]
                .sum()
            )

            
            base["todos"] = base["incrementos_hombres"] + base["incrementos_mujeres"]
            
            self.serie = base[[self.mapa_col[self.sexo.lower()]]]
            #self.serie = self.serie.resample("W-MON").asfreq()

            return True
            
        else:
            logger.error(f'Opción inválida: {self.sexo}. Valores permitidos: {sorted(sexo_validos)}')
            return False


    def prophet_cross_val(self) -> dict:
        
        #parametrizar en yaml inicio
        param_grid_prophet = {
            'seasonality_mode': ['additive', 'multiplicative'],
            'changepoint_prior_scale': [0.05, 0.1, 0.5, 0.7, 1.0],
            'seasonality_prior_scale': [0.25, 0.5, 0.6, 0.7, 1.0]
        }

        FECHA_CORTE_ENTRENAMIENTO = pd.to_datetime('2025-01-01')
        FECHA_INICIO_PRUEBA = pd.to_datetime('2025-01-01')
        TS_SPLITS = 3
        
        metrica = "rmse"

        dias_impacto_pandemia = int(2.5 * 365.25)
        pandemia_covid = pd.DataFrame({
        'holiday': 'pandemia_covid',
        'ds': pd.to_datetime(['2020-03-23']),
        'lower_window': 0, 'upper_window': dias_impacto_pandemia,
        })

        #parametrizar en yaml fin

        df_prophet = self.serie.reset_index()[["Fecha", self.mapa_col[self.sexo.lower()]]]
        df_prophet.columns = ["ds", "y"]

        parametros = [dict(zip(param_grid_prophet.keys(), v)) for v in itertools.product(*param_grid_prophet.values())]
        logger.info(f"Se probarán {len(parametros)} combinaciones de hiperparámetros.")

        logger.info(f"DataFrame de eventos (Pandemia) creado con un impacto de {pandemia_covid['upper_window'][0]} días.")

        # --- División de Datos (2014-2022 vs 2023-2025) ---
        train_data = df_prophet[df_prophet['ds'] < FECHA_CORTE_ENTRENAMIENTO]
        test_data = df_prophet[df_prophet['ds'] >= FECHA_INICIO_PRUEBA]

        logger.info(f"Datos de entrenamiento: {len(train_data)} semanas (hasta {train_data['ds'].max().date()})")
        logger.info(f"Datos de prueba: {len(test_data)} semanas (desde {test_data['ds'].min().date()})")

        # úsqueda de Hiperparámetros 
        tscv = TimeSeriesSplit(n_splits=TS_SPLITS)
        best_rmse = float('inf')
        best_param = None

        for parametro in parametros:
            rmse_fold = []
            for train_idx, val_idx in tscv.split(train_data):
                train_fold = train_data.iloc[train_idx]
                val_fold = train_data.iloc[val_idx]
                try:
                    modelo_cv = Prophet(
                            yearly_seasonality=True,
                            weekly_seasonality=True,
                            daily_seasonality=False,
                            holidays=pandemia_covid,
                            **parametro
                    )

                    modelo_cv.add_seasonality(name='monthly', period=30.5,fourier_order=3)
                    modelo_cv.fit(train_fold)

                    future_cv = modelo_cv.make_future_dataframe(periods=len(val_fold),freq='W-MON')
                    forecast_cv = modelo_cv.predict(future_cv)
                    y_pred_cv = forecast_cv.iloc[-len(val_fold):]['yhat']

                    rmse_fold.append(np.sqrt(mean_squared_error(val_fold['y'],y_pred_cv)))
                
                except Exception as e:
                    logger.warning(f'Ocurrio excepcion {e}')
                    continue

                if rmse_fold:
                    mean_rmse = np.mean(rmse_fold)
                    if mean_rmse < best_rmse:
                        best_rmse = mean_rmse
                        best_param = parametro

        logger.info(f"Mejores parámetros encontrados: {best_rmse}")
        
        return best_param
    
    def train(self,parametros) -> pd.DataFrame:

        # parametrizar en yaml
        dias_impacto_pandemia = int(2.5 * 365.25)
        pandemia_covid = pd.DataFrame({
        'holiday': 'pandemia_covid',
        'ds': pd.to_datetime(['2020-03-23']),
        'lower_window': 0, 'upper_window': dias_impacto_pandemia,
        })

        FECHA_CORTE_ENTRENAMIENTO = pd.to_datetime('2025-01-01')
        FECHA_INICIO_PRUEBA = pd.to_datetime('2025-01-01')
        #

        # ponerlo como self
        df_prophet = self.serie.reset_index()[["Fecha", self.mapa_col[self.sexo.lower()]]]
        df_prophet.columns = ["ds", "y"]
        train_data = df_prophet[df_prophet['ds'] < FECHA_CORTE_ENTRENAMIENTO]
        test_data = df_prophet[df_prophet['ds'] >= FECHA_INICIO_PRUEBA]
        #

        modelo_final = Prophet(
                yearly_seasonality=30,
                weekly_seasonality=True,
                daily_seasonality=False,
                holidays=pandemia_covid,
                **parametros
            )
        
        modelo_final.add_seasonality(name='monthly', period=30.5, fourier_order=5)
        modelo_final.fit(train_data) # 2014-2022

        # --- Generación del Pronóstico a 3 Años ---
        horizonte_total = len(test_data)
        future_final = modelo_final.make_future_dataframe(periods=horizonte_total, freq="W-MON")
        forecast_final = modelo_final.predict(future_final)

        df_eval = pd.merge(
            test_data, # Contiene 'ds' e 'y' real
            forecast_final[['ds', 'yhat']], # Contiene 'ds' y 'yhat' predicho
            on='ds',
            how='left'
        )

        #logger.info(len(df_eval))
        df_eval = df_eval.dropna(subset=["yhat"])
        #logger.info(len(df_eval))
        #poner mensaje de cuantos se eliminan, se ajusto 

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

    def graficar(self, df_eval, titulo: str):

        plt.figure(figsize=(15, 5))
        plt.plot(df_eval['ds'], df_eval['y'], 'o-', label='Datos Reales')
        plt.plot(df_eval['ds'], df_eval['yhat'], 'x--', label='Pronóstico')
        plt.title(f'Pronóstico vs. Realidad ({self.region}) agrupamiento por {self.sexo})')
        plt.legend()
        plt.grid(alpha=0.3)
        plt.show()


    def run(self):

        #self.region = 'Urbana media'
        #self.region = 'Sur-Sureste vulnerable'
        self.region = 'Metropolitana alta'
        #self.region = 'Rural / dispersa'

        #self.sexo = 'hombres'
        #self.sexo = 'mujeres'
        self.sexo = 'todos'

        if self.filtrar_region():
            if self.agrupa():
                parametros = self.prophet_cross_val()
                df_eval = self.train(parametros)
     
                df_eval_2025 = df_eval[df_eval['ds'].dt.year == 2025]
                self.calcular_metricas(df_eval_2025, "2023 (Año 1 del Pronóstico)")
                self.graficar(df_eval_2025, "2025")

                #df_eval_2024 = df_eval[df_eval['ds'].dt.year == 2024]
                #self.calcular_metricas(df_eval_2024, "2023 (Año 2 del Pronóstico)")
                #self.graficar(df_eval_2023, "2024")

        #model, forecast = self.entrenar("incrementos_mujeres", periodos = 365)
        #self.graficar(model,forecast,'prueba')

        #Prueba inicio
        from src.utils.graficos import GraficosHelper 

        paths = conf.get("paths")
        padecimiento = conf.get('padecimiento')


        grafica = GraficosHelper(paths['figures'], 33)

                
        padecimientos = self.df["Padecimiento"].unique()


        
        for padecimiento in padecimientos:
            grafica.serie_tiempo(self.df[self.df['Padecimiento'] == padecimiento],padecimiento,False,True)
        
        

