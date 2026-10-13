"""Actualiza la barra de fechas (meta-bar) de Reports/index.html SIN hardcodes.

Lee las fechas reales que muestran los charts (``zoom_data_neuro.json``) y deriva:
  * Pagina actualizada  -> fecha de hoy.
  * Datos reales hasta   -> semana del boletin de la ultima semana real (max ``last_real``),
                            con las fechas que imprime el boletin (domingo a sabado).
  * Periodo pronosticado -> desde la semana siguiente al CORTE del modelo (``corte_modelo``) hasta
                            la ultima semana pronosticada (max ``d``), con sus fechas del boletin.

``last_real`` y ``d`` son ``ds`` del calendario legado, que NO coincide con la semana ISO: la
semana N del boletin tiene el ``ds`` del lunes ISO de la N-1, y en los años con 53 semanas del
boletin o 53 ISO la frontera cambia. Antes se usaba ``isocalendar`` y la barra rotulaba la semana
N como N-1. La conversion se hace con ``epiforecast.utils.semana_epi`` (calendario v2).

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

from epiforecast.utils.semana_epi import (
    DsSinSemanaBoletinError,
    fin_semana_boletin,
    inicio_semana_boletin,
    semana_boletin_de_ds,
    semanas_del_anio_boletin,
)

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
    """(anio, semana) del boletin que representa un ``ds`` legado.

    Un ``ds`` sin semana del boletin (el lunes que el legado salta, p. ej. 2026-12-28) se rotula
    con la semana anterior: sólo ocurre como último punto del eje y nunca como dato real.
    """
    try:
        return tuple(semana_boletin_de_ds(d))  # type: ignore[return-value]
    except DsSinSemanaBoletinError:
        return _semana(d - dt.timedelta(days=7))


def _siguiente(anio: int, semana: int) -> tuple[int, int]:
    if semana < semanas_del_anio_boletin(anio):
        return anio, semana + 1
    return anio + 1, 1


def _rango(ini: tuple[int, int], fin: tuple[int, int]) -> str:
    """'27 sep – 3 oct 2026': del domingo de ``ini`` al sabado de ``fin`` (fechas del boletin)."""
    a, b = inicio_semana_boletin(*ini), fin_semana_boletin(*fin)
    desde = f"{a.day} {_MESES[a.month - 1]}" if a.year == b.year else _fmt(a)
    return f"{desde} – {_fmt(b)}"


def _parse(fecha: str) -> dt.date:
    return dt.date.fromisoformat(fecha)


def fechas_desde_zoom(zoom_path: Path) -> tuple[dt.date, dt.date, tuple[int, int] | None]:
    """Devuelve (ultimo_real, ultimo_pronostico, corte_modelo) a partir del zoom_data_neuro.json.

    ``ultimo_real``  = max de los ``last_real`` de todas las series.
    ``ultimo_pron.`` = max de la ultima fecha del eje ``d`` de todas las series.
    ``corte``        = (anio, semana) del corte que declaran los pronosticos; None si ninguno lo
                       declara. Si las series declaran cortes distintos, falla: la barra no puede
                       resumirlos en uno.
    """
    data = json.loads(zoom_path.read_text(encoding="utf-8"))
    ultimo_real: dt.date | None = None
    ultimo_pron: dt.date | None = None
    cortes: set[tuple[int, int]] = set()
    for serie in data.values():
        if not isinstance(serie, dict):
            continue
        c = serie.get("corte_modelo")
        if isinstance(c, dict):
            cortes.add((int(c["anio"]), int(c["semana"])))
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
    if len(cortes) > 1:
        raise ValueError(f"zoom con cortes de modelo distintos {sorted(cortes)}: {zoom_path}")
    return ultimo_real, ultimo_pron, (next(iter(cortes)) if cortes else None)


def actualiza_barra(index_path: Path, zoom_path: Path, hoy: dt.date | None = None) -> bool:
    """Reescribe la meta-bar de index.html. Devuelve True si hubo cambios."""
    hoy = hoy or dt.date.today()
    ultimo_real, ultimo_pron, corte = fechas_desde_zoom(zoom_path)
    ar_anio, ar_sem = _semana(ultimo_real)
    # El periodo pronosticado empieza tras el corte del modelo (puede ser anterior a la ultima
    # semana real: el observado avanza sin reentrenar). Sin corte declarado, tras lo real.
    ps_anio, ps_sem = _siguiente(*(corte or (ar_anio, ar_sem)))
    pe_anio, pe_sem = _semana(ultimo_pron)
    nota_corte = f"modelos con corte en la semana {corte[1]} de {corte[0]}; " if corte else ""

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
        rf"\g<1>semana {ar_sem} de {ar_anio}\g<2>{_rango((ar_anio, ar_sem), (ar_anio, ar_sem))}\g<3>",
        html,
    )
    # 3) Periodo pronosticado.
    html = re.sub(
        r"(Período pronosticado:\s*<strong>)sem\s*\d+\s*\d+\s*→\s*sem\s*\d+\s*\d+(</strong>\s*\()[^)]*(\))",
        rf"\g<1>sem {ps_sem} {ps_anio} → sem {pe_sem} {pe_anio}\g<2>"
        rf"{nota_corte}{_rango((ps_anio, ps_sem), (pe_anio, pe_sem))}\g<3>",
        html,
    )

    if html == original:
        print("  barra de fechas: sin cambios (¿patrones no encontrados?)", file=sys.stderr)
        return False
    index_path.write_text(html, encoding="utf-8")
    print(
        f"  barra de fechas -> actualizada {_fmt(hoy)} | "
        f"real sem {ar_sem}/{ar_anio} ({_rango((ar_anio, ar_sem), (ar_anio, ar_sem))}) | "
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
