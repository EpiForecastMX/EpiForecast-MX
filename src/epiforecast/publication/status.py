"""C7.6-PUBLICATION-STATUS — el estado prospectivo como CONTRATO, no como frase en un plan.

El release es inmutable y el gate prospectivo también: se congelaron antes de ver una sola semana de
verdad. Lo que cambia cada boletín es el **resultado observado**, y hasta ahora ese resultado vivía
sólo en el plan operativo. Publicar así mostraría un pronóstico puntual correcto omitiendo la
condición bajo la que se autorizó publicarlo, que es peor que no publicarlo (R74-P0).

Cuatro identidades separadas, y ninguna contamina a la otra:

1. **bundle** inmutable — modelos y forecast; su ``release_id`` no cambia por esto;
2. **gate** congelado inmutable — candidato, control, dataset de ENTRENAMIENTO, origen, semanas
   objetivo, umbrales y su ``gate_digest``;
3. **evaluation** — toda la evidencia que justifica el veredicto: qué verdad se usó, qué semanas
   contaron, cuáles se omitieron y por qué, y las métricas por ámbito. Es lo que hace auditable un
   futuro PASS o FAIL (R78-P0-3);
4. **status** — el resumen que viaja a los consumidores, que referencia el ``evaluation_digest``.

Nada de esto forma parte del ``release_id``. Todo es genérico: ni un padecimiento, ni un ``0/4``, ni
un umbral escritos en el código. La ruta de los archivos puede ser específica por configuración; el
contrato y el loader no.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
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
    SCOPES,
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
from epiforecast.runner.release_reproduce import horizon_periods

STATUS_SCHEMA = "prospective_status.v2"
EVALUATION_SCHEMA = "prospective_evaluation.v1"
GATE_FILE = "prospective_gate.json"
STATUS_FILE = "prospective_status.json"
EVALUATION_FILE = "prospective_evaluation.json"
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
        "evaluation_digest",
        "observation_dataset_id",
        "observation_dataset_digest",
        "verdict",
        "weeks_required",
        "weeks_available",
        "completed_weeks",
        "target_weeks",
    }
)
EVALUATION_KEYS: frozenset[str] = frozenset(
    {
        "schema",
        "disease_id",
        "release_id",
        "gate_digest",
        "candidate_forecast_digest",
        "control_forecast_digest",
        "training_dataset_id",
        "training_dataset_digest",
        "observation_dataset_id",
        "observation_dataset_digest",
        "observation_source_digests",
        "scheduled_weeks",
        "completed_weeks",
        "skipped_weeks",
        "scopes",
        "metrics",
        "per_week",
        "verdict",
        "evaluation_digest",
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


def _periods(valor: Any, etiqueta: str) -> tuple[Period, ...]:
    require(isinstance(valor, (list, tuple)), f"{etiqueta}: se esperaba una lista de periodos")
    return tuple(_period(p, etiqueta) for p in valor)


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
        target_weeks=_periods(datos.get("target_weeks"), "gate prospectivo: target_weeks"),
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
class ProspectiveEvaluation:
    """Evidencia completa de UNA evaluación: de dónde salió la verdad y qué decidió el gate.

    Sin esto, un futuro PASS o FAIL era una palabra sin nada detrás: el JSON sólo guardaba el
    veredicto y el conteo, así que nadie podía auditar por qué (R78-P0-3).
    """

    disease_id: str
    release_id: str
    gate_digest: str
    candidate_digest: str
    control_digest: str
    training_dataset_id: str
    training_dataset_digest: str
    observation_dataset_id: str
    observation_dataset_digest: str
    observation_source_digests: dict[str, str]
    scheduled_weeks: tuple[Period, ...]
    completed_weeks: tuple[Period, ...]
    skipped_weeks: tuple[tuple[Period, str], ...]
    verdict: str
    scopes: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    per_week: tuple[dict[str, Any], ...] = ()

    def payload(self) -> dict[str, Any]:
        cuerpo: dict[str, Any] = {
            "schema": EVALUATION_SCHEMA,
            "disease_id": self.disease_id,
            "release_id": self.release_id,
            "gate_digest": self.gate_digest,
            "candidate_forecast_digest": self.candidate_digest,
            "control_forecast_digest": self.control_digest,
            "training_dataset_id": self.training_dataset_id,
            "training_dataset_digest": self.training_dataset_digest,
            "observation_dataset_id": self.observation_dataset_id,
            "observation_dataset_digest": self.observation_dataset_digest,
            "observation_source_digests": dict(sorted(self.observation_source_digests.items())),
            "scheduled_weeks": [list(p) for p in self.scheduled_weeks],
            "completed_weeks": [list(p) for p in self.completed_weeks],
            "skipped_weeks": [{"week": list(p), "reason": r} for p, r in self.skipped_weeks],
            "scopes": self.scopes,
            "metrics": self.metrics,
            "per_week": [dict(d) for d in self.per_week],
            "verdict": self.verdict,
        }
        return {**cuerpo, "evaluation_digest": sha256_bytes(canonical_json(cuerpo))}

    def digest(self) -> str:
        return str(self.payload()["evaluation_digest"])


@dataclass(frozen=True, slots=True)
class ProspectiveStatus:
    """Resumen que viaja a los consumidores. Referencia gate y evaluación; no los redefine."""

    disease_id: str
    release_id: str
    gate_digest: str
    evaluation_digest: str
    observation_dataset_id: str
    observation_dataset_digest: str
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
            "evaluation_digest": self.evaluation_digest,
            "observation_dataset_id": self.observation_dataset_id,
            "observation_dataset_digest": self.observation_dataset_digest,
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


def _check_completed_weeks(semanas: tuple[Period, ...], gate: FrozenGate, etiqueta: str) -> None:
    """Ordenadas, únicas y DENTRO del horizonte congelado — no necesariamente las programadas.

    Exigir que fueran subconjunto de ``target_weeks`` hacía que el reemplazo de una semana ausente
    pasara su prueba unitaria y muriera en el loader (R78-P0-2): W31 sustituye a W28 y sigue siendo
    una semana del horizonte que el release pronosticó.
    """
    require(len(set(semanas)) == len(semanas), f"{etiqueta}: hay semanas completadas repetidas")
    require(
        list(semanas) == sorted(semanas), f"{etiqueta}: las semanas completadas deben ir ordenadas"
    )
    ventana = set(horizon_periods(gate.origin, gate.horizon))
    fuera = [p for p in semanas if p not in ventana]
    require(not fuera, f"{etiqueta}: semanas fuera del horizonte congelado: {fuera}")
    tempranas = [p for p in semanas if p < gate.target_weeks[0]]
    require(not tempranas, f"{etiqueta}: semanas anteriores al inicio del gate: {tempranas}")


def _check_evaluation(evaluation: ProspectiveEvaluation, gate: FrozenGate) -> None:
    equal("evaluación: disease_id", evaluation.disease_id, gate.disease_id)
    equal("evaluación: release_id", evaluation.release_id, gate.release_id)
    equal("evaluación: gate_digest", evaluation.gate_digest, gate.digest())
    # El congelado se verifica ENTERO: candidato, control y dataset de entrenamiento. El control
    # faltaba, y podía sustituirse sin que nadie lo notara (R78-P0-4).
    equal("evaluación: candidato del gate", evaluation.candidate_digest, gate.candidate_digest)
    equal("evaluación: control del gate", evaluation.control_digest, gate.control_digest)
    equal(
        "evaluación: dataset de entrenamiento del gate",
        evaluation.training_dataset_digest,
        gate.dataset_digest,
    )
    equal("evaluación: semanas programadas", evaluation.scheduled_weeks, gate.target_weeks)
    _check_completed_weeks(evaluation.completed_weeks, gate, "evaluación")
    require(
        evaluation.verdict in VERDICTS, f"evaluación: veredicto desconocido {evaluation.verdict!r}"
    )
    if evaluation.verdict != VERDICT_INCOMPLETE:
        faltan = [s for s in SCOPES if s not in evaluation.scopes]
        require(not faltan, f"evaluación: un veredicto {evaluation.verdict} sin ámbitos {faltan}")


def _check_status(
    status: ProspectiveStatus, gate: FrozenGate, evaluation: ProspectiveEvaluation
) -> None:
    equal("estado prospectivo: disease_id", status.disease_id, gate.disease_id)
    equal("estado prospectivo: release_id", status.release_id, gate.release_id)
    equal("estado prospectivo: gate_digest", status.gate_digest, gate.digest())
    equal("estado prospectivo: semanas objetivo", status.target_weeks, gate.target_weeks)
    equal("estado prospectivo: evaluation_digest", status.evaluation_digest, evaluation.digest())
    equal(
        "estado prospectivo: dataset de observación",
        (status.observation_dataset_id, status.observation_dataset_digest),
        (evaluation.observation_dataset_id, evaluation.observation_dataset_digest),
    )
    equal("estado prospectivo: veredicto contra la evaluación", status.verdict, evaluation.verdict)
    equal(
        "estado prospectivo: semanas completadas contra la evaluación",
        status.completed_weeks,
        evaluation.completed_weeks,
    )

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
    _check_completed_weeks(status.completed_weeks, gate, "estado prospectivo")

    # Coherencia veredicto ↔ conteos: un gate incompleto no puede declararse resuelto, ni uno
    # completo quedarse en «en curso».
    completo = status.weeks_available == status.weeks_required
    if status.verdict == VERDICT_INCOMPLETE:
        require(not completo, "estado prospectivo: INCOMPLETE con todas las semanas disponibles")
    else:
        require(
            completo,
            f"estado prospectivo: {status.verdict} exige las {status.weeks_required} semanas, "
            f"hay {status.weeks_available}",
        )


def load_evaluation(path: Path, gate: FrozenGate) -> ProspectiveEvaluation:
    """Carga la evidencia y **recomputa su digest** antes de creerle nada."""
    datos = _read_json(path, "evaluación prospectiva")
    equal("evaluación prospectiva: schema", datos.get("schema"), EVALUATION_SCHEMA)
    _exact_keys(datos, EVALUATION_KEYS, "evaluación prospectiva")
    declarado = _digest(
        datos.get("evaluation_digest"), "evaluación prospectiva: evaluation_digest"
    )

    fuentes = datos.get("observation_source_digests")
    require(
        isinstance(fuentes, dict), "evaluación prospectiva: observation_source_digests inválido"
    )
    assert isinstance(fuentes, dict)  # noqa: S101 — para mypy
    omitidas = datos.get("skipped_weeks")
    require(isinstance(omitidas, list), "evaluación prospectiva: skipped_weeks inválido")
    assert isinstance(omitidas, list)  # noqa: S101 — para mypy

    evaluation = ProspectiveEvaluation(
        disease_id=text_of(datos.get("disease_id"), "evaluación prospectiva: disease_id"),
        release_id=text_of(datos.get("release_id"), "evaluación prospectiva: release_id"),
        gate_digest=_digest(datos.get("gate_digest"), "evaluación prospectiva: gate_digest"),
        candidate_digest=_digest(
            datos.get("candidate_forecast_digest"), "evaluación prospectiva: candidato"
        ),
        control_digest=_digest(
            datos.get("control_forecast_digest"), "evaluación prospectiva: control"
        ),
        training_dataset_id=text_of(
            datos.get("training_dataset_id"), "evaluación prospectiva: training_dataset_id"
        ),
        training_dataset_digest=_digest(
            datos.get("training_dataset_digest"), "evaluación prospectiva: training_dataset_digest"
        ),
        observation_dataset_id=text_of(
            datos.get("observation_dataset_id"), "evaluación prospectiva: observation_dataset_id"
        ),
        observation_dataset_digest=_digest(
            datos.get("observation_dataset_digest"),
            "evaluación prospectiva: observation_dataset_digest",
        ),
        observation_source_digests={
            str(k): _digest(v, f"evaluación prospectiva: fuente {k}") for k, v in fuentes.items()
        },
        scheduled_weeks=_periods(
            datos.get("scheduled_weeks"), "evaluación prospectiva: scheduled_weeks"
        ),
        completed_weeks=_periods(
            datos.get("completed_weeks"), "evaluación prospectiva: completed_weeks"
        ),
        skipped_weeks=tuple(
            (
                _period(d.get("week"), "evaluación prospectiva: skipped_weeks"),
                text_of(d.get("reason"), "evaluación prospectiva: motivo"),
            )
            for d in omitidas
        ),
        verdict=text_of(datos.get("verdict"), "evaluación prospectiva: verdict"),
        scopes=dict(datos.get("scopes") or {}),
        metrics=dict(datos.get("metrics") or {}),
        per_week=tuple(dict(d) for d in (datos.get("per_week") or [])),
    )
    equal("evaluación prospectiva: digest recomputado", evaluation.digest(), declarado)
    _check_evaluation(evaluation, gate)
    return evaluation


def load_status(
    path: Path, gate: FrozenGate, evaluation: ProspectiveEvaluation
) -> ProspectiveStatus:
    """Carga y VALIDA el estado contra su gate y su evaluación. Falla cerrado ante incoherencias."""
    datos = _read_json(path, "estado prospectivo")
    equal("estado prospectivo: schema", datos.get("schema"), STATUS_SCHEMA)
    _exact_keys(datos, STATUS_KEYS, "estado prospectivo")
    status = ProspectiveStatus(
        disease_id=text_of(datos.get("disease_id"), "estado prospectivo: disease_id"),
        release_id=text_of(datos.get("release_id"), "estado prospectivo: release_id"),
        gate_digest=_digest(datos.get("gate_digest"), "estado prospectivo: gate_digest"),
        evaluation_digest=_digest(
            datos.get("evaluation_digest"), "estado prospectivo: evaluation_digest"
        ),
        observation_dataset_id=text_of(
            datos.get("observation_dataset_id"), "estado prospectivo: observation_dataset_id"
        ),
        observation_dataset_digest=_digest(
            datos.get("observation_dataset_digest"),
            "estado prospectivo: observation_dataset_digest",
        ),
        verdict=text_of(datos.get("verdict"), "estado prospectivo: verdict"),
        weeks_required=_strict_int(
            datos.get("weeks_required"), "estado prospectivo: weeks_required"
        ),
        weeks_available=_strict_int(
            datos.get("weeks_available"), "estado prospectivo: weeks_available"
        ),
        completed_weeks=_periods(
            datos.get("completed_weeks"), "estado prospectivo: completed_weeks"
        ),
        target_weeks=_periods(datos.get("target_weeks"), "estado prospectivo: target_weeks"),
    )
    _check_status(status, gate, evaluation)
    return status


# Marca interna: la capability sólo la emite el loader oficial. Un objeto construido a mano no es
# una capability validada, y con un token privado eso deja de ser una convención (R76-P0-2).
_LOADER_TOKEN = object()


@dataclass(frozen=True, slots=True)
class PublicationStatus:
    """Capability: gate + evaluación + estado, cruzados y validados. Sólo la emite el loader."""

    gate: FrozenGate
    evaluation: ProspectiveEvaluation
    status: ProspectiveStatus
    token: Any = None

    def __post_init__(self) -> None:
        require(
            self.token is _LOADER_TOKEN,
            "la capability de publicación sólo se obtiene de load_declared_status()",
        )
        _check_evaluation(self.evaluation, self.gate)
        _check_status(self.status, self.gate, self.evaluation)

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


def config_root(repo_root_path: Path | None = None) -> Path:
    """Raíz declarativa ``config/publication/``. La RUTA puede ser específica; el contrato no."""
    from .compiler import repo_root

    raiz = repo_root_path if repo_root_path is not None else repo_root()
    return raiz / "config" / CONFIG_DIRNAME


def declared_paths(disease_id: str, *, config_root_path: Path | None = None) -> dict[str, Path]:
    """Rutas declarativas del padecimiento. Un solo sitio construye estas rutas."""
    raiz = (config_root_path if config_root_path is not None else config_root()) / disease_id
    return {
        "root": raiz,
        "gate": raiz / GATE_FILE,
        "evaluation": raiz / EVALUATION_FILE,
        "status": raiz / STATUS_FILE,
    }


def load_declared_status(
    disease_id: str, *, config_root_path: Path | None = None
) -> PublicationStatus:
    """Gate + evaluación + estado DECLARADOS, ya validados y cruzados entre sí.

    Se lee aquí, en el borde, y se **inyecta**: ninguna función pura del compilador o de los puentes
    toca el filesystem para averiguar en qué estado está la validación.
    """
    rutas = declared_paths(disease_id, config_root_path=config_root_path)
    gate = load_gate(rutas["gate"])
    equal(f"{disease_id}: disease_id del gate declarado", gate.disease_id, disease_id)
    evaluation = load_evaluation(rutas["evaluation"], gate)
    status = load_status(rutas["status"], gate, evaluation)
    return PublicationStatus(gate=gate, evaluation=evaluation, status=status, token=_LOADER_TOKEN)


def status_facts(capability: PublicationStatus, *, label: str) -> dict[str, Any]:
    """Bloque que TODOS los puentes repiten igual: identidad del gate, conteos y etiqueta visible."""
    status = capability.status
    return {
        "schema": STATUS_SCHEMA,
        "gate_digest": status.gate_digest,
        "evaluation_digest": status.evaluation_digest,
        "observation_dataset_id": status.observation_dataset_id,
        "verdict": status.verdict,
        "weeks_required": status.weeks_required,
        "weeks_available": status.weeks_available,
        "completed_weeks": [list(p) for p in status.completed_weeks],
        "target_weeks": [list(p) for p in status.target_weeks],
        "status_digest": status.digest(),
        "label": label,
    }
