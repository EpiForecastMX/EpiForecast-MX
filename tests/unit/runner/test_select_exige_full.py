"""La selección sólo sale de un benchmark completo: un smoke cubre un único fold."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from epiforecast.runner import orchestrator
from epiforecast.runner.manifest import STATUS_SUCCEEDED, RunManifest

_RUN = "x_benchmark_smoke_abc"


@pytest.mark.parametrize("stage", ["smoke", "test"])
def test_select_rechaza_lo_que_no_sea_full(tmp_path, monkeypatch, stage):
    monkeypatch.setattr(
        orchestrator,
        "validate_data",
        lambda *_a, **_k: SimpleNamespace(dataset_id="d", disease_id="x"),
    )
    RunManifest(
        run_id=_RUN,
        disease_id="x",
        command="benchmark",
        dataset_id="d",
        stage=stage,
        status=STATUS_SUCCEEDED,
    ).write(tmp_path / _RUN)
    with pytest.raises(orchestrator.RunnerError, match="exige un benchmark 'full'"):
        orchestrator.run_selection("x", _RUN, runs_root=tmp_path)
