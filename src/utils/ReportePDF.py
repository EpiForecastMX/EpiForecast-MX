import os
import pandas as pd
from typing import List, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepInFrame
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from src.datos.EDA import ReportData


# ---------- Helpers ---------- #

def _crear_tabla(data: List[List[Any]], colWidths: Optional[List[float]] = None, hAlign: str = "CENTER") -> Table:
    """Crea una tabla con estilo estándar."""
    table = Table(data, colWidths=colWidths, hAlign=hAlign)
    style = TableStyle([
        # Cabecera
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Cuerpo
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),  # números a la derecha
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])
    table.setStyle(style)
    return table


def tabla_desde_dataframe(df: pd.DataFrame) -> Table:
    """Convierte un DataFrame en tabla PDF."""
    if df is None or df.empty:
        return _crear_tabla([["Sin datos"], ["—"]], colWidths=[16 * cm])

    # 👇 Si el índice tiene nombre, úsalo; si no, pon 'columna'
    idx_name = df.index.name if df.index.name else "columna"

    header = [idx_name] + df.columns.tolist()
    rows = [[str(idx)] + [str(v) for v in row] for idx, row in df.iterrows()]
    data = [header] + rows

    # Ajuste automático de ancho: primeras columnas un poco más anchas
    col_count = len(header)
    if col_count <= 4:
        col_widths = [6 * cm] + [((16 * cm) - 6 * cm) / (col_count - 1)] * (col_count - 1)
    else:
        col_widths = None  # deja que ReportLab calcule si son muchas columnas

    return _crear_tabla(data, colWidths=col_widths, hAlign="CENTER")



def tabla_kv(dic: Dict[str, str]) -> Table:
    """Convierte un dict clave-valor en tabla PDF."""
    if not dic:
        return _crear_tabla([["Campo", "Valor"], ["—", "—"]], colWidths=[7 * cm, 9 * cm])
    data = [["Campo", "Valor"]] + [[str(k), str(v)] for k, v in dic.items()]
    return _crear_tabla(data, colWidths=[7 * cm, 9 * cm], hAlign="CENTER")


def cabecera_pie(canv: canvas.Canvas, doc: SimpleDocTemplate):
    """Encabezado y pie de página comunes."""
    width, height = A4
    canv.saveState()
    
    # Margen
    margen = 0.5 * cm 

    canv.setStrokeColor(colors.HexColor("#A3BFD9"))
    canv.setLineWidth(1)
    canv.rect(margen, margen, width - 2*margen, height - 2*margen)
    

    # Encabezado
    canv.setFont("Helvetica", 9)
    canv.setFillColor(colors.grey)
    canv.drawString(2 * cm, height - 1 * cm, "Reporte EDA")
    # Pie con página

    canv.setFillColor(colors.black)
    page_num = canv.getPageNumber()
    canv.drawRightString(width - 2 * cm, 1 * cm, f"Página {page_num}")
    canv.restoreState()


# ---------- Clase principal ---------- #

