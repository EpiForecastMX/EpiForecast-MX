"""C7.6-ADAPTERS-B0 — el sink real de Google Sheets, con un doble de la API.

Lo que protege: que el sink de hojas cumpla el mismo contrato que el doble en memoria **incluidas
las rarezas de la API real** —recorte de celdas vacías al final, escritura por bloques, errores en
cualquier llamada— y que ni un id de hoja ni una credencial se escapen en un mensaje de error.

Ninguna prueba toca la red. `gspread` ni siquiera tiene que estar instalado.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from epiforecast.publication.sheets_sink import (
    CHUNK_ROWS,
    LEGACY_TABS,
    PRODUCTION_ID_ENV,
    STAGING_ID_ENV,
    GoogleSheetsTableSink,
    SheetsApiError,
    staging_ids,
)
from epiforecast.publication.tableau_adapter import (
    SUFFIX_BACKUP,
    SUFFIX_NEXT,
    SUFFIX_PREVIOUS,
    TABLE_FORECAST,
    TABLE_RELEASES,
    ArtifactValidationError,
    build_tables,
    managed_tables,
    promote,
    promotion_plan,
    rollback,
)
from tests.unit.publication.test_tableau_adapter import _shard

ID_STAGING = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF"
ID_PRODUCCION = "1ZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZ"


# ── Doble de la API de hojas ───────────────────────────────────────────────────────────────────
def _recorta(fila: list[str]) -> list[str]:
    """La API devuelve las filas SIN las celdas vacías del final. Aquí se emula tal cual."""
    fin = len(fila)
    while fin and fila[fin - 1] == "":
        fin -= 1
    return list(fila[:fin])


class FakeWorksheet:
    def __init__(self, hoja: FakeSpreadsheet, title: str, rows: int, cols: int) -> None:
        self.title = title
        self.row_count = rows
        self.col_count = cols
        self._hoja = hoja
        self._celdas: list[list[str]] = []

    def get_all_values(self) -> list[list[str]]:
        self._hoja._registrar(f"get_all_values:{self.title}")
        filas = [_recorta(f) for f in self._celdas]
        while filas and not filas[-1]:  # la API recorta también las filas vacías del final
            filas.pop()
        return filas

    def update(self, *, range_name: str, values: list[list[str]], value_input_option: str) -> None:
        self._hoja._registrar(f"update:{self.title}:{range_name}")
        assert value_input_option == "RAW", (
            "sin RAW la hoja reinterpreta fechas y ceros a la izquierda"
        )
        inicio = int(range_name[1:]) - 1
        while len(self._celdas) < inicio + len(values):
            self._celdas.append([])
        ancho = max((len(f) for f in values), default=0)
        for i, fila in enumerate(values):
            self._celdas[inicio + i] = [str(v) for v in fila] + [""] * (ancho - len(fila))

    def clear(self) -> None:
        self._hoja._registrar(f"clear:{self.title}")
        self._celdas = []

    def resize(self, rows: int, cols: int) -> None:
        self._hoja._registrar(f"resize:{self.title}")
        self.row_count, self.col_count = rows, cols

    def update_title(self, title: str) -> None:
        self._hoja._registrar(f"update_title:{self.title}->{title}")
        self.title = title


class FakeSpreadsheet:
    """Doble de `gspread.Spreadsheet`: registra llamadas y puede reventar en cualquiera."""

    def __init__(self, tabs: dict[str, pd.DataFrame] | None = None, *, falla=None) -> None:
        self._tabs: list[FakeWorksheet] = []
        self.llamadas: list[str] = []
        self.falla = falla or (lambda op: False)
        for nombre, frame in (tabs or {}).items():
            ws = FakeWorksheet(self, nombre, len(frame) + 1, len(frame.columns))
            ws._celdas = [list(frame.columns)] + frame.astype(str).values.tolist()
            self._tabs.append(ws)

    def _registrar(self, operacion: str) -> None:
        self.llamadas.append(operacion)
        if self.falla(operacion):
            raise RuntimeError(f"la API rechazó {operacion} para la hoja {ID_STAGING}")

    def worksheets(self) -> list[FakeWorksheet]:
        self._registrar("worksheets")
        return list(self._tabs)

    def add_worksheet(self, *, title: str, rows: int, cols: int) -> FakeWorksheet:
        self._registrar(f"add_worksheet:{title}")
        ws = FakeWorksheet(self, title, rows, cols)
        self._tabs.append(ws)
        return ws

    def del_worksheet(self, ws: FakeWorksheet) -> None:
        self._registrar(f"del_worksheet:{ws.title}")
        self._tabs = [t for t in self._tabs if t is not ws]


def _sink(tabs=None, **kwargs) -> GoogleSheetsTableSink:
    hoja = FakeSpreadsheet(tabs)
    return GoogleSheetsTableSink(hoja, spreadsheet_id=ID_STAGING, **kwargs)


# ── Lectura y escritura fieles ─────────────────────────────────────────────────────────────────
def test_los_strings_vacios_del_final_sobreviven_al_viaje(tmp_path):
    """La API recorta las celdas vacías de la derecha, y en point-only son las dos últimas columnas."""
    tablas = build_tables(_shard(tmp_path, filas=4))
    sink = _sink()
    sink.write_table(TABLE_FORECAST, tablas.forecast)

    leido = sink.read_table(TABLE_FORECAST)
    assert list(leido.columns) == list(tablas.forecast.columns)
    assert len(leido) == len(tablas.forecast)
    assert (leido["yhat_lower"] == "").all() and (leido["yhat_upper"] == "").all()
    pd.testing.assert_frame_equal(leido, tablas.forecast.astype(str), check_dtype=False)


def test_la_escritura_va_por_bloques_y_ninguno_se_pierde(tmp_path):
    tablas = build_tables(_shard(tmp_path, filas=12))
    hoja = FakeSpreadsheet()
    sink = GoogleSheetsTableSink(hoja, spreadsheet_id=ID_STAGING, chunk_rows=5)
    sink.write_table(TABLE_FORECAST, tablas.forecast)

    escrituras = [c for c in hoja.llamadas if c.startswith(f"update:{TABLE_FORECAST}:")]
    assert len(escrituras) == 1 + math.ceil(12 / 5), "una cabecera y tres bloques"
    assert escrituras[0].endswith(":A1")
    assert [c.split(":")[-1] for c in escrituras[1:]] == ["A2", "A7", "A12"]
    assert len(sink.read_table(TABLE_FORECAST)) == 12


def test_el_release_real_se_parte_en_bloques_y_no_se_trunca(tmp_path):
    """5,772 filas en un solo `update` es la petición que la API corta por su cuenta."""
    assert CHUNK_ROWS > 0
    assert math.ceil(5772 / CHUNK_ROWS) >= 2, "un release real no cabe en una sola llamada"
    grande = pd.DataFrame({"a": [str(i) for i in range(5772)], "b": [""] * 5772})
    hoja = FakeSpreadsheet()
    GoogleSheetsTableSink(hoja, spreadsheet_id=ID_STAGING).write_table(TABLE_FORECAST, grande)
    bloques = [c for c in hoja.llamadas if c.startswith(f"update:{TABLE_FORECAST}:")]
    assert len(bloques) == 1 + math.ceil(5772 / CHUNK_ROWS)


def test_una_hoja_que_devuelve_otro_contenido_se_detecta(tmp_path):
    """El read-back es del sink, no del protocolo: aquí la hoja miente y aun así falla."""
    tablas = build_tables(_shard(tmp_path, filas=3))

    class HojaQueAltera(FakeSpreadsheet):
        def add_worksheet(self, *, title, rows, cols):
            ws = super().add_worksheet(title=title, rows=rows, cols=cols)
            original = ws.update

            def update(*, range_name, values, value_input_option):
                if range_name != "A1":
                    values = [[*fila[:-3], "999999999", *fila[-2:]] for fila in values]
                original(
                    range_name=range_name, values=values, value_input_option=value_input_option
                )

            ws.update = update  # type: ignore[method-assign]
            return ws

    sink = GoogleSheetsTableSink(HojaQueAltera(), spreadsheet_id=ID_STAGING)
    with pytest.raises(ArtifactValidationError, match="contenido distinto del escrito"):
        sink.write_table(TABLE_FORECAST, tablas.forecast)


# ── Errores de la API ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "operacion",
    [
        "worksheets",
        f"add_worksheet:{TABLE_FORECAST}",
        f"update:{TABLE_FORECAST}:A1",
        f"get_all_values:{TABLE_FORECAST}",
    ],
)
def test_cualquier_error_de_la_api_sale_tipado_y_sin_secretos(tmp_path, operacion):
    tablas = build_tables(_shard(tmp_path, filas=2))
    hoja = FakeSpreadsheet(falla=lambda op: op == operacion)
    sink = GoogleSheetsTableSink(hoja, spreadsheet_id=ID_STAGING)

    with pytest.raises(SheetsApiError) as exc:
        sink.write_table(TABLE_FORECAST, tablas.forecast)

    assert exc.value.operation
    assert "RuntimeError" in exc.value.detail, "no se oculta qué falló"
    assert ID_STAGING not in str(exc.value), "el id de la hoja no viaja en el mensaje"
    assert "«redactado»" in str(exc.value)


@pytest.mark.parametrize("operacion", ["clear", "resize", "update_title", "del_worksheet"])
def test_los_errores_de_mutacion_tambien(tmp_path, operacion):
    tablas = build_tables(_shard(tmp_path, filas=2))
    hoja = FakeSpreadsheet({TABLE_FORECAST: tablas.forecast})
    sink = GoogleSheetsTableSink(hoja, spreadsheet_id=ID_STAGING)
    hoja.falla = lambda op: op.startswith(operacion)

    with pytest.raises(SheetsApiError):
        if operacion == "update_title":
            sink.rename_table(TABLE_FORECAST, f"{TABLE_FORECAST}{SUFFIX_BACKUP}")
        elif operacion == "del_worksheet":
            sink.drop_table(TABLE_FORECAST)
        else:
            sink.write_table(TABLE_FORECAST, tablas.forecast)


# ── Las cinco tabs legacy ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("legacy", LEGACY_TABS)
def test_ninguna_mutacion_alcanza_una_tab_legacy(tmp_path, legacy):
    tablas = build_tables(_shard(tmp_path, filas=2))
    hoja = FakeSpreadsheet({legacy: pd.DataFrame([{"x": "cohorte neuro"}])})
    sink = GoogleSheetsTableSink(hoja, spreadsheet_id=ID_STAGING)

    for accion in (
        lambda: sink.write_table(legacy, tablas.forecast),
        lambda: sink.drop_table(legacy),
        lambda: sink.rename_table(legacy, TABLE_FORECAST),
        lambda: sink.rename_table(TABLE_FORECAST, legacy),
    ):
        with pytest.raises(ArtifactValidationError, match="namespace administrado|tab legacy"):
            accion()
    assert legacy in sink.list_tables()
    assert not [c for c in hoja.llamadas if c.startswith(("update:", "del_worksheet", "clear"))]


def test_la_promocion_completa_deja_intactas_las_cinco_legacy(tmp_path):
    tablas = build_tables(_shard(tmp_path, filas=3))
    legacy = {t: pd.DataFrame([{"x": t}]) for t in LEGACY_TABS}
    hoja = FakeSpreadsheet(legacy)
    sink = GoogleSheetsTableSink(hoja, spreadsheet_id=ID_STAGING)

    promote(sink, tablas)

    for nombre, frame in legacy.items():
        pd.testing.assert_frame_equal(
            sink.read_table(nombre), frame.astype(str), check_dtype=False
        )
    assert sorted(sink.list_tables()) == sorted([*LEGACY_TABS, TABLE_FORECAST, TABLE_RELEASES])


# ── El protocolo entero sobre el sink real simulado ────────────────────────────────────────────
def test_promocion_y_rollback_sobre_la_hoja(tmp_path):
    tablas = build_tables(_shard(tmp_path, filas=3))
    previa = pd.DataFrame([{"x": "la de antes"}])
    sink = _sink({TABLE_FORECAST: previa})

    resultado = promote(sink, tablas)
    assert resultado["status"] == "PROMOTED"
    assert len(sink.read_table(TABLE_FORECAST)) == len(tablas.forecast)
    assert f"{TABLE_FORECAST}{SUFFIX_PREVIOUS}" in sink.list_tables()
    assert not [t for t in sink.list_tables() if t.endswith((SUFFIX_NEXT, SUFFIX_BACKUP))]

    assert rollback(sink, [TABLE_FORECAST]) == [TABLE_FORECAST]
    pd.testing.assert_frame_equal(
        sink.read_table(TABLE_FORECAST), previa.astype(str), check_dtype=False
    )


@pytest.mark.parametrize(
    "operacion",
    [
        f"add_worksheet:{TABLE_RELEASES}{SUFFIX_NEXT}",
        f"update_title:{TABLE_FORECAST}->{TABLE_FORECAST}{SUFFIX_BACKUP}",
        f"update_title:{TABLE_FORECAST}{SUFFIX_NEXT}->{TABLE_FORECAST}",
        f"update_title:{TABLE_RELEASES}{SUFFIX_NEXT}->{TABLE_RELEASES}",
    ],
)
def test_las_fronteras_de_la_promocion_tambien_se_compensan_en_la_hoja(tmp_path, operacion):
    tablas = build_tables(_shard(tmp_path, filas=3))
    previas = {
        TABLE_FORECAST: pd.DataFrame([{"x": "vieja_f"}]),
        TABLE_RELEASES: tablas.releases.assign(verdict="PASS"),
    }
    hoja = FakeSpreadsheet(previas)
    sink = GoogleSheetsTableSink(hoja, spreadsheet_id=ID_STAGING)
    hoja.falla = lambda op: op == operacion

    with pytest.raises(SheetsApiError):
        promote(sink, tablas)

    hoja.falla = lambda op: False
    assert sorted(sink.list_tables()) == sorted(previas), "el namespace vuelve a la fotografía"
    for nombre, frame in previas.items():
        pd.testing.assert_frame_equal(
            sink.read_table(nombre), frame.astype(str), check_dtype=False
        )


def test_el_plan_de_promocion_no_se_desvia_del_protocolo(tmp_path):
    """Anti-deriva: el plan que se enseña tiene que ser lo que `promote` hace, no una copia."""
    from epiforecast.publication.tableau_adapter import MemorySink

    tablas = build_tables(_shard(tmp_path, filas=3))
    for inicial in (
        {},
        {TABLE_FORECAST: pd.DataFrame([{"x": 1}])},
        {TABLE_FORECAST: pd.DataFrame([{"x": 1}]), TABLE_RELEASES: tablas.releases},
    ):
        sink = MemorySink(inicial)
        plan = promotion_plan(sink, tablas)
        promote(sink, tablas)
        assert plan["steps"] == sink.operaciones, f"el plan se desvió con {sorted(inicial)}"

    # Segunda promoción: ya hay __previous que consolidar encima.
    sink = MemorySink({TABLE_FORECAST: pd.DataFrame([{"x": 1}])})
    promote(sink, tablas)
    plan = promotion_plan(sink, tablas)
    antes = len(sink.operaciones)
    promote(sink, tablas)
    assert plan["steps"] == sink.operaciones[antes:]


# ── Identidad de la hoja ───────────────────────────────────────────────────────────────────────
def test_sin_hoja_de_staging_no_se_opera():
    with pytest.raises(ArtifactValidationError, match=STAGING_ID_ENV):
        staging_ids({})


def test_staging_y_produccion_no_pueden_ser_la_misma():
    with pytest.raises(ArtifactValidationError, match="MISMA hoja"):
        staging_ids({STAGING_ID_ENV: ID_STAGING, PRODUCTION_ID_ENV: ID_STAGING})
    assert staging_ids({STAGING_ID_ENV: ID_STAGING, PRODUCTION_ID_ENV: ID_PRODUCCION}) == (
        ID_STAGING,
        ID_PRODUCCION,
    )


def test_el_namespace_del_sink_no_incluye_ninguna_legacy():
    assert not set(managed_tables()) & set(LEGACY_TABS)


def test_importar_el_modulo_no_autentica_ni_exige_gspread():
    """`gspread` no está instalado en este entorno y las pruebas pasan igual: eso es la prueba."""
    import importlib
    import importlib.util
    import sys

    assert "gspread" not in sys.modules
    modulo = importlib.import_module("epiforecast.publication.sheets_sink")
    from pathlib import Path

    origen = importlib.util.find_spec("epiforecast.publication.sheets_sink").origin
    assert origen
    for linea in Path(origen).read_text(encoding="utf-8").splitlines():
        if linea.startswith(("import gspread", "from gspread", "from google")):
            raise AssertionError(f"import de nivel de módulo que autenticaría: {linea!r}")
    assert hasattr(modulo, "open_spreadsheet")
    assert "gspread" not in sys.modules
