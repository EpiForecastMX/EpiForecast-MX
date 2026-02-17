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
    return re.sub(r"\s+", "_", formato)


def entrenar(df, padecimiento, sexo, ruta_base, fecha, mapeo, region=None):
    ruta_padecimiento = os.path.join(ruta_base, normalizar(padecimiento))
    directory_manager.asegurar_ruta(ruta_padecimiento)

    modelo, rmse, parametros = SerieTiempoProphet(df, sexo=sexo).run()
    fila = {"padecimiento": padecimiento, "sexo": sexo, "rmse": rmse, **parametros}
    fila["nivel"] = "nacional" if region is None else "regional"
    if region:
        fila["Entidad"] = region

    nombre_extra = f"_{normalizar(region)}" if region else ""
    nombre_modelo = f"Prophet_{normalizar(padecimiento)}{nombre_extra}_{mapeo.get(sexo, sexo)}_{fecha}.pkl"
    ruta_modelo = os.path.join(ruta_padecimiento, nombre_modelo)

    with open(ruta_modelo, 'wb') as f:
        pickle.dump(modelo, f)

    fila["archivo_modelo"] = nombre_modelo

    return fila, ruta_padecimiento


def main():
    fecha = datetime.now().strftime("%Y%m%d")

    modelado_estados = conf['padecimiento']['modelado_estados']
    model_path = conf['paths']['models']
    valores_sexo = conf['valores_sexo']
    mapeo = conf['mapeo_columnas']

    ruta_datos = conf['data']['data_inegi']
    df_entrenamiento = pd.read_csv(ruta_datos)

    agrupador = 'Entidad' if modelado_estados else 'region_salud_mental'
    regiones = sorted(df_entrenamiento[agrupador].unique())
    padecimientos = sorted(df_entrenamiento["Padecimiento"].unique())

    for padecimiento in padecimientos:
        logger.info(f'iniciando entrenamiento para el padecimiento: {padecimiento}')
        df_padecimiento = df_entrenamiento[df_entrenamiento['Padecimiento'] == padecimiento]
        resultados = []

        # Nacional
        for sexo in valores_sexo:
            logger.info(f"Iniciando CV Prophet | Padecimiento: {padecimiento} | Nivel: Nacional | Sexo: {sexo}")
            fila, ruta_padecimiento = entrenar(df_padecimiento, padecimiento, sexo, model_path, fecha, mapeo)
            logger.success(f"Finalizado Prophet | Padecimiento: {padecimiento} | Nivel: Nacional | Sexo: {sexo}")
            resultados.append(fila)

        # Regional
        for region in regiones:
            df_region = df_padecimiento[df_padecimiento[agrupador] == region]
            for sexo in valores_sexo:
                logger.info(f"Iniciando CV Prophet | Padecimiento: {padecimiento} | Nivel: {'Nacional' if region is None else 'Regional'} | Región: {region or 'Todos'} | Sexo: {sexo}")
                fila, _ = entrenar(df_region, padecimiento, sexo, model_path, fecha, mapeo, region=region)
                logger.success(f"Finalizado Prophet | Padecimiento: {padecimiento} | Nivel: {'Nacional' if region is None else 'Regional'} | Región: {region or 'Todos'} | Sexo: {sexo}")
                resultados.append(fila)

        # Guardar todo en un solo CSV
        ruta_rmse = os.path.join(ruta_padecimiento, f"Prophet_{normalizar(padecimiento)}_completo_{fecha}.csv")
        pd.DataFrame(resultados).to_csv(ruta_rmse, index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
