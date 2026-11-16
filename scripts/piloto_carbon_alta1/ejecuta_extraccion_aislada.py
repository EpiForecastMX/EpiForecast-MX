"""Orquestador de extracción aislada por worktree detached — piloto Carbon alta1.

Ejecuta una pasada exclusiva de ``scripts.extrae_cuadro`` bajo contratos estrictos:
- Si ``<out_dir>/<id>_RUN_raw.json`` ya existe y ``valida_run_v2`` la revalida como válida para el
  mismo commit40 e inventario sellado, NO reextrae: reporta ``REVERIFICADO_POR_HASH_SIN_REEXTRAER``.
- Exige ``HEAD == expected_commit`` (40 hex) y árbol limpio antes de arrancar.
- Exige que ``<worktree>/data/interim/<slug>_boletin.csv`` y ``_extraccion_manifest.csv`` NO existan
  al iniciar (no copia ni pisa salidas viejas).
- Verifica el inventario PDF sellado antes y después de la extracción.
- Lanza ``sys.executable -m scripts.extrae_cuadro`` con ``cwd=<worktree>``,
  ``PYTHONPATH=<worktree>/src:<worktree>``, ``MPLCONFIGDIR`` propio escribible e hilos numéricos a 1.
- Archiva copias de sólo lectura (``0444``) y ``SHA256SUMS`` en ``<out_dir>``, escribe
  ``<id>_RUN_raw.json`` y ejecuta ``valida_run_v2.validate_single_run`` para emitir ``<id>_RUN_v2.json``.
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


def _probe_import_paths(worktree: Path, env: dict[str, str]) -> dict[str, str]:
    """Comprueba en subproceso limpio con cwd=worktree las rutas reales de los módulos."""
    code = (
        "import json, epiforecast.registry as reg, epiforecast.runner.orchestrator as orch, "
        "scripts.extrae_cuadro as ext; "
        "print(json.dumps({'registry_file': reg.__file__, 'orchestrator_file': orch.__file__, "
        "'extrae_cuadro_file': ext.__file__}))"
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
    return {k: str(Path(v).resolve()) for k, v in data.items()}


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
    expected_inventory_sha256: str | None = None,
    expected_validator_sha256: str | None = None,
    jobs: int = 4,
) -> int:
    """Ejecuta o reverifica por hash una corrida aislada de extracción."""
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
            verify_pdf_hashes=True,
        )
        if rc_prev == 0 and v2_prev["valida"]:
            print(
                f"REVERIFICADO_POR_HASH_SIN_REEXTRAER id={disease_id} pasada={pasada} "
                f"csv={v2_prev['csv_sha256']}"
            )
            return 0
        raise RuntimeError(
            f"Existe {raw_meta_path} pero no valida ({v2_prev['fallas']}); "
            "no se sobrescribe evidencia previa."
        )

    head40 = vr.git_head_40(wt)
    if head40 != expected_commit:
        raise RuntimeError(f"HEAD del worktree ({head40}) != expected_commit ({expected_commit})")
    dirty = vr.git_dirty_entries(wt)
    if dirty:
        raise RuntimeError(f"Worktree sucio antes de extraer: {dirty}")

    pad_cfg = yaml.safe_load((wt / "config" / "padecimientos.yaml").read_text(encoding="utf-8"))
    slug = vr.slug_for_disease(pad_cfg, disease_id)
    interim_csv = wt / "data" / "interim" / f"{slug}_boletin.csv"
    interim_man = wt / "data" / "interim" / f"{slug}_extraccion_manifest.csv"
    if interim_csv.exists() or interim_man.exists():
        raise RuntimeError(
            f"data/interim ya contiene salidas para {slug} en {wt}; abortando para no pisar ni "
            "reusar salidas rancias (F5)."
        )
    if (out / f"{disease_id}_boletin.csv").exists() or (
        out / f"{disease_id}_extraccion_manifest.csv"
    ).exists():
        raise RuntimeError(f"out_dir {out} ya contiene salidas previas; use un out_dir limpio.")

    inv_fallas_pre, inv_meta_pre = vr.verify_pdf_inventory(
        pdfs,
        inv,
        expected_inventory_sha256=expected_inventory_sha256,
        verify_pdf_hashes=True,
    )
    if inv_fallas_pre:
        raise RuntimeError(f"Inventario PDF inválido antes de extraer: {inv_fallas_pre}")

    mpl_dir = out / ".mplconfig"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    single_threads = dict.fromkeys(vr.SINGLE_THREAD_VARS, "1")
    child_env = {
        **os.environ,
        **single_threads,
        "PYTHONPATH": f"{wt / 'src'}:{wt}",
        "MPLCONFIGDIR": str(mpl_dir),
    }
    import_paths = _probe_import_paths(wt, child_env)
    expected_reg = str((wt / "src" / "epiforecast" / "registry.py").resolve())
    if import_paths["registry_file"] != expected_reg:
        raise RuntimeError(
            f"registry.__file__ ({import_paths['registry_file']}) != {expected_reg}"
        )

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
    proc = subprocess.run(argv_cmd, cwd=str(wt), env=child_env, check=False)

    fin_utc = datetime.now(UTC).isoformat()
    hashes_fin = vr.compute_tracked_hashes(wt)
    inv_fallas_post, inv_meta_post = vr.verify_pdf_inventory(
        pdfs,
        inv,
        expected_inventory_sha256=expected_inventory_sha256,
        verify_pdf_hashes=True,
    )
    if inv_fallas_post:
        raise RuntimeError(f"Inventario PDF cambió o falló tras extraer: {inv_fallas_post}")

    out.mkdir(parents=True, exist_ok=True)
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
        sums_path.write_text(
            f"{csv_sha}  {copy_csv.name}\n{man_sha}  {copy_man.name}\n",
            encoding="utf-8",
        )
        _set_readonly(sums_path)

    run_raw: dict[str, Any] = {
        "schema": "piloto_carbon_alta1.run_raw.v1",
        "id": disease_id,
        "slug": slug,
        "pasada": pasada,
        "snapshot_sha": head40,
        "cwd": str(wt),
        "python_executable": str(Path(sys.executable).resolve()),
        "pythonpath": child_env["PYTHONPATH"],
        "mplconfigdir": child_env["MPLCONFIGDIR"],
        "single_thread_env": single_threads,
        "registry_file": import_paths["registry_file"],
        "orchestrator_file": import_paths["orchestrator_file"],
        "extrae_cuadro_file": import_paths["extrae_cuadro_file"],
        "argv": argv_cmd,
        "jobs": jobs,
        "pre_interim_absent": True,
        "t0_epoch": t0_epoch,
        "inicio_utc": inicio_utc,
        "fin_utc": fin_utc,
        "rc": proc.returncode,
        "tracked_hashes_inicio": hashes_inicio,
        "tracked_hashes_fin": hashes_fin,
        "inventory_json": str(inv),
        "inventory_sha256_inicio": inv_meta_pre["inventory_sha256"],
        "inventory_sha256_fin": inv_meta_post["inventory_sha256"],
        "csv_sha256": csv_sha,
        "manifiesto_sha256": man_sha,
    }
    raw_meta_path.write_text(
        json.dumps(run_raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
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
        verify_pdf_hashes=True,
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
    ap.add_argument("--expected-inventory-sha256", default=None)
    ap.add_argument("--expected-validator-sha256", default=None)
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
