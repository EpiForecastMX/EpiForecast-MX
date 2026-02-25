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
    path = Path(path_str).resolve()

    if path.is_file():
        logger.debug(f"Archivo encontrado: {path}")
        return True

    logger.debug(f"Archivo no encontrado: {path}")
    return False


def advertir_sobrescritura(path_str: str | Path) -> bool:
    path = Path(path_str).resolve()
    if path.is_file():
        logger.warning(f"Archivo encontrado, será sobrescrito: {path}")
        return True
    logger.info(f"Archivo no encontrado, se creará: {path}")
    return False


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
