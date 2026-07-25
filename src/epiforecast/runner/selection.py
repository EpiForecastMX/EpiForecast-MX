"""F2/C5.1 — selector por SeriesKey CONSCIENTE DE COMPLEJIDAD sobre ``rolling_cv_v1``.

Selector NUEVO del carril E66: no reutiliza nada de la lógica legacy (baja incidencia, modelos
regionales, reglas por padecimiento). Consume un run de benchmark ya ejecutado y congela un mapa
serie→motor; no entrena, no toca 2025 y no elige motor para agregados.

Regla (declarada en ``config/evaluation/<policy>.yaml``, clave ``selection``):
1. Por SeriesKey base, mediana de sMAPE/MASE/RMSE sobre los folds de development (2021-24).
2. Mejor sMAPE entre los **incumbents**; mejor sMAPE entre los **challengers**.
3. El tier challenger se abre SOLO si mejora al incumbent ≥ ``challenger_min_improvement_pct``.
4. Dentro del tier elegido, banda de candidatos hasta ``band_pct`` del mejor.
5. Se resuelve por MASE → RMSE → **costo declarativo** (no wall-clock) → nombre del motor.

Los 47 productos derivados NUNCA eligen motor: se reconstruyen sumando las 64 bases seleccionadas.
El ``selection_digest`` (regla + mapa + procedencia) entra en la identidad de todo lo posterior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from epiforecast.data.epi_dataset_spec import (
    BASE_SEXES,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
    GEO_LEVEL_ESTADO,
)
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner import contracts as ct
from epiforecast.runner.evaluation import (
    build_evaluation_frame,
    build_metric_frame,
    derive_forecast_products,
)
from epiforecast.runner.manifest import ArtifactRecord
from epiforecast.runner.policy import EvaluationPolicy

SCHEMA_SELECTION = "selection.v1"
SCHEMA_SELECTION_MANIFEST = "selection_manifest.v1"
SCHEMA_PORTFOLIO = "portfolio_development.v1"
SCHEMA_SELECTION_REPORT = "selection_report.v1"

PORTFOLIO_ENGINE = "portfolio"  # identidad del portafolio compuesto en los frames
_IDENTITY = [COL_GEO_ID, COL_SEX]
_METRICS = (ct.COL_SMAPE, ct.COL_MASE, ct.COL_RMSE)
_WORST = float("inf")  # NaN (denominador cero) nunca gana un desempate


class SelectionError(ValueError):
    """La selección no puede congelarse (regla, cobertura o insumos inválidos)."""


@dataclass(frozen=True)
class SelectionRule:
    """Regla declarada; se serializa completa en el manifiesto (auditable sin leer código)."""

    aggregate: str
    challenger_min_improvement_pct: float
    band_pct: float
    tie_break: tuple[str, ...]
    incumbents: tuple[str, ...]
    challengers: tuple[str, ...]
    cost: dict[str, int]

    @classmethod
    def from_policy(cls, policy: EvaluationPolicy) -> SelectionRule:
        raw = policy.selection
        if not raw:
            raise SelectionError(f"la política {policy.name!r} no declara `selection`")
        tiers = raw["tiers"]
        rule = cls(
            aggregate=str(raw["aggregate"]),
            challenger_min_improvement_pct=float(raw["challenger_min_improvement_pct"]),
            band_pct=float(raw["band_pct"]),
            tie_break=tuple(str(t) for t in raw["tie_break"]),
            incumbents=tuple(str(e) for e in tiers["incumbents"]),
            challengers=tuple(str(e) for e in tiers["challengers"]),
            cost={str(k): int(v) for k, v in raw["cost"].items()},
        )
        if rule.aggregate != "median":
            raise SelectionError(f"agregado no soportado: {rule.aggregate!r}")
        faltan = set(rule.incumbents + rule.challengers) - set(rule.cost)
        if faltan:
            raise SelectionError(f"motores sin costo declarado: {sorted(faltan)}")
        if set(rule.incumbents) & set(rule.challengers):
            raise SelectionError("un motor no puede ser incumbent y challenger a la vez")
        return rule

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregate": self.aggregate,
            "challenger_min_improvement_pct": self.challenger_min_improvement_pct,
            "band_pct": self.band_pct,
            "tie_break": list(self.tie_break),
            "tiers": {"incumbents": list(self.incumbents), "challengers": list(self.challengers)},
            "cost": dict(sorted(self.cost.items())),
        }


def _num(value: Any) -> float:
    """NaN/no finito → peor posible: una métrica degenerada nunca gana un desempate."""
    out = float(value)
    return out if math.isfinite(out) else _WORST


def _improvement_pct(incumbent: float, challenger: float) -> float:
    """Mejora relativa del challenger sobre el incumbent, en %. Sin base útil → 0."""
    if not math.isfinite(incumbent) or incumbent <= 0.0:
        return 0.0
    return (incumbent - challenger) / incumbent * 100.0


def _resolve(band: list[dict[str, Any]], rule: SelectionRule) -> dict[str, Any]:
    """Desempate declarado dentro de la banda: MASE → RMSE → costo → nombre estable."""
    keys: dict[str, Any] = {
        "mase": lambda row: _num(row[ct.COL_MASE]),
        "rmse": lambda row: _num(row[ct.COL_RMSE]),
        "cost": lambda row: rule.cost[row[ct.COL_ENGINE]],
        "engine": lambda row: row[ct.COL_ENGINE],
    }
    unknown = [k for k in rule.tie_break if k not in keys]
    if unknown:
        raise SelectionError(f"desempates no soportados: {unknown}")
    return min(band, key=lambda row: tuple(keys[k](row) for k in rule.tie_break))


def select_for_series(rows: pd.DataFrame, rule: SelectionRule) -> dict[str, Any]:
    """Aplica la regla a UNA SeriesKey (una fila agregada por motor). Devuelve la decisión."""
    by_engine = {str(r[ct.COL_ENGINE]): r for _, r in rows.iterrows()}
    faltan = set(rule.incumbents) - set(by_engine)
    if faltan:
        raise SelectionError(f"faltan incumbents en el benchmark: {sorted(faltan)}")

    def best(engines: tuple[str, ...]) -> dict[str, Any] | None:
        presentes = [dict(by_engine[e]) for e in engines if e in by_engine]
        if not presentes:
            return None
        return min(presentes, key=lambda r: (_num(r[ct.COL_SMAPE]), r[ct.COL_ENGINE]))

    incumbent = best(rule.incumbents)
    assert incumbent is not None  # garantizado por la verificación de cobertura
    challenger = best(rule.challengers)
    improvement = (
        _improvement_pct(_num(incumbent[ct.COL_SMAPE]), _num(challenger[ct.COL_SMAPE]))
        if challenger is not None
        else 0.0
    )
    opens = challenger is not None and improvement >= rule.challenger_min_improvement_pct
    tier = rule.challengers if opens else rule.incumbents
    tier_rows = [dict(by_engine[e]) for e in tier if e in by_engine]
    best_smape = min(_num(r[ct.COL_SMAPE]) for r in tier_rows)
    limit = best_smape * (1.0 + rule.band_pct / 100.0)
    band = [r for r in tier_rows if _num(r[ct.COL_SMAPE]) <= limit]
    winner = _resolve(band, rule)
    return {
        "tier": "challenger" if opens else "incumbent",
        "best_incumbent": incumbent[ct.COL_ENGINE],
        "best_incumbent_smape": _num(incumbent[ct.COL_SMAPE]),
        "best_challenger": challenger[ct.COL_ENGINE] if challenger is not None else "",
        "best_challenger_smape": _num(challenger[ct.COL_SMAPE])
        if challenger is not None
        else None,
        "challenger_improvement_pct": improvement,
        "band_size": len(band),
        "band_engines": "|".join(sorted(str(r[ct.COL_ENGINE]) for r in band)),
        "selected_engine": winner[ct.COL_ENGINE],
        "selected_smape": _num(winner[ct.COL_SMAPE]),
        "selected_mase": float(winner[ct.COL_MASE]),
        "selected_rmse": float(winner[ct.COL_RMSE]),
        "selected_cost": rule.cost[winner[ct.COL_ENGINE]],
        "reason": (
            f"challenger +{improvement:.2f}% ≥ {rule.challenger_min_improvement_pct}%"
            if opens
            else (
                f"incumbent (challenger +{improvement:.2f}% "
                f"< {rule.challenger_min_improvement_pct}%)"
            )
        ),
    }


def aggregate_metrics(metrics: pd.DataFrame, rule: SelectionRule) -> pd.DataFrame:
    """Mediana por (SeriesKey, motor) sobre los folds de development, SOLO en las 64 bases."""
    base = metrics[
        (metrics[COL_GEO_LEVEL] == GEO_LEVEL_ESTADO)
        & metrics[COL_SEX].isin(BASE_SEXES)
        & (metrics[ct.COL_SPLIT] == ct.SPLIT_DEVELOPMENT)
    ]
    known = set(rule.incumbents) | set(rule.challengers)
    base = base[base[ct.COL_ENGINE].isin(known)]
    return (
        base.groupby([*_IDENTITY, ct.COL_ENGINE], sort=True)[list(_METRICS)].median().reset_index()
    )


def build_selection(metrics: pd.DataFrame, rule: SelectionRule) -> pd.DataFrame:
    """``selection.csv``: una fila por SeriesKey base con la decisión completa y su motivo."""
    agg = aggregate_metrics(metrics, rule)
    rows = [
        {COL_GEO_ID: str(cve), COL_SEX: str(sex), **select_for_series(grp, rule)}
        for (cve, sex), grp in agg.groupby(_IDENTITY, sort=True)
    ]
    out = pd.DataFrame(rows)
    if len(out) != 64 or out.duplicated(_IDENTITY).any():
        raise SelectionError(f"la selección debe cubrir las 64 bases sin duplicados ({len(out)})")
    return out


def selection_digest(rule: SelectionRule, provenance: dict[str, Any], sel: pd.DataFrame) -> str:
    """Digest de la selección congelada: regla + procedencia + mapa serie→motor."""
    payload = {
        "rule": rule.to_dict(),
        "provenance": provenance,
        "map": [
            [r[COL_GEO_ID], r[COL_SEX], r["selected_engine"]]
            for _, r in sel.sort_values(_IDENTITY).iterrows()
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compose_base_forecast(
    forecasts: dict[str, pd.DataFrame], sel: pd.DataFrame, run_id: str
) -> pd.DataFrame:
    """Toma de cada motor SOLO las bases que le tocaron y arma el ForecastFrame del portafolio."""
    chosen = {(r[COL_GEO_ID], r[COL_SEX]): r["selected_engine"] for _, r in sel.iterrows()}
    parts: list[pd.DataFrame] = []
    for engine, frame in forecasts.items():
        base = frame[(frame[COL_GEO_LEVEL] == GEO_LEVEL_ESTADO) & frame[COL_SEX].isin(BASE_SEXES)]
        keys = {k for k, e in chosen.items() if e == engine}
        if not keys:
            continue
        pares = pd.Series(
            list(zip(base[COL_GEO_ID], base[COL_SEX], strict=True)), index=base.index
        )
        parts.append(base[pares.isin(keys)])
    out = pd.concat(parts, ignore_index=True)
    out[ct.COL_ENGINE] = PORTFOLIO_ENGINE  # identidad del portafolio, no del motor donante
    out[ct.COL_RUN_ID] = run_id
    got = set(zip(out[COL_GEO_ID], out[COL_SEX], strict=True))
    if got != set(chosen):
        raise SelectionError(f"el portafolio no cubre las 64 bases ({len(got)})")
    return out.sort_values([ct.COL_FOLD, COL_GEO_ID, COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK])


def evaluate_portfolio(
    base_forecast: pd.DataFrame, products: pd.DataFrame, policy: EvaluationPolicy, split: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deriva 64→111 el portafolio y lo evalúa fold a fold. Devuelve (evaluación, métricas)."""
    catalog = load_geo_catalog()
    ev_parts: list[pd.DataFrame] = []
    fc_parts: list[pd.DataFrame] = []
    for fold_id, fold_fc in base_forecast.groupby(ct.COL_FOLD, sort=True):
        fold = next(f for f in policy.folds if f.fold_id == fold_id)
        full = derive_forecast_products(fold_fc.reset_index(drop=True), catalog)
        weeks = {w for (_, w) in fold.holdout}
        truth = products[
            (products[COL_EPI_YEAR] == fold.epi_year) & products[COL_EPI_WEEK].isin(weeks)
        ]
        ev_parts.append(build_evaluation_frame(full, truth, split))
        fc_parts.append(full)
    evaluation = pd.concat(ev_parts, ignore_index=True)
    ct.validate_forecast_frame(pd.concat(fc_parts, ignore_index=True))
    ct.validate_evaluation_frame(evaluation)
    metrics = build_metric_frame(evaluation, products, policy.mase_seasonal_lag)
    ct.validate_metric_frame(metrics)
    return evaluation, metrics


