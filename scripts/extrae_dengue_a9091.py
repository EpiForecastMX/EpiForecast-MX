#!/usr/bin/env python
"""extrae_dengue_a9091.py — Serie histórica de Dengue OMS 1997 (A90/A91), 2014→2018-W26.

Extrae Dengue **confirmado por sexo** de los boletines con el esquema viejo (A90/A91, por
estatus de caso) usando el parser posicional ``dengue_historico_a9091``. Es una serie de
**contexto/EDA SEPARADA** (``Padecimiento = "Dengue_A90A91"``): NO se mergea al consolidado
de producción porque cambia la taxonomía (A90/A91 vs A97.x de 2018+) y la definición (solo
confirmados). Sirve para análisis histórico, no para entrenar los 4 motores.

Cada boletín se valida contra el renglón TOTAL impreso; solo se emiten las semanas válidas y
el resto se reporta en un manifiesto.

Uso:
    python scripts/extrae_dengue_a9091.py
    python scripts/extrae_dengue_a9091.py --pattern "201[4-7]_*"

Salidas:
    data/interim/dengue_a90a91_historico.csv          # serie larga validada (por sexo + total)
    data/interim/dengue_a90a91_manifest.csv           # auditoría por boletín
    data/interim/dengue_a90a91_nacional.csv           # serie TOTAL nacional semanal (contexto)
"""

from __future__ import annotations

import argparse
from pathlib import Path
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

from epiforecast.data.extraction.dengue_historico_a9091 import (  # noqa: E402
    extract_a9091_from_pdf,
)
from epiforecast.utils.config import logger as log  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW_PDFS_DIR = ROOT / "data" / "raw_PDFs"
OUT = ROOT / "data" / "interim" / "dengue_a90a91_historico.csv"
MANIFEST = ROOT / "data" / "interim" / "dengue_a90a91_manifest.csv"
NACIONAL = ROOT / "data" / "interim" / "dengue_a90a91_nacional.csv"
# Esquema A90/A91 por entidad: 2014 → 2018-W26 (después es A97.x, otro extractor).
_PATTERN_DEFAULT = "201[4-8]_sem*.pdf"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default=_PATTERN_DEFAULT, help="Glob de PDFs en raw_PDFs/")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    pdfs = sorted(str(p) for p in RAW_PDFS_DIR.glob(args.pattern))
    if not pdfs:
        log.error("No se hallaron PDFs con patron {}", args.pattern)
        return 1
    log.info("Boletines a procesar (A90/A91): {}", len(pdfs))

    frames: list[pd.DataFrame] = []
    manifest: list[dict[str, object]] = []
    for path in pdfs:
        name = Path(path).name
        try:
            res = extract_a9091_from_pdf(path)
        except Exception as exc:  # noqa: BLE001 — auditoría: nunca abortar el lote
            manifest.append({"file": name, "status": "ERROR", "reason": str(exc)[:80]})
            continue
        df = res["df"]
        valid = bool(res["valid"])
        manifest.append(
            {
                "file": name,
                "status": "OK" if valid else "SKIP",
                "page": res["page"],
                "year": res["year"],
                "week": res["week"],
                "n_states": res["n_states"],
                "absdiff": res["absdiff"],
                "reason": res["reason"],
            }
        )
        if isinstance(df, pd.DataFrame) and valid:
            frames.append(df)

    pd.DataFrame(manifest).to_csv(MANIFEST, index=False, encoding="utf-8")
    ok = sum(1 for m in manifest if m.get("status") == "OK")
    log.info("=== A90/A91: {}/{} boletines validados ===", ok, len(pdfs))

    if not frames:
        log.warning("Ninguna semana valida. No se genero serie.")
        return 0

    serie = pd.concat(frames, ignore_index=True)
    serie["incrementos_total_confirmado"] = serie["Acumulado_hombres"] + serie["Acumulado_mujeres"]
    serie = serie.sort_values(["Anio", "Semana", "Entidad"]).reset_index(drop=True)
    serie.to_csv(args.out, index=False, encoding="utf-8")
    log.info("Serie A90/A91 por entidad: {} ({} filas)", args.out, len(serie))

    # Serie TOTAL nacional semanal (suma de entidades) para contexto/EDA.
    nac = (
        serie.groupby(["Anio", "Semana"], as_index=False)[
            ["Acumulado_hombres", "Acumulado_mujeres", "incrementos_total_confirmado"]
        ]
        .sum()
        .rename(columns={"incrementos_total_confirmado": "confirmado_acum_nacional"})
    )
    nac.to_csv(NACIONAL, index=False, encoding="utf-8")
    log.info("Serie TOTAL nacional A90/A91: {} ({} semanas)", NACIONAL, len(nac))
    log.info("Manifiesto: {}", MANIFEST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
