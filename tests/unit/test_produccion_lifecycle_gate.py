"""Fase 1 — lifecycle gate del selector productivo (``produccion_padecimiento``).

Contrato (plan §17 + docs/FASE_0_CONTENCION.md "Primer contrato de Fase 1"):
un padecimiento ``configured``/``trained`` (no ``published``) **no puede recrear** una
selección canónica ``reports/ProdDetails/produccion_<slug>.csv``, y **nunca** se etiqueta
con la política (p.ej. ``rolling_cv_v1``) sin haber corrido un OOS real.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.produccion_padecimiento import _PRELIMINAR_CRITERIO, resolve_destination

from epiforecast.registry import load_registry

# Registry sintético: un padecimiento por cada lifecycle, con la política mentirosa
# (rolling_cv_v1) en los no publicados para probar que el gate no la propaga.
_YAML = """
version: 1
perfiles:
  neuro: {cohorte_id: neuro, motor_rate: {prophet: true}}
  cronica: {cohorte_id: cronica, motor_rate: {prophet: true}}
padecimientos:
  - id: pub
    data_name: Publicado
    artifact_key: Publicado
    slug: publicado
    cie_codes: [P1]
    profile: neuro
    lifecycle: published
    selection_policy: legacy_neuro_2026
    eligible_engines: [prophet]
    training_engines: [prophet]
  - id: cfg
    data_name: Configurado
    artifact_key: Configurado
    slug: configurado
    cie_codes: [C1]
    profile: cronica
    lifecycle: configured
    selection_policy: rolling_cv_v1
    eligible_engines: [prophet]
    training_engines: [prophet]
  - id: trn
    data_name: Entrenado
    artifact_key: Entrenado
    slug: entrenado
    cie_codes: [T1]
    profile: cronica
    lifecycle: trained
    selection_policy: rolling_cv_v1
    eligible_engines: [prophet]
    training_engines: [prophet]
"""


@pytest.fixture
def reg(tmp_path: Path):
    p = tmp_path / "padecimientos.yaml"
    p.write_text(_YAML, encoding="utf-8")
    return load_registry(p)


def test_published_sin_adapter_esta_gated(reg, tmp_path):
    """Ownership: un published cuya política no tiene adapter en el genérico está gated."""
    d = reg.get("Publicado")  # legacy_neuro_2026 no está en _GENERIC_CANONICAL_POLICIES (vacío)
    assert resolve_destination(d, tmp_path, allow_preliminary=False) is None


def test_published_con_adapter_callable_registrado_escribe_canonico(reg, tmp_path, monkeypatch):
    """Con un adapter CALLABLE registrado, el published resuelve al canónico.

    (Registrar exige una función real, no una string en un allowlist.)
    """
    import pandas as pd
    import scripts.produccion_padecimiento as mod

    monkeypatch.setattr(
        mod, "_CANONICAL_ADAPTERS", {"legacy_neuro_2026": lambda d, root: pd.DataFrame()}
    )
    d = reg.get("Publicado")
    dest = mod.resolve_destination(d, tmp_path, allow_preliminary=False)
    assert dest is not None
    assert dest.canonical is True
    assert dest.path == tmp_path / "reports" / "ProdDetails" / "produccion_publicado.csv"
    assert dest.criterio == "legacy_neuro_2026"


def test_published_con_adapter_pero_allow_preliminary_es_none(reg, tmp_path, monkeypatch):
    """Gate completo en el resolver: published + allow_preliminary = None aunque haya adapter."""
    import pandas as pd
    import scripts.produccion_padecimiento as mod

    monkeypatch.setattr(
        mod, "_CANONICAL_ADAPTERS", {"legacy_neuro_2026": lambda d, root: pd.DataFrame()}
    )
    d = reg.get("Publicado")
    assert mod.resolve_destination(d, tmp_path, allow_preliminary=True) is None


@pytest.mark.parametrize("name", ["Configurado", "Entrenado"])
def test_no_publicado_sin_flag_esta_gated(reg, tmp_path, name):
    """Invariante central: un padecimiento no publicado NO puede recrear el canónico."""
    d = reg.get(name)
    assert resolve_destination(d, tmp_path, allow_preliminary=False) is None


@pytest.mark.parametrize("name", ["Configurado", "Entrenado"])
def test_no_publicado_con_flag_va_a_preliminar(reg, tmp_path, name):
    d = reg.get(name)
    dest = resolve_destination(d, tmp_path, allow_preliminary=True)
    assert dest is not None
    assert dest.canonical is False
    # NO es la ruta canónica.
    canonical = tmp_path / "reports" / "ProdDetails" / f"produccion_{d.slug}.csv"
    assert dest.path != canonical
    assert _PRELIMINAR_CRITERIO == "insample_cv_PRELIMINAR_NO_GO"
    assert "_preliminar_NO_GO" in dest.path.parts
    assert dest.path.name == f"produccion_{d.slug}_PRELIMINAR.csv"
    # NUNCA propaga la etiqueta de la política sin OOS real.
    assert dest.criterio == _PRELIMINAR_CRITERIO
    assert dest.criterio != d.selection_policy


def test_obesidad_real_gated_por_defecto(tmp_path):
    """Con el registry REAL: Obesidad (configured) está gated y no toca el canónico."""
    from epiforecast import registry

    d = registry.require("Obesidad")
    assert d.lifecycle != "published"
    assert resolve_destination(d, tmp_path, allow_preliminary=False) is None


def test_main_cli_gatea_sin_escribir(monkeypatch, tmp_path):
    """El CLI aborta (rc=2) para Obesidad y NO recrea produccion_obesidad.csv.

    ROOT se redirige a tmp_path para que un gate roto tampoco toque el repo real.
    """
    import scripts.produccion_padecimiento as mod

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    rc = mod.main(["--disease", "Obesidad"])
    assert rc == 2
    assert not (tmp_path / "reports" / "ProdDetails" / "produccion_obesidad.csv").exists()
