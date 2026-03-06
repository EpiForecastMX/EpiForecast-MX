"""Data cleaning: entity normalization, week-shift, outlier treatment."""

# src/datos/clean_dataset.py
from typing import Any

import pandas as pd

from epiforecast.utils.config import conf, logger


class CleanDataset:
    """Aplica las reglas de limpieza definidas en config/limpieza.yaml a un DataFrame.

    Expone `resumen()` con las métricas del proceso para construir SeccionNota en reportes.
    """

    def __init__(self, df: pd.DataFrame, config: dict[str, Any] | None = None) -> None:
        """Inicializa el limpiador con el DataFrame y reglas de configuración.

        Args:
            df: DataFrame de datos epidemiológicos crudos.
            config: Dict de configuración (default: conf global de YAML).
        """
        _conf = config if config is not None else conf
        self.df = df.copy()
        self._filas_inicial: int = len(df)
        self._cols_inicial: int = df.shape[1]

        # Reglas de limpieza definidas en limpieza.yaml
        self.columnas_a_eliminar: list[str] = _conf["columnas_eliminar"]
        self.valores_a_sustituir: list[dict[str, str]] = _conf["valores_sustituir"]
        self.registros_a_eliminar: list[dict[str, Any]] = _conf["registros_eliminar"]

        # Métricas acumuladas durante la limpieza
        self._columnas_eliminadas: list[str] = []
        self._sustituciones: int = 0
        self._registros_eliminados: int = 0

    def resumen(self) -> dict[str, str]:
        """Retorna las métricas de la limpieza como dict clave-valor (para SeccionNota)."""
        cols_eliminadas_str = (
            ", ".join(self._columnas_eliminadas) if self._columnas_eliminadas else "—"
        )
        return {
            "Filas antes": f"{self._filas_inicial:,}",
            "Filas después": f"{len(self.df):,}",
            "Registros eliminados": f"{self._registros_eliminados:,}",
            "Columnas antes": f"{self._cols_inicial}",
            "Columnas eliminadas": f"{len(self._columnas_eliminadas)}  ({cols_eliminadas_str})",
            "Sustituciones aplicadas": f"{self._sustituciones:,}",
        }

    # ---------- Pasos de limpieza ---------- #

    def _normalizar_columnas(self) -> None:
        """Elimina espacios en blanco de los nombres de todas las columnas."""
        self.df.columns = pd.Index([col.strip() for col in self.df.columns])

    def _elimina_columnas(self) -> None:
        """Elimina las columnas indicadas en la configuración."""
        existentes = set(self.df.columns)
        a_eliminar = set(self.columnas_a_eliminar)

        encontradas = sorted(a_eliminar & existentes)
        no_encontradas = sorted(a_eliminar - existentes)

        if encontradas:
            logger.debug("Eliminando columnas: {}", encontradas)
            self.df.drop(columns=encontradas, inplace=True)
            self._columnas_eliminadas.extend(encontradas)
        else:
            logger.info(
                "No se encontraron en el DataFrame las columnas configuradas para eliminar."
            )

        if no_encontradas:
            logger.warning("Columnas no localizadas en el DataFrame: {}", no_encontradas)

        logger.debug("Columnas restantes: {}", self.df.columns.tolist())

    def _sustituir_valores(self) -> None:
        """Aplica reglas de sustitución sobre el DataFrame, contando cambios por regla."""
        total_cambios = 0

        for regla in self.valores_a_sustituir:
            columna = regla["columna_objetivo"]
            viejo = regla["texto_a_reemplazar"]
            nuevo = regla["texto_sustituto"]

            logger.debug('Sustituyendo en "{}": "{}" → "{}"', columna, viejo, nuevo)

            if columna not in self.df.columns:
                logger.warning("Columna no encontrada: '{}' (regla omitida)", columna)
                continue

            serie = self.df[columna]
            try:
                coincidencias = int((serie == viejo).sum())
            except TypeError:
                coincidencias = int((serie.astype(str) == str(viejo)).sum())

            if coincidencias:
                self.df[columna] = serie.replace(viejo, nuevo)
                total_cambios += coincidencias

        logger.info("Total de sustituciones realizadas: {:,}", total_cambios)
        self._sustituciones = total_cambios

    def _eliminar_registros(self) -> None:
        """Elimina registros según las reglas configuradas y reestablece el índice."""
        filas_antes = len(self.df)

        for regla in self.registros_a_eliminar:
            columna = regla["columna_objetivo"]
            valor = regla["valor"]

            if columna not in self.df.columns:
                logger.warning("Columna no encontrada: '{}'. Regla omitida.", columna)
                continue

            coincidencias = int((self.df[columna] == valor).sum())
            logger.debug(
                "Regla | columna: '{}' | valor: '{}' | coincidencias: {}",
                columna,
                valor,
                coincidencias,
            )

            if coincidencias > 0:
                self.df = self.df[self.df[columna] != valor]

        self.df = self.df.reset_index(drop=True)
        self._registros_eliminados = filas_antes - len(self.df)
        logger.info("Registros eliminados: {:,}", self._registros_eliminados)

    # ---------- Punto de entrada ---------- #

    def run(self) -> pd.DataFrame:
        """Ejecuta el pipeline de limpieza: normaliza, elimina, sustituye y retorna DataFrame limpio."""
        logger.info(
            "Iniciando limpieza | filas: {:,} | columnas: {}",
            self._filas_inicial,
            self._cols_inicial,
        )

        self._normalizar_columnas()

        if self.columnas_a_eliminar:
            logger.info("Columnas a eliminar configuradas: {}", len(self.columnas_a_eliminar))
            self._elimina_columnas()
        else:
            logger.info("No se especificaron columnas para eliminar.")

        if self.valores_a_sustituir:
            logger.info("Reglas de sustitución configuradas: {}", len(self.valores_a_sustituir))
            self._sustituir_valores()
        else:
            logger.info("No se especificaron reglas de sustitución.")

        if self.registros_a_eliminar:
            logger.info("Reglas de eliminación configuradas: {}", len(self.registros_a_eliminar))
            self._eliminar_registros()
        else:
            logger.info("No se especificaron registros para eliminar.")

        logger.info(
            "Limpieza completada | filas: {:,} → {:,} | columnas: {} → {}",
            self._filas_inicial,
            len(self.df),
            self._cols_inicial,
            self.df.shape[1],
        )
        return self.df