class PDFReportGenerator:

    def __init__(self, datos_reporte: ReportData,
                 archivo_salida: str = "output/reportes/reporte_eda.pdf",
                 ancho_figura_cm: float = 16.0):
        self.datos = datos_reporte
        self.archivo_salida = archivo_salida
        self.ancho_figura_cm = ancho_figura_cm
        self.styles = self._crear_estilos()

    def _crear_estilos(self):
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='Titulo',
            parent=styles['Title'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            alignment=1,
            spaceAfter=12
        ))
        styles.add(ParagraphStyle(
            name='Subtitulo',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=12,
            textColor=colors.grey,
            alignment=1,
            spaceAfter=12
        ))
        styles.add(ParagraphStyle(
            name='Seccion',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            spaceBefore=12,
            spaceAfter=6,
            alignment=1  # centrado
        ))
        styles.add(ParagraphStyle(
            name='NormalJust',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14
        ))
        return styles

    def _agregar_portada_con_estadisticas(self, story: List[Any]):

        story.append(Paragraph(self.datos.titulo, self.styles['Titulo']))
        if self.datos.subtitulo:
            story.append(Paragraph(self.datos.subtitulo, self.styles['Subtitulo']))

        # Información general
        story.append(Paragraph("Resumen general del conjunto de datos", self.styles['Seccion']))
        #story.append(Paragraph("Resume los metadatos principales: fecha del análisis, fuente original, número de registros y porcentaje global de valores nulos.",
        #    self.styles['NormalJust']
        #))
        story.append(Spacer(1, 12))
        story.append(tabla_kv(self.datos.resumen_general))
        story.append(Spacer(1, 12))

        # Estadísticas numéricas
        story.append(Paragraph("Estadísticas descriptivas de variables numéricas", self.styles['Seccion']))
        story.append(Spacer(1, 12))
        #story.append(Paragraph("Presenta medidas estadísticas básicas (conteo, media, desviación estándar, mínimos, máximos y cuartiles) para las variables numéricas.",
        #    self.styles['NormalJust']
        # ))
        est_num = self.datos.estadisticas_numericas
        if est_num is not None and not est_num.empty:
            story.append(tabla_desde_dataframe(est_num))
        else:
            story.append(Paragraph("No se encontraron columnas numéricas para describir.", self.styles['NormalJust']))
        
        story.append(Spacer(1, 12))
        story.append(Paragraph("Estadísticas descriptivas de variables categóricas", self.styles['Seccion']))
        story.append(Spacer(1, 12))
        #story.append(Paragraph("Muestra el número de registros, cantidad de valores únicos, moda y su frecuencia relativa para las variables categóricas.",
        #    self.styles['NormalJust']
        #))
        est_cat = getattr(self.datos, "estadisticas_categoricas", None)
        if isinstance(est_cat, pd.DataFrame) and not est_cat.empty:
            story.append(tabla_desde_dataframe(est_cat))
        else:
            story.append(Paragraph("No se encontraron columnas categóricas para describir.", self.styles['NormalJust']))

        # Fin de portada
        story.append(PageBreak())

    def _agregar_tablas_campos(self, story: List[Any]):

        resumen_datos = getattr(self.datos, "resumen_datos", None)
        resumen_datos_nulos = getattr(self.datos, "resumen_datos_nulos", None)

        if isinstance(resumen_datos, pd.DataFrame):
            story.append(Paragraph("Características de los campos", self.styles['Seccion']))
            #story.append(Paragraph("Detalla el tipo de dato de cada columna y la cantidad de valores únicos, útil para identificar variables con baja variabilidad.",
            #self.styles['NormalJust']
            #))
            story.append(Spacer(1, 12))
            story.append(tabla_desde_dataframe(resumen_datos))
            story.append(Spacer(1, 12))

        if isinstance(resumen_datos_nulos, pd.DataFrame):
            story.append(Paragraph("Campos con valores nulos", self.styles['Seccion']))
            #story.append(Paragraph("Lista las columnas que contienen valores faltantes y el número de nulos en cada una.",
            #self.styles['NormalJust']
            #))
            story.append(Spacer(1, 12))
            story.append(tabla_desde_dataframe(resumen_datos_nulos))
            story.append(Spacer(1, 12))

        story.append(PageBreak())


        story.append(Paragraph("Distribuciones de variables categóricas", self.styles['Seccion']))
        #story.append(Paragraph("Expone las categorías más frecuentes en cada variable cualitativa, permitiendo detectar patrones y concentraciones.",
        #    self.styles['NormalJust']
        #    ))
        if self.datos.tablas_categoricas:
            for col, df in self.datos.tablas_categoricas.items():
                #story.append(Paragraph(f"{col}", self.styles['NormalJust']))
                story.append(tabla_desde_dataframe(df))
                story.append(Spacer(1, 8))
        else:
            story.append(Paragraph("No se identificaron columnas categóricas.", self.styles['NormalJust']))
        story.append(PageBreak())

    def _agregar_figuras(self, story: List[Any]):
        story.append(Paragraph("histogramas generados", self.styles['Seccion']))
        page_w, _ = A4
        available_w = page_w - 4 * cm
        max_w = min(self.ancho_figura_cm * cm, available_w)
        max_h = 11 * cm

        figuras_por_pagina = 2
        contador = 0

        for ruta in self.datos.figuras:
            if os.path.exists(ruta):
                img = Image(ruta)
                img._restrictSize(max_w, max_h)
                story.append(KeepInFrame(max_w, max_h, [img], mode='shrink'))
                story.append(Spacer(1, 6))
                #story.append(Paragraph(os.path.basename(ruta), self.styles['NormalJust']))
                story.append(Spacer(1, 8))

                contador += 1
 
                if contador % figuras_por_pagina == 0:
                    story.append(PageBreak())

        # Si al final no se cerró la página y hay figuras, forzar salto
        if contador % figuras_por_pagina != 0:
            story.append(PageBreak())


    def _agregar_notas(self, story: List[Any]):
        """Notas finales."""
        story.append(Paragraph("Notas", self.styles['Seccion']))
        story.append(Paragraph(self.datos.notas or "—", self.styles['NormalJust']))

    def build(self):
        doc = SimpleDocTemplate(
            self.archivo_salida,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2.2 * cm,
            bottomMargin=2.0 * cm
        )
        story: List[Any] = []

        # Portada + estadísticas (misma página)
        self._agregar_portada_con_estadisticas(story)
        # Página siguiente: tablas de campos
        self._agregar_tablas_campos(story)
        # Figuras
        self._agregar_figuras(story)
        # Notas
        #self._agregar_notas(story)

        doc.build(story, onFirstPage=cabecera_pie, onLaterPages=cabecera_pie)
