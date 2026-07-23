"""Selector productivo genérico por padecimiento (EPIC 3 + gate lifecycle, Fase 1).

Despacha por ``selection_policy`` del registry y aplica la regla canónica
(``epiforecast.selection.select_engine``: sMAPE→MASE→RMSE + banda 5% + orden estable)
sobre los motores ELEGIBLES del padecimiento, usando las métricas CV por serie de cada
``{Motor}_{Padecimiento}_completo.csv``.

**Lifecycle gate (contrato Fase 1):** un padecimiento no ``published`` NO puede recrear una
selección canónica. Solo ``lifecycle=published`` escribe ``reports/ProdDetails/produccion_<slug>.csv``
etiquetado con su ``selection_policy``. Un padecimiento ``configured``/``trained`` aborta sin escribir,
salvo ``--allow-preliminary``, que emite un CSV **PRELIMINAR** bajo ``_preliminar_NO_GO/`` con criterio
``insample_cv_PRELIMINAR_NO_GO`` (nunca la etiqueta de la política: este selector usa métricas CV
*in-sample*, no un rolling-origin OOS real). Ver ``resolve_destination``.

Nota: los motores no entrenados se omiten (se registra cuáles se usaron).

Uso: .venv/bin/python -m scripts.produccion_padecimiento --disease Obesidad [--allow-preliminary]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from epiforecast import registry
from epiforecast.selection import Candidate, select_engine
from epiforecast.utils.config import logger

ROOT = Path(__file__).resolve().parent.parent
_ENGINE_CAP = {
    "prophet": "Prophet",
    "deepar": "DeepAR",
    "ensemble": "Ensemble",
    "stacking": "Stacking",
    "nbglm": "NBGLM",
}
_SEXO_MAP = {
    "incrementos_hombres": "hombres",
    "incrementos_mujeres": "mujeres",
    "incrementos_total": "general",
}

# ── Lifecycle gate (contrato Fase 1) ──
_PRELIMINAR_DIRNAME = "_preliminar_NO_GO"
_PRELIMINAR_CRITERIO = "insample_cv_PRELIMINAR_NO_GO"


@dataclass(frozen=True)
class Destination:
    """Destino resuelto del CSV de selección + etiqueta de criterio honesta."""

    path: Path
    criterio: str
    canonical: bool


def resolve_destination(
    d: registry.Disease, root: Path, *, allow_preliminary: bool
) -> Destination | None:
    """Lifecycle gate: decide DÓNDE (y SI) puede escribir el selector.

    - ``published``: ruta CANÓNICA ``reports/ProdDetails/produccion_<slug>.csv``; criterio =
      ``selection_policy`` del registry (comportamiento legacy, sin cambios).
    - ``configured``/``trained`` **sin** ``allow_preliminary``: ``None`` (GATED — no se permite
      escribir nada; un padecimiento no publicado NO puede recrear una selección canónica).
    - ``configured``/``trained`` **con** ``allow_preliminary``: ruta PRELIMINAR bajo
      ``_preliminar_NO_GO/`` con sufijo ``_PRELIMINAR`` y criterio ``insample_cv_PRELIMINAR_NO_GO``
      — NUNCA la etiqueta de la política, porque este selector usa métricas CV *in-sample*, no un
      rolling-origin OOS real.
    """
    proddetails = root / "reports" / "ProdDetails"
    if d.lifecycle == "published":
        return Destination(proddetails / f"produccion_{d.slug}.csv", d.selection_policy, True)
    if not allow_preliminary:
        return None
    return Destination(
        proddetails / _PRELIMINAR_DIRNAME / f"produccion_{d.slug}_PRELIMINAR.csv",
        _PRELIMINAR_CRITERIO,
        False,
    )


def _load_engine_metrics(artifact_key: str, engine: str) -> pd.DataFrame | None:
    cap = _ENGINE_CAP.get(engine, engine.capitalize())
    path = ROOT / "models" / engine / artifact_key / f"{cap}_{artifact_key}_completo.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["entidad"] = df["Entidad"].fillna("Nacional").astype(str) if "Entidad" in df else "Nacional"
    df["sexo"] = df["sexo"].map(lambda s: _SEXO_MAP.get(str(s), str(s)))
    out = df[["entidad", "sexo", "smape", "mase", "rmse"]].copy()
    out["motor"] = engine
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disease", required=True)
    ap.add_argument(
        "--allow-preliminary",
        action="store_true",
        help=(
            "Permite emitir un CSV PRELIMINAR (bajo _preliminar_NO_GO/) para un padecimiento no "
            "publicado. Sin este flag, un padecimiento configured/trained aborta sin escribir."
        ),
    )
    args = ap.parse_args(argv)

    d = registry.require(args.disease)
    logger.info(
        "Selector {} | lifecycle={} | política={} | motores elegibles={}",
        d.data_name,
        d.lifecycle,
        d.selection_policy,
        list(d.eligible_engines),
    )

    dest = resolve_destination(d, ROOT, allow_preliminary=args.allow_preliminary)
    if dest is None:
        logger.error(
            "GATE lifecycle: '{}' está en lifecycle={} (no 'published'). El selector NO recrea la "
            "ruta canónica produccion_{}.csv de un padecimiento no publicado. Usa "
            "--allow-preliminary para emitir un CSV PRELIMINAR en reports/ProdDetails/{}/.",
            d.data_name,
            d.lifecycle,
            d.slug,
            _PRELIMINAR_DIRNAME,
        )
        return 2

    metricas: dict[str, pd.DataFrame] = {}
    for engine in d.eligible_engines:
        m = _load_engine_metrics(d.artifact_key, engine)
        if m is not None:
            metricas[engine] = m
    if not metricas:
        logger.error("Ningún motor entrenado para {} — corre entrena primero.", d.data_name)
        return 1
    faltantes = [e for e in d.eligible_engines if e not in metricas]
    if faltantes:
        logger.warning("Motores elegibles SIN entrenar (omitidos): {}", faltantes)

    # Series = unión de (entidad, sexo) de todos los motores disponibles.
    todas = pd.concat(metricas.values(), ignore_index=True)
    series = todas[["entidad", "sexo"]].drop_duplicates().itertuples(index=False)

    rows: list[dict] = []
    for entidad, sexo in series:
        cands: list[Candidate] = []
        detalle: dict[str, float] = {}
        for engine, mdf in metricas.items():
            sel = mdf[(mdf.entidad == entidad) & (mdf.sexo == sexo)]
            if sel.empty:
                continue
            r = sel.iloc[0]
            cands.append(
                Candidate(engine, smape=_num(r.smape), mase=_num(r.mase), rmse=_num(r.rmse))
            )
            detalle[f"smape_{engine}"] = _num(r.smape)
            detalle[f"mase_{engine}"] = _num(r.mase)
        ganador = select_engine(cands)
        rows.append(
            {
                "padecimiento": d.data_name,
                "entidad": entidad,
                "sexo": sexo,
                "motor_productivo": _ENGINE_CAP.get(ganador, ganador) if ganador else None,
                "criterio_seleccion": dest.criterio,
                "motores_evaluados": ",".join(sorted(metricas)),
                **detalle,
            }
        )

    prod = pd.DataFrame(rows).sort_values(["entidad", "sexo"]).reset_index(drop=True)
    dest.path.parent.mkdir(parents=True, exist_ok=True)
    prod.to_csv(dest.path, index=False, encoding="utf-8")

    dist = prod["motor_productivo"].value_counts().to_dict()
    logger.success(
        "Producción {} ({}): {} series | distribución motor {} -> {}",
        d.data_name,
        "CANÓNICA" if dest.canonical else "PRELIMINAR/NO-GO",
        len(prod),
        dist,
        dest.path,
    )
    return 0


def _num(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
