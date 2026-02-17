# scripts/limpieza_dataset.py
import pandas as pd

from src.configuraciones.config_params import conf, logger
from src.datos.clean_dataset import CleanDataset
from src.datos.EDA import EDAReportBuilder
from src.utils import directory_manager
from src.utils.reporte_PDF import PDFReportGenerator


def ejecuta_limpieza_raw() -> tuple[bool, pd.DataFrame | None]:
    raw_file_filter = conf["data"]["raw_data_filter"]

    if not directory_manager.existe_archivo(raw_file_filter):
        return False, None

    dataframe_filtrado = pd.read_csv(raw_file_filter)
    clean_df = CleanDataset(dataframe_filtrado).run()

    if not dataframe_filtrado.equals(clean_df):
        logger.info("El dataset fue modificado durante la limpieza.")
    else:
        logger.info("El dataset no presentó cambios.")

    return True, clean_df


def main():
    resultado, df_clean = ejecuta_limpieza_raw()

    if not resultado or df_clean is None:
        logger.error("Limpieza no completada. Abortando.")
        return

    interim_file = conf["data"]["interim_data_file"]
    configuracion_padecimiento = conf["padecimiento"]

    ya_existe = directory_manager.existe_archivo(interim_file)
    df_clean.to_csv(interim_file, index=False)

    if ya_existe:
        logger.warning("Archivo existente sobrescrito: {}", interim_file)
    else:
        logger.success("Archivo guardado: {}", interim_file)

    if configuracion_padecimiento["reporte_clean"]:
        opciones_reporte = conf["reporte_clean_dataset"]

        datos_reporte = EDAReportBuilder(
            df=df_clean,
            fuente_datos=interim_file,
            opciones=opciones_reporte
        ).run()

        PDFReportGenerator(datos_reporte, archivo_salida=opciones_reporte["ruta"], ancho_figura_cm=16).build()
        logger.success("Reporte PDF generado: {}", opciones_reporte["ruta"])


if __name__ == "__main__":
    main()
