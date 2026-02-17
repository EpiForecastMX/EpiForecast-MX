# scripts/get_dataset.py

import shutil
from datetime import datetime
from pathlib import Path

from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager

if __name__ == "__main__":

    raw_path = conf["paths"]["raw"]
    raw_file = conf["data"]["raw_data_file"]
    boletin_file = conf["data"]["boletin"]
    
    localizado = directory_manager.existe_archivo(boletin_file)

    if localizado:
        destino = Path(raw_path).resolve()
        archivo_final = Path(raw_file).resolve()

        logger.info(
            "Iniciando obtención del dataset | destino={} | timestamp={}",
            destino,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        directory_manager.asegurar_ruta(raw_path)
        shutil.copy(boletin_file, raw_file)

        logger.success(
            "Proceso completado | archivo={} | timestamp={}",
            archivo_final,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        
    else:
        logger.error("Archivo no localizado | archivo={}", boletin_file)
