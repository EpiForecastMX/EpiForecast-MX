"""C7.6-ADAPTERS-B0 — sink de Google Sheets para el namespace ``runner_``.

Es la implementación real del `TableSink` que hasta ahora sólo tenía un doble en memoria. Sigue sin
autenticar nada: el `Spreadsheet` se **inyecta**, de modo que las pruebas usan un falso y la
autenticación vive en un único borde explícito (`open_spreadsheet`), que este módulo no llama.

Tres cosas que no son detalle:

* **Nunca se importa `gspread` al importar este módulo.** La dependencia está declarada pero puede no
  estar instalada, y aunque lo esté, importar un cliente no debe ser el momento en que un proceso
  adquiere credenciales.
* **Las cinco tabs legacy son intocables.** Cualquier mutación fuera del namespace administrado se
  rechaza antes de llamar a la API; no se confía en que el llamador pase el nombre correcto.
* **Google Sheets recorta las celdas vacías del final.** Un release point-only tiene ``yhat_lower`` y
  ``yhat_upper`` vacías, que son justo las últimas columnas: leer sin repoblar devolvería filas más
  cortas que la cabecera y el read-back fallaría por una diferencia que no existe en el dato. Se
  repuebla explícitamente, y así los conteos y los strings vacíos se conservan.

Este módulo NO reutiliza nada de ``scripts/publish_gsheets.py``: ese publicador borra las tabs que no
estén en su lista, que sobre una hoja compartida es exactamente lo que no puede pasar aquí.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import re
from typing import Any, TypeVar

import pandas as pd

from epiforecast.runner.artifact_identity import require

from .tableau_adapter import (
    TABLES,
    TableauAdapterError,
    canonical_frame,
    managed_tables,
)

# Variables de entorno. La de staging es OTRA que la productiva, y el CLI exige que difieran.
STAGING_ID_ENV = "C7_TABLEAU_STAGING_SPREADSHEET_ID"
PRODUCTION_ID_ENV = "GSHEETS_SPREADSHEET_ID"
SERVICE_ACCOUNT_ENV = "GOOGLE_SERVICE_ACCOUNT_JSON"

# Las cinco tabs de la cadena viva. Ninguna operación de este sink puede tocarlas.
LEGACY_TABS: tuple[str, ...] = ("scaffold", "real", "forecast", "metricas", "entidades")

# Filas por llamada de escritura. 5,772 filas en un solo `update` es una petición que la API corta;
# el chunking es explícito para que el corte sea nuestro y no suyo.
CHUNK_ROWS = 500

SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)

T = TypeVar("T")


class SheetsApiError(TableauAdapterError):
    """Fallo de la API de hojas, tipado.

    Lleva la operación y la respuesta —sin eso no se puede diagnosticar nada— y **nunca** el id de la
    hoja ni credenciales: un traceback termina en un log, y un log se comparte.
    """

    def __init__(
        self, operacion: str, causa: BaseException, *, sensibles: Sequence[str] = ()
    ) -> None:
        detalle = _redactar(f"{type(causa).__name__}: {causa}", sensibles)
        super().__init__(f"Google Sheets · {operacion}: {detalle}")
        self.operation = operacion
        self.detail = detalle


def _redactar(texto: str, sensibles: Sequence[str]) -> str:
    """Sustituye cualquier valor sensible que la excepción de la API haya arrastrado."""
    salida = texto
    for valor in sensibles:
        if valor:
            salida = salida.replace(valor, "«redactado»")
    # Un id de hoja de cálculo que llegue por otra vía tampoco pasa.
    return re.sub(r"[A-Za-z0-9_-]{40,}", "«redactado»", salida)


class GoogleSheetsTableSink:
    """`TableSink` sobre un `gspread.Spreadsheet` inyectado.

    El namespace administrado limita QUÉ se puede mutar; la hoja puede tener lo que quiera, y este
    sink lo lista para poder inspeccionarlo, pero no lo escribe ni lo borra.
    """

    def __init__(
        self,
        spreadsheet: Any,
        *,
        namespace: Sequence[str] = TABLES,
        chunk_rows: int = CHUNK_ROWS,
        spreadsheet_id: str | None = None,
    ) -> None:
        require(chunk_rows > 0, "sheets_sink: chunk_rows tiene que ser positivo")
        self._hoja = spreadsheet
        self._gestionadas = managed_tables(namespace)
        self._chunk = int(chunk_rows)
        # Se guarda sólo para redactarlo de los mensajes de error, nunca para mostrarlo.
        self._sensibles = tuple(v for v in (spreadsheet_id,) if v)
        prohibidas = [t for t in self._gestionadas if t in LEGACY_TABS]
        require(not prohibidas, f"sheets_sink: el namespace pisa tabs legacy {prohibidas}")

    # ── infraestructura ──────────────────────────────────────────────────────────────────────
    def _llamar(self, operacion: str, fn: Callable[[], T]) -> T:
        try:
            return fn()
        except SheetsApiError:
            raise
        except Exception as exc:  # noqa: BLE001 — la API lanza de todo; se tipa aquí
            raise SheetsApiError(operacion, exc, sensibles=self._sensibles) from exc

    def _exigir_administrada(self, nombre: str, operacion: str) -> None:
        require(
            nombre in self._gestionadas,
            f"sheets_sink: {operacion} sobre {nombre!r}, fuera del namespace administrado",
        )
        require(
            nombre not in LEGACY_TABS,
            f"sheets_sink: {operacion} sobre la tab legacy {nombre!r}",
        )

    def _worksheet(self, nombre: str) -> Any | None:
        for ws in self._llamar("worksheets", self._hoja.worksheets):
            if ws.title == nombre:
                return ws
        return None

    # ── protocolo TableSink ──────────────────────────────────────────────────────────────────
    def list_tables(self) -> list[str]:
        """Todas las tabs de la hoja. Inventariar es read-only y tiene que ver el conjunto entero."""
        return sorted(ws.title for ws in self._llamar("worksheets", self._hoja.worksheets))

    def read_table(self, name: str) -> pd.DataFrame | None:
        ws = self._worksheet(name)
        if ws is None:
            return None
        valores = self._llamar(f"get_all_values({name})", ws.get_all_values)
        if not valores:
            return None
        cabecera = list(valores[0])
        ancho = len(cabecera)
        require(ancho > 0, f"{name}: la tab no tiene cabecera")
        # Repoblado explícito: la API recorta las celdas vacías de la derecha (ver el docstring).
        filas = [list(fila) + [""] * (ancho - len(fila)) for fila in valores[1:]]
        largas = [i for i, fila in enumerate(filas) if len(fila) > ancho]
        require(not largas, f"{name}: filas {largas[:3]} con más columnas que la cabecera")
        return pd.DataFrame(filas, columns=cabecera, dtype=str)

    def write_table(self, name: str, frame: pd.DataFrame) -> None:
        """Escribe y **relee** la tab entera. Escribir sin verificar es afirmar."""
        self._exigir_administrada(name, "write_table")
        datos = frame.astype(str)
        cabecera = [list(datos.columns)]
        filas = datos.values.tolist()

        ws = self._worksheet(name)
        if ws is None:
            ws = self._llamar(
                f"add_worksheet({name})",
                lambda: self._hoja.add_worksheet(
                    title=name, rows=max(len(filas) + 1, 2), cols=max(len(datos.columns), 1)
                ),
            )
        else:
            self._llamar(f"clear({name})", ws.clear)
            self._llamar(
                f"resize({name})",
                lambda: ws.resize(rows=max(len(filas) + 1, 2), cols=max(len(datos.columns), 1)),
            )

        self._llamar(
            f"update({name}, cabecera)",
            lambda: ws.update(range_name="A1", values=cabecera, value_input_option="RAW"),
        )
        for inicio in range(0, len(filas), self._chunk):
            self._escribir_bloque(ws, name, f"A{inicio + 2}", filas[inicio : inicio + self._chunk])
        self._verificar(name, datos)

    def _escribir_bloque(self, ws: Any, name: str, celda: str, bloque: list[list[Any]]) -> None:
        """Un bloque por llamada: el corte lo elegimos nosotros, no el límite de la petición."""
        self._llamar(
            f"update({name}, {celda})",
            lambda: ws.update(range_name=celda, values=bloque, value_input_option="RAW"),
        )

    def _verificar(self, name: str, esperado: pd.DataFrame) -> None:
        leido = self.read_table(name)
        require(leido is not None, f"{name}: la tab no existe tras escribirla")
        assert leido is not None  # noqa: S101 — para mypy
        if canonical_frame(leido) != canonical_frame(esperado):
            raise TableauAdapterError(
                f"{name}: la hoja devolvió un contenido distinto del escrito "
                f"({len(leido)} filas × {len(leido.columns)} columnas frente a "
                f"{len(esperado)} × {len(esperado.columns)})"
            )

    def rename_table(self, origen: str, destino: str) -> None:
        self._exigir_administrada(origen, "rename_table")
        self._exigir_administrada(destino, "rename_table")
        ws = self._worksheet(origen)
        require(ws is not None, f"sheets_sink: no existe la tab {origen}")
        require(
            self._worksheet(destino) is None,
            f"sheets_sink: {destino} ya existe; renombrar encima perdería su contenido",
        )
        assert ws is not None  # noqa: S101 — para mypy
        self._llamar(f"update_title({origen}->{destino})", lambda: ws.update_title(destino))

    def drop_table(self, name: str) -> None:
        self._exigir_administrada(name, "drop_table")
        ws = self._worksheet(name)
        if ws is None:
            return
        self._llamar(f"del_worksheet({name})", lambda: self._hoja.del_worksheet(ws))


def staging_ids(entorno: dict[str, str] | None = None) -> tuple[str, str | None]:
    """Id de staging y de producción, validados. Sin staging declarado no hay nada que abrir.

    Que el id de staging **no sea** el productivo no es una precaución de estilo: son la misma clase
    de identificador, y una confusión de variable escribiría las tablas del runner en la hoja que
    alimenta el Tableau público.
    """
    env = dict(os.environ if entorno is None else entorno)
    staging = (env.get(STAGING_ID_ENV) or "").strip()
    produccion = (env.get(PRODUCTION_ID_ENV) or "").strip() or None
    require(bool(staging), f"falta {STAGING_ID_ENV}: sin hoja de staging no se opera")
    require(
        staging != produccion,
        f"{STAGING_ID_ENV} y {PRODUCTION_ID_ENV} apuntan a la MISMA hoja",
    )
    return staging, produccion


def open_spreadsheet(spreadsheet_id: str) -> Any:
    """Único borde que autentica. No se llama al importar, ni en modo dry-run, ni en las pruebas."""
    try:
        from google.oauth2.service_account import Credentials  # noqa: PLC0415
        import gspread  # noqa: PLC0415 — import perezoso: importar no puede autenticar
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise SheetsApiError("import", exc) from exc

    bruto = os.getenv(SERVICE_ACCOUNT_ENV)
    require(bool(bruto), f"falta {SERVICE_ACCOUNT_ENV} en el entorno")
    import json  # noqa: PLC0415

    try:
        credenciales = Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
            json.loads(bruto or "{}"), scopes=list(SCOPES)
        )
        cliente = gspread.authorize(credenciales)
        return cliente.open_by_key(spreadsheet_id)
    except Exception as exc:  # noqa: BLE001 — se tipa y se redacta
        raise SheetsApiError("open_by_key", exc, sensibles=(spreadsheet_id, bruto or "")) from exc
