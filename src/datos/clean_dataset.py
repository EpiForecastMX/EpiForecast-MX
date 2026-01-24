# src/datos/clean_dataset.py
import pandas as pd

from src.configuraciones.config_params import conf, logger

class CleanDataset:
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df_raw = df.copy()

        #reglas de limpieza especificadas en limpieza.yaml
        self.columas_a_eliminar = conf.get("columnas_eliminar")
        self.valores_a_sustituir = conf.get("valores_sustituir")
        self.registros_a_eliminar = conf.get("registros_eliminar")

    def _elimina_columnas(self) -> pd.DataFrame:
        """Elimina las columnas indicadas en la configuración."""

        self.df.columns = [col.strip() for col in self.df.columns]

        existentes = set(self.df.columns)
        a_eliminar = set(self.columas_a_eliminar)

        encontradas = a_eliminar & existentes
        no_encontradas = a_eliminar - existentes

        if encontradas:
            logger.debug(f"Eliminando columnas: {sorted(encontradas)}")
            self.df.drop(columns=encontradas, inplace=True)
        else:
            logger.info("No se encontraron en el DataFrame las columnas configuradas para eliminar.")

        if no_encontradas:
            logger.warning(f"Columnas no localizadas: {sorted(no_encontradas)}")

        logger.debug(f"Columnas restantes: {self.df.columns.tolist()}")

        return self.df

    def _sustituir_valores(self) -> pd.DataFrame:
        """Aplica reglas de sustitución sobre el DataFrame, contando cambios por regla."""

        total_cambios = 0

        for regla in self.valores_a_sustituir:
            columna = regla["columna_objetivo"]
            viejo = regla["texto_a_reemplazar"]
            nuevo = regla["texto_sustituto"]

            logger.debug(f'Sustituyendo en columna "{columna}": "{viejo}" por "{nuevo}"')

            if columna not in self.df.columns:
                logger.warning(f"Columna no encontrada: {columna} (regla omitida)")
                continue

            serie = self.df[columna]
            
            try:
                coincidencias = (serie == viejo).sum()
            except Exception:
                coincidencias = (serie.astype(str) == str(viejo)).sum()

            if coincidencias:
                        self.df[columna] = serie.replace(viejo, nuevo)
                        total_cambios += int(coincidencias)

            logger.info(f"Se realizaron {total_cambios} actualizaciones.")

        return self.df

    def _eliminar_registros(self) -> pd.DataFrame:

        """Elimina registros según las reglas configuradas."""

        registros_iniciales = len(self.df)
        logger.debug(f"Registros iniciales: {registros_iniciales}")

        for regla in self.registros_a_eliminar:
            columna = regla.get("columna_objetivo")
            valor = regla.get("valor")

            if columna not in self.df.columns:
                logger.warning(f"Columna no encontrada: '{columna}'. Regla omitida.")
                continue

            coincidencias = (self.df[columna] == valor).sum()
            logger.debug(
                f"Regla -> columna: '{columna}' | valor: '{valor}' | "
                f"Coincidencias encontradas: {coincidencias}"
            )

            if coincidencias > 0:
                self.df = self.df[self.df[columna] != valor]

        registros_finales = len(self.df)
        eliminados = registros_iniciales - registros_finales

        logger.debug(f"Registros finales: {registros_finales}")
        logger.info(f"Total de registros eliminados: {eliminados}")

        return self.df

    def run(self) -> pd.DataFrame:

        if not self.columas_a_eliminar:
            logger.info("No se especificaron columnas para eliminar.")
        
        else:
            logger.info(f"Se encontraron {len(self.columas_a_eliminar)} registro(s) configurado(s) para eliminar.")
            for contador, regla in enumerate(self.columas_a_eliminar, start=1):
                logger.debug(f"Reg {contador} | columna = {regla}")

            self._elimina_columnas()
        
        if not self.valores_a_sustituir:
            logger.info("No se especificaron registros para sustituir.")
        
        else:
            logger.info(f"Total de reglas de sustitución configuradas: {len(self.valores_a_sustituir)}")
            self._sustituir_valores()

        if not self.registros_a_eliminar:
            logger.info("No se especificaron registros para eliminar.")
        
        else:
            logger.info(f"Se encontraron {len(self.registros_a_eliminar)} registro(s) configurado(s) para eliminar.")
            for contador, regla in enumerate(self.registros_a_eliminar, start=1):
                logger.debug(f"Reg {contador} | columna = '{regla['columna_objetivo']}' | valor = {regla['valor']}")
            
            self._eliminar_registros()
        
        return self.df