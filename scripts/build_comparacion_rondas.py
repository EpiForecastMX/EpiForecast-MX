"""Comparación nacional con entradas archivadas; no entrena ni modifica sus fuentes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from epiforecast.utils.semana_epi import (  # noqa: E402
    DsSinSemanaBoletinError,
    fin_semana_boletin,
    inicio_semana_boletin,
    semana_boletin_de_ds,
)

WCP_SHA = "76896a28edb2a7b2ba1492dbe0dac40a62e728f1831fe2a914988cabacfa7812"
SNAP_SHA = "7f08456f3f1dfd5895aff1c588a6ba948d326f8aec88eac0c0fb42152cf00ddd"
PADS = {
    "Depresion": "depresion",
    "Parkinson": "parkinson",
    "Alzheimer": "alzheimer",
    "Dengue": "dengue",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def build(knowledge: Path, zoom: Path, wcp: Path, snapshot: Path) -> dict:
    for path, expected in ((wcp, WCP_SHA), (snapshot, SNAP_SHA)):
        if sha(path) != expected:
            raise ValueError(f"fuente archivada alterada: {path}")
    k, z, old = (json.loads(p.read_text()) for p in (knowledge, zoom, wcp))
    if old["evaluation"] != dict(year=2026, first_week=7, last_week=31, recent_first_week=24):
        raise ValueError("ventana WCP inesperada")
    with snapshot.open() as f:
        archived = list(csv.DictReader(f))
    latest = k["weekly_comparison"]["Depresion"]["ultima_semana_observada"]
    if not latest.startswith("2026-W"):
        raise ValueError("esta comparación corresponde al año 2026")
    max_week = int(latest.split("W")[1])
    series = {}
    for pad, key in PADS.items():
        wc = k["weekly_comparison"][pad]
        if wc["version"] != 2 or wc["corte"] != "2026-W37":
            raise ValueError("corte o contrato semanal inesperado")
        source = next(
            (s for s in old["national"] if s["condition"] == key),
            {"motor": "deepar", "forecasts": []},
        )
        previous = {}
        for r in archived:
            if (r["padecimiento"], r["entidad"], r["sexo"]) != (pad, "Nacional", "general"):
                continue
            try:
                target = semana_boletin_de_ds(r["ds"])
            except DsSinSemanaBoletinError:
                continue  # Paso sin semana del boletín: nunca se empareja.
            if target.anio != 2026 or target.semana > max_week:
                continue
            if target.semana in previous:
                raise ValueError("pronóstico archivado duplicado")
            if r["motor"] != source["motor"]:
                raise ValueError("motor anterior cambió")
            previous[target.semana] = float(r["yhat"])
        # WCP conserva W7–W31. Donde también existe el CSV de junio, contrastamos
        # antes de usar SU valor: CSV redondeado a 2 decimales, WCP con más precisión.
        for i, v in enumerate(source["forecasts"]):
            week = 7 + i
            if week > max_week:
                continue
            if week in previous and abs(previous[week] - v) > 0.00501:
                raise ValueError(f"fuentes anteriores discrepan: {pad} W{week}")
            previous.setdefault(week, v)
        if set(previous) != set(range(22 if pad == "Dengue" else 7, max_week + 1)):
            raise ValueError("cobertura anterior incompleta: no se imputa")
        if wc["ultima_semana_observada"] != latest:
            raise ValueError("padecimientos con observado de semanas distintas")
        rows = []
        for w in wc["semanas"]:
            if w["semana"] > max_week:
                continue
            week = w["semana"]
            current = w.get("pronostico") if w["fase"] == "seguimiento" else None
            forecast = previous.get(week)
            if w["fase"] == "seguimiento" and w.get("estado") == "par":
                if not finite(current) or not finite(w.get("real")):
                    raise ValueError("par declarado sin observado o pronóstico finito")
            real = w.get("real")
            for v in (current, forecast, real):
                if v is not None and (not finite(v) or v < 0):
                    raise ValueError("valor no finito o negativo")
            rows.append(
                dict(
                    semana=week,
                    etiqueta=w["etiqueta"],
                    inicio=w["periodo_inicio"],
                    fin=w["periodo_fin"],
                    real=real,
                    anterior=forecast,
                    actual=current,
                    procedencia_anterior=("snapshot_junio" if week >= 22 else "archivo_wcp")
                    if forecast is not None
                    else None,
                    fase_anterior=("archivo_previo" if week >= 24 else "retrospectivo")
                    if forecast is not None
                    else "sin_pronostico",
                    motivo_ausencia=w.get("motivo", ""),
                )
            )
        if len(rows) != max_week:
            raise ValueError("observado no llega a la semana declarada")
        series[pad] = dict(motor_anterior=source["motor"], motor_actual=wc["motor"], semanas=rows)
    hz = z["depresion|nacional|general"]
    future = [ds for ds in hz["d"] if ds > hz["ds_corte"]]
    if len(future) != 52:
        raise ValueError("no hay 52 pasos en el pronóstico actual")
    targets, unmapped = [], []
    for ds in future:
        try:
            targets.append(semana_boletin_de_ds(ds))
        except DsSinSemanaBoletinError:
            unmapped.append(ds)
    first, last = targets[0], targets[-1]
    return dict(
        version=1,
        observado_hasta=latest,
        cobertura="Nacional · general · cuatro padecimientos",
        notas=[
            "W7–W23: comparación retrospectiva neuro; no se acredita un archivo emitido en febrero. Dengue sólo tiene archivo anterior desde W22.",
            f"W24–W{max_week}: pronósticos del CSV archivado el 5 de junio, anteriores al periodo comparado.",
            f"W38–W{max_week}: seguimiento del motor actual, con corte W37. Su ajuste histórico no se compara.",
            "Los periodos difieren; sus resúmenes no constituyen un ranking entre rondas.",
            "Estados, regiones y sexos no tienen una comparación anterior habilitada en esta función.",
        ],
        fuentes={
            "archivo_wcp": dict(archivo=wcp.name, sha256=sha(wcp), version=old["version"]),
            "snapshot_junio": dict(
                archivo=snapshot.name,
                sha256=sha(snapshot),
                commit="8751ba63894d77c816a07579b03128e521c85c80",
                fecha_archivo="2026-06-05",
                nota="fecha_corte del CSV es el corte del boletín al archivar, no prueba del corte de entrenamiento",
            ),
            "knowledge": dict(archivo=knowledge.name, sha256=sha(knowledge)),
            "zoom": dict(archivo=zoom.name, sha256=sha(zoom)),
        },
        horizonte_actual=dict(
            corte="2026-W37",
            inicio=inicio_semana_boletin(*first).isoformat(),
            fin=fin_semana_boletin(*last).isoformat(),
            primera=f"{first.anio}-W{first.semana:02}",
            ultima=f"{last.anio}-W{last.semana:02}",
            pasos=52,
            pasos_sin_semana=unmapped,
        ),
        series=series,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("knowledge", "zoom", "wcp", "snapshot", "out"):
        ap.add_argument(f"--{name}", type=Path, required=True)
    args = ap.parse_args()
    data = build(args.knowledge, args.zoom, args.wcp, args.snapshot)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    n_old = sum(
        sum(w["real"] is not None and w["anterior"] is not None for w in r["semanas"])
        for r in data["series"].values()
    )
    n_new = sum(
        sum(w["real"] is not None and w["actual"] is not None for w in r["semanas"])
        for r in data["series"].values()
    )
    print(f"4 series nacionales · {n_old} pares anteriores · {n_new} actuales · {args.out}")


if __name__ == "__main__":
    main()
