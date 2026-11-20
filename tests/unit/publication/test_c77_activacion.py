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
        "otitis media aguda",
        "faringitis y amigdalitis estreptococicas",
        "conjuntivitis",
        "amebiasis intestinal",
        "otras infecciones intestinales debidas a protozoarios",
        "enterobiasis",
        "ascariasis",
        "otras salmonelosis",
        "intoxicacion alimentaria bacteriana",
        "giardiasis",
        "fiebre tifoidea",
        "shigelosis",
        "escabiosis",
        "erisipela",
        "escarlatina",
        "parotiditis infecciosa",
        "varicela",
        "intoxicacion por picadura de alacran",
        "peaton lesionado en accidente de transporte",
        "accidente de transporte en vehiculos con motor",
        "candidiasis urogenital",
        "hepatitis virica a",
        "hepatitis virica b",
        "hepatitis virica c",
        "quemaduras",
        "mordeduras por perro",
        "mordeduras por otros mamiferos",
        "fiebre reumatica aguda",
        "insuficiencia venosa periferica",
        "displasia cervical leve y moderada",
        "displasia cervical severa y cacu in situ",
        "hiperplasia de la prostata",
        "edema proteinuria y trastornos hipertensivos en el embarazo parto y puerperio",
        "diabetes mellitus en el embarazo",
        "desnutricion leve",
        "desnutricion moderada",
        "desnutricion severa",
        "otras hepatitis viricas",
        "brucelosis",
        "leptospirosis",
        "otras helmintiasis",
        "enteritis debida a rotavirus",
        "efectos del calor y de la luz",
        "absceso hepatico amebiano",
        "bocio endemico",
        "tos ferina",
        "toxoplasmosis",
        "teniasis",
        "cisticercosis",
        "triquinosis",
        "mal del pinto",
        "sindrome coqueluchoide",
        "fiebre paratifoidea",
        "conjuntivitis epidemica aguda hemorragica",
        "tracoma",
        "sindrome meningeo",
        "intoxicacion por monoxido de carbono",
        "hipotermia",
        "intoxicacion por plaguicidas",
        "vulvovaginitis",
        "sifilis adquirida",
        "tetanos",
        "viruela simica",
        "infeccion por virus de papiloma humano",
        "infeccion gonococica del tracto genitourinario",
        "linfogranuloma venereo por clamidias",
        "chancro blando",
        "herpes genital",
        "tricomoniasis urogenital",
        "paralisis flacida aguda menores de 15 anos",
        "infeccion asociada a la atencion de la salud",
        "intoxicacion aguda por alcohol",
        "enfermedad alcoholica del higado",
        "anencefalia",
        "encefalocele",
        "microcefalia",
        "espina bifida",
        "labio y paladar hendido",
        "mordedura de arana viuda negra",
        "mordedura de arana violinista",
        "mordedura de otras aranas",
        "picadura de abeja",
        "picadura de avispa",
        "picadura por otros artropodos",
        "picadura o intoxicacion por otros animales ponzonosos",
        "mordedura por serpiente de cascabel",
        "mordedura por serpiente coral",
        "mordedura por otras serpientes",
        "cirrosis hepatica alcoholica",
        "enfermedad por virus chikungunya",
        "envenenamiento autoinfligido intencionalmente por analgesicos no narcoticos antipireticos y antirreumaticos",
        "envenenamiento autoinfligido intencionalmente por drogas antiepilepticas sedantes hipnoticas antiparkinsonianas y psicotropicas",
        "lesion autoinfligida intencionalmente por ahorcamiento estrangulamiento o sofocacion",
        "lesion autoinfligida intencionalmente por disparo de arma corta",
        "lesion autoinfligida intencionalmente por objeto cortante",
        "lesion autoinfligida intencionalmente al saltar desde un lugar elevado",
        "historia personal de lesion autoinfligida intencionalmente intento de suicidio",
        "otros sintomas y signos que involucran el estado emocional ideacion suicida",
        "violencia intrafamiliar",
        "tuberculosis otras formas",
        "tripanosomiasis americana enfermedad de chagas aguda",
        "tifo murino",
        "sifilis congenita",
        "eventos supuestamente asociados a la vacunacion esavi",
        "meningitis meningococica",
        "enfermedad invasiva por neumococo",
        "infecciones invasivas por haemophilus influenzae",
        "herida por arma de fuego",
        "tripanosomiasis americana enfermedad de chagas cronica",
        "infeccion por el virus de la inmunodeficiencia humana",
        "meningitis tuberculosa",
        "tuberculosis respiratoria",
        "lepra",
        "fiebre manchada",
        "otras rickettsiosis",
        "leishmaniasis cutanea",
        "paludismo por plasmodium vivax",
    )
    assert c.releases["obesidad"] == (_OBESIDAD, _RELEASE)
    assert c.releases["sifilis adquirida"] == (
        "sifilis_adquirida_a51",
        "sifilis_adquirida_a51_release_a18527def134",
    )
    assert sorted(i for i, _ in c.releases.values()) == [
        "abeja_u604",
        "absceso_hepatico_a064",
        "ahorcamiento_x70",
        "alacran_t63",
        "alcoholica_higado_k70",
        "alimentaria_a05",
        "amebiasis_a06",
        "anencefalia_q00",
        "anorexia_f50",
        "ascariasis_b77",
        "asma_j45",
        "avispa_u605",
        "bocio_e01",
        "brucelosis_a23",
        "calor_t67",
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
        "candidiasis_b37",
        "cerebrovascular_i60",
        "chagas_aguda_b570",
        "chagas_cronica_b572",
        "chancro_blando_a57",
        "chikungunya_a920",
        "cirrosis_alcoholica_k703",
        "cisticercosis_b69",
        "conjuntivitis_h10",
        "conjuntivitis_hemorragica_b303",
        "coqueluchoide_u99",
        "desnutricion_leve_e441",
        "desnutricion_moderada_e440",
        "desnutricion_severa_e40",
        "diabetes_t1",
        "diabetes_t2",
        "disparo_arma_corta_x72",
        "displasia_leve_n87",
        "displasia_severa_n87",
        "embarazo_diabetes_o24",
        "embarazo_hipertensivos_o10",
        "encefalocele_q01",
        "enterobiasis_b80",
        "envenenamiento_analgesicos_x60",
        "envenenamiento_psicotropicos_x61",
        "erisipela_a46",
        "esavi_y58",
        "escabiosis_b86",
        "escarlatina_a38",
        "espina_bifida_q05",
        "faringitis_j02",
        "fiebre_manchada_a770",
        "giardiasis_a071",
        "gingivitis_k05",
        "gonococica_a54",
        "haemophilus_a41",
        "helmintiasis_b65",
        "hepatitis_a_b15",
        "hepatitis_b_b16",
        "hepatitis_c_b17",
        "herida_arma_fuego_w32",
        "herpes_genital_a600",
        "hiperplasia_prostata_n40",
        "hipertension_i10",
        "hipotermia_t68",
        "iaas_sc",
        "ideacion_suicida_r458",
        "intento_suicidio_z915",
        "intestinales_a04",
        "intox_alcohol_f100",
        "ira_j00",
        "isquemica_i20",
        "ivp_i87",
        "ivu_n39",
        "labio_paladar_q35",
        "leishmaniasis_cutanea_b551",
        "lepra_a30",
        "leptospirosis_a27",
        "leucemia_c91",
        "linfogranuloma_a55",
        "linfoma_hodgkin_c81",
        "linfoma_no_hodgkin_c82",
        "mal_del_pinto_a67",
        "meningitis_tuberculosa_a170",
        "meningococica_a39",
        "microcefalia_q02",
        "monoxido_t58",
        "mordedura_cascabel_u600",
        "mordedura_coral_u601",
        "mordedura_mamiferos_w55",
        "mordedura_otras_serpientes_t630",
        "mordedura_perro_w54",
        "neumococo_a40",
        "neumonias_j12",
        "obesidad",
        "objeto_cortante_x78",
        "otitis_h65",
        "otras_aranas_t633",
        "otras_hepatitis_b17",
        "otras_rickettsiosis_a79",
        "otros_artropodos_t634",
        "otros_ponzonosos_t631",
        "paludismo_vivax_b51",
        "paralisis_flacida_u98",
        "paratifoidea_a011",
        "parotiditis_b26",
        "peaton_v01",
        "plaguicidas_t60",
        "protozoarios_a07",
        "quemaduras_t20",
        "reumatica_i00",
        "rotavirus_a080",
        "salmonelosis_a02",
        "salto_lugar_elevado_x80",
        "shigelosis_a03",
        "sifilis_adquirida_a51",
        "sifilis_congenita_a50",
        "sindrome_meningeo_g00",
        "teniasis_b68",
        "tetanos_a34",
        "tifo_murino_a752",
        "tifoidea_a01",
        "tos_ferina_a37",
        "toxoplasmosis_b58",
        "tracoma_a71",
        "tricomoniasis_a590",
        "triquinosis_b75",
        "tuberculosis_otras_formas_a171",
        "tuberculosis_respiratoria_a15",
        "ulceras_k25",
        "varicela_b01",
        "vehiculos_v20",
        "vih_b20",
        "violencia_intrafamiliar_y07",
        "violinista_u603",
        "viruela_simica_b04",
        "viuda_negra_u602",
        "vph_b97",
        "vulvovaginitis_n76",
    ]
    # La paridad de corte cubre a los ochenta y dos; las series legacy siguen siendo 3×111 + 99.
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
        "Infecciones respiratorias agudas": 42,
        "Infección de vías urinarias": 42,
        "Gingivitis y enfermedad periodontal": 42,
        "Asma": 42,
        "Úlceras, gastritis y duodenitis": 42,
        "Tumor maligno de la mama": 42,
        "Tumor maligno del cuello del útero": 42,
        "Tumor maligno de la próstata": 42,
        "Tumor maligno del cuerpo del útero": 42,
        "Tumor maligno del ovario": 42,
        "Tumor maligno de tráquea, bronquios y pulmón": 42,
        "Tumor maligno del estómago": 42,
        "Tumor maligno del colon y recto": 42,
        "Tumor maligno del hígado y de las vías biliares intrahepáticas": 42,
        "Linfoma de Hodgkin": 42,
        "Linfoma no Hodgkin": 42,
        "Leucemia": 42,
        "Tumor maligno del esófago": 42,
        "Tumor maligno del páncreas": 42,
        "Tumores malignos del encéfalo y otras partes del sistema nervioso central": 42,
        "Tumores malignos de los huesos y de los cartílagos articulares": 42,
        "Tumor maligno del riñón": 42,
        "Neumonías y bronconeumonías": 42,
        "Otitis media aguda": 42,
        "Faringitis y amigdalitis estreptocócicas": 42,
        "Conjuntivitis": 42,
        "Amebiasis intestinal": 42,
        "Otras infecciones intestinales debidas a protozoarios": 42,
        "Ascariasis": 42,
        "Otras salmonelosis": 42,
        "Intoxicación alimentaria bacteriana": 42,
        "Fiebre tifoidea": 42,
        "Shigelosis": 42,
        "Escabiosis": 42,
        "Erisipela": 42,
        "Escarlatina": 42,
        "Parotiditis infecciosa": 42,
        "Varicela": 42,
        "Peatón lesionado en accidente de transporte": 42,
        "Accidente de transporte en vehículos con motor": 42,
        "Candidiasis urogenital": 42,
        "Hepatitis vírica A": 42,
        "Hepatitis vírica C": 42,
        "Quemaduras": 42,
        "Insuficiencia venosa periférica": 42,
        "Displasia cervical leve y moderada": 42,
        "Displasia cervical severa y CaCu in situ": 42,
        "Hiperplasia de la próstata": 42,
        "Edema, proteinuria y trastornos hipertensivos en el embarazo, parto y puerperio": 42,
        "Diabetes mellitus en el embarazo": 42,
        "Desnutrición leve": 42,
        "Otras hepatitis víricas": 42,
        "Efectos del calor y de la luz": 42,
        "Brucelosis": 42,
        "Fiebre reumática aguda": 42,
        "Bocio endémico": 42,
        "Hepatitis vírica B": 42,
        "Enteritis debida a rotavirus": 42,
        "Absceso hepático amebiano": 42,
        "Leptospirosis": 42,
        "Otras helmintiasis": 42,
        "Desnutrición moderada": 42,
        "Desnutrición severa": 42,
        "Enterobiasis": 42,
        "Giardiasis": 42,
        "Fiebre paratifoidea": 42,
        "Mal del pinto": 42,
        "Vulvovaginitis": 42,
        "Tos ferina": 42,
        "Síndrome coqueluchoide": 42,
        "Síndrome meníngeo": 42,
        "Intoxicación por monóxido de carbono": 42,
        "Intoxicación por plaguicidas": 42,
        "Sífilis adquirida": 42,
        "Intoxicación por picadura de alacrán": 42,
        "Mordeduras por perro": 42,
        "Mordeduras por otros mamíferos": 42,
        "Toxoplasmosis": 42,
        "Teniasis": 42,
        "Cisticercosis": 42,
        "Triquinosis": 42,
        "Conjuntivitis epidémica aguda hemorrágica": 42,
        "Tracoma": 42,
        "Hipotermia": 42,
        "Tétanos": 42,
        "Viruela símica": 42,
        "Infección por virus de papiloma humano": 42,
        "Infección gonocócica del tracto genitourinario": 42,
        "Linfogranuloma venéreo por Clamidias": 42,
        "Chancro blando": 42,
        "Herpes genital": 42,
        "Tricomoniasis urogenital": 42,
        "Parálisis flácida aguda (menores de 15 años)": 42,
        "Infección asociada a la atención de la salud": 42,
        "Intoxicación aguda por alcohol": 42,
        "Enfermedad alcohólica del hígado": 42,
        "Anencefalia": 42,
        "Encefalocele": 42,
        "Microcefalia": 42,
        "Espina bífida": 42,
        "Labio y paladar hendido": 42,
        "Mordedura de araña viuda negra": 42,
        "Mordedura de araña violinista": 42,
        "Mordedura de otras arañas": 42,
        "Picadura de abeja": 42,
        "Picadura de avispa": 42,
        "Picadura por otros artrópodos": 42,
        "Picadura o intoxicación por otros animales ponzoñosos": 42,
        "Mordedura por serpiente de cascabel": 42,
        "Mordedura por serpiente coral": 42,
        "Mordedura por otras serpientes": 42,
        "Cirrosis hepática alcohólica": 42,
        "Enfermedad por virus Chikungunya": 42,
        "Envenenamiento autoinfligido intencionalmente por analgésicos no narcóticos, antipiréticos y antirreumáticos": 42,
        "Envenenamiento autoinfligido intencionalmente por drogas antiepilépticas, sedantes, hipnóticas, antiparkinsonianas y psicotrópicas": 42,
        "Lesión autoinfligida intencionalmente por ahorcamiento, estrangulamiento o sofocación": 42,
        "Lesión autoinfligida intencionalmente por disparo de arma corta": 42,
        "Lesión autoinfligida intencionalmente por objeto cortante": 42,
        "Lesión autoinfligida intencionalmente al saltar desde un lugar elevado": 42,
        "Historia personal de lesión autoinfligida intencionalmente (intento de suicidio)": 42,
        "Otros síntomas y signos que involucran el estado emocional (ideación suicida)": 42,
        "Violencia intrafamiliar": 42,
        "Tuberculosis otras formas": 42,
        "Tripanosomiasis americana (enfermedad de Chagas) aguda": 42,
        "Tifo murino": 42,
        "Sífilis congénita": 42,
        "Eventos supuestamente asociados a la vacunación (ESAVI)": 42,
        "Meningitis meningocócica": 42,
        "Enfermedad invasiva por neumococo": 42,
        "Infecciones invasivas por Haemophilus influenzae": 42,
        "Herida por arma de fuego": 42,
        "Tripanosomiasis americana (enfermedad de Chagas) crónica": 42,
        "Infección por el virus de la inmunodeficiencia humana": 42,
        "Tuberculosis respiratoria": 42,
        "Meningitis tuberculosa": 42,
        "Lepra": 42,
        "Otras rickettsiosis": 42,
        "Fiebre manchada": 42,
        "Leishmaniasis cutánea": 42,
        "Paludismo por Plasmodium vivax": 42,
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
    assert len(resultado.problemas) == 148
    assert any("release obesidad" in p for p in resultado.problemas)
    assert any("release diabetes tipo i:" in p for p in resultado.problemas)
    assert any("release sifilis adquirida:" in p for p in resultado.problemas)


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
