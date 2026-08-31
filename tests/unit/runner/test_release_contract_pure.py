"""Contratos puros de identidad de un release."""

import pytest

from epiforecast.runner.release_contract import identity_payload

pytestmark = pytest.mark.unit


def test_la_identidad_declara_el_schema_del_release_que_describe():
    """R19.1.7: la identidad declara la forma del manifest que describe."""
    identidad = identity_payload(
        disease_id="x", chain={"dataset_id": "x_1"}, payloads={"a.csv": "0" * 64}
    )
    assert identidad["schema"] == "identity_payload.v2"
    assert identidad["release_schema"] == "release_manifest.v2"
