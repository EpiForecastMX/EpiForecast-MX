# src/scripts/get_dataset.py
import shutil

from datetime import datetime
from pathlib import Path

from src.configuraciones.config_params import conf, logger
#from src.datos.descarga_dataset import DatasetDownloader
from src.utils import directory_manager


if __name__ == "__main__":
    #configuracion_descarga = conf["download"]
    raw_path = conf["paths"]["raw"]
    raw_file = conf["data"]["raw_data_file"]
    boletin_file = conf["data"]["boletin"]
    
    #downloader = DatasetDownloader(configuracion_descarga, raw_path,raw_file)
    #id_descarga = configuracion_descarga["dataset_id"]

    localizado = directory_manager.existe_archivo(boletin_file)

    if localizado:
        logger.info(
        f"Iniciando obtención del dataset | destino={Path(raw_path).resolve()} | archivo localizado {localizado} | "
        f"timestamp={datetime.now():%Y-%m-%d %H:%M:%S}"
        )
        
        directory_manager.asegurar_ruta(raw_path)
        shutil.copy(boletin_file, raw_file)
        
        logger.success(
        f"Proceso completado | archivo={Path(raw_path).resolve()} | timestamp={datetime.now():%Y-%m-%d %H:%M:%S}"
        )
        
    else:
        logger.error(f'Archivo {boletin_file} no localizado')


    #logger.debug(
    #    f"Configuracion de descarga | ID={configuracion_descarga["dataset_id"]} | destino={Path(raw_path).resolve()} | "
    #    f" archivo = {Path(raw_file).resolve()} | cookies={configuracion_descarga["cookies"]} | force = {configuracion_descarga['force']}"
    #)

    #downloader.run()
    
    


