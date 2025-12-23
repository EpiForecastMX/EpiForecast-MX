
# report/report_pdf.py
import os
from typing import List, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepInFrame
)

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

# Importa el dataclass desde el módulo de EDA
from src.datos.EDA import ReportData


def _tabla_desde_dataframe(df) -> Table:

    data = [ [str(c) for c in ["columna"] + df.columns.tolist()] ]  # Encabezado con 'columna'
    for idx, row in df.iterrows():
        data.append([str(idx)] + [str(v) for v in row.tolist()])

    table = Table(data, hAlign='LEFT')
    style = TableStyle([
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ])
    table.setStyle(style)
    return table


def _tabla_kv(dic: Dict[str, str]) -> Table:
    """
    Convierte un dict clave-valor en una tabla con dos columnas.
    """
    data = [['Campo', 'Valor']] + [[str(k), str(v)] for k, v in dic.items()]
    table = Table(data, colWidths=[7*cm, 9*cm], hAlign='LEFT')
    style = TableStyle([
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ])
    table.setStyle(style)
    return table


def _cabecera_pie(canvas: canvas.Canvas, doc: SimpleDocTemplate):
    """
    Dibuja encabezado y pie de página comunes.
    """
    width, height = A4
    canvas.saveState()
    # Encabezado
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2*cm, height - 1*cm, "Reporte EDA")
    # Pie con numeración
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica", 9)
    page_num = canvas.getPageNumber()
    canvas.drawRightString(width - 2*cm, 1*cm, f"Página {page_num}")
    canvas.restoreState()


class PDFReportGenerator:
    """
    Recibe un ReportData y construye un PDF bien formateado.
    """
    def __init__(
        self,
        datos_reporte: ReportData,
        archivo_salida: str = "output/reportes/reporte_eda.pdf",
        ancho_figura_cm: float = 16.0
    ):
        self.datos = datos_reporte
        self.archivo_salida = archivo_salida
        os.makedirs(os.path.dirname(self.archivo_salida), exist_ok=True)
        self.ancho_figura_cm = ancho_figura_cm

        # Estilos
        self.styles = getSampleStyleSheet()
        self.styles.add(ParagraphStyle(
            name='Titulo',
            parent=self.styles['Title'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            alignment=1,  # centrado
            spaceAfter=12
        ))
        self.styles.add(ParagraphStyle(
            name='Subtitulo',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=12,
            textColor=colors.grey,
            alignment=1,
            spaceAfter=12
        ))
        self.styles.add(ParagraphStyle(
            name='Seccion',
            parent=self.styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            spaceBefore=12,
            spaceAfter=6
        ))
        self.styles.add(ParagraphStyle(
            name='NormalJust',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14
        ))

    def build(self):
        doc = SimpleDocTemplate(
            self.archivo_salida,
            pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2.2*cm, bottomMargin=2.0*cm
        )
        story: List[Any] = []

        # Portada
        story.append(Paragraph(self.datos.titulo, self.styles['Titulo']))
        if self.datos.subtitulo:
            story.append(Paragraph(self.datos.subtitulo, self.styles['Subtitulo']))
        if self.datos.fuente_datos:
            story.append(Paragraph(f"Fuente: {self.datos.fuente_datos}", self.styles['NormalJust']))
        story.append(Spacer(1, 12))
        story.append(_tabla_kv(self.datos.resumen_general))
        story.append(PageBreak())

        # Sección: Estadísticas numéricas
        story.append(Paragraph("Estadísticas descriptivas (numéricas)", self.styles['Seccion']))
        if self.datos.estadisticas_numericas is not None and not self.datos.estadisticas_numericas.empty:
            story.append(_tabla_desde_dataframe(self.datos.estadisticas_numericas))
        else:
            story.append(Paragraph("No se encontraron columnas numéricas para describir.", self.styles['NormalJust']))
        story.append(Spacer(1, 12))

        # Sección: Tablas categóricas
        story.append(Paragraph("Distribuciones por columnas categóricas (Top)", self.styles['Seccion']))
        if self.datos.tablas_categoricas:
            for col, df in self.datos.tablas_categoricas.items():
                story.append(Paragraph(f"Columna: {col}", self.styles['NormalJust']))
                story.append(_tabla_desde_dataframe(df))
                story.append(Spacer(1, 8))
        else:
            story.append(Paragraph("No se identificaron columnas categóricas.", self.styles['NormalJust']))
        story.append(PageBreak())


        # Sección: Figuras
        story.append(Paragraph("Figuras generadas", self.styles['Seccion']))

        # Cálculo del ancho disponible del frame (con A4 y márgenes ya definidos en doc)
        page_w, _ = A4
        available_w = page_w - 2*cm - 2*cm  # leftMargin=2cm, rightMargin=2cm tal como configuras el doc
        # Usa el menor entre tu ancho configurado y el ancho disponible del frame
        max_w = min(self.ancho_figura_cm * cm, available_w)
        max_h = 11 * cm   # límite prudente de altura (ajústalo a gusto: 10–13 cm funcionan bien)

        for ruta in self.datos.figuras:
            if os.path.exists(ruta):
                img = Image(ruta)
                # Limita tamaño por seguridad (mantiene proporciones dentro del box si luego usamos KeepInFrame)
                img._restrictSize(max_w, max_h)

                # Encapsula para que, si el espacio restante del frame es menor, se reduzca automáticamente
                kif = KeepInFrame(max_w, max_h, [img], mode='shrink')

                story.append(kif)
                story.append(Spacer(1, 6))
                story.append(Paragraph(os.path.basename(ruta), self.styles['NormalJust']))
                story.append(Spacer(1, 8))

        # Opcional: salto de página tras la sección de figuras
        story.append(PageBreak())


        # Notas
        story.append(Paragraph("Notas", self.styles['Seccion']))
        story.append(Paragraph(self.datos.notas or "—", self.styles['NormalJust']))

        # Construir PDF con encabezado/pie
        doc.build(story, onFirstPage=_cabecera_pie, onLaterPages=_cabecera_pie)
