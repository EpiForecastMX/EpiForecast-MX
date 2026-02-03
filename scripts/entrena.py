# src/scripts/entrena.py
import pandas as pd
from src.modelado.prophet import SerieTiempoProphet
from src.configuraciones.config_params import conf, logger


def main():

    ruta_datos = conf['data']['data_prepare']
    df_entrenamiento = pd.read_csv(ruta_datos)
    SerieTiempoProphet(df_entrenamiento).run()


if __name__ == "__main__":
    main()