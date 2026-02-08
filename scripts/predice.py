#scripts/predice.py
import pandas as pd
from src.modelado.forecast import ForecastModelLoader
from src.configuraciones.config_params import conf, logger

def main():
    
    ruta = conf['data']['forecast']
    forecast = ForecastModelLoader(60).run()
    logger.info(ruta)
    forecast.to_csv(ruta)
    


if __name__ == "__main__":
    main()