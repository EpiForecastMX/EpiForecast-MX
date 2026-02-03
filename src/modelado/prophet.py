# src/utils/datos.py
import pandas as pd
from prophet import Prophet
from src.configuraciones.config_params import conf, logger
import matplotlib.pyplot as plt



class SerieTiempoProphet:
    def __init__(self, df: pd.DataFrame):
        
        self.df = df.copy()
        self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])

        self.serie = self.df.groupby("Fecha")[["incrementos_hombres", "incrementos_mujeres"]].sum()


    def entrenar(self, columna: str, periodos: int = 365):

        df_prophet = self.serie.reset_index()[["Fecha", columna]]
        df_prophet.columns = ["ds", "y"]

        model = Prophet()
        model.fit(df_prophet)

        future = model.make_future_dataframe(periods=periodos)
        forecast = model.predict(future)

        return model, forecast
    
    def graficar(self, model, forecast, titulo: str):

        fig = model.plot(forecast)
        plt.title(titulo)
        plt.xlabel("Fecha")
        plt.ylabel("Número de casos")
        plt.grid(True, color="lightgray", alpha=0.3, linestyle="--", linewidth=0.5)
        plt.show()



    def run(self):

        model, forecast = self.entrenar("incrementos_mujeres", periodos = 365)
        self.graficar(model,forecast,'prueba')

