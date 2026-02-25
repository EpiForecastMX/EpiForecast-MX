# scripts/publish_gsheets.py
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

from epiforecast.utils.config import conf, logger

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TAB_TABLEAU = "tableau"
TAB_META = "meta"


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
        return sh.add_worksheet(title=title, rows=str(rows), cols=str(cols))


def main() -> int:
    spreadsheet_id = os.getenv("GSHEETS_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise ValueError("Falta GSHEETS_SPREADSHEET_ID (GitHub Variable o Secret).")

    csv_path = Path(conf["data"]["tableau"])
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No existe tableau.csv en: {csv_path.resolve()} (corre make tableau primero)."
        )

    df = pd.read_csv(csv_path)
    n_rows, n_cols = df.shape
    logger.info(
        "Leído CSV: {} | filas={} cols={} | celdas={}",
        csv_path,
        n_rows,
        n_cols,
        n_rows * n_cols,
    )

    creds = _get_creds()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(spreadsheet_id)

    # 1) Tab "tableau": overwrite total (por chunks)
    ws_tableau = _get_or_create_ws(sh, TAB_TABLEAU)

    # Asegura tamaño de grid (header + datos)
    needed_rows = n_rows + 1  # +1 por header
    needed_cols = n_cols
    if ws_tableau.row_count < needed_rows or ws_tableau.col_count < needed_cols:
        logger.info(
            "Resize sheet '{}' de {}x{} -> {}x{}",
            TAB_TABLEAU,
            ws_tableau.row_count,
            ws_tableau.col_count,
            needed_rows,
            needed_cols,
        )
        ws_tableau.resize(rows=needed_rows, cols=needed_cols)

    ws_tableau.clear()

    # Header
    ws_tableau.update(range_name="A1", values=[df.columns.tolist()])

    # Chunks
    chunk_size = int(os.getenv("GSHEETS_CHUNK_SIZE", "5000"))
    total_rows = len(df)
    last_pct = -1

    for start in range(0, total_rows, chunk_size):
        end = min(start + chunk_size, total_rows)

        block = (
            df.iloc[start:end]
            .astype(object)
            .where(pd.notnull(df), "")
            .values.tolist()
        )

        # fila 1 es header
        row1 = start + 2
        row2 = end + 1

        ws_tableau.update(range_name=f"A{row1}", values=block)

        pct = int((end / total_rows) * 100)
        if pct != last_pct:
            logger.info(
                "Publicando tableau -> {}% | filas {}-{} de {}",
                pct,
                row1,
                row2,
                total_rows + 1,
            )
            last_pct = pct

    # 2) Tab "meta": updated + timestamp (America/Los_Angeles)
    ws_meta = _get_or_create_ws(sh, TAB_META, rows=50, cols=10)
    ts = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    ws_meta.update(range_name="A1:B1", values=[["updated", ts]])

    logger.success("Publicado a Google Sheets OK | sheet_id={} | meta B1={}", spreadsheet_id, ts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())