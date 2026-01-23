# src/scripts/padecimiento.py
import pandas as pd
from src.utils import directory_manager
from src.configuraciones.config_params import conf, logger
from src.datos.filtrar_padecimiento import FiltraPadecimiento
from src.datos.EDA import EDAReportBuilder
from src.utils.reporte_PDF import PDFReportGenerator


def filtrar() -> tuple[bool, pd.DataFrame | None]:
    padecimiento = conf.get("padecimiento")
    raw_file = conf.get("data", {}).get("raw_data_file")
    raw_data_filter = conf.get("data", {}).get("raw_data_filter")
    fuerza_filtrado = padecimiento["force"]

    existe_archivo = directory_manager.existe_archivo(raw_file)
    existe_filtrado = directory_manager.existe_archivo(raw_data_filter)

    if not existe_archivo:
        logger.error(f"No se pudo localizar el archivo RAW: {raw_file}")
        return False, None

    logger.success(f"Archivo RAW encontrado en la ruta: {raw_file}")
    logger.info(
        f"Configuración establecida -> Tipo '{padecimiento['tipo']}' | "
        f"Columna: '{padecimiento['columna']}' | Sobreescribe Archivo: {fuerza_filtrado} | Generar reporte: {padecimiento.get("reporte")}"
    )

    if existe_filtrado and not fuerza_filtrado:
        logger.warning(f"Archivo filtrado localizado: {raw_data_filter}")
        return True, pd.read_csv(raw_data_filter)

    dataframe = pd.read_csv(raw_file)
    df_filtrado = FiltraPadecimiento(dataframe, padecimiento).run()

    if df_filtrado is not None:
        logger.success(f"Guardando archivo filtrado en: {raw_data_filter}")
        df_filtrado.to_csv(raw_data_filter, index=False)
        return True, df_filtrado

    return False, None

def main():
    
    resultado, df_filtrado = filtrar()

    if resultado and df_filtrado is not None:

        padecimiento = conf.get("padecimiento")

        if padecimiento.get("reporte"):

            opciones_reporte = conf.get('reporte_EDA')
            ruta_df = conf.get("data", {}).get("raw_data_filter")

            directory_manager.asegurar_ruta(opciones_reporte.get('carpeta'))

            datos_reporte = EDAReportBuilder(
                df = df_filtrado,
                fuente_datos = ruta_df,
                opciones = opciones_reporte
            ).run()

            PDFReportGenerator(datos_reporte, archivo_salida=opciones_reporte.get('ruta'), ancho_figura_cm=16).build()
            logger.debug(f"Reporte generado en: {opciones_reporte.get('ruta')}")

if __name__ == "__main__":
    main()
    
