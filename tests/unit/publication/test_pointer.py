"""C7.5-PREP — el puntero público: preparado, inactivo y con rollback barato.

La separación que se prueba aquí es la que C7.2-A.1 introdujo: el release dice QUÉ modelos hay, el
puntero dice DÓNDE se publican. Consecuencias que deben cumplirse:

 - cambiar canales o galería NO mueve el `release_id`;
 - hacer rollback es reemplazar un puntero, no reconstruir un bundle;
 - un puntero preparado (`active=false`) no exige `published` y no puede escribir en público;
 - activarlo sí exige `lifecycle=published`.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from epiforecast import registry
from epiforecast.publication.pointer import (
    POINTER_SCHEMA,
    SUPPORTED_CHANNELS,
    check_activation,
    pointer_for,
    read_pointer,
    rollback_to,
    write_pointer,
)
from epiforecast.runner.artifact_identity import ArtifactValidationError

DISEASE = "obesidad"
REPO = Path(__file__).resolve().parents[3]


def _obesidad() -> registry.Disease:
    return registry.require(DISEASE)


# ── El registry ya declara la superficie candidata exacta ─────────────────────────────────────
def test_los_canales_candidatos_son_exactamente_los_cuatro_soportados():
    assert set(_obesidad().channels) == {"web", "epibot", "reports", "tableau"}
    assert set(_obesidad().channels) == set(SUPPORTED_CHANNELS)


def test_la_galeria_esta_apagada_y_el_lifecycle_sigue_trained():
    disease = _obesidad()
    assert disease.gallery_enabled is False
    assert disease.lifecycle == "trained"


def test_los_canales_del_carril_legacy_ya_no_se_declaran():
    """`weekly_validation`/`prospective_validation` viven en tabla_333 y el congelado, no en un release."""
    assert not {"weekly_validation", "prospective_validation"} & set(_obesidad().channels)


# ── Preparar no es publicar ───────────────────────────────────────────────────────────────────
def test_el_puntero_se_prepara_inactivo():
    p = pointer_for(_obesidad())
    assert p.active is False
    assert p.gallery_enabled is False
    assert p.lifecycle_required == "published"
    assert p.payload()["schema"] == POINTER_SCHEMA


def test_un_puntero_inactivo_no_exige_published():
    disease = _obesidad()
    assert disease.lifecycle == "trained"
    check_activation(pointer_for(disease), disease)  # no levanta


def test_activar_exige_lifecycle_published():
    disease = _obesidad()
    activo = dataclasses.replace(pointer_for(disease), active=True)
    with pytest.raises(ArtifactValidationError, match="lifecycle para activar"):
        check_activation(activo, disease)


def test_un_puntero_activo_a_otro_release_se_rechaza():
    publicado = dataclasses.replace(_obesidad(), lifecycle="published")
    activo = dataclasses.replace(pointer_for(publicado), active=True, release_id="x_release_000")
    with pytest.raises(ArtifactValidationError, match="apunta a otro release"):
        check_activation(activo, publicado)


def test_escribir_un_puntero_activo_esta_prohibido_en_preparacion(tmp_path):
    activo = dataclasses.replace(pointer_for(_obesidad()), active=True)
    with pytest.raises(ArtifactValidationError, match="escribir un puntero ACTIVO es publicar"):
        write_pointer(activo, tmp_path / "staging")


@pytest.mark.parametrize("publico", ["reports", "data", "epibot", "artifacts"])
def test_el_puntero_no_se_escribe_en_una_ruta_publica(tmp_path, publico):
    falso = tmp_path / "repo"
    (falso / publico).mkdir(parents=True)
    with pytest.raises(ArtifactValidationError, match="ruta pública"):
        write_pointer(pointer_for(_obesidad()), falso / publico, falso)


def test_round_trip_del_puntero(tmp_path):
    p = pointer_for(_obesidad())
    ruta = write_pointer(p, tmp_path / "staging")
    assert read_pointer(ruta).digest() == p.digest()
    assert json.loads(ruta.read_text(encoding="utf-8"))["active"] is False


# ── Canales inválidos ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("canales", [("weekly_validation",), ("web", "inventado"), ()])
def test_se_rechazan_canales_que_un_release_no_puede_alimentar(canales):
    disease = dataclasses.replace(_obesidad(), channels=canales)
    with pytest.raises(ArtifactValidationError):
        pointer_for(disease)


def test_un_padecimiento_sin_backend_de_release_no_tiene_puntero():
    with pytest.raises(ArtifactValidationError, match="exige backend"):
        pointer_for(registry.require("depresion"))


# ── Rollback ──────────────────────────────────────────────────────────────────────────────────
def test_el_rollback_solo_reemplaza_el_release_al_que_se_apunta():
    p = pointer_for(_obesidad())
    anterior = rollback_to(p, "obesidad_release_000000000000")
    assert anterior.release_id == "obesidad_release_000000000000"
    assert anterior.channels == p.channels
    assert anterior.gallery_enabled == p.gallery_enabled
    assert anterior.digest() != p.digest()


def test_el_rollback_a_uno_mismo_se_rechaza():
    p = pointer_for(_obesidad())
    with pytest.raises(ArtifactValidationError, match="ya apunta a ese release"):
        rollback_to(p, p.release_id)


def test_el_rollback_no_toca_ningun_bundle(tmp_path):
    """Rollback es cambiar un puntero; el release sigue siendo inmutable y no se reconstruye."""
    p = pointer_for(_obesidad())
    ruta = write_pointer(p, tmp_path / "staging")
    antes = ruta.read_bytes()
    otro = rollback_to(p, "obesidad_release_000000000000")
    assert ruta.read_bytes() == antes  # no se escribió nada al construir el rollback
    assert otro.release_id != p.release_id


# ── La consecuencia de C7.2-A.1, verificada de nuevo ──────────────────────────────────────────
@pytest.mark.parametrize(
    "politica",
    [{"channels": ("web",)}, {"gallery_enabled": True}, {"channels": ("web", "epibot")}],
)
def test_cambiar_la_politica_publica_no_mueve_el_release_id(politica):
    """Si esto fallara, apagar un canal obligaría a reconstruir modelos intactos."""
    disease = dataclasses.replace(_obesidad(), **politica)
    assert pointer_for(disease).release_id == _obesidad().artifact_source.release_id


# ── Regresión: el recorte de canales es SÓLO de Obesidad ──────────────────────────────────────
CANALES_LEGACY = (
    "web",
    "epibot",
    "reports",
    "tableau",
    "weekly_validation",
    "prospective_validation",
)


@pytest.mark.parametrize("padecimiento", ["depresion", "parkinson", "alzheimer", "dengue"])
def test_los_publicados_conservan_sus_seis_canales_y_su_galeria(padecimiento):
    """Regresión de C7.5-PREP: un `replace` global recortó los canales de LOS CINCO padecimientos.

    Los cuatro publicados alimentan `weekly_validation` y `prospective_validation` por el carril
    legacy (tabla_333 + congelado). Quitárselos no rompía ninguna prueba —nadie los afirmaba— pero
    los habría sacado de esas superficies en silencio. El recorte pertenece únicamente a Obesidad,
    cuyo release del runner no produce esos dos canales.
    """
    disease = registry.require(padecimiento)
    assert tuple(disease.channels) == CANALES_LEGACY
    assert disease.gallery_enabled is True
    assert disease.lifecycle == "published"


def test_solo_obesidad_tiene_la_superficie_recortada():
    recortados = [
        d.id
        for d in registry.get_registry().diseases
        if set(d.channels) == set(SUPPORTED_CHANNELS)
    ]
    assert recortados == [DISEASE]


def test_los_publicados_siguen_alcanzables_por_los_dos_canales_legacy():
    for canal in ("weekly_validation", "prospective_validation"):
        alcanzables = registry.published_members(canal)
        assert len(alcanzables) == 4, f"{canal}: {alcanzables}"
        assert DISEASE not in [m.lower() for m in alcanzables]
