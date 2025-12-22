# src/datos/EDA.py
import pandas as pd
import numpy as np
from loguru import logger
from io import StringIO
from pathlib import Path
import os
from datetime import datetime
import matplotlib.pyplot as plt

# ReportLab
from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.enums import TA_LEFT



from src.utils.reportes import histograma
from src.configuraciones.config_params import conf
from src.utils import paths


class EDA:
    
    def __init__(self, input_path):

        self.input_path = input_path            # Ruta del dataset original o DataFrame
        self.df = None                          # DataFrame que contendrá los datos cargados
        self._from_dataframe = isinstance(input_path, pd.DataFrame)

    # Carga del dataset original
    def load_dataset(self):

        logger.info(f"Cargando dataset original desde: {self.input_path}")
        
        if isinstance(self.input_path, pd.DataFrame):
            self.df = self.input_path.copy()
            logger.debug("Dataset cargado desde DataFrame en memoria")
            return

        if self.input_path is None:
            raise ValueError("input_path es None: debe proporcionar una ruta o un DataFrame antes de llamar a load_dataset().")

        self.df = pd.read_csv(self.input_path)

        df_Alzheimer = self.df[self.df["Padecimiento"].str.contains("^Enfermedad de Alzheimer", case=False, na=False)]

        return df_Alzheimer

    def caracteristicas_dataset(self, df_Alzheimer: pd.DataFrame) -> pd.DataFrame:

        datos = df_Alzheimer
        max_filas_tabla = 200
        incluir_graficos = True
        
        reporte_salida = Path(conf["paths"]["docs"])
        nombre_reporte = "EDA"
        paths.asegurar_ruta(reporte_salida) 

        #output_file = reporte_salida / nombre_reporte
        output_file = (reporte_salida / f"{nombre_reporte}.pdf").as_pos

        
        # --- Capturar info() ---
        buf = StringIO()
        datos.info(buf=buf)
        info_text = buf.getvalue()


        # --- Nulos por columna ---
        nulos = datos.isna().sum()
        porc_nulos = (datos.isna().mean() * 100).round(2)
        resumen_nulos = pd.DataFrame({
            "columna": datos.columns,
            "n_nulos": nulos.values,
            "%_nulos": porc_nulos.values
        }).sort_values(by="n_nulos", ascending=False)


    # --- Describe (numéricas y, si aplica, objetos con conteo) ---
        describe_num = datos.select_dtypes(include=[np.number]).describe().T
        # Para columnas no numéricas, mostramos conteo de valores únicos y top:
        describe_obj = None
        obj_cols = datos.select_dtypes(include=["object", "category"]).columns.tolist()
        if obj_cols:
            describe_obj = pd.DataFrame({
                "columna": obj_cols,
                "n_unique": [datos[c].nunique(dropna=True) for c in obj_cols],
                "top": [datos[c].value_counts(dropna=True).index[0] if datos[c].value_counts(dropna=True).size > 0 else None for c in obj_cols],
                "freq_top": [datos[c].value_counts(dropna=True).iloc[0] if datos[c].value_counts(dropna=True).size > 0 else 0 for c in obj_cols]
            }).sort_values(by="n_unique", ascending=False)

        
    # --- Estilos de texto ---
        title_style = ParagraphStyle(
            name="Title",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_LEFT,
            spaceAfter=12
        )
        h2_style = ParagraphStyle(
            name="H2",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            alignment=TA_LEFT,
            spaceAfter=8
        )
        mono_style = ParagraphStyle(
            name="Mono",
            fontName="Courier",
            fontSize=9.5,
            leading=12,
            alignment=TA_LEFT
        )
        body_style = ParagraphStyle(
            name="Body",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            alignment=TA_LEFT
        )
        small_style = ParagraphStyle(
            name="Small",
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            alignment=TA_LEFT
        )

        
        # --- Documento ---
        doc = SimpleDocTemplate(
            output_file,
            pagesize=LETTER,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        elementos = []


        # Portada
        elementos.append(Paragraph("Reporte EDA", title_style))
        elementos.append(Paragraph(f"Generado: {datetime.now():%Y-%m-%d %H:%M}", small_style))
        elementos.append(Paragraph(f"Filas: {len(datos):,} | Columnas: {len(datos.columns):,}", body_style))
        elementos.append(Spacer(1, 0.25*inch))


        # Sección nulos
        elementos.append(Paragraph("Valores nulos por columna", h2_style))
        # Preparar tabla de nulos
        tabla_nulos_data = [list(resumen_nulos.columns)] + resumen_nulos.values.tolist()
        # Limitar tamaño
        if len(tabla_nulos_data) - 1 > max_filas_tabla:
            tabla_nulos_data = tabla_nulos_data[:max_filas_tabla+1]
            elementos.append(Paragraph(
                f"Se muestran las primeras {max_filas_tabla} columnas por número de nulos.",
                small_style
            ))

        tabla_nulos = Table(tabla_nulos_data, repeatRows=1)
        tabla_nulos.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfbfb")])
        ]))
        elementos.append(tabla_nulos)
        elementos.append(Spacer(1, 0.25*inch))


        
        # Sección describe numéricas
        if not describe_num.empty:
            elementos.append(Paragraph("Estadísticos (numéricos) - describe()", h2_style))
            dn = describe_num.round(4).reset_index()
            dn.rename(columns={"index": "columna"}, inplace=True)
            tabla_dn = [list(dn.columns)] + dn.values.tolist()
            # Limitar filas si es grande
            if len(tabla_dn) - 1 > max_filas_tabla:
                tabla_dn = tabla_dn[:max_filas_tabla+1]
                elementos.append(Paragraph(
                    f"Se muestran las primeras {max_filas_tabla} columnas numéricas.",
                    small_style
                ))
            t_dn = Table(tabla_dn, repeatRows=1)
            t_dn.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfbfb")])
            ]))
            elementos.append(t_dn)




        # Sección objetos
        if describe_obj is not None and not describe_obj.empty:
            elementos.append(Spacer(1, 0.2*inch))
            elementos.append(Paragraph("Resumen columnas categóricas/objeto", h2_style))
            do = describe_obj
            do = do.replace({np.nan: None})
            tabla_do = [list(do.columns)] + do.values.tolist()
            if len(tabla_do) - 1 > max_filas_tabla:
                tabla_do = tabla_do[:max_filas_tabla+1]
                elementos.append(Paragraph(
                    f"Se muestran las primeras {max_filas_tabla} columnas categóricas.",
                    small_style
                ))
            t_do = Table(tabla_do, repeatRows=1)
            t_do.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfbfb")])
            ]))
            elementos.append(t_do)


        # (Opcional) Gráficos: histogramas de columnas numéricas
        if incluir_graficos and not datos.select_dtypes(include=[np.number]).empty:
            elementos.append(PageBreak())
            elementos.append(Paragraph("Distribuciones (histogramas) de columnas numéricas", h2_style))

            num_cols = datos.select_dtypes(include=[np.number]).columns.tolist()
            # Generar una imagen por columna (para PDFs robustos, evita demasiadas imágenes)
            max_imgs = 12  # límite razonable
            cols_to_plot = num_cols[:max_imgs]
            tmp_imgs = []

            for col in cols_to_plot:
                fig, ax = plt.subplots(figsize=(5, 3), dpi=120)
                serie = datos[col].dropna()
                if not serie.empty:
                    ax.hist(serie, bins=30, color="#4c78a8", alpha=0.85)
                    ax.set_title(f"Histograma: {col}")
                    ax.set_xlabel(col)
                    ax.set_ylabel("Frecuencia")
                    ax.grid(True, linestyle="--", alpha=0.3)
                else:
                    ax.text(0.5, 0.5, "Sin datos", ha="center", va="center")
                img_path = os.path.join(reporte_salida, f"_hist_{col}.png")
                fig.tight_layout()
                fig.savefig(img_path, bbox_inches="tight")
                plt.close(fig)
                tmp_imgs.append(img_path)

            # Insertar imágenes en el PDF
            for p in tmp_imgs:
                elementos.append(Image(p, width=5.5*inch, height=3.3*inch))
                elementos.append(Spacer(1, 0.15*inch))

            # Limpieza de archivos temporales (opcional)
            # for p in tmp_imgs:
            #     try:
            #         os.remove(p)
            #     except Exception:
            #         pass

        # --- Construir PDF ---
        doc.build(elementos)
        print(f"✅ Reporte PDF generado: {output_file}")
        return output_file

        
    




    def run(self):
        df_Alzheimer = self.load_dataset()
        self.caracteristicas_dataset(df_Alzheimer)
