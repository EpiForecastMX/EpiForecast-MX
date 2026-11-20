"""Pruebas unitarias sintéticas de validador RUN_v2, orquestador y QA (H1-H7) — piloto Carbon alta1.

Todas las pruebas de herramientas operan sobre repositorios git, scripts e inventarios PDF 100 %
sintéticos en ``tmp_path`` (sin PDFs reales ni métricas de 2025), cubriendo ``H1`` a ``H7``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time
from typing import Any

import pytest
from scripts import paso_semanal
from scripts.piloto_carbon_alta1 import add_a51_history_base as ahb
from scripts.piloto_carbon_alta1 import ejecuta_extraccion_aislada as ea
from scripts.piloto_carbon_alta1 import qa_serie_extraida as qa
from scripts.piloto_carbon_alta1 import valida_run_v2 as vr
import yaml

from epiforecast import registry
from epiforecast.data.epi_calendar import shift as semana_siguiente
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.data.extraction import cuadro_extractor
from epiforecast.publication import pointer as pt
from epiforecast.publication.contratos_datos import ContratoCobertura
from epiforecast.registry_doctor import diagnose
from epiforecast.runner.artifact_identity import ArtifactValidationError
from tests.unit.registry_pre_c77 import yaml_sin_alta_b44

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


_YAML_PADECIMIENTOS_REAL = (
    Path(registry.__file__).resolve().parents[2] / "config" / "padecimientos.yaml"
)
_A51_RELEASE_ID = "sifilis_adquirida_a51_release_a18527def134"
_A51_FALLBACK_RUN = "sifilis_adquirida_a51_benchmark_test_73490ea8b2b5_749316ac335e"


def _bloque_a51(texto: str) -> tuple[str, str, str, str, str]:
    cabeza, separador, resto = texto.partition("\n  - id: sifilis_adquirida_a51\n")
    if not separador:
        raise AssertionError("el registry real ya no declara sifilis_adquirida_a51")
    bloque, siguiente, cola = resto.partition("\n  - id: ")
    return cabeza, separador, bloque, siguiente, cola


def _yaml_a51_pre_pubflag_trained(texto: str | None = None) -> str:
    """Fixture hermético previo al pubflag (trained, channels=[], gallery_enabled=false)."""
    src = _YAML_PADECIMIENTOS_REAL.read_text(encoding="utf-8") if texto is None else texto
    cabeza, separador, bloque, siguiente, cola = _bloque_a51(src)
    assert "    lifecycle: published\n" in bloque
    assert "    channels: [web, epibot, reports]\n" in bloque
    assert "    gallery_enabled: true\n" in bloque
    bloque = bloque.replace("    lifecycle: published\n", "    lifecycle: trained\n", 1)
    bloque = bloque.replace("    channels: [web, epibot, reports]\n", "    channels: []\n", 1)
    bloque = bloque.replace("    gallery_enabled: true\n", "    gallery_enabled: false\n", 1)
    return cabeza + separador + bloque + siguiente + cola


def _yaml_a51_configured(texto: str | None = None) -> str:
    """Fixture hermético de fase aislada configured (patrón registry_pre_c77, sin bundle DVC)."""
    trained_yaml = _yaml_a51_pre_pubflag_trained(texto)
    cabeza, separador, bloque, siguiente, cola = _bloque_a51(trained_yaml)
    art_block = (
        "    artifact_source:\n"
        "      backend: runner_release\n"
        f"      release_id: {_A51_RELEASE_ID}\n"
    )
    fb_line = f"    acceptance_fallback_run: {_A51_FALLBACK_RUN}\n"
    assert art_block in bloque and fb_line in bloque
    bloque = bloque.replace("    lifecycle: trained\n", "    lifecycle: configured\n", 1)
    bloque = bloque.replace(art_block, "", 1)
    bloque = bloque.replace(fb_line, "", 1)
    return cabeza + separador + bloque + siguiente + cola


@contextmanager
def _registry_desde_yaml(texto: str) -> Iterator[registry._Registry]:
    """Instala un registry derivado en memoria temporal y restaura el cache original al salir."""
    anterior = registry._CACHE
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "padecimientos.yaml"
        ruta.write_text(texto, encoding="utf-8")
        cargado = registry.load_registry(ruta)
    registry._CACHE = cargado
    try:
        yield cargado
    finally:
        registry._CACHE = anterior


def _verifica_metadata_publicacion_a51() -> None:
    """Comprobación real de metadata de publicación en staging (sin leer bundles DVC locales)."""
    spec = registry.require("sifilis_adquirida_a51")
    assert spec.data_name == "Sífilis adquirida"
    assert spec.artifact_key == "Sifilis_Adquirida_A51"
    assert spec.cie_codes == ("A51", "A52", "A53")
    assert spec.exposure_source_id == "inegi_cpv2020_static"
    assert spec.selection_policy == "rolling_cv_baja_incidencia_v1"
    assert spec.lifecycle == "published"
    assert spec.channels == ("web", "epibot", "reports")
    assert spec.gallery_enabled is True
    assert spec.is_release_backed
    assert spec.artifact_source.backend == registry.BACKEND_RUNNER_RELEASE
    assert spec.artifact_source.release_id == _A51_RELEASE_ID
    assert spec.acceptance_fallback_run == _A51_FALLBACK_RUN

    # Nota contractual: registry.published_members() devuelve data_name; release_published() y
    # paso_semanal.publicados() exponen el id canónico. Verificamos ambos sin aserción vacua.
    assert spec.data_name in registry.published_members()
    assert spec.data_name in registry.names(published_only=True)
    assert spec.id in [d.id for d in registry.release_published()]
    assert spec.id in paso_semanal.publicados()
    for canal in ("web", "epibot", "reports"):
        assert spec.data_name in registry.published_members(channel=canal)
        assert spec.id in [d.id for d in registry.release_published(channel=canal)]
    assert spec.data_name not in registry.published_members(channel="tableau")
    assert spec.id not in [d.id for d in registry.release_published(channel="tableau")]
    assert spec.data_name not in [d.data_name for d in registry.legacy_published()]

    puntero = pt.pointer_for(spec, active=True)
    pt.check_activation(puntero, spec)
    assert puntero.disease_id == "sifilis_adquirida_a51"
    assert puntero.release_id == _A51_RELEASE_ID
    assert puntero.channels == ("epibot", "reports", "web")
    assert puntero.gallery_enabled is True
    assert puntero.active is True

    contrato = ContratoCobertura.canonico()
    assert "sifilis adquirida" in contrato.release
    assert contrato.releases["sifilis adquirida"] == ("sifilis_adquirida_a51", _A51_RELEASE_ID)
    errores = [
        p
        for p in diagnose("sifilis_adquirida_a51", check_artifacts=False)
        if p.severity == "error"
    ]
    assert errores == []


def test_config_aislada_sifilis_adquirida_invisible_y_doctor_verde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = Path(registry.__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)
    with _registry_desde_yaml(_yaml_a51_configured()):
        spec = registry.require("sifilis_adquirida_a51")
        assert spec.data_name == "Sífilis adquirida"
        assert spec.artifact_key == "Sifilis_Adquirida_A51"
        assert spec.cie_codes == ("A51", "A52", "A53")
        assert spec.exposure_source_id == "inegi_cpv2020_static"
        assert spec.lifecycle == "configured"
        assert spec.channels == ()
        assert spec.gallery_enabled is False
        assert spec.selection_policy == "rolling_cv_baja_incidencia_v1"
        assert spec.artifact_source.backend == registry.BACKEND_LEGACY
        assert spec.acceptance_fallback_run is None
        assert spec.data_name not in registry.published_members()
        assert spec.data_name not in registry.names(published_only=True)
        assert spec.id not in [d.id for d in registry.release_published()]
        assert spec.id not in paso_semanal.publicados()
        assert "sifilis adquirida" not in ContratoCobertura.canonico().release
        assert registry.try_get("sifilis") is None
        # alta_b44: A50 es sífilis congénita, nunca la adquirida (A51-A53).
        a50 = registry.try_get("a50")
        assert a50 is not None and a50.id == "sifilis_congenita_a50"
        errores_cfg = [
            p
            for p in diagnose("sifilis_adquirida_a51", check_artifacts=False)
            if p.severity == "error"
        ]
        assert errores_cfg == []

    grupo = cuadro_extractor.load_group("cuadro_6_sifilis_adquirida")
    assert grupo["observation_lag_weeks"] == 1
    assert grupo["n_states_expected"] == 32
    assert grupo["inner_block_columns"] == {12: [8, 4]}
    exc_01 = cuadro_extractor.source_exclusion(grupo, "2014_sem01.pdf", "sifilis_adquirida_a51")
    exc_20 = cuadro_extractor.source_exclusion(grupo, "2016_sem20.pdf", "sifilis_adquirida_a51")
    assert exc_01 is not None and not exc_01.get("keep_period", False)
    assert exc_20 is not None and exc_20["keep_period"] is True


def test_metadata_publicacion_control_sifilis_adquirida_real_y_falla_antes_de_pubflag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = Path(registry.__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)
    texto_real = _YAML_PADECIMIENTOS_REAL.read_text(encoding="utf-8")

    # 1) Después del pubflag (estado real de config/padecimientos.yaml en preparación BE)
    with _registry_desde_yaml(texto_real):
        _verifica_metadata_publicacion_a51()

    # 2) Antes del pubflag (fixtures trained y configured): la misma comprobación falla cerrado
    for yaml_previo in (
        _yaml_a51_pre_pubflag_trained(texto_real),
        _yaml_a51_configured(texto_real),
    ):
        with _registry_desde_yaml(yaml_previo):
            spec_prev = registry.require("sifilis_adquirida_a51")
            assert spec_prev.data_name not in registry.published_members()
            assert spec_prev.id not in [d.id for d in registry.release_published()]
            assert spec_prev.id not in paso_semanal.publicados()
            with pytest.raises(ArtifactValidationError):
                p_prev = pt.pointer_for(spec_prev, active=True)
                pt.check_activation(p_prev, spec_prev)
            with pytest.raises(AssertionError):
                _verifica_metadata_publicacion_a51()


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
    canon_dir_q = tmp_path / "canon_sealed_q"
    canon_dir_q.mkdir()
    canon_csv_q = canon_dir_q / "sint_id_boletin.csv"
    canon_csv_q.write_bytes(canon_csv.read_bytes())
    (canon_dir_q / "SHA256SUMS").write_text(
        f"{canon_sha}  sint_id_boletin.csv\n",
        encoding="utf-8",
    )
    (canon_dir_q / "sint_id_CANON_RAW.json").write_text(
        json.dumps(
            {
                "id": "sint_id",
                "valida": True,
                "raw_sha256": canon_sha,
                "snapshot_sha": sha_q,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # cwd distinto de worktree debe fallar cuando check_cwd_and_imports=True
    with pytest.raises(RuntimeError, match="cwd actual"):
        qa.verify_qa_preconditions(
            disease_id="sint_id",
            canon_csv=canon_csv_q,
            expected_canon_sha256=canon_sha,
            pdf_dir=pdf_q,
            inventory_json=inv_q,
            expected_inventory_sha256=inv_sha_q,
            worktree=wt_q,
            expected_commit=sha_q,
            expected_extraction_commit=sha_q,
            check_cwd_and_imports=True,
        )
    # expected_canon_sha256 distinto falla
    with pytest.raises(RuntimeError, match="canon_csv sha256"):
        qa.verify_qa_preconditions(
            disease_id="sint_id",
            canon_csv=canon_csv_q,
            expected_canon_sha256="0" * 64,
            pdf_dir=pdf_q,
            inventory_json=inv_q,
            expected_inventory_sha256=inv_sha_q,
            worktree=wt_q,
            expected_commit=sha_q,
            expected_extraction_commit=sha_q,
            check_cwd_and_imports=False,
        )
    # Con pines exactos pasa
    prov_ok = qa.verify_qa_preconditions(
        disease_id="sint_id",
        canon_csv=canon_csv_q,
        expected_canon_sha256=canon_sha,
        pdf_dir=pdf_q,
        inventory_json=inv_q,
        expected_inventory_sha256=inv_sha_q,
        worktree=wt_q,
        expected_commit=sha_q,
        expected_extraction_commit=sha_q,
        check_cwd_and_imports=False,
    )
    assert (
        prov_ok["commit_sha40"] == sha_q
        and prov_ok["extraction_commit_sha40"] == sha_q
        and prov_ok["cross_commit_revalidation"] is False
        and prov_ok["canon_csv_sha256"] == canon_sha
    )


def test_n1_inspect_one_pdf_ruta_real_miles_guion_y_desconocido_sin_descartar_celdas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N1: inspect_one_pdf parsea miles con espacio y guion en TOTAL y no descarta celdas si falla."""
    import pandas as pd

    catalog = load_geo_catalog()
    cves = sorted(catalog.cve_ents())
    entidades = [catalog.entity(cve).nombre_canonico for cve in cves]
    fake_pdf = tmp_path / "2026_sem43.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n% sint\n")

    class _FakePage:
        def extract_text(self) -> str:
            return "Casos hasta la semana epidemiológica 42 del 2026"

    class _FakeReader:
        def __init__(self, _path: str) -> None:
            self.pages = [_FakePage()]

    class _FakeTable:
        def __init__(self, df: pd.DataFrame) -> None:
            self.df = df

    state_rows = [
        [ent, "-", "10", "5", "-", "13", "391", "271", "559", "-", "-", "2", "-"]
        for ent in entidades
    ]
    clean_state_df = pd.DataFrame(state_rows)

    def _run_with_total_row(total_cells_12: list[str]) -> dict[str, Any]:
        raw_df = pd.DataFrame([*state_rows, ["TOTAL", *total_cells_12]])
        monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
        monkeypatch.setattr(qa, "PdfReader", _FakeReader)
        monkeypatch.setattr(
            "scripts.piloto_carbon_alta1.qa_serie_extraida.camelot.read_pdf",
            lambda *_a, **_k: [_FakeTable(raw_df)],
        )
        monkeypatch.setattr(qa, "_tabla_estatal", lambda *_a, **_k: clean_state_df.copy())
        return qa.inspect_one_pdf((str(fake_pdf), ["adquirida"], ["zacatecas"], 1))

    # Caso 1: TOTAL con separador de miles con espacio ("12 537") y guiones ("-")
    res_miles = _run_with_total_row(
        ["-", "1 200", "800", "-", "425", "12 537", "8 676", "17 918", "-", "-", "5 000", "-"]
    )
    assert res_miles["status"] == "ok"
    assert res_miles["printed_total_12"] == [
        0,
        1200,
        800,
        0,
        425,
        12537,
        8676,
        17918,
        0,
        0,
        5000,
        0,
    ]
    tot_12 = res_miles["printed_total_12"]
    assert isinstance(tot_12, list) and tot_12[4:8] == [425, 12537, 8676, 17918]
    assert res_miles["printed_total_unknown_tokens"] == []
    cells_51 = res_miles["cells_a51"]
    assert isinstance(cells_51, dict) and len(cells_51) == 32

    # Caso 2: TOTAL con token desconocido ("S/D") -> printed_total_12=None, pero status=="ok" y
    # las 32 entidades (128 celdas) NO se descartan en compare_canon_against_pdf_blocks.
    res_unk = _run_with_total_row(
        ["-", "1 200", "800", "-", "425", "S/D", "8 676", "17 918", "-", "-", "5 000", "-"]
    )
    assert res_unk["status"] == "ok"
    assert res_unk["printed_total_12"] is None
    assert res_unk["printed_total_unknown_tokens"] == [{"col_index": 5, "raw_token": "S/D"}]
    cells_51_unk = res_unk["cells_a51"]
    assert isinstance(cells_51_unk, dict) and len(cells_51_unk) == 32

    canon_lookup_n1: dict[tuple[int, int], dict[str, list[int | None]]] = {
        (2026, 43): {cve: [13, 391, 271, 559] for cve in cves}
    }
    c6_unk = qa.compare_canon_against_pdf_blocks(canon_lookup_n1, [res_unk])
    assert c6_unk["files_by_status"]["ok"] == ["2026_sem43.pdf"]
    assert c6_unk["files_by_status"]["sin_total_12"] == ["2026_sem43.pdf"]
    assert c6_unk["canon_cell_by_cell_contrast"]["denominator_bulletins"] == 1
    assert c6_unk["canon_cell_by_cell_contrast"]["denominator_cells_4col"] == 128
    assert c6_unk["canon_cell_by_cell_contrast"]["canon_vs_target_a51_diff_cells"] == 0


