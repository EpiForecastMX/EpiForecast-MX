"""Búsqueda anidada de hiperparámetros con Optuna sobre el banco (desarrollo; no publica nada).

Uso:
    python -m scripts.banco_optuna datos [--workers N]
    python -m scripts.banco_optuna busca [--motor M ...] [--trials N] [--alcance global|padecimiento]
    python -m scripts.banco_optuna evalua

Resultados en runs/banco_optuna/v2/. Un estudio por (motor, externo), con externo en {2023, 2024,
transferencia}; la búsqueda sólo ve los años internos (``ajuste_flujo``). La media móvil, de una
sola dimensión entera, se recorre completa con GridSampler; el resto usa TPE multivariado.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import pickle
import subprocess
from typing import Any

import numpy as np

from epiforecast.banco import ajuste
from epiforecast.banco import ajuste_flujo as af

_ROOT = Path(__file__).resolve().parents[1]
OUT = _ROOT / "runs" / "banco_optuna" / "v2"
SEMILLA = 20261122
EXTERNOS: tuple[int | str, ...] = (2023, 2024, af.TRANSFERENCIA)
REJILLA = {"media_movil": {"ventana": list(range(4, 157))}}
MIN_INTERNOS_PADECIMIENTO = 2


def _hilos() -> None:
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[var] = "1"


def _cargar_uno(disease: str) -> af.Padecimiento:
    _hilos()
    return af.precalcular_ets(af.cargar(disease))


def procedencia() -> dict[str, Any]:
    import optuna
    import statsmodels

    datos = OUT / "datos.pkl"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    sucio = subprocess.run(
        ["git", "status", "--porcelain", "--", "src", "scripts", "config"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return {
        "commit": head,
        "arbol_limpio": not sucio,
        "semilla": SEMILLA,
        "optuna": optuna.__version__,
        "statsmodels": statsmodels.__version__,
        "numpy": np.__version__,
        "datos_sha256": hashlib.sha256(datos.read_bytes()).hexdigest() if datos.exists() else None,
        "recorte_objetivo": af.RECORTE,
    }


def datos(workers: int) -> int:
    from epiforecast import registry

    ids = sorted(d.id for d in registry.release_published())
    with ProcessPoolExecutor(max_workers=workers) as ex:
        ps = list(ex.map(_cargar_uno, ids))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "datos.pkl").write_bytes(pickle.dumps(ps))
    print(f"{len(ps)} padecimientos; historia corta {sum(p.historia_corta for p in ps)}")
    return 0


def _ps() -> list[af.Padecimiento]:
    ps: list[af.Padecimiento] = pickle.loads((OUT / "datos.pkl").read_bytes())
    return ps


def _estudio(ps: list[af.Padecimiento], motor: str, externo: int | str, trials: int) -> Any:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    if motor in REJILLA:
        sampler: Any = optuna.samplers.GridSampler(REJILLA[motor], seed=SEMILLA)
        trials = len(next(iter(REJILLA[motor].values())))
    else:
        sampler = optuna.samplers.TPESampler(seed=SEMILLA, multivariate=True)
    est = optuna.create_study(direction="minimize", sampler=sampler)
    if motor not in REJILLA:
        est.enqueue_trial(ajuste.ESPACIOS[motor][2])  # el default compite: nunca se empeora
    est.optimize(af.objetivo(ps, motor, externo), n_trials=trials)
    return est


def _busca_global(args: tuple[str, int | str, int]) -> str:
    _hilos()
    motor, externo, trials = args
    ps = af.participantes(_ps(), externo)
    est = _estudio(ps, motor, externo, trials)
    default = af.objetivo(ps, motor, externo)
    res = {
        "motor": motor,
        "externo": externo,
        "trials": len(est.trials),
        "padecimientos": [p.disease_id for p in ps],
        "interno_default": default(_FijoTrial(ajuste.ESPACIOS[motor][2])),
        "interno_mejor": est.best_value,
        "params": af.params_de(motor, est.best_params),
        "procedencia": procedencia(),
    }
    dest = OUT / "global"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{motor}__{externo}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    est.trials_dataframe().to_csv(dest / f"{motor}__{externo}_trials.csv", index=False)
    return f"{motor} {externo}: {res['interno_default']:.4f} -> {res['interno_mejor']:.4f}"


class _FijoTrial:
    def __init__(self, crudos: dict[str, Any]) -> None:
        self.crudos = crudos

    def suggest_int(self, name: str, low: int, high: int) -> int:
        return int(self.crudos[name])

    def suggest_float(self, name: str, low: float, high: float, *, log: bool = False) -> float:
        return float(self.crudos[name])

    def suggest_categorical(self, name: str, choices: list[Any]) -> Any:
        return self.crudos[name]


def _busca_padecimiento(args: tuple[str, str, int, int]) -> dict[str, Any]:
    _hilos()
    disease, motor, externo, trials = args
    (p,) = [q for q in _ps() if q.disease_id == disease]
    est = _estudio([p], motor, externo, trials)
    return {
        "disease_id": disease,
        "externo": externo,
        "interno_mejor": est.best_value,
        "params": af.params_de(motor, est.best_params),
    }


def busca(motores: list[str], trials: int, alcance: str, workers: int) -> int:
    if alcance == "global":
        tareas = [(m, e, trials) for m in motores for e in EXTERNOS]
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for r in ex.map(_busca_global, tareas):
                print(r, flush=True)
        return 0
    ps = _ps()
    for motor in motores:
        tareas2 = [
            (p.disease_id, motor, e, trials)
            for e in EXTERNOS
            if e != af.TRANSFERENCIA
            for p in af.participantes(ps, e)
            if len(p.internos(e)) >= MIN_INTERNOS_PADECIMIENTO
        ]
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(_busca_padecimiento, tareas2))
        dest = OUT / "padecimiento"
        dest.mkdir(parents=True, exist_ok=True)
        cuerpo = {"procedencia": procedencia(), "resultados": res}
        (dest / f"{motor}.json").write_text(json.dumps(cuerpo, ensure_ascii=False, indent=1))
        print(f"{motor}: {len(res)} estudios por padecimiento", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = max(1, (os.cpu_count() or 2) - 1)
    d = sub.add_parser("datos")
    d.add_argument("--workers", type=int, default=w)
    b = sub.add_parser("busca")
    b.add_argument("--motor", action="append", choices=list(ajuste.ESPACIOS))
    b.add_argument("--trials", type=int, default=300)
    b.add_argument("--alcance", choices=["global", "padecimiento"], default="global")
    b.add_argument("--workers", type=int, default=w)
    sub.add_parser("evalua")
    a = ap.parse_args(argv)
    np.seterr(all="ignore")
    if a.cmd == "datos":
        return datos(a.workers)
    if a.cmd == "busca":
        return busca(a.motor or list(ajuste.ESPACIOS), a.trials, a.alcance, a.workers)
    from scripts import banco_optuna_evalua

    return banco_optuna_evalua.evalua(OUT, _ps())


if __name__ == "__main__":
    raise SystemExit(main())
