# src/scripts/limpieza_dataset.py
import pandas as pd
from src.configuraciones.config_params import conf, logger
from src.datos.clean_dataset import CleanDataset
from src.utils import directory_manager
from src.datos.EDA import EDAReportBuilder
from src.utils.reporte_PDF import PDFReportGenerator
from typing import List, Dict, Any
from omegaconf import DictConfig



def _get_section(conf: DictConfig, key: str):
    """
    Obtiene una sección del conf de forma robusta.
    Busca primero en la raíz y luego en conf.limpieza.<key>.
    Devuelve [] si no encuentra.
    """
    # En OmegaConf, .get admite default
    val = conf.get(key, None)
    if val is None:
        limpieza = conf.get("limpieza", None)
        if limpieza is not None:
            val = limpieza.get(key, None)
    return val or []



def generar_notas()  -> str:
    
    partes: List[str] = []

    columnas: List[str] = _get_section(conf, "columnas_eliminar")
    renglones: List[Dict[str, Any]] = _get_section(conf, "renglones_eliminar")
    sustituciones: List[Dict[str, Any]] = _get_section(conf, "valores_sustituir")

    partes.append(
    "Reglas aplicadas durante el proceso de limpieza de datos.<br/><br/>"
    "Estas reglas están definidas en el archivo de configuración limpieza.yaml, "
    "el cual indica:<br/>"
    "&nbsp;&nbsp;• Columnas eliminadas<br/>"
    "&nbsp;&nbsp;• Valores a sustituir para asegurar la consistencia<br/><br/>"
    )
    
    # Resumen con conteos
    partes.append(
        f"Resumen:<br/>"
        f"&nbsp;&nbsp;Columnas eliminadas = {len(columnas)}, <br/>"
        f"&nbsp;&nbsp;Sustituciones = {len(sustituciones)}<br/>"
    )
    partes.append("<br/>")


    # Sección: columnas_eliminar
    if columnas:
        partes.append("Columnas eliminadas:<br/>")
        partes.extend(f"&nbsp;&nbsp;• {str(col)}<br/>" for col in columnas)
        partes.append("<br/>")

    # Sección: renglones_eliminar
    if renglones:
        partes.append("Registros eliminados:<br/>")
        for regla in renglones:
            nombre = str(regla.get("Nombre", "(sin nombre)"))
            valores = regla.get("valor", [])
            valores = valores if isinstance(valores, list) else [valores]
            partes.append(f"&nbsp;&nbsp;• {nombre}:<br/>")
            for v in valores:
                partes.append(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- {str(v)}<br/>")
        partes.append("<br/>")

    if len(columnas) == 0 and len(renglones) == 0 and len(sustituciones) == 0:
        partes.append("No se encontraron reglas de limpieza en la configuración.")

    return "\n".join(partes).rstrip()



def main():

    raw_file = conf["data"]["raw_data_filter"]
    interim_path = conf["paths"]["interim"]
    interim_file = conf["data"]["interim_data_file"]
    archivo_salida = f"{conf['reporte_clean_dataset']['nombre_reporte']}.pdf"
    ruta_reporte = f"{conf['paths']['docs']}/{archivo_salida}"
    opciones_reporte = conf['reporte_clean_dataset']

    directory_manager.asegurar_ruta(interim_path)

    logger.info(f"Cargando datos desde {raw_file}...")
    df = pd.read_csv(raw_file)

    clean_df = CleanDataset(df).run()
    
    clean_df.to_csv(interim_file, index=False)
    logger.info(f"Datos limpios guardados en: {interim_file}")


    datos_reporte = EDAReportBuilder(
        df = clean_df,
        fuente_datos = interim_file,
        opciones = opciones_reporte
    ).run()


    datos_reporte.notas = generar_notas()

    PDFReportGenerator(datos_reporte, archivo_salida=ruta_reporte, ancho_figura_cm=16).build()
    logger.info(f"Reporte generado en: {ruta_reporte}")

if __name__ == "__main__":
    main()