"""CLI: backfill de un padecimiento desde su cuadro en todos los boletines (EPIC 2).

Recorre ``data/raw_PDFs/*.pdf``, extrae el bloque del padecimiento con
``cuadro_extractor`` y escribe la serie larga + un manifiesto por-PDF con estado y
validaciones. NO toca el consolidado (eso es merge_cuadro).

Uso: .venv/bin/python -m scripts.extrae_cuadro --disease Obesidad [--group <grupo>] [--jobs 8]
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd

from epiforecast import registry
from epiforecast.data.extraction.cuadro_extractor import extract_cuadro_from_pdf
from epiforecast.utils.config import logger

CONSOLIDATED_COLS = [
    "Anio",
    "Semana",
    "Entidad",
    "Padecimiento",
    "Casos_semana",
    "Acumulado_hombres",
    "Acumulado_mujeres",
    "Acumulado_anio_anterior",
]


def _extract_one(task: tuple[str, str, str]) -> dict[str, Any] | str:
    """Un boletín; la excepción vuelve como texto para registrarla sin tumbar el pool."""
    pdf, group, disease_id = task
    try:
        return extract_cuadro_from_pdf(pdf, group, disease_id)
    except Exception as e:  # noqa: BLE001 - registrar y seguir
        return f"{type(e).__name__}: {e}"


def _results(tasks: list[tuple[str, str, str]], jobs: int) -> Iterator[dict[str, Any] | str]:
    if jobs <= 1:
        yield from map(_extract_one, tasks)
        return
    with ProcessPoolExecutor(max_workers=jobs) as ex:  # map conserva el orden: salida determinista
        yield from ex.map(_extract_one, tasks, chunksize=4)


def _empty_periods(kept: list[tuple[int, int]], like: pd.DataFrame, name: str) -> pd.DataFrame:
    """Filas vacías (sin casos ni acumulados) para las erratas que conservan su periodo.

    Las entidades salen de un boletín válido, con la misma canonicalización del extractor.
    """
    entidades = sorted(like["Entidad"].unique())
    rows = [
        {"Anio": y, "Semana": w, "Entidad": e, "Padecimiento": name}
        for y, w in kept
        for e in entidades
    ]
    return pd.DataFrame(rows).reindex(columns=CONSOLIDATED_COLS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disease", required=True, help="nombre o alias del padecimiento (registry)")
    ap.add_argument("--group", default=None, help="grupo de cuadro (default: el del registry)")
    ap.add_argument("--pdf-dir", default="data/raw_PDFs")
    ap.add_argument("--jobs", type=int, default=1, help="procesos en paralelo")
    args = ap.parse_args()

    d = registry.require(args.disease)
    args.group = args.group or d.extraction_group
    pdfs = sorted(Path(args.pdf_dir).glob("*.pdf"))
    logger.info("Backfill {} desde {} PDFs (grupo {})", d.data_name, len(pdfs), args.group)

    frames: list[pd.DataFrame] = []
    manifest: list[dict[str, Any]] = []
    kept: list[tuple[int, int]] = []  # erratas con keep_period: (año, semana) a emitir vacíos
    ok = 0
    tasks = [(str(pdf), args.group, d.id) for pdf in pdfs]
    for i, (pdf, r) in enumerate(zip(pdfs, _results(tasks, args.jobs), strict=True)):
        if isinstance(r, str):
            manifest.append({"file": pdf.name, "status": "error", "reason": r})
            continue
        if r.get("excluded"):
            status = "excluded"
            if r.get("keep_period"):
                kept.append((r["year"], r["week"]))
        else:
            status = "ok" if r["valid"] else ("no_page" if r["page"] is None else "invalid")
        manifest.append(
            {
                "file": pdf.name,
                "year": r["year"],
                "week": r["week"],
                "page": r["page"],
                "layout": r["layout"],
                "n_states": r["n_states"],
                "status": status,
                "reason": r["reason"],
            }
        )
        if r["valid"] and r["df"] is not None:
            frames.append(r["df"])
            ok += 1
        if (i + 1) % 100 == 0:
            logger.info("  ... {}/{} PDFs ({} ok)", i + 1, len(pdfs), ok)

    out_dir = Path("data/interim")
    out_dir.mkdir(parents=True, exist_ok=True)
    serie_path = out_dir / f"{d.slug}_boletin.csv"
    manifest_path = out_dir / f"{d.slug}_extraccion_manifest.csv"

    if frames and kept:
        frames.append(_empty_periods(kept, frames[0], d.data_name))
    if frames:
        serie = pd.concat(frames, ignore_index=True)[CONSOLIDATED_COLS]
        serie = serie.drop_duplicates(subset=["Anio", "Semana", "Entidad", "Padecimiento"])
        serie = serie.sort_values(["Anio", "Semana", "Entidad"]).reset_index(drop=True)
        serie.to_csv(serie_path, index=False, encoding="utf-8")
    pd.DataFrame(manifest).to_csv(manifest_path, index=False, encoding="utf-8")

    n_rows = len(frames) and len(pd.concat(frames)) or 0
    logger.success(
        "Backfill {}: {} boletines ok, {} filas -> {}", d.data_name, ok, n_rows, serie_path
    )
    logger.info("Manifiesto -> {}", manifest_path)
    bad = [m for m in manifest if m["status"] != "ok"]
    if bad:
        logger.warning("{} boletines NO ok: {}", len(bad), [m["file"] for m in bad][:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
