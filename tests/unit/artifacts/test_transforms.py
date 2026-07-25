"""TransformContract v1: matrix, numeric roundtrip and fail-closed resolution.

Mapa de cobertura tras C7.1 (Acción 6.2). Obesidad salió del carril legacy, así que la cobertura
del resolver se ancla en Depresión y Dengue, que tienen la misma forma de contrato. Sus motores
REALES están cubiertos por el runner; no se vuelve a meter Obesidad en fixtures de
``ProphetForecaster`` legacy para "recuperar" cobertura:

| contrato | cobertura autoritativa |
| --- | --- |
| resolver de transformaciones legacy | este módulo, con Depresión y Dengue |
| Obesidad rechazada por el carril legacy | ``test_obesidad_ya_no_resuelve_contratos_legacy`` (aquí) y ``test_produccion_ownership.py::test_el_carril_legacy_rechaza_a_obesidad`` |
| perfiles Prophet count/rate del runner | ``tests/unit/runner/test_prophet_engine.py`` |
| tasa + exposición vuelve a casos | ``test_harness.py::test_round_trip_de_tasa_vuelve_a_casos`` |
| serialización final Prophet tasa | ``test_final_models.py::test_round_trip_prophet_tasa`` |
| cadena real de Obesidad con ambos perfiles | ``tests/integration/test_disease_run_gate.py`` |
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json

import numpy as np
import pytest

from epiforecast.artifacts.transforms import (
    TargetSpace,
    TransformContract,
    TransformContractError,
    TransformStep,
    resolve_transform_contract,
)


def test_perfil_de_tasa_resuelve_rate_log_sin_branch_por_enfermedad():
    # Depresión (perfil neuro) tiene la MISMA forma que tenía obesidad_cronica: prophet/deepar en
    # tasa, ensemble/stacking en conteos. Obesidad dejó de entrenar por el carril legacy en C7.1,
    # así que la cobertura de resolve_transform_contract se ancla aquí.
    contract = resolve_transform_contract("Depresión", "prophet")
    assert contract.disease_id == "depresion"
    assert contract.target_space is TargetSpace.TRANSFORMED
    assert contract.forward_steps == (
        TransformStep.RATE_PER_EXPOSURE,
        TransformStep.LOG1P,
    )
    assert contract.inverse_steps == (
        TransformStep.EXPM1,
        TransformStep.RATE_TO_COUNT,
    )
    assert contract.rate_scale == 100_000
    assert contract.requires_exposure


@pytest.mark.parametrize("engine", ["ensemble", "stacking"])
def test_ensemble_stacking_conservan_conteos(engine):
    contract = resolve_transform_contract("depresion", engine)
    assert contract.target_space is TargetSpace.COUNT
    assert contract.forward_steps == ()
    assert contract.inverse_steps == ()
    assert contract.rate_scale is None
    assert not contract.requires_exposure


def test_deepar_declara_tasa():
    contract = resolve_transform_contract("F32", "deepar")
    assert contract.target_space is TargetSpace.RATE
    assert contract.forward_steps == (TransformStep.RATE_PER_EXPOSURE,)
    assert contract.inverse_steps == (TransformStep.RATE_TO_COUNT,)


def test_prophet_aplica_tasa_antes_de_log1p():
    contract = resolve_transform_contract("Depresión", "prophet")
    transformed = contract.apply_forward([496.0], exposure=[126_014_024.0])
    np.testing.assert_allclose(transformed, [0.33189533899263346], rtol=1e-14)


def test_dengue_prophet_es_conteo_log_sin_exposure():
    contract = resolve_transform_contract("Dengue", "prophet")
    assert contract.target_space is TargetSpace.TRANSFORMED
    assert contract.forward_steps == (TransformStep.LOG1P,)
    assert contract.inverse_steps == (TransformStep.EXPM1,)
    assert not contract.requires_exposure


@pytest.mark.parametrize(
    ("disease", "engine"),
    [
        ("Depresión", "prophet"),
        ("Dengue", "prophet"),
        ("Depresión", "deepar"),
        ("Depresión", "ensemble"),
        ("Depresión", "stacking"),
    ],
)
def test_forward_inverse_roundtrip(disease, engine):
    contract = resolve_transform_contract(disease, engine)
    counts = np.array([0.0, 2.0, 496.0, 12_064.0])
    exposure = np.array([1_000_000.0, 900_000.0, 126_014_024.0, 130_000_000.0])
    transformed = contract.apply_forward(
        counts, exposure=exposure if contract.requires_exposure else None
    )
    restored = contract.apply_inverse(
        transformed, exposure=exposure if contract.requires_exposure else None
    )
    np.testing.assert_allclose(restored, counts, rtol=1e-12, atol=1e-12)


def test_rate_requiere_exposure_en_forward_e_inverse():
    contract = resolve_transform_contract("Depresión", "prophet")
    with pytest.raises(TransformContractError, match="requiere exposure"):
        contract.apply_forward([1.0])
    with pytest.raises(TransformContractError, match="requiere exposure"):
        contract.apply_inverse([1.0])


@pytest.mark.parametrize("exposure", [0, -1, np.nan, np.inf])
def test_exposure_debe_ser_finito_y_positivo(exposure):
    contract = resolve_transform_contract("Depresión", "deepar")
    with pytest.raises(TransformContractError, match="exposure"):
        contract.apply_forward([1.0], exposure=exposure)


def test_exposure_vector_debe_ser_broadcastable():
    contract = resolve_transform_contract("Depresión", "deepar")
    with pytest.raises(TransformContractError, match="shape"):
        contract.apply_forward([1.0, 2.0], exposure=[1.0, 2.0, 3.0])


def test_count_forward_rechaza_negativos():
    contract = resolve_transform_contract("Depresión", "ensemble")
    with pytest.raises(TransformContractError, match="negativos"):
        contract.apply_forward([-1.0])


def test_contrato_es_inmutable():
    contract = resolve_transform_contract("Depresión", "prophet")
    with pytest.raises(FrozenInstanceError):
        contract.engine_id = "deepar"  # type: ignore[misc]


def test_json_y_digest_son_deterministas_y_roundtrip():
    first = resolve_transform_contract("Depresión", "prophet")
    second = resolve_transform_contract("depre", "prophet")  # alias del mismo padecimiento
    assert first.to_json() == second.to_json()
    assert first.digest() == second.digest()
    assert len(first.digest()) == 64
    assert TransformContract.from_json(first.to_json()) == first
    assert json.loads(first.to_json())["disease_id"] == "depresion"


def test_json_rechaza_claves_desconocidas():
    raw = resolve_transform_contract("Depresión", "prophet").to_dict()
    raw["inventada"] = True
    with pytest.raises(TransformContractError, match="desconocidas"):
        TransformContract.from_dict(raw)


def test_inverse_debe_corresponder_al_forward():
    with pytest.raises(TransformContractError, match="no invierte"):
        TransformContract(
            disease_id="obesidad",
            engine_id="prophet",
            source_space=TargetSpace.COUNT,
            target_space=TargetSpace.TRANSFORMED,
            forward_steps=(TransformStep.LOG1P,),
            inverse_steps=(TransformStep.RATE_TO_COUNT,),
            rate_scale=None,
        )


def test_target_space_debe_corresponder_a_la_cadena():
    with pytest.raises(TransformContractError, match="no coincide"):
        TransformContract(
            disease_id="obesidad",
            engine_id="ensemble",
            source_space=TargetSpace.COUNT,
            target_space=TargetSpace.RATE,
            forward_steps=(),
            inverse_steps=(),
            rate_scale=None,
        )


@pytest.mark.parametrize(
    ("disease", "engine"),
    [
        ("no_existe", "prophet"),
        ("Obesidad", "motor_fantasma"),
        ("Obesidad", "Prophet"),
    ],
)
def test_resolver_falla_cerrado_en_disease_o_engine_desconocido(disease, engine):
    with pytest.raises(TransformContractError):
        resolve_transform_contract(disease, engine)


def test_obesidad_ya_no_resuelve_contratos_legacy():
    """C7.1: Obesidad no declara motores legacy, así que el carril viejo no puede resolverla.

    Es la consecuencia buscada de vaciar `training_engines`: ningún PKL preliminar ni ningún flujo
    legacy puede reclamar a Obesidad. Sus transformaciones reales las gobierna el runner
    (`contracts.log1p_transform` / `rate_log1p_transform`), no este resolutor.
    """
    for engine in ("prophet", "deepar", "ensemble", "stacking"):
        with pytest.raises(TransformContractError, match="no está declarado para entrenamiento"):
            resolve_transform_contract("Obesidad", engine)
