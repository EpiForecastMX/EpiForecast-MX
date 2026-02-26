# scripts/realiza_prep.py
import pandas as pd

from epiforecast.data.preprocessing.transformer import DataTransformation
from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger


def transforma_dataset() -> tuple[bool, pd.DataFrame | None]:
    interim_file = conf["data"]["interim_data_file"]
    transform_file = conf["data"]["data_prepare"]
    transform_path = conf["paths"]["processed"]

    logger.info("Cargando datos desde: {}", interim_file)

    if not directory_manager.existe_archivo(interim_file):
        logger.error("No se pudo localizar el archivo interim: {}", interim_file)
        return False, None

    df = pd.read_csv(interim_file)
    df_transformado = DataTransformation(df).run()

    if df_transformado.empty:
        logger.error(
            "La transformación produjo un DataFrame vacío. No se guardó: {}", transform_file
        )
        return False, None

    directory_manager.asegurar_ruta(transform_path)
    directory_manager.advertir_sobrescritura(transform_file)
    df_transformado.to_csv(transform_file, index=False)
    logger.success("Archivo procesado guardado: {}", transform_file)

    return True, df_transformado


def main():
    resultado, _ = transforma_dataset()

    if not resultado:
        logger.error("Transformación no completada. Abortando.")


if __name__ == "__main__":
    main()
