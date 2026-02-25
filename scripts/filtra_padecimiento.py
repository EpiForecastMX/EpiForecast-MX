# scripts/filtra_padecimiento.py
import sys

import pandas as pd

from epiforecast.data.preprocessing.filter import FiltraPadecimiento
from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger
from epiforecast.visualization.eda_plots import EDAReportBuilder
from epiforecast.visualization.reporters import PDFReportGenerator


def filtrar() -> tuple[bool, pd.DataFrame | None]:
    padecimiento = conf["padecimiento"]
    raw_file = conf["data"]["raw_data_file"]
    raw_data_filter = conf["data"]["raw_data_filter"]
    fuerza_filtrado = padecimiento["force"]

    if not directory_manager.existe_archivo(raw_file):
        logger.error("Archivo de datos crudos no encontrado, abortando | archivo={}", raw_file)
        return False, None

    logger.info(
        "Parámetros de filtrado | tipo='{}' | columna='{}' | forzar={} | reporte={}",
        padecimiento["tipo"],
        padecimiento["columna"],
        fuerza_filtrado,
        padecimiento["reporte"],
    )

    existe_filtrado = directory_manager.existe_archivo(raw_data_filter)

    if existe_filtrado and not fuerza_filtrado:
        logger.info("Archivo filtrado ya existe, omitiendo filtrado | archivo={}", raw_data_filter)
        return True, pd.read_csv(raw_data_filter)

    dataframe = pd.read_csv(raw_file)
    logger.info(
        "Dataset cargado | filas={:,} | columnas={}", len(dataframe), len(dataframe.columns)
    )

    df_filtrado = FiltraPadecimiento(dataframe, padecimiento).run()

    if df_filtrado is not None:
        df_filtrado.to_csv(raw_data_filter, index=False)
        directory_manager.advertir_sobrescritura(raw_data_filter)
        logger.success("Archivo filtrado guardado | archivo={}", raw_data_filter)
        return True, df_filtrado

    return False, None


def main():
    resultado, df_filtrado = filtrar()

    if not resultado or df_filtrado is None:
        logger.error("Filtrado no completado. Abortando.")
        sys.exit(1)

    padecimiento = conf["padecimiento"]

    if padecimiento["reporte"]:
        opciones_reporte = conf["reporte_filtrado"]

        directory_manager.asegurar_ruta(opciones_reporte["carpeta"])

        datos_reporte = EDAReportBuilder(
            df=df_filtrado,
            fuente_datos=conf["data"]["raw_data_filter"],
            opciones=opciones_reporte,
        ).run()

        PDFReportGenerator(
            datos_reporte, archivo_salida=opciones_reporte["ruta"], ancho_figura_cm=16
        ).build()


if __name__ == "__main__":
    main()
