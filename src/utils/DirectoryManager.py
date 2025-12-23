import os

from pathlib import Path
from typing import Optional


def asegurar_ruta(path_str: str | Path) -> Path:
    """
    Convierte un string o Path en objeto Path y crea los directorios necesarios.

    - Si la ruta es un directorio, lo crea directamente.
    - Si la ruta es un archivo, crea su carpeta contenedora.

    Args:
        path_str (str | Path): Ruta (archivo o carpeta) a convertir/crear.

    Returns:
        Path: Objeto Path garantizado (no crea el archivo, solo el directorio padre).
    """
    path = Path(path_str)

    # Si es archivo, crear carpeta contenedora
    if path.suffix:
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Si es directorio, crear directamente
        path.mkdir(parents=True, exist_ok=True)

    return path



def existe_archivo(path_str: str | Path) -> bool:
    """
    Verifica si un archivo existe en el sistema de archivos.

    :param path_str: Ruta del archivo como str o Path.
    :return: True si el archivo existe, False en caso contrario.
    """
    path = Path(path_str)  # Convertimos a Path para manejar ambos tipos
    return path.is_file()  # is_file() asegura que sea un archivo, no un directorio
