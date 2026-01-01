# src/utils/reporte_PDF.py
import os
import pandas as pd
from loguru import logger
from typing import List, Dict, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, LongTable, TableStyle, PageBreak, KeepInFrame
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from src.datos.EDA import ReportData


# ---------- Helpers ---------- #

def crear_tabla(data: List[List[Any]],
                colWidths: Optional[List[float]] = None,
                hAlign: str = "CENTER") -> LongTable:
    table = LongTable(data, colWidths=colWidths, hAlign=hAlign,splitByRow=0)
    table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return table


def tabla_desde_dataframe(df: pd.DataFrame) -> LongTable:
    """Convierte un DataFrame en tabla PDF."""
    if df is None or df.empty:
        return crear_tabla([["Sin datos"], ["—"]], colWidths=[16 * cm])

    header = [df.index.name or "columna"] + df.columns.tolist()
    rows = [[str(idx)] + [str(v) for v in row] for idx, row in df.iterrows()]
    data = [header] + rows

    if len(header) <= 4:
        col_widths = [6 * cm] + [((16 * cm) - 6 * cm) / (len(header) - 1)] * (len(header) - 1)
    else:
        col_widths = None

    return crear_tabla(data, colWidths=col_widths)


def tabla_kv(dic: Dict[str, str]) -> LongTable:
    """Convierte un dict clave-valor en tabla PDF."""
    data = [["Campo", "Valor"]] + [[str(k), str(v)] for k, v in dic.items()] if dic else [["Campo", "Valor"], ["—", "—"]]
    return crear_tabla(data, colWidths=[7 * cm, 9 * cm])


def cabecera_pie(canv: canvas.Canvas, doc: SimpleDocTemplate):
    """Encabezado y pie de página comunes."""
    width, height = A4
    margen = 0.5 * cm
    canv.saveState()

    canv.setStrokeColor(colors.HexColor("#A3BFD9"))
    canv.setLineWidth(1)
    canv.rect(margen, margen, width - 2*margen, height - 2*margen)

    canv.setFont("Helvetica", 9)
    canv.setFillColor(colors.grey)
    canv.drawString(2 * cm, height - 1 * cm, "Reporte EDA")

    canv.setFillColor(colors.black)
    canv.drawRightString(width - 2 * cm, 1 * cm, f"Página {canv.getPageNumber()}")
    canv.restoreState()


# ---------- Clase principal ---------- #

