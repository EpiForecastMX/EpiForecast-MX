"""Selector productivo genérico por padecimiento (EPIC 3 + gates Fase 1).

Aplica la regla canónica (``epiforecast.selection.select_engine``: sMAPE→MASE→RMSE + banda
5% + orden estable) sobre los motores ELEGIBLES del padecimiento, usando las métricas CV por
serie de cada ``{Motor}_{Padecimiento}_completo.csv``.

**Gate de lifecycle + ownership (contrato Fase 1):** ``resolve_destination`` decide dónde (y si)
puede escribir.

- Un padecimiento NO ``published`` no puede recrear una selección canónica: aborta sin escribir,
  salvo ``--allow-preliminary``, que emite un CSV **PRELIMINAR** bajo ``_preliminar_NO_GO/`` con
  criterio ``insample_cv_PRELIMINAR_NO_GO`` (nunca la etiqueta de la política: este selector usa
  métricas CV *in-sample*, no un rolling-origin OOS real).
- Un padecimiento ``published`` es dominio de su selector DEDICADO (neuro: ``reselect_motor_2026``;
  Dengue: ``produccion_dengue``). El genérico NO reproduce ``legacy_neuro_2026``/``legacy_dengue_2026``
  (solo copiaría la etiqueta y emitiría un esquema distinto — ~16 vs 30 columnas, rompería
  ``build_web_knowledge``), así que **rechaza** toda escritura canónica sin un adapter explícito
  registrado en ``_GENERIC_CANONICAL_POLICIES`` y reserva los artefactos de ``_DEDICATED_ARTIFACTS``.

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
# Etiqueta de DISPLAY para ``motor_productivo`` (convención del proyecto: DeepAR/NBGLM).
# NO sirve para construir nombres de archivo — ver ``_engine_file_prefix``.
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


def _engine_file_prefix(engine: str) -> str:
    """Prefijo REAL en disco del CSV de métricas (case-sensitive en Linux/CI).

    Los archivos son ``Prophet_``/``Deepar_``/``Ensemble_``/``Stacking_``/``Nbglm_`` (title-case),
    NO el display ``_ENGINE_CAP`` (``DeepAR``/``NBGLM``): usar ese mapa para el nombre de archivo
    encuentra el CSV en macOS (FS case-insensitive) y FALLA en Linux.
    """
    return engine.capitalize()


# ── Lifecycle gate (contrato Fase 1) ──
_PRELIMINAR_DIRNAME = "_preliminar_NO_GO"
_PRELIMINAR_CRITERIO = "insample_cv_PRELIMINAR_NO_GO"

# ── Ownership / policy gate (contrato Fase 1, P0) ──
# Políticas que el selector GENÉRICO reproduce de verdad para una escritura CANÓNICA. Vacío:
# no reproduce legacy_neuro_2026 (reselect_motor_2026.py) ni legacy_dengue_2026
# (produccion_dengue.py) ni un rolling_cv_v1 OOS real. Hasta que exista un adapter validado
# fila-por-fila contra el selector dedicado, el genérico NO escribe artefactos canónicos.
_GENERIC_CANONICAL_POLICIES: frozenset[str] = frozenset()

# Artefactos canónicos con dueño DEDICADO — el genérico nunca los escribe, ni con adapter.
_DEDICATED_ARTIFACTS: frozenset[str] = frozenset({"produccion_dengue.csv"})


@dataclass(frozen=True)
class Destination:
    """Destino resuelto del CSV de selección + etiqueta de criterio honesta."""

    path: Path
    criterio: str
    canonical: bool


def resolve_destination(
    d: registry.Disease, root: Path, *, allow_preliminary: bool
) -> Destination | None:
    """Gate de lifecycle + ownership: decide DÓNDE (y SI) puede escribir el genérico.

    - ``published`` con política en ``_GENERIC_CANONICAL_POLICIES`` y artefacto NO reservado:
      ruta CANÓNICA ``reports/ProdDetails/produccion_<slug>.csv``; criterio = ``selection_policy``.
    - ``published`` sin adapter registrado, o cuyo artefacto está en ``_DEDICATED_ARTIFACTS``:
      ``None`` (dominio del selector dedicado; el genérico no reproduce esa política ni lo pisa).
    - ``configured``/``trained`` **sin** ``allow_preliminary``: ``None`` (un padecimiento no
      publicado NO puede recrear una selección canónica).
    - ``configured``/``trained`` **con** ``allow_preliminary``: ruta PRELIMINAR bajo
      ``_preliminar_NO_GO/`` con criterio ``insample_cv_PRELIMINAR_NO_GO`` — NUNCA la política.
    """
    proddetails = root / "reports" / "ProdDetails"
    canonical = proddetails / f"produccion_{d.slug}.csv"

    if d.lifecycle == "published":
        if (
            d.selection_policy not in _GENERIC_CANONICAL_POLICIES
            or canonical.name in _DEDICATED_ARTIFACTS
        ):
            return None
        return Destination(canonical, d.selection_policy, True)

    if not allow_preliminary:
        return None
    return Destination(
        proddetails / _PRELIMINAR_DIRNAME / f"produccion_{d.slug}_PRELIMINAR.csv",
        _PRELIMINAR_CRITERIO,
        False,
    )


def _load_engine_metrics(artifact_key: str, engine: str) -> pd.DataFrame | None:
    prefix = _engine_file_prefix(engine)
    path = ROOT / "models" / engine / artifact_key / f"{prefix}_{artifact_key}_completo.csv"
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

    if args.allow_preliminary and d.lifecycle == "published":
        logger.error(
            "--allow-preliminary no aplica a un padecimiento published ('{}'): su selección "
            "canónica es dominio del selector dedicado, no un preliminar.",
            d.data_name,
        )
        return 2

    dest = resolve_destination(d, ROOT, allow_preliminary=args.allow_preliminary)
    if dest is None:
        if d.lifecycle == "published":
            logger.error(
                "GATE ownership: '{}' (published, política '{}') es dominio del selector DEDICADO "
                "(reselect_motor_2026.py / produccion_dengue.py). El genérico no reproduce esa "
                "política ni escribe su artefacto canónico produccion_{}.csv.",
                d.data_name,
                d.selection_policy,
                d.slug,
            )
        else:
            logger.error(
                "GATE lifecycle: '{}' está en lifecycle={} (no 'published'). Usa --allow-preliminary "
                "para emitir un CSV PRELIMINAR en reports/ProdDetails/{}/.",
                d.data_name,
                d.lifecycle,
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
