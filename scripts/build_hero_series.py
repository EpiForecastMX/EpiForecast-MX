#!/usr/bin/env python
"""build_hero_series.py — el gráfico vivo de la portada (``hero_series.json``) desde esta ronda.

Hasta la ronda W39 el archivo se había escrito una vez (11-jun-2026, datos a la semana 21) y ningún
paso del carril semanal lo regeneraba: la portada mostraba un motor, un total y curvas de junio, un
``smape`` por padecimiento y la línea del modelo también sobre las semanas observadas.

Ahora se deriva de lo que el productor ya generó y verificó:

* la serie NACIONAL general de cada padecimiento publicado, del zoom de la galería
  (``zoom_data_{neuro,dengue}.json``): observado hasta la última semana del boletín y el pronóstico
  del modelo nacional SÓLO desde el corte (antes del corte la línea sería el ajuste dentro de
  muestra); la banda, sólo si el motor la produce (nativa), nunca sintética;
* el motor y el total del MODELO NACIONAL: 52 pasos desde el corte (``casos_nacional`` de la tabla
  para neuro; ``casos_futuro_nacional_52sem`` para Dengue), que debe coincidir con la tabla semanal
  del EpiBot (``weekly_comparison.*.pronostico_52_pasos``); si no, falla;
* el corte y la última semana observada, del seguimiento publicado en el knowledge.

No lleva métricas de error. Uso:
    python scripts/build_hero_series.py --reports <dashboard>/Reports \\
        --knowledge <dashboard>/epibot/knowledge.json --out <dashboard>/hero_series.json
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any

# (clave del knowledge, clave corta, rótulo, color, CIE, carpeta del zoom) en el orden de la portada.
PADECIMIENTOS = (
    (
        "Depresion",
        "depresion",
        "Depresión",
        "#5B8DEF",
        "F32",
        "Depresión/Nacional/Depresión_Nacional_general.png",
    ),
    (
        "Parkinson",
        "parkinson",
        "Parkinson",
        "#2DD4BF",
        "G20",
        "Parkinson/Nacional/Parkinson_Nacional_general.png",
    ),
    (
        "Alzheimer",
        "alzheimer",
        "Alzheimer",
        "#F472B6",
        "G30",
        "Alzheimer/Nacional/Alzheimer_Nacional_general.png",
    ),
    (
        "Dengue",
        "dengue",
        "Dengue",
        "#F59E0B",
        "A97",
        "dengue/Nacional/Dengue_Nacional_general.png",
    ),
)


def _ds_corte(corte: dict[str, int]) -> str:
    from epiforecast.utils.semana_epi import ds_de_semana_boletin

    return ds_de_semana_boletin(int(corte["anio"]), int(corte["semana"])).date().isoformat()


def construye(reports: Path, knowledge: dict[str, Any], generado: str) -> dict[str, Any]:
    zoom = {
        **json.loads((reports / "zoom_data_neuro.json").read_text(encoding="utf-8")),
        **json.loads((reports / "zoom_data_dengue.json").read_text(encoding="utf-8")),
    }
    seg = knowledge.get("seguimiento_post_corte") or {}
    corte = seg.get("corte", {}).get("etiqueta")
    ultima = seg.get("ultima_semana_observada", {}).get("etiqueta")
    if not corte or not ultima:
        raise SystemExit(
            "knowledge sin seguimiento_post_corte: no se sabe el corte ni la última semana"
        )
    wc = knowledge.get("weekly_comparison") or {}
    stats = knowledge.get("stats") or {}
    series = []
    for pad, key, label, color, cie, clave in PADECIMIENTOS:
        z = zoom.get(clave)
        if z is None:
            raise SystemExit(f"el zoom de la galería no tiene {clave}")
        if f"{z['corte_modelo']['anio']}-W{int(z['corte_modelo']['semana']):02d}" != corte:
            raise SystemExit(f"{clave}: corte {z['corte_modelo']} ≠ {corte}")
        dsc = _ds_corte(z["corte_modelo"])
        if pad == "Dengue":
            dg = knowledge.get("dengue") or {}
            motor, casos = dg.get("motor_nacional"), dg.get("casos_futuro_nacional_52sem")
        else:
            nac = next(
                (
                    m
                    for m in knowledge.get("prod_models", [])
                    if m["padecimiento"] == pad
                    and m["entidad"] == "Nacional"
                    and m["sexo"] == "general"
                ),
                None,
            )
            motor = nac and nac.get("modelo_produccion")
            casos = (
                stats.get("por_pad", {})
                .get(pad, {})
                .get("por_sexo", {})
                .get("general", {})
                .get("casos_nacional")
            )
        if motor is None or casos is None:
            raise SystemExit(f"{pad}: sin motor o sin pronóstico del modelo nacional")
        if motor != z.get("motor"):
            raise SystemExit(
                f"{pad}: motor del knowledge {motor} ≠ el de la galería {z.get('motor')}"
            )
        esperado = (wc.get(pad) or {}).get("pronostico_52_pasos")
        if esperado != casos:
            raise SystemExit(
                f"{pad}: {casos} casos ≠ 52 pasos desde el corte de la tabla semanal ({esperado})"
            )
        despues = [d > dsc for d in z["d"]]
        series.append(
            {
                "pad": pad,
                "key": key,
                "label": label,
                "color": color,
                "cie": cie,
                "motor": motor,
                "casos": casos,
                "casos_definicion": "pronóstico del modelo nacional, 52 pasos desde el corte",
                "corte": corte,
                "ultima_observada": ultima,
                "last_real": z["last_real"],
                "intervalo_disponible": bool(z.get("intervalo_disponible")),
                "d": z["d"],
                "r": z["r"],
                "y": [v if a else None for v, a in zip(z["y"], despues, strict=True)],
                "lo": [v if a else None for v, a in zip(z["lo"], despues, strict=True)],
                "hi": [v if a else None for v, a in zip(z["hi"], despues, strict=True)],
            }
        )
    return {"_generated": generado, "corte": corte, "ultima_observada": ultima, "series": series}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reports", type=Path, required=True)
    ap.add_argument("--knowledge", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--generado", default=date.today().isoformat())
    a = ap.parse_args(argv)
    hero = construye(a.reports, json.loads(a.knowledge.read_text(encoding="utf-8")), a.generado)
    a.out.write_text(
        json.dumps(hero, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(
        f"hero_series.json: {len(hero['series'])} series · corte {hero['corte']} · "
        f"observado hasta {hero['ultima_observada']} -> {a.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
