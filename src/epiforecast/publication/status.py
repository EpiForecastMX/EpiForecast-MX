"""C7.6-PUBLICATION-STATUS — el estado prospectivo como CONTRATO, no como frase en un plan.

El release es inmutable y el gate prospectivo también: se congelaron antes de ver una sola semana de
verdad. Lo que cambia cada boletín es el **resultado observado**, y hasta ahora ese resultado vivía
sólo en el plan operativo. Publicar así mostraría un pronóstico puntual correcto omitiendo la
condición bajo la que se autorizó publicarlo, que es peor que no publicarlo (R74-P0).

Tres identidades separadas, y ninguna contamina a la otra:

1. **bundle** inmutable — modelos y forecast; su ``release_id`` no cambia por esto;
2. **gate** congelado inmutable — candidato, control, dataset, origen, semanas objetivo, umbrales y
   su ``gate_digest``;
3. **estado** mutable — veredicto y semanas observadas; referencia al gate y al release, y **nunca**
   forma parte de la identidad del bundle.

Todo lo de aquí es genérico: ni un padecimiento, ni un ``0/4``, ni un umbral escritos en el código.
La ruta de los archivos puede ser específica por configuración; el contrato y el loader no.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any

from epiforecast.data.epi_calendar import weeks_in_year
from epiforecast.publication.prospective import (
    ACCEPTANCE_RULE,
    CONTROL_ENGINE,
    GATE_SCHEMA,
    VERDICT_FAIL,
    VERDICT_INCOMPLETE,
    VERDICT_PASS,
    FrozenGate,
)
from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    require,
    text_of,
)
from epiforecast.runner.release_contract import canonical_json, sha256_bytes

STATUS_SCHEMA = "prospective_status.v1"
GATE_FILE = "prospective_gate.json"
STATUS_FILE = "prospective_status.json"
CONFIG_DIRNAME = "publication"

VERDICTS: tuple[str, ...] = (VERDICT_INCOMPLETE, VERDICT_PASS, VERDICT_FAIL)
# Sólo un veredicto habilita el modo público. FAIL nunca; INCOMPLETE únicamente porque el usuario
# autorizó publicación condicionada, y jamás se representa como PASS.
VERDICTS_PUBLICABLES: tuple[str, ...] = (VERDICT_INCOMPLETE, VERDICT_PASS)

Period = tuple[int, int]

SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

# Conjuntos EXACTOS de claves: una clave de más es un archivo que dice algo que nadie valida.
GATE_KEYS: frozenset[str] = frozenset(
    {
        "schema",
        "disease_id",
        "release_id",
        "origin",
        "horizon",
        "target_weeks",
        "candidate_forecast_digest",
        "control_engine",
        "control_forecast_digest",
        "dataset_digest",
        "acceptance_rule_max_degradation_pct",
        "gate_digest",
    }
)
STATUS_KEYS: frozenset[str] = frozenset(
    {
        "schema",
        "disease_id",
        "release_id",
        "gate_digest",
        "verdict",
        "weeks_required",
        "weeks_available",
        "completed_weeks",
        "target_weeks",
    }
)
RULE_KEYS: frozenset[str] = frozenset(ACCEPTANCE_RULE)


def _exact_keys(datos: Mapping[str, Any], esperadas: frozenset[str], etiqueta: str) -> None:
    sobran = sorted(set(datos) - esperadas)
    faltan = sorted(esperadas - set(datos))
    require(not sobran, f"{etiqueta}: claves no reconocidas {sobran}")
    require(not faltan, f"{etiqueta}: faltan claves {faltan}")


def _strict_int(valor: Any, etiqueta: str) -> int:
    """Entero de verdad: ``True`` es ``int`` en Python y no puede colarse como una semana."""
    require(
        isinstance(valor, int) and not isinstance(valor, bool),
        f"{etiqueta}: se esperaba un entero, no {valor!r}",
    )
    return int(valor)


def _digest(valor: Any, etiqueta: str) -> str:
    texto = text_of(valor, etiqueta)
    require(bool(SHA256_HEX.match(texto)), f"{etiqueta}: no es un SHA256 hex de 64 caracteres")
    return texto


def _period(valor: Any, etiqueta: str) -> Period:
    """Periodo MMWR válido: no basta con que sean dos enteros, la semana tiene que existir.

    Los años MMWR tienen 52 o 53 semanas según el año; aceptar ``(2026, 60)`` sería admitir una
    fecha que el calendario del proyecto no puede representar.
    """
    require(
        isinstance(valor, (list, tuple)) and len(valor) == 2,
        f"{etiqueta}: se esperaba [año, semana], no {valor!r}",
    )
    año = _strict_int(valor[0], f"{etiqueta}: año")
    semana = _strict_int(valor[1], f"{etiqueta}: semana")
    require(1900 < año < 2200, f"{etiqueta}: año fuera de rango ({año})")
    tope = weeks_in_year(año)
    require(
        1 <= semana <= tope,
        f"{etiqueta}: semana {semana} fuera del calendario MMWR de {año} (1..{tope})",
    )
    return (año, semana)


def _read_json(path: Path, etiqueta: str) -> dict[str, Any]:
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArtifactValidationError(f"{etiqueta}: no existe {path}") from exc
    except (*IO_ERRORS, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"{etiqueta}: ilegible ({exc})") from exc
    require(isinstance(datos, dict), f"{etiqueta}: se esperaba un objeto JSON")
    return dict(datos)


def load_gate(path: Path) -> FrozenGate:
    """Carga el gate congelado y **recomputa su digest**: no se cree lo que el archivo declara.

    Un gate cuyo digest declarado no coincide con el que produce su propio contenido no es el gate
    que se congeló: es otro, y aflojar un umbral después de ver resultados es exactamente el
    movimiento que esto impide.
    """
    datos = _read_json(path, "gate prospectivo")
    equal("gate prospectivo: schema", datos.get("schema"), GATE_SCHEMA)
    _exact_keys(datos, GATE_KEYS, "gate prospectivo")
    declarado = _digest(datos.get("gate_digest"), "gate prospectivo: gate_digest")

    rule = datos.get("acceptance_rule_max_degradation_pct")
    require(isinstance(rule, dict), "gate prospectivo: falta la regla de aceptación")
    assert isinstance(rule, dict)  # noqa: S101 — para mypy; `require` ya falló si no lo era
    _exact_keys(rule, RULE_KEYS, "gate prospectivo: regla de aceptación")
    for clave, umbral in rule.items():
        require(
            isinstance(umbral, (int, float))
            and not isinstance(umbral, bool)
            and math.isfinite(float(umbral))
            and float(umbral) >= 0.0,
            f"gate prospectivo: umbral {clave}={umbral!r} debe ser finito y no negativo",
        )
    horizonte = _strict_int(datos.get("horizon"), "gate prospectivo: horizon")
    require(horizonte > 0, "gate prospectivo: horizon debe ser positivo")
    gate = FrozenGate(
        disease_id=text_of(datos.get("disease_id"), "gate prospectivo: disease_id"),
        release_id=text_of(datos.get("release_id"), "gate prospectivo: release_id"),
        origin=_period(datos.get("origin"), "gate prospectivo: origin"),
        horizon=horizonte,
        target_weeks=tuple(
            _period(p, "gate prospectivo: target_weeks") for p in datos.get("target_weeks", ())
        ),
        candidate_digest=_digest(
            datos.get("candidate_forecast_digest"), "gate prospectivo: candidate_forecast_digest"
        ),
        control_digest=_digest(
            datos.get("control_forecast_digest"), "gate prospectivo: control_forecast_digest"
        ),
        dataset_digest=_digest(datos.get("dataset_digest"), "gate prospectivo: dataset_digest"),
        rule={str(k): float(v) for k, v in rule.items()},
    )
    require(gate.target_weeks, "gate prospectivo: sin semanas objetivo")
    require(
        list(gate.target_weeks) == sorted(set(gate.target_weeks)),
        "gate prospectivo: semanas objetivo repetidas o desordenadas",
    )
    equal("gate prospectivo: control_engine", datos.get("control_engine"), CONTROL_ENGINE)
    # El digest se RECOMPUTA desde el contenido; si no cuadra, el archivo miente sobre su identidad.
    equal("gate prospectivo: digest recomputado", gate.digest(), declarado)
    return gate


@dataclass(frozen=True, slots=True)
class ProspectiveStatus:
    """Resultado observado del gate. Referencia al gate y al release; jamás los redefine."""

    disease_id: str
    release_id: str
    gate_digest: str
    verdict: str
    weeks_required: int
    weeks_available: int
    completed_weeks: tuple[Period, ...]
    target_weeks: tuple[Period, ...]

    @property
    def publishable(self) -> bool:
        return self.verdict in VERDICTS_PUBLICABLES

    def payload(self) -> dict[str, Any]:
        return {
            "schema": STATUS_SCHEMA,
            "disease_id": self.disease_id,
            "release_id": self.release_id,
            "gate_digest": self.gate_digest,
            "verdict": self.verdict,
            "weeks_required": self.weeks_required,
            "weeks_available": self.weeks_available,
            "completed_weeks": [list(p) for p in self.completed_weeks],
            "target_weeks": [list(p) for p in self.target_weeks],
        }

    def digest(self) -> str:
        return sha256_bytes(canonical_json(self.payload()))

    def progress_label(self) -> str:
        """Etiqueta DERIVADA de los campos. Ni el texto ni el conteo se escriben a mano."""
        avance = f"({self.weeks_available}/{self.weeks_required} semanas)"
        if self.verdict == VERDICT_PASS:
            return f"Validación prospectiva superada {avance}"
        if self.verdict == VERDICT_FAIL:
            return f"Validación prospectiva NO superada {avance}"
        return f"Validación prospectiva en curso {avance}"


def _check_status(status: ProspectiveStatus, gate: FrozenGate) -> None:
    equal("estado prospectivo: disease_id", status.disease_id, gate.disease_id)
    equal("estado prospectivo: release_id", status.release_id, gate.release_id)
    equal("estado prospectivo: gate_digest", status.gate_digest, gate.digest())
    equal("estado prospectivo: semanas objetivo", status.target_weeks, gate.target_weeks)

    require(
        status.verdict in VERDICTS,
        f"estado prospectivo: veredicto desconocido {status.verdict!r} (esperado {list(VERDICTS)})",
    )
    require(status.weeks_required > 0, "estado prospectivo: weeks_required debe ser positivo")
    equal(
        "estado prospectivo: weeks_required contra las semanas del gate",
        status.weeks_required,
        len(gate.target_weeks),
    )
    require(
        0 <= status.weeks_available <= status.weeks_required,
        f"estado prospectivo: weeks_available fuera de rango "
        f"({status.weeks_available} de {status.weeks_required})",
    )
    equal(
        "estado prospectivo: semanas completadas contra weeks_available",
        len(status.completed_weeks),
        status.weeks_available,
    )
    require(
        len(set(status.completed_weeks)) == len(status.completed_weeks),
        "estado prospectivo: hay semanas completadas repetidas",
    )
    require(
        list(status.completed_weeks) == sorted(status.completed_weeks),
        "estado prospectivo: las semanas completadas deben ir ordenadas",
    )
    fuera = [p for p in status.completed_weeks if p not in gate.target_weeks]
    require(
        not fuera,
        f"estado prospectivo: semanas completadas que no son objetivo del gate: {fuera}",
    )

    # Coherencia veredicto ↔ conteos: un gate incompleto no puede declararse resuelto, ni uno
    # completo quedarse en «en curso».
    completo = status.weeks_available == status.weeks_required
    if status.verdict == VERDICT_INCOMPLETE:
        require(
            not completo,
            "estado prospectivo: INCOMPLETE con todas las semanas disponibles",
        )
    else:
        require(
            completo,
            f"estado prospectivo: {status.verdict} exige las {status.weeks_required} semanas, "
            f"hay {status.weeks_available}",
        )


@dataclass(frozen=True, slots=True)
class PublicationStatus:
    """Capability: gate congelado + estado, **validados entre sí en su construcción**.

    Antes se pasaba un ``ProspectiveStatus`` desnudo y el compilador sólo comparaba identificadores:
    un objeto construido a mano con digest y conteos falsos entraba igual, incluso en modo público
    (R76-P0-2). Aquí no hay forma de tener una instancia sin que el gate recompute su digest y el
    estado sea coherente con él; y el compilador, además, la ancla al release sellado.
    """

    gate: FrozenGate
    status: ProspectiveStatus

    def __post_init__(self) -> None:
        equal("capability: digest del gate", self.gate.digest(), self.status.gate_digest)
        _check_status(self.status, self.gate)

    @property
    def disease_id(self) -> str:
        return self.status.disease_id

    @property
    def release_id(self) -> str:
        return self.status.release_id

    @property
    def verdict(self) -> str:
        return self.status.verdict

    @property
    def publishable(self) -> bool:
        return self.status.publishable

    def progress_label(self) -> str:
        return self.status.progress_label()


def load_status(path: Path, gate: FrozenGate) -> ProspectiveStatus:
    """Carga y VALIDA el estado contra su gate. Falla cerrado ante cualquier incoherencia."""
    datos = _read_json(path, "estado prospectivo")
    equal("estado prospectivo: schema", datos.get("schema"), STATUS_SCHEMA)
    _exact_keys(datos, STATUS_KEYS, "estado prospectivo")
    status = ProspectiveStatus(
        disease_id=text_of(datos.get("disease_id"), "estado prospectivo: disease_id"),
        release_id=text_of(datos.get("release_id"), "estado prospectivo: release_id"),
        gate_digest=_digest(datos.get("gate_digest"), "estado prospectivo: gate_digest"),
        verdict=text_of(datos.get("verdict"), "estado prospectivo: verdict"),
        weeks_required=_strict_int(
            datos.get("weeks_required"), "estado prospectivo: weeks_required"
        ),
        weeks_available=_strict_int(
            datos.get("weeks_available"), "estado prospectivo: weeks_available"
        ),
        completed_weeks=tuple(
            _period(p, "estado prospectivo: completed_weeks")
            for p in datos.get("completed_weeks", ())
        ),
        target_weeks=tuple(
            _period(p, "estado prospectivo: target_weeks") for p in datos.get("target_weeks", ())
        ),
    )
    _check_status(status, gate)
    return status


def config_root(repo_root_path: Path | None = None) -> Path:
    """Raíz declarativa ``config/publication/``. La RUTA puede ser específica; el contrato no."""
    from .compiler import repo_root

    raiz = repo_root_path if repo_root_path is not None else repo_root()
    return raiz / "config" / CONFIG_DIRNAME


def load_declared_status(
    disease_id: str, *, config_root_path: Path | None = None
) -> PublicationStatus:
    """Gate + estado DECLARADOS de un padecimiento, ya validados entre sí.

    Se lee aquí, en el borde, y se **inyecta**: ninguna función pura del compilador o de los puentes
    toca el filesystem para averiguar en qué estado está la validación.
    """
    raiz = (config_root_path if config_root_path is not None else config_root()) / disease_id
    gate = load_gate(raiz / GATE_FILE)
    equal(f"{disease_id}: disease_id del gate declarado", gate.disease_id, disease_id)
    return PublicationStatus(gate=gate, status=load_status(raiz / STATUS_FILE, gate))


def status_facts(capability: PublicationStatus, *, label: str) -> dict[str, Any]:
    """Bloque que TODOS los puentes repiten igual: identidad del gate, conteos y etiqueta visible."""
    status = capability.status
    return {
        "schema": STATUS_SCHEMA,
        "gate_digest": status.gate_digest,
        "verdict": status.verdict,
        "weeks_required": status.weeks_required,
        "weeks_available": status.weeks_available,
        "completed_weeks": [list(p) for p in status.completed_weeks],
        "target_weeks": [list(p) for p in status.target_weeks],
        "status_digest": status.digest(),
        "label": label,
    }
