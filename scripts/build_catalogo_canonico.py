"""CLI: construye el catálogo canónico de producción (baseline E0-S1).

Escribe:
  * ``reports/ProdDetails/catalogo_canonico.csv``        (432 series, clave única)
  * ``reports/ProdDetails/catalogo_canonico_counts.json`` (conteos derivados + diagnóstico)

Sale con código != 0 si el catálogo no valida (duplicados o motores inválidos).

Uso: ``.venv/bin/python -m scripts.build_catalogo_canonico``
"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys

import pandas as pd

from epiforecast.catalog import CatalogCounts, build_production_catalog, validate_catalog
from epiforecast.utils.config import conf, logger


def escribe_salidas(df: pd.DataFrame, counts: CatalogCounts, out_dir: Path) -> tuple[Path, Path]:
    """Escribe el CSV y el JSON del catálogo en ``out_dir``.

    El JSON termina en salto de línea: el hook ``end-of-file-fixer`` lo exige y, si el
    generador no lo pone, lo confirmado deja de ser byte a byte lo sellado (P1, 2-sep-2026).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "catalogo_canonico.csv"
    json_path = out_dir / "catalogo_canonico_counts.json"
    df.to_csv(csv_path, index=False)
    json_path.write_text(
        json.dumps(asdict(counts), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return csv_path, json_path


def main() -> int:
    df, counts = build_production_catalog()
    problems = validate_catalog(df)

    out_dir = Path(conf["paths"]["reports"]) / "ProdDetails"
    csv_path, json_path = escribe_salidas(df, counts, out_dir)

    logger.info("Catálogo canónico: {} series productivas", counts.production_series_count)
    logger.info("  por cohorte: {}", counts.por_cohorte)
    logger.info("  por padecimiento: {}", counts.por_padecimiento)
    logger.info("  motor_dist Dengue: {}", counts.motor_dist.get("dengue"))
    logger.info("  gallery_item_count: {}", counts.gallery_item_count)
    logger.info("  diagnóstico tabla_333 Dengue (descartado): {}", counts.diagnostics)
    logger.success("-> {}", csv_path)
    logger.success("-> {}", json_path)

    if problems:
        for p in problems:
            logger.error("VALIDACIÓN: {}", p)
        return 1
    logger.success("Validación OK (sin duplicados ni motores inválidos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
