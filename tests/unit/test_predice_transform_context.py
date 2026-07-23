"""El adaptador legacy de predicción obtiene transforms del registry, no de disease literals."""

import pytest
from scripts.predice import _loader_disease_context

from epiforecast.registry import RegistryError


def test_obesidad_recibe_identidad_para_restaurar_rate_y_log() -> None:
    assert _loader_disease_context("E66") == "Obesidad"


def test_dengue_conserva_contexto_existente() -> None:
    assert _loader_disease_context("A97") == "Dengue"


def test_neuro_conserva_path_legacy() -> None:
    assert _loader_disease_context("Depresión") is None


@pytest.mark.parametrize("name", ["no_existe", "Obesdiad", " "])
def test_identidad_desconocida_o_vacia_falla_cerrado(name: str) -> None:
    with pytest.raises(RegistryError):
        _loader_disease_context(name)
