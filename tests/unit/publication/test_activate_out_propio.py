"""Activar nunca borra un shard original: ni el de otro padecimiento, ni el propio, ni con --check."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import publication_activate as activacion
from scripts.publication_activate import exige_out_propio, exige_sin_shard_previo

from epiforecast.runner.artifact_identity import ArtifactValidationError


def test_un_out_nuevo_o_propio_pasa(tmp_path):
    exige_out_propio(tmp_path, "x")
    (tmp_path / "compile_a" / "x").mkdir(parents=True)
    exige_out_propio(tmp_path, "x")


def test_el_out_de_otro_padecimiento_se_rechaza(tmp_path):
    (tmp_path / "compile_a" / "obesidad").mkdir(parents=True)
    with pytest.raises(ArtifactValidationError, match="obesidad"):
        exige_out_propio(tmp_path, "x")


def test_el_shard_propio_no_se_recompila_encima(tmp_path):
    exige_sin_shard_previo(tmp_path, "x")
    (tmp_path / "compile_a" / "x").mkdir(parents=True)
    with pytest.raises(ArtifactValidationError, match="original del paso semanal"):
        exige_sin_shard_previo(tmp_path, "x")


@pytest.fixture
def activacion_falsa(monkeypatch, tmp_path):
    """Activación sin release real: lo que se prueba es qué toca en disco."""

    def emite(_compilacion: object, raiz: Path) -> SimpleNamespace:
        raiz.mkdir(parents=True)
        (raiz / "shard_manifest.json").write_text(json.dumps({"mode": "public"}), "utf-8")
        return SimpleNamespace(root=raiz)

    puntero = SimpleNamespace(
        release_id="x_release", channels=("web",), digest=lambda: "d", active=True
    )
    (tmp_path / "puntero.json").write_text("{}", "utf-8")
    estado = SimpleNamespace(
        publishable=True,
        verdict="PASS",
        status=SimpleNamespace(observation_dataset_id="obs"),
    )
    disease = SimpleNamespace(id="x", lifecycle="published")
    monkeypatch.setattr(activacion, "_REPO", tmp_path)
    monkeypatch.setattr(activacion.registry, "require", lambda _i: disease)
    monkeypatch.setattr(activacion, "load_declared_status", lambda _i: estado)
    monkeypatch.setattr(activacion, "pointer_for", lambda *_a, **_k: puntero)
    monkeypatch.setattr(activacion, "declared_pointer_path", lambda _i: tmp_path / "puntero.json")
    monkeypatch.setattr(activacion, "read_pointer", lambda _r: puntero)
    monkeypatch.setattr(activacion, "write_active_pointer", lambda *_a: None)
    monkeypatch.setattr(activacion, "check_activation", lambda *_a: None)
    monkeypatch.setattr(
        activacion, "compile_release", lambda **_k: SimpleNamespace(label="etiqueta")
    )
    monkeypatch.setattr(activacion, "emit_shards", emite)
    monkeypatch.setattr(activacion, "diff_trees", lambda *_a: [])
    out = tmp_path / "runs" / "publication" / "x"
    original = out / "compile_a" / "x" / "x_release"
    original.mkdir(parents=True)
    (original / "shard.txt").write_text("original", "utf-8")
    return out, original


def test_check_no_toca_el_shard_original(activacion_falsa):
    out, original = activacion_falsa
    resumen = activacion.activate("x", out=out, write_pointer=False)
    assert (original / "shard.txt").read_text("utf-8") == "original"
    assert sorted(p.name for p in out.iterdir()) == ["compile_a"]
    assert resumen["shard_root"] is None


def test_activar_sobre_el_shard_propio_falla_sin_borrarlo(activacion_falsa):
    out, original = activacion_falsa
    with pytest.raises(ArtifactValidationError, match="original del paso semanal"):
        activacion.activate("x", out=out, write_pointer=True)
    assert (original / "shard.txt").is_file()


def test_reemplazar_shards_es_explicito(activacion_falsa):
    out, original = activacion_falsa
    activacion.activate("x", out=out, write_pointer=True, reemplazar_shards=True)
    assert not (original / "shard.txt").exists()
    assert (out / "compile_b" / "shard_manifest.json").is_file()


def test_reemplazar_shards_no_aplica_con_check():
    with pytest.raises(SystemExit):
        activacion.main(["x", "--out", "runs/x", "--check", "--reemplazar-shards"])
