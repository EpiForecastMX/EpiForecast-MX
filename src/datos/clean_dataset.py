# src/datos/clean_dataset.py
import pandas as pd
from src.configuraciones.config_params import conf, logger

class CleanDataset:
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df_raw = df.copy()
        self.df.columns = [col.strip() for col in self.df.columns]

        #reglas de limpieza especificadas en limpieza.yaml
        self.columas_a_eliminar = conf["columnas_eliminar"]
        self.valores_sustituir = conf["valores_sustituir"]
        self.registros_eliminar = conf["registros_eliminar"]

    def _filtrar_padecimiento(self, padecimiento: str) -> bool:

        if "Padecimiento" not in self.df.columns:
            logger.error("No se puede filtrar: la columna 'Padecimiento' no existe en el DataFrame.")
            return False
        
        if self.df.empty:
            logger.error("No se puede filtrar, DataFrame vacío.")
            return False
        
        logger.info(f"Filtrando datos por padecimiento: {padecimiento}")
        
        if "Padecimiento" in self.df.columns and padecimiento:
            self.df = self.df[self.df["Padecimiento"]
                            .astype(str)
                            .str.contains(padecimiento, case=False, na=False)]
            
        total_despues = len(self.df)

        if total_despues == 0:
            logger.warning(f"No se encontraron registros relacionados con el padecimiento: '{padecimiento}'.")
            self.df = self.df_raw.copy()
            
        return True
            


    def _elimina_columnas(self) -> pd.DataFrame:
        """Elimina columnas indicadas en el archivo de configuración."""

        columnas_existentes = set(self.df.columns)
        columnas_a_eliminar = set(self.columas_a_eliminar)
        columnas_encontradas = columnas_existentes.intersection(columnas_a_eliminar)
        columnas_no_encontradas = columnas_a_eliminar - columnas_existentes

        if columnas_encontradas:
            logger.debug(f"Eliminando columnas: {sorted(columnas_encontradas)}")
            self.df.drop(columns=columnas_encontradas, inplace=True)
        else:
            logger.info("Ninguna de las columnas a eliminar está presente en el DataFrame.")

        if columnas_no_encontradas:
            logger.warning(f"Columnas no encontradas y no eliminadas: {sorted(columnas_no_encontradas)}")

        logger.debug(f"Columnas restantes: {self.df.columns.tolist()}")


        return self.df
    
    def _sustituir_valores(self) -> pd.DataFrame:

        for regla in self.valores_sustituir:
            nombre_columna = regla["columna_objetivo"]
            valor_actual = regla["texto_a_reemplazar"]
            valor_nuevo = regla["texto_sustituto"]
            logger.debug(f'Sustituyendo en columna "{nombre_columna}": "{valor_actual}" por "{valor_nuevo}"')
            self.df[nombre_columna] = self.df[nombre_columna].replace(valor_actual, valor_nuevo)

        return self.df
    

    def _eliminar_registros(self) -> pd.DataFrame:
        """Elimina registros indicados en el archivo de configuración."""

        numero_registros_inicial = len(self.df)
        logger.debug(f'Número de registros inicial: {numero_registros_inicial}')

        for registro in self.registros_eliminar:
            logger.debug(f'Eliminando registros de la columna: {registro["nombre"]} con valor: {registro["valor"]}')
            nombre = registro["nombre"]
            valor = [registro["valor"]]
            self.df = self.df[~self.df[nombre].isin(valor)]


        numero_registros_final = len(self.df)
        logger.debug(f'Número de registros final: {numero_registros_final}')
        logger.info(f'Registros eliminados: {numero_registros_inicial - numero_registros_final}')

        return self.df

    def run(self) -> pd.DataFrame:
      
        filtrado = self._filtrar_padecimiento(conf["reporte_EDA"]["filtro_padecimiento"])

        if filtrado:

            if self.columas_a_eliminar is None or not self.columas_a_eliminar:
                logger.info("No se especificaron columnas para eliminar.")
            else:
                num_cols = len(self.columas_a_eliminar)
                logger.info(
                f'Se encontraron {num_cols} columnas configuradas para eliminar: {self.columas_a_eliminar}'
                )
                self._elimina_columnas()

            if self.valores_sustituir is None or not self.valores_sustituir:
                logger.info("No se especificaron registros para sustituir.")
        
            else:
                self._sustituir_valores()

            if self.registros_eliminar is None or not self.registros_eliminar:
                logger.info("No se especificaron registros para eliminar.")
        
            else:
                self._eliminar_registros()


        return self.df