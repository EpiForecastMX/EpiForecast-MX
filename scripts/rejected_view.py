"""Vista de un padecimiento analizado y RECHAZADO por el gate de aceptación.

No publica el padecimiento: exige ``lifecycle=trained``, sin canales y con la caída al control
sellada en la cadena del release. Es una foto fija para la sección de rechazados: lo que pasó en el
año de prueba (observado, portafolio y control) y la referencia del control a 52 semanas. No entra
al catálogo, al paso semanal ni a la paridad del consolidado.

Las cifras salen de los runs sellados y del release; aquí no se reentrena ni se reabre nada.

Uso:
    python -m scripts.rejected_view covid_19 --out <frontend>/publication/rechazados/covid_19.json
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd
from scripts.publication_view import SEXOS, _nombres, emision_del_pronostico

from epiforecast import registry
from epiforecast.runner import contracts as ct
from epiforecast.runner import selection
from epiforecast.runner.artifact_identity import ArtifactValidationError, equal, require
from epiforecast.runner.evaluation import smape_percent
from epiforecast.runner.policy import load_policy
from epiforecast.runner.release_loader import verify_bundle
from epiforecast.runner.release_sources import ACCEPTANCE_FILE, DIR_SELECTION
from epiforecast.runner.release_store import default_releases_root, release_path

VIEW_SCHEMA = "rejected_view.v1"
_REPO = Path(__file__).resolve().parents[1]
# Desde 2024: los años previos tienen otra escala y aplastarían la gráfica.
ANIO_HISTORIA = 2024
CLAVES = ["geography_level", "geography_id", "sex"]
ORDEN = ["epi_year", "epi_week"]


def exige_rechazo(disease: registry.Disease, chain: Mapping[str, str]) -> None:
    """Sólo un padecimiento sin publicar, con la caída al control autorizada y sellada."""
    equal(f"{disease.id}: lifecycle", disease.lifecycle, "trained")
    require(not disease.channels, f"{disease.id}: un rechazado no declara canales")
    require(
        chain.get("acceptance_outcome") == "fallback_control", f"{disease.id}: no cayó al control"
    )
    equal(
        f"{disease.id}: run autorizado",
        disease.acceptance_fallback_run,
        chain["acceptance_run_id"],
    )


def comprobaciones(acta: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Las comprobaciones del gate, sin redondear el veredicto: sale tal cual del acta sellada."""
    return [
        {
            "ambito": c["scope"],
            "portafolio": round(float(c["portfolio"]), 1),
            "control": round(float(c["control"]), 1),
            "peor_pct": round(float(c["worse_pct"]), 1),
            "maximo_pct": float(c["max_worse_pct"]),
            "pasa": bool(c["passed"]),
        }
        for c in acta["checks"]
    ]


def prueba_serie(portafolio: pd.DataFrame, control: pd.DataFrame) -> dict[str, Any]:
    """Semanas del año de prueba de una serie: observado, portafolio, control y su sMAPE."""
    cruce = portafolio.merge(control, on=[*ORDEN, "ds"], suffixes=("_p", "_c")).sort_values(ORDEN)
    equal("prueba: semanas cruzadas", len(cruce), len(portafolio))
    verdad = [float(v) for v in cruce["y_true_cases_p"]]
    return {
        "ds": [str(d) for d in cruce["ds"]],
        "observado": [int(v) for v in verdad],
        "portafolio": [round(float(v), 1) for v in cruce["y_pred_cases_p"]],
        "control": [round(float(v), 1) for v in cruce["y_pred_cases_c"]],
        "smape_portafolio": round(float(smape_percent(verdad, list(cruce["y_pred_cases_p"]))), 1),
        "smape_control": round(float(smape_percent(verdad, list(cruce["y_pred_cases_c"]))), 1),
    }


def _portafolio_prueba(
    disease: registry.Disease, runs: Path, acta: Mapping[str, Any], productos: pd.DataFrame
) -> pd.DataFrame:
    """Reconstruye la evaluación del portafolio rechazado con la selección congelada."""
    test_dir = runs / acta["provenance"]["run_id"]
    sel, _ = selection.load_frozen_selection(runs / acta["provenance"]["selection_run_id"])
    motores = sorted(set(sel["selected_engine"]))
    frames = {
        m: pd.read_csv(test_dir / "artifacts" / m / "forecast.csv", dtype={"geography_id": str})
        for m in motores
    }
    base = selection.compose_base_forecast(frames, sel, str(acta["provenance"]["run_id"]))
    evaluacion, _ = selection.evaluate_portfolio(
        base, productos, load_policy(disease.selection_policy), ct.SPLIT_TEST
    )
    return evaluacion


