# src/scripts/entrena.py
import pandas as pd
import pickle
import re
import unicodedata
import os
from datetime import datetime

from src.modelado.prophet import SerieTiempoProphet
from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager


def normalizar(region: str) -> str:
     
    formato = unicodedata.normalize("NFKD", region).encode("ascii", "ignore").decode("ascii")
    region_normalizado = re.sub(r"\s+", "_", formato)
    return region_normalizado
     

def main():

    
    fecha = datetime.now().strftime("%Y%m%d")

    modelado_estados = conf['padecimiento']['modelado_estados']
    model_path = conf['paths']['models']
    valores_sexo = conf['valores_sexo']
    mapeo = conf['mapeo_columnas']

    ruta_datos = conf['data']['data_inegi']
    df_entrenamiento = pd.read_csv(ruta_datos)

    if modelado_estados:
        agrupador = 'Entidad'
    
    if not modelado_estados:
        agrupador = 'region_salud_mental'
   
   
    regiones = sorted(df_entrenamiento[agrupador].unique())
    padecimientos = sorted(df_entrenamiento["Padecimiento"].unique())

    """
    # Entrenamiento Nacional por sexo
    for padecimiento in padecimientos:
        resultados = []
        for sexo in valores_sexo:
            ruta_padecimiento = os.path.join(model_path,normalizar(padecimiento))
            directory_manager.asegurar_ruta(ruta_padecimiento)
                
            df_padecimiento = df_entrenamiento[df_entrenamiento['Padecimiento'] == padecimiento]
            modelo , rmse, parametros = SerieTiempoProphet(df_padecimiento,sexo=sexo).run()
            
            fila = {"padecimiento": padecimiento,"sexo": sexo, "rmse": rmse, **parametros}
            resultados.append(fila)

            ruta_modelo = os.path.join(ruta_padecimiento, f"Prophet_{normalizar(padecimiento)}_{sexo}_{fecha}.pkl")
            
            with open(ruta_modelo,'wb') as f:
                pickle.dump(modelo,f)
                
        ruta_rmse = os.path.join(ruta_padecimiento, f"Prophet_{normalizar(padecimiento)}_{fecha}.csv")
        df_resultados = pd.DataFrame(resultados)
        df_resultados.to_csv(ruta_rmse, index=False, encoding="utf-8")
    
    """
    
    # Entrenamiento por Estado
    for padecimiento in padecimientos:
        ruta_padecimiento = os.path.join(model_path,normalizar(padecimiento))
        resultados = []
        df_padecimiento = df_entrenamiento[df_entrenamiento['Padecimiento'] == padecimiento]
        
        for region in regiones:
            df_region = df_padecimiento[df_padecimiento['Entidad'] == region]

            for sexo in valores_sexo:

                logger.info(f'Entrenando - {region} - {sexo}')

                modelo , rmse, parametros = SerieTiempoProphet(df_padecimiento,sexo=sexo).run()
                fila = {"padecimiento": padecimiento,"Entidad" : region,"sexo": sexo, "rmse": rmse, **parametros}
                resultados.append(fila)

                ruta_modelo = os.path.join(ruta_padecimiento, f"Prophet_{normalizar(padecimiento)}_{normalizar(region)}_{mapeo[sexo]}_{fecha}.pkl")
                
                with open(ruta_modelo,'wb') as f:
                    pickle.dump(modelo,f)
                
        ruta_rmse = os.path.join(ruta_padecimiento, f"Prophet_{normalizar(padecimiento)}_regiones_{fecha}.csv")
        df_resultados = pd.DataFrame(resultados)
        df_resultados.to_csv(ruta_rmse, index=False, encoding="utf-8")

        
        



if __name__ == "__main__":
    main()