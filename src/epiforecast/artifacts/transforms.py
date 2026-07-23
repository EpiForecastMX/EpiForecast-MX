"""Typed forward/inverse contracts for a future Artifact Envelope."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import math
from typing import Any, Self

import numpy as np
import numpy.typing as npt

from epiforecast import registry

TRANSFORM_CONTRACT_SCHEMA_VERSION = 1


class TransformContractError(ValueError):
    """The transform contract or its numeric inputs are invalid."""


class TargetSpace(StrEnum):
    COUNT = "count"
    RATE = "rate"
    TRANSFORMED = "transformed"


class TransformStep(StrEnum):
    RATE_PER_EXPOSURE = "rate_per_exposure"
    LOG1P = "log1p"
    EXPM1 = "expm1"
    RATE_TO_COUNT = "rate_to_count"


_FORWARD_STEPS = frozenset({TransformStep.RATE_PER_EXPOSURE, TransformStep.LOG1P})
_INVERSE_STEPS = frozenset({TransformStep.EXPM1, TransformStep.RATE_TO_COUNT})
_INVERSE_OF = {
    TransformStep.RATE_PER_EXPOSURE: TransformStep.RATE_TO_COUNT,
    TransformStep.LOG1P: TransformStep.EXPM1,
}
_SERIALIZED_KEYS = {
    "schema_version",
    "disease_id",
    "engine_id",
    "source_space",
    "target_space",
    "forward_steps",
    "inverse_steps",
    "rate_scale",
}


def _numeric_array(values: npt.ArrayLike, *, label: str) -> npt.NDArray[np.float64]:
    try:
        out = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise TransformContractError(f"{label} no es numérico") from exc
    if out.size == 0:
        raise TransformContractError(f"{label} está vacío")
    if not np.isfinite(out).all():
        raise TransformContractError(f"{label} contiene NaN o infinito")
    return out.copy()


def _exposure_for(
    values: npt.NDArray[np.float64], exposure: npt.ArrayLike | None
) -> npt.NDArray[np.float64]:
    if exposure is None:
        raise TransformContractError("la transformación de tasa requiere exposure")
    raw = _numeric_array(exposure, label="exposure")
    try:
        out = np.broadcast_to(raw, values.shape)
    except ValueError as exc:
        raise TransformContractError(
            f"exposure con shape {raw.shape} no es compatible con target {values.shape}"
        ) from exc
    if (out <= 0).any():
        raise TransformContractError("exposure debe ser estrictamente positivo")
    return np.asarray(out, dtype=np.float64)


@dataclass(frozen=True, slots=True)
class TransformContract:
    """Immutable transform contract resolved for one disease and engine."""

    disease_id: str
    engine_id: str
    source_space: TargetSpace
    target_space: TargetSpace
    forward_steps: tuple[TransformStep, ...]
    inverse_steps: tuple[TransformStep, ...]
    rate_scale: float | None
    schema_version: int = TRANSFORM_CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != TRANSFORM_CONTRACT_SCHEMA_VERSION:
            raise TransformContractError(
                f"schema_version no soportado: {self.schema_version}; "
                f"esperado {TRANSFORM_CONTRACT_SCHEMA_VERSION}"
            )
        if not self.disease_id or self.disease_id != self.disease_id.strip().lower():
            raise TransformContractError("disease_id debe ser canónico, no vacío y minúsculo")
        if not self.engine_id or self.engine_id != self.engine_id.strip().lower():
            raise TransformContractError("engine_id debe ser canónico, no vacío y minúsculo")
        if self.source_space is not TargetSpace.COUNT:
            raise TransformContractError("TransformContract v1 solo admite source_space='count'")
        if any(step not in _FORWARD_STEPS for step in self.forward_steps):
            raise TransformContractError("forward_steps contiene una transformación inversa")
        if any(step not in _INVERSE_STEPS for step in self.inverse_steps):
            raise TransformContractError("inverse_steps contiene una transformación forward")
        if len(set(self.forward_steps)) != len(self.forward_steps):
            raise TransformContractError("forward_steps contiene transformaciones duplicadas")

        expected_inverse = tuple(_INVERSE_OF[step] for step in reversed(self.forward_steps))
        if self.inverse_steps != expected_inverse:
            raise TransformContractError(
                f"inverse_steps {self.inverse_steps!r} no invierte forward_steps; "
                f"esperado {expected_inverse!r}"
            )

        space: TargetSpace = TargetSpace.COUNT
        for step in self.forward_steps:
            if step is TransformStep.RATE_PER_EXPOSURE:
                if space is not TargetSpace.COUNT:
                    raise TransformContractError("rate_per_exposure debe aplicarse sobre count")
                space = TargetSpace.RATE
            elif step is TransformStep.LOG1P:
                if space not in (TargetSpace.COUNT, TargetSpace.RATE):
                    raise TransformContractError("log1p debe ser la última transformación forward")
                space = TargetSpace.TRANSFORMED
        if self.target_space is not space:
            raise TransformContractError(
                f"target_space={self.target_space!s} no coincide con la cadena ({space!s})"
            )

        if self.requires_exposure:
            if self.rate_scale is None or not math.isfinite(self.rate_scale):
                raise TransformContractError("rate_scale finito es obligatorio para tasa")
            if self.rate_scale <= 0:
                raise TransformContractError("rate_scale debe ser estrictamente positivo")
        elif self.rate_scale is not None:
            raise TransformContractError("rate_scale debe ser null cuando no se modela tasa")

    @property
    def requires_exposure(self) -> bool:
        """Whether numeric forward/inverse operations require population/exposure."""
        return TransformStep.RATE_PER_EXPOSURE in self.forward_steps

    def apply_forward(
        self, values: npt.ArrayLike, *, exposure: npt.ArrayLike | None = None
    ) -> npt.NDArray[np.float64]:
        """Transform non-negative counts into the model target space."""
        out = _numeric_array(values, label="target count")
        if (out < 0).any():
            raise TransformContractError("target count no puede contener negativos")
        exp: npt.NDArray[np.float64] | None = None
        if self.requires_exposure:
            exp = _exposure_for(out, exposure)

        for step in self.forward_steps:
            if step is TransformStep.RATE_PER_EXPOSURE:
                assert exp is not None and self.rate_scale is not None
                out = out / exp * self.rate_scale
            elif step is TransformStep.LOG1P:
                out = np.log1p(out)
        if not np.isfinite(out).all():
            raise TransformContractError("forward produjo NaN o infinito")
        return np.asarray(out, dtype=np.float64)

    def apply_inverse(
        self, values: npt.ArrayLike, *, exposure: npt.ArrayLike | None = None
    ) -> npt.NDArray[np.float64]:
        """Invert model-space values back to absolute counts."""
        out = _numeric_array(values, label="model target")
        exp: npt.NDArray[np.float64] | None = None
        if self.requires_exposure:
            exp = _exposure_for(out, exposure)

        for step in self.inverse_steps:
            if step is TransformStep.EXPM1:
                out = np.expm1(out)
            elif step is TransformStep.RATE_TO_COUNT:
                assert exp is not None and self.rate_scale is not None
                out = out * exp / self.rate_scale
        if not np.isfinite(out).all():
            raise TransformContractError("inverse produjo NaN o infinito")
        return np.asarray(out, dtype=np.float64)

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-compatible representation."""
        return {
            "schema_version": self.schema_version,
            "disease_id": self.disease_id,
            "engine_id": self.engine_id,
            "source_space": self.source_space.value,
            "target_space": self.target_space.value,
            "forward_steps": [step.value for step in self.forward_steps],
            "inverse_steps": [step.value for step in self.inverse_steps],
            "rate_scale": self.rate_scale,
        }

    def to_json(self) -> str:
        """Serialize deterministically for hashing and future envelope embedding."""
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    def digest(self) -> str:
        """SHA-256 of the canonical JSON representation."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        """Parse a strict canonical representation."""
        unknown = set(raw) - _SERIALIZED_KEYS
        missing = _SERIALIZED_KEYS - set(raw)
        if unknown or missing:
            raise TransformContractError(
                f"representación inválida; faltantes={sorted(missing)}, "
                f"desconocidas={sorted(unknown)}"
            )
        try:
            return cls(
                schema_version=int(raw["schema_version"]),
                disease_id=str(raw["disease_id"]),
                engine_id=str(raw["engine_id"]),
                source_space=TargetSpace(str(raw["source_space"])),
                target_space=TargetSpace(str(raw["target_space"])),
                forward_steps=tuple(TransformStep(str(v)) for v in raw["forward_steps"]),
                inverse_steps=tuple(TransformStep(str(v)) for v in raw["inverse_steps"]),
                rate_scale=(None if raw["rate_scale"] is None else float(raw["rate_scale"])),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, TransformContractError):
                raise
            raise TransformContractError("representación de TransformContract inválida") from exc

    @classmethod
    def from_json(cls, raw: str) -> Self:
        """Parse a strict JSON object."""
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TransformContractError("JSON de TransformContract inválido") from exc
        if not isinstance(decoded, dict):
            raise TransformContractError("TransformContract JSON debe ser un objeto")
        return cls.from_dict(decoded)


def resolve_transform_contract(disease: str, engine: str) -> TransformContract:
    """Resolve a contract from registry traits, without disease-specific branches.

    The engine must be explicitly declared for training and its rate flag must exist in
    the resolved profile.  Missing configuration is an error, never an identity fallback.
    """
    if not isinstance(engine, str) or engine != engine.strip().lower() or not engine:
        raise TransformContractError(f"engine_id no canónico: {engine!r}")
    try:
        spec = registry.require(disease)
    except (registry.RegistryError, TypeError) as exc:
        raise TransformContractError(f"padecimiento desconocido: {disease!r}") from exc
    if engine not in spec.training_engines:
        raise TransformContractError(
            f"motor '{engine}' no está declarado para entrenamiento de '{spec.id}'"
        )
    if engine not in spec.profile.motor_rate:
        raise TransformContractError(
            f"perfil '{spec.profile_name}' no declara motor_rate.{engine}"
        )

    forward: list[TransformStep] = []
    uses_rate = bool(spec.profile.motor_rate[engine])
    if uses_rate:
        forward.append(TransformStep.RATE_PER_EXPOSURE)
    if registry.trait(spec.data_name, engine, "log_transform", default=False):
        forward.append(TransformStep.LOG1P)

    if forward and forward[-1] is TransformStep.LOG1P:
        target_space = TargetSpace.TRANSFORMED
    elif uses_rate:
        target_space = TargetSpace.RATE
    else:
        target_space = TargetSpace.COUNT

    rate_scale_raw = getattr(spec.profile, "rate_scale", None) if uses_rate else None
    rate_scale = None if rate_scale_raw is None else float(rate_scale_raw)
    forward_tuple = tuple(forward)
    inverse = tuple(_INVERSE_OF[step] for step in reversed(forward_tuple))
    return TransformContract(
        disease_id=spec.id,
        engine_id=engine,
        source_space=TargetSpace.COUNT,
        target_space=target_space,
        forward_steps=forward_tuple,
        inverse_steps=inverse,
        rate_scale=rate_scale,
    )
