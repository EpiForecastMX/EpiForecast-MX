# src/scripts/realiza_prep.py
import pandas as pd

from src.configuraciones.config_params import conf, logger
from src.datos.preparacion import dataTransformation
from src.utils import directory_manager


def transforma_dataset() -> bool:
    interim_file = conf["data"]["interim_data_file"]

    logger.info(f"Cargando datos desde {interim_file}...")

    if not directory_manager.existe_archivo(interim_file):
        logger.error(f"No se pudo localizar el archivo filtrado: {interim_file}")
        return False

    df = pd.read_csv(interim_file)
    dataTransformation(df).run()



def main():
    transforma_dataset()


if __name__ == "__main__":
    main()