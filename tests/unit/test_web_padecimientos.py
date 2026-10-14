"""E4: manifiesto `padecimientos` de knowledge.json (roster data-driven)."""

from __future__ import annotations

import json

import pytest

from epiforecast import catalog


def _sources_present() -> bool:
    return catalog._neuro_table_path().exists() and catalog._dengue_table_path().exists()


pytestmark = pytest.mark.skipif(not _sources_present(), reason="requiere artefactos de producción")


# Galería de la ronda W37: 333 neuro + 99 Dengue (las 4 regiones de Dengue salen).
_GALERIA = [{"p": "Depresión", "f": f"Depresión/x/{i}.png"} for i in range(333)] + [
    {"p": "Dengue", "f": f"dengue/x/{i}.png"} for i in range(99)
]


def _dashboard(raiz, items):
    (raiz / "Reports").mkdir(parents=True)
    (raiz / "Reports" / "index.html").write_text(
        f"<script>\nconst DATA = {json.dumps(items)};\n</script>\n", "utf-8"
    )
    return raiz


@pytest.fixture(scope="module")
def manifest(tmp_path_factory):
    from scripts.build_web_knowledge import build_padecimientos

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv(
            catalog.DASHBOARD_ENV, str(_dashboard(tmp_path_factory.mktemp("dash"), _GALERIA))
        )
        return build_padecimientos()


def test_sin_galeria_el_knowledge_no_se_construye(tmp_path, monkeypatch):
    """Sin inventario no hay conteo de gráficos: se aborta en vez de suponer uno."""
    from scripts.build_web_knowledge import build_padecimientos

    monkeypatch.setenv(catalog.DASHBOARD_ENV, str(tmp_path))
    with pytest.raises(SystemExit, match="gallery_items"):
        build_padecimientos()


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
    assert r["gallery_items"] == len(_GALERIA) == 432  # contado en la galería, no supuesto


def test_cada_padecimiento_completo(manifest):
    for p in manifest["padecimientos"]:
        assert p["cie"] and p["color"] and p["label"]
        assert p["aliases"]
        assert isinstance(p["n_models"], int) and p["n_models"] > 0
    dengue = next(p for p in manifest["padecimientos"] if p["id"] == "dengue")
    assert dengue["aggregate_national"] is False
    assert dengue["n_models"] == 99
