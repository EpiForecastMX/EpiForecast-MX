import pandas as pd
from src.configuraciones.config_params import conf, logger
from src.utils import DirectoryManager

class CleanDataset:
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df.columns = [col.strip() for col in self.df.columns]
        self.columas_a_eliminar = conf["columnas_eliminar"]
        self.renglones_a_eliminar = conf["renglones_eliminar"]

    def _filtrar_padecimiento(self, padecimiento: str) -> None:
        
        logger.info(f"Filtrando datos por padecimiento: {padecimiento}")
        if "Padecimiento" in self.df.columns and padecimiento:
            self.df = self.df[self.df["Padecimiento"]
                            .astype(str)
                            .str.contains(padecimiento, case=False, na=False)]

    def _elimina_columnas(self) -> pd.DataFrame:
        """Elimina columnas indicadas en el archivo de configuración."""

        logger.info(f'Eliminando columnas : {self.columas_a_eliminar}')
        self.df.drop(columns=self.columas_a_eliminar, inplace=True, errors='ignore')
        logger.debug(f'Columnas restantes: {self.df.columns.tolist()}')

        return self.df
    
    def _sustituir_valores(self) -> pd.DataFrame:
        """Sustituye valores nulos en el DataFrame."""

        self.df["Valor"] = pd.to_numeric(self.df["Valor"].replace("-", "0"), errors="coerce")
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
    


    #def generate_reporte(self) -> None:



    def run(self) -> pd.DataFrame:
        
        self._filtrar_padecimiento(conf["reporte_EDA"]["filtro_padecimiento"])
        self._elimina_columnas()
        self._sustituir_valores()
        self._eliminar_registros()

        return self.df