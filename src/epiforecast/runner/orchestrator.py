"""F2/C3 — orquestación del runner genérico de padecimientos (carril E66; no toca neuro/Dengue).

- ``validate_data``: FUNCIONAL. Construye dataset base (41,792) + 111 productos bajo
  ``runs/<dataset_id>/`` y escribe un ``DatasetManifest`` (identidad del dataset validado). NUNCA
  se sobrescribe por una ejecución de motores.
- ``run_command`` (benchmark/refit/forecast): calcula un ``run_id`` propio (dataset+comando+stage+
  política+motores+seed+commit), crea ``runs/<run_id>/`` (dir DISTINTO) que referencia el
  ``dataset_id``, y lanza un subprocess LIMPIO por motor. Motores por defecto = candidatos de la
  POLÍTICA (no los training_engines legacy).

Un job solo es exitoso si rc=0, el ``result.json`` es de ESTE intento (token) y cada artefacto
existe y coincide con su digest. stdout/stderr se guardan por job. Reanudación SOLO si el job está
succeeded con artefactos validados (un .pkl suelto NO cuenta). Sin train real/publicación/DVC/push.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from typing import Any

import pandas as pd

from epiforecast import registry
from epiforecast.data.epi_aggregate import build_products
from epiforecast.data.epi_dataset import build_epi_dataset_v2
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner import acceptance, forecasting, selection
from epiforecast.runner import contracts as ct
from epiforecast.runner import refit as refit_mod
from epiforecast.runner.contracts import SCHEMA_DATASET, SCHEMA_PRODUCTS
from epiforecast.runner.manifest import (
    STAGES,
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    ArtifactRecord,
    DatasetManifest,
    JobRecord,
    RunManifest,
    compute_run_id,
)
from epiforecast.runner.policy import candidate_engines, load_policy, policy_digest, policy_seed
from epiforecast.runner.report import comparative_report

_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_LINEAGE = "lineage.v1"

# Un solo thread numérico por subprocess de motor: ejecución secuencial y reproducible (BLAS/OpenMP
# multihilo puede reordenar reducciones en coma flotante entre corridas).
_SINGLE_THREAD_ENV: dict[str, str] = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}


class RunnerError(ValueError):
    """Error de orquestación del runner."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _tracked_dirty() -> list[str]:
    """Archivos TRACKEADOS con cambios sin commit (staged o no). Los untracked (``??``) NO cuentan."""
    try:
        out = subprocess.run(
            ["git", "-C", str(_ROOT), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [ln[3:] for ln in out.stdout.splitlines() if ln[:2] != "??"]


def validate_data(disease: str, runs_root: Path | None = None) -> DatasetManifest:
    """Construye dataset base + 111 productos bajo runs/<dataset_id>/ y escribe DatasetManifest."""
    result = build_epi_dataset_v2(disease, runs_root=runs_root)
    catalog = load_geo_catalog()
    agg = build_products(result.dataset, catalog, result.config.disease_id)

    dataset_dir = result.run_dir  # runs/<dataset_id>/
    products_path = dataset_dir / "products.csv"
    agg.products.to_csv(products_path, index=False)
    lineage_path = dataset_dir / "lineage.json"
    lineage_path.write_text(
        json.dumps(agg.lineage, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    man = DatasetManifest(dataset_id=result.run_id, disease_id=result.config.disease_id)
    man.code_commit = _git_commit()
    man.digests = dict(result.digests)
    man.counts = {
        "base": agg.counts["base"],
        "derived": agg.counts["derived"],
        "products": agg.counts["products"],
    }
    man.artifacts = [
        ArtifactRecord(
            "epi_dataset_v2.csv", result.digests["dataset"], SCHEMA_DATASET, validated=True
        ),
        ArtifactRecord("products.csv", _sha256(products_path), SCHEMA_PRODUCTS, validated=True),
        ArtifactRecord("lineage.json", _sha256(lineage_path), SCHEMA_LINEAGE, validated=True),
    ]
    man.write(dataset_dir)
    return man


def verify_artifacts(run_dir: Path, artifacts: list[dict[str, Any]]) -> list[str]:
    """Problemas (vacío = OK): cada artefacto declarado debe existir y coincidir con su digest."""
    problems: list[str] = []
    for a in artifacts:
        p = run_dir / str(a["path"])
        if not p.exists():
            problems.append(f"artefacto ausente: {a['path']}")
        elif _sha256(p) != a["digest"]:
            problems.append(f"digest no coincide: {a['path']}")
    return problems


def _resumable(run_dir: Path, job: JobRecord) -> bool:
    """Reanudable SOLO si terminó bien Y sus artefactos AÚN existen y verifican digest en disco."""
    if not job.is_complete():
        return False
    arts = [{"path": a.path, "digest": a.digest} for a in job.artifacts]
    return not verify_artifacts(run_dir, arts)


def _spawn_engine(
    run_dir: Path, engine: str, command: str, python_exe: str | None
) -> tuple[int, dict[str, Any] | None, str]:
    """Subprocess LIMPIO por motor. Genera token de intento, borra result.json previo, captura
    stdout/stderr a disco. Devuelve (exit_code, result.json | None, attempt)."""
    attempt = secrets.token_hex(8)
    jobs_dir = run_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    result_path = jobs_dir / f"{engine}.result.json"
    if result_path.exists():
        result_path.unlink()  # anti-stale: ningún result de un intento anterior sobrevive

    cmd = [
        python_exe or sys.executable,
        "-m",
        "epiforecast.runner.engine_worker",
        "--run-dir",
        str(run_dir),
        "--engine",
        engine,
        "--command",
        command,
        "--attempt",
        attempt,
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, env={**os.environ, **_SINGLE_THREAD_ENV}
    )
    (jobs_dir / f"{engine}.stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (jobs_dir / f"{engine}.stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    result: dict[str, Any] | None = None
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    return proc.returncode, result, attempt


def _apply_result(
    run_dir: Path,
    job: JobRecord,
    engine: str,
    rc: int,
    result: dict[str, Any] | None,
    attempt: str,
) -> None:
    """Acepta el job SOLO si rc=0, el result es de este intento y los artefactos verifican digest."""
    job.stdout = f"jobs/{engine}.stdout.txt"
    job.stderr = f"jobs/{engine}.stderr.txt"
    if result is None:
        job.fail(rc or 1, "SubprocessError", f"subprocess terminó rc={rc} sin result.json")
    elif result.get("attempt") != attempt:
        job.fail(1, "StaleResult", "result.json no pertenece a este intento")
    elif rc != 0 or result.get("status") != "succeeded":
        job.fail(
            int(result.get("exit_code") or rc or 1),
            str(result.get("error_type") or "EngineError"),
            str(result.get("error_message") or ""),
        )
    else:
        problems = verify_artifacts(run_dir, result.get("artifacts") or [])
        if problems:
            job.fail(1, "ArtifactMismatch", "; ".join(problems))
        else:
            arts = [
                ArtifactRecord(
                    path=a["path"], digest=a["digest"], schema=a["schema"], validated=True
                )
                for a in result["artifacts"]
            ]
            job.succeed(arts)


def run_engines(
    run_dir: Path,
    disease_id: str,
    command: str,
    engines: list[str],
    *,
    dataset_id: str = "",
    stage: str | None = None,
    policy_digest_value: str | None = None,
    seed: int | None = None,
    code_commit: str | None = None,
    input_digests: dict[str, str] | None = None,
    counts: dict[str, int] | None = None,
    resume: bool = True,
    python_exe: str | None = None,
) -> RunManifest:
    """Ejecuta ``command`` para cada motor en subprocess limpio; actualiza y escribe el manifiesto."""
    if not engines:
        raise RunnerError(f"{command}: se requiere al menos un motor (--engines o política)")
    run_dir = Path(run_dir)

    # Reanudación: reutiliza el manifiesto SOLO si es del mismo comando; si no, arranca limpio.
    man: RunManifest | None = None
    if resume and (run_dir / "run_manifest.json").exists():
        prev = RunManifest.read(run_dir)
        if prev.command == command:
            man = prev
    if man is None:
        man = RunManifest(
            run_id=run_dir.name,
            disease_id=disease_id,
            command=command,
            dataset_id=dataset_id,
            stage=stage if stage in STAGES else None,
            policy_digest=policy_digest_value,
            seed=seed,
            code_commit=code_commit,
            engines=list(engines),
        )
    # Digests y conteos del DatasetManifest viajan al RunManifest (trazabilidad).
    if input_digests is not None:
        man.input_digests = dict(input_digests)
    if counts is not None:
        man.counts = dict(counts)
    man.start()

    for engine in engines:
        prior = man.jobs.get(engine)
        if resume and prior is not None and _resumable(run_dir, prior):
            continue  # succeeded + artefactos que AÚN existen y verifican digest en disco
        job = man.job(engine)
        job.reset()
        job.start()
        rc, result, attempt = _spawn_engine(run_dir, engine, command, python_exe)
        _apply_result(run_dir, job, engine, rc, result, attempt)

    failed = [e for e, j in man.jobs.items() if j.status == STATUS_FAILED]
    if failed:
        codes = {man.jobs[e].exit_code for e in failed}
        man.fail(
            2 if codes == {2} else 1, "EngineJobsFailed", f"motores fallidos: {sorted(failed)}"
        )
    else:
        man.succeed()
    man.write(run_dir)
    return man


def run_selection(
    disease: str,
    benchmark_run_id: str,
    *,
    policy_name: str = "rolling_cv_v1",
    runs_root: Path | None = None,
    require_clean: bool = False,
) -> RunManifest:
    """Congela la selección por SeriesKey a partir de un benchmark YA ejecutado (no entrena nada).

    Verifica que el benchmark sea exitoso, del mismo dataset y con sus artefactos intactos; aplica
    la regla declarada en la política; compone el portafolio 64→111 en development y escribe
    selection.csv, portfolio_development.csv, selection_report.md y selection_manifest.json.
    """
    if require_clean:
        dirty = _tracked_dirty()
        if dirty:
            raise RunnerError(
                f"selección oficial rechazada: {len(dirty)} archivo(s) trackeado(s) sin commit "
                f"(p.ej. {dirty[0]}). Commitea antes de congelar la selección."
            )
    dm = validate_data(disease, runs_root=runs_root)
    runs_base = runs_root or (_ROOT / "runs")
    bench_dir = runs_base / benchmark_run_id
    if not (bench_dir / "run_manifest.json").exists():
        raise RunnerError(f"no existe el benchmark {benchmark_run_id!r} en {runs_base}")
    bench = RunManifest.read(bench_dir)
    if bench.command != "benchmark" or bench.status != STATUS_SUCCEEDED:
        raise RunnerError(f"{benchmark_run_id}: no es un benchmark exitoso ({bench.status})")
    if bench.dataset_id != dm.dataset_id:
        raise RunnerError(
            f"{benchmark_run_id}: dataset {bench.dataset_id} != actual {dm.dataset_id}"
        )
    for engine, job in bench.jobs.items():
        problems = verify_artifacts(
            bench_dir, [{"path": a.path, "digest": a.digest} for a in job.artifacts]
        )
        if problems:
            raise RunnerError(f"{benchmark_run_id}/{engine}: {'; '.join(problems)}")

    policy = load_policy(policy_name)
    rule = selection.SelectionRule.from_policy(policy)
    metrics = pd.concat(
        [
            pd.read_csv(bench_dir / "artifacts" / e / "metrics.csv", dtype={"geography_id": str})
            for e in bench.engines
        ],
        ignore_index=True,
    )
    sel = selection.build_selection(metrics, rule)

    code_commit = _git_commit()
    run_id = compute_run_id(
        dm.disease_id,
        dm.dataset_id,
        "select",
        benchmark_run_id.rsplit("_", 1)[-1],  # variante = sufijo del benchmark consumido
        policy.digest,
        list(bench.engines),
        policy.seed,
        code_commit,
    )
    run_dir = runs_base / run_id
    forecasts = {
        e: pd.read_csv(bench_dir / "artifacts" / e / "forecast.csv", dtype={"geography_id": str})
        for e in bench.engines
    }
    base_fc = selection.compose_base_forecast(forecasts, sel, run_id)
    products = pd.read_csv(runs_base / dm.dataset_id / "products.csv", dtype={"geography_id": str})
    _, portfolio_metrics = selection.evaluate_portfolio(
        base_fc, products, policy, ct.SPLIT_DEVELOPMENT
    )
    summary = selection.portfolio_summary(portfolio_metrics)

    provenance = {
        "disease_id": dm.disease_id,
        "dataset_id": dm.dataset_id,
        "dataset_digest": dm.digests["dataset"],
        "benchmark_run_id": benchmark_run_id,
        "benchmark_code_commit": bench.code_commit,
        "policy_name": policy_name,
        "policy_digest": policy.digest,
        "code_commit": code_commit,
    }
    digest = selection.selection_digest(rule, provenance, sel)
    report = selection.render_report(sel, summary, rule, provenance)
    arts, _ = selection.write_selection(
        run_dir,
        sel,
        portfolio_metrics,
        report,
        {
            "selection_digest": digest,
            "rule": rule.to_dict(),
            "provenance": provenance,
            "counts": {
                "series": int(len(sel)),
                "engines_selected": int(sel["selected_engine"].nunique()),
                "challengers": int((sel["tier"] == "challenger").sum()),
            },
            "distribution": {
                str(k): int(v)
                for k, v in sel["selected_engine"].value_counts().sort_index().items()
            },
            "portfolio_development": summary,
        },
    )

    man = RunManifest(
        run_id=run_id,
        disease_id=dm.disease_id,
        command="select",
        dataset_id=dm.dataset_id,
        policy_digest=policy.digest,
        seed=policy.seed,
        code_commit=code_commit,
        engines=list(bench.engines),
    )
    man.input_digests = {**dm.digests, "selection": digest}
    man.counts = {"series": int(len(sel)), "products": 111}
    man.start()
    man.artifacts = arts
    man.succeed()
    man.write(run_dir)
    return man


def _load_selection_for_test(
    runs_base: Path, selection_run_id: str | None, policy: Any, dataset_id: str
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """El stage ``test`` SOLO existe con una selección congelada, intacta y de la MISMA política."""
    if not selection_run_id:
        raise RunnerError(
            "stage 'test' requiere --selection <run_id>: 2025 no se abre sin selección congelada"
        )
    sel, manifest = selection.load_frozen_selection(runs_base / selection_run_id)
    provenance = manifest["provenance"]
    if provenance["policy_digest"] != policy.digest:
        raise RunnerError(
            "la selección se congeló con OTRA política "
            f"({provenance['policy_digest'][:12]} != {policy.digest[:12]})"
        )
    if provenance["dataset_id"] != dataset_id:
        raise RunnerError(
            f"la selección es de otro dataset ({provenance['dataset_id']} != {dataset_id})"
        )
    return sel, manifest


def _finish_test_stage(
    run_dir: Path,
    man: RunManifest,
    sel: pd.DataFrame,
    sel_manifest: dict[str, Any],
    policy: Any,
    products: pd.DataFrame,
    code_commit: str | None,
    selection_run_id: str,
) -> None:
    """Compone el portafolio 2025, aplica el gate de aceptación y escribe toda la evidencia."""
    rule = acceptance.AcceptanceRule.from_policy(policy)
    forecasts = {
        e: pd.read_csv(run_dir / "artifacts" / e / "forecast.csv", dtype={"geography_id": str})
        for e in man.engines
    }
    base_fc = selection.compose_base_forecast(forecasts, sel, man.run_id)
    _, portfolio_metrics = selection.evaluate_portfolio(base_fc, products, policy, ct.SPLIT_TEST)
    control_metrics = pd.read_csv(
        run_dir / "artifacts" / rule.control_engine / "metrics.csv", dtype={"geography_id": str}
    )
    verdict = acceptance.evaluate_gate(
        acceptance.summarize(portfolio_metrics), acceptance.summarize(control_metrics), rule
    )
    final = acceptance.final_selection(sel, verdict, rule)
    fold = policy.folds_for_stage("test")[-1]
    provenance = {
        "run_id": man.run_id,
        "code_commit": code_commit,
        "selection_run_id": selection_run_id,
        "benchmark_run_id": sel_manifest["provenance"]["benchmark_run_id"],
        "selection_digest": sel_manifest["selection_digest"],
        "fold_id": fold.fold_id,
        "n_weeks": fold.n_weeks,
    }
    report = acceptance.render_report(verdict, rule, final, provenance)
    arts = acceptance.write_acceptance(
        run_dir,
        portfolio_metrics,
        final,
        report,
        {
            **verdict,
            "rule": rule.to_dict(),
            "provenance": provenance,
            "portfolio": acceptance.summarize(portfolio_metrics),
            "control": acceptance.summarize(control_metrics),
            "engines_in_run": list(man.engines),
        },
    )
    man.artifacts = [*man.artifacts, *arts]
    man.write(run_dir)


def _refit_context(
    runs_base: Path, acceptance_run_id: str, dm: DatasetManifest, policy: Any
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    """Valida el run de aceptación y devuelve (selección final, payload, procedencia)."""
    test_dir = runs_base / acceptance_run_id
    if not (test_dir / "run_manifest.json").exists():
        raise RunnerError(f"no existe el run de aceptación {acceptance_run_id!r}")
    test_man = RunManifest.read(test_dir)
    if test_man.command != "benchmark" or test_man.stage != "test":
        raise RunnerError(f"{acceptance_run_id}: no es un run de stage test")
    if test_man.status != STATUS_SUCCEEDED:
        raise RunnerError(f"{acceptance_run_id}: el run de aceptación no fue exitoso")
    if test_man.dataset_id != dm.dataset_id or test_man.disease_id != dm.disease_id:
        raise RunnerError(f"{acceptance_run_id}: dataset o padecimiento distintos")
    if test_man.policy_digest != policy.digest:
        raise RunnerError(f"{acceptance_run_id}: se aceptó con OTRA política")
    for engine, job in test_man.jobs.items():
        problems = verify_artifacts(
            test_dir, [{"path": a.path, "digest": a.digest} for a in job.artifacts]
        )
        if problems:
            raise RunnerError(f"{acceptance_run_id}/{engine}: {'; '.join(problems)}")

    final, payload = acceptance.load_accepted(test_dir)  # re-verifica digests de la evidencia
    if not payload.get("accepted"):
        raise RunnerError(f"{acceptance_run_id}: la aceptación fue NEGATIVA; no se refitea")
    keys = set(zip(final["geography_id"], final["sex"], strict=True))
    if len(final) != 64 or len(keys) != 64:
        raise RunnerError(f"{acceptance_run_id}: la selección final no tiene 64 claves únicas")
    provenance = {
        "acceptance_run_id": acceptance_run_id,
        "acceptance_digest": _sha256(test_dir / "acceptance.json"),
        "final_selection_digest": _sha256(test_dir / "final_selection.csv"),
        "selection_run_id": payload["provenance"]["selection_run_id"],
        "selection_digest": payload["provenance"]["selection_digest"],
    }
    return final, payload, provenance


def run_command(
    disease: str,
    command: str,
    *,
    stage: str = "full",
    engines: list[str] | None = None,
    horizon: int | None = None,
    policy_name: str = "rolling_cv_v1",
    runs_root: Path | None = None,
    resume: bool = True,
    require_clean: bool = False,
    selection_run_id: str | None = None,
    acceptance_run_id: str | None = None,
    refit_run_id: str | None = None,
) -> RunManifest:
    """benchmark/refit/forecast: materializa el dataset (dataset_id) y orquesta los motores en runs/<run_id>/."""
    # 2025 no se abre sin selección congelada, y NUNCA para tunear: se comprueba ANTES de tocar
    # datos, para que un intento inválido no llegue siquiera a materializar el dataset.
    if stage == "test":
        if command != "benchmark":
            raise RunnerError(f"stage 'test' solo existe para benchmark, no para {command!r}")
        if not selection_run_id:
            raise RunnerError(
                "stage 'test' requiere --selection <run_id>: 2025 no se abre sin selección congelada"
            )
    # refit y forecast están gobernados por artefactos previos, nunca por una lista manual.
    if command == "refit" and not acceptance_run_id:
        raise RunnerError("refit requiere --acceptance-run <run_id> (la selección aceptada manda)")
    if command == "forecast" and not refit_run_id:
        raise RunnerError("forecast requiere --refit-run <run_id>: nunca reajusta implícitamente")
    if engines and command in ("refit", "forecast"):
        raise RunnerError(
            f"{command}: los motores salen de la selección aceptada, no de --engines"
        )
    # Un run OFICIAL exige árbol limpio: el code_commit del run_id debe reflejar el código real.
    if require_clean:
        dirty = _tracked_dirty()
        if dirty:
            raise RunnerError(
                f"run oficial rechazado: {len(dirty)} archivo(s) trackeado(s) sin commit "
                f"(p.ej. {dirty[0]}). Commitea antes de un benchmark canónico."
            )
    # Materializa dataset + productos + DatasetManifest (idempotente); el adapter lee products.csv.
    dm = validate_data(disease, runs_root=runs_root)
    dataset_id = dm.dataset_id
    disease_id = dm.disease_id
    runs_base = runs_root or (_ROOT / "runs")
    dataset_dir = runs_base / dataset_id

    pol_digest = policy_digest(policy_name)
    seed = policy_seed(policy_name)
    used_engines = engines if engines else candidate_engines(policy_name)
    code_commit = _git_commit()

    # El stage `test` (2025) se abre UNA vez y SOLO con selección congelada; tunear con él está
    # prohibido: sería convertir el conjunto de aceptación en otro conjunto de tuning.
    sel: pd.DataFrame | None = None
    sel_manifest: dict[str, Any] = {}
    if stage == "test":
        policy = load_policy(policy_name)
        sel, sel_manifest = _load_selection_for_test(
            runs_base, selection_run_id, policy, dataset_id
        )
        control = acceptance.AcceptanceRule.from_policy(policy).control_engine
        # Solo las familias efectivamente seleccionadas + el control (nada de motores ociosos).
        used_engines = sorted({*sel["selected_engine"].unique(), control})

    # refit: los motores y las series salen de la selección ACEPTADA, nunca de --engines.
    final_sel: pd.DataFrame | None = None
    refit_prov: dict[str, Any] = {}
    origin: tuple[int, int] | None = None
    if command == "refit":
        policy = load_policy(policy_name)
        final_sel, _, refit_prov = _refit_context(runs_base, str(acceptance_run_id), dm, policy)
        used_engines = sorted(final_sel["selected_engine"].unique())
    elif command == "forecast":
        refit_dir = runs_base / str(refit_run_id)
        if not (refit_dir / "run_manifest.json").exists():
            raise RunnerError(f"no existe el run de refit {refit_run_id!r}")
        refit_man = RunManifest.read(refit_dir)
        if refit_man.command != "refit" or refit_man.status != STATUS_SUCCEEDED:
            raise RunnerError(f"{refit_run_id}: no es un refit exitoso ({refit_man.status})")
        if refit_man.dataset_id != dataset_id:
            raise RunnerError(f"{refit_run_id}: refit de otro dataset")
        used_engines = list(refit_man.engines)
        refit_prov = dict(refit_man.input_digests)
        origin = tuple(json.loads((refit_dir / "refit_summary.json").read_text())["train_end"])

    # variant identifica la ejecución dentro del run_id: stage (benchmark/tune) o h<N> (forecast).
    variant = f"h{horizon}" if command == "forecast" and horizon else stage
    if stage == "test":  # la identidad del run incluye la selección congelada que lo autoriza
        variant = f"test_{sel_manifest['selection_digest'][:12]}"
    if command == "refit":  # identidad = la aceptación y la selección final que la gobiernan
        variant = f"final_{refit_prov['final_selection_digest'][:12]}"
    if command == "forecast":
        variant = f"h{horizon}_{str(refit_run_id).rsplit('_', 1)[-1]}"
    run_id = compute_run_id(
        disease_id, dataset_id, command, variant, pol_digest, used_engines, seed, code_commit
    )
    run_dir = runs_base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if final_sel is not None:  # la selección utilizada viaja DENTRO del run de refit
        final_sel.to_csv(run_dir / refit_mod.SELECTION_FILE, index=False)

    # Contexto que el adapter (subprocess) necesita para localizar datos + política.
    (run_dir / "job_context.json").write_text(
        json.dumps(
            {
                "dataset_dir": str(dataset_dir),
                "dataset_id": dataset_id,
                "dataset_digest": dm.digests["dataset"],  # digest COMPLETO → TrainingSpec
                "disease_id": disease_id,
                "policy_name": policy_name,
                "policy_digest": pol_digest,
                "stage": stage,
                "seed": seed,
                "horizon": horizon if horizon else load_policy(policy_name).seasonal_horizon,
                "code_commit": code_commit,
                "selection_digest": (
                    sel_manifest.get("selection_digest") or refit_prov.get("selection_digest")
                ),
                "selection_run_id": (
                    selection_run_id if stage == "test" else refit_prov.get("selection_run_id")
                ),
                "acceptance_run_id": refit_prov.get("acceptance_run_id"),
                "acceptance_digest": refit_prov.get("acceptance_digest"),
                "refit_dir": str(runs_base / str(refit_run_id)) if refit_run_id else None,
                "refit_run_id": refit_run_id,
                "origin": list(origin) if origin else None,
                "exposure_source_id": registry.require(disease).exposure_source_id,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    digests = dict(dm.digests)
    if sel_manifest:
        digests["selection"] = sel_manifest["selection_digest"]
    digests.update({k: v for k, v in refit_prov.items() if k.endswith("digest")})
    man = run_engines(
        run_dir,
        disease_id,
        command,
        used_engines,
        dataset_id=dataset_id,
        stage=stage if command in ("benchmark", "tune") else None,
        policy_digest_value=pol_digest,
        seed=seed,
        code_commit=code_commit,
        input_digests=digests,
        counts=dm.counts,
        resume=resume,
    )
    # Un benchmark multi-motor exitoso emite el reporte comparativo (sin elegir ganador).
    if command == "benchmark" and man.status == STATUS_SUCCEEDED and len(used_engines) > 1:
        comparative_report(run_dir)
    if command == "refit" and man.status == STATUS_SUCCEEDED and final_sel is not None:
        refit_mod.write_summary(run_dir, man, final_sel, refit_prov, code_commit)
    if command == "forecast" and man.status == STATUS_SUCCEEDED:
        forecasting.finish_forecast(run_dir, man, runs_base / str(refit_run_id), code_commit)
    # El stage test cierra con el gate de aceptación: veredicto global y selección final.
    if stage == "test" and man.status == STATUS_SUCCEEDED and sel is not None:
        _finish_test_stage(
            run_dir,
            man,
            sel,
            sel_manifest,
            load_policy(policy_name),
            pd.read_csv(dataset_dir / "products.csv", dtype={"geography_id": str}),
            code_commit,
            str(selection_run_id),
        )
    return man
