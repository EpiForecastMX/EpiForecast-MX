"""PDF report generation with IMSS branding and forecast results."""

# src/utils/reporte_PDF.py
import os
from typing import Any

from loguru import logger
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepInFrame,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from epiforecast.visualization.eda_plots import ReportData, SeccionNota
from epiforecast.visualization.report_tables import (
    _hacer_cabecera_pie,
    tabla_desde_dataframe,
    tabla_kv,
)

# ---------- Clase principal ---------- #


class PDFReportGenerator:
    """Genera un reporte PDF de EDA a partir de un objeto ReportData."""

    def __init__(
        self,
        datos_reporte: ReportData,
        archivo_salida: str | os.PathLike[str],
        ancho_figura_cm: float = 16.0,
    ) -> None:
        """Inicializa el generador de reportes PDF con datos y ruta de salida.

        Args:
            datos_reporte:   Objeto ReportData con resúmenes, figuras y notas.
            archivo_salida:  Ruta del archivo PDF a generar.
            ancho_figura_cm: Ancho máximo de figuras en centímetros.
        """
        self.datos = datos_reporte
        self.archivo_salida = archivo_salida
        self.ancho_figura_cm = ancho_figura_cm
        self.styles = self._crear_estilos()

    # ---------- Estilos ---------- #

    def _crear_estilos(self) -> Any:
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="Titulo",
                parent=styles["Title"],
                fontName="Helvetica-Bold",
                fontSize=18,
                leading=22,
                alignment=1,
                spaceAfter=12,
            )
        )
        styles.add(
            ParagraphStyle(
                name="Subtitulo",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=12,
                textColor=colors.grey,
                alignment=1,
                spaceAfter=12,
            )
        )
        styles.add(
            ParagraphStyle(
                name="Seccion",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=14,
                spaceBefore=12,
                spaceAfter=6,
                alignment=1,
            )
        )
        styles.add(
            ParagraphStyle(
                name="NormalJust",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
            )
        )
        return styles

    # ---------- Secciones ---------- #

    def _agregar_portada(self, story: list[Any]) -> None:
        story.append(Paragraph(self.datos.titulo, self.styles["Titulo"]))
        if self.datos.subtitulo:
            story.append(Paragraph(self.datos.subtitulo, self.styles["Subtitulo"]))
        story.append(Spacer(1, 24))
        story.append(tabla_kv(self.datos.resumen_general))
        story.append(PageBreak())

    def _agregar_tabla_si_existe(
        self, story: list[Any], titulo: str, df: pd.DataFrame | None
    ) -> None:
        story.append(Spacer(1, 6))
        story.append(Paragraph(titulo, self.styles["Seccion"]))
        if isinstance(df, pd.DataFrame) and not df.empty:
            story.append(tabla_desde_dataframe(df))
        else:
            story.append(Paragraph("No se encontraron datos.", self.styles["NormalJust"]))
        story.append(Spacer(1, 12))

    def _agregar_tablas_campos(self, story: list[Any]) -> None:
        self._agregar_tabla_si_existe(
            story, "Características de los campos", self.datos.resumen_datos
        )
        self._agregar_tabla_si_existe(
            story,
            "Estadísticas descriptivas de variables numéricas",
            self.datos.estadisticas_numericas,
        )
        self._agregar_tabla_si_existe(
            story,
            "Estadísticas descriptivas de variables categóricas",
            self.datos.estadisticas_categoricas,
        )
        self._agregar_tabla_si_existe(
            story, "Campos con valores nulos", self.datos.resumen_datos_nulos
        )
        story.append(PageBreak())

        story.append(Paragraph("Distribuciones de variables categóricas", self.styles["Seccion"]))
        if self.datos.tablas_categoricas:
            for df in self.datos.tablas_categoricas.values():
                story.append(tabla_desde_dataframe(df))
                story.append(Spacer(1, 8))
        else:
            story.append(
                Paragraph("No se identificaron columnas categóricas.", self.styles["NormalJust"])
            )
        story.append(PageBreak())

    def _agregar_figuras(self, story: list[Any]) -> None:
        story.append(Paragraph("Visualizaciones generadas", self.styles["Seccion"]))
        max_w = min(self.ancho_figura_cm * cm, A4[0] - 4 * cm)
        # Espacio útil vertical en A4 (página - márgenes - encabezado/pie)
        alto_pagina = A4[1] - 5.5 * cm
        # Umbral: figuras con altura natural > 14 cm reciben página propia
        umbral_alto = 14 * cm
        contador = 0
        par_abierto = False  # lleva cuenta de si hay una figura "suelta" en la página actual

        for ruta in self.datos.figuras:
            if not os.path.exists(ruta):
                logger.warning(f"Figura no encontrada, se omite: {ruta}")
                continue

            img = Image(ruta)
            # Altura proporcional al ancho disponible (mantiene aspect ratio)
            aspect = img.imageHeight / img.imageWidth if img.imageWidth > 0 else 1.0
            h_natural = aspect * max_w
            es_figura_alta = h_natural > umbral_alto

            if es_figura_alta:
                # Si hay una figura suelta arriba, cerrar la página antes
                if par_abierto:
                    story.append(PageBreak())
                    par_abierto = False
                max_h = min(h_natural, alto_pagina)
                img._restrictSize(max_w, max_h)
                story.append(KeepInFrame(max_w, max_h, [img], mode="shrink"))
                story.append(PageBreak())
            else:
                max_h = min(h_natural, umbral_alto)
                img._restrictSize(max_w, max_h)
                story.append(KeepInFrame(max_w, max_h, [img], mode="shrink"))
                story.append(Spacer(1, 8))
                par_abierto = not par_abierto
                if not par_abierto:  # se completó el par → salto de página
                    story.append(PageBreak())

            contador += 1

        if par_abierto:
            story.append(PageBreak())

    def _agregar_seccion_nota(self, story: list[Any], seccion: SeccionNota) -> None:
        """Renderiza una SeccionNota: título + texto libre + tabla kv + DataFrame."""
        story.append(Spacer(1, 6))
        story.append(Paragraph(seccion.titulo, self.styles["Seccion"]))
        if seccion.texto:
            story.append(Paragraph(seccion.texto, self.styles["NormalJust"]))
            story.append(Spacer(1, 8))
        if seccion.parametros:
            story.append(tabla_kv(seccion.parametros))
            story.append(Spacer(1, 8))
        if isinstance(seccion.tabla, pd.DataFrame) and not seccion.tabla.empty:
            story.append(tabla_desde_dataframe(seccion.tabla))
        story.append(Spacer(1, 12))

    def _agregar_notas(self, story: list[Any]) -> None:
        tiene_notas = bool(self.datos.notas or self.datos.secciones_notas)
        if not tiene_notas:
            return

        story.append(Paragraph("Notas del proceso", self.styles["Titulo"]))
        story.append(Spacer(1, 8))

        # Texto libre (compatibilidad con campo legacy `notas`)
        if self.datos.notas:
            story.append(Paragraph(self.datos.notas, self.styles["NormalJust"]))
            story.append(Spacer(1, 16))

        # Secciones estructuradas
        for seccion in self.datos.secciones_notas:
            self._agregar_seccion_nota(story, seccion)

        story.append(PageBreak())

    # ---------- Punto de entrada ---------- #

    def build(self) -> None:
        """Construye y guarda el reporte PDF con portada, tablas, figuras y notas."""

        """Construye y guarda el reporte PDF."""
        doc = SimpleDocTemplate(
            self.archivo_salida,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2.2 * cm,
            bottomMargin=2.0 * cm,
        )
        logger.info(f"Generando reporte PDF: {self.archivo_salida}")
        logger.debug(
            f"Página {doc.pagesize[0] / cm:.2f} × {doc.pagesize[1] / cm:.2f} cm | "
            f"Márgenes izq={doc.leftMargin / cm:.2f} der={doc.rightMargin / cm:.2f} "
            f"sup={doc.topMargin / cm:.2f} inf={doc.bottomMargin / cm:.2f} cm"
        )

        story: list[Any] = []
        logger.debug("Construyendo secciones del reporte PDF.")
        self._agregar_portada(story)
        self._agregar_tablas_campos(story)
        self._agregar_figuras(story)
        self._agregar_notas(story)

        on_page = _hacer_cabecera_pie(self.datos.titulo)
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
        logger.success(f"Reporte PDF generado: {self.archivo_salida}")
