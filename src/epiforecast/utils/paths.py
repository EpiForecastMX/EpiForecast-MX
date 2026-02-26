"""Path management utilities: directory creation and normalization."""

# src/utils/directory_manager.py

from pathlib import Path

from loguru import logger


def asegurar_ruta(path_str: str | Path) -> Path:
    """Crea el directorio si no existe y devuelve el Path resuelto.

    Args:
        path_str: Ruta del directorio a asegurar.

    Returns:
        Path del directorio (existente o recién creado).
    """
    path = Path(path_str)

    if path.exists():
        logger.debug(f"Carpeta existente: {path}")

    else:
        logger.warning(f"Carpeta no encontrada, creando: {path}")
        path.mkdir(parents=True, exist_ok=True)

    return path


def existe_archivo(path_str: str | Path) -> bool:
    """Verifica si un archivo existe en la ruta indicada.

    Args:
        path_str: Ruta del archivo a verificar.

    Returns:
        True si el archivo existe, False en caso contrario.
    """
    path = Path(path_str).resolve()

    if path.is_file():
        logger.debug(f"Archivo encontrado: {path}")
        return True

    logger.debug(f"Archivo no encontrado: {path}")
    return False


def advertir_sobrescritura(path_str: str | Path) -> bool:
    """Registra una advertencia si el archivo ya existe y será sobrescrito.

    Args:
        path_str: Ruta del archivo a verificar.

    Returns:
        True si el archivo existe (será sobrescrito), False si no.
    """
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
