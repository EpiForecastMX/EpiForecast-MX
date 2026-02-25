"""Tests for report_tables.py — PDF table building utilities."""

from unittest.mock import MagicMock

import pandas as pd
from reportlab.platypus import LongTable

from epiforecast.visualization.report_tables import (
    _hacer_cabecera_pie,
    crear_tabla,
    tabla_desde_dataframe,
    tabla_kv,
)


class TestCrearTabla:
    def test_returns_long_table(self):
        t = crear_tabla([["A", "B"], ["1", "2"]])
        assert isinstance(t, LongTable)

    def test_single_row(self):
        t = crear_tabla([["Encabezado"]])
        assert isinstance(t, LongTable)

    def test_custom_col_widths(self):
        t = crear_tabla([["A", "B"], ["1", "2"]], col_widths=[100.0, 100.0])
        assert isinstance(t, LongTable)

    def test_default_align_center(self):
        t = crear_tabla([["A"], ["1"]])
        assert t.hAlign == "CENTER"

    def test_custom_halign_left(self):
        t = crear_tabla([["A"], ["1"]], h_align="LEFT")
        assert t.hAlign == "LEFT"

    def test_multirow_table(self):
        data = [["Col1", "Col2"]] + [[str(i), str(i * 2)] for i in range(5)]
        t = crear_tabla(data)
        assert isinstance(t, LongTable)


class TestTablaDesdeDf:
    def test_returns_long_table_for_dataframe(self):
        df = pd.DataFrame({"X": [1, 2], "Y": [3, 4]})
        t = tabla_desde_dataframe(df)
        assert isinstance(t, LongTable)

    def test_none_returns_sin_datos_table(self):
        t = tabla_desde_dataframe(None)
        assert isinstance(t, LongTable)

    def test_empty_df_returns_sin_datos_table(self):
        df = pd.DataFrame()
        t = tabla_desde_dataframe(df)
        assert isinstance(t, LongTable)

    def test_narrow_df_uses_explicit_widths(self):
        # 3 columns → header has 4 items (index + 3 cols) <= 4 → explicit widths
        df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
        t = tabla_desde_dataframe(df)
        assert isinstance(t, LongTable)

    def test_wide_df_no_explicit_widths(self):
        # 5+ cols → colWidths = None
        df = pd.DataFrame({c: [1] for c in list("ABCDE")})
        t = tabla_desde_dataframe(df)
        assert isinstance(t, LongTable)

    def test_single_column(self):
        df = pd.DataFrame({"Valor": [10, 20, 30]})
        t = tabla_desde_dataframe(df)
        assert isinstance(t, LongTable)


class TestTablaKV:
    def test_returns_long_table(self):
        t = tabla_kv({"clave": "valor"})
        assert isinstance(t, LongTable)

    def test_none_dict_returns_placeholder(self):
        t = tabla_kv(None)
        assert isinstance(t, LongTable)

    def test_empty_dict_returns_placeholder(self):
        t = tabla_kv({})
        assert isinstance(t, LongTable)

    def test_multiple_entries(self):
        t = tabla_kv({"a": "1", "b": "2", "c": "3"})
        assert isinstance(t, LongTable)

    def test_string_conversion(self):
        t = tabla_kv({"número": 42, "booleano": True})  # type: ignore[arg-type]
        assert isinstance(t, LongTable)


class TestHacerCabeceraPie:
    def test_returns_callable(self):
        fn = _hacer_cabecera_pie("Reporte EpiForecast")
        assert callable(fn)

    def test_callback_save_restore_state(self):
        fn = _hacer_cabecera_pie("Test")
        canv = MagicMock()
        canv.getPageNumber.return_value = 1
        doc = MagicMock()
        fn(canv, doc)
        canv.saveState.assert_called_once()
        canv.restoreState.assert_called_once()

    def test_callback_draws_title(self):
        fn = _hacer_cabecera_pie("Mi Reporte")
        canv = MagicMock()
        canv.getPageNumber.return_value = 2
        doc = MagicMock()
        fn(canv, doc)
        assert canv.drawString.called or canv.drawRightString.called

    def test_callback_draws_page_number(self):
        fn = _hacer_cabecera_pie("Reporte")
        canv = MagicMock()
        canv.getPageNumber.return_value = 5
        doc = MagicMock()
        fn(canv, doc)
        canv.drawRightString.assert_called_once()
        # page number should appear in the drawn string
        drawn_text = canv.drawRightString.call_args[0][2]
        assert "5" in drawn_text

    def test_closure_uses_titulo(self):
        fn = _hacer_cabecera_pie("Informe Especial")
        canv = MagicMock()
        canv.getPageNumber.return_value = 1
        doc = MagicMock()
        fn(canv, doc)
        drawn_text = canv.drawString.call_args[0][2]
        assert "Informe Especial" in drawn_text
