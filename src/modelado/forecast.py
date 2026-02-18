# src/modelado/forecast.py
import pickle
import pandas as pd
from pathlib import Path
from prophet import Prophet

from src.configuraciones.config_params import conf, logger

class ForecastModelLoader:
    
    def __init__(self, periodo, model_path=None):

        #self.model_path = conf['data']['model_train']
        self.model_path = Path(model_path) if model_path else Path(conf["data"]["model_train"])
        self.model = None
        self.periodo = periodo


    def load(self):

        #if not self.model_path.exists():
        #    raise FileNotFoundError(f"No se encontró el archivo: {self.model_path}")

        with open(self.model_path, "rb") as f:
            self.model = pickle.load(f)

    def predict(self,periodo: int):
        
        future = self.model.make_future_dataframe(periods=periodo, freq="W-MON")
        forecast = self.model.predict(future)

        return forecast
    
    def run(self) -> pd.DataFrame:
        
        self.load()
        forecast = self.predict(self.periodo)

        return forecast




