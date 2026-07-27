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
    GATE_FILE,
    STATUS_FILE,
    STATUS_SCHEMA,
    ProspectiveStatus,
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


def _status(gate: FrozenGate, **cambios) -> dict:
    completadas = cambios.pop("completed_weeks", [])
    base = {
        "schema": STATUS_SCHEMA,
        "disease_id": gate.disease_id,
        "release_id": gate.release_id,
        "gate_digest": gate.digest(),
        "verdict": VERDICT_INCOMPLETE,
        "weeks_required": len(gate.target_weeks),
        "weeks_available": len(completadas),
        "completed_weeks": [list(p) for p in completadas],
        "target_weeks": [list(p) for p in gate.target_weeks],
    }
    base.update(cambios)
    return base


def _escribir(tmp_path: Path, gate: FrozenGate, status: dict | None, *, gate_digest=None) -> Path:
    raiz = tmp_path / "publication" / gate.disease_id
    raiz.mkdir(parents=True, exist_ok=True)
    payload = {**gate.payload(), "gate_digest": gate_digest or gate.digest()}
    (raiz / GATE_FILE).write_bytes(canonical_json(payload))
    if status is not None:
        (raiz / STATUS_FILE).write_bytes(canonical_json(status))
    return tmp_path / "publication"


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
    status = load_declared_status(OTRO, config_root_path=raiz)
    assert status.verdict == VERDICT_INCOMPLETE
    assert (status.weeks_available, status.weeks_required) == (0, GATE_WEEKS)
    assert status.publishable is True


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
        ({"verdict": "CASI"}, "veredicto desconocido"),
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
        ([(2020, 1), objetivo[0]], "ordenadas|no son objetivo"),
    ]
    for completadas, patron in casos:
        datos = _status(gate, completed_weeks=completadas)
        datos["weeks_available"] = len(completadas)
        raiz = _escribir(tmp_path / patron[:6], gate, datos)
        with pytest.raises(ArtifactValidationError, match=patron):
            load_declared_status(OTRO, config_root_path=raiz)


def test_coherencia_entre_veredicto_y_conteos(tmp_path):
    gate = _gate()
    completas = list(gate.target_weeks)
    # INCOMPLETE con todas las semanas: contradicción.
    datos = _status(gate, completed_weeks=completas)
    datos["weeks_available"] = len(completas)
    raiz = _escribir(tmp_path / "a", gate, datos)
    with pytest.raises(ArtifactValidationError, match="INCOMPLETE con todas las semanas"):
        load_declared_status(OTRO, config_root_path=raiz)

    # PASS sin las semanas: tampoco.
    raiz = _escribir(tmp_path / "b", gate, _status(gate, verdict=VERDICT_PASS))
    with pytest.raises(ArtifactValidationError, match="PASS exige las 4 semanas"):
        load_declared_status(OTRO, config_root_path=raiz)


def test_un_fail_no_es_publicable_pero_si_cargable(tmp_path):
    gate = _gate()
    datos = _status(gate, verdict=VERDICT_FAIL, completed_weeks=list(gate.target_weeks))
    datos["weeks_available"] = len(gate.target_weeks)
    raiz = _escribir(tmp_path, gate, datos)
    status = load_declared_status(OTRO, config_root_path=raiz)
    assert status.verdict == VERDICT_FAIL
    assert status.publishable is False


# ── Etiqueta derivada ─────────────────────────────────────────────────────────────────────────
class _Release:
    """Doble mínimo: la etiqueta sólo necesita saber si el release trae intervalos."""

    def __init__(self, uncertainty_available: bool) -> None:
        self.uncertainty_available = uncertainty_available


def _st(verdict: str, disponibles: int) -> ProspectiveStatus:
    gate = _gate()
    return ProspectiveStatus(
        disease_id=OTRO,
        release_id=OTRO_RELEASE,
        gate_digest=gate.digest(),
        verdict=verdict,
        weeks_required=GATE_WEEKS,
        weeks_available=disponibles,
        completed_weeks=gate.target_weeks[:disponibles],
        target_weeks=gate.target_weeks,
    )


@pytest.mark.parametrize(
    ("verdict", "disponibles", "esperado"),
    [
        (VERDICT_INCOMPLETE, 0, "Validación prospectiva en curso (0/4 semanas)"),
        (VERDICT_INCOMPLETE, 2, "Validación prospectiva en curso (2/4 semanas)"),
        (VERDICT_PASS, 4, "Validación prospectiva superada (4/4 semanas)"),
        (VERDICT_FAIL, 4, "Validación prospectiva NO superada (4/4 semanas)"),
    ],
)
def test_la_etiqueta_sale_de_los_datos(verdict, disponibles, esperado):
    st = _st(verdict, disponibles)
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
    status = load_declared_status(af.DISEASE)
    assert status.release_id == str(registry.require(af.DISEASE).artifact_source.release_id)
    assert (status.verdict, status.weeks_available, status.weeks_required) == (
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
        assert estado["gate_digest"] == load_declared_status(af.DISEASE).gate_digest


@real
def test_sin_estado_no_se_emite_ningun_shard(sede, tmp_path):
    """Compilar sin estado se permite; EMITIR sin él, no: el shard iría sin su condición."""
    c = compile_release(disease_id=af.DISEASE, mode=MODE_CANDIDATE, releases_root=sede)
    assert c.status is None
    with pytest.raises(ArtifactValidationError, match="sin estado prospectivo validado"):
        emit_shards(c, tmp_path / "staging")


@real
def test_un_estado_de_otro_release_o_padecimiento_se_rechaza(sede):
    bueno = load_declared_status(af.DISEASE)
    for cambio, patron in (
        ({"release_id": "obesidad_release_000000000000"}, "release_id del estado"),
        ({"disease_id": "otro"}, "disease_id del estado"),
    ):
        with pytest.raises(ArtifactValidationError, match=patron):
            compile_release(
                disease_id=af.DISEASE,
                mode=MODE_CANDIDATE,
                releases_root=sede,
                status=dataclasses.replace(bueno, **cambio),
            )


@real
def test_el_modo_public_exige_estado_y_rechaza_un_fail(sede, monkeypatch):
    publicado = dataclasses.replace(registry.require(af.DISEASE), lifecycle="published")
    monkeypatch.setattr(registry, "require", lambda _: publicado)
    release_id = str(publicado.artifact_source.release_id)
    bueno = load_declared_status(af.DISEASE)

    # Sin estado: falla aunque el puntero apunte bien.
    with pytest.raises(ArtifactValidationError, match="exige un estado prospectivo"):
        compile_release(
            disease_id=af.DISEASE,
            mode=MODE_PUBLIC,
            releases_root=sede,
            pointer_release_id=release_id,
        )

    # Con FAIL: nunca habilita el modo público.
    fallido = dataclasses.replace(
        bueno,
        verdict=VERDICT_FAIL,
        weeks_available=GATE_WEEKS,
        completed_weeks=bueno.target_weeks,
    )
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
    otro = dataclasses.replace(
        bueno, verdict=VERDICT_PASS, weeks_available=GATE_WEEKS, completed_weeks=bueno.target_weeks
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
