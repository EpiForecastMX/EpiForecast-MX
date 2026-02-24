# scripts/mapea.py
import pandas as pd
import sys

from src.configuraciones.config_params import conf, logger
from src.modelado.mapea_inegi import MapeaInegi
from src.utils import directory_manager


def main():
    transform_path = conf["data"]["data_prepare"]

    logger.info("Iniciando mapeo INEGI | archivo fuente: {}", transform_path)

    if not directory_manager.existe_archivo(transform_path):
        logger.error("No se pudo localizar el archivo: {}", transform_path)
        sys.exit(1)

    dataset = pd.read_csv(transform_path)

    MapeaInegi(dataset).run()

    logger.success("Mapeo INEGI completado.")


if __name__ == "__main__":
    main()