# scripts/publish_gsheets.py
#
# Publica tableau_model.xlsx a Google Sheets.
# Cada hoja del Excel se escribe en su propia pestaña con el mismo nombre.
# Antes de publicar imprime un resumen de filas, columnas y celdas por tabla
# y el total acumulado para tener visibilidad del volumen que se enviará.

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from google.oauth2.service_account import Credentials
import gspread
from gspread.utils import rowcol_to_a1
import pandas as pd

from epiforecast.utils.config import conf, logger

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Hojas que se publican, en el orden en que aparecerán en Google Sheets
SHEET_NAMES = ["scaffold", "real", "forecast", "metricas", "entidades"]

TAB_META = "meta"


# ---------------------------------------------------------------------------
# Autenticación y utilidades de hoja
# ---------------------------------------------------------------------------


def _get_creds() -> Credentials:
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise ValueError("Falta GOOGLE_SERVICE_ACCOUNT_JSON (GitHub Secret con el JSON completo).")
    info = json.loads(sa_json)
    return Credentials.from_service_account_info(info, scopes=SCOPES)


def _get_or_create_ws(
    sh: gspread.Spreadsheet, title: str, rows: int = 1000, cols: int = 26
) -> gspread.Worksheet:
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def _clear_ws(ws: gspread.Worksheet) -> None:
    last_cell = rowcol_to_a1(ws.row_count, ws.col_count)
    ws.batch_clear([f"A1:{last_cell}"])


def _delete_legacy_tabs(sh: gspread.Spreadsheet, keep_titles: set[str]) -> None:
    """Elimina pestañas del esquema anterior (tableau_1, tableau_2, …) si aún existen."""
    for ws in sh.worksheets():
        if ws.title.startswith("tableau_") and ws.title not in keep_titles:
            logger.info("Eliminando pestaña obsoleta del esquema anterior: {}", ws.title)
            sh.del_worksheet(ws)


# ---------------------------------------------------------------------------
# Resumen de tamaño
# ---------------------------------------------------------------------------


def _print_summary(sheets: dict[str, pd.DataFrame]) -> int:
    """Imprime filas, columnas y celdas por tabla. Retorna el total de celdas."""
    sep = "-" * 52
    logger.info(sep)
    logger.info("  Tablas a publicar en Google Sheets")
    logger.info(sep)
    logger.info("  {:<12} {:>8}  {:>5}  {:>12}", "Tabla", "Filas", "Cols", "Celdas")
    logger.info(sep)

    total_cells = 0
    for name, df in sheets.items():
        rows, cols = df.shape
        # +1 fila por la cabecera de columnas
        cells = (rows + 1) * cols
        total_cells += cells
        logger.info("  {:<12} {:>8,}  {:>5}  {:>12,}", name, rows, cols, cells)

    logger.info(sep)
    logger.info("  {:<12} {:>8}  {:>5}  {:>12,}", "TOTAL", "", "", total_cells)
    logger.info(sep)
    return total_cells


# ---------------------------------------------------------------------------
# Publicación por tabla
# ---------------------------------------------------------------------------


def _publish_sheet(
    sh: gspread.Spreadsheet,
    tab_name: str,
    df: pd.DataFrame,
    chunk_size: int,
    idx: int,
    total_sheets: int,
) -> None:
    """Escribe un DataFrame en una pestaña de Google Sheets con progreso por chunk."""
    n_rows, n_cols = df.shape

    ws = _get_or_create_ws(sh, tab_name, rows=n_rows + 1, cols=n_cols)

    # Redimensiona si la hoja existente es más pequeña de lo necesario
    if ws.row_count < n_rows + 1 or ws.col_count < n_cols:
        ws.resize(rows=n_rows + 1, cols=n_cols)

    _clear_ws(ws)

    # Escribe cabecera
    ws.update(range_name="A1", values=[df.columns.tolist()])

    logger.info(
        "[{}/{}] '{}' | {:,} filas × {} cols = {:,} celdas",
        idx,
        total_sheets,
        tab_name,
        n_rows,
        n_cols,
        (n_rows + 1) * n_cols,
    )

    # Escribe datos en bloques para no exceder el tamaño máximo por petición
    last_reported_pct = -1
    for start in range(0, n_rows, chunk_size):
        end = min(start + chunk_size, n_rows)
        block = (
            df.iloc[start:end]
            .astype(object)
            .where(pd.notnull(df.iloc[start:end]), "")
            .values.tolist()
        )
        ws.update(range_name=f"A{start + 2}", values=block)

        pct = int((end / n_rows) * 100)
        # Reporta cada 10 puntos porcentuales para no saturar el log
        if pct // 10 != last_reported_pct // 10:
            logger.info("  '{}' -> {}% ({:,} / {:,} filas)", tab_name, pct, end, n_rows)
            last_reported_pct = pct

    logger.info("  '{}' listo.", tab_name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    spreadsheet_id = os.getenv("GSHEETS_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise ValueError("Falta GSHEETS_SPREADSHEET_ID (GitHub Variable o Secret).")

    xlsx_path = Path(conf["data"]["tableau"]).parent / "tableau_model.xlsx"
    if not xlsx_path.exists():
        raise FileNotFoundError(
            f"No existe tableau_model.xlsx en: {xlsx_path.resolve()} — corre 'make tableau' primero."
        )

    # Carga todas las hojas del Excel.
    # Las columnas datetime se convierten a string (YYYY-MM-DD) porque la API
    # de Google Sheets no acepta objetos Timestamp en la serialización JSON.
    logger.info("Leyendo Excel: {}", xlsx_path)
    sheets: dict[str, pd.DataFrame] = {}
    for name in SHEET_NAMES:
        df = pd.read_excel(xlsx_path, sheet_name=name)
        for col in df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns:
            df[col] = df[col].dt.strftime("%Y-%m-%d")
        sheets[name] = df

    # Resumen de tamaño antes de empezar
    total_cells = _print_summary(sheets)

    # Autenticación y apertura del Spreadsheet
    creds = _get_creds()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(spreadsheet_id)

    chunk_size = int(os.getenv("GSHEETS_CHUNK_SIZE", "5000"))
    total_sheets = len(SHEET_NAMES)

    # Publica cada tabla en su propia pestaña
    for idx, name in enumerate(SHEET_NAMES, start=1):
        _publish_sheet(
            sh,
            tab_name=name,
            df=sheets[name],
            chunk_size=chunk_size,
            idx=idx,
            total_sheets=total_sheets,
        )

    # Limpia pestañas del esquema anterior si aún existen
    _delete_legacy_tabs(sh, keep_titles=set(SHEET_NAMES) | {TAB_META})

    # Actualiza la pestaña de metadatos con el resumen de esta publicación
    ws_meta = _get_or_create_ws(sh, TAB_META, rows=20, cols=5)
    ts = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S %Z")

    meta_rows: list[list] = [
        ["campo", "valor"],
        ["updated", ts],
        ["xlsx_path", str(xlsx_path)],
        ["chunk_size", str(chunk_size)],
        ["total_celdas", f"{total_cells:,}"],
        [],
        ["tabla", "filas", "cols", "celdas"],
    ]
    for name, df in sheets.items():
        rows, cols = df.shape
        meta_rows.append([name, rows, cols, (rows + 1) * cols])

    ws_meta.clear()
    ws_meta.update(range_name="A1", values=meta_rows)

    logger.success(
        "Publicado OK | sheet_id={} | pestañas={} | total_celdas={:,} | {}",
        spreadsheet_id,
        SHEET_NAMES,
        total_cells,
        ts,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
