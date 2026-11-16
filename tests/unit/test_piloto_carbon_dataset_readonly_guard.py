"""Guardas de idempotencia readonly (0444), no-replace y rechazo fail-closed en EpiDatasetV2.

Cubre de forma 100% sintética y CI-safe (sin skips ni datos gitignored):
1. Reproducción exacta del ``PermissionError`` de ``smoke7_935`` cuando ``raw`` sellado ``0444``
   se copia en la primera pasada de ``validate_data`` / ``build_epi_dataset_v2`` y una segunda
   llamada reentra sobre ``runs/<dataset_id>/inputs/data_raw_*.csv`` en modo ``0444``.
2. Equivalencia dorada de ``dataset_id``, digests, 64 series base + 47 derivados = 111 productos
   y valores tabulares frente al pipeline puro de referencia, incluido reingreso con distinto
   ``code_commit`` en ``dataset_manifest.json``.
3. Rechazo ANTES de cualquier escritura/chmod/borrado cuando difieren ``raw`` (incluso con mismo
   ``dataset_digest`` / ``run_id``), catálogo geográfico, exposición efectiva, config efectiva,
   nombre de insumo, manifiestos o contexto ajeno/incompleto/enlaces simbólicos.
4. Creación exclusiva sin reemplazo (``hardlink_to`` atómico no-replace) ante carreras concurrentes.
"""

from __future__ import annotations

from datetime import date
import hashlib
import importlib
import json
from pathlib import Path
import stat
from typing import Any

import pandas as pd
import pytest

from epiforecast.data import epi_aggregate as ea
from epiforecast.data import epi_calendar as ec
from epiforecast.data import epi_dataset as ed
from epiforecast.data.epi_dataset_spec import EpiDatasetConfig, ExposureSnapshot
from epiforecast.data.epi_geo_exposure import GeoCatalog, geo_catalog_path, load_geo_catalog
from epiforecast.data.epi_reconcile import reconcile_state
from epiforecast.data.sex_scheme import scheme_for
from epiforecast.runner import orchestrator as orch

_DISEASE_ID = "sifilis_adquirida_a51"
_DISEASE_NAME = "Sífilis Adquirida"
_RAW_FILENAME = "data_raw_Sifilis_Adquirida_A51.csv"
_READONLY_FILE_MODE = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH  # 0o444
_READONLY_DIR_MODE = (
    stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
)  # 0o555


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_tree(root: Path) -> dict[str, tuple[str, int, int, int, int]]:
    """Mapa ``rel_path -> (sha256, mode_perms, mtime_ns, ino, size)`` sin seguir symlinks."""
    out: dict[str, tuple[str, int, int, int, int]] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        st = p.lstat()
        if stat.S_ISLNK(st.st_mode):
            out[rel] = ("SYMLINK", stat.S_IMODE(st.st_mode), st.st_mtime_ns, st.st_ino, st.st_size)
        elif stat.S_ISREG(st.st_mode):
            out[rel] = (
                _sha256(p),
                stat.S_IMODE(st.st_mode),
                st.st_mtime_ns,
                st.st_ino,
                st.st_size,
            )
        elif stat.S_ISDIR(st.st_mode):
            out[rel] = ("DIR", stat.S_IMODE(st.st_mode), 0, st.st_ino, 0)
    return out


def _synthetic_exposure(catalog: GeoCatalog, *, bump: int = 0) -> ExposureSnapshot:
    by_cve: dict[str, dict[str, int]] = {}
    for idx, cve in enumerate(catalog.cve_ents(), start=1):
        h = 100_000 + idx * 1_000 + bump
        m = 105_000 + idx * 1_000 + bump
        by_cve[cve] = {"Hombres": h, "Mujeres": m, "Total": h + m}
    payload = json.dumps(by_cve, sort_keys=True).encode("utf-8")
    return ExposureSnapshot(
        source_id="inegi_cpv2020_static",
        reference="CPV 2020 sintético",
        cutoff=date(2020, 3, 15),
        columns_by_sex={"hombres": "Hombres", "mujeres": "Mujeres"},
        total_column="Total",
        digest=hashlib.sha256(payload).hexdigest(),
        by_cve_ent=by_cve,
    )


