"""F2/C3 — gate de INTEGRACIÓN: disease_run sobre E66 real (identidad dataset_id vs run_id).

validate-data materializa runs/<dataset_id>/ (DatasetManifest, intacto). benchmark crea un dir
run_id DISTINTO que referencia el dataset_id y NO sobrescribe el manifest del dataset. Requiere
datos gitignored (DVC); skip si faltan. Marcado ``integration`` → excluido de CI.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from epiforecast.data import epi_dataset as ed
from epiforecast.runner import orchestrator as orch
from epiforecast.runner.manifest import DATASET_MANIFEST_SCHEMA, DatasetManifest

pytestmark = pytest.mark.integration

_ROOT = ed._ROOT
_RAW = _ROOT / "data" / "raw" / "data_raw_Obesidad.csv"
_INEGI = _ROOT / "data" / "utils" / "inegi.csv"


def _require_data() -> None:
    if not _RAW.exists() or not _INEGI.exists():
        pytest.skip("datos locales E66/INEGI no disponibles (DVC no restaurado)")


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    _require_data()
    return tmp_path_factory.mktemp("runs")


@pytest.fixture(scope="module")
def dataset(root):
    return orch.validate_data("Obesidad", runs_root=root)


def test_gate_dataset_manifest(dataset, root):
    assert dataset.schema == DATASET_MANIFEST_SCHEMA
    assert dataset.counts == {"base": 64, "derived": 47, "products": 111}
    assert set(dataset.digests) == {"raw", "exposure", "config", "dataset"}
    dsdir = root / dataset.dataset_id
    assert (dsdir / "dataset_manifest.json").exists()
    assert len(pd.read_csv(dsdir / "products.csv")) == 72_483  # 111 × 653
    assert len(json.loads((dsdir / "lineage.json").read_text(encoding="utf-8"))) == 47
    assert {a.schema for a in dataset.artifacts} == {"epi_dataset_v2", "products.v1", "lineage.v1"}
    assert all(a.validated for a in dataset.artifacts)


def test_gate_benchmark_dir_distinto_no_clobber(dataset, root):
    man = orch.run_command("Obesidad", "benchmark", stage="smoke", runs_root=root)
    # run_id es un dir DISTINTO al del dataset y lo referencia.
    assert man.run_id != dataset.dataset_id
    assert man.dataset_id == dataset.dataset_id
    assert man.stage == "smoke" and man.policy_digest and man.engines == ["seasonal_naive_lag52"]
    # Sin adapter en C3.0 → fail-closed rc=2 (honesto).
    assert man.status == "failed" and man.exit_code == 2
    # validate-data permanece INTACTO tras el benchmark fallido.
    back = DatasetManifest.read(root / dataset.dataset_id)
    assert back.counts == {"base": 64, "derived": 47, "products": 111}
    assert all(a.validated for a in back.artifacts)


def test_gate_run_id_distinto_por_stage(dataset, root):
    smoke = orch.run_command("Obesidad", "benchmark", stage="smoke", runs_root=root)
    full = orch.run_command("Obesidad", "benchmark", stage="full", runs_root=root)
    assert smoke.run_id != full.run_id  # distinto stage → distinto run_id
