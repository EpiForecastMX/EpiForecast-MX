"""C7.7 — Vista pública derivada de un release publicado: observado + pronóstico + desempeño.

El shard del release es inmutable y sólo describe el PRONÓSTICO sellado. La página del sitio y el
EpiBot necesitan además lo OBSERVADO (que avanza con cada boletín) para mostrar honestamente cómo
le va al pronóstico congelado. Este comando lo deriva sin decidir nada:

- el pronóstico sale del ``web/series.csv`` de un shard PÚBLICO cuya integridad se comprueba contra
  su ``shard_manifest.json`` (digest por archivo);
- lo observado sale del dataset de observación DECLARADO en la validación prospectiva
  (``config/publication/<id>/prospective_status.json``), nunca de una ruta pasada a mano;
- el desempeño fuera de muestra se calcula sólo sobre semanas posteriores al origen del release y
  con verdad observada: sMAPE (misma fórmula que el runner), MAE y sesgo.

    python -m scripts.publication_view obesidad \\
        --shard-root runs/publication/compile_a/obesidad/<release_id> --out vista.json
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd

from epiforecast import registry
from epiforecast.publication.status import load_declared_status
from epiforecast.runner.artifact_identity import ArtifactValidationError, equal, require
from epiforecast.runner.release_loader import VerifiedRelease, verify_bundle
from epiforecast.runner.release_sources import ACCEPTANCE_FILE, DIR_SELECTION
from epiforecast.runner.release_store import default_releases_root, release_path

VIEW_SCHEMA = "publication_view.v1"
_REPO = Path(__file__).resolve().parents[1]
CATALOGO = _REPO / "config" / "geografia" / "entidades_mx.csv"
OBSERVACIONES = _REPO / "artifacts" / "observations"
# Historia visible: desde 2023 basta para ver tres estaciones completas antes del origen.
ANIO_HISTORIA = 2023
SEXOS = {"general": "General", "hombres": "Hombres", "mujeres": "Mujeres"}


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _verifica_shard(raiz: Path, disease_id: str, release_id: str) -> dict[str, Any]:
    manifiesto = json.loads((raiz / "shard_manifest.json").read_text("utf-8"))
    equal("vista: modo del shard", manifiesto.get("mode"), "public")
    equal("vista: padecimiento del shard", manifiesto.get("disease_id"), disease_id)
    equal("vista: release del shard", manifiesto.get("release_id"), release_id)
    for rel, digest in sorted(manifiesto["files"].items()):
        equal(f"vista: digest de {rel}", _sha256(raiz / rel), digest)
    return dict(manifiesto)


def _nombres() -> dict[tuple[str, str], str]:
    nombres: dict[tuple[str, str], str] = {("nacional", "mx"): "Nacional"}
    with CATALOGO.open(encoding="utf-8") as fh:
        for fila in csv.DictReader(fh):
            nombres[("estado", fila["cve_ent"])] = fila["nombre_canonico"]
            nombres[("region", fila["macroregion_id"])] = f"Región {fila['macroregion_name']}"
    return nombres


def emision_del_pronostico(bundle: Path) -> str:
    """Instante en que se escribió el pronóstico sellado (``forecast/run_manifest.json``).

    Es la fecha que sostiene cualquier afirmación prospectiva: las semanas evaluadas sólo son
    «futuras» respecto de lo que se sabía en ese momento. Se lee del bundle ya verificado.
    """
    manifiesto = json.loads((bundle / "forecast" / "run_manifest.json").read_text("utf-8"))
    equal("vista: comando del pronóstico", manifiesto.get("command"), "forecast")
    creado = manifiesto.get("created_at")
    require(isinstance(creado, str) and creado.endswith("+00:00"), "vista: created_at sin UTC")
    return str(creado)


def _smape(y: pd.Series, f: pd.Series) -> float:
    den = y.abs() + f.abs()
    term = (2.0 * (y - f).abs() / den).where(den > 0, 0.0)
    return float(100.0 * term.mean())


def _num(valor: float) -> float | None:
    return None if valor is None or not math.isfinite(valor) else round(float(valor), 2)


def tras_origen(cruce: pd.DataFrame, origen: tuple[int, int]) -> pd.DataFrame:
    """Filas posteriores al origen; con 0 semanas observadas, frame vacío con sus columnas."""
    posteriores = pd.Series(
        [(a, s) > origen for a, s in zip(cruce["epi_year"], cruce["epi_week"], strict=True)],
        index=cruce.index,
        dtype=bool,
    )
    return cruce.loc[posteriores]


def caida_al_control(bundle: Path, verificado: VerifiedRelease) -> dict[str, Any] | None:
    """Qué rechazó el gate cuando lo publicado es el control; ``None`` en un release aceptado.

    Las cifras salen del veredicto sellado dentro del bundle, nunca se escriben a mano.
    """
    resultado = verificado.chain.get("acceptance_outcome")
    if resultado is None:
        return None
    acta = json.loads((bundle / DIR_SELECTION / ACCEPTANCE_FILE).read_text("utf-8"))
    return {
        "resultado": resultado,
        "motor": acta["rule"]["control_engine"],
        "fold": acta["provenance"]["fold_id"],
        "comprobaciones": [
            {
                "ambito": check["scope"],
                "portafolio": round(float(check["portfolio"]), 1),
                "control": round(float(check["control"]), 1),
                "pasa": bool(check["passed"]),
            }
            for check in acta["checks"]
        ],
    }


def build_view(disease_id: str, shard_root: Path) -> dict[str, Any]:
    disease = registry.require(disease_id)
    equal(f"{disease.id}: lifecycle", disease.lifecycle, "published")
    estado = load_declared_status(disease.id)
    release_id = estado.release_id
    manifiesto = _verifica_shard(shard_root, disease.id, release_id)
    bundle = release_path(default_releases_root(), disease.id, release_id)
    verificado = verify_bundle(bundle)
    emitido = emision_del_pronostico(bundle)
    web = json.loads((shard_root / "web" / "manifest.json").read_text("utf-8"))

    obs_id = estado.status.observation_dataset_id
    productos = OBSERVACIONES / disease.id / obs_id / "products.csv"
    require(productos.is_file(), f"vista: falta la observación declarada {obs_id}")
    obs = pd.read_csv(productos, dtype={"geography_id": str})
    obs = obs[obs["observed"].astype(bool)]
    pron = pd.read_csv(shard_root / "web" / "series.csv", dtype={"geography_id": str})

    origen = tuple(web["origin"])
    claves = ["geography_level", "geography_id", "sex"]
    nombres = _nombres()
    ultima_obs = obs[["epi_year", "epi_week", "ds"]].sort_values(["epi_year", "epi_week"]).iloc[-1]

    series: dict[str, Any] = {}
    for clave, grupo in pron.groupby(claves, sort=True):
        nivel, geo, sexo = (str(x) for x in clave)
        nombre = nombres.get((nivel, geo))
        require(nombre is not None, f"vista: geografía sin nombre {nivel}/{geo}")
        grupo = grupo.sort_values(["epi_year", "epi_week"])
        o = obs[
            (obs["geography_level"] == nivel) & (obs["geography_id"] == geo) & (obs["sex"] == sexo)
        ].sort_values(["epi_year", "epi_week"])
        historia = o[o["epi_year"] >= ANIO_HISTORIA]
        cruce = grupo.merge(o[["epi_year", "epi_week", "y_cases"]], on=["epi_year", "epi_week"])
        cruce = tras_origen(cruce, origen)
        motores = sorted(set(grupo["engine"]))
        # Los puntos se publican a un decimal; el total de 52 semanas es la suma de ESOS puntos,
        # para que ningún consumidor (acumulados, tablas) vea dos cifras distintas.
        puntos = [round(float(y), 1) for y in grupo["yhat_cases"]]
        series[f"{nivel}|{geo}|{sexo}"] = {
            "nivel": nivel,
            "id": geo,
            "nombre": str(nombre),
            "sexo": sexo,
            "sexo_nombre": SEXOS[sexo],
            "motor": motores[0] if len(motores) == 1 else "portafolio",
            "observado": [
                [str(d), int(y)] for d, y in zip(historia["ds"], historia["y_cases"], strict=True)
            ],
            "pronostico": [[str(d), y] for d, y in zip(grupo["ds"], puntos, strict=True)],
            "oos": {
                "semanas": int(len(cruce)),
                "smape": _num(_smape(cruce["y_cases"], cruce["yhat_cases"]))
                if len(cruce)
                else None,
                "mae": _num((cruce["y_cases"] - cruce["yhat_cases"]).abs().mean())
                if len(cruce)
                else None,
                "sesgo_pct": _num(
                    100.0 * (cruce["yhat_cases"].sum() / cruce["y_cases"].sum() - 1.0)
                )
                if len(cruce) and cruce["y_cases"].sum() > 0
                else None,
                "observado_total": int(cruce["y_cases"].sum()),
                "pronostico_total": round(float(cruce["yhat_cases"].sum()), 1),
            },
            "pronostico_52_total": round(sum(puntos), 1),
        }

    vista: dict[str, Any] = {
        "schema": VIEW_SCHEMA,
        "disease_id": disease.id,
        "display_name": disease.display_name,
        "nombre_completo": disease.web.get("nombre_completo"),
        "color": disease.web.get("color"),
        "release_id": release_id,
        "origin": list(origen),
        "forecast_emitted_at": emitido,
        "horizon_weeks": int(web["horizon_weeks"]),
        "publication_label": web["publication_label"],
        "uncertainty_label": web["uncertainty_label"],
        "verdict": estado.verdict,
        "weeks_required": estado.status.weeks_required,
        "weeks_available": estado.status.weeks_available,
        "observation_dataset_id": obs_id,
        "observation_cutoff": [int(ultima_obs["epi_year"]), int(ultima_obs["epi_week"])],
        "observation_cutoff_ds": str(ultima_obs["ds"]),
        "engines": web["engines"],
        "models": int(web["models"]),
        "products": int(web["products"]),
        "shard_manifest_files": manifiesto["files"],
        "series": series,
    }
    control = caida_al_control(bundle, verificado)
    if control is not None:
        vista["caida_al_control"] = control
    return vista


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    ap.add_argument("disease_id")
    ap.add_argument("--shard-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        vista = build_view(args.disease_id, args.shard_root)
    except (ArtifactValidationError, KeyError, ValueError, OSError) as exc:
        print(f"ERROR: vista de {args.disease_id}: {exc}", file=sys.stderr)
        return 1
    datos = json.dumps(vista, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(datos + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "series": len(vista["series"]),
                "observation_cutoff": vista["observation_cutoff"],
                "bytes": len(datos),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
