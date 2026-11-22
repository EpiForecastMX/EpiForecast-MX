"""Banco ampliado de motores en pliegues de desarrollo: ¿le ganamos al naive y a los simples?

No selecciona, no publica y no toca releases ni años de prueba. Uso:
    python -m scripts.banco_ampliado corre [--disease ID ...] [--motor M ...] [--workers N]
    python -m scripts.banco_ampliado reporte

Resultados en runs/banco_ampliado/v1/ (reanudable: una tarea ya escrita no se repite).
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import time

import pandas as pd

from epiforecast.banco import flujo, reporte

_ROOT = Path(__file__).resolve().parents[1]
OUT = _ROOT / "runs" / "banco_ampliado" / "v1"
_PESADOS = ("prophet_log1p", "ets_amortiguado_log1p", "theta_log1p", "lgbm_global_directo")


def _tarea(disease: str, motor: str) -> str:
    import logging

    logging.getLogger("cmdstanpy").disabled = True
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[var] = "1"
    cfg = flujo.cargar_config()
    t0 = time.time()
    df, info = flujo.correr(disease, motor, cfg, _ROOT)
    fallidos = {f["fold"] for f in info["fallos"]}
    met = flujo.metricas(df, fallidos, info["series"]) if not df.empty else pd.DataFrame()
    base = OUT / "tareas" / f"{disease}__{motor}"
    df.to_parquet(base.with_suffix(".parquet"), index=False)
    info |= {
        "disease_id": disease,
        "engine": motor,
        "segundos": round(time.time() - t0, 1),
        "metricas": met.to_dict(orient="records"),
    }
    base.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, default=float))
    return f"{disease} {motor} {info['segundos']}s fallos={len(info['fallos'])}"


def _publicados() -> list[str]:
    from epiforecast import registry

    return sorted(d.id for d in registry.release_published())


def corre(diseases: list[str], motores: list[str], workers: int) -> int:
    (OUT / "tareas").mkdir(parents=True, exist_ok=True)
    pend = [
        (d, m)
        for m in motores
        for d in diseases
        if not (OUT / "tareas" / f"{d}__{m}.json").exists()
    ]
    pend.sort(key=lambda t: t[1] not in _PESADOS)  # los pesados primero
    print(f"{len(pend)} tareas pendientes", flush=True)
    errores = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_tarea, d, m): (d, m) for d, m in pend}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                print(f"[{i}/{len(pend)}] {f.result()}", flush=True)
            except Exception as exc:  # noqa: BLE001 - la tarea queda pendiente para reintento
                errores += 1
                print(f"[{i}/{len(pend)}] ERROR {futs[f]}: {exc!r}", flush=True)
    return 1 if errores else 0


def informe() -> int:
    cfg = flujo.cargar_config()
    filas, fallos = [], []
    for j in sorted((OUT / "tareas").glob("*.json")):
        info = json.loads(j.read_text())
        for m in info["metricas"]:
            filas.append({"disease_id": info["disease_id"], "engine": info["engine"]} | m)
        fallos.append(
            {
                "disease_id": info["disease_id"],
                "engine": info["engine"],
                "series_fallidas": len(info["fallos"]),
                "recortes": info["recortes"],
                "segundos": info["segundos"],
            }
        )
    met, fal = pd.DataFrame(filas), pd.DataFrame(fallos)
    met.to_csv(OUT / "metricas.csv", index=False)
    t = reporte.tabla(met)
    t.to_csv(OUT / "smape_nacional_por_padecimiento.csv")
    fijo = reporte.motor_fijo(t, cfg["control"], cfg["clase_de"])
    fijo = fijo.merge(
        fal.groupby("engine")[["series_fallidas", "recortes", "segundos"]].sum(),
        on="engine",
        how="left",
    )
    fijo.to_csv(OUT / "motor_fijo.csv", index=False)
    res = {
        "seleccion_creciente": reporte.seleccion_creciente(met, cfg["control"], cfg["clase_de"]),
        "techo_por_clase": reporte.techo_por_clase(t, cfg["clase_de"]),
    }
    (OUT / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(fijo.to_string(index=False))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("corre")
    c.add_argument("--disease", action="append")
    c.add_argument("--motor", action="append")
    c.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    sub.add_parser("reporte")
    args = ap.parse_args(argv)
    if args.cmd == "reporte":
        return informe()
    cfg = flujo.cargar_config()
    return corre(args.disease or _publicados(), args.motor or cfg["motores"], args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
