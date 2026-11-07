"""C7.7 — vista pública derivada: integridad del shard y métricas fuera de muestra.

Sin datos reales (CI corre en clon limpio con presupuesto exacto de skips): shards sintéticos.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from scripts import publication_view as vista

from epiforecast.publication.compiler import POINT_ONLY_SUFFIX
from epiforecast.publication.status import VERDICT_FAIL
from epiforecast.runner.artifact_identity import ArtifactValidationError


def _shard(raiz: Path, *, modo: str = "public") -> Path:
    archivos = {"web/series.csv": b"a,b\n1,2\n", "web/manifest.json": b"{}"}
    for rel, datos in archivos.items():
        (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
        (raiz / rel).write_bytes(datos)
    manifiesto = {
        "mode": modo,
        "disease_id": "obesidad",
        "release_id": "obesidad_release_x",
        "files": {rel: hashlib.sha256(d).hexdigest() for rel, d in archivos.items()},
    }
    (raiz / "shard_manifest.json").write_text(json.dumps(manifiesto), encoding="utf-8")
    return raiz


def test_un_shard_integro_se_acepta(tmp_path):
    m = vista._verifica_shard(_shard(tmp_path), "obesidad", "obesidad_release_x")
    assert set(m["files"]) == {"web/series.csv", "web/manifest.json"}


def test_un_byte_alterado_se_rechaza(tmp_path):
    raiz = _shard(tmp_path)
    (raiz / "web/series.csv").write_bytes(b"a,b\n1,3\n")
    with pytest.raises(ArtifactValidationError, match="digest"):
        vista._verifica_shard(raiz, "obesidad", "obesidad_release_x")


def test_un_shard_candidate_no_alimenta_la_vista(tmp_path):
    with pytest.raises(ArtifactValidationError, match="modo"):
        vista._verifica_shard(_shard(tmp_path, modo="candidate"), "obesidad", "obesidad_release_x")


def test_otro_release_se_rechaza(tmp_path):
    with pytest.raises(ArtifactValidationError, match="release"):
        vista._verifica_shard(_shard(tmp_path), "obesidad", "obesidad_release_y")


def test_smape_misma_formula_que_el_runner():
    from epiforecast.runner.evaluation import smape_percent

    y = pd.Series([10.0, 0.0, 5.0, 20.0])
    f = pd.Series([12.0, 0.0, 4.0, 10.0])
    assert vista._smape(y, f) == pytest.approx(smape_percent(y.to_numpy(), f.to_numpy()))


def test_los_nombres_cubren_estados_regiones_y_nacional():
    nombres = vista._nombres()
    assert nombres[("nacional", "mx")] == "Nacional"
    assert nombres[("estado", "09")] == "Ciudad de México"
    assert sum(1 for nivel, _ in nombres if nivel == "estado") == 32
    assert sum(1 for nivel, _ in nombres if nivel == "region") == 4


def test_la_emision_sale_del_manifiesto_del_pronostico(tmp_path):
    (tmp_path / "forecast").mkdir()
    m = {"command": "forecast", "created_at": "2026-07-25T04:55:28.423845+00:00"}
    (tmp_path / "forecast" / "run_manifest.json").write_text(json.dumps(m), encoding="utf-8")
    assert vista.emision_del_pronostico(tmp_path) == m["created_at"]
    m["command"] = "benchmark"
    (tmp_path / "forecast" / "run_manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match="comando"):
        vista.emision_del_pronostico(tmp_path)


def test_sin_semanas_observadas_el_cruce_conserva_sus_columnas():
    """Un release recién emitido (0/4) no tiene cruce: una lista vacía seleccionaría columnas."""
    vacio = pd.DataFrame(columns=["epi_year", "epi_week", "y_cases", "yhat_cases"])
    assert list(vista.tras_origen(vacio, (2026, 41)).columns) == list(vacio.columns)
    filas = pd.DataFrame({"epi_year": [2026, 2026], "epi_week": [41, 42]})
    assert vista.tras_origen(filas, (2026, 41))["epi_week"].tolist() == [42]


class _Avance:
    weeks_required = 4
    weeks_available = 1
    observation_dataset_id = "obs"

    @staticmethod
    def progress_label() -> str:
        return "Validación prospectiva en curso (1/4 semanas)"


def _vista_sintetica(monkeypatch, tmp_path, *, publicable: bool = True) -> Path:
    """Shard compilado en 0/4 y estado vigente en 1/4, sin datos reales."""
    shard = tmp_path / "shard"
    (shard / "web").mkdir(parents=True)
    (shard / "web" / "manifest.json").write_text(
        json.dumps(
            {
                "origin": [2026, 41],
                "horizon_weeks": 1,
                "publication_label": "Validación prospectiva en curso (0/4 semanas)",
                "uncertainty_label": "puntual",
                "engines": ["motor"],
                "models": 64,
                "products": 111,
            }
        ),
        "utf-8",
    )
    fila = "nacional,mx,general,2026,42,2026-10-18,motor,5\n"
    (shard / "web" / "series.csv").write_text(
        "geography_level,geography_id,sex,epi_year,epi_week,ds,engine,yhat_cases\n" + fila + "",
        "utf-8",
    )
    obs = tmp_path / "obs" / "x" / "obs"
    obs.mkdir(parents=True)
    (obs / "products.csv").write_text(
        "geography_level,geography_id,sex,epi_year,epi_week,ds,y_cases,observed\n"
        "nacional,mx,general,2026,42,2026-10-18,7,True\n",
        "utf-8",
    )
    estado = SimpleNamespace(
        publishable=publicable,
        verdict="INCOMPLETE" if publicable else VERDICT_FAIL,
        release_id="x_release",
        status=_Avance(),
        progress_label=_Avance.progress_label,
    )
    disease = SimpleNamespace(id="x", lifecycle="published", display_name="X", web={})
    verificado = SimpleNamespace(chain={}, uncertainty_available=False)
    monkeypatch.setattr(vista.registry, "require", lambda _i: disease)
    monkeypatch.setattr(vista, "load_declared_status", lambda _i: estado)
    monkeypatch.setattr(vista, "_verifica_shard", lambda *_a: {"files": {}})
    monkeypatch.setattr(vista, "verify_bundle", lambda _b: verificado)
    monkeypatch.setattr(vista, "emision_del_pronostico", lambda _b: "2026-11-07T00:00:00+00:00")
    monkeypatch.setattr(vista, "OBSERVACIONES", tmp_path / "obs")
    monkeypatch.setattr(vista, "_nombres", lambda: {("nacional", "mx"): "Nacional"})
    return shard


def test_la_etiqueta_sale_del_estado_vigente_no_del_shard(monkeypatch, tmp_path):
    shard = _vista_sintetica(monkeypatch, tmp_path)
    v = vista.build_view("x", shard)
    assert v["publication_label"].startswith("Validación prospectiva en curso (1/4 semanas)")
    assert v["publication_label"].endswith(POINT_ONLY_SUFFIX)


def test_un_fail_no_genera_vista_publica(monkeypatch, tmp_path):
    shard = _vista_sintetica(monkeypatch, tmp_path, publicable=False)
    with pytest.raises(ArtifactValidationError, match="FAIL"):
        vista.build_view("x", shard)
