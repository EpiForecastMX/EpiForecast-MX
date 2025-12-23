
from src.configuraciones.config_params import conf, logger
from src.datos.EDA import EDAReportBuilder
from src.utils.ReportePDF import PDFReportGenerator

import pandas as pd


def main():

    raw_file = conf["data"]["raw_data_file"]
    archivo_salida = conf["reporte_EDA"]["nombre_reporte"] +"." +conf["reporte_EDA"]["formato"]
    ruta_reporte = conf["paths"]["docs"] + "/" + archivo_salida

    logger.info(f"Cargando datos desde {raw_file}...")
    logger.info(f"Generando reporte EDA en {ruta_reporte}...")


    df = pd.read_csv(raw_file)
        

    # Ejecutar EDA
    eda_builder = EDAReportBuilder(
        df=df,
        titulo="Análisis Exploratorio de Datos",
        subtitulo="Subtitulo del reporte EDA",
        fuente_datos=raw_file,
        carpeta_salida="output",
        max_cols_numericas=6,
        max_categorias_tabla=8
    )
    datos_reporte = eda_builder.run()

    

    
    # Generar PDF

    generador = PDFReportGenerator(datos_reporte, archivo_salida=ruta_reporte, ancho_figura_cm=16)
    generador.build()
    print(f"Reporte generado en: {ruta_reporte}")

    
if __name__ == "__main__":
    main()

