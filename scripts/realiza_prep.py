# src/scripts/realiza_prep.py
import pandas as pd

from src.configuraciones.config_params import conf, logger
from src.datos.preparacion import dataTransformation
from src.utils import directory_manager


def transforma_dataset() -> tuple[bool, pd.DataFrame | None]:
    interim_file = conf["data"]["interim_data_file"]
    transform_file = conf["data"]["data_prepare"]
    transform_path = conf["paths"]["processed"]

    logger.info(f"Cargando datos desde {interim_file}...")

    if not directory_manager.existe_archivo(interim_file):
        logger.error(f"No se pudo localizar el archivo filtrado: {interim_file}")
        return False, None

    df = pd.read_csv(interim_file)
    df_transformado = dataTransformation(df).run()

    if not df_transformado.empty:
        directory_manager.asegurar_ruta(transform_path)
        logger.success(f'Archivo procesado guardado en {transform_file}')
        df_transformado.to_csv(transform_file, index=False)

    else:
        logger.error('No se pudo guardar el archivo filtrado: {interim_file}')



def main():
    transforma_dataset()


if __name__ == "__main__":
    main()