def portfolio_summary(metrics: pd.DataFrame) -> dict[str, float]:
    """Medianas del portafolio: 64 bases, 111 productos y nacional General."""
    base = metrics[
        (metrics[COL_GEO_LEVEL] == GEO_LEVEL_ESTADO) & metrics[COL_SEX].isin(BASE_SEXES)
    ]
    nat = metrics[(metrics[COL_GEO_LEVEL] == "nacional") & (metrics[COL_SEX] == "general")]
    return {
        "smape_bases": float(base[ct.COL_SMAPE].median()),
        "smape_all": float(metrics[ct.COL_SMAPE].median()),
        "smape_nacional_general": float(nat[ct.COL_SMAPE].median()),
        "mase_bases": float(base[ct.COL_MASE].median()),
        "mase_all": float(metrics[ct.COL_MASE].median()),
    }


def render_report(
    sel: pd.DataFrame, summary: dict[str, float], rule: SelectionRule, provenance: dict[str, Any]
) -> str:
    """``selection_report.md``: resumen humano, distribución y anomalías (sin elegir nada nuevo)."""
    dist = sel["selected_engine"].value_counts().sort_index()
    etiqueta = provenance.get("disease_label") or provenance["disease_id"]
    folds = provenance.get("development_folds") or []
    lines = [
        f"# Selección por SeriesKey — {etiqueta}, desarrollo",
        "",
        f"- Folds de development: {', '.join(str(f) for f in folds) or 'los de la política'}",
        f"- Benchmark: `{provenance['benchmark_run_id']}` @ `{provenance['code_commit']}`",
        f"- Política: `{provenance['policy_name']}` (digest `{provenance['policy_digest'][:12]}`)",
        f"- Dataset: `{provenance['dataset_id']}`",
        f"- Regla: challenger ≥ {rule.challenger_min_improvement_pct}% · banda "
        f"{rule.band_pct}% · desempate {' → '.join(rule.tie_break)}",
        "",
        "## Distribución de motores seleccionados",
        "",
        "| motor | series | tier |",
        "| --- | ---: | --- |",
    ]
    for engine, n in dist.items():
        tier = "challenger" if engine in rule.challengers else "incumbent"
        lines.append(f"| `{engine}` | {n} | {tier} |")
    activos = sel[sel["tier"] == "challenger"]
    n_ch = len(activos)
    # Mediana SOLO de los challengers activos; sobre las 64 series el valor es negativo y engaña.
    mejora = float(activos["challenger_improvement_pct"].median()) if n_ch else float("nan")
    lines += [
        "",
        f"Challengers activos en **{n_ch}/64** series "
        f"(mejora mediana entre los activos: {mejora:.2f}%; "
        f"sobre las 64 series la mediana es {sel['challenger_improvement_pct'].median():.2f}%).",
        "",
        "## Portafolio en desarrollo (64→111 derivado, sin elegir motor para agregados)",
        "",
        "| ámbito | sMAPE mediana | MASE mediana |",
        "| --- | ---: | ---: |",
        f"| 64 bases | {summary['smape_bases']:.2f} | {summary['mase_bases']:.2f} |",
        f"| 111 productos | {summary['smape_all']:.2f} | {summary['mase_all']:.2f} |",
        f"| nacional General | {summary['smape_nacional_general']:.2f} | — |",
        "",
        "## Anomalías",
        "",
    ]
    anomalias = [
        f"- `{r[COL_GEO_ID]}/{r[COL_SEX]}`: MASE del motor elegido no calculable (denominador cero)"
        for _, r in sel.iterrows()
        if not math.isfinite(float(r["selected_mase"]))
    ]
    banda_amplia = int((sel["band_size"] > 1).sum())
    lines += anomalias or ["- Sin métricas degeneradas en los motores elegidos."]
    lines += [
        f"- {banda_amplia}/64 series resolvieron con banda de más de un candidato "
        "(desempate por MASE/RMSE/costo).",
        "",
        f"**No es una decisión de producción**: {etiqueta} sigue NO-GO y sin publicar.",
    ]
    return "\n".join(lines) + "\n"


