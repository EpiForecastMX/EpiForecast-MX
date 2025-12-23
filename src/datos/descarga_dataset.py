# src/datos/descarga_dataset.py

import gdown
from loguru import logger
from src.utils import DirectoryManager

# Clase encargada de descargar datasets desde Google Drive a una ruta local

class DatasetDownloader:

    def __init__(self, dataset_id: str, output_path: str, force: bool = False):
        self.dataset_id = dataset_id    # ID del dataset en Google Drive
        self.output_path = output_path  # Ruta local donde se guardará el archivo descargado
        self.force = force

    
    def prepara_directorio(self) -> bool:
        """
        Prepara el directorio de salida.
        Retorna True si se debe descargar (no existe o force=True), False si NO.
        """
        DirectoryManager.asegurar_ruta(self.output_path)
        
        if DirectoryManager.existe_archivo(self.output_path) and not self.force:
            logger.info(f"El archivo ya existe: {self.output_path}. Se omite la descarga.")
            return False
        
        if self.force and DirectoryManager.existe_archivo(self.output_path):            
            logger.warning(f"El archivo existe pero 'force=True': se volverá a descargar -> {self.output_path}")
        else:
            logger.debug(f"Archivo no encontrado. Se descargará en: {self.output_path}")

        return True


    # Descarga del dataset desde Google Drive
    def descarga(self) -> None:
        logger.info(f"Descargando dataset desde Google Drive (ID: {self.dataset_id})...")
        gdown.download(id=self.dataset_id, output=self.output_path, quiet=True)
        logger.info(f"Archivo descargado exitosamente en: {self.output_path}")

    
    def run(self):
        descargar = self.prepara_directorio()
        if descargar:
            self.descarga()