"""Evaluación única en los pliegues externos de la búsqueda anidada (lo llama ``banco_optuna``).

Escala única para todo (mesa de expertos): log(sMAPE_motor / sMAPE_naive) por padecimiento,
promediado sobre sus pliegues externos; la mejora se reporta como exp(mediana) - 1 en %, con IC
bootstrap percentil remuestreando padecimientos. Una sola familia de Holm para todas las pruebas
de la búsqueda (cada alcance contra el naive y entre alcances). También se escribe la tabla de
optimismo interno frente a externo y una selección honesta del sistema que puede escoger entre
motores y alcances usando sólo sus puntajes internos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from epiforecast.banco import ajuste, estadistica
from epiforecast.banco import ajuste_flujo as af

ALCANCES = ("default", "global", "padecimiento")


def _leer(ruta: Path) -> Any:
    return json.loads(ruta.read_text()) if ruta.exists() else None


def _filas(out: Path, ps: list[af.Padecimiento]) -> pd.DataFrame:
    propios: dict[str, dict[tuple[str, Any], dict[str, Any]]] = {}
    for motor in ajuste.ESPACIOS:
        cuerpo = _leer(out / "padecimiento" / f"{motor}.json") or {"resultados": []}
        propios[motor] = {(r["disease_id"], r["externo"]): r for r in cuerpo["resultados"]}
    filas = []
    for p in ps:
        externos: list[Any] = [p.desarrollo[-1]] if p.historia_corta else p.externos
        for ext in externos:
            estudio = af.TRANSFERENCIA if p.historia_corta else ext
            fila: dict[str, Any] = {
                "disease_id": p.disease_id,
                "grupo": "transferencia" if p.historia_corta else "externo",
                "externo": int(ext),
                "naive": af.naive(p, int(ext)),
            }
            for motor, (_, _, default) in ajuste.ESPACIOS.items():
                configs: dict[str, dict[str, Any] | None] = {"default": default}
                g = _leer(out / "global" / f"{motor}__{estudio}.json")
                configs["global"] = g["params"] if g else None
                r = propios[motor].get((p.disease_id, ext))
                configs["padecimiento"] = r["params"] if r else None
                for alcance, params in configs.items():
                    if params is None:
                        continue
                    fila[f"{motor}__{alcance}"] = af.log_ratio(p, motor, params, [int(ext)])
                    if not p.historia_corta:
                        fila[f"{motor}__{alcance}__interno"] = af.log_ratio(
                            p, motor, params, p.internos(ext)
                        )
            internos = {
                k[: -len("__interno")]: v for k, v in fila.items() if k.endswith("__interno")
            }
            if internos:  # selección honesta: menor puntaje interno entre motores y alcances
                elegido = min(internos, key=lambda k: internos[k])
                fila["sistema"] = fila[elegido]
                fila["sistema_eleccion"] = elegido
            filas.append(fila)
    return pd.DataFrame(filas)


def _bootstrap_log(lr: np.ndarray[Any, Any], semilla: int = 20261122) -> tuple[float, float]:
    rng = np.random.default_rng(semilla)
    meds = np.median(rng.choice(lr, size=(10_000, len(lr)), replace=True), axis=1)
    lo, hi = np.percentile(meds, [2.5, 97.5])
    return float(np.expm1(lo) * 100), float(np.expm1(hi) * 100)


def _resumen(t: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    por_pad = t.drop(columns=["externo", "naive", "sistema_eleccion"], errors="ignore")
    por_pad = por_pad.groupby(["grupo", "disease_id"]).mean(numeric_only=True)
    filas, pruebas = [], []
    for grupo, g in por_pad.groupby(level="grupo"):
        for col in [str(c) for c in g if not str(c).endswith("__interno")]:
            lr = g[col].dropna().to_numpy()
            if len(lr) < 6:
                continue
            lo, hi = _bootstrap_log(lr)
            w = estadistica.wilcoxon_pareado(lr, np.zeros_like(lr))
            fila = {
                "grupo": grupo,
                "config": col,
                "padecimientos": len(lr),
                "mejora_mediana_pct": float(np.expm1(np.median(lr)) * 100),
                "ic_bajo": lo,
                "ic_alto": hi,
                "gana_al_naive": int((lr < 0).sum()),
                "peor_mas_10pct": int((lr > np.log(1.1)).sum()),
                "p": w["p"],
            }
            interno = f"{col}__interno"
            if interno in g:
                fila["mejora_interna_pct"] = float(np.expm1(np.median(g[interno].dropna())) * 100)
            filas.append(fila)
            pruebas.append(fila | {"comparacion": f"{col} vs naive"})
        for motor in ajuste.ESPACIOS:
            for a, b in (("global", "default"), ("padecimiento", "global")):
                ca, cb = f"{motor}__{a}", f"{motor}__{b}"
                if ca in g and cb in g:
                    x = g[[ca, cb]].dropna()
                    w = estadistica.wilcoxon_pareado(x[ca].to_numpy(), x[cb].to_numpy())
                    pruebas.append(
                        {
                            "grupo": grupo,
                            "comparacion": f"{ca} vs {cb}",
                            "padecimientos": len(x),
                            "dif_mediana_log": w["mediana_dif"],
                            "r_rb": w["r_rb"],
                            "p": w["p"],
                        }
                    )
    res, pr = pd.DataFrame(filas), pd.DataFrame(pruebas)
    ok = pr["p"].notna()
    pr.loc[ok, "p_holm"] = estadistica.holm(pr.loc[ok, "p"].tolist())  # una sola familia
    return res.sort_values(["grupo", "mejora_mediana_pct"]), pr


def evalua(out: Path, ps: list[af.Padecimiento]) -> int:
    t = _filas(out, ps)
    t.to_csv(out / "externo_por_padecimiento.csv", index=False)
    res, pr = _resumen(t)
    res.to_csv(out / "resumen_configuraciones.csv", index=False)
    pr.to_csv(out / "pruebas_holm.csv", index=False)
    resumen = {
        "pliegues_externos": t.groupby("grupo")["externo"].value_counts().to_dict().__repr__(),
        "sistema_elecciones": t["sistema_eleccion"].value_counts().to_dict()
        if "sistema_eleccion" in t
        else {},
    }
    (out / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1))
    cols = ["grupo", "config", "padecimientos", "mejora_mediana_pct", "ic_bajo", "ic_alto"]
    cols += ["mejora_interna_pct", "gana_al_naive", "peor_mas_10pct"]
    print(res[cols].round(2).to_string(index=False))
    print(
        pr[[c for c in ("grupo", "comparacion", "padecimientos", "p", "p_holm") if c in pr]]
        .round(4)
        .to_string(index=False)
    )
    return 0
