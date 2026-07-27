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
    METRIC_KEYS,
    SCOPE_BASE,
    SCOPE_NATIONAL,
    SCOPE_PRODUCTS,
    SCOPES,
    SKIP_REASONS,
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
EVALUATION_SCHEMA = "prospective_evaluation.v2"
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
        "observation_cutoff",
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
    observation_cutoff: Period | None
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
            "observation_cutoff": list(self.observation_cutoff)
            if self.observation_cutoff
            else None,
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


SCOPE_KEYS: frozenset[str] = frozenset(
    {
        "rows",
        "smape_candidate",
        "smape_control",
        "degradation_pct",
        "max_degradation_pct",
        "passes",
    }
)
METRIC_SIDE_KEYS: frozenset[str] = frozenset({"products", "median", "flags"})
# Procedencia EXACTA del snapshot de observación. Aceptar `{}` convertía la verdad en una identidad
# sin origen (R82-P0-2). La geografía sigue sellada dentro del digest efectivo de `config`.
SOURCE_DIGEST_KEYS: frozenset[str] = frozenset({"raw", "config", "exposure"})
PER_WEEK_KEYS: frozenset[str] = frozenset({"week", "series", "smape_candidate", "smape_control"})
# Filas esperadas por semana en cada ámbito: bases, productos derivados y el único nacional General.
SCOPE_ROWS_PER_WEEK: dict[str, int] = {SCOPE_BASE: 64, SCOPE_PRODUCTS: 111, SCOPE_NATIONAL: 1}


def _number(valor: Any, etiqueta: str, *, permite_inf: bool = False) -> float:
    require(
        isinstance(valor, (int, float)) and not isinstance(valor, bool),
        f"{etiqueta}: se esperaba un número, no {valor!r}",
    )
    numero = float(valor)
    require(
        math.isfinite(numero) or permite_inf,
        f"{etiqueta}: valor no finito ({valor!r})",
    )
    return numero


def _check_scopes(evaluation: ProspectiveEvaluation, gate: FrozenGate) -> None:
    """La aritmética del artefacto tiene que sostenerse sola.

    El digest sella los BYTES: alguien podía cambiar ``passes`` o la degradación y recalcularlo, y
    el loader lo aceptaba (R80-P1). Aquí se recomputan degradación, ``passes`` y veredicto desde
    sMAPE candidato/control y el umbral del gate, que es lo único que decide.
    """
    semanas = len(evaluation.completed_weeks)
    if not evaluation.scopes:
        require(
            evaluation.verdict == VERDICT_INCOMPLETE and semanas < len(gate.target_weeks),
            "evaluación: sin ámbitos, el veredicto sólo puede ser INCOMPLETE",
        )
        return

    equal("evaluación: ámbitos declarados", sorted(evaluation.scopes), sorted(SCOPES))
    pasan: list[bool] = []
    for scope, cuerpo in evaluation.scopes.items():
        require(isinstance(cuerpo, dict), f"evaluación: ámbito {scope} no es un objeto")
        _exact_keys(cuerpo, SCOPE_KEYS, f"evaluación: ámbito {scope}")
        equal(
            f"evaluación: filas del ámbito {scope}",
            _strict_int(cuerpo["rows"], f"evaluación: {scope}.rows"),
            SCOPE_ROWS_PER_WEEK[scope] * semanas,
        )
        candidato = _number(cuerpo["smape_candidate"], f"evaluación: {scope}.smape_candidate")
        control = _number(cuerpo["smape_control"], f"evaluación: {scope}.smape_control")
        umbral = _number(cuerpo["max_degradation_pct"], f"evaluación: {scope}.max_degradation_pct")
        equal(f"evaluación: umbral del ámbito {scope}", umbral, float(gate.rule[scope]))

        declarada = _number(
            cuerpo["degradation_pct"], f"evaluación: {scope}.degradation_pct", permite_inf=True
        )
        # Único caso zero-safe declarado: control perfecto y candidato imperfecto ⇒ inf ⇒ falla.
        esperada = (
            (0.0 if candidato == 0.0 else float("inf"))
            if control == 0.0
            else (candidato - control) / control * 100.0
        )
        require(
            declarada == esperada or math.isclose(declarada, esperada, rel_tol=1e-9, abs_tol=1e-9),
            f"evaluación: {scope}.degradation_pct declarada {declarada} ≠ {esperada} recomputada",
        )
        require(
            isinstance(cuerpo["passes"], bool), f"evaluación: {scope}.passes debe ser booleano"
        )
        equal(
            f"evaluación: {scope}.passes recomputado", cuerpo["passes"], bool(declarada <= umbral)
        )
        pasan.append(bool(cuerpo["passes"]))

    completo = semanas >= len(gate.target_weeks)
    esperado = (VERDICT_PASS if all(pasan) else VERDICT_FAIL) if completo else VERDICT_INCOMPLETE
    equal("evaluación: veredicto recomputado desde los ámbitos", evaluation.verdict, esperado)


