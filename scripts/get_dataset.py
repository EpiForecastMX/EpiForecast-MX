# src/scripts/get_dataset.py
from src.configuraciones.config_params import conf, logger
from src.datos.descarga_dataset import DatasetDownloader
from datetime import datetime
from pathlib import Path

if __name__ == "__main__":
    dataset_id = conf["download"]["dataset_id"]
    raw_file = conf["data"]["raw_data_file"]
    downloader = DatasetDownloader(dataset_id, raw_file)

    logger.info(
        f"Iniciando descarga del dataset | ID={dataset_id} | destino={Path(raw_file).resolve()} | "
        f"timestamp={datetime.now():%Y-%m-%d %H:%M:%S}"
    )

    downloader.run()
    
    logger.success(
        f"Proceso completado | archivo={Path(raw_file).resolve()} | timestamp={datetime.now():%Y-%m-%d %H:%M:%S}"
    )


