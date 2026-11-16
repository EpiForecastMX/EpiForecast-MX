"""Orquestador de extracción aislada por worktree detached — piloto Carbon alta1.

Ejecuta una pasada exclusiva de ``scripts.extrae_cuadro`` bajo contratos estrictos (``H1-H5``,
``H7``):
- Pines obligatorios: ``expected_commit`` (40 hex), ``expected_inventory_sha256`` (64 hex) y
  ``expected_validator_sha256`` (64 hex).
- Reanudación idempotente sin sobrescritura: si ``<id>_RUN_raw.json`` ya existe y valida, reporta
  ``REVERIFICADO_POR_HASH_SIN_REEXTRAER`` y conserva ``RUN_v2.json`` intacto.
- Evidencia completa (``H5``): captura ``stdout`` y ``stderr`` del subproceso en
  ``<out_dir>/<id>_extrae_subprocess.log`` (``0444``) con su SHA-256 en ``RUN_raw.json``; registra
  el listado previo real de ``data/interim`` (``pre_interim_entries``), ``sys.prefix``,
  ``sys.executable`` sin resolver (conservando ruta ``.venv``), versiones de Python/pandas/pypdf/
  camelot/ghostscript, y la ruta + SHA-256 de este propio guion orquestador
  (``orchestrator_script_file`` / ``orchestrator_script_sha256``).
- Persistencia ante fallo post-extracción (``H5(b)``): si el inventario o el estado posterior
  fallan tras correr el subproceso, escribe igualmente ``RUN_raw.json`` y ``RUN_v2.json``
  (``valida=False``, ``0444``) antes de terminar con ``rc=1``, sin perder la evidencia del intento.
  Recuperación: conservar intactos el worktree y ``out_dir`` fallidos y repetir en un worktree
  detached nuevo y un ``out_dir`` nuevo sobre el mismo commit.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
from typing import Any

from scripts.piloto_carbon_alta1 import valida_run_v2 as vr
import yaml


def _probe_child_environment(worktree: Path, env: dict[str, str]) -> dict[str, Any]:
    """Comprueba en subproceso limpio con cwd=worktree rutas de módulos, sys.prefix y versiones."""
    code = (
        "import importlib.metadata as md, json, platform, sys; "
        "import epiforecast.registry as reg, scripts.extrae_cuadro as ext; "
        "runner_orch = None\n"
        "try:\n"
        "    import epiforecast.runner.orchestrator as orch\n"
        "    runner_orch = orch.__file__\n"
        "except Exception:\n"
        "    runner_orch = None\n"
        "def ver(pkg):\n"
        "    try:\n"
        "        return md.version(pkg)\n"
        "    except Exception:\n"
        "        return None\n"
        "print(json.dumps({"
        "'registry_file': reg.__file__, "
        "'runner_orchestrator_file': runner_orch, "
        "'extrae_cuadro_file': ext.__file__, "
        "'sys_prefix': sys.prefix, "
        "'sys_executable_raw': sys.executable, "
        "'versions': {"
        "'python': platform.python_version(), "
        "'pandas': ver('pandas'), "
        "'pypdf': ver('pypdf'), "
        "'camelot_py': ver('camelot-py')"
        "}}))"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(worktree),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res.stdout.strip())
    gs_res = subprocess.run(
        ["gs", "--version"],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        check=False,
    )
    gs_ver = gs_res.stdout.strip() if gs_res.returncode == 0 else None
    data["versions"]["ghostscript"] = gs_ver
    data["registry_file"] = str(Path(data["registry_file"]).resolve())
    data["extrae_cuadro_file"] = str(Path(data["extrae_cuadro_file"]).resolve())
    if data.get("runner_orchestrator_file"):
        data["runner_orchestrator_file"] = str(Path(data["runner_orchestrator_file"]).resolve())
    return dict(data)


def _set_readonly(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def run_isolated_extraction(
    *,
    disease_id: str,
    worktree: Path,
    pdf_dir: Path,
    inventory_json: Path,
    out_dir: Path,
    pasada: str,
    expected_commit: str,
    expected_inventory_sha256: str,
    expected_validator_sha256: str,
    jobs: int = 4,
    validator_file: Path | None = None,
) -> int:
    """Ejecuta o reverifica por hash una corrida aislada de extracción con pines obligatorios."""
    if not vr.HEX40_RE.fullmatch(expected_commit or ""):
        raise RuntimeError("expected_commit ausente o no es SHA de 40 hex")
    if not vr.HEX64_RE.fullmatch(expected_inventory_sha256 or ""):
        raise RuntimeError("expected_inventory_sha256 ausente o no es SHA-256 de 64 hex")
    if not vr.HEX64_RE.fullmatch(expected_validator_sha256 or ""):
        raise RuntimeError("expected_validator_sha256 ausente o no es SHA-256 de 64 hex")

    wt = worktree.resolve()
    out = out_dir.resolve()
    pdfs = pdf_dir.resolve()
    inv = inventory_json.resolve()
    raw_meta_path = out / f"{disease_id}_RUN_raw.json"

    if raw_meta_path.is_file():
        rc_prev, v2_prev = vr.validate_single_run(
            run_raw_path=raw_meta_path,
            worktree=wt,
            out_dir=out,
            pdf_dir=pdfs,
            inventory_json=inv,
            expected_commit=expected_commit,
            expected_inventory_sha256=expected_inventory_sha256,
            expected_validator_sha256=expected_validator_sha256,
            validator_file=validator_file,
        )
        if rc_prev == 0 and v2_prev["valida"]:
            print(
                f"REVERIFICADO_POR_HASH_SIN_REEXTRAER id={disease_id} pasada={pasada} "
                f"csv={v2_prev['csv_sha256']}"
            )
            return 0
        raise RuntimeError(
            f"Existe {raw_meta_path} pero no valida ({v2_prev['fallas']}); "
            "evidencia previa preservada intacta sin sobrescribir."
        )

    head40 = vr.git_head_40(wt)
    if head40 != expected_commit:
        raise RuntimeError(f"HEAD del worktree ({head40}) != expected_commit ({expected_commit})")
    dirty = vr.git_dirty_entries(wt)
    if dirty:
        raise RuntimeError(f"Worktree sucio antes de extraer: {dirty}")

    val_target = (validator_file or (wt / vr.VALIDATOR_REL_PATH)).resolve()
    val_disk_sha = vr.sha256_file(val_target)
    if val_disk_sha != expected_validator_sha256:
        raise RuntimeError(
            f"Validador en worktree ({val_disk_sha}) != expected_validator_sha256 "
            f"({expected_validator_sha256})"
        )

    pad_cfg = yaml.safe_load((wt / "config" / "padecimientos.yaml").read_text(encoding="utf-8"))
    slug = vr.slug_for_disease(pad_cfg, disease_id)
    interim_dir = wt / "data" / "interim"
    pre_interim_existed = interim_dir.is_dir()
    pre_interim_entries = (
        sorted(p.name for p in interim_dir.iterdir()) if pre_interim_existed else []
    )
    interim_csv = interim_dir / f"{slug}_boletin.csv"
    interim_man = interim_dir / f"{slug}_extraccion_manifest.csv"
    if (
        interim_csv.exists()
        or interim_man.exists()
        or any(n.startswith(f"{slug}_") for n in pre_interim_entries)
    ):
        raise RuntimeError(
            f"data/interim ya contiene salidas para {slug} en {wt} ({pre_interim_entries}); "
            "abortando para no pisar ni reusar salidas rancias (F5)."
        )
    for existing_target in (
        out / f"{disease_id}_boletin.csv",
        out / f"{disease_id}_extraccion_manifest.csv",
        out / f"{disease_id}_RUN_v2.json",
        out / f"{disease_id}_extrae_subprocess.log",
        out / "SHA256SUMS",
    ):
        if existing_target.exists():
            raise RuntimeError(
                f"out_dir {out} ya contiene {existing_target.name}; no se sobrescribe evidencia."
            )

    inv_fallas_pre, inv_meta_pre = vr.verify_pdf_inventory(
        pdfs,
        inv,
        expected_inventory_sha256=expected_inventory_sha256,
    )
    if inv_fallas_pre:
        raise RuntimeError(f"Inventario PDF inválido antes de extraer: {inv_fallas_pre}")

    out.mkdir(parents=True, exist_ok=True)
    mpl_dir = out / ".mplconfig"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    single_threads = dict.fromkeys(vr.SINGLE_THREAD_VARS, "1")
    child_env = {
        **os.environ,
        **single_threads,
        "PYTHONPATH": f"{wt / 'src'}:{wt}",
        "MPLCONFIGDIR": str(mpl_dir),
    }
    probe_meta = _probe_child_environment(wt, child_env)
    expected_reg = str((wt / "src" / "epiforecast" / "registry.py").resolve())
    if probe_meta["registry_file"] != expected_reg:
        raise RuntimeError(f"registry.__file__ ({probe_meta['registry_file']}) != {expected_reg}")

    orch_script_path = Path(__file__).resolve()
    orch_script_sha = vr.sha256_file(orch_script_path)

    hashes_inicio = vr.compute_tracked_hashes(wt)
    t0_epoch = time.time()
    inicio_utc = datetime.now(UTC).isoformat()

    argv_cmd = [
        sys.executable,
        "-m",
        "scripts.extrae_cuadro",
        "--disease",
        disease_id,
        "--pdf-dir",
        str(pdfs),
        "--jobs",
        str(jobs),
    ]
    proc = subprocess.run(
        argv_cmd,
        cwd=str(wt),
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )

    fin_utc = datetime.now(UTC).isoformat()
    log_path = out / f"{disease_id}_extrae_subprocess.log"
    with log_path.open("x", encoding="utf-8") as fh:
        fh.write("=== STDOUT ===\n")
        fh.write(proc.stdout or "")
        if proc.stdout and not proc.stdout.endswith("\n"):
            fh.write("\n")
        fh.write("=== STDERR ===\n")
        fh.write(proc.stderr or "")
        if proc.stderr and not proc.stderr.endswith("\n"):
            fh.write("\n")
    _set_readonly(log_path)
    log_sha = vr.sha256_file(log_path)

    hashes_fin = vr.compute_tracked_hashes(wt)
    inv_fallas_post, inv_meta_post = vr.verify_pdf_inventory(
        pdfs,
        inv,
        expected_inventory_sha256=expected_inventory_sha256,
    )

    copy_csv = out / f"{disease_id}_boletin.csv"
    copy_man = out / f"{disease_id}_extraccion_manifest.csv"
    if interim_csv.is_file():
        shutil.copy2(interim_csv, copy_csv)
        _set_readonly(copy_csv)
    if interim_man.is_file():
        shutil.copy2(interim_man, copy_man)
        _set_readonly(copy_man)

    csv_sha = vr.sha256_file(copy_csv)
    man_sha = vr.sha256_file(copy_man)
    if csv_sha and man_sha:
        sums_path = out / "SHA256SUMS"
        with sums_path.open("x", encoding="utf-8") as fh:
            fh.write(f"{csv_sha}  {copy_csv.name}\n{man_sha}  {copy_man.name}\n")
        _set_readonly(sums_path)

    run_raw: dict[str, Any] = {
        "schema": "piloto_carbon_alta1.run_raw.v2",
        "id": disease_id,
        "slug": slug,
        "pasada": pasada,
        "snapshot_sha": head40,
        "cwd": str(wt),
        "python_executable_argv": sys.executable,
        "python_executable_resolved": str(Path(sys.executable).resolve()),
        "sys_prefix": probe_meta["sys_prefix"],
        "tool_versions": probe_meta["versions"],
        "pythonpath": child_env["PYTHONPATH"],
        "mplconfigdir": child_env["MPLCONFIGDIR"],
        "single_thread_env": single_threads,
        "orchestrator_script_file": str(orch_script_path),
        "orchestrator_script_sha256": orch_script_sha,
        "registry_file": probe_meta["registry_file"],
        "runner_orchestrator_file": probe_meta["runner_orchestrator_file"],
        "extrae_cuadro_file": probe_meta["extrae_cuadro_file"],
        "argv": argv_cmd,
        "jobs": jobs,
        "pre_interim_dir_existed": pre_interim_existed,
        "pre_interim_entries": pre_interim_entries,
        "pre_interim_absent": True,
        "t0_epoch": t0_epoch,
        "inicio_utc": inicio_utc,
        "fin_utc": fin_utc,
        "rc": proc.returncode,
        "subprocess_log_path": str(log_path),
        "subprocess_log_sha256": log_sha,
        "tracked_hashes_inicio": hashes_inicio,
        "tracked_hashes_fin": hashes_fin,
        "inventory_json": str(inv),
        "inventory_sha256_inicio": inv_meta_pre["inventory_sha256"],
        "inventory_sha256_fin": inv_meta_post["inventory_sha256"],
        "post_inventory_fallas": inv_fallas_post,
        "csv_sha256": csv_sha,
        "manifiesto_sha256": man_sha,
    }
    with raw_meta_path.open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(run_raw, ensure_ascii=False, indent=2) + "\n")
    _set_readonly(raw_meta_path)

    rc_v2, res_v2 = vr.validate_single_run(
        run_raw_path=raw_meta_path,
        worktree=wt,
        out_dir=out,
        pdf_dir=pdfs,
        inventory_json=inv,
        expected_commit=expected_commit,
        expected_inventory_sha256=expected_inventory_sha256,
        expected_validator_sha256=expected_validator_sha256,
        validator_file=validator_file,
    )
    print(
        f"{disease_id} {pasada} {'VALIDA' if res_v2['valida'] else 'FALLA'} "
        f"csv={res_v2['csv_sha256']} fallas={res_v2['fallas']}"
    )
    return int(rc_v2)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--disease", required=True)
    ap.add_argument("--worktree", type=Path, required=True)
    ap.add_argument("--pdf-dir", type=Path, required=True)
    ap.add_argument("--inventory-json", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--pasada", required=True)
    ap.add_argument("--expected-commit", required=True)
    ap.add_argument("--expected-inventory-sha256", required=True)
    ap.add_argument("--expected-validator-sha256", required=True)
    ap.add_argument("--jobs", type=int, default=4)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return run_isolated_extraction(
        disease_id=args.disease,
        worktree=args.worktree,
        pdf_dir=args.pdf_dir,
        inventory_json=args.inventory_json,
        out_dir=args.out_dir,
        pasada=args.pasada,
        expected_commit=args.expected_commit,
        expected_inventory_sha256=args.expected_inventory_sha256,
        expected_validator_sha256=args.expected_validator_sha256,
        jobs=args.jobs,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
