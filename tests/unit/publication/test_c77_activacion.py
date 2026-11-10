"""C7.7 — activación de un publicado del runner: contrato semanal, puntero activo y CLI.

Ninguna de estas pruebas necesita datos (runs/, DVC ni bundle real): el CI corre en un clon limpio
con presupuesto EXACTO de skips, así que todo lo que aquí se afirma es estructural o sintético.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from scripts import publication_activate as activacion

from epiforecast import registry
from epiforecast.publication import pointer as pt
from epiforecast.publication.contratos_datos import (
    ContratoCobertura,
    revisa_consolidado,
    revisa_releases,
)
from epiforecast.publication.errores import StagingError
from epiforecast.runner.artifact_identity import ArtifactValidationError
from tests.unit.registry_pre_c77 import registry_pre_c77, yaml_pre_c77

_OBESIDAD = "obesidad"
_RELEASE = "obesidad_release_2517e7858901"


# ── Contrato semanal: paridad para todos, artefactos legacy sólo para el carril legacy ──────────
def test_el_contrato_separa_legacy_de_release():
    c = ContratoCobertura.canonico()
    assert c.neuro == ("depresion", "parkinson", "alzheimer")
    assert c.conteo == ("dengue",)
    assert c.release == (
        "obesidad",
        "anorexia f50",
        "diabetes tipo i",
        "diabetes tipo ii",
        "hipertension arterial",
        "enfermedad isquemica del corazon",
        "enfermedad cerebrovascular",
        "infecciones intestinales por otros organismos y las mal definidas",
        "infecciones respiratorias agudas",
        "infeccion de vias urinarias",
        "gingivitis y enfermedad periodontal",
        "asma",
        "ulceras gastritis y duodenitis",
        "tumor maligno de la mama",
        "tumor maligno del cuello del utero",
        "tumor maligno de la prostata",
        "tumor maligno del cuerpo del utero",
        "tumor maligno del ovario",
        "tumor maligno de traquea bronquios y pulmon",
        "tumor maligno del estomago",
        "tumor maligno del colon y recto",
        "tumor maligno del higado y de las vias biliares intrahepaticas",
        "linfoma de hodgkin",
        "linfoma no hodgkin",
        "leucemia",
        "tumor maligno del esofago",
        "tumor maligno del pancreas",
        "tumores malignos del encefalo y otras partes del sistema nervioso central",
        "tumores malignos de los huesos y de los cartilagos articulares",
        "tumor maligno del rinon",
        "neumonias y bronconeumonias",
    )
    assert c.releases["obesidad"] == (_OBESIDAD, _RELEASE)
    assert sorted(i for i, _ in c.releases.values()) == [
        "anorexia_f50",
        "asma_j45",
        "cancer_colon_c18",
        "cancer_cuello_utero_c53",
        "cancer_cuerpo_utero_c54",
        "cancer_encefalo_c70",
        "cancer_esofago_c15",
        "cancer_estomago_c16",
        "cancer_higado_c22",
        "cancer_huesos_c40",
        "cancer_mama_c50",
        "cancer_ovario_c56",
        "cancer_pancreas_c26",
        "cancer_prostata_c61",
        "cancer_pulmon_c33",
        "cancer_rinon_c64",
        "cerebrovascular_i60",
        "diabetes_t1",
        "diabetes_t2",
        "gingivitis_k05",
        "hipertension_i10",
        "intestinales_a04",
        "ira_j00",
        "isquemica_i20",
        "ivu_n39",
        "leucemia_c91",
        "linfoma_hodgkin_c81",
        "linfoma_no_hodgkin_c82",
        "neumonias_j12",
        "obesidad",
        "ulceras_k25",
    ]
    # La paridad de corte cubre a los treinta y uno; las series legacy siguen siendo 3×111 + 99.
    assert c.padecimientos == (*c.legado, *c.release)
    assert c.legado == ("depresion", "parkinson", "alzheimer", "dengue")
    assert len(c.claves_esperadas()) == 432


def test_un_publicado_del_runner_no_tiene_series_legacy():
    with pytest.raises(StagingError, match="release del runner"):
        ContratoCobertura.canonico().productos("Obesidad")


def _consolidado(ruta: Path, cortes: dict[str, int]) -> Path:
    filas = ["Anio,Semana,Entidad,Padecimiento"]
    for pad, ultima in cortes.items():
        for semana in range(ultima - 1, ultima + 1):
            for entidad in ("Aguascalientes", "México"):
                filas.append(f'2026,{semana},{entidad},"{pad}"')
    ruta.write_text("\n".join(filas) + "\n", encoding="utf-8")
    return ruta


def _contrato_pequeno() -> ContratoCobertura:
    return dataclasses.replace(
        ContratoCobertura.canonico(),
        entidades=("aguascalientes", "mexico"),
        alias={},
        profundidad_minima=2,
    )


def test_la_paridad_de_corte_incluye_al_publicado_del_runner(tmp_path):
    contrato = _contrato_pequeno()
    pads = {"Depresión": 42, "Parkinson": 42, "Alzheimer": 42, "Dengue": 42}
    pads |= {"Anorexia F50": 42, "Diabetes tipo I": 42, "Diabetes tipo II": 42}
    pads |= {
        "Hipertensión arterial": 42,
        "Enfermedad isquémica del corazón": 42,
        "Enfermedad cerebrovascular": 42,
        "Infecciones intestinales por otros organismos y las mal definidas": 42,
        "Infección de vías urinarias": 42,
        "Úlceras, gastritis y duodenitis": 42,
        "Infecciones respiratorias agudas": 42,
        "Gingivitis y enfermedad periodontal": 42,
        "Asma": 42,
        "Tumor maligno de la mama": 42,
        "Tumor maligno del cuello del útero": 42,
        "Tumor maligno del riñón": 42,
        "Neumonías y bronconeumonías": 42,
        "Tumor maligno de la próstata": 42,
        "Tumores malignos de los huesos y de los cartílagos articulares": 42,
        "Tumor maligno del hígado y de las vías biliares intrahepáticas": 42,
        "Tumor maligno del esófago": 42,
        "Tumor maligno de tráquea, bronquios y pulmón": 42,
        "Tumor maligno del estómago": 42,
        "Tumor maligno del colon y recto": 42,
        "Linfoma de Hodgkin": 42,
        "Linfoma no Hodgkin": 42,
        "Leucemia": 42,
        "Tumor maligno del páncreas": 42,
        "Tumores malignos del encéfalo y otras partes del sistema nervioso central": 42,
        "Tumor maligno del cuerpo del útero": 42,
        "Tumor maligno del ovario": 42,
    }
    rezagada = _consolidado(tmp_path / "a.csv", {**pads, "Obesidad": 27})
    resultado = revisa_consolidado(rezagada, contrato, contrato.padecimientos)
    assert not resultado.pasa
    assert any("corte dispar" in p for p in resultado.problemas)

    alineada = _consolidado(tmp_path / "b.csv", {**pads, "Obesidad": 42})
    assert revisa_consolidado(alineada, contrato, contrato.padecimientos).pasa


def test_un_publicado_del_runner_ausente_del_consolidado_falla(tmp_path):
    contrato = _contrato_pequeno()
    sin = _consolidado(tmp_path / "c.csv", {"Depresión": 42, "Dengue": 42})
    problemas = revisa_consolidado(sin, contrato, contrato.padecimientos).problemas
    assert any("obesidad" in p for p in problemas)


def test_revisa_releases_falla_cerrado_sin_bundle_ni_estado(tmp_path):
    resultado = revisa_releases(tmp_path, ContratoCobertura.canonico())
    assert not resultado.pasa
    assert len(resultado.problemas) == 31
    assert any("release obesidad" in p for p in resultado.problemas)
    assert any("release diabetes tipo i:" in p for p in resultado.problemas)


def test_sin_publicados_del_runner_revisa_releases_no_exige_nada(tmp_path):
    contrato = dataclasses.replace(ContratoCobertura.canonico(), release=(), releases={})
    assert revisa_releases(tmp_path, contrato).pasa


def test_el_contrato_del_registry_pre_c77_no_tiene_release(tmp_path):
    ruta = tmp_path / "padecimientos.yaml"
    ruta.write_text(yaml_pre_c77(), encoding="utf-8")
    catalogo = (
        Path(__file__).resolve().parents[3] / "config/geografia/entidades_mx.csv"
    ).read_text(encoding="utf-8")
    c = ContratoCobertura.desde_catalogo(catalogo, registro=registry.load_registry(ruta))
    assert c.release == () and c.padecimientos == c.legado


# ── Puntero activo ───────────────────────────────────────────────────────────────────────────────
def test_el_puntero_activo_se_escribe_en_su_sede_declarativa(tmp_path):
    disease = registry.require(_OBESIDAD)
    puntero = pt.pointer_for(disease, active=True)
    destino = pt.write_active_pointer(puntero, disease, config_root_path=tmp_path)
    assert destino == tmp_path / _OBESIDAD / pt.POINTER_FILE
    leido = pt.read_pointer(destino)
    assert leido == puntero and leido.active
    assert leido.channels == ("epibot", "reports", "web")


def test_un_puntero_inactivo_no_se_activa_por_este_escritor(tmp_path):
    disease = registry.require(_OBESIDAD)
    with pytest.raises(ArtifactValidationError, match="sólo activa"):
        pt.write_active_pointer(pt.pointer_for(disease), disease, config_root_path=tmp_path)


def test_un_puntero_que_no_es_el_del_registry_se_rechaza(tmp_path):
    disease = registry.require(_OBESIDAD)
    otro = dataclasses.replace(
        pt.pointer_for(disease, active=True), release_id="obesidad_release_x"
    )
    with pytest.raises(ArtifactValidationError):
        pt.write_active_pointer(otro, disease, config_root_path=tmp_path)
    assert not (tmp_path / _OBESIDAD).exists()


def test_activar_sin_published_falla_antes_de_escribir(tmp_path):
    with registry_pre_c77():
        disease = registry.require(_OBESIDAD)
        with pytest.raises(ArtifactValidationError):
            pt.write_active_pointer(
                pt.pointer_for(disease, active=True), disease, config_root_path=tmp_path
            )
    assert not (tmp_path / _OBESIDAD).exists()


def test_el_puntero_versionado_coincide_con_el_registry():
    ruta = pt.declared_pointer_path(_OBESIDAD)
    assert ruta.as_posix().endswith("config/publication/obesidad/public_release_pointer.json")
    assert pt.read_pointer(ruta) == pt.pointer_for(registry.require(_OBESIDAD), active=True)


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────
def test_el_cli_exige_published(tmp_path, capsys):
    with registry_pre_c77():
        rc = activacion.main([_OBESIDAD, "--out", "runs/publication_test", "--check"])
    assert rc == 1
    assert "lifecycle" in capsys.readouterr().err


def test_el_cli_solo_compila_bajo_runs(tmp_path):
    with pytest.raises(ArtifactValidationError, match="runs/"):
        activacion._check_output(tmp_path)


def test_el_cli_rechaza_otra_cosa_que_un_runner_release(capsys):
    rc = activacion.main(["dengue", "--out", "runs/publication_test", "--check"])
    assert rc == 1
    salida = capsys.readouterr().err
    assert "dengue" in salida.lower()
    assert json.dumps({}) not in salida
