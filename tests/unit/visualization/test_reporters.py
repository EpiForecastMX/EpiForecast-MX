"""Tests for reporters.py — PDFReportGenerator."""

import matplotlib.pyplot as plt
import pandas as pd

from epiforecast.visualization.eda_plots import ReportData, SeccionNota
from epiforecast.visualization.reporters import PDFReportGenerator


def _create_png(path, width: int = 800, height: int = 200) -> str:
    """Create a minimal PNG at given path and return path str."""
    fig, ax = plt.subplots(figsize=(width / 100, height / 100))
    ax.plot([0, 1], [0, 1])
    fig.savefig(str(path), dpi=100)
    plt.close(fig)
    return str(path)


def _make_report_data(
    figuras: list[str] | None = None,
    notas: str | None = None,
    secciones: list | None = None,
) -> ReportData:
    return ReportData(
        titulo="Reporte Test",
        subtitulo="Subtítulo de prueba",
        fuente_datos="datos_test.csv",
        resumen_general={"Filas": "100", "Columnas": "5"},
        resumen_datos=pd.DataFrame({"Campo": ["col_a"], "Tipo": ["int64"]}),
        resumen_datos_nulos=None,
        estadisticas_numericas=pd.DataFrame({"count": [100.0]}, index=["col_a"]),
        estadisticas_categoricas=None,
        tablas_categoricas={},
        figuras=figuras or [],
        notas=notas,
        secciones_notas=secciones or [],
    )


class TestInit:
    def test_datos_stored(self, tmp_path):
        rd = _make_report_data()
        gen = PDFReportGenerator(rd, str(tmp_path / "r.pdf"))
        assert gen.datos is rd

    def test_archivo_salida_stored(self, tmp_path):
        rd = _make_report_data()
        path = str(tmp_path / "r.pdf")
        gen = PDFReportGenerator(rd, path)
        assert str(gen.archivo_salida) == path

    def test_default_ancho_figura(self, tmp_path):
        rd = _make_report_data()
        gen = PDFReportGenerator(rd, str(tmp_path / "r.pdf"))
        assert gen.ancho_figura_cm == 16.0

    def test_custom_ancho_figura(self, tmp_path):
        rd = _make_report_data()
        gen = PDFReportGenerator(rd, str(tmp_path / "r.pdf"), ancho_figura_cm=12.0)
        assert gen.ancho_figura_cm == 12.0


class TestCrearEstilos:
    def test_styles_created(self, tmp_path):
        rd = _make_report_data()
        gen = PDFReportGenerator(rd, str(tmp_path / "r.pdf"))
        assert "Titulo" in gen.styles
        assert "Subtitulo" in gen.styles
        assert "Seccion" in gen.styles
        assert "NormalJust" in gen.styles


class TestBuild:
    def test_build_creates_pdf(self, tmp_path):
        rd = _make_report_data()
        out = tmp_path / "output.pdf"
        gen = PDFReportGenerator(rd, str(out))
        gen.build()
        assert out.exists()
        assert out.stat().st_size > 0

    def test_build_with_notas(self, tmp_path):
        rd = _make_report_data(notas="Nota de prueba del proceso.")
        out = tmp_path / "output_notas.pdf"
        gen = PDFReportGenerator(rd, str(out))
        gen.build()
        assert out.exists()

    def test_build_with_secciones_notas(self, tmp_path):
        seccion = SeccionNota(
            titulo="Sección especial",
            texto="Texto explicativo.",
            parametros={"Param A": "Valor A"},
        )
        rd = _make_report_data(secciones=[seccion])
        out = tmp_path / "output_secciones.pdf"
        gen = PDFReportGenerator(rd, str(out))
        gen.build()
        assert out.exists()

    def test_build_no_subtitulo(self, tmp_path):
        rd = ReportData(
            titulo="Solo Título",
            subtitulo=None,
            fuente_datos=None,
            resumen_general={},
            resumen_datos=None,
            resumen_datos_nulos=None,
            estadisticas_numericas=None,
            estadisticas_categoricas=None,
            tablas_categoricas={},
        )
        out = tmp_path / "output_notitulo.pdf"
        gen = PDFReportGenerator(rd, str(out))
        gen.build()
        assert out.exists()

    def test_build_with_missing_figura_skips(self, tmp_path):
        rd = _make_report_data(figuras=["/nonexistent/path/figura.png"])
        out = tmp_path / "output_missing_fig.pdf"
        gen = PDFReportGenerator(rd, str(out))
        gen.build()
        assert out.exists()

    def test_build_with_tablas_categoricas(self, tmp_path):
        rd = ReportData(
            titulo="Con Tablas Cat",
            subtitulo=None,
            fuente_datos=None,
            resumen_general={},
            resumen_datos=None,
            resumen_datos_nulos=None,
            estadisticas_numericas=None,
            estadisticas_categoricas=pd.DataFrame({"cat": ["A", "B"], "count": [10, 5]}),
            tablas_categoricas={
                "Padecimiento": pd.DataFrame({"Padecimiento": ["Depresión"], "n": [50]})
            },
        )
        out = tmp_path / "output_cat.pdf"
        gen = PDFReportGenerator(rd, str(out))
        gen.build()
        assert out.exists()


