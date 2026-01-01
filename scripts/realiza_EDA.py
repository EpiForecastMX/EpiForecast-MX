# src/scripts/realiza_EDA.py
import pandas as pd
from src.configuraciones.config_params import conf, logger
from src.datos.EDA import EDAReportBuilder
from src.utils.reporte_PDF import PDFReportGenerator
from src.utils import directory_manager


def main():
    raw_file = conf["data"]["raw_data_file"]
    archivo_salida = f"{conf['reporte_EDA']['nombre_reporte']}.pdf"
    ruta_reporte = f"{conf['paths']['docs']}/{archivo_salida}"
    opciones_reporte = conf['reporte_EDA']

    logger.info(f"Cargando datos desde {raw_file}...")
    df = pd.read_csv(raw_file)

    directory_manager.asegurar_ruta(ruta_reporte)

    datos_reporte = EDAReportBuilder(
        df = df,
        fuente_datos = raw_file,
        opciones = opciones_reporte
    ).run()

    PDFReportGenerator(datos_reporte, archivo_salida=ruta_reporte, ancho_figura_cm=16).build()
    logger.info(f"Reporte generado en: {ruta_reporte}")


if __name__ == "__main__":
    main()