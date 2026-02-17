# src/datos/clean_dataset.py
import pandas as pd

from src.configuraciones.config_params import conf, logger


class CleanDataset:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df_raw = df.copy()

        # reglas de limpieza especificadas en limpieza.yaml
        self.columnas_a_eliminar = conf["columnas_eliminar"]
        self.valores_a_sustituir = conf["valores_sustituir"]
        self.registros_a_eliminar = conf["registros_eliminar"]

    def _elimina_columnas(self) -> pd.DataFrame:
        """Elimina las columnas indicadas en la configuración."""

        self.df.columns = [col.strip() for col in self.df.columns]

        existentes = set(self.df.columns)
        a_eliminar = set(self.columnas_a_eliminar)

        encontradas = a_eliminar & existentes
        no_encontradas = a_eliminar - existentes

        if encontradas:
            logger.debug("Eliminando columnas: {}", sorted(encontradas))
            self.df.drop(columns=encontradas, inplace=True)
        else:
            logger.info("No se encontraron en el DataFrame las columnas configuradas para eliminar.")

        if no_encontradas:
            logger.warning("Columnas no localizadas en el DataFrame: {}", sorted(no_encontradas))

        logger.debug("Columnas restantes: {}", self.df.columns.tolist())

        return self.df

    def _sustituir_valores(self) -> pd.DataFrame:
        """Aplica reglas de sustitución sobre el DataFrame, contando cambios por regla."""

        total_cambios = 0

        for regla in self.valores_a_sustituir:
            columna = regla["columna_objetivo"]
            viejo = regla["texto_a_reemplazar"]
            nuevo = regla["texto_sustituto"]

            logger.debug('Sustituyendo en columna "{}": "{}" → "{}"', columna, viejo, nuevo)

            if columna not in self.df.columns:
                logger.warning("Columna no encontrada: {} (regla omitida)", columna)
                continue

            serie = self.df[columna]

            try:
                coincidencias = (serie == viejo).sum()
            except Exception:
                coincidencias = (serie.astype(str) == str(viejo)).sum()

            if coincidencias:
                self.df[columna] = serie.replace(viejo, nuevo)
                total_cambios += int(coincidencias)

        logger.info("Total de sustituciones realizadas: {:,}", total_cambios)

        return self.df

    def _eliminar_registros(self) -> pd.DataFrame:
        """Elimina registros según las reglas configuradas."""

        registros_iniciales = len(self.df)
        logger.debug("Registros iniciales: {:,}", registros_iniciales)

        for regla in self.registros_a_eliminar:
            columna = regla["columna_objetivo"]
            valor = regla["valor"]

            if columna not in self.df.columns:
                logger.warning("Columna no encontrada: '{}'. Regla omitida.", columna)
                continue

            coincidencias = (self.df[columna] == valor).sum()
            logger.debug(
                "Regla | columna: '{}' | valor: '{}' | coincidencias: {}",
                columna, valor, coincidencias,
            )

            if coincidencias > 0:
                self.df = self.df[self.df[columna] != valor]

        registros_finales = len(self.df)
        eliminados = registros_iniciales - registros_finales

        logger.debug("Registros finales: {:,}", registros_finales)
        logger.info("Total de registros eliminados: {:,}", eliminados)

        return self.df

    def run(self) -> pd.DataFrame:

        if not self.columnas_a_eliminar:
            logger.info("No se especificaron columnas para eliminar.")
        else:
            logger.info("Columnas configuradas para eliminar: {}", len(self.columnas_a_eliminar))
            for contador, regla in enumerate(self.columnas_a_eliminar, start=1):
                logger.debug("Col {} | {}", contador, regla)
            self._elimina_columnas()

        if not self.valores_a_sustituir:
            logger.info("No se especificaron reglas de sustitución.")
        else:
            logger.info("Reglas de sustitución configuradas: {}", len(self.valores_a_sustituir))
            self._sustituir_valores()

        if not self.registros_a_eliminar:
            logger.info("No se especificaron registros para eliminar.")
        else:
            logger.info("Reglas de eliminación configuradas: {}", len(self.registros_a_eliminar))
            for contador, regla in enumerate(self.registros_a_eliminar, start=1):
                logger.debug("Reg {} | columna='{}' | valor='{}'", contador, regla["columna_objetivo"], regla["valor"])
            self._eliminar_registros()

        return self.df