def sexo_estimado_pct(flags: pd.Series) -> float:
    """% de filas con el reparto por sexo estimado. Un total discordante no es una estimación."""
    return round(float(flags.str.contains("sex_fallback").mean()) * 100.0, 1)


def build_view(disease_id: str, runs: Path) -> dict[str, Any]:
    disease = registry.require(disease_id)
    release_id = str(disease.artifact_source.release_id)
    bundle = release_path(default_releases_root(), disease.id, release_id)
    verificado = verify_bundle(bundle)
    exige_rechazo(disease, verificado.chain)
    acta = json.loads((bundle / DIR_SELECTION / ACCEPTANCE_FILE).read_text("utf-8"))

    ruta = runs / verificado.chain["dataset_id"] / "products.csv"
    productos = pd.read_csv(ruta, dtype={"geography_id": str})
    productos["observed"] = productos["observed"].astype(bool)
    productos = productos.assign(quality_flags=productos["quality_flags"].fillna(""))
    # La evaluación exige la forma original de los productos del run.
    portafolio = _portafolio_prueba(disease, runs, acta, productos)
    control = pd.read_csv(
        runs
        / acta["provenance"]["run_id"]
        / "artifacts"
        / acta["rule"]["control_engine"]
        / "evaluation.csv",
        dtype={"geography_id": str},
    )
    pron = pd.read_csv(bundle / "forecast" / "forecast.csv", dtype={"geography_id": str})

    obs = productos[productos["observed"]]
    nombres = _nombres()
    series: dict[str, Any] = {}
    grupos_p = dict(tuple(portafolio.groupby(CLAVES, sort=True)))
    grupos_c = dict(tuple(control.groupby(CLAVES, sort=True)))
    grupos_o = dict(tuple(obs[obs["epi_year"] >= ANIO_HISTORIA].groupby(CLAVES, sort=True)))
    for clave, grupo in pron.groupby(CLAVES, sort=True):
        nivel, geo, sexo = (str(x) for x in clave)
        nombre = nombres.get((nivel, geo))
        require(nombre is not None, f"vista: geografía sin nombre {nivel}/{geo}")
        grupo = grupo.sort_values(ORDEN)
        puntos = [round(float(y), 1) for y in grupo["y_pred_cases"]]
        historia = grupos_o[clave].sort_values(ORDEN)
        series[f"{nivel}|{geo}|{sexo}"] = {
            "nivel": nivel,
            "id": geo,
            "nombre": str(nombre),
            "sexo": sexo,
            "sexo_nombre": SEXOS[sexo],
            "observado": [
                [str(d), int(y)] for d, y in zip(historia["ds"], historia["y_cases"], strict=True)
            ],
            "pronostico": [[str(d), y] for d, y in zip(grupo["ds"], puntos, strict=True)],
            "pronostico_52_total": round(sum(puntos), 1),
            "prueba": prueba_serie(grupos_p[clave], grupos_c[clave]),
        }

    nacional = obs[(obs["geography_level"] == "nacional") & (obs["sex"] == "general")]
    bases = obs[(obs["geography_level"] == "estado") & (obs["sex"] != "general")]
    recientes = bases[bases["epi_year"] >= ANIO_HISTORIA]
    ultima = obs.sort_values(ORDEN).iloc[-1]
    return {
        "schema": VIEW_SCHEMA,
        "disease_id": disease.id,
        "display_name": disease.display_name,
        "nombre_completo": disease.web.get("nombre_completo"),
        "release_id": release_id,
        "origin": list(verificado.origin),
        "forecast_emitted_at": emision_del_pronostico(bundle),
        "horizon_weeks": verificado.horizon,
        "motor": acta["rule"]["control_engine"],
        "motores_portafolio": sorted(set(acta["engines_in_run"])),
        "fold": acta["provenance"]["fold_id"],
        "comprobaciones": comprobaciones(acta),
        "observation_cutoff": [int(ultima["epi_year"]), int(ultima["epi_week"])],
        "observation_cutoff_ds": str(ultima["ds"]),
        "casos_por_anio": {
            str(a): int(v) for a, v in nacional.groupby("epi_year")["y_cases"].sum().items()
        },
        "sexo_estimado_pct": sexo_estimado_pct(recientes["quality_flags"]),
        "series": series,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("disease")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--runs", type=Path, default=_REPO / "runs")
    args = parser.parse_args(argv)
    try:
        vista = build_view(args.disease, args.runs)
    except ArtifactValidationError as exc:
        print(f"[rejected-view] FALLA: {exc}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(vista, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    args.out.write_text(texto, encoding="utf-8")
    print(json.dumps({"out": str(args.out), "series": len(vista["series"]), "bytes": len(texto)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
