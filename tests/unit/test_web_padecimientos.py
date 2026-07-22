"""E4: manifiesto `padecimientos` de knowledge.json (roster data-driven)."""

from __future__ import annotations

import pytest

from epiforecast import catalog


def _sources_present() -> bool:
    return catalog._neuro_table_path().exists() and catalog._dengue_table_path().exists()


pytestmark = pytest.mark.skipif(not _sources_present(), reason="requiere artefactos de producción")


@pytest.fixture(scope="module")
def manifest():
    from scripts.build_web_knowledge import build_padecimientos

    return build_padecimientos()


def test_solo_published_obesidad_invisible(manifest):
    ids = {p["id"] for p in manifest["padecimientos"]}
    assert ids == {"depresion", "parkinson", "alzheimer", "dengue"}
    assert "obesidad" not in ids  # configured -> invisible


def test_conteos_canonicos_no_inflados(manifest):
    r = manifest["rosters"]
    assert r["total_series"] == 432  # no 435
    assert r["por_cohorte"] == {"neuro": 333, "dengue": 99}
    assert r["national_aggregators"] == 333  # solo los 3 neuro suman
    assert r["n_padecimientos"] == 4
    assert r["gallery_items"] == 444


def test_cada_padecimiento_completo(manifest):
    for p in manifest["padecimientos"]:
        assert p["cie"] and p["color"] and p["label"]
        assert p["aliases"]
        assert isinstance(p["n_models"], int) and p["n_models"] > 0
    dengue = next(p for p in manifest["padecimientos"] if p["id"] == "dengue")
    assert dengue["aggregate_national"] is False
    assert dengue["n_models"] == 99
