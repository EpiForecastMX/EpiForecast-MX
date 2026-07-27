"""C7.6-PUBLICATION-STATUS-A — el estado prospectivo como contrato verificable.

Lo que se protege: que la condición bajo la que se autorizó publicar viaje CON los datos y no en un
documento aparte. Publicar un pronóstico puntual correcto omitiendo que su validación prospectiva
va 0 de 4 es peor que no publicarlo (R74-P0).

El grueso de estas pruebas usa un padecimiento SINTÉTICO y un gate fabricado: si el contrato sólo
funcionara con Obesidad, no sería un contrato. Sólo las que verifican los cuatro puentes contra el
release real se saltan cuando `runs/` no está en el entorno.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
import shutil

import pytest

from epiforecast import registry
from epiforecast.publication.compiler import (
    MODE_CANDIDATE,
    MODE_PUBLIC,
    POINT_ONLY_SUFFIX,
    compile_release,
    publication_label,
)
from epiforecast.publication.prospective import (
    ACCEPTANCE_RULE,
    GATE_WEEKS,
    VERDICT_FAIL,
    VERDICT_INCOMPLETE,
    VERDICT_PASS,
    FrozenGate,
    Period,
)
from epiforecast.publication.shards import (
    CHANNEL_EPIBOT,
    CHANNEL_REPORTS,
    CHANNEL_TABLEAU,
    CHANNEL_WEB,
    SHARD_MANIFEST,
    emit_shards,
)
from epiforecast.publication.status import (
    EVALUATION_FILE,
    GATE_FILE,
    STATUS_FILE,
    STATUS_SCHEMA,
    ProspectiveEvaluation,
    load_declared_status,
    load_gate,
)
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_contract import canonical_json
from epiforecast.runner.release_reproduce import horizon_periods
from epiforecast.runner.release_store import promote_release
from tests.unit.runner import artifact_fixtures as af
from tests.unit.runner import release_fixtures as rf

# ── Padecimiento sintético: el contrato no puede depender de Obesidad ─────────────────────────
OTRO = "padecimiento_x"
OTRO_RELEASE = "padecimiento_x_release_abc123456789"
ORIGEN = (2026, 10)


def _gate(**cambios) -> FrozenGate:
    base = {
        "disease_id": OTRO,
        "release_id": OTRO_RELEASE,
        "origin": ORIGEN,
        "horizon": 52,
        "target_weeks": tuple(horizon_periods(ORIGEN, GATE_WEEKS)),
        "candidate_digest": "a" * 64,
        "control_digest": "b" * 64,
        "dataset_digest": "c" * 64,
        "rule": dict(ACCEPTANCE_RULE),
    }
    base.update(cambios)
    return FrozenGate(**base)


def _desde_payload(payload: dict) -> dict:
    """Campos de `ProspectiveEvaluation` a partir de su payload, para re-sellar una versión torcida."""
    return {
        "disease_id": payload["disease_id"],
        "release_id": payload["release_id"],
        "gate_digest": payload["gate_digest"],
        "candidate_digest": payload["candidate_forecast_digest"],
        "control_digest": payload["control_forecast_digest"],
        "training_dataset_id": payload["training_dataset_id"],
        "training_dataset_digest": payload["training_dataset_digest"],
        "observation_dataset_id": payload["observation_dataset_id"],
        "observation_dataset_digest": payload["observation_dataset_digest"],
        "observation_source_digests": payload["observation_source_digests"],
        "observation_cutoff": (
            tuple(payload["observation_cutoff"]) if payload.get("observation_cutoff") else None
        ),
        "scheduled_weeks": tuple(tuple(p) for p in payload["scheduled_weeks"]),
        "completed_weeks": tuple(tuple(p) for p in payload["completed_weeks"]),
        "skipped_weeks": tuple((tuple(d["week"]), d["reason"]) for d in payload["skipped_weeks"]),
        "verdict": payload["verdict"],
        "scopes": payload["scopes"],
        "metrics": payload["metrics"],
        "per_week": tuple(payload["per_week"]),
    }


ROWS_POR_SEMANA = {"smape_base": 64, "smape_products": 111, "smape_national_general": 1}


def _cuerpo(gate: FrozenGate, completadas, veredicto: str) -> ProspectiveEvaluation:
    """Evaluación SEMÁNTICAMENTE coherente: la aritmética del artefacto se sostiene sola (A.3)."""
    completadas = tuple(completadas)
    n = len(completadas)
    scopes, metrics = {}, {}
    if n:
        for scope, filas in ROWS_POR_SEMANA.items():
            control = 10.0
            candidato = control if veredicto != VERDICT_FAIL else control * 2
            degradacion = (candidato - control) / control * 100.0
            scopes[scope] = {
                "rows": filas * n,
                "smape_candidate": candidato,
                "smape_control": control,
                "degradation_pct": degradacion,
                "max_degradation_pct": float(gate.rule[scope]),
                "passes": degradacion <= float(gate.rule[scope]),
            }
            metrics[scope] = {
                lado: {"products": filas, "median": {"smape": 10.0}, "flags": {}}
                for lado in ("candidate", "control")
            }
    return ProspectiveEvaluation(
        disease_id=gate.disease_id,
        release_id=gate.release_id,
        gate_digest=gate.digest(),
        candidate_digest=gate.candidate_digest,
        control_digest=gate.control_digest,
        training_dataset_id="x_dataset_congelado",
        training_dataset_digest=gate.dataset_digest,
        observation_dataset_id="x_dataset_observacion",
        observation_dataset_digest="e" * 64,
        observation_source_digests={"raw": "f" * 64},
        observation_cutoff=(max(completadas) if completadas else None),
        scheduled_weeks=gate.target_weeks,
        completed_weeks=completadas,
        skipped_weeks=(),
        verdict=veredicto,
        scopes=scopes,
        metrics=metrics,
        per_week=tuple(
            {
                "week": list(p),
                "series": 64,
                "smape_candidate": 10.0,
                "smape_control": 10.0,
            }
            for p in completadas
        ),
    )


def _evaluacion(gate: FrozenGate, **cambios) -> dict:
    """Payload de una evaluación coherente con el gate. Los tests sólo tuercen lo que prueban."""
    completadas = tuple(cambios.pop("completed_weeks", ()))
    veredicto = cambios.pop(
        "verdict", VERDICT_INCOMPLETE if len(completadas) < GATE_WEEKS else VERDICT_PASS
    )
    return {**_cuerpo(gate, completadas, veredicto).payload(), **cambios}


def _evaluacion_con_veredicto(gate: FrozenGate, veredicto: str) -> dict:
    """Evaluación COMPLETA (4/4) con el veredicto pedido, coherente consigo misma."""
    return _cuerpo(gate, gate.target_weeks, veredicto).payload()


def _status(gate: FrozenGate, evaluacion: dict | None = None, **cambios) -> dict:
    ev = evaluacion if evaluacion is not None else _evaluacion(gate)
    completadas = [tuple(p) for p in ev["completed_weeks"]]
    base = {
        "schema": STATUS_SCHEMA,
        "disease_id": gate.disease_id,
        "release_id": gate.release_id,
        "gate_digest": gate.digest(),
        "evaluation_digest": ev["evaluation_digest"],
        "observation_dataset_id": ev["observation_dataset_id"],
        "observation_dataset_digest": ev["observation_dataset_digest"],
        "verdict": ev["verdict"],
        "weeks_required": len(gate.target_weeks),
        "weeks_available": len(completadas),
        "completed_weeks": [list(p) for p in completadas],
        "target_weeks": [list(p) for p in gate.target_weeks],
    }
    base.update(cambios)
    return base


def _escribir(
    tmp_path: Path,
    gate: FrozenGate,
    status: dict | None,
    *,
    gate_digest=None,
    evaluacion: dict | None = None,
) -> Path:
    raiz = tmp_path / "publication" / gate.disease_id
    raiz.mkdir(parents=True, exist_ok=True)
    payload = {**gate.payload(), "gate_digest": gate_digest or gate.digest()}
    (raiz / GATE_FILE).write_bytes(canonical_json(payload))
    if status is not None:
        (raiz / EVALUATION_FILE).write_bytes(
            canonical_json(evaluacion if evaluacion is not None else _evaluacion(gate))
        )
        (raiz / STATUS_FILE).write_bytes(canonical_json(status))
    return tmp_path / "publication"


def _capability(tmp_path: Path, gate: FrozenGate, evaluacion: dict | None = None):
    """Capability emitida por el LOADER: es la única vía, también en las pruebas."""
    ev = evaluacion if evaluacion is not None else _evaluacion(gate)
    raiz = _escribir(tmp_path, gate, _status(gate, ev), evaluacion=ev)
    return load_declared_status(gate.disease_id, config_root_path=raiz)


# ── Carga y validación ────────────────────────────────────────────────────────────────────────
def test_el_gate_persistido_se_recomputa_y_valida(tmp_path):
    gate = _gate()
    raiz = _escribir(tmp_path, gate, _status(gate))
    cargado = load_gate(raiz / OTRO / GATE_FILE)
    assert cargado.digest() == gate.digest()
    assert cargado.target_weeks == gate.target_weeks


def test_un_gate_con_digest_declarado_falso_se_rechaza(tmp_path):
    """Aflojar un umbral y dejar el digest viejo es exactamente lo que esto impide."""
    gate = _gate()
    raiz = _escribir(tmp_path, gate, _status(gate), gate_digest="0" * 64)
    with pytest.raises(ArtifactValidationError, match="digest recomputado"):
        load_gate(raiz / OTRO / GATE_FILE)


def test_alterar_el_umbral_del_gate_mueve_su_digest_y_rompe_el_estado(tmp_path):
    gate = _gate()
    status = _status(gate)
    aflojado = _gate(rule={**ACCEPTANCE_RULE, "smape_base": 99.0})
    raiz = _escribir(tmp_path, aflojado, status)  # el estado sigue apuntando al gate original
    with pytest.raises(ArtifactValidationError, match="gate_digest"):
        load_declared_status(OTRO, config_root_path=raiz)


def test_el_estado_se_valida_contra_su_gate(tmp_path):
    gate = _gate()
    raiz = _escribir(tmp_path, gate, _status(gate))
    cap = load_declared_status(OTRO, config_root_path=raiz)
    assert cap.verdict == VERDICT_INCOMPLETE
    assert (cap.status.weeks_available, cap.status.weeks_required) == (0, GATE_WEEKS)
    assert cap.publishable is True


def test_estado_ausente(tmp_path):
    gate = _gate()
    raiz = _escribir(tmp_path, gate, None)
    with pytest.raises(ArtifactValidationError, match="no existe"):
        load_declared_status(OTRO, config_root_path=raiz)


@pytest.mark.parametrize(
    ("cambio", "patron"),
    [
        ({"disease_id": "otro"}, "disease_id"),
        ({"release_id": "otro_release_000000000000"}, "release_id"),
        ({"gate_digest": "0" * 64}, "gate_digest"),
        ({"schema": "prospective_status.v0"}, "schema"),
        ({"verdict": "CASI"}, "veredicto desconocido|veredicto contra la evaluación"),
        ({"weeks_available": 9}, "fuera de rango"),
        ({"weeks_available": -1}, "fuera de rango"),
        ({"weeks_required": 3}, "weeks_required contra las semanas del gate"),
        ({"weeks_available": 2}, "semanas completadas contra weeks_available"),
        ({"target_weeks": [[2026, 1], [2026, 2], [2026, 3], [2026, 4]]}, "semanas objetivo"),
    ],
)
def test_rechazos_del_estado(tmp_path, cambio, patron):
    gate = _gate()
    raiz = _escribir(tmp_path, gate, {**_status(gate), **cambio})
    with pytest.raises(ArtifactValidationError, match=patron):
        load_declared_status(OTRO, config_root_path=raiz)


def test_semanas_completadas_duplicadas_desordenadas_o_ajenas(tmp_path):
    gate = _gate()
    objetivo = gate.target_weeks
    casos = [
        ([objetivo[0], objetivo[0]], "repetidas"),
        ([objetivo[1], objetivo[0]], "ordenadas"),
        ([(2020, 1), objetivo[0]], "ordenadas|fuera del horizonte|anteriores al inicio"),
    ]
    for completadas, patron in casos:
        ev = _evaluacion(gate, completed_weeks=completadas)
        datos = _status(gate, ev)
        raiz = _escribir(tmp_path / patron[:6], gate, datos, evaluacion=ev)
        with pytest.raises(ArtifactValidationError, match=patron):
            load_declared_status(OTRO, config_root_path=raiz)


def test_coherencia_entre_veredicto_y_conteos(tmp_path):
    gate = _gate()
    completas = gate.target_weeks

    # INCOMPLETE con todas las semanas: contradicción con sus propios ámbitos.
    incoherente = _cuerpo(gate, completas, VERDICT_PASS).payload()
    incoherente = {**incoherente, "verdict": VERDICT_INCOMPLETE}
    incoherente["evaluation_digest"] = ProspectiveEvaluation(
        **_desde_payload(incoherente)
    ).digest()
    raiz = _escribir(tmp_path / "a", gate, _status(gate, incoherente), evaluacion=incoherente)
    with pytest.raises(
        ArtifactValidationError, match="veredicto recomputado|INCOMPLETE con todas"
    ):
        load_declared_status(OTRO, config_root_path=raiz)

    # PASS sin las semanas: tampoco.
    sin_semanas = _cuerpo(gate, (), VERDICT_PASS).payload()
    raiz = _escribir(tmp_path / "b", gate, _status(gate, sin_semanas), evaluacion=sin_semanas)
    with pytest.raises(ArtifactValidationError, match="sin ámbitos|sólo puede ser INCOMPLETE"):
        load_declared_status(OTRO, config_root_path=raiz)


def test_un_fail_no_es_publicable_pero_si_cargable(tmp_path):
    gate = _gate()
    ev = _evaluacion(gate, completed_weeks=list(gate.target_weeks))
    ev = _evaluacion_con_veredicto(gate, VERDICT_FAIL)
    raiz = _escribir(tmp_path, gate, _status(gate, ev), evaluacion=ev)
    cap = load_declared_status(OTRO, config_root_path=raiz)
    assert cap.verdict == VERDICT_FAIL
    assert cap.publishable is False


# ── Etiqueta derivada ─────────────────────────────────────────────────────────────────────────
class _Release:
    """Doble mínimo: la etiqueta sólo necesita saber si el release trae intervalos."""

    def __init__(self, uncertainty_available: bool) -> None:
        self.uncertainty_available = uncertainty_available


def _st(tmp_path: Path, verdict: str, disponibles: int):
    gate = _gate()
    if disponibles == GATE_WEEKS:
        ev = _evaluacion_con_veredicto(gate, verdict)
    else:
        ev = _evaluacion(gate, completed_weeks=gate.target_weeks[:disponibles])
    return _capability(tmp_path, gate, ev)


@pytest.mark.parametrize(
    ("verdict", "disponibles", "esperado"),
    [
        (VERDICT_INCOMPLETE, 0, "Validación prospectiva en curso (0/4 semanas)"),
        (VERDICT_INCOMPLETE, 2, "Validación prospectiva en curso (2/4 semanas)"),
        (VERDICT_PASS, 4, "Validación prospectiva superada (4/4 semanas)"),
        (VERDICT_FAIL, 4, "Validación prospectiva NO superada (4/4 semanas)"),
    ],
)
def test_la_etiqueta_sale_de_los_datos(tmp_path, verdict, disponibles, esperado):
    st = _st(tmp_path, verdict, disponibles)
    assert st.progress_label() == esperado
    assert publication_label(st, _Release(False)) == f"{esperado} · {POINT_ONLY_SUFFIX}"
    # Con intervalos disponibles, la cola point-only NO se inventa.
    assert publication_label(st, _Release(True)) == esperado


# ── Contra el release real ────────────────────────────────────────────────────────────────────
real = pytest.mark.skipif(
    not af.hay_runs(), reason="los runs sellados de C5 no están en este entorno (runs/ gitignored)"
)

ETIQUETA_VIGENTE = (
    "Validación prospectiva en curso (0/4 semanas) · pronóstico puntual sin intervalos"
)


@pytest.fixture(scope="module")
def sede(tmp_path_factory) -> Path:
    raiz = tmp_path_factory.mktemp("status")
    bundle = rf.construir(raiz).path
    destino = raiz / "releases"
    promote_release(bundle, releases_root=destino, disease_id=af.DISEASE)
    return destino


@real
def test_el_estado_declarado_del_repo_es_el_del_gate_congelado():
    cap = load_declared_status(af.DISEASE)
    assert cap.release_id == str(registry.require(af.DISEASE).artifact_source.release_id)
    assert (cap.verdict, cap.status.weeks_available, cap.status.weeks_required) == (
        VERDICT_INCOMPLETE,
        0,
        GATE_WEEKS,
    )


@real
def test_los_cuatro_puentes_muestran_la_etiqueta_exacta(sede, tmp_path):
    c = compile_release(
        disease_id=af.DISEASE,
        mode=MODE_CANDIDATE,
        releases_root=sede,
        status=load_declared_status(af.DISEASE),
    )
    assert c.label == ETIQUETA_VIGENTE
    shards = emit_shards(c, tmp_path / "staging")

    reports = (shards.root / CHANNEL_REPORTS / "report.md").read_text(encoding="utf-8")
    tableau = json.loads(
        (shards.root / CHANNEL_TABLEAU / "schema.json").read_text(encoding="utf-8")
    )
    web = json.loads((shards.root / CHANNEL_WEB / "manifest.json").read_text(encoding="utf-8"))
    know = json.loads(
        (shards.root / CHANNEL_EPIBOT / "knowledge.json").read_text(encoding="utf-8")
    )
    corpus = (shards.root / CHANNEL_EPIBOT / f"corpus/{af.DISEASE}.md").read_text(encoding="utf-8")
    manifest = json.loads((shards.root / SHARD_MANIFEST).read_text(encoding="utf-8"))

    assert ETIQUETA_VIGENTE in reports
    assert ETIQUETA_VIGENTE in corpus
    for bloque in (tableau, web, know["release"], manifest):
        estado = bloque["publication_status"]
        assert bloque["publication_label"] == ETIQUETA_VIGENTE
        assert estado["verdict"] == VERDICT_INCOMPLETE
        assert (estado["weeks_available"], estado["weeks_required"]) == (0, GATE_WEEKS)
        assert estado["gate_digest"] == load_declared_status(af.DISEASE).status.gate_digest


@real
def test_sin_estado_no_se_emite_ningun_shard(sede, tmp_path):
    """Compilar sin estado se permite; EMITIR sin él, no: el shard iría sin su condición."""
    c = compile_release(disease_id=af.DISEASE, mode=MODE_CANDIDATE, releases_root=sede)
    assert c.status is None
    with pytest.raises(ArtifactValidationError, match="sin estado prospectivo validado"):
        emit_shards(c, tmp_path / "staging")


def _evidencia_valida(gate: FrozenGate, semanas: int, veredicto: str) -> dict:
    """Ámbitos, métricas y detalle semanal con la forma cerrada que exige el loader (A.3)."""
    payload = _cuerpo(gate, gate.target_weeks[:semanas], veredicto).payload()
    return {
        "scopes": payload["scopes"],
        "metrics": payload["metrics"],
        "per_week": payload["per_week"],
        "completed_weeks": payload["completed_weeks"],
    }


def _capability_real(tmp_path: Path, **cambios):
    """Capability del padecimiento REAL, con el gate declarado y una evaluación torcida a gusto."""
    from epiforecast.publication.status import config_root

    origen = config_root() / af.DISEASE
    raiz = tmp_path / "publication" / af.DISEASE
    raiz.mkdir(parents=True, exist_ok=True)
    (raiz / GATE_FILE).write_bytes((origen / GATE_FILE).read_bytes())
    ev = json.loads((origen / EVALUATION_FILE).read_text(encoding="utf-8"))
    ev.pop("evaluation_digest")
    ev.update(cambios)
    if ev["completed_weeks"]:
        ev["observation_cutoff"] = max(tuple(p) for p in ev["completed_weeks"])
    evaluation = ProspectiveEvaluation(
        disease_id=ev["disease_id"],
        release_id=ev["release_id"],
        gate_digest=ev["gate_digest"],
        candidate_digest=ev["candidate_forecast_digest"],
        control_digest=ev["control_forecast_digest"],
        training_dataset_id=ev["training_dataset_id"],
        training_dataset_digest=ev["training_dataset_digest"],
        observation_dataset_id=ev["observation_dataset_id"],
        observation_dataset_digest=ev["observation_dataset_digest"],
        observation_source_digests=ev["observation_source_digests"],
        observation_cutoff=(
            tuple(ev["observation_cutoff"]) if ev.get("observation_cutoff") else None
        ),
        scheduled_weeks=tuple(tuple(p) for p in ev["scheduled_weeks"]),
        completed_weeks=tuple(tuple(p) for p in ev["completed_weeks"]),
        skipped_weeks=tuple((tuple(d["week"]), d["reason"]) for d in ev["skipped_weeks"]),
        verdict=ev["verdict"],
        scopes=ev["scopes"],
        metrics=ev["metrics"],
        per_week=tuple(ev["per_week"]),
    )
    payload = evaluation.payload()
    (raiz / EVALUATION_FILE).write_bytes(canonical_json(payload))
    status = json.loads((origen / STATUS_FILE).read_text(encoding="utf-8"))
    status.update(
        {
            "evaluation_digest": payload["evaluation_digest"],
            "observation_dataset_id": payload["observation_dataset_id"],
            "observation_dataset_digest": payload["observation_dataset_digest"],
            "verdict": payload["verdict"],
            "completed_weeks": payload["completed_weeks"],
            "weeks_available": len(payload["completed_weeks"]),
        }
    )
    (raiz / STATUS_FILE).write_bytes(canonical_json(status))
    return load_declared_status(af.DISEASE, config_root_path=tmp_path / "publication")


@real
def test_un_control_o_candidato_inventado_no_llega_a_la_capability(tmp_path):
    """R78-P0-4: el control es parte del congelado y ya no puede sustituirse en silencio."""
    for clave, patron in (
        ("control_forecast_digest", "control del gate"),
        ("candidate_forecast_digest", "candidato del gate"),
        ("training_dataset_digest", "dataset de entrenamiento del gate"),
    ):
        with pytest.raises(ArtifactValidationError, match=patron):
            _capability_real(tmp_path / clave, **{clave: "d" * 64})


@real
def test_el_modo_public_exige_estado_y_rechaza_un_fail(sede, monkeypatch, tmp_path):
    publicado = dataclasses.replace(registry.require(af.DISEASE), lifecycle="published")
    release_id = str(publicado.artifact_source.release_id)
    fallido = _capability_real(
        tmp_path,
        verdict=VERDICT_FAIL,
        **_evidencia_valida(load_declared_status(af.DISEASE).gate, GATE_WEEKS, VERDICT_FAIL),
    )
    monkeypatch.setattr(registry, "require", lambda _: publicado)

    # Sin estado: falla aunque el puntero apunte bien.
    with pytest.raises(ArtifactValidationError, match="exige un estado prospectivo"):
        compile_release(
            disease_id=af.DISEASE,
            mode=MODE_PUBLIC,
            releases_root=sede,
            pointer_release_id=release_id,
        )

    # Con FAIL: nunca habilita el modo público.
    with pytest.raises(ArtifactValidationError, match="no habilita publicación"):
        compile_release(
            disease_id=af.DISEASE,
            mode=MODE_PUBLIC,
            releases_root=sede,
            pointer_release_id=release_id,
            status=fallido,
        )


@real
def test_el_estado_no_toca_la_identidad_del_bundle(sede, tmp_path):
    """Cambiar el estado NO puede mover el release_id ni las filas: son identidades separadas."""
    bueno = load_declared_status(af.DISEASE)
    otro = _capability_real(
        tmp_path,
        verdict=VERDICT_PASS,
        **_evidencia_valida(bueno.gate, GATE_WEEKS, VERDICT_PASS),
    )
    a = compile_release(
        disease_id=af.DISEASE, mode=MODE_CANDIDATE, releases_root=sede, status=bueno
    )
    b = compile_release(
        disease_id=af.DISEASE, mode=MODE_CANDIDATE, releases_root=sede, status=otro
    )
    assert a.release_id == b.release_id
    assert a.rows.equals(b.rows)
    # Y la etiqueta sí cambia: es lo único que debe moverse.
    assert a.label != b.label


# ── Tipos, formas y claves (A.1) ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("cambio", "patron"),
    [
        ({"gate_digest": "ABC"}, "SHA256"),
        ({"dataset_digest": "z" * 64}, "SHA256"),
        ({"horizon": 0}, "positivo"),
        ({"horizon": True}, "entero"),
        ({"origin": [2026, 99]}, "calendario MMWR"),
        ({"target_weeks": [[2026, 27], [2026, 27]]}, "repetidas"),
        ({"acceptance_rule_max_degradation_pct": {"smape_base": 5.0}}, "faltan claves"),
        (
            {"acceptance_rule_max_degradation_pct": {**ACCEPTANCE_RULE, "otra": 1.0}},
            "no reconocidas",
        ),
        ({"control_engine": "otro_motor"}, "control_engine"),
        ({"extra": 1}, "no reconocidas"),
    ],
)
def test_rechazos_de_forma_del_gate(tmp_path, cambio, patron):
    gate = _gate()
    datos = {**gate.payload(), "gate_digest": gate.digest(), **cambio}
    raiz = tmp_path / "publication" / OTRO
    raiz.mkdir(parents=True)
    (raiz / GATE_FILE).write_bytes(canonical_json(datos))
    with pytest.raises(ArtifactValidationError, match=patron):
        load_gate(raiz / GATE_FILE)


@pytest.mark.parametrize(
    ("cambio", "patron"),
    [
        ({"weeks_available": True}, "entero"),
        ({"weeks_required": "4"}, "entero"),
        ({"completed_weeks": [[2026, 60]]}, "calendario MMWR"),
        ({"completed_weeks": [[True, 27]]}, "entero"),
        ({"extra": 1}, "no reconocidas"),
    ],
)
def test_rechazos_de_forma_del_estado(tmp_path, cambio, patron):
    gate = _gate()
    raiz = _escribir(tmp_path, gate, {**_status(gate), **cambio})
    with pytest.raises(ArtifactValidationError, match=patron):
        load_declared_status(OTRO, config_root_path=raiz)


# ── Entry point reproducible (A.1) ────────────────────────────────────────────────────────────
@real
def test_check_es_no_mutante_y_write_exige_verdad_declarada(tmp_path):
    """El estado se DERIVA; editar el JSON a mano contradice el contrato (R76-P1)."""
    from scripts.prospective_status import main

    from epiforecast.publication.status import config_root

    origen = config_root() / af.DISEASE
    vigentes = {f: (origen / f).read_bytes() for f in (GATE_FILE, EVALUATION_FILE, STATUS_FILE)}

    # --check contra lo declarado del repo: coincide y no toca nada.
    assert main([af.DISEASE, "--check"]) == 0
    for archivo, bytes_ in vigentes.items():
        assert (origen / archivo).read_bytes() == bytes_

    # --write sin declarar la verdad: se niega. Antes caía al dataset congelado en silencio.
    assert main([af.DISEASE, "--write"]) == 2

    # Copia con el gate real y un estado MENTIDO: --check falla y NO lo corrige.
    raiz = tmp_path / "publication" / af.DISEASE
    raiz.mkdir(parents=True)
    for archivo, bytes_ in vigentes.items():
        (raiz / archivo).write_bytes(bytes_)
    mentira = json.loads(vigentes[STATUS_FILE])
    mentira["verdict"] = VERDICT_PASS
    mentira["weeks_available"] = GATE_WEEKS
    mentira["completed_weeks"] = mentira["target_weeks"]
    (raiz / STATUS_FILE).write_bytes(canonical_json(mentira))
    config = str(tmp_path / "publication")
    assert main([af.DISEASE, "--check", "--config-root", config]) == 1
    assert json.loads((raiz / STATUS_FILE).read_bytes())["verdict"] == VERDICT_PASS

    # --write con la verdad declarada deja los dos archivos, byte-idénticos a los del repo.
    observacion = json.loads(vigentes[STATUS_FILE])["observation_dataset_id"]
    assert (
        main(
            [
                af.DISEASE,
                "--write",
                "--observation-dataset-id",
                observacion,
                "--config-root",
                config,
            ]
        )
        == 0
    )
    assert (raiz / STATUS_FILE).read_bytes() == vigentes[STATUS_FILE]
    assert (raiz / EVALUATION_FILE).read_bytes() == vigentes[EVALUATION_FILE]
    assert not list(raiz.glob("*.tmp")), "la escritura atómica no deja temporales"


# ── Verdad nueva: el flujo avanza y admite reemplazos (A.2) ───────────────────────────────────
def _observacion(destino: Path, training_dir: Path, semanas: list[Period], dataset_id: str) -> str:
    """Dataset de observación sintético: la historia congelada + semanas nuevas completas.

    No se descarga ningún boletín: se fabrica el snapshot que un boletín produciría, con el mismo
    carril (config/exposición) y el prefijo histórico intacto.
    """
    import csv as csvmod

    from epiforecast.runner.manifest import DatasetManifest
    from epiforecast.runner.release_contract import sha256_bytes

    origen_csv = training_dir / "epi_dataset_v2.csv"
    filas = list(csvmod.DictReader(origen_csv.open(encoding="utf-8")))
    campos = list(filas[0])
    series = sorted({(f["cve_ent"], f["sexo"]) for f in filas})
    plantilla = dict(filas[-1])
    nuevas = []
    for año, semana in semanas:
        for cve, sexo in series:
            fila = dict(plantilla)
            fila.update(
                {"cve_ent": cve, "sexo": sexo, "epi_year": str(año), "epi_week": str(semana)}
            )
            fila["y_cases"] = "7"
            nuevas.append(fila)

    destino.mkdir(parents=True, exist_ok=True)
    salida = destino / "epi_dataset_v2.csv"
    with salida.open("w", encoding="utf-8", newline="") as fh:
        escritor = csvmod.DictWriter(fh, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows([*filas, *nuevas])

    manifest_origen = DatasetManifest.read(training_dir)
    DatasetManifest(
        dataset_id=dataset_id,
        disease_id=manifest_origen.disease_id,
        digests={
            **manifest_origen.digests,
            "dataset": sha256_bytes(salida.read_bytes()),
            "raw": "9" * 64,  # boletín nuevo: la fuente cruda sí cambia
        },
        counts=dict(manifest_origen.counts),
    ).write(destino)
    return dataset_id


@real
def test_una_verdad_nueva_avanza_el_contador_sin_tocar_el_congelado(tmp_path):
    """R78-P0-1: con el dataset congelado como verdad, esto nunca pasaría de 0/4."""
    from scripts.prospective_status import derive_evaluation

    from epiforecast.publication.status import config_root
    from epiforecast.runner.manifest import dataset_dir

    gate = load_declared_status(af.DISEASE).gate
    training_id = load_declared_status(af.DISEASE).evaluation.training_dataset_id
    runs = tmp_path / "runs"
    shutil.copytree(dataset_dir(training_id), runs / training_id)

    obs_id = _observacion(
        runs / "obs_una_semana", runs / training_id, [gate.target_weeks[0]], "obs_una_semana"
    )
    evaluation, status = derive_evaluation(
        af.DISEASE,
        observation_dataset_id=obs_id,
        runs_root=runs,
        config_root_path=config_root(),
    )
    assert (status.weeks_available, status.verdict) == (1, VERDICT_INCOMPLETE)
    assert status.completed_weeks == (gate.target_weeks[0],)
    assert status.progress_label() == "Validación prospectiva en curso (1/4 semanas)"
    # El congelado no se movió: mismo gate, mismo control, mismo dataset de entrenamiento.
    assert evaluation.gate_digest == gate.digest()
    assert evaluation.control_digest == gate.control_digest
    assert evaluation.training_dataset_digest == gate.dataset_digest
    assert evaluation.observation_dataset_id == obs_id != evaluation.training_dataset_id


@real
def test_una_semana_de_reemplazo_atraviesa_loader_compilador_y_shards(tmp_path, sede):
    """R78-P0-2: W31 sustituye a W28 y el estado resultante tiene que poder cargarse y emitirse."""
    from scripts.prospective_status import derive_evaluation

    from epiforecast.publication.status import config_root
    from epiforecast.runner.manifest import dataset_dir
    from epiforecast.runner.release_reproduce import horizon_periods

    cap = load_declared_status(af.DISEASE)
    gate = cap.gate
    training_id = cap.evaluation.training_dataset_id
    runs = tmp_path / "runs"
    shutil.copytree(dataset_dir(training_id), runs / training_id)

    ventana = list(horizon_periods(gate.origin, gate.horizon))
    w27, w28, w29, w30 = gate.target_weeks
    w31 = ventana[ventana.index(w30) + 1]
    obs_id = _observacion(
        runs / "obs_con_hueco", runs / training_id, [w27, w29, w30, w31], "obs_con_hueco"
    )

    evaluation, status = derive_evaluation(
        af.DISEASE, observation_dataset_id=obs_id, runs_root=runs, config_root_path=config_root()
    )
    assert status.completed_weeks == (w27, w29, w30, w31)
    assert status.weeks_available == 4
    assert (w28, "ausente") in evaluation.skipped_weeks
    assert status.verdict in (VERDICT_PASS, VERDICT_FAIL)

    # Y el trío se carga: antes, W31 moría en el loader por no ser una semana "objetivo".
    raiz = tmp_path / "publication" / af.DISEASE
    raiz.mkdir(parents=True)
    (raiz / GATE_FILE).write_bytes((config_root() / af.DISEASE / GATE_FILE).read_bytes())
    (raiz / EVALUATION_FILE).write_bytes(canonical_json(evaluation.payload()))
    (raiz / STATUS_FILE).write_bytes(canonical_json(status.payload()))
    capability = load_declared_status(af.DISEASE, config_root_path=tmp_path / "publication")
    assert capability.status.completed_weeks == (w27, w29, w30, w31)

    if capability.publishable:
        c = compile_release(
            disease_id=af.DISEASE, mode=MODE_CANDIDATE, releases_root=sede, status=capability
        )
        shards = emit_shards(c, tmp_path / "staging")
        reports = (shards.root / CHANNEL_REPORTS / "report.md").read_text(encoding="utf-8")
        assert capability.progress_label() in reports


# ── Corte observado, duplicados y coherencia semántica (A.3) ──────────────────────────────────
@real
def test_el_snapshot_vigente_no_declara_semanas_futuras_como_ausentes(tmp_path):
    """R80-P0-1: una semana futura no es una semana ausente. Antes se registraban las 52."""
    cap = load_declared_status(af.DISEASE)
    assert cap.evaluation.observation_cutoff == (2026, 26)
    assert cap.evaluation.skipped_weeks == ()
    assert (cap.status.weeks_available, cap.status.verdict) == (0, VERDICT_INCOMPLETE)


@real
def test_con_verdad_hasta_w27_no_se_omite_ninguna_semana_futura(tmp_path):
    from scripts.prospective_status import derive_evaluation

    from epiforecast.publication.status import config_root
    from epiforecast.runner.manifest import dataset_dir

    cap = load_declared_status(af.DISEASE)
    runs = tmp_path / "runs"
    shutil.copytree(
        dataset_dir(cap.evaluation.training_dataset_id), runs / cap.evaluation.training_dataset_id
    )
    obs = _observacion(
        runs / "obs_w27",
        runs / cap.evaluation.training_dataset_id,
        [cap.gate.target_weeks[0]],
        "obs_w27",
    )
    evaluation, status = derive_evaluation(
        af.DISEASE, observation_dataset_id=obs, runs_root=runs, config_root_path=config_root()
    )
    assert evaluation.observation_cutoff == cap.gate.target_weeks[0]
    assert evaluation.skipped_weeks == ()
    assert (status.weeks_available, status.verdict) == (1, VERDICT_INCOMPLETE)


@real
def test_con_un_hueco_real_la_unica_omitida_es_esa_semana(tmp_path):
    from scripts.prospective_status import derive_evaluation

    from epiforecast.publication.status import config_root
    from epiforecast.runner.manifest import dataset_dir
    from epiforecast.runner.release_reproduce import horizon_periods

    cap = load_declared_status(af.DISEASE)
    gate = cap.gate
    runs = tmp_path / "runs"
    shutil.copytree(
        dataset_dir(cap.evaluation.training_dataset_id), runs / cap.evaluation.training_dataset_id
    )
    ventana = list(horizon_periods(gate.origin, gate.horizon))
    w27, w28, w29, w30 = gate.target_weeks
    w31 = ventana[ventana.index(w30) + 1]
    obs = _observacion(
        runs / "obs_hueco",
        runs / cap.evaluation.training_dataset_id,
        [w27, w29, w30, w31],
        "obs_hueco",
    )
    evaluation, status = derive_evaluation(
        af.DISEASE, observation_dataset_id=obs, runs_root=runs, config_root_path=config_root()
    )
    assert evaluation.observation_cutoff == w31
    assert evaluation.skipped_weeks == ((w28, "ausente"),)
    assert status.completed_weeks == (w27, w29, w30, w31)


@real
def test_un_duplicado_del_csv_se_rechaza_antes_de_construir_la_historia(tmp_path):
    """R80-P0-3: `read_base_history` los perdía al convertir a dict; ahora mueren en el frame."""
    from epiforecast.publication.prospective import check_dataset_frame
    from epiforecast.runner.manifest import dataset_dir

    origen = dataset_dir(load_declared_status(af.DISEASE).evaluation.training_dataset_id)
    csv = (origen / "epi_dataset_v2.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    duplicado = tmp_path / "epi_dataset_v2.csv"
    duplicado.write_text("".join([*csv, csv[1]]), encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match="duplicadas"):
        check_dataset_frame(duplicado, expected_series=64)
    # Y el canónico pasa.
    check_dataset_frame(origen / "epi_dataset_v2.csv", expected_series=64)


@real
@pytest.mark.parametrize(
    ("torcer", "patron"),
    [
        (lambda e: e["scopes"]["smape_base"].update({"rows": 1}), "filas del ámbito"),
        (
            lambda e: e["scopes"]["smape_base"].update({"degradation_pct": -99.0}),
            "degradation_pct",
        ),
        (lambda e: e["scopes"]["smape_base"].update({"passes": True}), "passes recomputado"),
        (lambda e: e.update({"verdict": VERDICT_PASS}), "veredicto recomputado|veredicto contra"),
        (lambda e: e["per_week"].append(dict(e["per_week"][0])), "detalle semanal"),
        (lambda e: e.update({"observation_cutoff": [2026, 27]}), "posteriores al corte"),
        (
            lambda e: e["skipped_weeks"].append({"week": [2026, 29], "reason": "porque si"}),
            "motivo de omisión desconocido",
        ),
    ],
)
def test_torcer_la_aritmetica_del_artefacto_se_rechaza_aunque_se_reselle(tmp_path, torcer, patron):
    """R80-P1: el digest sella BYTES; la coherencia interna se recomputa aparte."""
    from epiforecast.publication.status import config_root

    gate = load_declared_status(af.DISEASE).gate
    payload = _cuerpo(gate, gate.target_weeks, VERDICT_FAIL).payload()
    payload = {
        **payload,
        "training_dataset_id": load_declared_status(af.DISEASE).evaluation.training_dataset_id,
        "training_dataset_digest": gate.dataset_digest,
    }
    torcer(payload)
    payload.pop("evaluation_digest")
    reSellado = ProspectiveEvaluation(**_desde_payload(payload)).payload()  # digest recalculado

    raiz = tmp_path / "publication" / af.DISEASE
    raiz.mkdir(parents=True)
    (raiz / GATE_FILE).write_bytes((config_root() / af.DISEASE / GATE_FILE).read_bytes())
    (raiz / EVALUATION_FILE).write_bytes(canonical_json(reSellado))
    (raiz / STATUS_FILE).write_bytes(canonical_json(_status(gate, reSellado)))
    with pytest.raises(ArtifactValidationError, match=patron):
        load_declared_status(af.DISEASE, config_root_path=tmp_path / "publication")
