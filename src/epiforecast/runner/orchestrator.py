"""F2/C2 — orquestación del runner genérico de padecimientos (carril E66; no toca neuro/Dengue).

- ``validate_data``: FUNCIONAL en C2. Construye el dataset base (41,792) + los 111 productos, los
  materializa bajo ``runs/<run_id>/`` y escribe ``run_manifest.v1`` (succeeded) con digests,
  artefactos validados y counts 64/47/111.
- ``run_engines``: por comando (benchmark/refit/forecast), lanza UN subprocess limpio por motor;
  resuelve el adapter (vacío en C2) → job rc=2; nunca aparenta éxito. Reanudación SOLO si el job
  está ``succeeded`` con artefactos validados (un .pkl existente NO cuenta). Todo bajo runs/<run_id>/.

Sin train real, sin publicación, sin DVC, sin git push.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from epiforecast.data.epi_aggregate import build_products
from epiforecast.data.epi_dataset import build_epi_dataset_v2
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner.contracts import SCHEMA_DATASET, SCHEMA_PRODUCTS
from epiforecast.runner.manifest import (
    CMD_VALIDATE_DATA,
    STATUS_FAILED,
    ArtifactRecord,
    RunManifest,
)

_ROOT = Path(__file__).resolve().parents[3]


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


def validate_data(disease: str, runs_root: Path | None = None) -> RunManifest:
    """Construye dataset base + 111 productos, los versiona y escribe run_manifest.v1 (succeeded)."""
    result = build_epi_dataset_v2(disease, runs_root=runs_root)
    catalog = load_geo_catalog()
    agg = build_products(result.dataset, catalog, result.config.disease_id)

    run_dir = result.run_dir
    products_path = run_dir / "products.csv"
    agg.products.to_csv(products_path, index=False)
    (run_dir / "lineage.json").write_text(
        json.dumps(agg.lineage, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    man = RunManifest(
        run_id=result.run_id,
        disease_id=result.config.disease_id,
        command=CMD_VALIDATE_DATA,
    )
    man.code_commit = _git_commit()
    man.input_digests = dict(result.digests)
    man.counts = {
        "base": agg.counts["base"],
        "derived": agg.counts["derived"],
        "products": agg.counts["products"],
    }
    man.start()
    man.add_artifact(
        ArtifactRecord(
            "epi_dataset_v2.csv", result.digests["dataset"], SCHEMA_DATASET, validated=True
        )
    )
    man.add_artifact(
        ArtifactRecord("products.csv", _sha256(products_path), SCHEMA_PRODUCTS, validated=True)
    )
    man.succeed()
    man.write(run_dir)
    return man


def _spawn_engine(
    run_dir: Path, engine: str, command: str, python_exe: str | None
) -> tuple[int, dict[str, Any] | None]:
    """Lanza el worker en un subprocess limpio; devuelve (exit_code, result.json | None)."""
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
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    result_path = run_dir / "jobs" / f"{engine}.result.json"
    result: dict[str, Any] | None = None
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    return proc.returncode, result


def run_engines(
    run_dir: Path,
    disease_id: str,
    command: str,
    engines: list[str],
    *,
    resume: bool = True,
    python_exe: str | None = None,
) -> RunManifest:
    """Ejecuta ``command`` para cada motor en subprocess limpio; actualiza y escribe el manifiesto."""
    if not engines:
        raise RunnerError(f"{command}: se requiere al menos un motor (--engines)")
    run_dir = Path(run_dir)

    # Reanudación: reutiliza el manifiesto SOLO si es del mismo comando; si no, arranca limpio.
    man: RunManifest | None = None
    mpath = run_dir / "run_manifest.json"
    if resume and mpath.exists():
        prev = RunManifest.read(run_dir)
        if prev.command == command:
            man = prev
    if man is None:
        man = RunManifest(run_id=run_dir.name, disease_id=disease_id, command=command)
    man.start()

    for engine in engines:
        prior = man.jobs.get(engine)
        if resume and prior is not None and prior.is_complete():
            continue  # succeeded + artefactos validados → no se re-ejecuta
        job = man.job(engine)
        # Reinicia el estado del job (un intento previo fallido/incompleto no se hereda).
        job.status = "pending"
        job.started_at = job.finished_at = None
        job.exit_code = job.error_type = job.error_message = None
        job.artifacts.clear()
        job.start()

        rc, result = _spawn_engine(run_dir, engine, command, python_exe)
        if result is not None and result.get("status") == "succeeded":
            arts = [
                ArtifactRecord(**{k: a[k] for k in ("path", "digest", "schema", "validated")})
                for a in (result.get("artifacts") or [])
            ]
            job.succeed(arts)
        elif result is not None:
            job.fail(
                int(result.get("exit_code") or rc or 1),
                str(result.get("error_type") or "EngineError"),
                str(result.get("error_message") or ""),
            )
        else:  # sin result.json: el worker no dejó señal → fallo por exit-code
            job.fail(rc or 1, "SubprocessError", f"subprocess terminó rc={rc} sin result.json")

    failed = [e for e, j in man.jobs.items() if j.status == STATUS_FAILED]
    if failed:
        codes = {man.jobs[e].exit_code for e in failed}
        man.fail(
            2 if codes == {2} else 1,
            "EngineJobsFailed",
            f"motores fallidos: {sorted(failed)}",
        )
    else:
        man.succeed()
    man.write(run_dir)
    return man


def run_command(
    disease: str,
    command: str,
    engines: list[str],
    *,
    runs_root: Path | None = None,
    resume: bool = True,
) -> RunManifest:
    """benchmark/refit/forecast: localiza el run del dataset (determinista) y orquesta los motores."""
    result = build_epi_dataset_v2(disease, runs_root=runs_root)
    return run_engines(result.run_dir, result.config.disease_id, command, engines, resume=resume)