def _check_metrics(evaluation: ProspectiveEvaluation) -> None:
    if not evaluation.metrics:
        require(not evaluation.scopes, "evaluación: hay ámbitos pero no métricas")
        return
    equal("evaluación: métricas por ámbito", sorted(evaluation.metrics), sorted(SCOPES))
    for scope, cuerpo in evaluation.metrics.items():
        require(isinstance(cuerpo, dict), f"evaluación: métricas de {scope} no son un objeto")
        equal(f"evaluación: lados de {scope}", sorted(cuerpo), ["candidate", "control"])
        for lado, bloque in cuerpo.items():
            _exact_keys(bloque, METRIC_SIDE_KEYS, f"evaluación: métricas {scope}.{lado}")
            productos = _strict_int(bloque["products"], f"evaluación: {scope}.{lado}.products")
            equal(
                f"evaluación: productos del ámbito {scope}.{lado}",
                productos,
                SCOPE_ROWS_PER_WEEK[scope],
            )
            mediana = bloque["median"]
            require(
                isinstance(mediana, dict), f"evaluación: {scope}.{lado}.median no es un objeto"
            )
            # Las seis, siempre: una clave ausente no es un null, es evidencia perdida.
            _exact_keys(mediana, frozenset(METRIC_KEYS), f"evaluación: {scope}.{lado}.median")
            flags = bloque["flags"]
            require(isinstance(flags, dict), f"evaluación: {scope}.{lado}.flags no es un objeto")
            for nombre, cuenta in flags.items():
                n = _strict_int(cuenta, f"evaluación: {scope}.{lado}.flags.{nombre}")
                require(
                    0 <= n <= productos,
                    f"evaluación: {scope}.{lado}.flags.{nombre}={n} fuera de 0..{productos}",
                )
            for nombre, valor in mediana.items():
                if valor is None:
                    # Indefinido SÓLO con su bandera: un null sin explicación es un dato perdido.
                    require(
                        any(nombre in f for f in flags),
                        f"evaluación: {scope}.{lado}.{nombre} es null sin bandera que lo explique",
                    )
                    continue
                _number(valor, f"evaluación: {scope}.{lado}.median.{nombre}")


def _check_per_week(evaluation: ProspectiveEvaluation) -> None:
    equal(
        "evaluación: detalle semanal contra las semanas completadas",
        [tuple(d.get("week", ())) for d in evaluation.per_week],
        [tuple(p) for p in evaluation.completed_weeks],
    )
    for detalle in evaluation.per_week:
        _exact_keys(detalle, PER_WEEK_KEYS, "evaluación: detalle semanal")
        equal(
            "evaluación: series del detalle semanal",
            _strict_int(detalle["series"], "evaluación: detalle semanal .series"),
            SCOPE_ROWS_PER_WEEK[SCOPE_BASE],
        )
        _number(detalle["smape_candidate"], "evaluación: detalle semanal .smape_candidate")
        _number(detalle["smape_control"], "evaluación: detalle semanal .smape_control")