def _synthetic_raw_df(
    catalog: GeoCatalog,
    *,
    case_offset: int = 0,
    prev_year_acum: int = 7,
) -> pd.DataFrame:
    """4 semanas fuente cruzando frontera 2025-W53..2026-W03 (lag=1 → 2025-W52..2026-W02)."""
    source_periods = [(2025, 53), (2026, 1), (2026, 2), (2026, 3)]
    rows: list[dict[str, object]] = []
    acum: dict[str, tuple[int, int]] = {}
    for k, (anio, semana) in enumerate(source_periods):
        tp = ec.target_period(anio, semana, 1)
        for idx, ent in enumerate(catalog.entities):
            h0, m0 = (0, 0) if tp.epi_week == 1 else acum.get(ent.cve_ent, (0, 0))
            casos = 2 + ((k + idx) % 6) + case_offset
            h = casos // 2
            m = casos - h
            acum[ent.cve_ent] = (h0 + h, m0 + m)
            # Una celda Casos_semana en NA (Querétaro, última semana) para ejercitar imputación.
            casos_cell: float | int = float("nan") if (k == 3 and ent.cve_ent == "22") else casos
            rows.append(
                {
                    "Anio": anio,
                    "Semana": semana,
                    "Entidad": ent.nombre_canonico,
                    "Padecimiento": _DISEASE_NAME,
                    "Casos_semana": casos_cell,
                    "Acumulado_hombres": h0 + h,
                    "Acumulado_mujeres": m0 + m,
                    "Acumulado_anio_anterior": prev_year_acum,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def syn_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    catalog = load_geo_catalog()
    snap = _synthetic_exposure(catalog)
    monkeypatch.setattr(
        ed,
        "load_exposure_snapshot",
        lambda source_id, cat, config_path=None: snap,
    )
    monkeypatch.setattr(orch, "_git_commit", lambda: "9" * 40)

    raw_dir = tmp_path / "staged_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_csv = raw_dir / _RAW_FILENAME
    raw_df = _synthetic_raw_df(catalog)
    raw_df.to_csv(raw_csv, index=False)
    raw_csv.chmod(_READONLY_FILE_MODE)  # Tal como sella stage_raw_for_validate_data (0444)

    runs_root = tmp_path / "runs"
    return {
        "catalog": catalog,
        "snapshot": snap,
        "raw_csv": raw_csv,
        "raw_df": raw_df,
        "runs_root": runs_root,
    }


def test_repro_smoke935_readonly_raw_idempotent_noop_builder_and_validate_data(
    syn_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduce el PermissionError exacto de smoke7_935 y verifica NO-OP preservando modo/mtime/hash."""
    raw_csv: Path = syn_env["raw_csv"]
    runs_root: Path = syn_env["runs_root"]

    dm1 = orch.validate_data(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    dataset_dir = runs_root / dm1.dataset_id
    staged_raw = dataset_dir / "inputs" / _RAW_FILENAME
    assert staged_raw.is_file()
    assert stat.S_IMODE(staged_raw.lstat().st_mode) == _READONLY_FILE_MODE

    constructor_rels = (
        f"inputs/{_RAW_FILENAME}",
        "inputs/entidades_mx.csv",
        "inputs/exposure_inegi_cpv2020_static.csv",
        "inputs/config_effective.json",
        "epi_dataset_v2.csv",
        "manifest.json",
    )
    before_snap = _snapshot_tree(dataset_dir)
    for rel in constructor_rels:
        assert rel in before_snap

    # 1) Segunda llamada directa a build_epi_dataset_v2 (antes levantaba PermissionError en copy2).
    res2 = ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    assert res2.run_id == dm1.dataset_id
    after_builder_snap = _snapshot_tree(dataset_dir)
    assert after_builder_snap == before_snap

    # 2) Segunda llamada vía validate_data bajo un code_commit NUEVO (como retry de smoke7).
    monkeypatch.setattr(orch, "_git_commit", lambda: "a" * 40)
    dm2 = orch.validate_data(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    assert dm2.dataset_id == dm1.dataset_id
    assert dm2.code_commit == "a" * 40
    assert dm2.digests == dm1.digests
    assert dm2.counts == {"base": 64, "derived": 47, "products": 111}
    assert {a.path: a.digest for a in dm2.artifacts} == {a.path: a.digest for a in dm1.artifacts}

    after_validate_snap = _snapshot_tree(dataset_dir)
    for rel in constructor_rels:
        assert after_validate_snap[rel] == before_snap[rel]

    # 3) Incluso con TODOS los artefactos del constructor en 0444 e inputs/ en 0555 es NO-OP puro.
    inputs_dir = dataset_dir / "inputs"
    for rel in constructor_rels:
        (dataset_dir / rel).chmod(_READONLY_FILE_MODE)
    inputs_dir.chmod(_READONLY_DIR_MODE)
    try:
        sealed_snap = _snapshot_tree(dataset_dir)
        res3 = ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
        assert res3.run_id == dm1.dataset_id
        assert _snapshot_tree(dataset_dir) == sealed_snap
    finally:
        inputs_dir.chmod(0o755)
        for rel in constructor_rels:
            (dataset_dir / rel).chmod(0o644)


def test_golden_equivalence_111_products_values_and_dataset_id(syn_env: dict[str, Any]) -> None:
    """Verifica equivalencia byte-a-byte, dataset_id y 111 productos frente al cálculo puro."""
    catalog: GeoCatalog = syn_env["catalog"]
    snap: ExposureSnapshot = syn_env["snapshot"]
    raw_csv: Path = syn_env["raw_csv"]
    raw_df: pd.DataFrame = syn_env["raw_df"]
    runs_root: Path = syn_env["runs_root"]

    cfg = ed.load_config(_DISEASE_ID)
    scheme = scheme_for(cfg.disease_id)
    ref_prep = ed.build_prep(raw_df, catalog, cfg.observation_lag_weeks)
    ref_state = reconcile_state(ref_prep, set(catalog.cve_ents()))
    ref_base = (
        ed.explode_base(ref_state, snap, catalog, cfg.disease_id, scheme)
        .sort_values(ed._CANONICAL_ORDER)
        .reset_index(drop=True)
    )
    ref_csv_bytes = ed._canonical_csv(ref_base).encode("utf-8")
    ref_dataset_digest = hashlib.sha256(ref_csv_bytes).hexdigest()
    expected_dataset_id = f"{_DISEASE_ID}_{ref_dataset_digest[:12]}"
    ref_agg = ea.build_products(ref_base, catalog, cfg.disease_id)

    dm = orch.validate_data(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    dataset_dir = runs_root / dm.dataset_id

    assert dm.dataset_id == expected_dataset_id
    assert dm.dataset_id == "sifilis_adquirida_a51_ce26c6678eb1"
    assert dm.counts == {"base": 64, "derived": 47, "products": 111}
    assert dm.digests["dataset"] == ref_dataset_digest
    assert dm.digests["raw"] == _sha256(raw_csv)
    assert dm.digests["exposure"] == snap.digest
    assert (dataset_dir / "epi_dataset_v2.csv").read_bytes() == ref_csv_bytes

    manifest_disk = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_disk["counts"] == {
        "base_rows": 256,
        "state_rows": 128,
        "series": 64,
        "periods": 4,
        "imputed_totals": 1,
    }

    ref_products_csv: str = ref_agg.products.to_csv(index=False)
    assert (dataset_dir / "products.csv").read_bytes() == ref_products_csv.encode("utf-8")
    products_disk = pd.read_csv(dataset_dir / "products.csv", dtype={"geography_id": str})
    products_disk["quality_flags"] = products_disk["quality_flags"].fillna("")
    assert len(products_disk) == 111 * 4
    assert products_disk.groupby(["geography_level", "geography_id", "sex"]).ngroups == 111
    ref_products = ref_agg.products.copy()
    for col in ("geography_id", "period_start", "ds"):
        ref_products[col] = ref_products[col].astype(str)
    pd.testing.assert_frame_equal(
        products_disk.reset_index(drop=True),
        ref_products.reset_index(drop=True),
        check_dtype=False,
    )
    ref_lineage_bytes = json.dumps(ref_agg.lineage, indent=2, ensure_ascii=False).encode("utf-8")
    assert (dataset_dir / "lineage.json").read_bytes() == ref_lineage_bytes
    assert (dataset_dir / "inputs" / "entidades_mx.csv").read_bytes() == (
        geo_catalog_path().read_bytes()
    )


def test_mismatch_raw_same_dataset_digest_refused_before_any_write(
    syn_env: dict[str, Any], tmp_path: Path
) -> None:
    """Si cambia raw sin alterar dataset_digest (mismo run_id implícito), falla sin tocar nada."""
    catalog: GeoCatalog = syn_env["catalog"]
    raw_csv: Path = syn_env["raw_csv"]
    runs_root: Path = syn_env["runs_root"]

    res1 = ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    snap_readonly = _snapshot_tree(res1.run_dir)

    # Cambiar Acumulado_anio_anterior no cambia epi_dataset_v2.csv → mismo run_id automático,
    # pero distinto raw_digest y bytes de raw.
    alt_dir = tmp_path / "alt_raw_same_ds"
    alt_dir.mkdir()
    raw_v2 = alt_dir / _RAW_FILENAME
    _synthetic_raw_df(catalog, prev_year_acum=999).to_csv(raw_v2, index=False)

    # Caso A: existente en 0444 → debe levantar EpiDatasetError (no PermissionError) sin tocar nada
    with pytest.raises(ed.EpiDatasetError):
        ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_v2)
    assert _snapshot_tree(res1.run_dir) == snap_readonly

    # Caso B: existente en 0644 → también debe rehusar sin sobrescribir
    (res1.run_dir / "inputs" / _RAW_FILENAME).chmod(0o644)
    snap_writable = _snapshot_tree(res1.run_dir)
    with pytest.raises(ed.EpiDatasetError):
        ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_v2)
    assert _snapshot_tree(res1.run_dir) == snap_writable


def test_mismatch_inputs_raw_catalog_exposure_and_config_refused_intact(
    syn_env: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cambios en raw, nombre de raw, catálogo, exposición o config fallan ANTES de escribir."""
    catalog: GeoCatalog = syn_env["catalog"]
    raw_csv: Path = syn_env["raw_csv"]
    runs_root: Path = syn_env["runs_root"]

    res1 = ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    run_dir = res1.run_dir
    # Incluso si todos los archivos existentes fuesen escribibles (0644), NO deben sobrescribirse.
    (run_dir / "inputs" / _RAW_FILENAME).chmod(0o644)
    snap_before = _snapshot_tree(run_dir)

    # 1) Raw con valores distintos sobre el mismo run_id
    raw_diff = tmp_path / "diff_cases" / _RAW_FILENAME
    raw_diff.parent.mkdir()
    _synthetic_raw_df(catalog, case_offset=5).to_csv(raw_diff, index=False)
    with pytest.raises(ed.EpiDatasetError):
        ed.build_epi_dataset_v2(
            _DISEASE_ID, runs_root=runs_root, run_id=res1.run_id, raw_path=raw_diff
        )
    assert _snapshot_tree(run_dir) == snap_before

    # 2) Raw con los mismos bytes pero distinto nombre de archivo en inputs/
    raw_renamed = tmp_path / "renamed" / "data_raw_OtroNombre.csv"
    raw_renamed.parent.mkdir()
    raw_renamed.write_bytes(raw_csv.read_bytes())
    with pytest.raises(ed.EpiDatasetError):
        ed.build_epi_dataset_v2(
            _DISEASE_ID, runs_root=runs_root, run_id=res1.run_id, raw_path=raw_renamed
        )
    assert _snapshot_tree(run_dir) == snap_before

    # 3) Exposición efectiva distinta
    snap_bumped = _synthetic_exposure(catalog, bump=500)
    with monkeypatch.context() as mp:
        mp.setattr(ed, "load_exposure_snapshot", lambda sid, cat, config_path=None: snap_bumped)
        with pytest.raises(ed.EpiDatasetError):
            ed.build_epi_dataset_v2(
                _DISEASE_ID, runs_root=runs_root, run_id=res1.run_id, raw_path=raw_csv
            )
    assert _snapshot_tree(run_dir) == snap_before

    # 4a) Catálogo geográfico fuente alterado (cambia catalog_digest y config_digest)
    fake_root = tmp_path / "fake_root"
    (fake_root / "config" / "geografia").mkdir(parents=True)
    (fake_root / "config" / "data").symlink_to(ed._ROOT / "config" / "data")
    fake_cat = fake_root / "config" / "geografia" / "entidades_mx.csv"
    fake_cat.write_bytes(geo_catalog_path().read_bytes() + b"\n")
    with monkeypatch.context() as mp:
        mp.setattr(ed, "_ROOT", fake_root)
        mp.setattr(ed, "geo_catalog_path", lambda: fake_cat)
        with pytest.raises(ed.EpiDatasetError):
            ed.build_epi_dataset_v2(
                _DISEASE_ID, runs_root=runs_root, run_id=res1.run_id, raw_path=raw_csv
            )
    assert _snapshot_tree(run_dir) == snap_before

    # 4b) Corrupción en disco de inputs/entidades_mx.csv (aunque manifest.json siga intacto)
    cat_in_inputs = run_dir / "inputs" / "entidades_mx.csv"
    orig_cat_bytes = cat_in_inputs.read_bytes()
    cat_in_inputs.write_bytes(orig_cat_bytes + b"\n")
    tampered_cat_snap = _snapshot_tree(run_dir)
    with pytest.raises(ed.EpiDatasetError):
        ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    assert _snapshot_tree(run_dir) == tampered_cat_snap
    cat_in_inputs.write_bytes(orig_cat_bytes)

    # 5) Config efectiva distinta (expected_n_states alterado)
    orig_cfg = ed.load_config(_DISEASE_ID)
    altered_cfg = EpiDatasetConfig(
        disease_id=orig_cfg.disease_id,
        observation_lag_weeks=orig_cfg.observation_lag_weeks,
        exposure_source_id=orig_cfg.exposure_source_id,
        expected_n_states=31,
    )
    snap_restored = _snapshot_tree(run_dir)
    with monkeypatch.context() as mp:
        mp.setattr(ed, "load_config", lambda _d: altered_cfg)
        with pytest.raises(ed.EpiDatasetError):
            ed.build_epi_dataset_v2(
                _DISEASE_ID, runs_root=runs_root, run_id=res1.run_id, raw_path=raw_csv
            )
    assert _snapshot_tree(run_dir) == snap_restored


def test_foreign_context_and_incomplete_sealed_context_refused_intact(
    syn_env: dict[str, Any], tmp_path: Path
) -> None:
    """Contexto de otro padecimiento, residuos ajenos, symlinks o sellado incompleto se rehúsan."""
    catalog: GeoCatalog = syn_env["catalog"]
    raw_csv: Path = syn_env["raw_csv"]
    runs_root: Path = syn_env["runs_root"]

    # A) Contexto existente de Obesidad no puede reutilizarse para Sífilis con run_id forzado
    ob_raw = tmp_path / "ob" / "data_raw_Obesidad.csv"
    ob_raw.parent.mkdir()
    ob_df = _synthetic_raw_df(catalog)
    ob_df["Padecimiento"] = "Obesidad"
    ob_df.to_csv(ob_raw, index=False)
    ob_res = ed.build_epi_dataset_v2("obesidad", runs_root=runs_root, raw_path=ob_raw)
    ob_snap = _snapshot_tree(ob_res.run_dir)

    with pytest.raises(ed.EpiDatasetError):
        ed.build_epi_dataset_v2(
            _DISEASE_ID, runs_root=runs_root, run_id=ob_res.run_id, raw_path=raw_csv
        )
    assert _snapshot_tree(ob_res.run_dir) == ob_snap

    # B) Directorio ajeno con residuo de ejecución (run_manifest.json) no se pisa ni contamina
    foreign_run = runs_root / "foreign_exec_run"
    foreign_run.mkdir(parents=True)
    (foreign_run / "run_manifest.json").write_text(
        '{"schema": "run_manifest.v1"}', encoding="utf-8"
    )
    foreign_snap = _snapshot_tree(foreign_run)
    with pytest.raises(ed.EpiDatasetError):
        ed.build_epi_dataset_v2(
            _DISEASE_ID, runs_root=runs_root, run_id="foreign_exec_run", raw_path=raw_csv
        )
    assert _snapshot_tree(foreign_run) == foreign_snap

    # C) Contexto sellado (con manifest.json) pero con un insumo faltante falla cerrado sin recrear
    dm = orch.validate_data(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    ds_dir = runs_root / dm.dataset_id
    (ds_dir / "inputs" / "config_effective.json").unlink()
    incomplete_snap = _snapshot_tree(ds_dir)
    with pytest.raises(ed.EpiDatasetError):
        ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    assert _snapshot_tree(ds_dir) == incomplete_snap

    # D) Symlink en ruta de destino se rechaza sin seguirlo ni modificar el blanco
    outside_target = tmp_path / "outside_secret.csv"
    outside_target.write_text("intact\n", encoding="utf-8")
    sym_runs = tmp_path / "sym_runs"
    sym_ds = sym_runs / "sym_ctx" / "inputs"
    sym_ds.mkdir(parents=True)
    (sym_ds / _RAW_FILENAME).symlink_to(outside_target)
    sym_snap = _snapshot_tree(sym_runs / "sym_ctx")
    with pytest.raises(ed.EpiDatasetError):
        ed.build_epi_dataset_v2(
            _DISEASE_ID, runs_root=sym_runs, run_id="sym_ctx", raw_path=raw_csv
        )
    assert outside_target.read_text(encoding="utf-8") == "intact\n"
    assert _snapshot_tree(sym_runs / "sym_ctx") == sym_snap


def test_staging_contract_prestaged_readonly_and_atomic_no_replace_race(
    syn_env: dict[str, Any], tmp_path: Path
) -> None:
    """Insumo 0444 pre-stageado idéntico es NO-OP; carrera concurrente no reemplaza destino."""
    ed_io = importlib.import_module("epiforecast.data.epi_dataset_io")

    raw_csv: Path = syn_env["raw_csv"]
    runs_root: Path = syn_env["runs_root"]

    # 1) Pre-stage sólo del raw 0444 idéntico (sin manifest sellado): preserva inodo/modo/mtime
    partial_id = "sifilis_prestaged_0444"
    prestaged_inputs = runs_root / partial_id / "inputs"
    prestaged_inputs.mkdir(parents=True)
    prestaged_raw = prestaged_inputs / _RAW_FILENAME
    prestaged_raw.write_bytes(raw_csv.read_bytes())
    prestaged_raw.chmod(_READONLY_FILE_MODE)
    st_before = prestaged_raw.lstat()

    res = ed.build_epi_dataset_v2(
        _DISEASE_ID, runs_root=runs_root, run_id=partial_id, raw_path=raw_csv
    )
    st_after = prestaged_raw.lstat()
    assert (st_after.st_ino, st_after.st_mtime_ns, stat.S_IMODE(st_after.st_mode)) == (
        st_before.st_ino,
        st_before.st_mtime_ns,
        _READONLY_FILE_MODE,
    )
    assert (res.run_dir / "manifest.json").is_file()

    # 2) Carrera concurrente en write_exclusive_no_replace: otro escritor crea dst antes de link
    race_dir = tmp_path / "race"
    race_dir.mkdir()
    dst = race_dir / "target.csv"
    payload = b"nuevo_contenido\n"
    payload_sha = hashlib.sha256(payload).hexdigest()
    winner_bytes = b"ganador_concurrente_intacto\n"

    def _simulate_concurrent_writer(_tmp: Path, target: Path) -> None:
        target.write_bytes(winner_bytes)
        target.chmod(_READONLY_FILE_MODE)

    with pytest.raises(ed.EpiDatasetError):
        ed_io.write_exclusive_no_replace(
            dst,
            payload,
            payload_sha,
            error_cls=ed.EpiDatasetError,
            _before_link_hook=_simulate_concurrent_writer,
        )

    assert dst.read_bytes() == winner_bytes
    assert stat.S_IMODE(dst.lstat().st_mode) == _READONLY_FILE_MODE
    # Cero archivos temporales huérfanos
    assert [p.name for p in race_dir.iterdir()] == ["target.csv"]

    # 3) stage_file_idempotent directo sobre 0444 idéntico vs distinto
    assert (
        ed_io.stage_file_idempotent(dst, winner_bytes, error_cls=ed.EpiDatasetError)
        == "verified_noop"
    )
    with pytest.raises(ed.EpiDatasetError):
        ed_io.stage_file_idempotent(dst, b"otro\n", error_cls=ed.EpiDatasetError)
    assert dst.read_bytes() == winner_bytes


def test_srp_module_budget_and_fable_g1_g4_diagnostics(
    syn_env: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica límite SRP <=300 líneas en src y mejoras diagnósticas G1-G4 (Fable v1)."""
    ed_io = importlib.import_module("epiforecast.data.epi_dataset_io")
    ed_guard = importlib.import_module("epiforecast.data.epi_dataset_guard")

    # Regla SRP del repositorio: todo módulo src/ tocado/añadido <= 300 líneas
    for mod in (ed, ed_io, ed_guard):
        mod_path = Path(str(mod.__file__)).resolve()
        n_lines = len(mod_path.read_text(encoding="utf-8").splitlines())
        assert n_lines <= 300, f"{mod_path.name} excede 300 líneas ({n_lines})"

    catalog: GeoCatalog = syn_env["catalog"]
    raw_csv: Path = syn_env["raw_csv"]
    runs_root: Path = syn_env["runs_root"]

    # G1: mensaje ante divergencia de raw indica remedio explícito (runs_root limpio / _quarantine)
    res1 = ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    raw_v2 = tmp_path / "g1_raw" / _RAW_FILENAME
    raw_v2.parent.mkdir()
    _synthetic_raw_df(catalog, prev_year_acum=123).to_csv(raw_v2, index=False)
    with pytest.raises(ed.EpiDatasetError, match="runs/_quarantine"):
        ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_v2)

    # G2: .DS_Store o .tmp huérfano se identifican nominalmente manteniendo fail-closed
    ds_store_dir = runs_root / "ctx_ds_store"
    ds_store_dir.mkdir()
    (ds_store_dir / ".DS_Store").write_bytes(b"x")
    with pytest.raises(ed.EpiDatasetError, match=r"\.DS_Store"):
        ed.build_epi_dataset_v2(
            _DISEASE_ID, runs_root=runs_root, run_id="ctx_ds_store", raw_path=raw_csv
        )

    tmp_left_dir = runs_root / "ctx_tmp_left" / "inputs"
    tmp_left_dir.mkdir(parents=True)
    (tmp_left_dir / ".raw.123.deadbeef.tmp").write_bytes(b"partial")
    with pytest.raises(ed.EpiDatasetError, match=r"\.tmp"):
        ed.build_epi_dataset_v2(
            _DISEASE_ID, runs_root=runs_root, run_id="ctx_tmp_left", raw_path=raw_csv
        )

    # G3: run_manifest.json o jobs/ conserva indicación de cuarentena (runs/_quarantine/)
    exec_res_dir = runs_root / "ctx_exec_residue"
    exec_res_dir.mkdir()
    (exec_res_dir / "run_manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ed.EpiDatasetError, match="runs/_quarantine"):
        ed.build_epi_dataset_v2(
            _DISEASE_ID, runs_root=runs_root, run_id="ctx_exec_residue", raw_path=raw_csv
        )

    # G4: stage_dataset_run escribe manifest.json SIEMPRE al final aunque llegue primero en la tupla
    write_order: list[str] = []
    orig_writer = ed_io.write_exclusive_no_replace

    def _recording_writer(dst: Path, content: bytes, expected_digest: str, **kw: Any) -> None:
        write_order.append(dst.name)
        orig_writer(dst, content, expected_digest, **kw)

    monkeypatch.setattr(ed_io, "write_exclusive_no_replace", _recording_writer)
    man_bytes = json.dumps(
        {
            "run_id": "g4_order",
            "disease_id": _DISEASE_ID,
            "digests": {"dataset": "0" * 64},
        }
    ).encode("utf-8")
    csv_bytes = b"col\n1\n"
    raw_b = b"raw\n"
    reordered_artifacts = (
        ed_io.StagedArtifact("manifest.json", man_bytes, hashlib.sha256(man_bytes).hexdigest()),
        ed_io.StagedArtifact("inputs/r.csv", raw_b, hashlib.sha256(raw_b).hexdigest()),
        ed_io.StagedArtifact(
            "epi_dataset_v2.csv", csv_bytes, hashlib.sha256(csv_bytes).hexdigest()
        ),
    )
    action = ed_io.stage_dataset_run(
        run_dir=tmp_path / "g4_runs" / "g4_order",
        run_id="g4_order",
        disease_id=_DISEASE_ID,
        digests={"dataset": "0" * 64},
        artifacts=reordered_artifacts,
        error_cls=ed.EpiDatasetError,
    )
    assert action == "created"
    assert write_order == ["r.csv", "epi_dataset_v2.csv", "manifest.json"]
    _ = res1


def test_r1_interrupted_staging_recovery_completed_partial_manifest_last(
    syn_env: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fable R1: interrupción tras escribir artefactos deja manifest ausente y reingreso recupera."""
    ed_io = importlib.import_module("epiforecast.data.epi_dataset_io")
    orig_writer = ed_io.write_exclusive_no_replace

    # Parte A: stage_dataset_run interrumpido tras epi_dataset_v2.csv (con manifest primero en tupla)
    man_payload = {
        "run_id": "r1_partial_ctx",
        "disease_id": _DISEASE_ID,
        "digests": {"raw": "1" * 64, "dataset": "2" * 64},
    }
    man_bytes = json.dumps(man_payload, indent=2).encode("utf-8")
    raw_b = b"Anio,Semana\n2026,1\n"
    cfg_b = b'{"disease_id": "sifilis_adquirida_a51"}\n'
    ds_b = b"cve_ent,y_cases\n01,5\n"
    artifacts_reordered = (
        ed_io.StagedArtifact("manifest.json", man_bytes, hashlib.sha256(man_bytes).hexdigest()),
        ed_io.StagedArtifact("inputs/raw.csv", raw_b, hashlib.sha256(raw_b).hexdigest()),
        ed_io.StagedArtifact(
            "inputs/config_effective.json", cfg_b, hashlib.sha256(cfg_b).hexdigest()
        ),
        ed_io.StagedArtifact("epi_dataset_v2.csv", ds_b, hashlib.sha256(ds_b).hexdigest()),
    )
    ctx_dir = tmp_path / "r1_runs" / "r1_partial_ctx"

    def _crash_after_dataset_csv(
        dst: Path, content: bytes, expected_digest: str, **kw: Any
    ) -> None:
        orig_writer(dst, content, expected_digest, **kw)
        if dst.name == "epi_dataset_v2.csv":
            raise RuntimeError("interrupción simulada tras epi_dataset_v2.csv")

    monkeypatch.setattr(ed_io, "write_exclusive_no_replace", _crash_after_dataset_csv)
    with pytest.raises(RuntimeError, match="interrupción simulada"):
        ed_io.stage_dataset_run(
            run_dir=ctx_dir,
            run_id="r1_partial_ctx",
            disease_id=_DISEASE_ID,
            digests={"raw": "1" * 64, "dataset": "2" * 64},
            artifacts=artifacts_reordered,
            error_cls=ed.EpiDatasetError,
        )

    assert not (ctx_dir / "manifest.json").exists()
    assert (ctx_dir / "epi_dataset_v2.csv").is_file()
    # Sellar los artefactos previos en 0444 para demostrar que la recuperación NO los sobrescribe
    for rel in ("inputs/raw.csv", "inputs/config_effective.json", "epi_dataset_v2.csv"):
        (ctx_dir / rel).chmod(_READONLY_FILE_MODE)
    partial_snap = _snapshot_tree(ctx_dir)

    reentry_written: list[str] = []

    def _recording_writer(dst: Path, content: bytes, expected_digest: str, **kw: Any) -> None:
        reentry_written.append(dst.name)
        orig_writer(dst, content, expected_digest, **kw)

    monkeypatch.setattr(ed_io, "write_exclusive_no_replace", _recording_writer)
    action = ed_io.stage_dataset_run(
        run_dir=ctx_dir,
        run_id="r1_partial_ctx",
        disease_id=_DISEASE_ID,
        digests={"raw": "1" * 64, "dataset": "2" * 64},
        artifacts=artifacts_reordered,
        error_cls=ed.EpiDatasetError,
    )
    assert action == "completed_partial"
    assert reentry_written == ["manifest.json"]
    recovered_snap = _snapshot_tree(ctx_dir)
    for rel, meta_before in partial_snap.items():
        if meta_before[0] != "DIR":
            assert recovered_snap[rel] == meta_before
    assert (ctx_dir / "manifest.json").is_file()

    # Parte B: build_epi_dataset_v2 real interrumpido tras el primer artefacto (raw 0444) y reingreso
    raw_csv: Path = syn_env["raw_csv"]
    b_runs = tmp_path / "r1_builder_runs"
    calls = 0

    def _crash_after_first_file(
        dst: Path, content: bytes, expected_digest: str, **kw: Any
    ) -> None:
        nonlocal calls
        orig_writer(dst, content, expected_digest, **kw)
        calls += 1
        if calls == 1:
            raise RuntimeError("interrupción simulada tras primer insumo")

    monkeypatch.setattr(ed_io, "write_exclusive_no_replace", _crash_after_first_file)
    with pytest.raises(RuntimeError, match="primer insumo"):
        ed.build_epi_dataset_v2(
            _DISEASE_ID, runs_root=b_runs, run_id="r1_builder_ctx", raw_path=raw_csv
        )

    staged_first = b_runs / "r1_builder_ctx" / "inputs" / _RAW_FILENAME
    assert staged_first.is_file()
    assert not (b_runs / "r1_builder_ctx" / "manifest.json").exists()
    first_stat_before = staged_first.lstat()
    first_sha_before = _sha256(staged_first)

    monkeypatch.setattr(ed_io, "write_exclusive_no_replace", orig_writer)
    res_rec = ed.build_epi_dataset_v2(
        _DISEASE_ID, runs_root=b_runs, run_id="r1_builder_ctx", raw_path=raw_csv
    )
    assert (res_rec.run_dir / "manifest.json").is_file()
    first_stat_after = staged_first.lstat()
    assert (
        first_stat_after.st_ino,
        first_stat_after.st_mtime_ns,
        stat.S_IMODE(first_stat_after.st_mode),
        _sha256(staged_first),
    ) == (
        first_stat_before.st_ino,
        first_stat_before.st_mtime_ns,
        _READONLY_FILE_MODE,
        first_sha_before,
    )


def test_r2_precise_remedy_hint_quarantine_backup_invalidation_and_no_invented_cli(
    syn_env: dict[str, Any], tmp_path: Path
) -> None:
    """Fable R2: el remedio prioriza worktree/runs_root limpio, exige SHA-256 e invalida corridas."""
    catalog: GeoCatalog = syn_env["catalog"]
    raw_csv: Path = syn_env["raw_csv"]
    runs_root: Path = syn_env["runs_root"]

    res1 = ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_csv)
    snap_before = _snapshot_tree(res1.run_dir)

    raw_v2 = tmp_path / "r2_raw" / _RAW_FILENAME
    raw_v2.parent.mkdir()
    _synthetic_raw_df(catalog, prev_year_acum=777).to_csv(raw_v2, index=False)

    with pytest.raises(ed.EpiDatasetError) as exc_info:
        ed.build_epi_dataset_v2(_DISEASE_ID, runs_root=runs_root, raw_path=raw_v2)

    msg = str(exc_info.value)
    for required_fragment in (
        "worktree limpio",
        "runs_root",
        "runs/_quarantine/",
        "sin procesos activos",
        "SHA-256",
        "no borrar",
        "invalidadas",
    ):
        assert required_fragment in msg, f"Falta {required_fragment!r} en mensaje R2: {msg}"
    for forbidden_cli in ("--runs-root", "--dataset-id"):
        assert forbidden_cli not in msg
    assert _snapshot_tree(res1.run_dir) == snap_before
