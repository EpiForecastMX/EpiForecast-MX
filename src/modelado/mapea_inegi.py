# src/modelado/mapea_inegi.py
import pandas as pd
import sys 

from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager


class MapeaInegi:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        conf_paths = conf.get("data")
        self.inegi_path = conf_paths['inegi']
        self.final_path = conf_paths['data_inegi']
        self.xlsx_path = conf_paths['xlsx_inegi']
        self.inegi = pd.DataFrame
        self.df_merge = pd.DataFrame

    def renombra(self):
        
        map_entidades = {
            "Coahuila de Zaragoza": "Coahuila",
            "Michoacán de Ocampo": "Michoacán",
            "Veracruz de Ignacio de la Llave": "Veracruz",
        }
        
        self.inegi = self.inegi.rename(columns={"Entidad federativa": "Entidad"})        
        self.inegi["Entidad"] = self.inegi["Entidad"].replace(map_entidades)


    def combina(self):

        cols_extra = [c for c in self.inegi.columns if c != "Entidad"]

        self.df_merge = self.df.merge(
            self.inegi[["Entidad"] + cols_extra],
            on = "Entidad",
            how="left"
        )
        

    def run(self):

        if not directory_manager.existe_archivo(self.inegi_path):
            logger.error(f"No se pudo localizar el archivo de INEGI: {self.inegi_path}")
            sys.exit(1)

        self.inegi = pd.read_csv(self.inegi_path)

        self.renombra()
        self.combina()

        if not self.df_merge.empty:

            if directory_manager.existe_archivo(self.final_path):
                logger.warning(f"archivo {self.final_path} encontrado. El archivo será sobrescrito.")

            else:
                logger.info(f"archivo {self.final_path} no localizado. Guardando archivo.")
            
            self.df_merge.to_csv(self.final_path,index=False)
            self.df_merge.to_excel(self.xlsx_path,sheet_name="data",index=False)


