# scripts/get_dataset.py

from pathlib import Path
import shutil
import sys

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger

if __name__ == "__main__":
    raw_path = conf["paths"]["raw"]
    raw_file = conf["data"]["raw_data_file"]
    boletin_file = conf["data"]["boletin"]

    if not directory_manager.existe_archivo(boletin_file):
        sys.exit(1)

    archivo_final = Path(raw_file).resolve()
    logger.info(
        "Iniciando obtención del dataset | origen={} | destino={}", boletin_file, archivo_final
    )

    directory_manager.asegurar_ruta(raw_path)
    shutil.copy(boletin_file, raw_file)

    logger.success("Proceso completado | archivo={}", archivo_final)
