"""Activar en el ``--out`` de otro padecimiento borraría sus shards originales."""

from __future__ import annotations

import pytest
from scripts.publication_activate import exige_out_propio

from epiforecast.runner.artifact_identity import ArtifactValidationError


def test_un_out_nuevo_o_propio_pasa(tmp_path):
    exige_out_propio(tmp_path, "x")
    (tmp_path / "compile_a" / "x").mkdir(parents=True)
    exige_out_propio(tmp_path, "x")


def test_el_out_de_otro_padecimiento_se_rechaza(tmp_path):
    (tmp_path / "compile_a" / "obesidad").mkdir(parents=True)
    with pytest.raises(ArtifactValidationError, match="obesidad"):
        exige_out_propio(tmp_path, "x")
