from __future__ import annotations

import os
import re
import unicodedata
from io import StringIO
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from loguru import logger

# ReportLab
from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
)

from src.configuraciones.config_params import conf
from src.utils import DirectoryManager


class EDA:

    def __init__(self, input_path: str | Path | pd.DataFrame,
                 salida_dir: str | Path | None = None,
                 nombre_reporte: str = "EDA",
                 filtro_padecimiento: str | None = r"^Enfermedad de Alzheimer",
                 incluir_graficos: bool = True,
                 max_filas_tabla: int = 200,
                 max_imgs: int = 12):
        
        self.input_path = input_path
        self.df: pd.DataFrame | None = None
        self.salida_dir = Path(salida_dir) if salida_dir else self._default_salida_dir()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.nombre_reporte = f"{nombre_reporte}_{timestamp}"

        self.filtro_padecimiento = filtro_padecimiento
        self.incluir_graficos = incluir_graficos
        self.max_filas_tabla = max_filas_tabla
        self.max_imgs = max_imgs

    def _default_salida_dir(self) -> Path:
        """
        Usa conf['paths']['docs'] si existe, si no, crea ./reportes
        """
        if conf and "paths" in conf and "docs" in conf["paths"]:
            return Path(conf["paths"]["docs"])
        return Path("./reportes")

    def _pdf_path(self) -> Path:
        return self.salida_dir / f"{self.nombre_reporte}.pdf"

    @staticmethod
    def _safe_filename(text: str) -> str:
        """
        Convierte un texto a un nombre de archivo seguro:
        - Quita acentos (ñ -> n, á -> a, etc.)
        - Reemplaza caracteres no [a-zA-Z0-9_-] por '_'
        - Evita nombre vacío retornando 'columna'
        """
        norm = unicodedata.normalize("NFKD", text)
        ascii_text = norm.encode("ascii", "ignore").decode("ascii")
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", ascii_text)
        safe = safe.strip("_")
        return safe or "columna"



    # ---------- Carga ----------
    def load_dataset(self) -> pd.DataFrame:

        logger.info(f"Cargando dataset desde: {self.input_path}")

        if isinstance(self.input_path, pd.DataFrame):
            datos = self.input_path.copy()
        else:
            if DirectoryManager.existe_archivo is False:
                logger.error(f'Archivo no localizado {self.input_path}')
                raise ValueError(f'Archivo no localizado {self.input_path}')
            datos = pd.read_csv(self.input_path)



        if self.filtro_padecimiento and "Padecimiento" in datos.columns:
            datos = datos[datos["Padecimiento"].astype(str).str.contains(
                self.filtro_padecimiento, case=False, na=False
            )]

        self.df = datos
        return datos

    # ---------- Análisis ----------
    def resumen_nulos(self, datos: pd.DataFrame) -> pd.DataFrame:
        nulos = datos.isna().sum()
        porc = (datos.isna().mean() * 100).round(2)
        return pd.DataFrame({
            "columna": datos.columns,
            "n_nulos": nulos.values,
            "%_nulos": porc.values
        }).sort_values(by="n_nulos", ascending=False)

    def describe_numericas(self, datos: pd.DataFrame) -> pd.DataFrame:
        dn = datos.select_dtypes(include=[np.number]).describe().T
        return dn.round(4).reset_index().rename(columns={"index": "columna"})

    def describe_objetos(self, datos: pd.DataFrame) -> pd.DataFrame:
        cols = datos.select_dtypes(include=["object", "category"]).columns.tolist()
        if not cols:
            return pd.DataFrame()
        return pd.DataFrame({
            "columna": cols,
            "n_unique": [datos[c].nunique(dropna=True) for c in cols],
            "top": [datos[c].value_counts(dropna=True).index[0] if datos[c].value_counts(dropna=True).size > 0 else None for c in cols],
            "freq_top": [int(datos[c].value_counts(dropna=True).iloc[0]) if datos[c].value_counts(dropna=True).size > 0 else 0 for c in cols],
        }).sort_values(by="n_unique", ascending=False)

    def info_texto(self, datos: pd.DataFrame) -> str:
        buf = StringIO()
        datos.info(buf=buf)
        return buf.getvalue()

    # ---------- PDF ----------
    def _styles(self):
        title = ParagraphStyle(name="Title", fontName="Helvetica-Bold", fontSize=18, leading=22, alignment=TA_LEFT, spaceAfter=12)
        h2 = ParagraphStyle(name="H2", fontName="Helvetica-Bold", fontSize=14, leading=18, alignment=TA_LEFT, spaceAfter=8)
        body = ParagraphStyle(name="Body", fontName="Helvetica", fontSize=10, leading=14, alignment=TA_LEFT)
        small = ParagraphStyle(name="Small", fontName="Helvetica-Oblique", fontSize=8, leading=10, alignment=TA_LEFT)
        return title, h2, body, small

    def _tabla(self, df: pd.DataFrame, max_filas: int) -> Table:
        data = [list(df.columns)] + df.values.tolist()
        if len(data) - 1 > max_filas:
            data = data[:max_filas + 1]
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfbfb")]),
        ]))
        return t

    def _histogramas(self, datos: pd.DataFrame, dir_salida: Path, max_imgs: int) -> list[Path]:

        num_cols = datos.select_dtypes(include=[np.number]).columns.tolist()
        imgs: list[Path] = []

        # Asegurar el directorio antes de guardar imágenes
        dir_salida.mkdir(parents=True, exist_ok=True)

        for col in num_cols[:max_imgs]:
            serie = datos[col].dropna()
            fig, ax = plt.subplots(figsize=(5, 3), dpi=120)
            if not serie.empty:
                ax.hist(serie, bins=30, color="#4c78a8", alpha=0.85)
                ax.set_title(f"Histograma: {col}")
                ax.set_xlabel(col)
                ax.set_ylabel("Frecuencia")
                ax.grid(True, linestyle="--", alpha=0.3)
            else:
                ax.text(0.5, 0.5, "Sin datos", ha="center", va="center")

            safe = self._safe_filename(str(col))
            img_path = dir_salida / f"_hist_{safe}.png"
            fig.tight_layout()
            fig.savefig(img_path, bbox_inches="tight")
            plt.close(fig)
            imgs.append(img_path)

        return imgs

    def construir_pdf(self, datos: pd.DataFrame) -> Path:
        """
        Construye el PDF. Inserta imágenes con rutas absolutas y
        realiza la limpieza de PNGs temporales DESPUÉS de doc.build().
        """
        # Asegurar directorio de salida
        self.salida_dir.mkdir(parents=True, exist_ok=True)
        output_file = self._pdf_path()

        title, h2, body, small = self._styles()
        elementos = []

        # Portada
        elementos.append(Paragraph("Reporte EDA", title))
        elementos.append(Paragraph(f"Generado: {datetime.now():%Y-%m-%d %H:%M}", small))
        elementos.append(Paragraph(f"Filas: {len(datos):,}  |  Columnas: {len(datos.columns):,}", body))
        elementos.append(Spacer(1, 0.25 * inch))

        # Nulos
        elementos.append(Paragraph("Valores nulos por columna", h2))
        elementos.append(self._tabla(self.resumen_nulos(datos), self.max_filas_tabla))
        elementos.append(Spacer(1, 0.25 * inch))

        # Describe numéricas
        dn = self.describe_numericas(datos)
        if not dn.empty:
            elementos.append(Paragraph("Estadísticos (numéricos) - describe()", h2))
            elementos.append(self._tabla(dn, self.max_filas_tabla))

        # Categóricas
        do = self.describe_objetos(datos)
        if not do.empty:
            elementos.append(Spacer(1, 0.2 * inch))
            elementos.append(Paragraph("Resumen columnas categóricas/objeto", h2))
            elementos.append(self._tabla(do, self.max_filas_tabla))

        # Gráficos
        imgs: list[Path] = []
        if self.incluir_graficos and not datos.select_dtypes(include=[np.number]).empty:
            elementos.append(PageBreak())
            elementos.append(Paragraph("Distribuciones (histogramas) de columnas numéricas", h2))

            # Generar imágenes
            imgs = self._histogramas(datos, self.salida_dir, self.max_imgs)

            # Insertar con rutas absolutas (robusto si cambia el cwd)
            for p in imgs:
                elementos.append(Image(str(p.resolve()), width=5.5 * inch, height=3.3 * inch))
                elementos.append(Spacer(1, 0.15 * inch))

        # Construir PDF
        doc = SimpleDocTemplate(
            str(output_file.resolve()),
            pagesize=LETTER,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch
        )
        doc.build(elementos)

        # Limpieza de archivos temporales (ahora sí)
        for p in imgs:
            try:
                os.remove(p)
            except Exception:
                # Si no se puede borrar, lo dejamos; no es crítico.
                pass

        print(f"✅ Reporte PDF generado: {output_file.resolve()}")
        return output_file

    # ---------- Orquestación ----------
    def run(self) -> Path:
        datos = self.load_dataset()
        return self.construir_pdf(datos)
