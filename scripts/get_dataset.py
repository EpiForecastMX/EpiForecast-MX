# src/scripts/get_dataset.py
from src.configuraciones.config_params import conf, logger
from src.datos.descarga_dataset import DatasetDownloader
from datetime import datetime
from pathlib import Path

if __name__ == "__main__":
    configuracion_descarga = conf["download"]
    raw_path = conf["paths"]["raw"]
    raw_file = conf["data"]["raw_data_file"]
    downloader = DatasetDownloader(configuracion_descarga, raw_path,raw_file)

    id_descarga = configuracion_descarga["dataset_id"]

    logger.info(
        f"Iniciando descarga del dataset | destino={Path(raw_path).resolve()} | "
        f"timestamp={datetime.now():%Y-%m-%d %H:%M:%S}"
    )

    logger.debug(
        f"Configuracion de descarga | ID={configuracion_descarga["dataset_id"]} | destino={Path(raw_path).resolve()} | "
        f" archivo = {Path(raw_file).resolve()} | cookies={configuracion_descarga["cookies"]} | force = {configuracion_descarga['force']}"
    )

    downloader.run()
    
    logger.success(
        f"Proceso completado | archivo={Path(raw_path).resolve()} | timestamp={datetime.now():%Y-%m-%d %H:%M:%S}"
    )


