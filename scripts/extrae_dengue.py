#!/usr/bin/env python
"""extrae_dengue.py — Extrae la serie de Dengue (agregada) de los boletines SINAVE.

Recorre los PDFs de ``data/raw_PDFs/``, localiza la tabla de Dengue por entidad
(esquema OMS 2009, CIE A97.0/A97.1/A97.2), agrega las tres severidades en un único
padecimiento ``"Dengue"`` y emite un CSV con el mismo esquema que
``dataset_boletin_epidemiologico.csv``.

Cada boletín se valida comparando la suma por categoría de las 32 entidades contra el
renglón TOTAL impreso. Solo se emiten filas de boletines que pasan la validación; el
resto se reporta en un manifiesto para inspección (típicamente boletines pre-2019 con el
esquema OMS 1997 A90/A91, no soportado).

Uso:
    python scripts/extrae_dengue.py                       # todos los PDFs de data/raw_PDFs
    python scripts/extrae_dengue.py --pattern "202[3-6]_*"  # subconjunto por glob
    python scripts/extrae_dengue.py --out data/interim/dengue_boletin.csv

Salidas:
    data/interim/dengue_boletin.csv            # serie larga validada
    data/interim/dengue_extraccion_manifest.csv  # auditoría por boletín
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

from epiforecast.data.extraction.dengue_extractor import extract_dengue_from_pdf  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_PDFS_DIR = PROJECT_ROOT / "data" / "raw_PDFs"
DEFAULT_OUT = PROJECT_ROOT / "data" / "interim" / "dengue_boletin.csv"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "interim" / "dengue_extraccion_manifest.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("extrae_dengue")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default="*.pdf", help="Glob de PDFs dentro de raw_PDFs/")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="CSV de salida (serie larga)")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="CSV de auditoría")
    args = parser.parse_args()

    pdfs = sorted(str(p) for p in RAW_PDFS_DIR.glob(args.pattern))
    if not pdfs:
        log.error("No se hallaron PDFs con patron %s en %s", args.pattern, RAW_PDFS_DIR)
        return 1
    log.info("Boletines a procesar: %d", len(pdfs))

    frames: list[pd.DataFrame] = []
    manifest_rows: list[dict[str, object]] = []

    for idx, path in enumerate(pdfs, start=1):
        name = Path(path).name
        try:
            res = extract_dengue_from_pdf(path)
        except Exception as exc:  # noqa: BLE001 — auditoría: nunca abortar el lote
            manifest_rows.append({"file": name, "status": "ERROR", "reason": str(exc)})
            log.warning("%3d/%d %s ERROR: %s", idx, len(pdfs), name, exc)
            continue

        df = res["df"]
        valid = bool(res["valid"])
        status = "OK" if (df is not None and valid) else "SKIP"
        manifest_rows.append(
            {
                "file": name,
                "status": status,
                "page": res["page"],
                "year": res["year"],
                "week": res["week"],
                "n_states": res["n_states"],
                "valid": valid,
                "absdiff": res["absdiff"],
                "reason": res["reason"],
            }
        )
        if df is not None and valid:
            frames.append(df)
        log.info(
            "%3d/%d %s | p%s | %s W%s | estados=%s | %s",
            idx,
            len(pdfs),
            name,
            res["page"],
            res["year"],
            res["week"],
            res["n_states"],
            status,
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(args.manifest, index=False, encoding="utf-8")

    if not frames:
        log.warning("Ningun boletin paso la validacion. CSV de serie no generado.")
        _print_summary(manifest)
        return 0

    final = pd.concat(frames, ignore_index=True)
    final = _apply_source_corrections(final)
    final = final.sort_values(["Anio", "Semana", "Entidad"]).reset_index(drop=True)
    final.to_csv(out_path, index=False, encoding="utf-8")
    log.info("Serie Dengue generada: %s (%d filas)", out_path, len(final))
    log.info("Manifiesto: %s", args.manifest)
    _print_summary(manifest)
    _audit_series(final)
    return 0


# Correcciones de errores de fuente conocidos del boletín SINAVE (typos imposibles).
# Keyed por (Anio, Semana, Entidad) → columnas a corregir. Documentar SIEMPRE el porqué.
#   Zacatecas 2024-W41: el boletín imprime A97.1 acumulado H=14,522 / M=17,657 (imposible
#   para un estado de incidencia casi nula). El acumulado correcto, consistente con el
#   Casos_semana validado (W41=19, W42=10) y monótono con los vecinos (W40 33/31, W42 46/47),
#   es H=42 / M=41 (incremento W41 = 9+10 = 19; W42 = 4+6 = 10).
_SOURCE_CORRECTIONS: dict[tuple[int, int, str], dict[str, int]] = {
    (2024, 41, "Zacatecas"): {"Acumulado_hombres": 42, "Acumulado_mujeres": 41},
}


def _apply_source_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica correcciones puntuales de errores de fuente del boletín (ver dict)."""
    df = df.copy()
    for (anio, semana, entidad), cols in _SOURCE_CORRECTIONS.items():
        mask = (
            (df["Anio"] == anio)
            & (df["Semana"].astype(int) == semana)
            & (df["Entidad"] == entidad)
        )
        n = int(mask.sum())
        if n:
            for col, val in cols.items():
                df.loc[mask, col] = val
            log.info(
                "Corrección de fuente aplicada: %s %d-W%02d -> %s", entidad, anio, semana, cols
            )
    return df


