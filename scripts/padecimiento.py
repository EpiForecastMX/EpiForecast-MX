# scripts/padecimiento.py
import pandas as pd

from src.configuraciones.config_params import conf, logger
from src.datos.EDA import EDAReportBuilder
from src.datos.filtrar_padecimiento import FiltraPadecimiento
from src.utils import directory_manager
from src.utils.reporte_PDF import PDFReportGenerator


def filtrar() -> tuple[bool, pd.DataFrame | None]:
    padecimiento = conf["padecimiento"]
    raw_file = conf["data"]["raw_data_file"]
    raw_data_filter = conf["data"]["raw_data_filter"]
    fuerza_filtrado = padecimiento["force"]

    existe_archivo = directory_manager.existe_archivo(raw_file)
    existe_filtrado = directory_manager.existe_archivo(raw_data_filter)

    if not existe_archivo:
        return False, None

    logger.info(
        "Parámetros de filtrado | tipo='{}' | columna='{}' | forzar={} | reporte={}",
        padecimiento["tipo"],
        padecimiento["columna"],
        fuerza_filtrado,
        padecimiento["reporte"],
    )

    if existe_filtrado and not fuerza_filtrado:
        logger.info("Archivo filtrado ya existe, omitiendo filtrado: {}", raw_data_filter)
        return True, pd.read_csv(raw_data_filter)

    dataframe = pd.read_csv(raw_file)
    df_filtrado = FiltraPadecimiento(dataframe, padecimiento).run()

    if df_filtrado is not None:
        df_filtrado.to_csv(raw_data_filter, index=False)
        logger.success("Archivo filtrado guardado: {}", raw_data_filter)
        return True, df_filtrado

    return False, None


def main():
    resultado, df_filtrado = filtrar()

    if not resultado or df_filtrado is None:
        logger.error("Filtrado no completado. Abortando.")
        return

    padecimiento = conf["padecimiento"]

    if padecimiento["reporte"]:

        opciones_reporte = conf["reporte_filtrado"]
        ruta_df = conf["data"]["raw_data_filter"]

        directory_manager.asegurar_ruta(opciones_reporte["carpeta"])

        datos_reporte = EDAReportBuilder(
            df=df_filtrado,
            fuente_datos=ruta_df,
            opciones=opciones_reporte
        ).run()

        PDFReportGenerator(datos_reporte, archivo_salida=opciones_reporte["ruta"], ancho_figura_cm=16).build()
        logger.success("Reporte PDF generado: {}", opciones_reporte["ruta"])


if __name__ == "__main__":
    main()