def test_n2_cross_commit_misma_ciencia_acepta_y_source_cambiado_rechaza(tmp_path: Path) -> None:
    """N2: QA en commit posterior acepta si TRACKED_EXTRACTION_INPUTS es idéntico y rechaza si cambia."""
    wt, out_dir, pdf_dir, inv_json, sha_ext, inv_sha, _, _ = _build_synthetic_env(
        tmp_path / "n2_env"
    )
    canon_dir = tmp_path / "canon_n2"
    canon_dir.mkdir()
    canon_csv = canon_dir / "sint_id_boletin.csv"
    shutil.copyfile(out_dir / "sint_id_boletin.csv", canon_csv)
    canon_sha = vr.sha256_file(canon_csv)
    assert canon_sha is not None
    (canon_dir / "SHA256SUMS").write_text(
        f"{canon_sha}  sint_id_boletin.csv\n",
        encoding="utf-8",
    )
    (canon_dir / "sint_id_CANON_RAW.json").write_text(
        json.dumps(
            {
                "id": "sint_id",
                "valida": True,
                "raw_sha256": canon_sha,
                "snapshot_sha": sha_ext,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Pin --expected-extraction-commit faltante en CLI debe abortar
    with pytest.raises(SystemExit) as exc_cli:
        qa.main(
            [
                "--disease",
                "sint_id",
                "--canon-csv",
                str(canon_csv),
                "--expected-canon-sha256",
                canon_sha,
                "--pdf-dir",
                str(pdf_dir),
                "--inventory-json",
                str(inv_json),
                "--expected-inventory-sha256",
                inv_sha,
                "--worktree",
                str(wt),
                "--expected-commit",
                sha_ext,
                "--out-json",
                str(tmp_path / "o.json"),
                "--out-md",
                str(tmp_path / "o.md"),
            ]
        )
    assert exc_cli.value.code != 0

    # Commit posterior que SÓLO toca un helper de medición (sin tocar TRACKED_EXTRACTION_INPUTS)
    (wt / "scripts/piloto_carbon_alta1/qa_helper_note.py").write_text(
        "# fix medicion N1\n",
        encoding="utf-8",
    )
    _git(wt, "add", "scripts/piloto_carbon_alta1/qa_helper_note.py")
    _git(wt, "commit", "-qm", "fix(qa): measurement only")
    sha_qa_ok = _git(wt, "rev-parse", "HEAD")
    assert sha_qa_ok != sha_ext

    prov_cross = qa.verify_qa_preconditions(
        disease_id="sint_id",
        canon_csv=canon_csv,
        expected_canon_sha256=canon_sha,
        pdf_dir=pdf_dir,
        inventory_json=inv_json,
        expected_inventory_sha256=inv_sha,
        worktree=wt,
        expected_commit=sha_qa_ok,
        expected_extraction_commit=sha_ext,
        check_cwd_and_imports=False,
    )
    assert prov_cross["commit_sha40"] == sha_qa_ok
    assert prov_cross["extraction_commit_sha40"] == sha_ext
    assert prov_cross["cross_commit_revalidation"] is True

    # Commit posterior que cambia una fuente de extracción (cuadro_extractor.py) -> DEBE RECHAZAR
    ext_src = wt / "src/epiforecast/data/extraction/cuadro_extractor.py"
    ext_src.write_text(
        ext_src.read_text(encoding="utf-8") + "# cambio extractor\n", encoding="utf-8"
    )
    _git(wt, "add", "src/epiforecast/data/extraction/cuadro_extractor.py")
    _git(wt, "commit", "-qm", "feat(extract): mutated extractor")
    sha_qa_mutated = _git(wt, "rev-parse", "HEAD")

    with pytest.raises(RuntimeError, match="TRACKED_EXTRACTION_INPUTS cambió"):
        qa.verify_qa_preconditions(
            disease_id="sint_id",
            canon_csv=canon_csv,
            expected_canon_sha256=canon_sha,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            expected_inventory_sha256=inv_sha,
            worktree=wt,
            expected_commit=sha_qa_mutated,
            expected_extraction_commit=sha_ext,
            check_cwd_and_imports=False,
        )


def test_n3_checkpoint_por_pdf_antes_de_csv_y_canon_raw_sha256sums_obligatorios(
    tmp_path: Path,
) -> None:
    """N3: SHA256SUMS + CANON_RAW obligatorios y <stem>_por_pdf.json se persiste antes de leer CSV."""
    wt, _, pdf_dir, inv_json, sha_wt, inv_sha, _, _ = _build_synthetic_env(tmp_path / "n3_env")

    # Copiar configuración real de sifilis_adquirida_a51 al worktree sintético para run_qa_report
    repo_root = Path(__file__).resolve().parents[2]
    shutil.copyfile(repo_root / "config/data/cuadros.yaml", wt / "config/data/cuadros.yaml")
    shutil.copyfile(repo_root / "config/padecimientos.yaml", wt / "config/padecimientos.yaml")
    _git(wt, "add", "config/data/cuadros.yaml", "config/padecimientos.yaml")
    _git(wt, "commit", "-qm", "chore(qa): real sifilis config for N3")
    sha_real_cfg = _git(wt, "rev-parse", "HEAD")

    canon_dir = tmp_path / "canon_n3"
    canon_dir.mkdir()
    bad_csv = canon_dir / "sifilis_adquirida_a51_boletin.csv"
    bad_csv.write_text("ColumnaInvalida\n1\n", encoding="utf-8")
    bad_sha = vr.sha256_file(bad_csv)
    assert bad_sha is not None

    # 1) Sin SHA256SUMS falla cerrado
    with pytest.raises(RuntimeError, match="Falta archivo obligatorio SHA256SUMS"):
        qa.verify_qa_preconditions(
            disease_id="sifilis_adquirida_a51",
            canon_csv=bad_csv,
            expected_canon_sha256=bad_sha,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            expected_inventory_sha256=inv_sha,
            worktree=wt,
            expected_commit=sha_real_cfg,
            expected_extraction_commit=sha_real_cfg,
            check_cwd_and_imports=False,
        )

    # 2) Con SHA256SUMS pero sin CANON_RAW.json falla cerrado
    (canon_dir / "SHA256SUMS").write_text(
        f"{bad_sha}  sifilis_adquirida_a51_boletin.csv\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match=r"Falta archivo obligatorio CANON_RAW\.json"):
        qa.verify_qa_preconditions(
            disease_id="sifilis_adquirida_a51",
            canon_csv=bad_csv,
            expected_canon_sha256=bad_sha,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            expected_inventory_sha256=inv_sha,
            worktree=wt,
            expected_commit=sha_real_cfg,
            expected_extraction_commit=sha_real_cfg,
            check_cwd_and_imports=False,
        )

    # 3) Con SHA256SUMS y CANON_RAW válidos apuntando a un CSV que revienta en analyze_canon_csv:
    #    <stem>_por_pdf.json YA debe quedar persistido y en 0444 en disco antes de analizar el CSV.
    (canon_dir / "sifilis_adquirida_a51_CANON_RAW.json").write_text(
        json.dumps(
            {
                "id": "sifilis_adquirida_a51",
                "valida": True,
                "raw_sha256": bad_sha,
                "snapshot_sha": sha_real_cfg,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "out_n3" / "QA_N3.json"
    out_md = tmp_path / "out_n3" / "QA_N3.md"
    out_por_pdf = tmp_path / "out_n3" / "QA_N3_por_pdf.json"

    with pytest.raises(KeyError):
        qa.run_qa_report(
            disease_id="sifilis_adquirida_a51",
            canon_csv=bad_csv,
            expected_canon_sha256=bad_sha,
            pdf_dir=pdf_dir,
            inventory_json=inv_json,
            expected_inventory_sha256=inv_sha,
            worktree=wt,
            expected_commit=sha_real_cfg,
            expected_extraction_commit=sha_real_cfg,
            out_json=out_json,
            out_md=out_md,
            jobs=1,
            run_validate_data=False,
            check_cwd_and_imports=False,
        )

    assert out_por_pdf.is_file()
    assert not (out_por_pdf.stat().st_mode & stat.S_IWUSR)
    por_pdf_doc = json.loads(out_por_pdf.read_text(encoding="utf-8"))
    assert por_pdf_doc["schema"] == "piloto_carbon_alta1.qa_por_pdf.v2"
    # 2014_sem02.pdf no está excluido en sifilis_adquirida_a51 (2014_sem01 y 2016_sem20 sí)
    assert [r["file"] for r in por_pdf_doc["pdf_rows"]] == ["2014_sem02.pdf"]
    assert sha_wt != sha_real_cfg


class _FakePageGeometryQA:
    """Página sintética pdfplumber con geometría válida/negativa del Cuadro 6 para pruebas QA."""

    width = 540.0
    height = 720.0

    def __init__(
        self,
        *,
        include_central_acum_text: bool = False,
        omit_left_acum_text: bool = False,
        n_central_images: int = 33,
        extra_outside_image: bool = False,
        stray_word_in_gap: bool = False,
    ) -> None:
        self._words: list[dict[str, Any]] = [
            {"text": "Sem.", "x0": 139.9, "x1": 156.3, "top": 183.5},
            {"text": "H", "x0": 175.2, "x1": 180.3, "top": 189.5},
            {"text": "M", "x0": 204.3, "x1": 210.6, "top": 189.5},
            {"text": "Sem.", "x0": 258.3, "x1": 274.7, "top": 183.5},
            {"text": "H", "x0": 293.1, "x1": 298.3, "top": 189.5},
            {"text": "M", "x0": 321.2, "x1": 327.6, "top": 189.5},
            {"text": "Sem.", "x0": 375.7, "x1": 392.2, "top": 183.5},
            {"text": "H", "x0": 412.1, "x1": 417.3, "top": 189.5},
            {"text": "M", "x0": 444.3, "x1": 450.7, "top": 189.5},
            {"text": "Acum.", "x0": 469.3, "x1": 490.9, "top": 183.5},
            {"text": "Aguascalientes", "x0": 45.3, "x1": 98.8, "top": 201.3},
            {"text": "95", "x0": 326.9, "x1": 334.4, "top": 201.0},
            {"text": "-", "x0": 391.8, "x1": 394.0, "top": 201.0},
            {"text": "TOTAL", "x0": 75.9, "x1": 101.1, "top": 637.0},
        ]
        if not omit_left_acum_text:
            self._words.append({"text": "Acum.", "x0": 226.1, "x1": 247.7, "top": 183.5})
        if include_central_acum_text:
            self._words.append({"text": "Acum.", "x0": 342.0, "x1": 364.0, "top": 183.5})
        if stray_word_in_gap:
            self._words.append({"text": "429", "x0": 348.0, "x1": 362.0, "top": 215.0})

        self.images: list[dict[str, float]] = [{"x0": 410.0, "x1": 510.0, "top": 35.0}]
        for k in range(n_central_images):
            self.images.append({"x0": 345.0, "x1": 368.0, "top": 201.0 + k * 13.0})
        if extra_outside_image:
            self.images.append({"x0": 230.0, "x1": 247.0, "top": 220.0})

    def extract_words(self, **_kw: Any) -> list[dict[str, Any]]:
        return list(self._words)


class _FakePdfPlumberDocQA:
    def __init__(self, page_obj: _FakePageGeometryQA, n_pages: int = 24) -> None:
        self.pages = [page_obj] * n_pages

    def __enter__(self) -> _FakePdfPlumberDocQA:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _build_layout_tables_qa() -> tuple[
    Any,
    Any,
    Any,
    dict[str, list[int]],
    dict[str, list[int]],
    list[int],
    list[int],
]:
    """Construye tablas Camelot 100 % sintéticas: 12 col unida, partida (row_tol=2) y 11 col."""
    import pandas as pd

    catalog = load_geo_catalog()
    cves = sorted(catalog.cve_ents())
    entidades = [catalog.entity(cve).nombre_canonico for cve in cves]

    filas_partidas: list[list[str]] = [
        ["", "Sem.", "", "", "Acum.", "Sem.", "", "", "Acum.", "Sem.", "", "", "Acum.", "", ""]
    ]
    filas_12: list[list[str]] = [["FEDERATIVA", *[""] * 12]]
    filas_11: list[list[str]] = [["FEDERATIVA", *[""] * 11]]
    expected_12_a51: dict[str, list[int]] = {}
    expected_11_a51_3: dict[str, list[int]] = {}
    sums_12 = [0] * 12
    sums_11 = [0] * 11

    for idx, (cve, ent) in enumerate(zip(cves, entidades, strict=True)):
        sem_51, h_51, m_51, prev_51 = idx + 1, 20 + idx, 10 + idx, 100 + idx
        expected_12_a51[cve] = [sem_51, h_51, m_51, prev_51]
        vals_12 = [0, 2, 1, 5, sem_51, h_51, m_51, prev_51, 3, 4, 5, 6]
        for j, val in enumerate(vals_12):
            sums_12[j] += val
        filas_partidas.append(
            [
                "-",
                "2",
                "1",
                "5",
                str(sem_51),
                "",
                str(h_51),
                str(m_51),
                str(prev_51),
                "3",
                "",
                "4",
                "",
                "5",
                "6",
            ]
        )
        filas_partidas.append([ent, *[""] * 14])
        filas_12.append([ent, *("-" if v == 0 else str(v) for v in vals_12)])

        a50_11 = [400 + idx, 500 + idx, 600 + idx, 700 + idx]
        a51_3 = [idx + 2, 30 + idx, 15 + idx]
        a54_11 = [800 + idx, 900 + idx, 1000 + idx, 1100 + idx]
        expected_11_a51_3[cve] = a51_3
        vals_11 = [*a50_11, *a51_3, *a54_11]
        for j, val in enumerate(vals_11):
            sums_11[j] += val
        filas_11.append([ent, *(f"{v:,}".replace(",", " ") for v in vals_11)])

    filas_12.append(["TOTAL", *("-" if s == 0 else f"{s:,}".replace(",", " ") for s in sums_12)])
    filas_11.append(["TOTAL", *(f"{s:,}".replace(",", " ") for s in sums_11)])
    return (
        pd.DataFrame(filas_12),
        pd.DataFrame(filas_partidas),
        pd.DataFrame(filas_11),
        expected_12_a51,
        expected_11_a51_3,
        sums_12,
        sums_11,
    )


def _optin_group_spec_qa() -> dict[str, Any]:
    return {
        "page_anchors": ["adquirida"],
        "state_markers": ["zacatecas"],
        "observation_lag_weeks": 1,
        "n_states_expected": 32,
        "reintento_row_tol": 4,
        "inner_block_columns": {12: [8, 4]},
        "bloque_sin_prev_en_capa_texto": {11: [4, 3, 4]},
    }


def test_p1_tracked_extraction_inputs_incluye_cuadro_capa_texto_y_rechaza_mutacion(
    tmp_path: Path,
) -> None:
    """P1: cuadro_capa_texto.py está fijado en TRACKED_EXTRACTION_INPUTS para RUN_v2 y pin N2."""
    helper_rel = "src/epiforecast/data/extraction/cuadro_capa_texto.py"
    assert helper_rel in vr.TRACKED_EXTRACTION_INPUTS

    # 1) RUN_v2 rechaza si cambia el hash de cuadro_capa_texto.py respecto a RUN_raw
    wt, out_dir, pdf_dir, inv_json, sha40, inv_sha, val_sha, _ = _build_synthetic_env(
        tmp_path / "p1_single"
    )
    rc_ok, res_ok = vr.validate_single_run(
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
    assert rc_ok == 0 and helper_rel in res_ok["tracked_hashes_recomputed"]

    wt_mut, out_mut, pdf_mut, inv_mut, sha_mut, inv_sha_mut, val_sha_mut, _ = _build_synthetic_env(
        tmp_path / "p1_mut_raw"
    )
    raw_mut = json.loads((out_mut / "sint_id_RUN_raw.json").read_text(encoding="utf-8"))
    raw_mut["tracked_hashes_inicio"][helper_rel] = "f" * 64
    (out_mut / "sint_id_RUN_raw.json").write_text(json.dumps(raw_mut, indent=2), encoding="utf-8")
    rc_mut, res_mut = vr.validate_single_run(
        run_raw_path=out_mut / "sint_id_RUN_raw.json",
        worktree=wt_mut,
        out_dir=out_mut,
        pdf_dir=pdf_mut,
        inventory_json=inv_mut,
        expected_commit=sha_mut,
        expected_inventory_sha256=inv_sha_mut,
        expected_validator_sha256=val_sha_mut,
        validator_file=wt_mut / vr.VALIDATOR_REL_PATH,
    )
    assert rc_mut == 1 and any("tracked_hashes_inicio" in f for f in res_mut["fallas"])

    # 2) Pin cruzado N2 en QA rechaza un commit posterior si muta cuadro_capa_texto.py
    wt_n2, out_n2, pdf_n2, inv_n2, sha_ext, inv_sha_n2, _, _ = _build_synthetic_env(
        tmp_path / "p1_cross_n2"
    )
    canon_dir = tmp_path / "canon_p1_n2"
    canon_dir.mkdir()
    canon_csv = canon_dir / "sint_id_boletin.csv"
    shutil.copyfile(out_n2 / "sint_id_boletin.csv", canon_csv)
    canon_sha = vr.sha256_file(canon_csv)
    assert canon_sha is not None
    (canon_dir / "SHA256SUMS").write_text(
        f"{canon_sha}  sint_id_boletin.csv\n",
        encoding="utf-8",
    )
    (canon_dir / "sint_id_CANON_RAW.json").write_text(
        json.dumps(
            {
                "id": "sint_id",
                "valida": True,
                "raw_sha256": canon_sha,
                "snapshot_sha": sha_ext,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    helper_file = wt_n2 / helper_rel
    helper_file.write_text(
        helper_file.read_text(encoding="utf-8") + "# mutacion helper layout\n",
        encoding="utf-8",
    )
    _git(wt_n2, "add", helper_rel)
    _git(wt_n2, "commit", "-qm", "feat(extract): mutate cuadro_capa_texto")
    sha_after_helper_mut = _git(wt_n2, "rev-parse", "HEAD")

    with pytest.raises(RuntimeError, match=r"TRACKED_EXTRACTION_INPUTS cambió.*cuadro_capa_texto"):
        qa.verify_qa_preconditions(
            disease_id="sint_id",
            canon_csv=canon_csv,
            expected_canon_sha256=canon_sha,
            pdf_dir=pdf_n2,
            inventory_json=inv_n2,
            expected_inventory_sha256=inv_sha_n2,
            worktree=wt_n2,
            expected_commit=sha_after_helper_mut,
            expected_extraction_commit=sha_ext,
            check_cwd_and_imports=False,
        )


def test_p2_regresion_12col_normal_y_row_tol_4_con_grupos_sin_opt_in_intactos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2: 12 col normal no reintenta; renglón partido recupera con row_tol=4 sólo con opt-in."""
    df_12, df_split, _, exp_12_a51, _, sums_12, _ = _build_layout_tables_qa()
    spec_optin = _optin_group_spec_qa()
    spec_no_optin = {
        "page_anchors": ["adquirida"],
        "state_markers": ["zacatecas"],
        "observation_lag_weeks": 1,
        "n_states_expected": 32,
        "inner_block_columns": {12: [8, 4]},
    }

    pdf_normal = tmp_path / "2025_sem11.pdf"
    pdf_split = tmp_path / "2025_sem02.pdf"
    pdf_normal.write_bytes(b"%PDF-1.4\n")
    pdf_split.write_bytes(b"%PDF-1.4\n")

    class _FakeCutoffPage:
        def __init__(self, txt: str) -> None:
            self._txt = txt

        def extract_text(self) -> str:
            return self._txt

    class _FakeCutoffReader:
        def __init__(self, path: str) -> None:
            txt = (
                "Casos hasta la semana epidemiológica 10 del 2025"
                if path.endswith("2025_sem11.pdf")
                else "Casos hasta la semana epidemiológica 1 del 2025"
            )
            self.pages = [_FakeCutoffPage(txt)]

    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
    monkeypatch.setattr(qa, "_area_pagina", lambda *_a, **_k: "0,720,540,0")
    monkeypatch.setattr(qa, "PdfReader", _FakeCutoffReader)

    # 1) Regresión 12 columnas normal: no lanza row_tol=4 y mantiene A50/A51/A54 + TOTAL 12
    calls_12: list[dict[str, Any]] = []

    def _read_normal_12(_path: str, **kw: Any) -> list[Any]:
        calls_12.append(kw)
        return [type("T", (), {"df": df_12.copy()})()]

    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf", _read_normal_12
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_capa_texto.camelot.read_pdf", _read_normal_12
    )
    monkeypatch.setattr(
        "scripts.piloto_carbon_alta1.qa_serie_extraida.camelot.read_pdf", _read_normal_12
    )

    res_12 = qa.inspect_one_pdf((str(pdf_normal), ["adquirida"], ["zacatecas"], 1, spec_optin))
    assert res_12["status"] == "ok"
    assert res_12["data_cols"] == 12
    assert res_12["optional_prev_in_image"] is False
    assert res_12["layout_reparaciones"] == []
    assert res_12["printed_total_12"] == sums_12
    assert res_12["lag_matches_mmwr"] is True
    assert not any(c.get("row_tol") == 4 for c in calls_12)
    assert res_12["cells_a51"] == exp_12_a51

    # 2) Boletín con renglón partido: sin opt-in falla en unexpected_shape; con opt-in recupera row_tol=4
    def _read_split_then_rt4(_path: str, **kw: Any) -> list[Any]:
        chosen = df_12.copy() if kw.get("row_tol") == 4 else df_split.copy()
        return [type("T", (), {"df": chosen})()]

    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf", _read_split_then_rt4
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_capa_texto.camelot.read_pdf", _read_split_then_rt4
    )
    monkeypatch.setattr(
        "scripts.piloto_carbon_alta1.qa_serie_extraida.camelot.read_pdf", _read_split_then_rt4
    )

    res_no_opt = qa.inspect_one_pdf(
        (str(pdf_split), ["adquirida"], ["zacatecas"], 1, spec_no_optin)
    )
    assert res_no_opt["status"] == "unexpected_shape"
    res_4tuple = qa.inspect_one_pdf((str(pdf_split), ["adquirida"], ["zacatecas"], 1))
    assert res_4tuple["status"] == "unexpected_shape"

    res_rt4 = qa.inspect_one_pdf((str(pdf_split), ["adquirida"], ["zacatecas"], 1, spec_optin))
    assert res_rt4["status"] == "ok"
    assert res_rt4["data_cols"] == 12
    assert res_rt4["layout_reparaciones"] == ["row_tol=4"]
    assert res_rt4["optional_prev_in_image"] is False
    assert res_rt4["printed_total_12"] == sums_12
    assert res_rt4["cells_a51"] == exp_12_a51

    canon_rt4: dict[tuple[int, int], dict[str, list[int | None]]] = {
        (2025, 2): {cve: list(vals) for cve, vals in exp_12_a51.items()}
    }
    c6_rt4 = qa.compare_canon_against_pdf_blocks(canon_rt4, [res_rt4])
    assert c6_rt4["files_by_status"]["reparado_row_tol"] == ["2025_sem02.pdf"]
    assert c6_rt4["files_by_status"]["total_coincide"] == ["2025_sem02.pdf"]
    assert c6_rt4["files_by_status"]["total_coincide_12col"] == ["2025_sem02.pdf"]
    assert c6_rt4["canon_cell_by_cell_contrast"]["canon_vs_target_a51_diff_cells"] == 0

    # 3) Negativa row_tol=4: si el TOTAL impreso no cuadra con las 32 entidades, falla cerrado
    df_bad_tot = df_12.copy()
    df_bad_tot.iloc[-1, 5] = "99999"

    def _read_split_bad_tot(_path: str, **kw: Any) -> list[Any]:
        chosen = df_bad_tot.copy() if kw.get("row_tol") == 4 else df_split.copy()
        return [type("T", (), {"df": chosen})()]

    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf", _read_split_bad_tot
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_capa_texto.camelot.read_pdf", _read_split_bad_tot
    )
    monkeypatch.setattr(
        "scripts.piloto_carbon_alta1.qa_serie_extraida.camelot.read_pdf", _read_split_bad_tot
    )

    res_rt4_bad = qa.inspect_one_pdf((str(pdf_split), ["adquirida"], ["zacatecas"], 1, spec_optin))
    assert res_rt4_bad["status"] == "unexpected_shape"
    assert "TOTAL impreso" in str(res_rt4_bad.get("reason", ""))


def test_p2_11col_prev_en_imagen_total_proyectado_corte_raster_y_deltas_sin_caida_falsa(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2+L2: 11 col proyecta None en prev/TOTAL[7], corte raster es denominador ausente y sin caída falsa."""
    df_12, _, df_11, exp_12_a51, exp_11_a51_3, sums_12, sums_11 = _build_layout_tables_qa()
    spec_optin = _optin_group_spec_qa()
    spec_no_sp = {k: v for k, v in spec_optin.items() if k != "bloque_sin_prev_en_capa_texto"}

    pdf_11_w11 = tmp_path / "2025_sem11.pdf"
    pdf_11_w12 = tmp_path / "2025_sem12.pdf"
    pdf_11_w11.write_bytes(b"%PDF-1.4\n")
    pdf_11_w12.write_bytes(b"%PDF-1.4\n")

    class _FakePageText:
        def __init__(self, txt: str) -> None:
            self._txt = txt

        def extract_text(self) -> str:
            return self._txt

    class _FakeMixedReader:
        def __init__(self, path: str) -> None:
            # En 2025_sem12.pdf el subtítulo de corte también es imagen rasterizada (sin texto)
            txt = (
                "Casos hasta la semana epidemiológica 10 del 2025"
                if path.endswith("2025_sem11.pdf")
                else "CUADRO 6 Sífilis adquirida"
            )
            self.pages = [_FakePageText(txt)]

    def _read_mixed(path: str, **_kw: Any) -> list[Any]:
        chosen = df_12.copy() if path.endswith("2025_sem11.pdf") else df_11.copy()
        return [type("T", (), {"df": chosen})()]

    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
    monkeypatch.setattr(qa, "_area_pagina", lambda *_a, **_k: "0,720,540,0")
    monkeypatch.setattr(qa, "PdfReader", _FakeMixedReader)
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf", _read_mixed
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_capa_texto.camelot.read_pdf", _read_mixed
    )
    monkeypatch.setattr(
        "scripts.piloto_carbon_alta1.qa_serie_extraida.camelot.read_pdf", _read_mixed
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_capa_texto.pdfplumber.open",
        lambda _p: _FakePdfPlumberDocQA(_FakePageGeometryQA()),
    )

    # 1) Sin bloque_sin_prev_en_capa_texto, 11 columnas sigue rechazándose como unexpected_shape
    res_no_sp = qa.inspect_one_pdf((str(pdf_11_w12), ["adquirida"], ["zacatecas"], 1, spec_no_sp))
    assert res_no_sp["status"] == "unexpected_shape"

    # 2) Con opt-in real: valida geometría + TOTAL 11, proyecta prev=None y TOTAL[7]=None
    res_w11 = qa.inspect_one_pdf((str(pdf_11_w11), ["adquirida"], ["zacatecas"], 1, spec_optin))
    res_w12 = qa.inspect_one_pdf((str(pdf_11_w12), ["adquirida"], ["zacatecas"], 1, spec_optin))
    assert res_w11["status"] == "ok" and res_w12["status"] == "ok"
    assert res_w12["data_cols"] == 11
    assert res_w12["optional_prev_in_image"] is True
    assert res_w12["layout_reparaciones"] == ["sin_prev_en_capa_texto"]
    assert res_w12["printed_target"] is None and res_w12["lag_matches_mmwr"] is None

    tot_proj = res_w12["printed_total_12"]
    assert isinstance(tot_proj, list) and len(tot_proj) == 12
    assert tot_proj[7] is None
    assert tot_proj[:7] == sums_11[:7]
    assert tot_proj[8:] == sums_11[7:]

    for cve, vals3 in exp_11_a51_3.items():
        assert res_w12["cells_a51"][cve] == [*vals3, None]
        assert len(res_w12["cells_a50"][cve]) == 4 and None not in res_w12["cells_a50"][cve]
        assert len(res_w12["cells_a54"][cve]) == 4 and None not in res_w12["cells_a54"][cve]

    # 3) Contraste C6 sobre el par (12 col + 11 col): TOTAL coincide en Sem/H/M disponibles,
    #    corte raster es denominador ausente (ni lag_verified_match ni lag_mismatch), y NA separados
    canon_pair: dict[tuple[int, int], dict[str, list[int | None]]] = {
        (2025, 11): {cve: list(vals) for cve, vals in exp_12_a51.items()},
        (2025, 12): {cve: [*vals3, None] for cve, vals3 in exp_11_a51_3.items()},
    }
    c6 = qa.compare_canon_against_pdf_blocks(canon_pair, [res_w11, res_w12])
    assert c6["files_by_status"]["ok"] == ["2025_sem11.pdf", "2025_sem12.pdf"]
    assert c6["files_by_status"]["sin_prev_en_capa_texto"] == ["2025_sem12.pdf"]
    assert c6["files_by_status"]["total_coincide"] == ["2025_sem11.pdf", "2025_sem12.pdf"]
    assert c6["files_by_status"]["total_coincide_12col"] == ["2025_sem11.pdf"]
    assert c6["files_by_status"]["total_coincide_11col_sin_prev"] == ["2025_sem12.pdf"]
    assert c6["files_by_status"]["total_difiere"] == []
    assert c6["files_by_status"]["sin_total_12"] == []

    # Rezago: 1 legible verificado, 0 discrepancias, 1 denominador ausente por raster
    assert c6["files_by_status"]["lag_verified_match"] == ["2025_sem11.pdf"]
    assert c6["files_by_status"]["lag_mismatch"] == []
    assert c6["files_by_status"]["header_cutoff_unparsed"] == ["2025_sem12.pdf"]
    assert c6["files_by_status"]["header_cutoff_unparsed_raster_prev"] == ["2025_sem12.pdf"]
    assert c6["files_by_status"]["header_cutoff_unparsed_full_text"] == []

    cc = c6["canon_cell_by_cell_contrast"]
    assert cc["denominator_bulletins"] == 2
    assert cc["denominator_cells_4col"] == 256
    assert cc["optional_prev_image_bulletins"] == 1
    assert cc["optional_prev_image_cells"] == 32
    assert cc["denominator_text_extractable_cells"] == 224
    assert cc["canon_vs_target_a51_diff_cells"] == 0
    assert cc["canon_vs_target_a51_current_sem_h_m_diff_cells"] == 0
    assert cc["canon_missing_current_sem_h_m_cells"] == 0
    assert cc["canon_missing_prev_year_cells"] == 32
    assert cc["pdf_a51_missing_current_sem_h_m_cells"] == 0
    assert cc["pdf_a51_missing_prev_year_cells"] == 32
    assert cc["pdf_a51_missing_prev_year_text_cells"] == 0
    assert sums_12 != sums_11

    # Negativa: si canon_csv hubiera rellenado 0 en lugar de NA para 2025_sem12, C6 lo detecta
    canon_zero_bug: dict[tuple[int, int], dict[str, list[int | None]]] = {
        (2025, 12): {cve: [*vals3, 0] for cve, vals3 in exp_11_a51_3.items()}
    }
    c6_zero_bug = qa.compare_canon_against_pdf_blocks(canon_zero_bug, [res_w12])
    assert c6_zero_bug["canon_cell_by_cell_contrast"]["canon_vs_target_a51_diff_cells"] == 32
    assert c6_zero_bug["files_by_status"]["total_difiere"] == ["2025_sem12.pdf"]

    # 4) Trayectorias y NA separados en CSV: acum_prev vacío NO fabrica caída falsa en 2025_sem12
    catalog = load_geo_catalog()
    entidades = [catalog.entity(cve).nombre_canonico for cve in sorted(catalog.cve_ents())]
    header = (
        "Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_hombres,"
        "Acumulado_mujeres,Acumulado_anio_anterior"
    )
    csv_ok_lines = [header]
    for ent in entidades:
        csv_ok_lines.append(f"2025,11,{ent},Sífilis adquirida,2,20,10,100")
        csv_ok_lines.append(f"2025,12,{ent},Sífilis adquirida,3,23,12,")
        csv_ok_lines.append(f"2025,13,{ent},Sífilis adquirida,2,25,14,110")
    csv_ok = tmp_path / "canon_prev_na_ok.csv"
    csv_ok.write_text("\n".join(csv_ok_lines) + "\n", encoding="utf-8")

    _, diag_ok = qa.analyze_canon_csv_cells_and_trajectories(
        csv_ok, lag=1, keep_period_files=set()
    )
    t25 = diag_ok["target_2025_csv_na_and_minus_one"]
    assert t25["na_current_sem_h_m_cells_in_2025_targets"] == 0
    assert t25["na_optional_prev_year_cells_in_2025_targets"] == 32
    assert t25["na_optional_prev_year_files_in_2025_targets"] == ["2025_sem12.pdf"]

    raw_sum = diag_ok["raw_csv_missing_cells_summary"]
    assert raw_sum["missing_current_sem_h_m_cells_total"] == 0
    assert raw_sum["missing_optional_prev_year_cells_total"] == 32
    assert raw_sum["missing_optional_prev_year_files"] == ["2025_sem12.pdf"]

    traj_ok = diag_ok["cumulative_trajectories_and_anomalies"]
    nat_by_file = {r["file"]: r for r in traj_ok["national_series_by_source_week"]}
    assert nat_by_file["2025_sem12.pdf"]["acum_prev"] is None
    assert traj_ok["optional_prev_na_national_files"] == ["2025_sem12.pdf"]
    assert traj_ok["national_cumulative_drops_by_file"] == []
    assert traj_ok["national_prev_year_drops_by_file"] == []

    # L2: si 2025_sem13 cae realmente en Acumulado_anio_anterior respecto a 2025_sem11 (a través del NA), sí se detecta
    csv_drop_lines = [header]
    for ent in entidades:
        csv_drop_lines.append(f"2025,11,{ent},Sífilis adquirida,2,20,10,100")
        csv_drop_lines.append(f"2025,12,{ent},Sífilis adquirida,3,23,12,")
        csv_drop_lines.append(f"2025,13,{ent},Sífilis adquirida,2,25,14,80")
    csv_drop = tmp_path / "canon_prev_drop_l2.csv"
    csv_drop.write_text("\n".join(csv_drop_lines) + "\n", encoding="utf-8")
    _, diag_drop = qa.analyze_canon_csv_cells_and_trajectories(
        csv_drop, lag=1, keep_period_files=set()
    )
    traj_drop = diag_drop["cumulative_trajectories_and_anomalies"]
    assert [x["file"] for x in traj_drop["national_prev_year_drops_by_file"]] == ["2025_sem13.pdf"]
    assert [x["file"] for x in traj_drop["national_cumulative_drops_by_file"]] == [
        "2025_sem13.pdf"
    ]
    assert traj_drop["state_prev_year_negative_delta_files"] == ["2025_sem13.pdf"]


@pytest.mark.parametrize(
    ("geo_kwargs", "mutate_mode", "expected_reason"),
    [
        ({"include_central_acum_text": True}, "none", "patrón de encabezados Acum."),
        ({"omit_left_acum_text": True}, "none", "patrón de encabezados Acum."),
        ({"n_central_images": 10}, "none", "imágenes de celda en banda central"),
        ({"extra_outside_image": True}, "none", "imágenes de celda en banda central"),
        ({"stray_word_in_gap": True}, "none", "tokens de texto dentro de la banda"),
        ({}, "bad_total", "distinta del TOTAL impreso"),
        ({}, "empty_cell", "celdas o filas vacías"),
    ],
)
def test_p2_11col_geometria_negativa_y_total_descuadrado_fallan_cerrado(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    geo_kwargs: dict[str, Any],
    mutate_mode: str,
    expected_reason: str,
) -> None:
    """P2: cualquier desviación de geometría PDF, TOTAL 11 o celda vacía rechaza en unexpected_shape."""
    _, _, df_11, _, _, _, _ = _build_layout_tables_qa()
    spec_optin = _optin_group_spec_qa()
    pdf = tmp_path / "2026_sem42.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    tbl_used = df_11.copy()
    if mutate_mode == "bad_total":
        tbl_used.iloc[-1, 6] = "1"
    elif mutate_mode == "empty_cell":
        tbl_used.iloc[2, 6] = ""

    class _FakePage:
        def extract_text(self) -> str:
            return "CUADRO 6 Sífilis adquirida"

    class _FakeReader:
        def __init__(self, _path: str) -> None:
            self.pages = [_FakePage()]

    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
    monkeypatch.setattr(qa, "_area_pagina", lambda *_a, **_k: "0,720,540,0")
    monkeypatch.setattr(qa, "PdfReader", _FakeReader)
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": tbl_used.copy()})()],
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_capa_texto.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": tbl_used.copy()})()],
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_capa_texto.pdfplumber.open",
        lambda _p: _FakePdfPlumberDocQA(_FakePageGeometryQA(**geo_kwargs)),
    )

    res = qa.inspect_one_pdf((str(pdf), ["adquirida"], ["zacatecas"], 1, spec_optin))
    assert res["status"] == "unexpected_shape"
    assert expected_reason in str(res.get("reason", ""))

    c6 = qa.compare_canon_against_pdf_blocks({}, [res])
    assert c6["files_by_status"]["ok"] == []
    assert c6["files_by_status"]["unexpected_shape"] == ["2026_sem42.pdf"]
    assert len(c6["unexpected_shape_details"]) == 1


def test_i1_fila_nacional_y_trayectorias_marcan_estados_sin_sem_h_m_independiente_de_prev(
    tmp_path: Path,
) -> None:
    """I1: contadores exactos de estados sin Sem/H/M en fila nacional y caídas/saltos, independientes de prev."""
    catalog = load_geo_catalog()
    entidades = [catalog.entity(cve).nombre_canonico for cve in sorted(catalog.cve_ents())]
    header = (
        "Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_hombres,"
        "Acumulado_mujeres,Acumulado_anio_anterior"
    )

    lines_with_na = [header]
    lines_control = [header]
    for ent in entidades:
        # 2016_sem49: las 32 entidades completas
        lines_with_na.append(f"2016,49,{ent},Sífilis adquirida,2,24,14,52")
        lines_control.append(f"2016,49,{ent},Sífilis adquirida,2,24,14,52")

        # 2016_sem50: Querétaro trae Casos_semana vacío (n.e. en fuente abierta -> NA, no 0) y acumulados presentes
        sem_50 = "" if ent == "Querétaro" else "2"
        lines_with_na.append(f"2016,50,{ent},Sífilis adquirida,{sem_50},26,15,54")
        lines_control.append(f"2016,50,{ent},Sífilis adquirida,2,26,15,54")

        # 2016_sem51: las 32 entidades completas de nuevo (sin umbral nuevo ni alteración del resto)
        lines_with_na.append(f"2016,51,{ent},Sífilis adquirida,2,28,16,56")
        lines_control.append(f"2016,51,{ent},Sífilis adquirida,2,28,16,56")

        # 2017_sem04..06: ausencia sintética en acum_h (1 estado) y acum_m (2 estados) en sem05 para verificar
        # arrastre de contadores a caídas, saltos y tripletas revertidas
        lines_with_na.append(f"2017,04,{ent},Sífilis adquirida,2,10,10,8")
        h_05 = "" if ent == "Aguascalientes" else "12"
        m_05 = "" if ent in {"Aguascalientes", "Zacatecas"} else "12"
        lines_with_na.append(f"2017,05,{ent},Sífilis adquirida,2,{h_05},{m_05},10")
        lines_with_na.append(f"2017,06,{ent},Sífilis adquirida,2,14,14,12")

        # 2026_sem08: las 32 entidades sin Acumulado_anio_anterior (3col_noprev) pero con Sem/H/M completos
        lines_with_na.append(f"2026,08,{ent},Sífilis adquirida,3,30,20,")

    csv_na = tmp_path / "canon_i1_na.csv"
    csv_ctrl = tmp_path / "canon_i1_ctrl.csv"
    csv_na.write_text("\n".join(lines_with_na) + "\n", encoding="utf-8")
    csv_ctrl.write_text("\n".join(lines_control) + "\n", encoding="utf-8")

    _, diag_na = qa.analyze_canon_csv_cells_and_trajectories(
        csv_na, lag=1, keep_period_files=set()
    )
    _, diag_ctrl = qa.analyze_canon_csv_cells_and_trajectories(
        csv_ctrl, lag=1, keep_period_files=set()
    )

    traj = diag_na["cumulative_trajectories_and_anomalies"]
    traj_ctrl = diag_ctrl["cumulative_trajectories_and_anomalies"]
    nat_by_file = {r["file"]: r for r in traj["national_series_by_source_week"]}
    ctrl_by_file = {r["file"]: r for r in traj_ctrl["national_series_by_source_week"]}

    # 1) Caso 2016_sem50 (Querétaro Sem NA): contador sem_missing_states=1 y acum_prev independiente (0)
    r50 = nat_by_file["2016_sem50.pdf"]
    assert r50["sem"] == 62  # 31 estados numéricos * 2; la ausencia queda marcada explícitamente
    assert r50["acum_h"] == 832 and r50["acum_m"] == 480 and r50["acum_total"] == 1312
    assert r50["acum_prev"] == 1728
    assert r50["sem_missing_states"] == 1
    assert r50["acum_h_missing_states"] == 0
    assert r50["acum_m_missing_states"] == 0
    assert r50["has_current_missing_states"] is True
    assert r50["acum_prev_missing_states"] == 0

    # Datos numéricos idénticos en las semanas completas adyacentes (2016_sem49 y 2016_sem51)
    for intact_file in ("2016_sem49.pdf", "2016_sem51.pdf"):
        assert nat_by_file[intact_file] == ctrl_by_file[intact_file]
        assert nat_by_file[intact_file]["has_current_missing_states"] is False

    # La entrada de brecha Sem - delta_acum_total para 2016_sem50 arrastra el indicador exacto
    gaps_by_file = {g["file"]: g for g in traj["top_10_abs_sem_minus_delta_acum_total"]}
    g50 = gaps_by_file["2016_sem50.pdf"]
    assert g50["sem_printed"] == 62
    assert g50["delta_acum_total"] == 96
    assert g50["sem_minus_delta_total"] == -34
    assert g50["sem_missing_states"] == 1
    assert g50["acum_h_missing_states"] == 0
    assert g50["acum_m_missing_states"] == 0
    assert g50["has_current_missing_states"] is True
    assert g50["acum_prev_missing_states"] == 0

    # 2) Independencia frente a NA del año anterior (2026_sem08: prev NA=32, actuales NA=0)
    r26 = nat_by_file["2026_sem08.pdf"]
    assert r26["acum_prev"] is None
    assert r26["acum_prev_missing_states"] == 32
    assert r26["sem_missing_states"] == 0
    assert r26["acum_h_missing_states"] == 0
    assert r26["acum_m_missing_states"] == 0
    assert r26["has_current_missing_states"] is False
    assert traj["current_sem_h_m_na_national_files"] == ["2016_sem50.pdf", "2017_sem05.pdf"]
    assert traj["optional_prev_na_national_files"] == ["2026_sem08.pdf"]

    # 3) Arrastre a caídas, saltos y tripletas revertidas cuando faltan acum_h / acum_m (2017_sem05..06)
    r17_05 = nat_by_file["2017_sem05.pdf"]
    assert r17_05["acum_h_missing_states"] == 1 and r17_05["acum_m_missing_states"] == 2
    jumps_by_file = {j["file"]: j for j in traj["top_10_weekly_acum_total_jumps"]}
    j06 = jumps_by_file["2017_sem06.pdf"]
    assert j06["prev_acum_h_missing_states"] == 1
    assert j06["prev_acum_m_missing_states"] == 2
    assert j06["acum_h_missing_states"] == 0 and j06["acum_m_missing_states"] == 0
    assert j06["has_current_missing_states"] is True

    # 2017_sem05 tuvo 31*12 + 30*12 = 732 > 640 (sem04), pero si probamos caída aparente con valores altos:
    # Verificamos también que cualquier caída aparente en national_cumulative_drops_by_file conserva los contadores
    lines_drop_na = [
        header,
        *(f"2018,01,{ent},Sífilis adquirida,5,100,100,90" for ent in entidades),
        *(
            f"2018,02,{ent},Sífilis adquirida,5,{'101' if idx > 1 else ''},101,95"
            for idx, ent in enumerate(entidades)
        ),
        *(f"2018,03,{ent},Sífilis adquirida,5,102,102,98" for ent in entidades),
    ]
    csv_drop_na = tmp_path / "canon_i1_drop_triplet.csv"
    csv_drop_na.write_text("\n".join(lines_drop_na) + "\n", encoding="utf-8")
    _, diag_drop_na = qa.analyze_canon_csv_cells_and_trajectories(
        csv_drop_na, lag=1, keep_period_files=set()
    )
    traj_dn = diag_drop_na["cumulative_trajectories_and_anomalies"]
    drops_dn = {d["file"]: d for d in traj_dn["national_cumulative_drops_by_file"]}
    assert drops_dn["2018_sem02.pdf"]["acum_h_missing_states"] == 2
    assert drops_dn["2018_sem02.pdf"]["has_current_missing_states"] is True
    triplets_dn = {t["file"]: t for t in traj_dn["national_spike_or_drop_reverted_triplets"]}
    assert triplets_dn["2018_sem02.pdf"]["triplet_acum_h_missing_states"] == [0, 2, 0]
    assert triplets_dn["2018_sem02.pdf"]["triplet_has_current_missing_states"] is True


def test_add_a51_history_base_hermetico_paridad_85_a_86_noop_y_no_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica add_a51_history_base: prefijo idéntico, <=W43, NO-OP y no-overwrite."""
    import csv as csv_mod
    import io

    repo_root = Path(registry.__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)
    # Estado de 86 publicados que el script histórico exige: alta_b44 vuelve a ``trained``.
    texto_real = yaml_sin_alta_b44(_YAML_PADECIMIENTOS_REAL.read_text(encoding="utf-8"))

    with _registry_desde_yaml(texto_real):
        catalog = load_geo_catalog()
        entidades = [catalog.entity(cve).nombre_canonico for cve in sorted(catalog.cve_ents())]
        assert len(entidades) == 32
        old_85_names = [
            d.data_name
            for d in registry.get_registry().diseases
            if d.lifecycle == "published" and d.id != "sifilis_adquirida_a51"
        ]
        assert len(old_85_names) == 85

        # Generar 53 semanas MMWR contiguas hasta (2026, 43) inclusive + (2026, 44) post-corte
        start_period = (2025, 44)
        periods_53: list[tuple[int, int]] = [start_period]
        while periods_53[-1] != (2026, 43):
            periods_53.append(semana_siguiente(periods_53[-1][0], periods_53[-1][1], 1))
        assert len(periods_53) == 53

        buf_base = io.StringIO()
        w_base = csv_mod.writer(buf_base, lineterminator="\n")
        w_base.writerow(paso_semanal.CONSOLIDADO_COLS.split(","))
        for pad_name in old_85_names:
            for anio, sem in periods_53[-52:]:
                for ent in entidades:
                    w_base.writerow([anio, sem, ent, pad_name, "1", "2", "3", "4"])
        base_csv = tmp_path / "base_85_w43.csv"
        base_bytes = buf_base.getvalue().encode("utf-8")
        base_csv.write_bytes(base_bytes)
        base_sha = _sha256_bytes(base_bytes)

        buf_raw = io.StringIO()
        w_raw = csv_mod.writer(buf_raw, lineterminator="\n")
        w_raw.writerow(paso_semanal.CONSOLIDADO_COLS.split(","))
        full_na_p = periods_53[0]
        prev_na_p = periods_53[1]
        partial_na_p = periods_53[2]
        for anio, sem in [*periods_53, (2026, 44)]:
            for ent in entidades:
                if (anio, sem) == full_na_p:
                    vals = ["", "", "", ""]
                elif (anio, sem) == prev_na_p:
                    vals = ["2", "10.0", "8.0", ""]
                elif (anio, sem) == partial_na_p and ent == "Querétaro":
                    vals = ["", "11.0", "9.0", "15"]
                else:
                    vals = ["3", "12.0", "10.0", "18"]
                w_raw.writerow([anio, f"{sem:02d}", ent, "Sífilis adquirida", *vals])
        raw_csv = tmp_path / "raw_a51.csv"
        raw_bytes = buf_raw.getvalue().encode("utf-8")
        raw_csv.write_bytes(raw_bytes)
        raw_sha = _sha256_bytes(raw_bytes)

        out_csv = tmp_path / "out" / "base_86_w43.csv"
        rep_json = tmp_path / "out" / "report_86.json"
        cli_args = [
            "--base-csv",
            str(base_csv),
            "--expected-base-sha256",
            base_sha,
            "--raw-a51-csv",
            str(raw_csv),
            "--expected-raw-sha256",
            raw_sha,
            "--cutoff-year",
            "2026",
            "--cutoff-week",
            "43",
            "--out-csv",
            str(out_csv),
            "--report-json",
            str(rep_json),
        ]

        # 1) Sin pubflag falla cerrado sin crear salida
        with _registry_desde_yaml(_yaml_a51_pre_pubflag_trained(texto_real)):
            assert ahb.main(cli_args) == 2
            assert not out_csv.exists()

        # 2) Con pubflag construye BASE_86_W43 conservando prefijo byte a byte y excluyendo W44
        assert ahb.main(cli_args) == 0
        assert out_csv.is_file() and rep_json.is_file()
        assert base_csv.read_bytes() == base_bytes
        out_bytes = out_csv.read_bytes()
        assert out_bytes[: len(base_bytes)] == base_bytes
        rep = json.loads(rep_json.read_text(encoding="utf-8"))
        assert rep["status"] == "CREATED_VERIFIED" and rep["noop_identical"] is False
        assert rep["old85_guard"]["old_published_verified"] == 85
        assert rep["new86_guard"]["new_published_verified"] == 86
        assert rep["a51_history"]["rows_added"] == 53 * 32
        assert rep["a51_history"]["periods_excluded_after_cutoff"] == [[2026, 44]]
        assert rep["a51_history"]["na_declaration"]["full_row_na_periods"] == [list(full_na_p)]
        assert rep["a51_history"]["na_declaration"]["prev_year_only_na_periods"] == [
            list(prev_na_p)
        ]
        assert len(rep["a51_history"]["na_declaration"]["partial_na_cells"]) == 1
        assert rep["inherited_exclusions_and_lag"]["lag_applied_in_consolidado"] is False

        # 3) Segunda pasada sobre archivo idéntico: NO-OP sin reescribir el inodo
        ino_before = out_csv.stat().st_ino
        rep2 = ahb.build_base_86_w43(
            base_csv=base_csv,
            expected_base_sha256=base_sha,
            raw_a51_csv=raw_csv,
            expected_raw_sha256=raw_sha,
            cutoff_year=2026,
            cutoff_week=43,
            out_csv=out_csv,
            report_json=None,
        )
        assert rep2["status"] == "NOOP_IDENTICAL" and rep2["noop_identical"] is True
        assert out_csv.stat().st_ino == ino_before

        # 4) Archivo existente distinto jamás se sobrescribe
        unique_existing = tmp_path / "unique_existing.csv"
        unique_payload = b"unique_content_do_not_touch\n"
        unique_existing.write_bytes(unique_payload)
        bad_args = [*cli_args[:-4], "--out-csv", str(unique_existing)]
        assert ahb.main(bad_args) == 2
        assert unique_existing.read_bytes() == unique_payload
