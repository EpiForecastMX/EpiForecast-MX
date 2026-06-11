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
from pathlib import Path
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

from epiforecast.data.extraction.dengue_extractor import extract_dengue_from_pdf  # noqa: E402
from epiforecast.utils.config import logger as log  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_PDFS_DIR = PROJECT_ROOT / "data" / "raw_PDFs"
DEFAULT_OUT = PROJECT_ROOT / "data" / "interim" / "dengue_boletin.csv"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "interim" / "dengue_extraccion_manifest.csv"

# Acumulado mínimo (H+M) de una serie Anio×Entidad para evaluar el ratio cumsum/acumulado
# en la auditoría (por debajo, las series casi-cero dan ratios inestables y ruidosos).
_MIN_ACUM_CONSISTENCIA = 50


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default="*.pdf", help="Glob de PDFs dentro de raw_PDFs/")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="CSV de salida (serie larga)")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="CSV de auditoría")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Solo parsea PDFs que aún no estén en el manifiesto y anexa a la serie "
        "existente (refresh semanal). Sin la bandera, reconstruye todo desde cero.",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    manifest_path = Path(args.manifest)
    pdfs = sorted(str(p) for p in RAW_PDFS_DIR.glob(args.pattern))
    if not pdfs:
        log.error("No se hallaron PDFs con patron {} en {}", args.pattern, RAW_PDFS_DIR)
        return 1

    # Modo incremental: reutiliza la serie + manifiesto previos y parsea SOLO los PDFs
    # que aún no figuran en el manifiesto (los boletines nuevos). Evita re-parsear ~648
    # boletines (la mayoría del esquema viejo que igual se descarta) en cada refresh.
    prev_serie: pd.DataFrame | None = None
    prev_manifest: pd.DataFrame | None = None
    if args.incremental and out_path.exists() and manifest_path.exists():
        prev_serie = pd.read_csv(out_path)
        prev_manifest = pd.read_csv(manifest_path)
        ya_vistos = set(prev_manifest["file"].astype(str))
        pdfs_nuevos = [p for p in pdfs if Path(p).name not in ya_vistos]
        log.info(
            "Incremental: {} PDFs nuevos de {} en disco ({} ya en el manifiesto).",
            len(pdfs_nuevos),
            len(pdfs),
            len(ya_vistos),
        )
        if not pdfs_nuevos:
            log.info("Sin boletines nuevos; serie Dengue sin cambios: {}", out_path)
            return 0
        pdfs = pdfs_nuevos
    log.info("Boletines a procesar: {}", len(pdfs))

    frames: list[pd.DataFrame] = []
    manifest_rows: list[dict[str, object]] = []

    for idx, path in enumerate(pdfs, start=1):
        name = Path(path).name
        try:
            res = extract_dengue_from_pdf(path)
        except Exception as exc:  # noqa: BLE001 — auditoría: nunca abortar el lote
            manifest_rows.append({"file": name, "status": "ERROR", "reason": str(exc)})
            log.warning("{:>3}/{} {} ERROR: {}", idx, len(pdfs), name, exc)
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
            "{:>3}/{} {} | p{} | {} W{} | estados={} | {}",
            idx,
            len(pdfs),
            name,
            res["page"],
            res["year"],
            res["week"],
            res["n_states"],
            status,
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_manifest = pd.DataFrame(manifest_rows)
    # Fusiona el manifiesto previo (incremental) con el de los boletines nuevos.
    if prev_manifest is not None:
        manifest = pd.concat([prev_manifest, new_manifest], ignore_index=True)
        manifest = manifest.drop_duplicates(subset=["file"], keep="last")
    else:
        manifest = new_manifest
    manifest.to_csv(manifest_path, index=False, encoding="utf-8")

    nuevos_df = pd.concat(frames, ignore_index=True) if frames else None
    if prev_serie is not None:
        # Anexa lo nuevo a la serie previa; (Anio,Semana,Entidad) repetidos -> gana lo nuevo.
        partes = [prev_serie] + ([nuevos_df] if nuevos_df is not None else [])
        final = pd.concat(partes, ignore_index=True)
        final = final.drop_duplicates(subset=["Anio", "Semana", "Entidad"], keep="last")
    elif nuevos_df is not None:
        final = nuevos_df
    else:
        log.warning("Ningun boletin paso la validacion. CSV de serie no generado.")
        _print_summary(new_manifest)
        return 0

    # Normaliza tipos: la serie previa viene de CSV y los frames nuevos del parser; al
    # concatenar, Anio/Semana pueden quedar como object y romper el sort/auditoría.
    final["Anio"] = final["Anio"].astype(int)
    final["Semana"] = final["Semana"].astype(int)
    final = _apply_source_corrections(final)
    final = final.sort_values(["Anio", "Semana", "Entidad"]).reset_index(drop=True)
    final.to_csv(out_path, index=False, encoding="utf-8")
    log.info("Serie Dengue generada: {} ({} filas)", out_path, len(final))
    log.info("Manifiesto: {}", args.manifest)
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
                "Corrección de fuente aplicada: {} {}-W{:02d} -> {}", entidad, anio, semana, cols
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
    log.info("  Duplicados (Anio,Semana,Entidad): {}", n_dups)
    if n_dups:
        log.warning("  ¡DUPLICADOS! {}", dups[dups > 1].head(10).to_dict())

    counts = df.groupby(["Anio", "Semana"]).Entidad.nunique()
    incompletas = counts[counts != 32]
    log.info("  Semanas con != 32 entidades: {}", len(incompletas))
    if len(incompletas):
        log.warning("  Semanas incompletas: {}", incompletas.head(10).to_dict())

    # Consistencia cumsum vs acumulado final (muestra de hasta 200 series Anio×Entidad).
    ratios = []
    for (_, _), g in df.groupby(["Anio", "Entidad"]):
        g = g.sort_values("Semana")
        acum = g.iloc[-1].Acumulado_hombres + g.iloc[-1].Acumulado_mujeres
        if acum > _MIN_ACUM_CONSISTENCIA:  # evita ratios inestables en series casi-cero
            ratios.append(g.Casos_semana.sum() / acum)
    if ratios:
        sr = pd.Series(ratios)
        fuera = int(((sr < 0.95) | (sr > 1.05)).sum())
        log.info(
            "  Consistencia cumsum/acumulado: mediana ratio={:.3f} | fuera de [0.95,1.05]: {}/{}",
            sr.median(),
            fuera,
            len(sr),
        )


def _print_summary(manifest: pd.DataFrame) -> None:
    n = len(manifest)
    ok = int((manifest["status"] == "OK").sum()) if "status" in manifest else 0
    log.info(
        "=== Resumen: {}/{} boletines validados ({:.1f}%) ===", ok, n, 100 * ok / n if n else 0
    )
    if "status" in manifest:
        for status, grp in manifest.groupby("status"):
            log.info("  {:<5}: {}", status, len(grp))


if __name__ == "__main__":
    raise SystemExit(main())
