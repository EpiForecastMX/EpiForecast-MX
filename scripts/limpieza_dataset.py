# src/scripts/limpieza_dataset.py

import pandas as pd
from src.configuraciones.config_params import conf, logger
from src.datos.clean_dataset import CleanDataset
from src.utils import DirectoryManager
from src.datos.EDA import EDAReportBuilder
from src.utils.ReportePDF import PDFReportGenerator

def main():

    raw_file = conf["data"]["raw_data_file"]
    interim_file = conf["data"]["interim_data_file"]

    archivo_salida = f"{conf['reporte_clean_dataset']['nombre_reporte']}.pdf"
    ruta_reporte = f"{conf['paths']['docs']}/{archivo_salida}"

    DirectoryManager.asegurar_ruta(interim_file)

    logger.info(f"Cargando datos desde {raw_file}...")
    df = pd.read_csv(raw_file)

    clean_df = CleanDataset(df).run()
    
    clean_df.to_csv(interim_file, index=False)
    logger.info(f"Datos limpios guardados en: {interim_file}")

    datos_reporte = EDAReportBuilder(
        df = clean_df,
        titulo = conf["reporte_clean_dataset"]["titulo_reporte"],
        subtitulo = conf["reporte_clean_dataset"]["subtitulo_reporte"],
        fuente_datos = interim_file,
        numero_top_columnas = conf["reporte_clean_dataset"]["max_cols"],
    ).run()

    PDFReportGenerator(datos_reporte, archivo_salida=ruta_reporte, ancho_figura_cm=16).build()
    logger.info(f"Reporte generado en: {ruta_reporte}")

if __name__ == "__main__":
    main()