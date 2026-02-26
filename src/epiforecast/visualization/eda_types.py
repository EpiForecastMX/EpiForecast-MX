"""EDA report data structures: SeccionNota and ReportData."""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class SeccionNota:
    """Sección estructurada del bloque de notas del reporte PDF.

    Cada proceso que construya un ReportData puede agregar una o varias
    SeccionNota con la información que considere relevante:

    Ejemplo::

        nota = SeccionNota(
            titulo="Proceso de limpieza",
            texto="Se eliminaron filas con nulos en columnas críticas.",
            parametros={"Filas antes": "10,000", "Filas después": "9,500"},
        )
        report_data.secciones_notas.append(nota)
    """

    titulo: str
    texto: str | None = None  # párrafo descriptivo libre
    parametros: dict[str, str] | None = None  # se renderiza como tabla clave-valor
    tabla: pd.DataFrame | None = None  # se renderiza como tabla de datos


@dataclass
class ReportData:
    titulo: str
    subtitulo: str | None
    fuente_datos: str | None
    resumen_general: dict[str, str]
    resumen_datos: pd.DataFrame | None
    resumen_datos_nulos: pd.DataFrame | None
    estadisticas_numericas: pd.DataFrame | None
    estadisticas_categoricas: pd.DataFrame | None
    tablas_categoricas: dict[str, pd.DataFrame]
    figuras: list[str] = field(default_factory=list)
    notas: str | None = None  # texto libre (compatibilidad)
    secciones_notas: list[SeccionNota] = field(default_factory=list)  # secciones estructuradas
