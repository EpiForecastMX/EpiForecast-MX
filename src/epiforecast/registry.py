"""Registry central de padecimientos — cargador tipado de ``config/padecimientos.yaml``.

Única fuente de verdad de identidad, perfil (traits POR MOTOR), extracción, selección y
publicación. Cargado AISLADO del ``conf`` global (evita contaminar el namespace plano de
OmegaConf). Lazy + cacheado + CWD-independiente + path inyectable para pruebas.

Reemplaza los literales dispersos: ``constants.CONDITIONS/NEURO_CONDITIONS`` y
``utils.cohorts.is_neuro/is_count_log_cohort/filter_neuro`` pasan a ser shims respaldados
por este registry (EPIC 2), preservando los bordes de ``None``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, cast
import unicodedata

from omegaconf import OmegaConf

__all__ = [
    "RegistryError",
    "Disease",
    "Profile",
    "get_registry",
    "load_registry",
    "require",
    "try_get",
    "canonical",
    "ascii_key",
    "slug",
    "display",
    "cie",
    "cie_map",
    "aliases",
    "all_diseases",
    "names",
    "production_cohort",
    "standalone_members",
    "published_members",
    "profile",
    "trait",
    "trait_or",
    "is_rate",
    "engines",
    "prophet_grid_key",
    "deepar_grid_key",
    "web",
    "cohorte_id",
    "validate_config",
]


class RegistryError(ValueError):
    """Config de padecimientos inválida (duplicados, claves desconocidas, referencia rota)."""


# Claves permitidas (rechazo de desconocidas = fail-fast).
_PROFILE_KEYS = frozenset(
    {
        "cohorte_id",
        "unidad",
        "prophet_log_transform",
        "prophet_covid_holidays",
        "ensemble_covid_holidays",
        "prophet_cv_weights",
        "prophet_enso",
        "nbglm_enso",
        "ensemble_clamp",
        "stacking_clamp",
        "deepar_short_series",
        "fallback_regional",
        "excluir_outliers",
        "invert_log_predict",
        "motor_rate",
        "rate_scale",
    }
)
_DISEASE_KEYS = frozenset(
    {
        "id",
        "data_name",
        "artifact_key",
        "slug",
        "display_name",
        "cie_codes",
        "aliases",
        "profile",
        "batch",
        "extraction_group",
        "exposure_source_id",
        "lifecycle",
        "channels",
        "training_engines",
        "eligible_engines",
        "selection_policy",
        "prophet_grid_key",
        "deepar_grid_key",
        "aggregate_national",
        "gallery_enabled",
        "web",
        "artifact_source",
    }
)
_LIFECYCLES = frozenset({"configured", "trained", "published"})

# ── Backends de artefactos (C7.1) ──────────────────────────────────────────────────────────────
# De DÓNDE salen los modelos de un padecimiento. Existir un directorio NO es evidencia: antes de
# C7.1 el doctor daba verde a Obesidad por 790 PKL preliminares del carril viejo que no son sus
# modelos finales. Cada backend declara su propia prueba de identidad.
BACKEND_LEGACY = "legacy_models"  # models/<engine>/<artifact_key>/ (los 4 publicados)
BACKEND_RUNNER_RUNS = "runner_runs"  # refit+forecast sellados bajo runs_root; SOLO para `trained`
BACKEND_RUNNER_RELEASE = (
    "runner_release"  # release_manifest.v1 restaurable; exigido por `published`
)
ARTIFACT_BACKENDS = frozenset({BACKEND_LEGACY, BACKEND_RUNNER_RUNS, BACKEND_RUNNER_RELEASE})
_RUNNER_RUNS_KEYS = frozenset(
    {"backend", "refit_run_id", "forecast_run_id", "policy_digest", "final_selection_digest"}
)
_RUNNER_RELEASE_KEYS = frozenset({"backend", "release_id"})
_BACKEND_KEYS: dict[str, frozenset[str]] = {
    BACKEND_LEGACY: frozenset({"backend"}),
    BACKEND_RUNNER_RUNS: _RUNNER_RUNS_KEYS,
    BACKEND_RUNNER_RELEASE: _RUNNER_RELEASE_KEYS,
}
# Matriz lifecycle × backend. `runner_runs` describe artefactos locales sin sede distribuible:
# vale para el estado en que se demuestra el entrenamiento, no para publicar. Publicar exige un
# release restaurable. `legacy_models` es el carril histórico y admite cualquier estado.
_BACKEND_LIFECYCLES: dict[str, frozenset[str]] = {
    BACKEND_LEGACY: _LIFECYCLES,
    BACKEND_RUNNER_RUNS: frozenset({"trained"}),
    BACKEND_RUNNER_RELEASE: frozenset({"trained", "published"}),
}


@dataclass(frozen=True, slots=True)
class ArtifactSource:
    """De dónde salen los modelos de un padecimiento. Inmutable y validado al cargar (C7.1)."""

    backend: str
    refit_run_id: str | None = None
    forecast_run_id: str | None = None
    policy_digest: str | None = None
    final_selection_digest: str | None = None
    release_id: str | None = None

    @property
    def is_legacy(self) -> bool:
        return self.backend == BACKEND_LEGACY

    def to_dict(self) -> dict[str, str]:
        return {
            k: v
            for k, v in (
                ("backend", self.backend),
                ("refit_run_id", self.refit_run_id),
                ("forecast_run_id", self.forecast_run_id),
                ("policy_digest", self.policy_digest),
                ("final_selection_digest", self.final_selection_digest),
                ("release_id", self.release_id),
            )
            if v is not None
        }


_BOOL_PROFILE_KEYS = _PROFILE_KEYS - {
    "cohorte_id",
    "unidad",
    "motor_rate",
    "rate_scale",
}


def _fold(s: str) -> str:
    """NFKD-fold + lower + strip (índice de aliases; NO para construir rutas)."""
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().strip().lower()


@dataclass(frozen=True)
class Profile:
    cohorte_id: str
    unidad: str
    rate_scale: float | None
    fallback_regional: bool
    excluir_outliers: bool
    invert_log_predict: bool
    motor_rate: Mapping[str, bool]
    _raw: Mapping[str, Any]  # para trait(engine, key) con fallback f"{engine}_{key}" -> key


@dataclass(frozen=True)
class Disease:
    id: str
    data_name: str
    artifact_key: str
    slug: str
    display_name: str
    cie_codes: tuple[str, ...]
    aliases: tuple[str, ...]
    profile_name: str
    batch: str
    extraction_group: str
    lifecycle: str
    channels: tuple[str, ...]
    training_engines: tuple[str, ...]
    eligible_engines: tuple[str, ...]
    selection_policy: str
    prophet_grid_key: str | None
    deepar_grid_key: str | None
    aggregate_national: bool
    gallery_enabled: bool
    web: Mapping[str, Any]
    profile: Profile
    exposure_source_id: str | None = None  # solo EpiDatasetV2 lo exige; legacy = None
    # De dónde salen los modelos (C7.1). Sin declarar = backend legacy.
    artifact_source: ArtifactSource = field(
        default_factory=lambda: ArtifactSource(backend=BACKEND_LEGACY)
    )

    @property
    def artifact_backend(self) -> str:
        return self.artifact_source.backend


@dataclass(frozen=True)
class _Registry:
    diseases: tuple[Disease, ...]
    _by_id: Mapping[str, Disease]
    _alias_index: Mapping[str, str]  # folded alias -> disease id

    def get(self, key: str | None) -> Disease | None:
        if key is None:
            return None
        did = self._alias_index.get(_fold(key))
        return self._by_id.get(did) if did else None


def _default_config_path() -> Path:
    packaged = Path(__file__).resolve().parents[2] / "config" / "padecimientos.yaml"
    return packaged if packaged.exists() else Path("config/padecimientos.yaml")


def _build_profiles(raw: Mapping[str, Any]) -> dict[str, Profile]:
    profiles: dict[str, Profile] = {}
    for name, body in (raw.get("perfiles") or {}).items():
        unknown = set(body) - _PROFILE_KEYS
        if unknown:
            raise RegistryError(f"perfil '{name}': claves desconocidas {sorted(unknown)}")
        invalid_bools = sorted(
            key for key in _BOOL_PROFILE_KEYS if key in body and type(body[key]) is not bool
        )
        if invalid_bools:
            raise RegistryError(
                f"perfil '{name}': traits booleanos con tipo inválido {invalid_bools}"
            )
        raw_motor_rate = body.get("motor_rate", {})
        if not isinstance(raw_motor_rate, Mapping):
            raise RegistryError(f"perfil '{name}': motor_rate debe ser un mapping")
        invalid_motor_rate = sorted(
            str(engine) for engine, enabled in raw_motor_rate.items() if type(enabled) is not bool
        )
        if invalid_motor_rate:
            raise RegistryError(
                f"perfil '{name}': motor_rate debe usar booleanos; motores inválidos "
                f"{invalid_motor_rate}"
            )
        motor_rate = {str(engine): enabled for engine, enabled in raw_motor_rate.items()}
        raw_rate_scale = body.get("rate_scale")
        if isinstance(raw_rate_scale, bool):
            raise RegistryError(f"perfil '{name}': rate_scale debe ser numérico")
        try:
            rate_scale = float(raw_rate_scale) if raw_rate_scale is not None else None
        except (TypeError, ValueError) as exc:
            raise RegistryError(f"perfil '{name}': rate_scale debe ser numérico") from exc
        if rate_scale is not None and (not math.isfinite(rate_scale) or rate_scale <= 0):
            raise RegistryError(f"perfil '{name}': rate_scale debe ser finito y positivo")
        if any(motor_rate.values()) and rate_scale is None:
            raise RegistryError(
                f"perfil '{name}': rate_scale finito y positivo es obligatorio "
                "cuando un motor usa tasa"
            )
        profiles[name] = Profile(
            cohorte_id=str(body["cohorte_id"]),
            unidad=str(body.get("unidad", "tasa")),
            rate_scale=rate_scale,
            fallback_regional=bool(body.get("fallback_regional", False)),
            excluir_outliers=bool(body.get("excluir_outliers", False)),
            invert_log_predict=bool(body.get("invert_log_predict", False)),
            motor_rate=motor_rate,
            _raw=dict(body),
        )
    return profiles


def _build_artifact_source(body: Mapping[str, Any], lifecycle: str) -> ArtifactSource:
    """Valida ``artifact_source`` fail-closed. Sin declararlo, el backend es el legacy."""
    disease_id = body.get("id")
    raw = body.get("artifact_source")
    if raw is None:
        if lifecycle == "published":  # los publicados actuales viven en el carril legacy
            return ArtifactSource(backend=BACKEND_LEGACY)
        return ArtifactSource(backend=BACKEND_LEGACY)
    if not isinstance(raw, Mapping):
        raise RegistryError(f"'{disease_id}': artifact_source debe ser un mapeo")

    backend = raw.get("backend")
    if not isinstance(backend, str) or backend not in ARTIFACT_BACKENDS:
        raise RegistryError(
            f"'{disease_id}': artifact_source.backend desconocido {backend!r} "
            f"(esperado {sorted(ARTIFACT_BACKENDS)})"
        )
    esperadas = _BACKEND_KEYS[backend]
    faltan, sobran = esperadas - set(raw), set(raw) - esperadas
    if faltan or sobran:
        raise RegistryError(
            f"'{disease_id}': artifact_source de {backend!r} con claves faltantes "
            f"{sorted(faltan)} y desconocidas {sorted(sobran)}"
        )
    for clave, valor in raw.items():
        # Un valor no-string (int, bool, lista, None) es una identidad inválida, no algo a coercer.
        if not isinstance(valor, str):
            raise RegistryError(
                f"'{disease_id}': artifact_source.{clave} debe ser string, no "
                f"{type(valor).__name__}"
            )
        if not valor.strip():
            raise RegistryError(f"'{disease_id}': artifact_source.{clave} vacío")
    permitidos = _BACKEND_LIFECYCLES[backend]
    if lifecycle not in permitidos:
        raise RegistryError(
            f"'{disease_id}': backend {backend!r} no es admisible con lifecycle {lifecycle!r} "
            f"(permitidos {sorted(permitidos)})"
        )
    if (
        lifecycle == "published"
        and backend != BACKEND_RUNNER_RELEASE
        and backend != BACKEND_LEGACY
    ):
        raise RegistryError(
            f"'{disease_id}': lifecycle=published exige {BACKEND_LEGACY!r} o "
            f"{BACKEND_RUNNER_RELEASE!r}"
        )
    return ArtifactSource(**{str(k): str(v) for k, v in raw.items()})


def _build_disease(body: Mapping[str, Any], profiles: Mapping[str, Profile]) -> Disease:
    unknown = set(body) - _DISEASE_KEYS
    if unknown:
        raise RegistryError(
            f"padecimiento '{body.get('id')}': claves desconocidas {sorted(unknown)}"
        )
    pname = str(body["profile"])
    if pname not in profiles:
        raise RegistryError(f"padecimiento '{body['id']}': perfil '{pname}' no existe")
    lifecycle = str(body.get("lifecycle", "configured"))
    if lifecycle not in _LIFECYCLES:
        raise RegistryError(f"padecimiento '{body['id']}': lifecycle '{lifecycle}' inválido")
    return Disease(
        id=str(body["id"]),
        data_name=str(body["data_name"]),
        artifact_key=str(body["artifact_key"]),
        slug=str(body["slug"]),
        display_name=str(body.get("display_name", body["data_name"])),
        cie_codes=tuple(str(c) for c in body.get("cie_codes", [])),
        aliases=tuple(str(a) for a in body.get("aliases", [])),
        profile_name=pname,
        batch=str(body.get("batch", "standalone")),
        extraction_group=str(body.get("extraction_group", "")),
        lifecycle=lifecycle,
        channels=tuple(str(c) for c in body.get("channels", [])),
        training_engines=tuple(str(e) for e in body.get("training_engines", [])),
        eligible_engines=tuple(str(e) for e in body.get("eligible_engines", [])),
        selection_policy=str(body.get("selection_policy", "")),
        prophet_grid_key=(body.get("prophet_grid_key") or None),
        deepar_grid_key=(body.get("deepar_grid_key") or None),
        aggregate_national=bool(body.get("aggregate_national", False)),
        gallery_enabled=bool(body.get("gallery_enabled", True)),
        web=dict(body.get("web", {})),
        artifact_source=_build_artifact_source(body, lifecycle),
        profile=profiles[pname],
        exposure_source_id=(body.get("exposure_source_id") or None),
    )


def load_registry(path: str | Path | None = None) -> _Registry:
    """Carga y valida el registry desde ``path`` (o el default). NO cachea (para pruebas)."""
    p = Path(path) if path is not None else _default_config_path()
    raw = cast("dict[str, Any]", OmegaConf.to_container(OmegaConf.load(p), resolve=True))
    profiles = _build_profiles(raw)
    diseases = tuple(_build_disease(b, profiles) for b in (raw.get("padecimientos") or []))

    by_id: dict[str, Disease] = {}
    alias_index: dict[str, str] = {}
    seen_slugs: dict[str, str] = {}
    seen_artifacts: dict[str, str] = {}
    seen_cie: dict[str, str] = {}
    for d in diseases:
        if d.id in by_id:
            raise RegistryError(f"id duplicado: {d.id}")
        by_id[d.id] = d
        if d.slug in seen_slugs:
            raise RegistryError(f"slug duplicado '{d.slug}' ({d.id} y {seen_slugs[d.slug]})")
        seen_slugs[d.slug] = d.id
        if d.artifact_key in seen_artifacts:
            raise RegistryError(f"artifact_key duplicado '{d.artifact_key}'")
        seen_artifacts[d.artifact_key] = d.id
        # índice de aliases: id, slug, data_name, display, artifact_key, cie codes, aliases
        for token in (
            d.id,
            d.slug,
            d.data_name,
            d.display_name,
            d.artifact_key,
            *d.cie_codes,
            *d.aliases,
        ):
            f = _fold(token)
            if not f:
                continue
            if f in alias_index and alias_index[f] != d.id:
                raise RegistryError(f"alias duplicado '{token}' ({d.id} y {alias_index[f]})")
            alias_index[f] = d.id
        for c in d.cie_codes:
            if c in seen_cie and seen_cie[c] != d.id:
                raise RegistryError(f"cie duplicado '{c}'")
            seen_cie[c] = d.id
    return _Registry(diseases=diseases, _by_id=by_id, _alias_index=alias_index)


_CACHE: _Registry | None = None


def get_registry() -> _Registry:
    """Registry cacheado (default path). Usar ``load_registry(path)`` en pruebas."""
    global _CACHE
    if _CACHE is None:
        _CACHE = load_registry()
    return _CACHE


def reset_cache() -> None:
    global _CACHE
    _CACHE = None


# ── API pública ──
def require(key: str) -> Disease:
    d = get_registry().get(key)
    if d is None:
        raise RegistryError(f"padecimiento desconocido: {key!r}")
    return d


def try_get(key: str | None) -> Disease | None:
    return get_registry().get(key)


def canonical(key: str | None) -> str | None:
    d = get_registry().get(key)
    return d.data_name if d else None


def ascii_key(key: str) -> str:
    return require(key).artifact_key


def slug(key: str) -> str:
    return require(key).slug


def display(key: str) -> str:
    return require(key).display_name


def cie(key: str) -> str | None:
    d = get_registry().get(key)
    return d.cie_codes[0] if d and d.cie_codes else None


def cie_map() -> dict[str, str]:
    """``{cie_primario: data_name}`` — reemplazo de ``constants.CONDITIONS``."""
    return {d.cie_codes[0]: d.data_name for d in get_registry().diseases if d.cie_codes}


def aliases() -> dict[str, str]:
    """``{alias_folded: id}``."""
    return dict(get_registry()._alias_index)


def all_diseases(lifecycle: str | None = None) -> list[Disease]:
    ds = list(get_registry().diseases)
    return [d for d in ds if lifecycle is None or d.lifecycle == lifecycle]


def names(published_only: bool = False) -> list[str]:
    return [
        d.data_name
        for d in get_registry().diseases
        if not published_only or d.lifecycle == "published"
    ]


def production_cohort() -> list[str]:
    """Lote 'General': neuro publicado. Reemplaza ``constants.NEURO_CONDITIONS``."""
    return [
        d.data_name
        for d in get_registry().diseases
        if d.batch == "General" and d.lifecycle == "published"
    ]


def standalone_members(published_only: bool = True) -> list[str]:
    return [
        d.data_name
        for d in get_registry().diseases
        if d.batch != "General" and (not published_only or d.lifecycle == "published")
    ]


def published_members(channel: str | None = None) -> list[str]:
    out = []
    for d in get_registry().diseases:
        if d.lifecycle != "published":
            continue
        if channel is None or channel in d.channels:
            out.append(d.data_name)
    return out


def profile(key: str) -> Profile:
    return require(key).profile


def cohorte_id(key: str | None) -> str | None:
    d = get_registry().get(key)
    return d.profile.cohorte_id if d else None


def trait(disease: str, engine: str, key: str, default: bool = False) -> bool:
    """Trait POR MOTOR. ``rate`` sale de ``motor_rate[engine]``; el resto busca
    ``f"{engine}_{key}"`` y luego ``key`` en el perfil (fallback), si no ``default``."""
    prof = require(disease).profile
    if key == "rate":
        return bool(prof.motor_rate.get(engine, default))
    raw = prof._raw
    for candidate in (f"{engine}_{key}", key):
        if candidate in raw:
            return bool(raw[candidate])
    return default


def trait_or(disease: str | None, engine: str, key: str, default: bool = False) -> bool:
    """Como ``trait`` pero seguro para ``None``/desconocido: devuelve ``default``.

    Los gates de modelo lo usan con ``default`` = el predicado de cohorte viejo, para
    quedar byte-idénticos en los padecimientos vigentes (y desconocidos) y respetar el
    perfil de un padecimiento nuevo (p.ej. Obesidad: log on, short_series off)."""
    d = get_registry().get(disease)
    if d is None:
        return default
    return trait(d.data_name, engine, key, default)


def is_rate(disease: str, engine: str) -> bool:
    return trait(disease, engine, "rate")


def engines(disease: str, eligible_only: bool = True) -> tuple[str, ...]:
    d = require(disease)
    return d.eligible_engines if eligible_only else d.training_engines


def prophet_grid_key(disease: str) -> str | None:
    return require(disease).prophet_grid_key


def deepar_grid_key(disease: str) -> str | None:
    return require(disease).deepar_grid_key


def web(key: str) -> Mapping[str, Any]:
    return require(key).web


def validate_config(reg: _Registry | None = None) -> list[str]:
    """Problemas de config (vacío = OK). No lanza; para CI/doctor."""
    reg = reg or get_registry()
    problems: list[str] = []
    for d in reg.diseases:
        if (
            d.artifact_key != _fold(d.artifact_key).title().replace(" ", "_")
            and " " not in d.artifact_key
        ):
            pass  # artifact_key libre; no forzamos formato
        for e in d.eligible_engines:
            if e not in d.training_engines:
                problems.append(f"{d.id}: motor elegible '{e}' no está en training_engines")
        if not d.cie_codes:
            problems.append(f"{d.id}: sin cie_codes")
    return problems
