"""Pruebas unitarias sintéticas del validador RUN_v2 (SHA40) y de la config QA aislada.

Todas las pruebas del validador operan sobre repositorios git e inventarios PDF 100 % sintéticos
en ``tmp_path``, mutando hashes, inventario, frescura (``mtime < t0``), limpieza del árbol git
(``dirty``), commit40 y aislamiento entre dos worktrees.
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
) -> tuple[Path, Path, Path, Path, str, float]:
    """Construye un worktree git sintético en commit40 limpio + 3 PDFs sellados + corrida válida."""
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

    _git(wt, "init", "-q")
    _git(wt, "config", "user.email", "qa@sint.local")
    _git(wt, "config", "user.name", "QA Sint")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "chore(qa): synthetic snapshot")
    sha40 = _git(wt, "rev-parse", "HEAD")

    pdf_dir = tmp_path / "source_pdfs"
    pdf_dir.mkdir(exist_ok=True)
    pdf_specs: list[dict[str, Any]] = []
    for fname in ("2014_sem01.pdf", "2014_sem02.pdf", "2016_sem20.pdf"):
        p = pdf_dir / fname
        payload = f"%PDF-1.4 synthetic {fname}\n".encode()
        p.write_bytes(payload)
        pdf_specs.append({"file": fname, "bytes": len(payload), "sha256": _sha256_bytes(payload)})

    inv_json = tmp_path / "ROOT_PDF_INVENTORY.json"
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

    out_dir = tmp_path / f"out_{name}"
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
    return wt, out_dir, pdf_dir, inv_json, sha40, t0


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
    # Sin alias ambiguo «sífilis» a secas: no captura A50.
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


def test_valida_run_v2_acepta_corrida_limpia_sha40(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, _ = _build_synthetic_env(tmp_path)
    inv_sha = vr.sha256_file(inv_json)
    rc, res = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        expected_inventory_sha256=inv_sha,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 0, f"fallas inesperadas: {res['fallas']}"
    assert res["valida"] is True and res["fallas"] == []
    assert len(res["snapshot_sha"]) == 40 and res["snapshot_sha"] == sha40
    assert res["csv_rows"] == 4


def test_valida_run_v2_rechaza_mutacion_hash_csv_o_config_o_validador(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, _ = _build_synthetic_env(tmp_path)
    # 1) Mutación de la copia archivada del CSV
    (out_dir / "sint_id_boletin.csv").write_text("corrupto\n", encoding="utf-8")
    rc1, res1 = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc1 == 1 and res1["valida"] is False
    assert any("csv" in f for f in res1["fallas"])

    # 2) Mutación del propio validador en disco frente al blob del commit40
    wt2, out2, pdf2, inv2, sha2, _ = _build_synthetic_env(tmp_path / "sub2")
    mutated_val = tmp_path / "mutated_validator.py"
    mutated_val.write_text("# validador alterado\n", encoding="utf-8")
    rc2, res2 = vr.validate_single_run(
        run_raw_path=out2 / "sint_id_RUN_raw.json",
        worktree=wt2,
        out_dir=out2,
        pdf_dir=pdf2,
        inventory_json=inv2,
        expected_commit=sha2,
        validator_file=mutated_val,
    )
    assert rc2 == 1 and any("validador en disco" in f for f in res2["fallas"])


def test_valida_run_v2_rechaza_mutacion_inventario_pdf(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, _ = _build_synthetic_env(tmp_path)
    # Alterar el contenido de un PDF respecto al sha256 sellado en ROOT_PDF_INVENTORY.json
    (pdf_dir / "2014_sem02.pdf").write_bytes(b"%PDF-1.4 tampered bytes!!\n")
    rc, res = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 1 and any("inventario" in f for f in res["fallas"])

    # Agregar un PDF extra no declarado
    (pdf_dir / "2099_sem01.pdf").write_bytes(b"%PDF-1.4 extra\n")
    rc_extra, res_extra = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc_extra == 1 and any("sobran" in f for f in res_extra["fallas"])


def test_valida_run_v2_rechaza_archivo_no_fresco_o_preexistente(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, t0 = _build_synthetic_env(tmp_path)
    interim_csv = wt / "data/interim/sint_id_boletin.csv"
    os.utime(interim_csv, (t0 - 120.0, t0 - 120.0))
    rc, res = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 1 and any("no es fresco" in f for f in res["fallas"])


def test_valida_run_v2_rechaza_worktree_dirty_o_commit_distinto(tmp_path: Path) -> None:
    wt, out_dir, pdf_dir, inv_json, sha40, _ = _build_synthetic_env(tmp_path)
    # Ensuciar un archivo rastreado
    (wt / "scripts/extrae_cuadro.py").write_text("# dirty change\n", encoding="utf-8")
    rc, res = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit=sha40,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 1 and any("dirty" in f for f in res["fallas"])

    # Árbol limpio pero expected_commit distinto
    _git(wt, "checkout", "--", "scripts/extrae_cuadro.py")
    rc_bad_sha, res_bad_sha = vr.validate_single_run(
        run_raw_path=out_dir / "sint_id_RUN_raw.json",
        worktree=wt,
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_commit="0" * 40,
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc_bad_sha == 1 and any("expected_commit" in f for f in res_bad_sha["fallas"])


def test_validate_pair_exige_dos_worktrees_distintos_e_igualdad_byte(tmp_path: Path) -> None:
    wt_a, out_a, pdf_dir, inv_json, sha40, t0 = _build_synthetic_env(
        tmp_path / "env_a", name="wt_a"
    )
    wt_b = tmp_path / "env_b" / "wt_b"
    shutil.copytree(wt_a, wt_b)
    out_b = tmp_path / "env_b" / "out_b"
    shutil.copytree(out_a, out_b)
    raw_b = json.loads((out_b / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw_b["pasada"] = "wt_b"
    raw_b["cwd"] = str(wt_b.resolve())
    raw_b["registry_file"] = str((wt_b / "src/epiforecast/registry.py").resolve())
    raw_b["extrae_cuadro_file"] = str((wt_b / "scripts/extrae_cuadro.py").resolve())
    (out_b / "sint_id_RUN_raw.json").write_text(json.dumps(raw_b, indent=2), encoding="utf-8")
    now = time.time()
    for p in (
        wt_b / "data/interim/sint_id_boletin.csv",
        wt_b / "data/interim/sint_id_extraccion_manifest.csv",
        out_b / "sint_id_boletin.csv",
        out_b / "sint_id_extraccion_manifest.csv",
    ):
        os.utime(p, (max(now, t0 + 1.0), max(now, t0 + 1.0)))

    # Mismo worktree repetido debe fallar (F5)
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
    )
    assert rc_same == 1 and any("distintos" in f for f in res_same["fallas"])

    # Dos worktrees distintos en el mismo commit40 con bytes idénticos -> sella en sólo lectura
    canon_ok = tmp_path / "canon_ok"
    # Ajuste para que validate_pair use el validador sintético del commit40
    real_file = vr.__file__
    try:
        vr.__file__ = str(wt_a / vr.VALIDATOR_REL_PATH)
        rc_ok, res_ok = vr.validate_pair(
            disease_id="sint_id",
            dir_a=out_a,
            worktree_a=wt_a,
            dir_b=out_b,
            worktree_b=wt_b,
            canon_dir=canon_ok,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            expected_commit=sha40,
        )
    finally:
        vr.__file__ = real_file

    assert rc_ok == 0, f"fallas pair inesperadas: {res_ok['fallas']}"
    assert res_ok["valida"] is True
    canon_csv = canon_ok / "sint_id_boletin.csv"
    assert canon_csv.is_file()
    assert not (canon_csv.stat().st_mode & stat.S_IWUSR)


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
    wt, out_dir, pdf_dir, inv_json, sha40, t0 = _build_synthetic_env(tmp_path)
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
        validator_file=wt / vr.VALIDATOR_REL_PATH,
    )
    assert rc == 1 and res["valida"] is False
    assert any(expected_substr in f for f in res["fallas"])
