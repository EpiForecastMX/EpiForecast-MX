"""Pruebas unitarias sintéticas de validador RUN_v2, orquestador y QA (H1-H7) — piloto Carbon alta1.

Todas las pruebas de herramientas operan sobre repositorios git, scripts e inventarios PDF 100 %
sintéticos en ``tmp_path`` (sin PDFs reales ni métricas de 2025), cubriendo ``H1`` a ``H7``.
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
from scripts.piloto_carbon_alta1 import qa_serie_extraida as qa
from scripts.piloto_carbon_alta1 import valida_run_v2 as vr
import yaml

from epiforecast import registry
from epiforecast.data.epi_geo_exposure import load_geo_catalog
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
    tmp_path: Path,
    *,
    name: str = "wt_a",
    with_runnable_extractor: bool = False,
    mutate_pdf_inside_extractor: bool = False,
) -> tuple[Path, Path, Path, Path, str, str, str, float]:
    """Construye worktree git sintético en commit40 + 3 PDFs sintéticos + corrida válida."""
    base_tmp = tmp_path.resolve()
    wt = base_tmp / name
    for rel_dir in (
        "config/data",
        "src/epiforecast/data/extraction",
        "scripts/piloto_carbon_alta1",
        "data/interim",
    ):
        (wt / rel_dir).mkdir(parents=True, exist_ok=True)

    (wt / ".gitignore").write_text("/data/\n/runs/\n__pycache__/\n*.py[cod]\n", encoding="utf-8")
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
    (wt / "src/epiforecast/__init__.py").write_text("", encoding="utf-8")
    (wt / "src/epiforecast/registry.py").write_text("# sint registry\n", encoding="utf-8")

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

    if with_runnable_extractor:
        tamper_line = (
            "    (Path(args.pdf_dir) / '2014_sem02.pdf').write_bytes(b'corrupted_post_run')\n"
            if mutate_pdf_inside_extractor
            else ""
        )
        ext_script = (
            "import argparse, sys\n"
            "from pathlib import Path\n"
            "if __name__ == '__main__':\n"
            "    ap = argparse.ArgumentParser()\n"
            "    ap.add_argument('--disease')\n"
            "    ap.add_argument('--pdf-dir')\n"
            "    ap.add_argument('--jobs')\n"
            "    args = ap.parse_args()\n"
            "    d = Path('data/interim')\n"
            "    d.mkdir(parents=True, exist_ok=True)\n"
            f"    (d / 'sint_id_boletin.csv').write_text({csv_text!r}, encoding='utf-8')\n"
            f"    (d / 'sint_id_extraccion_manifest.csv').write_text({man_text!r}, encoding='utf-8')\n"
            f"{tamper_line}"
            "    print('SINT_EXTRACTOR_STDOUT_OK')\n"
            "    print('SINT_EXTRACTOR_STDERR_WARN', file=sys.stderr)\n"
        )
        (wt / "scripts/extrae_cuadro.py").write_text(ext_script, encoding="utf-8")

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

    out_dir = base_tmp / f"out_{name}"
    if with_runnable_extractor:
        return wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, time.time()

    t0 = time.time() - 2.0
    interim_csv = wt / "data/interim/sint_id_boletin.csv"
    interim_man = wt / "data/interim/sint_id_extraccion_manifest.csv"
    interim_csv.write_text(csv_text, encoding="utf-8")
    interim_man.write_text(man_text, encoding="utf-8")

    out_dir.mkdir(parents=True, exist_ok=True)
    copy_csv = out_dir / "sint_id_boletin.csv"
    copy_man = out_dir / "sint_id_extraccion_manifest.csv"
    shutil.copy2(interim_csv, copy_csv)
    shutil.copy2(interim_man, copy_man)
    sub_log = out_dir / "sint_id_extrae_subprocess.log"
    sub_log.write_text("=== STDOUT ===\nok\n=== STDERR ===\n", encoding="utf-8")

    tracked_hashes = vr.compute_tracked_hashes(wt)
    run_raw = {
        "schema": "piloto_carbon_alta1.run_raw.v2",
        "id": "sint_id",
        "slug": "sint_id",
        "pasada": name,
        "snapshot_sha": sha40,
        "cwd": str(wt.resolve()),
        "single_thread_env": dict.fromkeys(vr.SINGLE_THREAD_VARS, "1"),
        "registry_file": str((wt / "src/epiforecast/registry.py").resolve()),
        "extrae_cuadro_file": str((wt / "scripts/extrae_cuadro.py").resolve()),
        "pre_interim_dir_existed": True,
        "pre_interim_entries": [],
        "pre_interim_absent": True,
        "t0_epoch": t0,
        "inicio_utc": datetime.fromtimestamp(t0, UTC).isoformat(),
        "fin_utc": datetime.now(UTC).isoformat(),
        "rc": 0,
        "subprocess_log_path": str(sub_log),
        "subprocess_log_sha256": vr.sha256_file(sub_log),
        "tracked_hashes_inicio": tracked_hashes,
        "tracked_hashes_fin": tracked_hashes,
        "inventory_sha256_inicio": inv_sha,
        "inventory_sha256_fin": inv_sha,
        "post_inventory_fallas": [],
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
    assert not ((out_dir / "sint_id_RUN_v2.json").stat().st_mode & stat.S_IWUSR)


def test_h2_h3_pines_obligatorios_formato_y_desajuste_de_pin(tmp_path: Path) -> None:
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
    for incomplete in (
        [*base_single, "--expected-commit", sha40, "--expected-inventory-sha256", inv_sha],
        [*base_single, "--expected-commit", sha40, "--expected-validator-sha256", val_sha],
        [
            *base_single,
            "--expected-inventory-sha256",
            inv_sha,
            "--expected-validator-sha256",
            val_sha,
        ],
        [
            *base_single,
            "--expected-commit",
            sha40,
            "--expected-inventory-sha256",
            inv_sha,
            "--expected-validator-sha256",
            val_sha,
            "--skip-pdf-hashes",
        ],
    ):
        with pytest.raises(SystemExit) as exc:
            vr.main(incomplete)
        assert exc.value.code != 0

    with pytest.raises(SystemExit) as exc_orch:
        ea.main(["--disease", "sint_id", "--worktree", str(wt), "--expected-commit", sha40])
    assert exc_orch.value.code != 0

    # Pines bien formados (64 hex) pero distintos del inventario o del validador real (H3)
    wrong_64 = "a" * 64 if inv_sha != "a" * 64 else "b" * 64
    out_wrong_inv = tmp_path / "out_wrong_inv"
    shutil.copytree(out_dir, out_wrong_inv)
    rc_inv, res_inv = vr.validate_single_run(
        run_raw_path=out_wrong_inv / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_wrong_inv,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=wrong_64,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc_inv == 1 and any("expected_inventory_sha256" in f for f in res_inv["fallas"])

    wrong_val_64 = "c" * 64 if val_sha != "c" * 64 else "d" * 64
    out_wrong_val = tmp_path / "out_wrong_val"
    shutil.copytree(out_dir, out_wrong_val)
    rc_val, res_val = vr.validate_single_run(
        run_raw_path=out_wrong_val / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_wrong_val,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=wrong_val_64,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc_val == 1 and any("expected_validator_sha256" in f for f in res_val["fallas"])


def test_h2_inventario_sin_sha256_por_pdf_falla_cerrado(tmp_path: Path) -> None:
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
    assert rc == 1 and any("sin bytes o sha256 de 64 hex" in f for f in res["fallas"])


def test_h1_run_v2_valido_es_noop_intacto_y_fallido_jamas_se_sobrescribe(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(
        tmp_path / "ok_case"
    )
    assert (
        vr.validate_single_run(
            run_raw_path=out_dir / "sint_id_RUN_raw.json",
            worktree=wt,
            out_dir=out_dir,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            expected_commit=sha40,
            expected_inventory_sha256=inv_sha,
            expected_validator_sha256=val_sha,
            validator_file=wt / vr.VALIDATOR_REL_PATH,
        )[0]
        == 0
    )
    v2_path = out_dir / "sint_id_RUN_v2.json"
    orig_bytes = v2_path.read_bytes()

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
    assert rc2 == 0 and v2_path.read_bytes() == orig_bytes
    assert Path(res2["revalidacion_aditiva"]["report_path"]).is_file()

    wt_f, out_f, pdf_f, inv_f, sha_f, inv_sha_f, val_sha_f, _ = _build_synthetic_env(
        tmp_path / "fail_case"
    )
    raw_f = json.loads((out_f / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw_f["rc"] = 2
    (out_f / "sint_id_RUN_raw.json").write_text(json.dumps(raw_f, indent=2), encoding="utf-8")
    assert (
        vr.validate_single_run(
            run_raw_path=out_f / "sint_id_RUN_raw.json",
            worktree=wt_f,
            out_dir=out_f,
            pdf_dir=pdf_f,
            inventory_json=inv_f,
            expected_commit=sha_f,
            expected_inventory_sha256=inv_sha_f,
            expected_validator_sha256=val_sha_f,
            validator_file=wt_f / vr.VALIDATOR_REL_PATH,
        )[0]
        == 1
    )
    failed_v2 = out_f / "sint_id_RUN_v2.json"
    failed_bytes = failed_v2.read_bytes()

    raw_f["rc"] = 0
    (out_f / "sint_id_RUN_raw.json").write_text(json.dumps(raw_f, indent=2), encoding="utf-8")
    rc_f2, _ = vr.validate_single_run(
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
    assert rc_f2 == 1 and failed_v2.read_bytes() == failed_bytes


def test_h3_rechaza_mutacion_hash_csv_config_log_y_validador(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(
        tmp_path / "c1"
    )
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
    assert rc1 == 1 and any("csv" in f for f in res1["fallas"])

    # Config cambiada durante la extracción (tracked_hashes_inicio != actual)
    wt_c, out_c, pdf_c, inv_c, sha_c, inv_sha_c, val_sha_c, _ = _build_synthetic_env(
        tmp_path / "c2"
    )
    raw_c = json.loads((out_c / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw_c["tracked_hashes_inicio"]["config/data/cuadros.yaml"] = "0" * 64
    (out_c / "sint_id_RUN_raw.json").write_text(json.dumps(raw_c, indent=2), encoding="utf-8")
    rc_cfg, res_cfg = vr.validate_single_run(
        run_raw_path=out_c / "sint_id_RUN_raw.json",
        worktree=wt_c,
        out_dir=out_c,
        pdf_dir=pdf_c,
        inventory_json=inv_c,
        expected_commit=sha_c,
        expected_inventory_sha256=inv_sha_c,
        expected_validator_sha256=val_sha_c,
        validator_file=wt_c / vr.VALIDATOR_REL_PATH,
    )
    assert rc_cfg == 1 and any("tracked_hashes_inicio" in f for f in res_cfg["fallas"])

    # Log del subproceso alterado respecto a subprocess_log_sha256
    wt_l, out_l, pdf_l, inv_l, sha_l, inv_sha_l, val_sha_l, _ = _build_synthetic_env(
        tmp_path / "c3"
    )
    (out_l / "sint_id_extrae_subprocess.log").write_text("tampered log\n", encoding="utf-8")
    rc_log, res_log = vr.validate_single_run(
        run_raw_path=out_l / "sint_id_RUN_raw.json",
        worktree=wt_l,
        out_dir=out_l,
        pdf_dir=pdf_l,
        inventory_json=inv_l,
        expected_commit=sha_l,
        expected_inventory_sha256=inv_sha_l,
        expected_validator_sha256=val_sha_l,
        validator_file=wt_l / vr.VALIDATOR_REL_PATH,
    )
    assert rc_log == 1 and any("subprocess_log" in f for f in res_log["fallas"])


def test_h3_rechaza_pdf_faltante_extra_y_mutado(tmp_path: Path) -> None:
    # 1) PDF faltante del directorio (faltan)
    wt_m, out_m, pdf_m, inv_m, sha_m, inv_sha_m, val_sha_m, _ = _build_synthetic_env(
        tmp_path / "missing_pdf"
    )
    (pdf_m / "2014_sem02.pdf").unlink()
    rc_m, res_m = vr.validate_single_run(
        run_raw_path=out_m / "sint_id_RUN_raw.json",
        worktree=wt_m,
        out_dir=out_m,
        pdf_dir=pdf_m,
        inventory_json=inv_m,
        expected_commit=sha_m,
        expected_inventory_sha256=inv_sha_m,
        expected_validator_sha256=val_sha_m,
        validator_file=wt_m / vr.VALIDATOR_REL_PATH,
    )
    assert rc_m == 1 and any("faltan=['2014_sem02.pdf']" in f for f in res_m["fallas"])

    # 2) PDF extra (sobran)
    wt_e, out_e, pdf_e, inv_e, sha_e, inv_sha_e, val_sha_e, _ = _build_synthetic_env(
        tmp_path / "extra_pdf"
    )
    (pdf_e / "2099_sem01.pdf").write_bytes(b"%PDF-1.4 extra\n")
    rc_e, res_e = vr.validate_single_run(
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
    assert rc_e == 1 and any("sobran" in f for f in res_e["fallas"])

    # 3) PDF con bytes mutados
    wt_t, out_t, pdf_t, inv_t, sha_t, inv_sha_t, val_sha_t, _ = _build_synthetic_env(
        tmp_path / "tampered_pdf"
    )
    (pdf_t / "2014_sem02.pdf").write_bytes(b"%PDF-1.4 same length?"[:27])
    rc_t, res_t = vr.validate_single_run(
        run_raw_path=out_t / "sint_id_RUN_raw.json",
        worktree=wt_t,
        out_dir=out_t,
        pdf_dir=pdf_t,
        inventory_json=inv_t,
        expected_commit=sha_t,
        expected_inventory_sha256=inv_sha_t,
        expected_validator_sha256=val_sha_t,
        validator_file=wt_t / vr.VALIDATOR_REL_PATH,
    )
    assert rc_t == 1 and any("sha256 PDF distinto" in f for f in res_t["fallas"])


def test_h3_rechaza_no_fresco_pre_interim_presente_rc_no_cero_y_claves_duplicadas(
    tmp_path: Path,
) -> None:
    # 1) mtime < t0
    wt1, out1, pdf1, inv1, sha1, inv_sha1, val_sha1, t0 = _build_synthetic_env(tmp_path / "nf")
    os.utime(wt1 / "data/interim/sint_id_boletin.csv", (t0 - 120.0, t0 - 120.0))
    rc1, res1 = vr.validate_single_run(
        run_raw_path=out1 / "sint_id_RUN_raw.json",
        worktree=wt1,
        out_dir=out1,
        pdf_dir=pdf1,
        inventory_json=inv1,
        expected_commit=sha1,
        expected_inventory_sha256=inv_sha1,
        expected_validator_sha256=val_sha1,
        validator_file=wt1 / vr.VALIDATOR_REL_PATH,
    )
    assert rc1 == 1 and any("no es fresco" in f for f in res1["fallas"])

    # 2) pre_interim_entries con residuo previo del slug
    wt2, out2, pdf2, inv2, sha2, inv_sha2, val_sha2, _ = _build_synthetic_env(tmp_path / "pi")
    raw2 = json.loads((out2 / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw2["pre_interim_entries"] = ["sint_id_boletin.csv"]
    (out2 / "sint_id_RUN_raw.json").write_text(json.dumps(raw2, indent=2), encoding="utf-8")
    rc2, res2 = vr.validate_single_run(
        run_raw_path=out2 / "sint_id_RUN_raw.json",
        worktree=wt2,
        out_dir=out2,
        pdf_dir=pdf2,
        inventory_json=inv2,
        expected_commit=sha2,
        expected_inventory_sha256=inv_sha2,
        expected_validator_sha256=val_sha2,
        validator_file=wt2 / vr.VALIDATOR_REL_PATH,
    )
    assert rc2 == 1 and any("pre_interim_entries" in f for f in res2["fallas"])

    # 3) rc != 0 con manifiesto y CSV por lo demás válidos
    wt3, out3, pdf3, inv3, sha3, inv_sha3, val_sha3, _ = _build_synthetic_env(tmp_path / "rc")
    raw3 = json.loads((out3 / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw3["rc"] = 1
    (out3 / "sint_id_RUN_raw.json").write_text(json.dumps(raw3, indent=2), encoding="utf-8")
    rc3, res3 = vr.validate_single_run(
        run_raw_path=out3 / "sint_id_RUN_raw.json",
        worktree=wt3,
        out_dir=out3,
        pdf_dir=pdf3,
        inventory_json=inv3,
        expected_commit=sha3,
        expected_inventory_sha256=inv_sha3,
        expected_validator_sha256=val_sha3,
        validator_file=wt3 / vr.VALIDATOR_REL_PATH,
    )
    assert rc3 == 1 and "rc=1" in res3["fallas"]

    # 4) Claves duplicadas en boletin.csv (mismo conteo total de 4 filas)
    wt4, out4, pdf4, inv4, sha4, inv_sha4, val_sha4, t0_4 = _build_synthetic_env(tmp_path / "dup")
    dup_csv = (
        "Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_hombres,"
        "Acumulado_mujeres,Acumulado_anio_anterior\n"
        "2014,02,Aguascalientes,Sint,1,1,0,0\n"
        "2014,02,Aguascalientes,Sint,2,1,1,0\n"
        "2016,20,Aguascalientes,Sint,,,,\n"
        "2016,20,Zacatecas,Sint,,,,\n"
    )
    for p in (wt4 / "data/interim/sint_id_boletin.csv", out4 / "sint_id_boletin.csv"):
        p.write_text(dup_csv, encoding="utf-8")
        os.utime(p, (t0_4 + 2.0, t0_4 + 2.0))
    raw4 = json.loads((out4 / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw4["csv_sha256"] = vr.sha256_file(out4 / "sint_id_boletin.csv")
    (out4 / "sint_id_RUN_raw.json").write_text(json.dumps(raw4, indent=2), encoding="utf-8")
    rc4, res4 = vr.validate_single_run(
        run_raw_path=out4 / "sint_id_RUN_raw.json",
        worktree=wt4,
        out_dir=out4,
        pdf_dir=pdf4,
        inventory_json=inv4,
        expected_commit=sha4,
        expected_inventory_sha256=inv_sha4,
        expected_validator_sha256=val_sha4,
        validator_file=wt4 / vr.VALIDATOR_REL_PATH,
    )
    assert rc4 == 1 and any("claves duplicadas" in f for f in res4["fallas"])


def test_h7_rechaza_untracked_en_raiz_worktree_shadowing(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(tmp_path)
    # Archivo no rastreado en la RAÍZ del worktree (p. ej. sitecustomize.py / yaml.py en PYTHONPATH)
    (wt / "sitecustomize.py").write_text("import os\n", encoding="utf-8")
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
    assert rc == 1 and any("dirty" in f and "sitecustomize.py" in f for f in res["fallas"])


@pytest.mark.parametrize(
    ("man_body", "expected_substr"),
    [
        # H3: invalid, no_page y error
        (
            "2014_sem01.pdf,2014,1,,,0,excluded,excluido\n"
            "2014_sem02.pdf,2014,2,22,4col_prev,2,invalid,columnas\n"
            "2016_sem20.pdf,2016,20,,,0,excluded,excluido\n",
            "estados no válidos",
        ),
        (
            "2014_sem01.pdf,2014,1,,,0,excluded,excluido\n"
            "2014_sem02.pdf,2014,2,,,,no_page,sin pagina\n"
            "2016_sem20.pdf,2016,20,,,0,excluded,excluido\n",
            "estados no válidos",
        ),
        # H4: fila error sin n_states provoca "2.0" float en la columna pandas -> NO lanza ValueError
        (
            "2014_sem01.pdf,2014,1,,,,error,RuntimeError: boom\n"
            "2014_sem02.pdf,2014,2,22.0,4col_prev,2.0,ok,ok\n"
            "2016_sem20.pdf,2016,20,,,0.0,excluded,excluido\n",
            "estados no válidos en manifiesto: ['error']",
        ),
        # H3: PDF omitido en el manifiesto
        (
            "2014_sem01.pdf,2014,1,,,0,excluded,excluido\n"
            "2014_sem02.pdf,2014,2,22,4col_prev,2,ok,ok\n",
            "manifiesto no cubre el inventario",
        ),
        # H3: PDF duplicado en el manifiesto
        (
            "2014_sem01.pdf,2014,1,,,0,excluded,excluido\n"
            "2014_sem02.pdf,2014,2,22,4col_prev,2,ok,ok\n"
            "2014_sem02.pdf,2014,2,22,4col_prev,2,ok,ok\n"
            "2016_sem20.pdf,2016,20,,,0,excluded,excluido\n",
            "manifiesto con PDFs duplicados",
        ),
        # Conteo de entidades distinto del esperado
        (
            "2014_sem01.pdf,2014,1,,,0,excluded,excluido\n"
            "2014_sem02.pdf,2014,2,22,4col_prev,1,ok,1 estado\n"
            "2016_sem20.pdf,2016,20,,,0,excluded,excluido\n",
            "boletines ok sin 2 entidades",
        ),
        # Exclusión no declarada
        (
            "2014_sem01.pdf,2014,1,,,0,excluded,excluido\n"
            "2014_sem02.pdf,2014,2,,,0,excluded,excluido no declarado\n"
            "2016_sem20.pdf,2016,20,,,0,excluded,excluido\n",
            "excluidos",
        ),
    ],
)
def test_h3_h4_manifiesto_es_el_gate_y_float_n_states_no_revienta(
    tmp_path: Path, man_body: str, expected_substr: str
) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, t0 = _build_synthetic_env(tmp_path)
    man_text = "file,year,week,page,layout,n_states,status,reason\n" + man_body
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


def test_h1_h3_validate_pair_inmutabilidad_y_diferencia_bytes_entre_a_y_b(tmp_path: Path) -> None:
    wt_a, out_a, pdf_dir, inv_json, sha40, inv_sha, val_sha, t0 = _build_synthetic_env(
        tmp_path / "env_a", name="wt_a"
    )
    wt_b_root = (tmp_path / "env_b").resolve()
    wt_b_root.mkdir(parents=True, exist_ok=True)
    wt_b_repo = wt_b_root / "wt_b"
    shutil.copytree(wt_a, wt_b_repo)
    out_b = wt_b_root / "out_b"
    shutil.copytree(out_a, out_b)
    raw_b = json.loads((out_b / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw_b["pasada"] = "wt_b"
    raw_b["cwd"] = str(wt_b_repo.resolve())
    raw_b["registry_file"] = str((wt_b_repo / "src/epiforecast/registry.py").resolve())
    raw_b["extrae_cuadro_file"] = str((wt_b_repo / "scripts/extrae_cuadro.py").resolve())
    raw_b["subprocess_log_path"] = str(out_b / "sint_id_extrae_subprocess.log")
    (out_b / "sint_id_RUN_raw.json").write_text(json.dumps(raw_b, indent=2), encoding="utf-8")
    now = time.time()
    for p in (
        wt_b_repo / "data/interim/sint_id_boletin.csv",
        wt_b_repo / "data/interim/sint_id_extraccion_manifest.csv",
        out_b / "sint_id_boletin.csv",
        out_b / "sint_id_extraccion_manifest.csv",
    ):
        os.utime(p, (max(now, t0 + 1.0), max(now, t0 + 1.0)))

    # H3: dos corridas individualmente válidas en worktrees distintos pero con CSV distinto -> falla
    wt_diff = wt_b_root / "wt_diff"
    out_diff = wt_b_root / "out_diff"
    shutil.copytree(wt_b_repo, wt_diff)
    shutil.copytree(out_b, out_diff)
    alt_csv = (
        (out_diff / "sint_id_boletin.csv")
        .read_text(encoding="utf-8")
        .replace(",2,1,1,0", ",9,5,4,0")
    )
    for p in (wt_diff / "data/interim/sint_id_boletin.csv", out_diff / "sint_id_boletin.csv"):
        p.write_text(alt_csv, encoding="utf-8")
        os.utime(p, (now + 2.0, now + 2.0))
    raw_diff = json.loads((out_diff / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw_diff["cwd"] = str(wt_diff.resolve())
    raw_diff["registry_file"] = str((wt_diff / "src/epiforecast/registry.py").resolve())
    raw_diff["extrae_cuadro_file"] = str((wt_diff / "scripts/extrae_cuadro.py").resolve())
    raw_diff["subprocess_log_path"] = str(out_diff / "sint_id_extrae_subprocess.log")
    raw_diff["csv_sha256"] = vr.sha256_file(out_diff / "sint_id_boletin.csv")
    (out_diff / "sint_id_RUN_raw.json").write_text(
        json.dumps(raw_diff, indent=2), encoding="utf-8"
    )
    rc_ab_diff, res_ab_diff = vr.validate_pair(
        disease_id="sint_id",
        dir_a=out_a,
        worktree_a=wt_a,
        dir_b=out_diff,
        worktree_b=wt_diff,
        canon_dir=tmp_path / "canon_ab_diff",
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt_a / vr.VALIDATOR_REL_PATH,
    )
    assert rc_ab_diff == 1 and any(
        "boletin.csv distinto entre A" in f for f in res_ab_diff["fallas"]
    )

    # Camino feliz tras emisión previa de RUN_v2 + no-op idempotente + protección ante conflicto
    canon_ok = tmp_path / "canon_ok"
    rc_ok, _ = vr.validate_pair(
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
    assert rc_ok == 0
    canon_files = [
        canon_ok / "sint_id_boletin.csv",
        canon_ok / "sint_id_extraccion_manifest.csv",
        canon_ok / "SHA256SUMS",
        canon_ok / "sint_id_CANON_RAW.json",
    ]
    snap_bytes = {p.name: p.read_bytes() for p in canon_files}

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

    rc_conf, _ = vr.validate_pair(
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
    assert rc_conf == 1 and {p.name: p.read_bytes() for p in canon_files} == snap_bytes


def test_h3_h5_orquestador_end_to_end_negativas_y_fallo_post_inventario(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(
        tmp_path / "orch_ok", with_runnable_extractor=True
    )

    # Negativa 1: HEAD != expected_commit
    with pytest.raises(RuntimeError, match="expected_commit"):
        ea.run_isolated_extraction(
            disease_id="sint_id",
            worktree=wt,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            out_dir=out_dir,
            pasada="p1",
            expected_commit="0" * 40,
            expected_inventory_sha256=inv_sha,
            expected_validator_sha256=val_sha,
            validator_file=wt / vr.VALIDATOR_REL_PATH,
        )

    # Negativa 2: archivo no rastreado en raíz del worktree (H7)
    (wt / "yaml_shadow.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Worktree sucio"):
        ea.run_isolated_extraction(
            disease_id="sint_id",
            worktree=wt,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            out_dir=out_dir,
            pasada="p1",
            expected_commit=sha40,
            expected_inventory_sha256=inv_sha,
            expected_validator_sha256=val_sha,
            validator_file=wt / vr.VALIDATOR_REL_PATH,
        )
    (wt / "yaml_shadow.py").unlink()

    # Negativa 3: interim preexistente
    stale_interim = wt / "data/interim/sint_id_boletin.csv"
    stale_interim.write_text("viejo\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="data/interim ya contiene"):
        ea.run_isolated_extraction(
            disease_id="sint_id",
            worktree=wt,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            out_dir=out_dir,
            pasada="p1",
            expected_commit=sha40,
            expected_inventory_sha256=inv_sha,
            expected_validator_sha256=val_sha,
            validator_file=wt / vr.VALIDATOR_REL_PATH,
        )
    stale_interim.unlink()

    # Negativa 4: out_dir con salida previa
    out_busy = tmp_path / "out_busy"
    out_busy.mkdir()
    (out_busy / "sint_id_boletin.csv").write_text("previo\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ya contiene"):
        ea.run_isolated_extraction(
            disease_id="sint_id",
            worktree=wt,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            out_dir=out_busy,
            pasada="p1",
            expected_commit=sha40,
            expected_inventory_sha256=inv_sha,
            expected_validator_sha256=val_sha,
            validator_file=wt / vr.VALIDATOR_REL_PATH,
        )

    # Ejecución limpia end-to-end (H5: log capturado, sys_prefix, versiones, orchestrator_script_sha256)
    rc_run = ea.run_isolated_extraction(
        disease_id="sint_id",
        worktree=wt,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        out_dir=out_dir,
        pasada="p1",
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc_run == 0
    raw_doc = json.loads((out_dir / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    log_path = Path(raw_doc["subprocess_log_path"])
    assert log_path.is_file() and "SINT_EXTRACTOR_STDOUT_OK" in log_path.read_text(
        encoding="utf-8"
    )
    assert "SINT_EXTRACTOR_STDERR_WARN" in log_path.read_text(encoding="utf-8")
    assert raw_doc["sys_prefix"] and raw_doc["python_executable_argv"]
    assert "python" in raw_doc["tool_versions"]
    assert raw_doc["orchestrator_script_file"].endswith("ejecuta_extraccion_aislada.py")
    assert len(raw_doc["orchestrator_script_sha256"]) == 64

    # Reanudación válida: no reextrae ni toca RUN_v2.json
    v2_bytes_before = (out_dir / "sint_id_RUN_v2.json").read_bytes()
    rc_resume = ea.run_isolated_extraction(
        disease_id="sint_id",
        worktree=wt,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        out_dir=out_dir,
        pasada="p1",
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        expected_validator_sha256=val_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc_resume == 0 and (out_dir / "sint_id_RUN_v2.json").read_bytes() == v2_bytes_before

    # H5(b): fallo de inventario DESPUÉS de correr el subproceso -> escribe RUN_raw y RUN_v2 (rc=1)
    wt_post, out_post, pdf_post, inv_post, sha_post, inv_sha_post, val_sha_post, _ = (
        _build_synthetic_env(
            tmp_path / "orch_post_fail",
            with_runnable_extractor=True,
            mutate_pdf_inside_extractor=True,
        )
    )
    rc_post = ea.run_isolated_extraction(
        disease_id="sint_id",
        worktree=wt_post,
        pdf_dir=pdf_post,
        inventory_json=inv_post,
        out_dir=out_post,
        pasada="p_fail",
        expected_commit=sha_post,
        expected_inventory_sha256=inv_sha_post,
        expected_validator_sha256=val_sha_post,
        validator_file=wt_post / vr.VALIDATOR_REL_PATH,
    )
    assert rc_post == 1
    assert (out_post / "sint_id_RUN_raw.json").is_file()
    v2_post = json.loads((out_post / "sint_id_RUN_v2.json").read_text(encoding="utf-8"))
    assert v2_post["valida"] is False
    assert any("post-extracción" in f or "inventario" in f for f in v2_post["fallas"])

    # Reanudación sobre corrida fallida: lanza RuntimeError y conserva RUN_v2 fallido intacto
    v2_fail_bytes = (out_post / "sint_id_RUN_v2.json").read_bytes()
    with pytest.raises(RuntimeError, match="no valida"):
        ea.run_isolated_extraction(
            disease_id="sint_id",
            worktree=wt_post,
            pdf_dir=pdf_post,
            inventory_json=inv_post,
            out_dir=out_post,
            pasada="p_fail",
            expected_commit=sha_post,
            expected_inventory_sha256=inv_sha_post,
            expected_validator_sha256=val_sha_post,
            validator_file=wt_post / vr.VALIDATOR_REL_PATH,
        )
    assert (out_post / "sint_id_RUN_v2.json").read_bytes() == v2_fail_bytes


def test_h6_qa_mediciones_na_2025_celdas_3bloques_caidas_excepcion_raw_noop_y_pines(
    tmp_path: Path,
) -> None:
    catalog = load_geo_catalog()
    entidades = [catalog.entity(cve).nombre_canonico for cve in sorted(catalog.cve_ents())]

    # 1) H6(a) y H6(d): CSV sintético con NA en objetivo 2025 (2025_sem02 -> 2025-W01 y
    #    2026_sem01 -> 2025-W53) y patrón de pico/caída revertido tipo 2016_sem20 en 2018_sem10..12
    rows: list[str] = [
        "Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_hombres,"
        "Acumulado_mujeres,Acumulado_anio_anterior"
    ]
    for wk, mult in ((9, 10), (10, 1), (11, 12)):  # caída en sem10 y recuperación en sem11
        for ent in entidades:
            rows.append(f"2018,{wk:02d},{ent},Sífilis adquirida,1,{mult},{mult},5")
    for idx, ent in enumerate(entidades):
        # En 2025_sem02 (objetivo 2025-W01), primera entidad trae Casos_semana vacío (p. ej. '-1' en fuente)
        sem_val = "" if idx == 0 else "2"
        rows.append(f"2025,02,{ent},Sífilis adquirida,{sem_val},3,2,4")
    for idx, ent in enumerate(entidades):
        # En 2026_sem01 (objetivo 2025-W53), segunda entidad trae literal '-1'
        sem_val = "-1" if idx == 1 else "1"
        rows.append(f"2026,01,{ent},Sífilis adquirida,{sem_val},20,15,18")

    canon_csv = tmp_path / "canon.csv"
    canon_csv.write_text("\n".join(rows) + "\n", encoding="utf-8")
    canon_lookup, diag = qa.analyze_canon_csv_cells_and_trajectories(
        canon_csv, lag=1, keep_period_files=set()
    )

    na_info = diag["target_2025_csv_na_and_minus_one"]
    assert na_info["target_weeks_2025_mapped_from_csv"] == 2
    assert na_info["na_counts_by_column_in_2025_targets"]["Casos_semana"] == 2
    assert len(na_info["literal_minus_one_strings_in_csv_2025"]) == 1

    traj = diag["cumulative_trajectories_and_anomalies"]
    assert [x["file"] for x in traj["national_cumulative_drops_by_file"]] == ["2018_sem10.pdf"]
    assert [x["file"] for x in traj["national_spike_or_drop_reverted_triplets"]] == [
        "2018_sem10.pdf"
    ]
    assert "2018_sem10.pdf" in traj["state_negative_delta_files"]

    # 2) H6(c) y H6(e): comparación celda a celda del CSV contra los 3 bloques + tokens crudos -1
    cves = sorted(catalog.cve_ents())
    cells_2025_w02 = {
        cve: ([None, 3, 2, 4] if i == 0 else [2, 3, 2, 4]) for i, cve in enumerate(cves)
    }
    cells_a50 = {cve: [0, 0, 0, 0] for cve in cves}
    cells_a54 = {cve: [9, 9, 9, 9] for cve in cves}
    pdf_rows_mock = [
        {
            "file": "2025_sem02.pdf",
            "year": 2025,
            "week": 2,
            "page": 24,
            "status": "ok",
            "data_cols": 12,
            "n_states": 32,
            "printed_target": [2025, 1],
            "mmwr_target": [2025, 1],
            "lag_matches_mmwr": True,
            "cells_a50": cells_a50,
            "cells_a51": cells_2025_w02,
            "cells_a54": cells_a54,
            "printed_total_12": [0, 0, 0, 0, 62, 96, 64, 128, 288, 288, 288, 288],
            "raw_minus_one_a51": [{"cve_ent": cves[0], "col_offset": 0}],
            "raw_non_numeric_a51": [{"cve_ent": cves[0], "col_offset": 0, "raw_token": "-1"}],
        },
        {
            "file": "2020_sem99.pdf",
            "year": 2020,
            "week": 99,
            "status": "exception",
            "error": "Boom",
        },
        {"file": "2019_sem01.pdf", "year": 2019, "week": 1, "status": "no_page"},
    ]
    c6_res = qa.compare_canon_against_pdf_blocks(canon_lookup, pdf_rows_mock)
    cc = c6_res["canon_cell_by_cell_contrast"]
    assert cc["denominator_bulletins"] == 1 and cc["denominator_cells_4col"] == 128
    assert cc["canon_vs_target_a51_diff_cells"] == 0
    assert cc["canon_vs_left_a50_diff_cells"] == 128
    assert cc["canon_vs_right_a54_diff_cells"] == 128
    assert c6_res["files_by_status"]["exception"] == ["2020_sem99.pdf"]
    assert c6_res["files_by_status"]["no_page"] == ["2019_sem01.pdf"]
    assert (
        len(c6_res["raw_pdf_tokens_before_normalize_number"]["raw_minus_one_cells_target_2025"])
        == 1
    )

    # Si una celda del CSV difiere de A51 en el PDF, canon_vs_target_a51_diff_cells lo detecta
    canon_lookup[(2025, 2)][cves[5]][1] = 999
    c6_mismatch = qa.compare_canon_against_pdf_blocks(canon_lookup, pdf_rows_mock[:1])
    assert c6_mismatch["canon_cell_by_cell_contrast"]["canon_vs_target_a51_diff_cells"] == 1

    # 3) H6(b): inspect_one_pdf captura excepciones sin abortar
    bad_pdf = tmp_path / "2024_sem01.pdf"
    bad_pdf.write_bytes(b"not a valid pdf")
    r_exc = qa.inspect_one_pdf((str(bad_pdf), ["adquirida"], ["zacatecas"], 1))
    assert r_exc["status"] == "exception" and "error" in r_exc

    # 4) H6(f): stage_raw_for_validate_data hace no-op en 0444 idéntico y rehúsa si difiere
    canon_sha = vr.sha256_file(canon_csv)
    assert canon_sha is not None
    raw_dest = tmp_path / "data/raw/data_raw_Sifilis_Adquirida_A51.csv"
    assert (
        qa.stage_raw_for_validate_data(canon_csv, raw_dest, canon_sha)
        == "copied_and_sealed_readonly"
    )
    assert not (raw_dest.stat().st_mode & stat.S_IWUSR)
    # Segunda ejecución idéntica: no lanza PermissionError
    assert (
        qa.stage_raw_for_validate_data(canon_csv, raw_dest, canon_sha) == "verified_existing_noop"
    )
    # Hash distinto: rehúsa sobrescribir
    other_csv = tmp_path / "other.csv"
    other_csv.write_text("distinto\n", encoding="utf-8")
    other_sha = vr.sha256_file(other_csv)
    assert other_sha is not None
    with pytest.raises(RuntimeError, match="se rehúsa sobrescribir"):
        qa.stage_raw_for_validate_data(other_csv, raw_dest, other_sha)

    # 5) H6(g): pines obligatorios en CLI y verify_qa_preconditions (cwd, commit, inventario, canon)
    with pytest.raises(SystemExit) as exc_qa_cli:
        qa.main(["--canon-csv", str(canon_csv), "--pdf-dir", str(tmp_path)])
    assert exc_qa_cli.value.code != 0

    wt_q, _, pdf_q, inv_q, sha_q, inv_sha_q, _, _ = _build_synthetic_env(tmp_path / "qa_pins")
    # cwd distinto de worktree debe fallar cuando check_cwd_and_imports=True
    with pytest.raises(RuntimeError, match="cwd actual"):
        qa.verify_qa_preconditions(
            disease_id="sint_id",
            canon_csv=canon_csv,
            expected_canon_sha256=canon_sha,
            pdf_dir=pdf_q,
            inventory_json=inv_q,
            expected_inventory_sha256=inv_sha_q,
            worktree=wt_q,
            expected_commit=sha_q,
            check_cwd_and_imports=True,
        )
    # expected_canon_sha256 distinto falla
    with pytest.raises(RuntimeError, match="canon_csv sha256"):
        qa.verify_qa_preconditions(
            disease_id="sint_id",
            canon_csv=canon_csv,
            expected_canon_sha256="0" * 64,
            pdf_dir=pdf_q,
            inventory_json=inv_q,
            expected_inventory_sha256=inv_sha_q,
            worktree=wt_q,
            expected_commit=sha_q,
            check_cwd_and_imports=False,
        )
    # Con pines exactos pasa
    prov_ok = qa.verify_qa_preconditions(
        disease_id="sint_id",
        canon_csv=canon_csv,
        expected_canon_sha256=canon_sha,
        pdf_dir=pdf_q,
        inventory_json=inv_q,
        expected_inventory_sha256=inv_sha_q,
        worktree=wt_q,
        expected_commit=sha_q,
        check_cwd_and_imports=False,
    )
    assert prov_ok["commit_sha40"] == sha_q and prov_ok["canon_csv_sha256"] == canon_sha
