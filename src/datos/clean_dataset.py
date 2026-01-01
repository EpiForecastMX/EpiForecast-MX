# src/datos/clean_dataset.py
import pandas as pd
from src.configuraciones.config_params import conf, logger

class CleanDataset:
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df.columns = [col.strip() for col in self.df.columns]
        self.columas_a_eliminar = conf["columnas_eliminar"]
        self.renglones_a_eliminar = conf["renglones_eliminar"]
        self.valores_sustituir = conf["valores_sustituir"]
        self.cadena_sustituir = conf["sustituir_cadena"]

    def _filtrar_padecimiento(self, padecimiento: str) -> None:
        
        logger.info(f"Filtrando datos por padecimiento: {padecimiento}")
        if "Padecimiento" in self.df.columns and padecimiento:
            self.df = self.df[self.df["Padecimiento"]
                            .astype(str)
                            .str.contains(padecimiento, case=False, na=False)]

    def _elimina_columnas(self) -> pd.DataFrame:
        """Elimina columnas indicadas en el archivo de configuración."""

        logger.debug(f'Eliminando columnas : {self.columas_a_eliminar}')
        self.df.drop(columns=self.columas_a_eliminar, inplace=True, errors='ignore')
        logger.debug(f'Columnas restantes: {self.df.columns.tolist()}')

        return self.df
    
    def _sustituir_valores(self) -> pd.DataFrame:

        for regla in self.valores_sustituir:
            nombre_columna = regla["columna_objetivo"]
            valor_actual = regla["texto_a_reemplazar"]
            valor_nuevo = regla["texto_sustituto"]
            logger.debug(f'Sustituyendo en columna "{nombre_columna}": "{valor_actual}" por "{valor_nuevo}"')
            self.df[nombre_columna] = self.df[nombre_columna].replace(valor_actual, valor_nuevo)

        for regla in self.cadena_sustituir:
            nombre_columna = regla["columna_objetivo"]
            valor_actual = regla["texto_a_reemplazar"]
            valor_nuevo = regla["texto_sustituto"]
            tipo_dato = regla["tipo"]
            logger.debug(f'Sustituyendo en columna "{nombre_columna}": "{valor_actual}" por "{valor_nuevo}" convertir a tipo "{tipo_dato}"')
            
            if not nombre_columna or nombre_columna not in self.df.columns:
                logger.debug(f'Columna no identificada {nombre_columna}')
                pass

            
            self.df[nombre_columna] = (
                self.df[nombre_columna]
                .astype(str)
                .str.replace(valor_actual, valor_nuevo, regex=False)  # subcadena literal
                .str.strip()
                .pipe(pd.to_numeric, errors='coerce')
                .astype(tipo_dato)  # opcional: enteros anulables
                )
            
        return self.df

    def _eliminar_registros(self) -> pd.DataFrame:
        """Elimina registros indicados en el archivo de configuración."""

        numero_registros_inicial = len(self.df)
        logger.debug(f'Número de registros inicial: {numero_registros_inicial}')

        for renglon in self.renglones_a_eliminar:
            logger.debug(f'Eliminando registros de la columna: {renglon["Nombre"]} con valor: {renglon["valor"]}')
            nombre = renglon["Nombre"]
            valor = renglon["valor"]
            self.df = self.df[~self.df[nombre].isin(valor)]

        logger.debug('Eliminando registros con valores nulos...')
        logger.debug(f'Número de registros nulos: {self.df.isnull().sum().sum()}')
        self.df = self.df.dropna()
        numero_registros_final = len(self.df)
        logger.debug(f'Número de registros final: {numero_registros_final}')
        logger.info(f'Registros eliminados: {numero_registros_inicial - numero_registros_final}')

        return self.df
    

    def run(self) -> pd.DataFrame:
        
        self._filtrar_padecimiento(conf["reporte_EDA"]["filtro_padecimiento"])
        self._elimina_columnas()
        self._sustituir_valores()
        self._eliminar_registros()

        return self.df