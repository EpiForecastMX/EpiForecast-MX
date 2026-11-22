"""Política v2 en sombra: carga de artefactos, retroprueba, emisión congelada y validación.

Lee sólo lo ya sellado: el benchmark de desarrollo del release público (``runs/<benchmark>``), la
observación vigente (``artifacts/observations``) y el pronóstico publicado. Escribe la emisión en
``runs/sombra_v2/<emision>/`` (sin versionar, por tamaño) y su índice de hashes en
``docs/sombra_v2/emisiones/`` (versionado: el commit fecha la emisión antes de la verdad).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np
import pandas as pd
import yaml

from epiforecast import registry
from epiforecast.data.epi_geo_exposure import GeoCatalog
from epiforecast.data.sex_scheme import base_sexes_of
from epiforecast.publication.prospective import read_base_history
from epiforecast.runner import sombra_v2 as sv
from epiforecast.runner.evaluation import smape_percent

_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = "sombra_v2_emision.v1"
_EV_COLS = [
    "engine",
    "fold",
    "split",
    "geography_level",
    "geography_id",
    "sex",
    "epi_year",
    "epi_week",
    "y_true_cases",
    "y_pred_cases",
]


def _json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publicados() -> list[str]:
    return sorted(d.id for d in registry.release_published())


def release_dir(disease: str, root: Path = _ROOT) -> Path:
    puntero = _json(root / "config" / "publication" / disease / "public_release_pointer.json")
    return root / "artifacts" / "releases" / disease / str(puntero["release_id"])


def _anios_prueba(rel: Path) -> set[int]:
    (politica,) = sorted((rel / "policy").glob("*.yaml"))
    folds = yaml.safe_load(politica.read_text(encoding="utf-8"))["folds"]
    return {int(f["epi_year"]) for f in folds.get("test") or []}


def desarrollo(disease: str, reglas: sv.Reglas, root: Path = _ROOT) -> pd.DataFrame:
    """Filas base de desarrollo del benchmark sellado. Falla cerrado ante un año de prueba."""
    rel = release_dir(disease, root)
    prov = _json(rel / "selection" / "acceptance.json")["provenance"]
    bdir = root / "runs" / str(prov["benchmark_run_id"]) / "artifacts"
    prueba = _anios_prueba(rel)
    frames = []
    for engine in reglas.candidatos:
        f = bdir / engine / "evaluation.csv"
        if f.is_file():
            ev = pd.read_csv(f, usecols=_EV_COLS, dtype={"geography_id": str})
            frames.append(ev[(ev["split"] == "development") & (ev["geography_level"] == "estado")])
    if not frames:
        raise sv.SombraError(f"{disease}: sin benchmark de desarrollo en {bdir}")
    ev = pd.concat(frames, ignore_index=True)
    if set(ev["epi_year"]) & prueba:
        raise sv.SombraError(f"{disease}: el desarrollo contiene años de prueba {prueba}")
    return ev[ev["sex"].isin(base_sexes_of(ev["sex"].unique()))].drop(columns="split")


def observacion(disease: str, root: Path = _ROOT) -> tuple[str, Path]:
    estado = _json(root / "config" / "publication" / disease / "prospective_status.json")
    oid = str(estado["observation_dataset_id"])
    csv = root / "artifacts" / "observations" / disease / oid / "epi_dataset_v2.csv"
    if not csv.is_file():
        raise sv.SombraError(f"{disease}: falta la observación {oid} (dvc pull)")
    return oid, csv


def retro(ev: pd.DataFrame, catalog: GeoCatalog, reglas: sv.Reglas) -> list[dict[str, Any]]:
    """Ventana creciente: elige con los pliegues previos y mide en el siguiente (sólo desarrollo)."""
    folds = sorted(ev["fold"].unique())
    sin_margen = dataclasses.replace(reglas, margen_minimo_pct=0.0, mayoria_pliegues=False)
    filas = []
    for i in range(1, len(folds)):
        previo, eval_ = ev[ev["fold"].isin(folds[:i])], ev[ev["fold"] == folds[i]]
        met = sv.metricas_desarrollo(previo)
        fila: dict[str, Any] = {"fold": folds[i]}
        for nombre, r in [("v2", reglas), ("v2_sin_margen", sin_margen)]:
            fila[f"motor_{nombre}"] = sv.seleccionar(met, r)["engine"]
        nac = eval_.groupby(["engine", *sv.PERIODO])[["y_true_cases", "y_pred_cases"]].sum()
        for nombre, e in [
            ("control", reglas.control),
            ("v2", fila["motor_v2"]),
            ("v2_sin_margen", fila["motor_v2_sin_margen"]),
        ]:
            g = nac.loc[e]
            fila[f"smape_nacional_{nombre}"] = smape_percent(g["y_true_cases"], g["y_pred_cases"])
        q = sv.cuantiles(previo[previo["engine"] == fila["motor_v2"]], catalog, reglas)
        p = sv.productos(
            eval_[eval_["engine"] == fila["motor_v2"]].drop(columns="engine"),
            catalog,
            ["y_true_cases", "y_pred_cases"],
        ).merge(q, on=sv.LLAVE)
        r = np.log1p(p["y_true_cases"]) - np.log1p(p["y_pred_cases"])
        for n in reglas.niveles:
            fila[f"cobertura_{n}"] = float(
                ((r >= p[f"q_lo_{n}"]) & (r <= p[f"q_hi_{n}"])).mean() * 100
            )
        filas.append(fila)
    return filas


def _commit(root: Path) -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    return out.stdout.strip()


def emitir(
    diseases: list[str], catalog: GeoCatalog, reglas: sv.Reglas, root: Path = _ROOT
) -> dict[str, Any]:
    """Una emisión congelada por padecimiento; nunca sobrescribe una emisión previa."""
    ahora = datetime.now(UTC)
    staging = root / "runs" / "sombra_v2" / f"_staging_{ahora:%Y%m%dT%H%M%S}"
    staging.mkdir(parents=True, exist_ok=False)
    entradas = []
    for d in diseases:
        ev = desarrollo(d, reglas, root)
        sel = sv.seleccionar(sv.metricas_desarrollo(ev), reglas)
        q = sv.cuantiles(ev[ev["engine"] == sel["engine"]].drop(columns="engine"), catalog, reglas)
        oid, csv = observacion(d, root)
        fc = sv.pronostico(read_base_history(csv), sel["engine"], reglas, q, catalog)
        fc.insert(0, "disease_id", d)
        destino = staging / f"{d}.csv"
        fc.to_csv(destino, index=False)
        entradas.append(
            sel
            | {
                "disease_id": d,
                "release_id": release_dir(d, root).name,
                "observation_dataset_id": oid,
                "observation_sha256": _sha(csv),
                "origen": list(fc.attrs["origen"]),
                "forecast_sha256": _sha(destino),
                "filas": len(fc),
            }
        )
        print(
            json.dumps({k: entradas[-1][k] for k in ("disease_id", "engine", "origen")}),
            flush=True,
        )
    huella = hashlib.sha256("".join(e["forecast_sha256"] for e in entradas).encode()).hexdigest()
    eid = f"sombra_v2_{ahora:%Y%m%d}_{huella[:10]}"
    indice = {
        "schema": SCHEMA,
        "emision_id": eid,
        "emitida_utc": ahora.isoformat(),
        "code_commit": _commit(root),
        "config_sha256": _sha(sv.CONFIG),
        "padecimientos": entradas,
    }
    destino_dir = root / "runs" / "sombra_v2" / eid
    staging.rename(destino_dir)  # falla si la emisión ya existía
    texto = json.dumps(indice, ensure_ascii=False, indent=1) + "\n"
    (destino_dir / "emision.json").write_text(texto, encoding="utf-8")
    doc = root / "docs" / "sombra_v2" / "emisiones" / f"{eid}.json"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(texto, encoding="utf-8")
    return indice


def validar(eid: str, catalog: GeoCatalog, reglas: sv.Reglas, root: Path = _ROOT) -> pd.DataFrame:
    """Compara sombra, publicado y control en semanas posteriores al origen con verdad completa."""
    edir = root / "runs" / "sombra_v2" / eid
    indice = _json(edir / "emision.json")
    filas = []
    for e in indice["padecimientos"]:
        d = e["disease_id"]
        f = edir / f"{d}.csv"
        if _sha(f) != e["forecast_sha256"]:
            raise sv.SombraError(f"{d}: la emisión congelada cambió")
        em = pd.read_csv(f, dtype={"geography_id": str})
        origen = tuple(e["origen"])
        oid, csv = observacion(d, root)
        historia = read_base_history(csv)
        semanas = sorted(
            {p for h in historia.values() for p in h if p > origen}
            & set(zip(em["epi_year"], em["epi_week"], strict=True))
        )
        semanas = [p for p in semanas if all(p in h for h in historia.values())]
        fila: dict[str, Any] = {"disease_id": d, "observacion": oid, "engine": e["engine"]}
        if semanas:
            base = pd.DataFrame(
                [
                    {
                        "geography_id": g,
                        "sex": s,
                        "epi_year": p[0],
                        "epi_week": p[1],
                        "y_true_cases": historia[(g, s)][p],
                    }
                    for (g, s) in historia
                    for p in semanas
                ]
            )
            verdad = sv.productos(base, catalog, ["y_true_cases"])
            pub = pd.read_csv(
                root
                / "artifacts"
                / "releases"
                / d
                / e["release_id"]
                / "forecast"
                / "forecast.csv",
                dtype={"geography_id": str},
            )
            pub = pub[[*sv.LLAVE, *sv.PERIODO, "y_pred_cases"]]
            fila |= sv.evaluar(em, verdad, pub, reglas.niveles)
        else:
            fila["semanas"] = 0
        filas.append(fila)
    out = pd.DataFrame(filas)
    out.to_csv(edir / "validacion.csv", index=False)
    return out
