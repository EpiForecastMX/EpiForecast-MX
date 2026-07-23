"""Fase 1 P0 — ownership/policy + E2E del selector genérico (``produccion_padecimiento``).

Contrato: el genérico NO reproduce las políticas legacy ni pisa artefactos de selectores
dedicados (``produccion_dengue.csv``); solo escribe un CANÓNICO cuando hay un adapter
explícito registrado, y un PRELIMINAR (esquema/etiqueta honestos) para no publicados.
Incluye E2E de escritura y la regresión de case de nombre de archivo (Linux/CI).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import scripts.produccion_padecimiento as mod

from epiforecast.registry import load_registry

# Registry con un published cuyo slug es 'dengue' (artefacto dedicado) + política Dengue.
_YAML_DENGUE_SLUG = """
version: 1
perfiles:
  conteos: {cohorte_id: conteos, motor_rate: {prophet: false, deepar: true}}
padecimientos:
  - id: dengue_fake
    data_name: DengueFake
    artifact_key: DengueFake
    slug: dengue
    cie_codes: [Z9]
    profile: conteos
    lifecycle: published
    selection_policy: legacy_dengue_2026
    eligible_engines: [prophet]
    training_engines: [prophet]
"""


def _write_completo(root: Path, engine_prefix: str, artifact_key: str, engine_dir: str) -> None:
    """Escribe un ``<Prefix>_<key>_completo.csv`` mínimo (schema que lee _load_engine_metrics)."""
    d = root / "models" / engine_dir / artifact_key
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{engine_prefix}_{artifact_key}_completo.csv").write_text(
        "Entidad,sexo,smape,mase,rmse\n"
        "Nacional,incrementos_total,10.0,0.5,1.0\n"
        "Aguascalientes,incrementos_hombres,20.0,0.8,2.0\n",
        encoding="utf-8",
    )


# ── Ownership: artefacto dedicado reservado ──
def test_slug_dengue_reservado_incluso_con_adapter(tmp_path, monkeypatch):
    reg = load_registry_from_text(tmp_path, _YAML_DENGUE_SLUG)
    # Aun registrando la política como adapter, produccion_dengue.csv está reservado.
    monkeypatch.setattr(mod, "_GENERIC_CANONICAL_POLICIES", frozenset({"legacy_dengue_2026"}))
    d = reg.get("DengueFake")
    assert mod.resolve_destination(d, tmp_path, allow_preliminary=False) is None


def load_registry_from_text(tmp_path: Path, text: str):
    p = tmp_path / "padecimientos.yaml"
    p.write_text(text, encoding="utf-8")
    return load_registry(p)


# ── Engine filename case (regresión Linux/CI) ──
@pytest.mark.parametrize(
    "engine,expected",
    [
        ("prophet", "Prophet"),
        ("deepar", "Deepar"),
        ("ensemble", "Ensemble"),
        ("stacking", "Stacking"),
        ("nbglm", "Nbglm"),
    ],
)
def test_engine_file_prefix_case_real(engine, expected):
    assert mod._engine_file_prefix(engine) == expected


def test_engine_file_prefix_difiere_del_display_en_deepar_nbglm():
    # El display (DeepAR/NBGLM) construiría un nombre inexistente en un FS case-sensitive.
    assert mod._engine_file_prefix("deepar") != mod._ENGINE_CAP["deepar"]
    assert mod._engine_file_prefix("nbglm") != mod._ENGINE_CAP["nbglm"]


# ── E2E: preliminar (no publicado) ──
def test_e2e_preliminar_escribe_schema_honesto(tmp_path, monkeypatch):
    """Obesidad (configured) + --allow-preliminary escribe a _preliminar_NO_GO con
    criterio honesto y sin recrear el canónico. Incluye un fixture Deepar_ (case real)."""
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_completo(tmp_path, "Prophet", "Obesidad", "prophet")
    _write_completo(tmp_path, "Deepar", "Obesidad", "deepar")  # case real: Deepar_, no DeepAR_

    rc = mod.main(["--disease", "Obesidad", "--allow-preliminary"])
    assert rc == 0

    canonical = tmp_path / "reports" / "ProdDetails" / "produccion_obesidad.csv"
    preliminar = (
        tmp_path
        / "reports"
        / "ProdDetails"
        / "_preliminar_NO_GO"
        / "produccion_obesidad_PRELIMINAR.csv"
    )
    assert not canonical.exists()  # invariante: no toca el canónico
    assert preliminar.exists()

    df = pd.read_csv(preliminar)
    assert set(df["criterio_seleccion"]) == {"insample_cv_PRELIMINAR_NO_GO"}
    assert "rolling_cv_v1" not in set(df["criterio_seleccion"].astype(str))
    # El fixture Deepar_ SE cargó (case fix): aparece la columna smape_deepar.
    assert "smape_deepar" in df.columns
    assert "deepar" in set(df["motores_evaluados"].iloc[0].split(","))
    assert list(df.columns[:3]) == ["padecimiento", "entidad", "sexo"]


# ── E2E: published dedicado → gated, no escribe ──
def test_e2e_dengue_published_gated_no_escribe(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    # Aunque existieran métricas, el gate corta antes de escribir.
    _write_completo(tmp_path, "Prophet", "Dengue", "prophet")
    rc = mod.main(["--disease", "Dengue"])
    assert rc == 2
    assert not (tmp_path / "reports" / "ProdDetails" / "produccion_dengue.csv").exists()


def test_e2e_allow_preliminary_en_published_es_error(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    rc = mod.main(["--disease", "Dengue", "--allow-preliminary"])
    assert rc == 2
    assert not (tmp_path / "reports" / "ProdDetails" / "produccion_dengue.csv").exists()
