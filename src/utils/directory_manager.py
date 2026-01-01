# src/utils/directory_manager.py
from pathlib import Path
from loguru import logger


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
        logger.info(f"Creando carpeta contenedora para archivo: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        logger.info(f"Creando carpeta: {path}")
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

def limpia_carpeta(path_str: str | Path) -> None:
    """
    Elimina todos los archivos dentro de una carpeta especificada.

    :param path_str: Ruta de la carpeta como str o Path.
    """
    path = Path(path_str)

    if not path.is_dir():
        raise ValueError(f"La ruta {path} no es una carpeta válida.")

    for archivo in path.iterdir():
        if archivo.is_file():
            logger.debug(f"Eliminando archivo: {archivo}")
            archivo.unlink()

