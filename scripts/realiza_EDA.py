import pandas as pd
from src.configuraciones.config_params import conf, logger
from src.datos.EDA import EDAReportBuilder
from src.utils.ReportePDF import PDFReportGenerator


def main():
    raw_file = conf["data"]["raw_data_file"]
    archivo_salida = f"{conf['reporte_EDA']['nombre_reporte']}.pdf"
    ruta_reporte = f"{conf['paths']['docs']}/{archivo_salida}"

    logger.info(f"Cargando datos desde {raw_file}...")
    df = pd.read_csv(raw_file)

    logger.info(f"Generando reporte EDA en {ruta_reporte}...")
    datos_reporte = EDAReportBuilder(
        df = df,
        titulo = conf["reporte_EDA"]["titulo_reporte"],
        subtitulo = conf["reporte_EDA"]["filtro_padecimiento"],
        fuente_datos = raw_file,
        numero_cols_numericas = conf["reporte_EDA"]["max_cols_numericas"],
        numero_cols_categoricas = conf["reporte_EDA"]["max_categorias_tabla"],
    ).run()

    PDFReportGenerator(datos_reporte, archivo_salida=ruta_reporte, ancho_figura_cm=16).build()
    print(f"Reporte generado en: {ruta_reporte}")


if __name__ == "__main__":
    main()