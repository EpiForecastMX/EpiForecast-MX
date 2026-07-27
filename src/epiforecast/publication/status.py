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

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from epiforecast.publication.prospective import (
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


def _period(valor: Any, etiqueta: str) -> Period:
    require(
        isinstance(valor, (list, tuple)) and len(valor) == 2,
        f"{etiqueta}: se esperaba [año, semana], no {valor!r}",
    )
    año, semana = valor
    require(
        isinstance(año, int) and isinstance(semana, int) and not isinstance(año, bool),
        f"{etiqueta}: año y semana deben ser enteros, no {valor!r}",
    )
    return (int(año), int(semana))


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
    declarado = text_of(datos.get("gate_digest"), "gate prospectivo: gate_digest")

    rule = datos.get("acceptance_rule_max_degradation_pct")
    require(
        isinstance(rule, dict) and bool(rule), "gate prospectivo: falta la regla de aceptación"
    )
    assert isinstance(rule, dict)  # noqa: S101 — para mypy; `require` ya falló si no lo era
    gate = FrozenGate(
        disease_id=text_of(datos.get("disease_id"), "gate prospectivo: disease_id"),
        release_id=text_of(datos.get("release_id"), "gate prospectivo: release_id"),
        origin=_period(datos.get("origin"), "gate prospectivo: origin"),
        horizon=int(datos.get("horizon", 0)),
        target_weeks=tuple(
            _period(p, "gate prospectivo: target_weeks") for p in datos.get("target_weeks", ())
        ),
        candidate_digest=text_of(
            datos.get("candidate_forecast_digest"), "gate prospectivo: candidate_forecast_digest"
        ),
        control_digest=text_of(
            datos.get("control_forecast_digest"), "gate prospectivo: control_forecast_digest"
        ),
        dataset_digest=text_of(datos.get("dataset_digest"), "gate prospectivo: dataset_digest"),
        rule={str(k): float(v) for k, v in rule.items()},
    )
    require(gate.target_weeks, "gate prospectivo: sin semanas objetivo")
    equal(
        "gate prospectivo: control_engine",
        datos.get("control_engine"),
        gate.payload()["control_engine"],
    )
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


def load_status(path: Path, gate: FrozenGate) -> ProspectiveStatus:
    """Carga y VALIDA el estado contra su gate. Falla cerrado ante cualquier incoherencia."""
    datos = _read_json(path, "estado prospectivo")
    equal("estado prospectivo: schema", datos.get("schema"), STATUS_SCHEMA)
    status = ProspectiveStatus(
        disease_id=text_of(datos.get("disease_id"), "estado prospectivo: disease_id"),
        release_id=text_of(datos.get("release_id"), "estado prospectivo: release_id"),
        gate_digest=text_of(datos.get("gate_digest"), "estado prospectivo: gate_digest"),
        verdict=text_of(datos.get("verdict"), "estado prospectivo: verdict"),
        weeks_required=int(datos.get("weeks_required", 0)),
        weeks_available=int(datos.get("weeks_available", -1)),
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
) -> ProspectiveStatus:
    """Gate + estado DECLARADOS de un padecimiento, ya validados entre sí.

    Se lee aquí, en el borde, y se **inyecta**: ninguna función pura del compilador o de los puentes
    toca el filesystem para averiguar en qué estado está la validación.
    """
    raiz = (config_root_path if config_root_path is not None else config_root()) / disease_id
    gate = load_gate(raiz / GATE_FILE)
    equal(f"{disease_id}: disease_id del gate declarado", gate.disease_id, disease_id)
    return load_status(raiz / STATUS_FILE, gate)


def status_facts(status: ProspectiveStatus, *, label: str) -> dict[str, Any]:
    """Bloque que TODOS los puentes repiten igual: identidad del gate, conteos y etiqueta visible."""
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
