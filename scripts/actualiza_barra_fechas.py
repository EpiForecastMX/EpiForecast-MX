"""Actualiza la barra de fechas (meta-bar) de Reports/index.html SIN hardcodes.

Lee las fechas reales que muestran los charts (``zoom_data_neuro.json``) y deriva:
  * Pagina actualizada  -> fecha de hoy.
  * Datos reales hasta   -> ultima semana con dato real (max ``last_real``), semana ISO + lunes.
  * Periodo pronosticado -> desde la semana siguiente al ultimo real hasta el ultimo
                            punto pronosticado (max ``d``), semanas ISO + lunes.

Las semanas epidemiologicas de SINAVE coinciden con el lunes ISO de cada semana
(verificado: 2026-W20 = 2026-05-11). Por eso usamos ``date.fromisocalendar`` y
``isocalendar`` para mapear fecha<->semana sin tablas externas.

Uso:
    python scripts/actualiza_barra_fechas.py \
        --index ../EpiForecast-IMSS-Dashboard/Reports/index.html \
        --zoom  ../EpiForecast-IMSS-Dashboard/Reports/zoom_data_neuro.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys

# Meses en espanol abreviados (minuscula, como en la barra existente).
_MESES = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
]


def _fmt(d: dt.date) -> str:
    """'18 may 2026' (dia sin cero a la izquierda, mes es-MX, anio)."""
    return f"{d.day} {_MESES[d.month - 1]} {d.year}"


def _semana(d: dt.date) -> tuple[int, int]:
    """(anio_iso, semana_iso) de una fecha."""
    iso = d.isocalendar()
    return iso[0], iso[1]


def _parse(fecha: str) -> dt.date:
    return dt.date.fromisoformat(fecha)


def fechas_desde_zoom(zoom_path: Path) -> tuple[dt.date, dt.date]:
    """Devuelve (ultimo_real, ultimo_pronostico) a partir del zoom_data_neuro.json.

    ``ultimo_real``  = max de los ``last_real`` de todas las series.
    ``ultimo_pron.`` = max de la ultima fecha del eje ``d`` de todas las series.
    """
    data = json.loads(zoom_path.read_text(encoding="utf-8"))
    ultimo_real: dt.date | None = None
    ultimo_pron: dt.date | None = None
    for serie in data.values():
        if not isinstance(serie, dict):
            continue
        lr = serie.get("last_real")
        if lr:
            d = _parse(lr)
            if ultimo_real is None or d > ultimo_real:
                ultimo_real = d
        eje = serie.get("d") or []
        if eje:
            d = _parse(eje[-1])
            if ultimo_pron is None or d > ultimo_pron:
                ultimo_pron = d
    if ultimo_real is None or ultimo_pron is None:
        raise ValueError(f"zoom sin last_real/d utilizables: {zoom_path}")
    return ultimo_real, ultimo_pron


def actualiza_barra(index_path: Path, zoom_path: Path, hoy: dt.date | None = None) -> bool:
    """Reescribe la meta-bar de index.html. Devuelve True si hubo cambios."""
    hoy = hoy or dt.date.today()
    ultimo_real, ultimo_pron = fechas_desde_zoom(zoom_path)
    inicio_pron = ultimo_real + dt.timedelta(days=7)

    ar_anio, ar_sem = _semana(ultimo_real)
    ps_anio, ps_sem = _semana(inicio_pron)
    pe_anio, pe_sem = _semana(ultimo_pron)

    html = index_path.read_text(encoding="utf-8")
    original = html

    # 1) Pagina actualizada.
    html = re.sub(
        r"(Página actualizada:\s*<strong>)[^<]*(</strong>)",
        rf"\g<1>{_fmt(hoy)}\g<2>",
        html,
    )
    # 2) Datos reales hasta.
    html = re.sub(
        r"(Datos reales hasta:\s*<strong>)semana\s*\d+\s*de\s*\d+(</strong>\s*\()[^)]*(\))",
        rf"\g<1>semana {ar_sem} de {ar_anio}\g<2>{_fmt(ultimo_real)}\g<3>",
        html,
    )
    # 3) Periodo pronosticado.
    html = re.sub(
        r"(Período pronosticado:\s*<strong>)sem\s*\d+\s*\d+\s*→\s*sem\s*\d+\s*\d+(</strong>\s*\()[^)]*(\))",
        rf"\g<1>sem {ps_sem} {ps_anio} → sem {pe_sem} {pe_anio}\g<2>{_fmt(inicio_pron)} – {_fmt(ultimo_pron)}\g<3>",
        html,
    )

    if html == original:
        print("  barra de fechas: sin cambios (¿patrones no encontrados?)", file=sys.stderr)
        return False
    index_path.write_text(html, encoding="utf-8")
    print(
        f"  barra de fechas -> actualizada {_fmt(hoy)} | "
        f"real sem {ar_sem}/{ar_anio} ({_fmt(ultimo_real)}) | "
        f"pron sem {ps_sem} {ps_anio} → sem {pe_sem} {pe_anio}"
    )
    return True


def main() -> None:
    p = argparse.ArgumentParser(description="Actualiza la meta-bar de Reports/index.html")
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--zoom", required=True, type=Path)
    args = p.parse_args()
    actualiza_barra(args.index, args.zoom)


if __name__ == "__main__":
    main()