class PDFReportGenerator:

    def __init__(self, datos_reporte: ReportData,
                 archivo_salida,
                 ancho_figura_cm: float = 16.0):
        self.datos = datos_reporte
        self.archivo_salida = archivo_salida
        self.ancho_figura_cm = ancho_figura_cm
        self.styles = self._crear_estilos()

    def _crear_estilos(self):
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Titulo', parent=styles['Title'],
                                  fontName='Helvetica-Bold', fontSize=18, leading=22,
                                  alignment=1, spaceAfter=12))
        styles.add(ParagraphStyle(name='Subtitulo', parent=styles['Normal'],
                                  fontName='Helvetica', fontSize=12, textColor=colors.grey,
                                  alignment=1, spaceAfter=12))
        styles.add(ParagraphStyle(name='Seccion', parent=styles['Heading2'],
                                  fontName='Helvetica-Bold', fontSize=14,
                                  spaceBefore=12, spaceAfter=6, alignment=1))
        styles.add(ParagraphStyle(name='NormalJust', parent=styles['Normal'],
                                  fontName='Helvetica', fontSize=10, leading=14))
        return styles

    def _agregar_tabla_si_existe(self, story: List[Any], titulo: str, df: Optional[pd.DataFrame]):
        
        story.append(Paragraph(titulo, self.styles['Seccion']))
        story.append(tabla_desde_dataframe(df) if isinstance(df, pd.DataFrame) and not df.empty
                     else Paragraph("No se encontraron datos.", self.styles['NormalJust']))
        story.append(Spacer(1, 12))

    def _agregar_portada(self, story: List[Any]):

        story.append(Paragraph(self.datos.titulo, self.styles['Titulo']))
        if self.datos.subtitulo:
            story.append(Paragraph(self.datos.subtitulo, self.styles['Subtitulo']))
        story.append(Spacer(1, 24))
        story.append(tabla_kv(self.datos.resumen_general))
        story.append(PageBreak())

    def _agregar_notas(self, story: List[Any]):
        if self.datos.notas:
            #notas_html = self.datos.notas.replace("\n", "<br/>")
            story.append(Paragraph("Notas", self.styles['Seccion']))
            story.append(Paragraph(self.datos.notas or "—", self.styles['NormalJust']))
            story.append(PageBreak())

    def _agregar_tablas_campos(self, story: List[Any]):

        self._agregar_tabla_si_existe(story, "Características de los campos", getattr(self.datos, "resumen_datos", None))
        self._agregar_tabla_si_existe(story, "Estadísticas descriptivas de variables numéricas", self.datos.estadisticas_numericas)
        self._agregar_tabla_si_existe(story, "Estadísticas descriptivas de variables categóricas", getattr(self.datos, "estadisticas_categoricas", None))
        self._agregar_tabla_si_existe(story, "Campos con valores nulos", getattr(self.datos, "resumen_datos_nulos", None))
        story.append(PageBreak())

        story.append(Paragraph("Distribuciones de variables categóricas", self.styles['Seccion']))
        if self.datos.tablas_categoricas:
            for df in self.datos.tablas_categoricas.values():
                story.append(tabla_desde_dataframe(df))
                story.append(Spacer(1, 8))
        else:
            story.append(Paragraph("No se identificaron columnas categóricas.", self.styles['NormalJust']))
        story.append(PageBreak())

    def _agregar_figuras(self, story: List[Any]):
        story.append(Paragraph("Histogramas generados", self.styles['Seccion']))
        max_w, max_h = min(self.ancho_figura_cm * cm, A4[0] - 4 * cm), 11 * cm
        contador = 0

        for ruta in self.datos.figuras:
            if os.path.exists(ruta):
                img = Image(ruta)
                img._restrictSize(max_w, max_h)
                story.append(KeepInFrame(max_w, max_h, [img], mode='shrink'))
                story.append(Spacer(1, 8))
                contador += 1
                if contador % 2 == 0:
                    story.append(PageBreak())

        if contador % 2 != 0:
            story.append(PageBreak())

    def build(self):
        doc = SimpleDocTemplate(self.archivo_salida, pagesize=A4,
                                leftMargin=2 * cm, rightMargin=2 * cm,
                                topMargin=2.2 * cm, bottomMargin=2.0 * cm)
        logger.info(f"Generando reporte PDF en: {self.archivo_salida}")
        
        page_w_cm = round(doc.pagesize[0] / cm, 2)
        page_h_cm = round(doc.pagesize[1] / cm, 2)

        logger.debug(f"Datos del reporte: tamaño página: {page_w_cm} x {page_h_cm} cm | Márgenes -> "
            f"izq: {doc.leftMargin/cm:.2f} cm, "
            f"der: {doc.rightMargin/cm:.2f} cm, "
            f"sup: {doc.topMargin/cm:.2f} cm, "
            f"inf: {doc.bottomMargin/cm:.2f} cm"
        )

        story: List[Any] = []
        logger.debug("Agregando portada al reporte PDF.")
        self._agregar_portada(story)
        logger.debug("Agregando tablas de campos al reporte PDF.")
        self._agregar_tablas_campos(story)
        logger.debug("Agregando figuras al reporte PDF.")
        self._agregar_figuras(story)
        self._agregar_notas(story)

        doc.build(story, onFirstPage=cabecera_pie, onLaterPages=cabecera_pie)