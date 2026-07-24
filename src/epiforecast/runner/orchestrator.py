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
from pathlib import Path
import secrets
import subprocess
import sys
from typing import Any

from epiforecast.data.epi_aggregate import build_products
from epiforecast.data.epi_dataset import build_epi_dataset_v2
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner.contracts import SCHEMA_DATASET, SCHEMA_PRODUCTS
from epiforecast.runner.manifest import (
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    ArtifactRecord,
    DatasetManifest,
    JobRecord,
    RunManifest,
    compute_run_id,
)
from epiforecast.runner.policy import candidate_engines, policy_digest, policy_seed
from epiforecast.runner.report import comparative_report

_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_LINEAGE = "lineage.v1"


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
    proc = subprocess.run(cmd, capture_output=True, text=True)
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
            stage=stage if stage in ("smoke", "full") else None,
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
) -> RunManifest:
    """benchmark/refit/forecast: materializa el dataset (dataset_id) y orquesta los motores en runs/<run_id>/."""
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

    # variant identifica la ejecución dentro del run_id: stage (benchmark) o h<N> (forecast).
    variant = f"h{horizon}" if command == "forecast" and horizon else stage
    run_id = compute_run_id(
        disease_id, dataset_id, command, variant, pol_digest, used_engines, seed, code_commit
    )
    run_dir = runs_base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Contexto que el adapter (subprocess) necesita para localizar datos + política.
    (run_dir / "job_context.json").write_text(
        json.dumps(
            {
                "dataset_dir": str(dataset_dir),
                "dataset_id": dataset_id,
                "disease_id": disease_id,
                "policy_name": policy_name,
                "stage": stage,
                "seed": seed,
                "horizon": horizon,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    man = run_engines(
        run_dir,
        disease_id,
        command,
        used_engines,
        dataset_id=dataset_id,
        stage=stage if command == "benchmark" else None,
        policy_digest_value=pol_digest,
        seed=seed,
        code_commit=code_commit,
        input_digests=dm.digests,
        counts=dm.counts,
        resume=resume,
    )
    # Un benchmark multi-motor exitoso emite el reporte comparativo (sin elegir ganador).
    if command == "benchmark" and man.status == STATUS_SUCCEEDED and len(used_engines) > 1:
        comparative_report(run_dir)
    return man