class TestAgregarTablaSiExiste:
    def test_with_valid_df(self, tmp_path):
        rd = _make_report_data()
        gen = PDFReportGenerator(rd, str(tmp_path / "r.pdf"))
        story = []
        gen._agregar_tabla_si_existe(story, "Título", pd.DataFrame({"A": [1]}))
        assert len(story) > 0

    def test_with_none_df(self, tmp_path):
        rd = _make_report_data()
        gen = PDFReportGenerator(rd, str(tmp_path / "r.pdf"))
        story = []
        gen._agregar_tabla_si_existe(story, "Título", None)
        assert len(story) > 0

    def test_with_empty_df(self, tmp_path):
        rd = _make_report_data()
        gen = PDFReportGenerator(rd, str(tmp_path / "r.pdf"))
        story = []
        gen._agregar_tabla_si_existe(story, "Título", pd.DataFrame())
        assert len(story) > 0


class TestAgregarSeccionNota:
    def test_with_all_fields(self, tmp_path):
        rd = _make_report_data()
        gen = PDFReportGenerator(rd, str(tmp_path / "r.pdf"))
        story = []
        seccion = SeccionNota(
            titulo="Mi Sección",
            texto="Párrafo.",
            parametros={"k": "v"},
            tabla=pd.DataFrame({"X": [1, 2]}),
        )
        gen._agregar_seccion_nota(story, seccion)
        assert len(story) > 0

    def test_with_minimal_seccion(self, tmp_path):
        rd = _make_report_data()
        gen = PDFReportGenerator(rd, str(tmp_path / "r.pdf"))
        story = []
        seccion = SeccionNota(titulo="Solo título")
        gen._agregar_seccion_nota(story, seccion)
        assert len(story) > 0


class TestAgregarFiguras:
    def test_with_wide_figure_short_branch(self, tmp_path):
        """Wide PNG → es_figura_alta=False → fills even/odd pair logic."""
        fig_path = _create_png(tmp_path / "wide.png", width=1600, height=400)
        rd = _make_report_data(figuras=[fig_path])
        gen = PDFReportGenerator(rd, str(tmp_path / "out.pdf"))
        story: list = []
        gen._agregar_figuras(story)
        assert len(story) > 0

    def test_with_tall_figure_tall_branch(self, tmp_path):
        """Tall PNG → es_figura_alta=True → uses KeepInFrame + PageBreak."""
        fig_path = _create_png(tmp_path / "tall.png", width=400, height=800)
        rd = _make_report_data(figuras=[fig_path])
        gen = PDFReportGenerator(rd, str(tmp_path / "out_tall.pdf"))
        story: list = []
        gen._agregar_figuras(story)
        assert len(story) > 0

    def test_odd_figure_count_closes_pair(self, tmp_path):
        """Odd number of short figures triggers par_abierto PageBreak at end."""
        paths = [
            _create_png(tmp_path / f"wide_{i}.png", width=1600, height=400)
            for i in range(3)  # 3 wide figs → last closes as odd
        ]
        rd = _make_report_data(figuras=paths)
        gen = PDFReportGenerator(rd, str(tmp_path / "out_odd.pdf"))
        story: list = []
        gen._agregar_figuras(story)
        assert len(story) > 0

    def test_build_with_real_figures(self, tmp_path):
        """Integration: build() with real PNG files in figuras list."""
        fig_path = _create_png(tmp_path / "figure.png", width=1600, height=400)
        rd = _make_report_data(figuras=[fig_path])
        out = tmp_path / "report_with_fig.pdf"
        gen = PDFReportGenerator(rd, str(out))
        gen.build()
        assert out.exists()
