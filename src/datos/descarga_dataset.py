# src/datos/descarga_dataset.py
from datetime import datetime
from pathlib import Path

import gdown
import pandas as pd
from loguru import logger

from src.utils import directory_manager


# Clase encargada de descargar datasets desde Google Drive a una ruta local

class DatasetDownloader:

    def __init__(self, configuracion: str, output_path: str, archivo_raw: str):
        self.dataset_id = configuracion["dataset_id"]    # ID del dataset en Google Drive
        self.use_cookies = configuracion["cookies"]
        self.output_path = output_path  # Ruta local donde se guardará el archivo descargado
        self.salida_raw = archivo_raw
        self.force = configuracion["force"] 
    
    def prepara_directorio(self) -> bool:
        """
        Prepara el directorio de salida.
        Retorna True si se debe descargar (no existe o force=True), False si NO.
        """
        directory_manager.asegurar_ruta(self.output_path)
        
        if directory_manager.existe_archivo(self.salida_raw) and not self.force:
            logger.info(f"El archivo ya existe: {self.salida_raw}. Se omite la descarga.")
            return False
        
        if self.force and directory_manager.existe_archivo(self.salida_raw):            
            logger.warning(f"'force' habilitado; los archivos existentes serán sobrescritos → {self.salida_raw}")
        else:
            logger.debug(f"Archivo no encontrado. Se descargará en: {self.salida_raw}")

        return True

    def descarga(self) -> None:
        logger.info(f"Descargando carpeta de Google Drive (ID: {self.dataset_id})...")
        directory_manager.limpia_carpeta(self.output_path)
        
        paths = gdown.download_folder(
                id=self.dataset_id,
                output=str(self.output_path),
                quiet=True,
                use_cookies=self.use_cookies,
                remaining_ok=True
            )
        
        if not paths:
                logger.warning("No se descargó ningún archivo. Verifica permisos o que la carpeta no esté vacía.")
                return []
        
        logger.info(f"Descarga completada. Archivos guardados en: {self.output_path}")
        return paths

    def agrupar_archivos(self) -> None:
        ruta = Path(self.output_path)
        archivos = sorted(ruta.glob("*.csv"))
        archivo_final = Path(self.salida_raw)
       
        if archivo_final.exists():            
            creado = datetime.fromtimestamp(archivo_final.stat().st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            modificado = datetime.fromtimestamp(archivo_final.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            logger.warning(f"El archivo de salida localizado, finalizando proceso")
            logger.debug(f"Ruta: {archivo_final} | tamaño: {archivo_final.stat().st_size} | Creado: {creado} | Modificado: {modificado}")
            return None

        if not archivos:
            logger.warning(f"No se encontraron CSV en {ruta}")
            return None
        
        logger.info(f"Archivos localizados-> {len(archivos)}")

        if len(archivos) == 1:
            archivo_unico = archivos[0]
            logger.info(f"Solo se encontró un archivo: {archivo_unico}")
            logger.info(f"Renombrando a: {self.salida_raw}")
        
            archivo_unico.rename(self.salida_raw)

            logger.info("Archivo renombrado correctamente.")
            return None


        logger.info("Unificando archivos CSV...")

        df_final = pd.read_csv(archivos[0])
        logger.debug(f"Primer archivo leído: {archivos[0]}")

        for f in archivos[1:]:
            logger.debug(f"Concatenando archivo: {f}")
            df = pd.read_csv(f)
            df_final = pd.concat([df_final, df], ignore_index=True)

        df_final.to_csv(self.salida_raw, index=False)
        logger.info(f"Archivo combinado guardado en: {self.salida_raw}")

    
    def run(self):
        descargar = self.prepara_directorio()
        if descargar:
            self.descarga()
            self.agrupar_archivos()
        
