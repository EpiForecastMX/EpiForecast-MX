"""F2/C5.2 — gate de aceptación del stage ``test`` (2025), evaluado UNA sola vez.

El portafolio congelado en desarrollo se confronta con 2025 completo (53 semanas) contra un motor de
**control** declarado. El veredicto es global y binario: si el portafolio no pasa, se rechaza
ENTERO y la selección final cae al motor de fallback para las 64 bases. Nunca se retunea con 2025 ni
se cambia una serie por su resultado individual: eso convertiría el test en otro conjunto de tuning.

Umbrales y motores viven en la política (``acceptance``); aquí no hay números en código.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from epiforecast.data.epi_dataset_spec import COL_GEO_ID, COL_SEX
from epiforecast.runner.manifest import ArtifactRecord
from epiforecast.runner.policy import EvaluationPolicy
from epiforecast.runner.selection import portfolio_summary

SCHEMA_ACCEPTANCE = "acceptance.v1"
SCHEMA_PORTFOLIO_TEST = "portfolio_test.v1"
SCHEMA_FINAL_SELECTION = "final_selection.v1"
SCHEMA_ACCEPTANCE_REPORT = "acceptance_report.v1"

_SCOPES = ("smape_bases", "smape_all", "smape_nacional_general")


class AcceptanceError(ValueError):
    """El gate de aceptación no puede evaluarse (regla o insumos inválidos)."""


@dataclass(frozen=True)
class AcceptanceRule:
    """Regla declarada del gate; se serializa completa en ``acceptance.json``."""

    control_engine: str
    fallback_engine: str
    max_worse_pct: dict[str, float]

    @classmethod
    def from_policy(cls, policy: EvaluationPolicy) -> AcceptanceRule:
        raw = policy.acceptance
        if not raw:
            raise AcceptanceError(f"la política {policy.name!r} no declara `acceptance`")
        max_worse = {str(k): float(v) for k, v in raw["max_worse_pct"].items()}
        faltan = set(_SCOPES) - set(max_worse)
        if faltan:
            raise AcceptanceError(f"umbrales faltantes en acceptance: {sorted(faltan)}")
        return cls(
            control_engine=str(raw["control_engine"]),
            fallback_engine=str(raw["fallback_engine"]),
            max_worse_pct=max_worse,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_engine": self.control_engine,
            "fallback_engine": self.fallback_engine,
            "max_worse_pct": dict(sorted(self.max_worse_pct.items())),
        }


def evaluate_gate(
    portfolio: dict[str, float], control: dict[str, float], rule: AcceptanceRule
) -> dict[str, Any]:
    """Veredicto GLOBAL: el portafolio no puede empeorar al control más de lo declarado."""
    checks: list[dict[str, Any]] = []
    for scope in _SCOPES:
        p, c = float(portfolio[scope]), float(control[scope])
        # Positivo = el portafolio es PEOR que el control, en % relativo al control.
        worse_pct = (p - c) / c * 100.0 if c > 0 else float("inf")
        limit = rule.max_worse_pct[scope]
        checks.append(
            {
                "scope": scope,
                "portfolio": p,
                "control": c,
                "worse_pct": worse_pct,
                "max_worse_pct": limit,
                "passed": bool(worse_pct <= limit),
            }
        )
    return {"accepted": all(c["passed"] for c in checks), "checks": checks}


def final_selection(
    sel: pd.DataFrame, verdict: dict[str, Any], rule: AcceptanceRule
) -> pd.DataFrame:
    """Mapa serie→motor DEFINITIVO: el congelado si pasa; si no, el fallback en las 64 bases."""
    out = sel[[COL_GEO_ID, COL_SEX, "selected_engine"]].copy()
    if not verdict["accepted"]:
        out["selected_engine"] = rule.fallback_engine
    out["source"] = "development_selection" if verdict["accepted"] else "acceptance_fallback"
    return out.sort_values([COL_GEO_ID, COL_SEX]).reset_index(drop=True)


def render_report(
    verdict: dict[str, Any],
    rule: AcceptanceRule,
    final: pd.DataFrame,
    provenance: dict[str, Any],
) -> str:
    """``acceptance_report.md``: veredicto, cada comprobación y qué queda como selección final."""
    estado = "ACEPTADO" if verdict["accepted"] else "RECHAZADO"
    lines = [
        f"# Gate de aceptación 2025 — portafolio {estado}",
        "",
        f"- Selección congelada: `{provenance['selection_run_id']}` "
        f"(digest `{provenance['selection_digest'][:12]}`)",
        f"- Benchmark test: `{provenance['run_id']}` @ `{provenance['code_commit']}`",
        f"- Control: `{rule.control_engine}` · fold `{provenance['fold_id']}` "
        f"({provenance['n_weeks']} semanas)",
        "",
        "## Comprobaciones (positivo = el portafolio es peor que el control)",
        "",
        "| ámbito | portafolio | control | dif. % | máx. permitido | resultado |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for check in verdict["checks"]:
        lines.append(
            f"| {check['scope']} | {check['portfolio']:.2f} | {check['control']:.2f} | "
            f"{check['worse_pct']:+.2f}% | {check['max_worse_pct']:.1f}% | "
            f"{'pasa' if check['passed'] else 'FALLA'} |"
        )
    dist = final["selected_engine"].value_counts().sort_index()
    lines += [
        "",
        "## Selección final",
        "",
        (
            "El mapa de desarrollo queda aceptado SIN modificaciones."
            if verdict["accepted"]
            else f"Portafolio rechazado: las 64 bases pasan a `{rule.fallback_engine}`. "
            "NO se retunea con 2025 ni se cambia ninguna serie por su resultado individual."
        ),
        "",
        "| motor | series |",
        "| --- | ---: |",
        *[f"| `{engine}` | {n} |" for engine, n in dist.items()],
        "",
        "**No es una decisión de producción**: Obesidad sigue NO-GO y sin publicar.",
    ]
    return "\n".join(lines) + "\n"


def _rec(run_dir: Path, path: Path, schema: str) -> ArtifactRecord:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactRecord(str(path.relative_to(run_dir)), digest, schema, validated=True)


def write_acceptance(
    run_dir: Path,
    portfolio_metrics: pd.DataFrame,
    final: pd.DataFrame,
    report: str,
    body: dict[str, Any],
) -> list[ArtifactRecord]:
    """Escribe la evidencia del gate (pase o falle): métricas, selección final, veredicto y reporte."""
    arts: list[ArtifactRecord] = []
    for frame, fname, schema in (
        (portfolio_metrics, "portfolio_test.csv", SCHEMA_PORTFOLIO_TEST),
        (final, "final_selection.csv", SCHEMA_FINAL_SELECTION),
    ):
        path = run_dir / fname
        frame.to_csv(path, index=False)
        arts.append(_rec(run_dir, path, schema))
    report_path = run_dir / "acceptance_report.md"
    report_path.write_text(report, encoding="utf-8")
    arts.append(_rec(run_dir, report_path, SCHEMA_ACCEPTANCE_REPORT))

    payload = {**body, "schema": SCHEMA_ACCEPTANCE, "artifacts": [a.__dict__ for a in arts]}
    path = run_dir / "acceptance.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    arts.append(_rec(run_dir, path, SCHEMA_ACCEPTANCE))
    return arts


def load_accepted(test_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Carga la selección FINAL de un run de test verificando digests (evidencia intacta)."""
    path = test_dir / "acceptance.json"
    if not path.exists():
        raise AcceptanceError(f"no hay acceptance.json en {test_dir}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA_ACCEPTANCE:
        raise AcceptanceError(f"schema de aceptación inesperado: {payload.get('schema')!r}")
    for art in payload["artifacts"]:
        target = test_dir / art["path"]
        if not target.exists():
            raise AcceptanceError(f"artefacto de aceptación ausente: {art['path']}")
        if hashlib.sha256(target.read_bytes()).hexdigest() != art["digest"]:
            raise AcceptanceError(f"artefacto de aceptación alterado: {art['path']}")
    final = pd.read_csv(test_dir / "final_selection.csv", dtype={COL_GEO_ID: str})
    if len(final) != 64:
        raise AcceptanceError(f"selección final incompleta: {len(final)} bases")
    return final, payload


def summarize(metrics: pd.DataFrame) -> dict[str, float]:
    """Resumen del portafolio/control en los mismos ámbitos del gate."""
    return portfolio_summary(metrics)
