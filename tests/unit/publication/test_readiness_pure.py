"""Contratos puros de identidad del preflight de publicación."""

import pytest
from scripts.publication_readiness import identity_digest

pytestmark = pytest.mark.unit


def test_el_mismo_id_en_los_dos_papeles_no_da_la_misma_huella():
    """Separación de contexto: confundir las variables tiene que notarse."""
    assert identity_digest("c7-staging", "X") != identity_digest("c7-production", "X")
