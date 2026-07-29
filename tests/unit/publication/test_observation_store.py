"""La verdad prospectiva portable no depende del ``runs/`` de una sola máquina."""

from __future__ import annotations

import hashlib
import json

import pytest

from epiforecast.publication import observation_store as store
from epiforecast.runner.artifact_identity import ArtifactValidationError


def _dataset(root, dataset_id="enfermedad_digest"):
    dataset = root / dataset_id
    inputs = dataset / "inputs"
    inputs.mkdir(parents=True)
    raw = inputs / "raw.csv"
    raw.write_text("x\n1\n", encoding="utf-8")
    (dataset / "dataset_manifest.json").write_text(
        json.dumps(
            {
                "schema": "dataset_manifest.v1",
                "dataset_id": dataset_id,
                "disease_id": "enfermedad",
                "code_commit": "a",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (dataset / "epi_dataset_v2.csv").write_text("x\n1\n", encoding="utf-8")
    return dataset, raw


def test_materializa_dataset_reporte_y_pdf_e_idempotente(tmp_path):
    dataset, _ = _dataset(tmp_path / "runs")
    pdf = tmp_path / "boletin.pdf"
    pdf.write_bytes(b"%PDF")
    report = {"schema": "prospective_week_dry_run.v1", "disease_id": "enfermedad"}

    first = store.materialize_observation(
        dataset,
        training_dataset_dir=dataset,
        disease_id="enfermedad",
        dataset_id=dataset.name,
        source_pdfs=[pdf],
        report=report,
        store_root=tmp_path / "store",
    )
    digest = store.tree_digest(first)
    second = store.materialize_observation(
        dataset,
        training_dataset_dir=dataset,
        disease_id="enfermedad",
        dataset_id=dataset.name,
        source_pdfs=[pdf],
        report=report,
        store_root=tmp_path / "store",
    )
    assert second == first
    assert store.tree_digest(second) == digest
    assert (first / store.SOURCE_DIR / pdf.name).read_bytes() == b"%PDF"
    assert json.loads((first / store.REPORT_FILE).read_bytes()) == report


def test_materializacion_existente_con_bytes_distintos_falla(tmp_path):
    dataset, _ = _dataset(tmp_path / "runs")
    pdf = tmp_path / "boletin.pdf"
    pdf.write_bytes(b"%PDF")
    kwargs = {
        "training_dataset_dir": dataset,
        "disease_id": "enfermedad",
        "dataset_id": dataset.name,
        "source_pdfs": [pdf],
        "store_root": tmp_path / "store",
    }
    store.materialize_observation(dataset, report={"v": 1}, **kwargs)
    with pytest.raises(ArtifactValidationError, match="bytes distintos"):
        store.materialize_observation(dataset, report={"v": 2}, **kwargs)


def test_repetir_ignora_solo_telemetria_volatil_del_manifest(tmp_path):
    dataset, _ = _dataset(tmp_path / "runs")
    pdf = tmp_path / "boletin.pdf"
    pdf.write_bytes(b"%PDF")
    kwargs = {
        "training_dataset_dir": dataset,
        "disease_id": "enfermedad",
        "dataset_id": dataset.name,
        "source_pdfs": [pdf],
        "report": {"v": 1},
        "store_root": tmp_path / "store",
    }
    destination = store.materialize_observation(dataset, **kwargs)
    manifest = json.loads((dataset / "dataset_manifest.json").read_bytes())
    manifest["created_at"] = "otra-fecha"
    manifest["code_commit"] = "otro-commit"
    (dataset / "dataset_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert store.materialize_observation(dataset, **kwargs) == destination


def test_effective_raw_se_resuelve_por_digest(tmp_path):
    dataset, raw = _dataset(tmp_path)
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    assert store.effective_raw_path(dataset, digest) == raw
    with pytest.raises(ArtifactValidationError, match="encontrados 0"):
        store.effective_raw_path(dataset, "0" * 64)


def test_resolver_prefiere_run_local_y_luego_portable(tmp_path):
    runs = tmp_path / "runs"
    local, _ = _dataset(runs)
    portable, _ = _dataset(tmp_path / "store" / "enfermedad")
    assert (
        store.resolve_observation_dir(
            "enfermedad", local.name, runs_root=runs, store_root=tmp_path / "store"
        )
        == local
    )
    local.rename(tmp_path / "movido")
    assert (
        store.resolve_observation_dir(
            "enfermedad", portable.name, runs_root=runs, store_root=tmp_path / "store"
        )
        == portable
    )


def test_resolver_training_desde_observacion_portable(tmp_path):
    portable, _ = _dataset(
        tmp_path / "store" / "enfermedad" / "obs" / store.TRAINING_DIR,
        dataset_id="training",
    )
    assert (
        store.resolve_training_dir(
            "enfermedad",
            "obs",
            "training",
            runs_root=tmp_path / "runs",
            store_root=tmp_path / "store",
        )
        == portable
    )


@pytest.mark.parametrize("value", ["../x", "/abs", "A", "", "x/y"])
def test_identidades_no_pueden_salir_de_la_sede(tmp_path, value):
    with pytest.raises(ArtifactValidationError, match="inválido"):
        store.observation_path(value, "dataset", store_root=tmp_path)
