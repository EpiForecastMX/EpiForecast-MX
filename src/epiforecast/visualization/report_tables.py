"""PDF table helpers and page decorators for IMSS-branded reports."""

from collections.abc import Callable
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import LongTable, SimpleDocTemplate, TableStyle


def crear_tabla(
    data: list[list[Any]],
    col_widths: list[float] | None = None,
    h_align: str = "CENTER",
) -> LongTable:
    """Crea una LongTable con estilo institucional IMSS."""
    # splitByRow=0: evita que una fila se parta entre dos páginas
    table = LongTable(data, colWidths=col_widths, hAlign=h_align, splitByRow=0)
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def tabla_desde_dataframe(df: pd.DataFrame | None) -> LongTable:
    """Convierte un DataFrame en tabla PDF."""
    if df is None or df.empty:
        return crear_tabla([["Sin datos"], ["—"]], col_widths=[16 * cm])

    header = [df.index.name or "columna"] + df.columns.tolist()
    rows = [[str(idx)] + [str(v) for v in row] for idx, row in df.iterrows()]

    if len(header) <= 4:
        ancho_resto = (16 * cm - 6 * cm) / (len(header) - 1)
        col_widths: list[float] | None = [6 * cm] + [ancho_resto] * (len(header) - 1)
    else:
        col_widths = None

    return crear_tabla([header] + rows, col_widths=col_widths)


def tabla_kv(dic: dict[str, str] | None) -> LongTable:
    """Convierte un diccionario clave-valor en tabla PDF de dos columnas."""
    if not dic:
        data = [["Campo", "Valor"], ["—", "—"]]
    else:
        data = [["Campo", "Valor"]] + [[str(k), str(v)] for k, v in dic.items()]
    return crear_tabla(data, col_widths=[7 * cm, 9 * cm])


def _hacer_cabecera_pie(
    titulo_reporte: str,
) -> Callable[[canvas.Canvas, SimpleDocTemplate], None]:
    """Retorna el callback onPage con el título del reporte inyectado como closure."""

    def cabecera_pie(canv: canvas.Canvas, doc: SimpleDocTemplate) -> None:
        """Callback onPage: dibuja marco IMSS, encabezado y número de página."""

        width, height = A4
        margen = 0.5 * cm
        canv.saveState()

        canv.setStrokeColor(colors.HexColor("#A3BFD9"))
        canv.setLineWidth(1)
        canv.rect(margen, margen, width - 2 * margen, height - 2 * margen)

        canv.setFont("Helvetica", 9)
        canv.setFillColor(colors.grey)
        canv.drawString(2 * cm, height - 1 * cm, titulo_reporte)

        canv.setFillColor(colors.black)
        canv.drawRightString(width - 2 * cm, 1 * cm, f"Página {canv.getPageNumber()}")
        canv.restoreState()

    return cabecera_pie
