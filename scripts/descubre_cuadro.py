"""Discovery del cuadro de un padecimiento a través de todo el corpus de PDFs (read-only).

Fingerprint por PDF del "CUADRO 14.1 Trastornos de la Nutrición" (Obesidad E66):
página, layout (3col_noprev/4col_prev), etiquetas de sexo (M/F vs H/M), variante de
entidad (Distrito Federal vs Ciudad de México) y si hay renglón TOTAL. Fija las
fronteras `years`/`backend` de ``config/data/cuadros.yaml`` antes de comprometer el
extractor (EPIC 2). NO toca el consolidado.

Uso: ``.venv/bin/python -m scripts.descubre_cuadro --group trastornos_nutricion``
Salida: ``data/interim/cuadro_<group>_discovery.csv`` + resumen impreso.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re
import subprocess

# Anclas por grupo (EPIC 2 las mueve a config/data/cuadros.yaml).
GROUPS = {
    "trastornos_nutricion": {
        "anchors": ("e66", "obesidad"),
        "state_markers": ("aguascalientes", "zacatecas"),
    },
}

_WEEK_RE = re.compile(r"(\d{4})_sem(\d{2})", re.IGNORECASE)


def _pdftotext(pdf: Path) -> str:
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"],
            capture_output=True,
            timeout=60,
            check=False,
        )
        return out.stdout.decode("utf-8", "replace")
    except Exception:
        return ""


def _year_week(pdf: Path) -> tuple[int | None, int | None]:
    m = _WEEK_RE.search(pdf.name)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _fingerprint(text: str, anchors: tuple[str, ...], markers: tuple[str, ...]) -> dict:
    low = text.lower()
    has_e66 = "e66" in low
    if not (all(a in low for a in anchors) and any(m in low for m in markers)):
        return {"page_found": False}
    # ventana alrededor del ancla E66
    idx = low.find("obesidad")
    window = text[max(0, idx - 400) : idx + 1200]
    wl = window.lower()
    n_acum = wl.count("acum")
    # 4col trae dos años (año en curso + anterior) por padecimiento; 3col uno.
    years_in_window = len(set(re.findall(r"\b20\d{2}\b", window)))
    layout = "4col_prev" if (n_acum >= 3 and years_in_window >= 2) else "3col_noprev"
    sex_label = (
        "H/M"
        if re.search(r"\bH\b.*\bM\b", window)
        else ("M/F" if re.search(r"\bM\b.*\bF\b", window) else "?")
    )
    entity_variant = (
        "CDMX"
        if "ciudad de méxico" in low or "ciudad de mexico" in low
        else ("DF" if "distrito federal" in low else "?")
    )
    total_found = "total" in wl
    return {
        "page_found": True,
        "has_e66": has_e66,
        "layout_fingerprint": layout,
        "n_acum": n_acum,
        "years_in_window": years_in_window,
        "sex_label": sex_label,
        "entity_variant": entity_variant,
        "total_row_found": total_found,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="trastornos_nutricion", choices=list(GROUPS))
    ap.add_argument("--pdf-dir", default="data/raw_PDFs")
    args = ap.parse_args()

    spec = GROUPS[args.group]
    pdf_dir = Path(args.pdf_dir)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    out_dir = Path("data/interim")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"cuadro_{args.group}_discovery.csv"

    rows: list[dict] = []
    for i, pdf in enumerate(pdfs):
        year, week = _year_week(pdf)
        fp = _fingerprint(_pdftotext(pdf), spec["anchors"], spec["state_markers"])
        rows.append({"file": pdf.name, "year": year, "week": week, **fp})
        if (i + 1) % 100 == 0:
            print(f"  ... {i + 1}/{len(pdfs)} PDFs procesados", flush=True)

    cols = [
        "file",
        "year",
        "week",
        "page_found",
        "has_e66",
        "layout_fingerprint",
        "n_acum",
        "years_in_window",
        "sex_label",
        "entity_variant",
        "total_row_found",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})

    found = [r for r in rows if r.get("page_found")]
    missing = [r for r in rows if not r.get("page_found")]
    layouts: dict[str, int] = {}
    for r in found:
        layouts[r.get("layout_fingerprint", "?")] = (
            layouts.get(r.get("layout_fingerprint", "?"), 0) + 1
        )
    yrs = sorted({r["year"] for r in found if r["year"]})
    print(f"\n=== DISCOVERY {args.group} ===")
    print(f"PDFs totales: {len(pdfs)} | con cuadro: {len(found)} | sin cuadro: {len(missing)}")
    print(f"layouts: {layouts}")
    print(f"años con cuadro: {yrs[:3]}...{yrs[-3:] if len(yrs) > 3 else ''}")
    if missing:
        print(f"faltantes (primeros 6): {[r['file'] for r in missing[:6]]}")
    # flip 3col->4col
    by_key = sorted(
        (f"{r['year']}_sem{str(r['week']).zfill(2)}", r["layout_fingerprint"])
        for r in found
        if r["year"]
    )
    prev = None
    for key, lay in by_key:
        if lay != prev:
            print(f"  layout={lay} desde {key}")
            prev = lay
    print(f"-> {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
