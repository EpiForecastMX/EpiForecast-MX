#!/usr/bin/env python
"""build_epibot_zoom.py — Re-llave los zoom_data_{neuro,dengue}.json de la galería a un índice
que el EpiBot resuelve con detectEntities (estado × sexo), y escribe ``zoom_series.json``.

La galería llavea por la ruta del PNG (``Depresión/Jalisco/Depresión_Jalisco_general.png``).
El EpiBot, en cambio, detecta padecimiento/estado/sexo con nombres canónicos sin acento. Este
script traduce cada serie a la clave ``pad|estado|sexo`` usando la MISMA normalización que el
``norm()`` del bot (minúsculas, sin acentos, no alfanumérico -> espacio, espacios colapsados),
de modo que el bot la busca sin mapeos frágiles. Así el zoom del EpiBot funciona por estado y
sexo (``zoom depresión jalisco``, ``zoom dengue yucatán mujeres``), no solo nacional.

Con ``--seguimiento`` (``seguimiento_post_corte.csv``) cada serie lleva además sus pares del
seguimiento posterior al corte (semana, periodo oficial del boletín, corte, horizonte, estado y
motivo), el ``ds`` del corte y la definición de lo observado. El EpiBot compara SÓLO esos pares:
la línea del motor anterior al corte es ajuste dentro de muestra y no se presenta como validación.
Toda serie del zoom debe tener su seguimiento y viceversa; si no, falla.

Uso:
    python scripts/build_epibot_zoom.py --reports ../EpiForecast-IMSS-Dashboard/Reports \
        --out ../EpiForecast-IMSS-Dashboard/epibot [--seguimiento reports/ProdDetails/seguimiento_post_corte.csv]
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import unicodedata

# Carpetas de la galería de las 4 regiones neuro (la tabla las llama ``region_<nombre>``).
_REGION_CARPETA = {
    "region_Metropolitana alta": "Region_Metropolitana_alta",
    "region_Rural / dispersa": "Region_Rural_-_dispersa",
    "region_Sur-Sureste vulnerable": "Region_Sur-Sureste_vulnerable",
    "region_Urbana media": "Region_Urbana_media",
}
_ENTERO = ("horizonte", "pronostico", "real", "error_abs")


def _norm(text: str) -> str:
    """Réplica de ``norm()`` del EpiBot (entities.js): minúsculas, sin acentos (á→a, ñ→n),
    todo lo no alfanumérico a espacio, espacios colapsados."""
    t = text.lower()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = "".join(c if (c.isalnum() and c.isascii()) or c == " " else " " for c in t)
    return " ".join(t.split())


def clave_galeria(fila: dict[str, str]) -> str:
    """Clave del ``zoom_data_*.json`` (ruta del PNG) de una fila del seguimiento."""
    if fila["cohorte"] == "neuro":
        pad = {"Depresion": "Depresión"}.get(fila["padecimiento"], fila["padecimiento"])
        carpeta = _REGION_CARPETA.get(fila["entidad"], fila["entidad"].replace(" ", "_"))
        return f"{pad}/{carpeta}/{pad}_{carpeta}_{fila['sexo']}.png"
    disp = {"México": "Estado de México"}.get(fila["entidad"], fila["entidad"]).replace(" ", "_")
    return f"dengue/{disp}/Dengue_{disp}_{fila['sexo']}.png"


def carga_seguimiento(ruta: Path) -> dict[str, dict[str, object]]:
    """Por clave de la galería: los pares del seguimiento, el ds del corte y la definición."""
    out: dict[str, dict[str, object]] = {}
    pares: dict[str, list[dict[str, object]]] = {}
    with ruta.open(encoding="utf-8") as fh:
        for f in csv.DictReader(fh):
            par: dict[str, object] = {
                "etiqueta": f["semana_objetivo"],
                "periodo_inicio": f["inicio_semana"],
                "periodo_fin": f["fin_semana"],
                "corte": f["corte"],
                "estado": f["estado"],
                "motivo": f["motivo"],
            }
            for k in _ENTERO:
                par[k] = int(f[k]) if f[k] else None
            clave = clave_galeria(f)
            if clave not in out:
                pares[clave] = []
                out[clave] = {
                    "definicion_real": f["definicion_real"],
                    "corte": f["corte"],
                    "seguimiento": pares[clave],
                }
            pares[clave].append(par)
    return out


def ds_del_corte(etiqueta: str) -> str:
    from epiforecast.utils.semana_epi import ds_de_semana_boletin

    anio, semana = (int(x) for x in etiqueta.split("-W"))
    return ds_de_semana_boletin(anio, semana).date().isoformat()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reports", required=True, help="Directorio Reports/ (con zoom_data_*.json)")
    ap.add_argument(
        "--out", required=True, help="Directorio epibot/ donde escribir zoom_series.json"
    )
    ap.add_argument("--seguimiento", type=Path, default=None, help="seguimiento_post_corte.csv")
    args = ap.parse_args()
    reports = Path(args.reports)
    seg = carga_seguimiento(args.seguimiento) if args.seguimiento is not None else None
    usados: set[str] = set()

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
            if seg is not None:
                if key not in seg:
                    raise SystemExit(f"la serie {key} del zoom no tiene seguimiento")
                usados.add(key)
                info = seg[key]
                payload = {
                    **payload,
                    "definicion_real": info["definicion_real"],
                    "corte": info["corte"],
                    "ds_corte": ds_del_corte(str(info["corte"])),
                    "seguimiento": info["seguimiento"],
                }
            series[f"{_norm(pad_folder)}|{_norm(estado)}|{sexo}"] = payload

    if seg is not None and set(seg) != usados:
        raise SystemExit(f"{len(set(seg) - usados)} serie(s) del seguimiento sin zoom")
    out = Path(args.out) / "zoom_series.json"
    out.write_text(json.dumps(series, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"zoom_series.json: {len(series)} series de {n_files} archivos -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
