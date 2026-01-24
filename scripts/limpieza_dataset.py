# src/scripts/limpieza_dataset.py
import pandas as pd

from src.configuraciones.config_params import conf, logger
from src.datos.clean_dataset import CleanDataset
from src.datos.EDA import EDAReportBuilder
from src.utils import directory_manager
from src.utils.reporte_PDF import PDFReportGenerator



def ejecuta_limpieza_raw() -> tuple[bool, pd.DataFrame | None]:

    raw_file_filter = conf.get("data",{}).get("raw_data_filter")

    if not directory_manager.existe_archivo(raw_file_filter):
        logger.error(f"No se pudo localizar el archivo filtrado: {raw_file_filter}")
        return False, None
    
    logger.success(f"Archivo filtrado encontrado en la ruta: {raw_file_filter}")
    dataframe_filtrado = pd.read_csv(raw_file_filter)

    clean_df = CleanDataset(dataframe_filtrado).run()

    cambios = not dataframe_filtrado.equals(clean_df)
    
    if cambios:
        logger.info("El dataset fue modificado.")
        return True, clean_df
        
    else:
        logger.info("El dataset no tuvo cambios.")
        return False, None

def main():

    resultado, df_clean = ejecuta_limpieza_raw()

    if resultado:
        interim_file = conf["data"]["interim_data_file"]
        
        if directory_manager.existe_archivo(interim_file):
            logger.info(f"archivo {interim_file} encontrado. El archivo será sobrescrito.")
            df_clean.to_csv(interim_file,index=False)

        else:
            logger.info(f"archivo {interim_file} no localizado. Guardando archivo.")
            df_clean.to_csv(interim_file,index=False)
        
        opciones_reporte = conf.get('reporte_clean_dataset')

        datos_reporte = EDAReportBuilder(
            df = df_clean,
            fuente_datos = interim_file,
            opciones = opciones_reporte
        ).run()

        PDFReportGenerator(datos_reporte, archivo_salida=opciones_reporte.get('ruta'), ancho_figura_cm=16).build()
        logger.info(f"Reporte generado en: {opciones_reporte.get('ruta')}")
        
        


if __name__ == "__main__":
    main()