# scripts/limpieza_dataset.py
from pathlib import Path

import pandas as pd

from src.configuraciones.config_params import conf, logger
from src.datos.clean_dataset import CleanDataset
from src.datos.EDA import EDAReportBuilder, SeccionNota
from src.utils import directory_manager
from src.utils.reporte_PDF import PDFReportGenerator


def ejecuta_limpieza_raw() -> tuple[bool, pd.DataFrame | None, dict[str, str] | None]:
    raw_file_filter = conf["data"]["raw_data_filter"]

    if not directory_manager.existe_archivo(raw_file_filter):
        logger.error("Archivo de datos filtrado no encontrado: {}", raw_file_filter)
        return False, None, None

    logger.info("Leyendo dataset filtrado: {}", raw_file_filter)
    df = pd.read_csv(raw_file_filter)
    logger.info("Dataset leído | filas: {:,} | columnas: {}", len(df), df.shape[1])

    cleaner = CleanDataset(df)
    clean_df = cleaner.run()

    hubo_cambios = len(df) != len(clean_df) or df.shape[1] != clean_df.shape[1]
    if hubo_cambios:
        logger.info("El dataset fue modificado durante la limpieza.")
    else:
        logger.info("El dataset no presentó cambios.")

    return True, clean_df, cleaner.resumen()


def main():
    resultado, df_clean, metricas_limpieza = ejecuta_limpieza_raw()

    if not resultado or df_clean is None:
        logger.error("Limpieza no completada. Abortando.")
        return

    interim_file = conf["data"]["interim_data_file"]
    configuracion_padecimiento = conf["padecimiento"]

    directory_manager.asegurar_ruta(str(Path(interim_file).parent))
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
            opciones=opciones_reporte,
        ).run()

        if metricas_limpieza:
            datos_reporte.secciones_notas.append(SeccionNota(
                titulo="Resultado de la limpieza",
                parametros=metricas_limpieza,
            ))

        PDFReportGenerator(
            datos_reporte,
            archivo_salida=opciones_reporte["ruta"],
            ancho_figura_cm=16,
        ).build()


if __name__ == "__main__":
    main()
