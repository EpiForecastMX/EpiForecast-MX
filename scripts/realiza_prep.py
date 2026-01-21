# src/scripts/realiza_prep.py
import pandas as pd
from src.configuraciones.config_params import conf, logger
from src.datos.preparacion import dataTransformation

def main():

    interim_file = conf["data"]["interim_data_file"]

    logger.info(f"Cargando datos desde {interim_file}...")
    df = pd.read_csv(interim_file)

    dataTransformation(df).run()

    


if __name__ == "__main__":
    main()