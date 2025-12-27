# src/scripts/limpieza_dataset.py

import pandas as pd
from src.configuraciones.config_params import conf, logger
from src.datos.clean_dataset import CleanDataset

def main():

    raw_file = conf["data"]["raw_data_file"]
    logger.info(f"Cargando datos desde {raw_file}...")
    df = pd.read_csv(raw_file)

    clean_df = CleanDataset(df).run()

if __name__ == "__main__":
    main()