def _rec(run_dir: Path, path: Path, schema: str) -> ArtifactRecord:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactRecord(str(path.relative_to(run_dir)), digest, schema, validated=True)


def write_selection(
    run_dir: Path,
    sel: pd.DataFrame,
    portfolio_metrics: pd.DataFrame,
    report: str,
    manifest_body: dict[str, Any],
) -> tuple[list[ArtifactRecord], dict[str, Any]]:
    """Escribe los cuatro artefactos con digests; el manifiesto sella a los otros tres."""
    run_dir.mkdir(parents=True, exist_ok=True)
    arts: list[ArtifactRecord] = []
    for frame, fname, schema in (
        (sel, "selection.csv", SCHEMA_SELECTION),
        (portfolio_metrics, "portfolio_development.csv", SCHEMA_PORTFOLIO),
    ):
        path = run_dir / fname
        frame.to_csv(path, index=False)
        arts.append(_rec(run_dir, path, schema))
    report_path = run_dir / "selection_report.md"
    report_path.write_text(report, encoding="utf-8")
    arts.append(_rec(run_dir, report_path, SCHEMA_SELECTION_REPORT))

    manifest = {
        **manifest_body,
        "schema": SCHEMA_SELECTION_MANIFEST,
        "artifacts": [asdict(a) for a in arts],
    }
    manifest_path = run_dir / "selection_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    arts.append(_rec(run_dir, manifest_path, SCHEMA_SELECTION_MANIFEST))
    return arts, manifest


def load_frozen_selection(selection_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Carga una selección CONGELADA verificando digests: sin eso, nada aguas abajo puede correr."""
    manifest_path = selection_dir / "selection_manifest.json"
    if not manifest_path.exists():
        raise SelectionError(f"no hay selection_manifest.json en {selection_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA_SELECTION_MANIFEST:
        raise SelectionError(f"schema de selección inesperado: {manifest.get('schema')!r}")
    for art in manifest["artifacts"]:
        path = selection_dir / art["path"]
        if not path.exists():
            raise SelectionError(f"artefacto de selección ausente: {art['path']}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != art["digest"]:
            raise SelectionError(f"artefacto de selección alterado: {art['path']}")
    sel = pd.read_csv(selection_dir / "selection.csv", dtype={COL_GEO_ID: str})
    if len(sel) != 64:
        raise SelectionError(f"selección incompleta: {len(sel)} bases")
    return sel, manifest
