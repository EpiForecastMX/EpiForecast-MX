# src/datos/descarga_dataset.py
import gdown
from loguru import logger
from src.utils import paths

# Clase encargada de descargar datasets desde Google Drive a una ruta local

class DatasetDownloader:
    # Inicialización de la clase y definición de parámetros
    def __init__(self, dataset_id: str, output_path: str):
        self.dataset_id = dataset_id    # ID del dataset en Google Drive
        self.output_path = output_path  # Ruta local donde se guardará el archivo descargado

    # Preparación del directorio de salida
    def prepare_directory(self):
        logger.debug(f"Creando directorio: {self.output_path}") # Log de creación de carpeta
        paths.asegurar_ruta(self.output_path)                     # Asegura que la carpeta exista

    # Descarga del dataset desde Google Drive
    def download(self):
        logger.info(f"Descargando dataset desde Google Drive (ID: {self.dataset_id})...")   # Log de inicio
        gdown.download(id=self.dataset_id, output=self.output_path, quiet=True)             # Descarga el archivo
        logger.success(f"Archivo descargado exitosamente en: {self.output_path}")           # Log de éxito

    # Ejecución completa del proceso de descarga
    def run(self):
        self.prepare_directory()    # Crea la carpeta de salida si no existe
        self.download()             # Descarga el dataset