def _audit_series(df: pd.DataFrame) -> None:
    """Auditoría a nivel de dataset: duplicados, completitud y consistencia interna.

    - Duplicados: una (Anio, Semana, Entidad) no debe repetirse.
    - Completitud: cada (Anio, Semana) válida debe traer 32 entidades.
    - Consistencia: cumsum semanal por (Anio, Entidad) ~ acumulado (H+M) de la última
      semana (verificación independiente del orden de columnas; ratio ~1.0).
    """
    log.info("=== Auditoría de la serie ===")
    dups = df.groupby(["Anio", "Semana", "Entidad"]).size()
    n_dups = int((dups > 1).sum())
    log.info("  Duplicados (Anio,Semana,Entidad): %d", n_dups)
    if n_dups:
        log.warning("  ¡DUPLICADOS! %s", dups[dups > 1].head(10).to_dict())

    counts = df.groupby(["Anio", "Semana"]).Entidad.nunique()
    incompletas = counts[counts != 32]
    log.info("  Semanas con != 32 entidades: %d", len(incompletas))
    if len(incompletas):
        log.warning("  Semanas incompletas: %s", incompletas.head(10).to_dict())

    # Consistencia cumsum vs acumulado final (muestra de hasta 200 series Anio×Entidad).
    ratios = []
    for (_, _), g in df.groupby(["Anio", "Entidad"]):
        g = g.sort_values("Semana")
        acum = g.iloc[-1].Acumulado_hombres + g.iloc[-1].Acumulado_mujeres
        if acum > 50:  # evita ratios inestables en series casi-cero
            ratios.append(g.Casos_semana.sum() / acum)
    if ratios:
        sr = pd.Series(ratios)
        fuera = int(((sr < 0.95) | (sr > 1.05)).sum())
        log.info(
            "  Consistencia cumsum/acumulado: mediana ratio=%.3f | fuera de [0.95,1.05]: %d/%d",
            sr.median(),
            fuera,
            len(sr),
        )


def _print_summary(manifest: pd.DataFrame) -> None:
    n = len(manifest)
    ok = int((manifest["status"] == "OK").sum()) if "status" in manifest else 0
    log.info(
        "=== Resumen: %d/%d boletines validados (%.1f%%) ===", ok, n, 100 * ok / n if n else 0
    )
    if "status" in manifest:
        for status, grp in manifest.groupby("status"):
            log.info("  %-5s: %d", status, len(grp))


if __name__ == "__main__":
    raise SystemExit(main())
