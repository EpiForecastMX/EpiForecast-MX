"""Path management utilities: directory creation and normalization."""

# src/utils/directory_manager.py

from pathlib import Path

from loguru import logger


def asegurar_ruta(path_str: str | Path) -> Path:
    path = Path(path_str)

    if path.exists():
        logger.debug(f"Carpeta existente: {path}")

    else:
        logger.warning(f"Carpeta no encontrada, creando: {path}")
        path.mkdir(parents=True, exist_ok=True)

    return path


def existe_archivo(path_str: str | Path) -> bool:
    path = Path(path_str)

    if path.is_file():
        logger.debug(f"Archivo encontrado: {path}")
        resultado = True
    else:
        logger.error(f"Archivo no encontrado: {path}")
        resultado = False

    return resultado


def limpia_carpeta(path_str: str | Path) -> None:
    """
    Elimina todos los archivos dentro de una carpeta especificada.

    :param path_str: Ruta de la carpeta como str o Path.
    """
    path = Path(path_str)

    logger.debug(f"Limpiando carpeta: {path}")

    if not path.is_dir():
        raise ValueError(f"La ruta {path} no es una carpeta válida.")

    for archivo in path.iterdir():
        if archivo.is_file():
            logger.debug(f"Eliminando archivo: {archivo}")
            archivo.unlink()
