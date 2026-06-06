#!/usr/bin/env python
"""build_epibot_zoom.py — Re-llave los zoom_data_{neuro,dengue}.json de la galería a un índice
que el EpiBot resuelve con detectEntities (estado × sexo), y escribe ``zoom_series.json``.

La galería llavea por la ruta del PNG (``Depresión/Jalisco/Depresión_Jalisco_general.png``).
El EpiBot, en cambio, detecta padecimiento/estado/sexo con nombres canónicos sin acento. Este
script traduce cada serie a la clave ``pad|estado|sexo`` usando la MISMA normalización que el
``norm()`` del bot (minúsculas, sin acentos, no alfanumérico -> espacio, espacios colapsados),
de modo que el bot la busca sin mapeos frágiles. Así el zoom del EpiBot funciona por estado y
sexo (``zoom depresión jalisco``, ``zoom dengue yucatán mujeres``), no solo nacional.

Uso:
    python scripts/build_epibot_zoom.py --reports ../EpiForecast-IMSS-Dashboard/Reports \
        --out ../EpiForecast-IMSS-Dashboard/epibot
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import unicodedata


def _norm(text: str) -> str:
    """Réplica de ``norm()`` del EpiBot (entities.js): minúsculas, sin acentos (á→a, ñ→n),
    todo lo no alfanumérico a espacio, espacios colapsados."""
    t = text.lower()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = "".join(c if (c.isalnum() and c.isascii()) or c == " " else " " for c in t)
    return " ".join(t.split())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reports", required=True, help="Directorio Reports/ (con zoom_data_*.json)")
    ap.add_argument(
        "--out", required=True, help="Directorio epibot/ donde escribir zoom_series.json"
    )
    args = ap.parse_args()
    reports = Path(args.reports)

    series: dict[str, object] = {}
    n_files = 0
    for name in ("zoom_data_neuro.json", "zoom_data_dengue.json"):
        p = reports / name
        if not p.exists():
            continue
        n_files += 1
        data = json.loads(p.read_text(encoding="utf-8"))
        for key, payload in data.items():
            parts = key.split("/")
            if len(parts) != 3:
                continue
            pad_folder, estado_folder, fname = parts
            sexo = fname[: -len(".png")].split("_")[-1]  # general | hombres | mujeres
            estado = estado_folder.replace("_", " ")
            series[f"{_norm(pad_folder)}|{_norm(estado)}|{sexo}"] = payload

    out = Path(args.out) / "zoom_series.json"
    out.write_text(json.dumps(series, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"zoom_series.json: {len(series)} series de {n_files} archivos -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
