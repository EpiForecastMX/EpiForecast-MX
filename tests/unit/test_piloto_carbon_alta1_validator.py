"""Pruebas unitarias sintéticas del validador RUN_v2 (SHA40) y de la config QA aislada.

Todas las pruebas del validador operan sobre repositorios git e inventarios PDF 100 % sintéticos
en ``tmp_path``, cubriendo:
- Pines obligatorios en API y CLI (``ROOT_V2``): ``expected_commit``, ``expected_inventory_sha256``
  y ``expected_validator_sha256`` requeridos; rechazo de ``--skip-pdf-hashes`` y de entradas de
  inventario sin ``sha256``/``bytes``.
- Inmutabilidad de evidencia previa (``ROOT_V1``): prohibición de ``chmod +w`` y de sobrescritura
  sobre ``RUN_v2.json`` (válido o fallido) y sobre ``canon_dir`` (no-op idéntico con reporte
  aditivo frente a conflicto/fallo preservando bytes originales intactos).
- Mutación de hashes, inventario, frescura (``mtime < t0``), árbol sucio (``dirty``) y manifiesto.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
from typing import Any

import pytest
from scripts.piloto_carbon_alta1 import ejecuta_extraccion_aislada as ea
from scripts.piloto_carbon_alta1 import valida_run_v2 as vr
import yaml

from epiforecast import registry
from epiforecast.data.extraction import cuadro_extractor
from epiforecast.registry_doctor import diagnose

pytestmark = pytest.mark.unit


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()


def _build_synthetic_env(
    tmp_path: Path, *, name: str = "wt_a"
) -> tuple[Path, Path, Path, Path, str, str, str, float]:
    """Construye worktree git sintético en commit40 + 3 PDFs reales pequeños + corrida válida."""
    base_tmp = tmp_path.resolve()
    wt = base_tmp / name
    for rel_dir in (
        "config/data",
        "src/epiforecast/data/extraction",
        "scripts/piloto_carbon_alta1",
        "data/interim",
    ):
        (wt / rel_dir).mkdir(parents=True, exist_ok=True)

    (wt / ".gitignore").write_text("/data/\n/runs/\n", encoding="utf-8")
    cuadros = {
        "version": 1,
        "cuadro_groups": {
            "g_sint": {
                "n_states_expected": 2,
                "diseases": [{"id": "sint_id", "keyword": "Sint", "block_index": 0}],
                "source_exclusions": [
                    {"file": "2014_sem01.pdf", "diseases": ["sint_id"]},
                    {"file": "2016_sem20.pdf", "diseases": ["sint_id"], "keep_period": True},
                ],
            }
        },
    }
    pad = {"version": 1, "padecimientos": [{"id": "sint_id", "slug": "sint_id"}]}
    (wt / "config/data/cuadros.yaml").write_text(
        yaml.safe_dump(cuadros, sort_keys=False), encoding="utf-8"
    )
    (wt / "config/padecimientos.yaml").write_text(
        yaml.safe_dump(pad, sort_keys=False), encoding="utf-8"
    )
    (wt / "src/epiforecast/registry.py").write_text("# sint registry\n", encoding="utf-8")
    for rel in vr.TRACKED_EXTRACTION_INPUTS:
        target = wt / rel
        if not target.exists():
            target.write_text(f"# sint {rel}\n", encoding="utf-8")

    real_val = Path(vr.__file__).resolve()
    shutil.copy2(real_val, wt / vr.VALIDATOR_REL_PATH)
    val_sha = vr.sha256_file(wt / vr.VALIDATOR_REL_PATH)
    assert val_sha is not None

    _git(wt, "init", "-q")
    _git(wt, "config", "user.email", "qa@sint.local")
    _git(wt, "config", "user.name", "QA Sint")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "chore(qa): synthetic snapshot")
    sha40 = _git(wt, "rev-parse", "HEAD")

    pdf_dir = base_tmp / "source_pdfs"
    pdf_dir.mkdir(exist_ok=True)
    pdf_specs: list[dict[str, Any]] = []
    for fname in ("2014_sem01.pdf", "2014_sem02.pdf", "2016_sem20.pdf"):
        p = pdf_dir / fname
        payload = f"%PDF-1.4 synthetic {fname}\n".encode()
        p.write_bytes(payload)
        pdf_specs.append({"file": fname, "bytes": len(payload), "sha256": _sha256_bytes(payload)})

    inv_json = base_tmp / "ROOT_PDF_INVENTORY.json"
    inv_json.write_text(
        json.dumps({"schema": "pilot_pdf_inventory.v1", "count": 3, "files": pdf_specs}, indent=2),
        encoding="utf-8",
    )
    inv_sha = vr.sha256_file(inv_json)
    assert inv_sha is not None

    t0 = time.time() - 2.0
    csv_text = (
        "Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_hombres,"
        "Acumulado_mujeres,Acumulado_anio_anterior\n"
        "2014,02,Aguascalientes,Sint,1,1,0,0\n"
        "2014,02,Zacatecas,Sint,2,1,1,0\n"
        "2016,20,Aguascalientes,Sint,,,,\n"
        "2016,20,Zacatecas,Sint,,,,\n"
    )
    man_text = (
        "file,year,week,page,layout,n_states,status,reason\n"
        "2014_sem01.pdf,2014,1,,,0,excluded,excluido: previo\n"
        "2014_sem02.pdf,2014,2,22,4col_prev,2,ok,ok\n"
        "2016_sem20.pdf,2016,20,,,0,excluded,excluido: errata\n"
    )
    interim_csv = wt / "data/interim/sint_id_boletin.csv"
    interim_man = wt / "data/interim/sint_id_extraccion_manifest.csv"
    interim_csv.write_text(csv_text, encoding="utf-8")
    interim_man.write_text(man_text, encoding="utf-8")

    out_dir = base_tmp / f"out_{name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    copy_csv = out_dir / "sint_id_boletin.csv"
    copy_man = out_dir / "sint_id_extraccion_manifest.csv"
    shutil.copy2(interim_csv, copy_csv)
    shutil.copy2(interim_man, copy_man)

    tracked_hashes = vr.compute_tracked_hashes(wt)
    run_raw = {
        "schema": "piloto_carbon_alta1.run_raw.v1",
        "id": "sint_id",
        "slug": "sint_id",
        "pasada": name,
        "snapshot_sha": sha40,
        "cwd": str(wt.resolve()),
        "single_thread_env": dict.fromkeys(vr.SINGLE_THREAD_VARS, "1"),
        "registry_file": str((wt / "src/epiforecast/registry.py").resolve()),
        "extrae_cuadro_file": str((wt / "scripts/extrae_cuadro.py").resolve()),
        "pre_interim_absent": True,
        "t0_epoch": t0,
        "inicio_utc": datetime.fromtimestamp(t0, UTC).isoformat(),
        "fin_utc": datetime.now(UTC).isoformat(),
        "rc": 0,
        "tracked_hashes_inicio": tracked_hashes,
        "tracked_hashes_fin": tracked_hashes,
        "inventory_sha256_inicio": inv_sha,
        "inventory_sha256_fin": inv_sha,
        "csv_sha256": vr.sha256_file(copy_csv),
        "manifiesto_sha256": vr.sha256_file(copy_man),
    }
    (out_dir / "sint_id_RUN_raw.json").write_text(json.dumps(run_raw, indent=2), encoding="utf-8")
    return wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, t0


def test_config_aislada_sifilis_adquirida_invisible_y_doctor_verde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = Path(registry.__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)
    spec = registry.require("sifilis_adquirida_a51")
    assert spec.data_name == "Sífilis adquirida"
    assert spec.artifact_key == "Sifilis_Adquirida_A51"
    assert spec.cie_codes == ("A51", "A52", "A53")
    assert spec.exposure_source_id == "inegi_cpv2020_static"
    assert spec.lifecycle == "configured"
    assert spec.channels == ()
    assert spec.gallery_enabled is False
    assert spec.selection_policy == "rolling_cv_v1"
    assert "Sífilis adquirida" not in registry.published_members()
    assert registry.try_get("sifilis") is None
    assert registry.try_get("a50") is None
    assert [p for p in diagnose("sifilis_adquirida_a51") if p.severity == "error"] == []

    grupo = cuadro_extractor.load_group("cuadro_6_sifilis_adquirida")
    assert grupo["observation_lag_weeks"] == 1
    assert grupo["n_states_expected"] == 32
    assert grupo["inner_block_columns"] == {12: [8, 4]}
    exc_01 = cuadro_extractor.source_exclusion(grupo, "2014_sem01.pdf", "sifilis_adquirida_a51")
    exc_20 = cuadro_extractor.source_exclusion(grupo, "2016_sem20.pdf", "sifilis_adquirida_a51")
    assert exc_01 is not None and not exc_01.get("keep_period", False)
    assert exc_20 is not None and exc_20["keep_period"] is True


def test_valida_run_v2_acepta_corrida_limpia_sha40_y_sella_readonly(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(tmp_path)
    rc, res = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 0, f"fallas inesperadas: {res['fallas']}"
    assert res["valida"] is True and res["fallas"] == []
    assert len(res["snapshot_sha"]) == 40 and res["snapshot_sha"] == sha40
    assert res["csv_rows"] == 4
    run_v2_path = out_dir / "sint_id_RUN_v2.json"
    assert not (run_v2_path.stat().st_mode & stat.S_IWUSR)


def test_root_v2_cli_exige_tres_pines_y_rechaza_skip_pdf_hashes(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(tmp_path)
    base_single = [
        "single",
        "--run-raw",
        str(out_dir / "sint_id_RUN_raw.json"),
        "--worktree",
        str(wt),
        "--out-dir",
        str(out_dir),
        "--pdf-dir",
        str(pdf_dir),
        "--inventory-json",
        str(inv_json),
    ]
    # Omitir cualquiera de los 3 pines en CLI debe abortar con SystemExit != 0
    with pytest.raises(SystemExit) as exc1:
        vr.main([*base_single, "--expected-commit", sha40, "--expected-inventory-sha256", inv_sha])
    assert exc1.value.code != 0

    with pytest.raises(SystemExit) as exc2:
        vr.main([*base_single, "--expected-commit", sha40, "--expected-validator-sha256", val_sha])
    assert exc2.value.code != 0

    with pytest.raises(SystemExit) as exc3:
        vr.main(
            [
                *base_single,
                "--expected-inventory-sha256",
                inv_sha,
                "--expected-validator-sha256",
                val_sha,
            ]
        )
    assert exc3.value.code != 0

    # --skip-pdf-hashes ya no existe y debe ser rechazado por argparse
    with pytest.raises(SystemExit) as exc_skip:
        vr.main(
            [
                *base_single,
                "--expected-commit",
                sha40,
                "--expected-inventory-sha256",
                inv_sha,
                "--expected-validator-sha256",
                val_sha,
                "--skip-pdf-hashes",
            ]
        )
    assert exc_skip.value.code != 0

    # También el orquestador CLI exige los 3 pines
    with pytest.raises(SystemExit) as exc_orch:
        ea.main(
            [
                "--disease",
                "sint_id",
                "--worktree",
                str(wt),
                "--pdf-dir",
                str(pdf_dir),
                "--inventory-json",
                str(inv_json),
                "--out-dir",
                str(out_dir),
                "--pasada",
                "corrida_a",
                "--expected-commit",
                sha40,
            ]
        )
    assert exc_orch.value.code != 0

    # En API Python, pines vacíos o malformados jamás producen valida=True
    for bad_commit, bad_inv, bad_val in [
        ("", inv_sha, val_sha),
        (sha40, "corto", val_sha),
        (sha40, inv_sha, "z" * 64),
    ]:
        out_bad = tmp_path / f"bad_{bad_commit[:2]}_{bad_inv[:2]}_{bad_val[:2]}"
        shutil.copytree(out_dir, out_bad)
        rc_b, res_b = vr.validate_single_run(
            run_raw_path=out_bad / "sint_id_RUN_raw.json",
            worktree=wt,
            out_dir=out_bad,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            expected_commit=bad_commit,
            expected_inventory_sha256=bad_inv,
            expected_validator_sha256=bad_val,
            validator_file=wt / vr.VALIDATOR_REL_PATH,
        )
        assert rc_b == 1 and res_b["valida"] is False


def test_root_v2_inventario_sin_sha256_por_pdf_falla_cerrado(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, _, val_sha, _ = _build_synthetic_env(tmp_path)
    inv_doc = json.loads(inv_json.read_text(encoding="utf-8"))
    del inv_doc["files"][0]["sha256"]
    inv_json.write_text(json.dumps(inv_doc, indent=2), encoding="utf-8")
    new_inv_sha = vr.sha256_file(inv_json)
    assert new_inv_sha is not None
    raw_doc = json.loads((out_dir / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw_doc["inventory_sha256_inicio"] = new_inv_sha
    raw_doc["inventory_sha256_fin"] = new_inv_sha
    (out_dir / "sint_id_RUN_raw.json").write_text(json.dumps(raw_doc, indent=2), encoding="utf-8")

    rc, res = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=new_inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 1 and res["valida"] is False
    assert any("sin bytes o sha256 de 64 hex" in f for f in res["fallas"])


def test_root_v1_run_v2_valido_es_noop_intacto_y_fallido_jamas_se_sobrescribe(
    tmp_path: Path,
) -> None:
    # 1) RUN_v2 válido existente: revalidación no toca bytes ni permisos y crea informe aditivo
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(
        tmp_path / "ok_case"
    )
    rc1, _ = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc1 == 0
    v2_path = out_dir / "sint_id_RUN_v2.json"
    orig_bytes = v2_path.read_bytes()
    orig_mode = v2_path.stat().st_mode

    rc2, res2 = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc2 == 0 and res2["valida"] is True
    assert v2_path.read_bytes() == orig_bytes
    assert v2_path.stat().st_mode == orig_mode
    assert Path(res2["revalidacion_aditiva"]["report_path"]).is_file()

    # Si después se corrompe la copia CSV, RUN_v2 original sigue byte-idéntico y falla aditivamente
    (out_dir / "sint_id_boletin.csv").write_text("alterado\n", encoding="utf-8")
    rc3, res3 = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc3 == 1 and res3["valida"] is False
    assert v2_path.read_bytes() == orig_bytes
    assert Path(res3["revalidacion_aditiva"]["report_path"]).is_file()

    # 2) RUN_v2 fallido original (rc=1): jamás puede sobrescribirse ni volverse válido en sitio
    wt_f, out_f, pdf_f, inv_f, sha_f, inv_sha_f, val_sha_f, _ = _build_synthetic_env(
        tmp_path / "fail_case"
    )
    raw_f = json.loads((out_f / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw_f["rc"] = 2
    (out_f / "sint_id_RUN_raw.json").write_text(json.dumps(raw_f, indent=2), encoding="utf-8")
    rc_fail1, _ = vr.validate_single_run(
        run_raw_path=out_f / "sint_id_RUN_raw.json",
        worktree=wt_f,
        out_dir=out_f,
        pdf_dir=pdf_f,
        inventory_json=inv_f,
        expected_commit=sha_f,
        expected_inventory_sha256=inv_sha_f,
        expected_validator_sha256=val_sha_f,
        validator_file=wt_f / vr.VALIDATOR_REL_PATH,
    )
    assert rc_fail1 == 1
    failed_v2_path = out_f / "sint_id_RUN_v2.json"
    failed_orig_bytes = failed_v2_path.read_bytes()

    # Aunque alguien edite RUN_raw a rc=0 después, RUN_v2 fallido original no se sobrescribe y falla
    raw_f["rc"] = 0
    (out_f / "sint_id_RUN_raw.json").write_text(json.dumps(raw_f, indent=2), encoding="utf-8")
    rc_fail2, res_fail2 = vr.validate_single_run(
        run_raw_path=out_f / "sint_id_RUN_raw.json",
        worktree=wt_f,
        out_dir=out_f,
        pdf_dir=pdf_f,
        inventory_json=inv_f,
        expected_commit=sha_f,
        expected_inventory_sha256=inv_sha_f,
        expected_validator_sha256=val_sha_f,
        validator_file=wt_f / vr.VALIDATOR_REL_PATH,
    )
    assert rc_fail2 == 1 and res_fail2["valida"] is False
    assert failed_v2_path.read_bytes() == failed_orig_bytes


def test_valida_run_v2_rechaza_mutacion_hash_csv_o_validador(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(tmp_path)
    (out_dir / "sint_id_boletin.csv").write_text("corrupto\n", encoding="utf-8")
    rc1, res1 = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc1 == 1 and res1["valida"] is False
    assert any("csv" in f for f in res1["fallas"])

    wt2, out2, pdf2, inv2, sha2, inv_sha2, val_sha2, _ = _build_synthetic_env(tmp_path / "sub2")
    mutated_val = tmp_path / "mutated_validator.py"
    mutated_val.write_text("# validador alterado\n", encoding="utf-8")
    rc2, res2 = vr.validate_single_run(
        run_raw_path=out2 / "sint_id_RUN_raw.json",
        worktree=wt2,
        out_dir=out2,
        pdf_dir=pdf2,
        inventory_json=inv2,
        expected_commit=sha2,
        expected_inventory_sha256=inv_sha2,
        expected_validator_sha256=val_sha2,
        validator_file=mutated_val,
    )
    assert rc2 == 1 and any("validador en disco" in f for f in res2["fallas"])


def test_valida_run_v2_rechaza_mutacion_inventario_pdf(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(tmp_path)
    (pdf_dir / "2014_sem02.pdf").write_bytes(b"%PDF-1.4 tampered bytes!!\n")
    rc, res = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 1 and any("inventario" in f for f in res["fallas"])

    wt_e, out_e, pdf_e, inv_e, sha_e, inv_sha_e, val_sha_e, _ = _build_synthetic_env(
        tmp_path / "extra_case"
    )
    (pdf_e / "2099_sem01.pdf").write_bytes(b"%PDF-1.4 extra\n")
    rc_extra, res_extra = vr.validate_single_run(
        run_raw_path=out_e / "sint_id_RUN_raw.json",
        worktree=wt_e,
        out_dir=out_e,
        pdf_dir=pdf_e,
        inventory_json=inv_e,
        expected_commit=sha_e,
        expected_inventory_sha256=inv_sha_e,
        expected_validator_sha256=val_sha_e,
        validator_file=wt_e / vr.VALIDATOR_REL_PATH,
    )
    assert rc_extra == 1 and any("sobran" in f for f in res_extra["fallas"])


def test_valida_run_v2_rechaza_archivo_no_fresco(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, t0 = _build_synthetic_env(tmp_path)
    interim_csv = wt / "data/interim/sint_id_boletin.csv"
    os.utime(interim_csv, (t0 - 120.0, t0 - 120.0))
    rc, res = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 1 and any("no es fresco" in f for f in res["fallas"])


def test_valida_run_v2_rechaza_worktree_dirty_o_commit_distinto(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(tmp_path)
    (wt / "scripts/extrae_cuadro.py").write_text("# dirty change\n", encoding="utf-8")
    rc, res = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 1 and any("dirty" in f for f in res["fallas"])

    wt2, out2, pdf2, inv2, _, inv_sha2, val_sha2, _ = _build_synthetic_env(tmp_path / "wrong_sha")
    rc_bad_sha, res_bad_sha = vr.validate_single_run(
        run_raw_path=out2 / "sint_id_RUN_raw.json",
        worktree=wt2,
        out_dir=out2,
        pdf_dir=pdf2,
        inventory_json=inv2,
        expected_commit="0" * 40,
        expected_inventory_sha256=inv_sha2,
        expected_validator_sha256=val_sha2,
        validator_file=wt2 / vr.VALIDATOR_REL_PATH,
    )
    assert rc_bad_sha == 1 and any("expected_commit" in f for f in res_bad_sha["fallas"])


def test_root_v1_validate_pair_tras_orquestador_noop_e_inmutabilidad_canon(tmp_path: Path) -> None:
    wt_a, out_a, pdf_dir, inv_json, sha40, inv_sha, val_sha, t0 = _build_synthetic_env(
        tmp_path / "env_a", name="wt_a"
    )
    wt_b = (tmp_path / "env_b").resolve()
    wt_b.mkdir(parents=True, exist_ok=True)
    wt_b_repo = wt_b / "wt_b"
    shutil.copytree(wt_a, wt_b_repo)
    out_b = wt_b / "out_b"
    shutil.copytree(out_a, out_b)
    raw_b = json.loads((out_b / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw_b["pasada"] = "wt_b"
    raw_b["cwd"] = str(wt_b_repo.resolve())
    raw_b["registry_file"] = str((wt_b_repo / "src/epiforecast/registry.py").resolve())
    raw_b["extrae_cuadro_file"] = str((wt_b_repo / "scripts/extrae_cuadro.py").resolve())
    (out_b / "sint_id_RUN_raw.json").write_text(json.dumps(raw_b, indent=2), encoding="utf-8")
    now = time.time()
    for p in (
        wt_b_repo / "data/interim/sint_id_boletin.csv",
        wt_b_repo / "data/interim/sint_id_extraccion_manifest.csv",
        out_b / "sint_id_boletin.csv",
        out_b / "sint_id_extraccion_manifest.csv",
    ):
        os.utime(p, (max(now, t0 + 1.0), max(now, t0 + 1.0)))

    # Simular que el orquestador YA emitió RUN_v2.json (0444) en out_a y out_b antes de correr pair
    for d, w in ((out_a, wt_a), (out_b, wt_b_repo)):
        rc_pre, _ = vr.validate_single_run(
            run_raw_path=d / "sint_id_RUN_raw.json",
            worktree=w,
            out_dir=d,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            expected_commit=sha40,
            expected_inventory_sha256=inv_sha,
            expected_validator_sha256=val_sha,
            validator_file=wt_a / vr.VALIDATOR_REL_PATH,
        )
        assert rc_pre == 0

    run_v2_a_bytes = (out_a / "sint_id_RUN_v2.json").read_bytes()
    run_v2_b_bytes = (out_b / "sint_id_RUN_v2.json").read_bytes()

    # Mismo worktree repetido debe fallar
    canon_same = tmp_path / "canon_same"
    rc_same, res_same = vr.validate_pair(
        disease_id="sint_id",
        dir_a=out_a,
        worktree_a=wt_a,
        dir_b=out_b,
        worktree_b=wt_a,
        canon_dir=canon_same,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt_a / vr.VALIDATOR_REL_PATH,
    )
    assert rc_same == 1 and any("distintos" in f for f in res_same["fallas"])

    # 1ª ejecución de pair en canon_ok: funciona sin romper los RUN_v2 previos (quedan intactos)
    canon_ok = tmp_path / "canon_ok"
    rc_ok, res_ok = vr.validate_pair(
        disease_id="sint_id",
        dir_a=out_a,
        worktree_a=wt_a,
        dir_b=out_b,
        worktree_b=wt_b_repo,
        canon_dir=canon_ok,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt_a / vr.VALIDATOR_REL_PATH,
    )
    assert rc_ok == 0, f"fallas pair inesperadas: {res_ok['fallas']}"
    assert res_ok["valida"] is True
    assert (out_a / "sint_id_RUN_v2.json").read_bytes() == run_v2_a_bytes
    assert (out_b / "sint_id_RUN_v2.json").read_bytes() == run_v2_b_bytes

    canon_files = [
        canon_ok / "sint_id_boletin.csv",
        canon_ok / "sint_id_extraccion_manifest.csv",
        canon_ok / "SHA256SUMS",
        canon_ok / "sint_id_CANON_RAW.json",
    ]
    snap_bytes = {p.name: p.read_bytes() for p in canon_files}
    for p in canon_files:
        assert not (p.stat().st_mode & stat.S_IWUSR)

    # 2ª ejecución idéntica de pair sobre canon_ok existente -> no-op intacto + reporte aditivo
    rc_noop, res_noop = vr.validate_pair(
        disease_id="sint_id",
        dir_a=out_a,
        worktree_a=wt_a,
        dir_b=out_b,
        worktree_b=wt_b_repo,
        canon_dir=canon_ok,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt_a / vr.VALIDATOR_REL_PATH,
    )
    assert rc_noop == 0 and res_noop["revalidacion_aditiva"]["noop_preserved_original"] is True
    assert {p.name: p.read_bytes() for p in canon_files} == snap_bytes
    assert Path(res_noop["revalidacion_aditiva"]["report_path"]).is_file()

    # Conflicto contra canon_ok existente (p. ej. expected_commit inválido): NO toca ni chmod canon_ok
    rc_conf, res_conf = vr.validate_pair(
        disease_id="sint_id",
        dir_a=out_a,
        worktree_a=wt_a,
        dir_b=out_b,
        worktree_b=wt_b_repo,
        canon_dir=canon_ok,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit="0" * 40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt_a / vr.VALIDATOR_REL_PATH,
    )
    assert rc_conf == 1 and res_conf["valida"] is False
    assert {p.name: p.read_bytes() for p in canon_files} == snap_bytes
    for p in canon_files:
        assert not (p.stat().st_mode & stat.S_IWUSR)
    assert Path(res_conf["conflict_report_path"]).is_file()


@pytest.mark.parametrize(
    ("bad_man_line", "expected_substr"),
    [
        (
            "2014_sem02.pdf,2014,2,22,4col_prev,2,invalid,columnas inesperadas\n",
            "estados no válidos",
        ),
        ("2014_sem02.pdf,2014,2,22,4col_prev,1,ok,1 estados\n", "boletines ok sin 2 entidades"),
        ("2014_sem02.pdf,2014,2,,,0,excluded,excluido no declarado\n", "excluidos"),
    ],
)
def test_valida_run_v2_manifiesto_es_el_gate_no_rc0(
    tmp_path: Path, bad_man_line: str, expected_substr: str
) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, t0 = _build_synthetic_env(tmp_path)
    man_text = (
        "file,year,week,page,layout,n_states,status,reason\n"
        "2014_sem01.pdf,2014,1,,,0,excluded,excluido: previo\n"
        f"{bad_man_line}"
        "2016_sem20.pdf,2016,20,,,0,excluded,excluido: errata\n"
    )
    for p in (
        wt / "data/interim/sint_id_extraccion_manifest.csv",
        out_dir / "sint_id_extraccion_manifest.csv",
    ):
        p.write_text(man_text, encoding="utf-8")
        os.utime(p, (t0 + 2.0, t0 + 2.0))
    raw_meta = json.loads((out_dir / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw_meta["manifiesto_sha256"] = vr.sha256_file(out_dir / "sint_id_extraccion_manifest.csv")
    (out_dir / "sint_id_RUN_raw.json").write_text(json.dumps(raw_meta, indent=2), encoding="utf-8")

    rc, res = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 1 and res["valida"] is False
    assert any(expected_substr in f for f in res["fallas"])