def _check_sequence(evaluation: ProspectiveEvaluation, gate: FrozenGate) -> None:
    """La secuencia observada tiene que estar COMPLETA: sin huecos que borren evidencia.

    Validar cada omisión por separado permitía re-sellar un artefacto sin W28 conservando W29–W31
    como completas: el veredicto numérico no cambia, pero desaparece qué pasó con una semana
    programada (R82-P1). Aquí se exige que completadas ∪ omitidas cubran exactamente cada periodo
    observable, sin solapes ni repeticiones.
    """
    corte = evaluation.observation_cutoff
    require(corte is not None, "evaluación: falta observation_cutoff")
    assert corte is not None  # noqa: S101 — para mypy; `require` ya falló si era None
    ventana = [
        p for p in horizon_periods(gate.origin, gate.horizon) if gate.target_weeks[0] <= p <= corte
    ]
    completas = list(evaluation.completed_weeks)
    if len(completas) >= len(gate.target_weeks):
        # Ya se llegó a la meta: la secuencia termina en la última semana que contó.
        ventana = [p for p in ventana if p <= completas[-1]]
    observadas = sorted([*completas, *[p for p, _ in evaluation.skipped_weeks]])
    equal(
        "evaluación: secuencia observada (completadas ∪ omitidas)",
        observadas,
        sorted(ventana),
    )


def _check_skipped(evaluation: ProspectiveEvaluation, gate: FrozenGate) -> None:
    """Sólo se omite lo que ya se pudo observar. El futuro no es una semana ausente (R80-P0-1)."""
    corte = evaluation.observation_cutoff
    for periodo, motivo in evaluation.skipped_weeks:
        require(
            motivo in SKIP_REASONS,
            f"evaluación: motivo de omisión desconocido {motivo!r} (esperado {list(SKIP_REASONS)})",
        )
        require(
            corte is not None and periodo <= corte,
            f"evaluación: {periodo} se declara omitida pero es posterior al corte observado {corte}",
        )
        require(
            periodo >= gate.target_weeks[0],
            f"evaluación: {periodo} es anterior al inicio del gate",
        )
    omitidas = [p for p, _ in evaluation.skipped_weeks]
    require(len(set(omitidas)) == len(omitidas), "evaluación: semanas omitidas repetidas")
    solapan = set(omitidas) & set(evaluation.completed_weeks)
    require(not solapan, f"evaluación: semanas a la vez completas y omitidas: {sorted(solapan)}")
    if corte is not None:
        tardias = [p for p in evaluation.completed_weeks if p > corte]
        require(not tardias, f"evaluación: semanas completadas posteriores al corte: {tardias}")


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
    _exact_keys(
        evaluation.observation_source_digests,
        SOURCE_DIGEST_KEYS,
        "evaluación: procedencia del dataset de observación",
    )
    corte = evaluation.observation_cutoff
    require(corte is not None, "evaluación: observation_cutoff es obligatorio")
    assert corte is not None  # noqa: S101 — para mypy
    require(
        corte >= gate.origin,
        f"evaluación: el corte observado {corte} es anterior al origen congelado {gate.origin}",
    )
    _check_completed_weeks(evaluation.completed_weeks, gate, "evaluación")
    require(
        evaluation.verdict in VERDICTS, f"evaluación: veredicto desconocido {evaluation.verdict!r}"
    )
    if evaluation.verdict != VERDICT_INCOMPLETE:
        faltan = [s for s in SCOPES if s not in evaluation.scopes]
        require(not faltan, f"evaluación: un veredicto {evaluation.verdict} sin ámbitos {faltan}")
    _check_skipped(evaluation, gate)
    _check_sequence(evaluation, gate)
    _check_scopes(evaluation, gate)
    _check_metrics(evaluation)
    _check_per_week(evaluation)


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
        observation_cutoff=(
            _period(datos["observation_cutoff"], "evaluación prospectiva: observation_cutoff")
            if datos.get("observation_cutoff") is not None
            else None
        ),
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
