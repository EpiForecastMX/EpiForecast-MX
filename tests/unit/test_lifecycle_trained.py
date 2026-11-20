"""C7.7 — Obesidad publicada DESDE su release, en canales exactos; F50 sigue invisible.

Antes (F2/C5.6) este archivo probaba que `trained` no publica. El 4-nov-2026 el autor dio el OK
formal y Obesidad pasó a `published`: lo que ahora se fija es CÓMO está publicada —sólo desde el
release sellado, sólo en web/epibot/reports, sin galería— y que el carril legacy no la absorba.
"""

from __future__ import annotations

from epiforecast import registry

_OBESIDAD = "obesidad"
_LEGACY = ["Depresión", "Parkinson", "Alzheimer", "Dengue"]


def test_obesidad_esta_published_desde_su_release():
    spec = registry.require(_OBESIDAD)
    assert spec.lifecycle == "published"
    assert spec.is_release_backed
    assert spec.artifact_source.release_id == "obesidad_release_2517e7858901"


def test_canales_exactos_sin_tableau_ni_galeria():
    spec = registry.require(_OBESIDAD)
    assert spec.channels == ("web", "epibot", "reports")
    assert spec.gallery_enabled is False
    for canal in ("web", "epibot", "reports"):
        assert _OBESIDAD in [n.lower() for n in registry.published_members(channel=canal)]
    assert _OBESIDAD not in [n.lower() for n in registry.published_members(channel="tableau")]


def test_el_carril_legacy_no_cambia():
    assert [d.data_name for d in registry.legacy_published()] == _LEGACY
    assert registry.production_cohort() == ["Depresión", "Parkinson", "Alzheimer"]
    assert registry.names(published_only=True) == [
        *_LEGACY,
        "Obesidad",
        "Anorexia F50",
        "Diabetes tipo I",
        "Diabetes tipo II",
        "Hipertensión arterial",
        "Enfermedad isquémica del corazón",
        "Enfermedad cerebrovascular",
        "Infecciones intestinales por otros organismos y las mal definidas",
        "Infecciones respiratorias agudas",
        "Infección de vías urinarias",
        "Gingivitis y enfermedad periodontal",
        "Asma",
        "Úlceras, gastritis y duodenitis",
        "Tumor maligno de la mama",
        "Tumor maligno del cuello del útero",
        "Tumor maligno de la próstata",
        "Tumor maligno del cuerpo del útero",
        "Tumor maligno del ovario",
        "Tumor maligno de tráquea, bronquios y pulmón",
        "Tumor maligno del estómago",
        "Tumor maligno del colon y recto",
        "Tumor maligno del hígado y de las vías biliares intrahepáticas",
        "Linfoma de Hodgkin",
        "Linfoma no Hodgkin",
        "Leucemia",
        "Tumor maligno del esófago",
        "Tumor maligno del páncreas",
        "Tumores malignos del encéfalo y otras partes del sistema nervioso central",
        "Tumores malignos de los huesos y de los cartílagos articulares",
        "Tumor maligno del riñón",
        "Neumonías y bronconeumonías",
        "Otitis media aguda",
        "Faringitis y amigdalitis estreptocócicas",
        "Conjuntivitis",
        "Amebiasis intestinal",
        "Otras infecciones intestinales debidas a protozoarios",
        "Enterobiasis",
        "Ascariasis",
        "Otras salmonelosis",
        "Intoxicación alimentaria bacteriana",
        "Giardiasis",
        "Fiebre tifoidea",
        "Shigelosis",
        "Escabiosis",
        "Erisipela",
        "Escarlatina",
        "Parotiditis infecciosa",
        "Varicela",
        "Intoxicación por picadura de alacrán",
        "Peatón lesionado en accidente de transporte",
        "Accidente de transporte en vehículos con motor",
        "Candidiasis urogenital",
        "Hepatitis vírica A",
        "Hepatitis vírica B",
        "Hepatitis vírica C",
        "Quemaduras",
        "Mordeduras por perro",
        "Mordeduras por otros mamíferos",
        "Fiebre reumática aguda",
        "Insuficiencia venosa periférica",
        "Displasia cervical leve y moderada",
        "Displasia cervical severa y CaCu in situ",
        "Hiperplasia de la próstata",
        "Edema, proteinuria y trastornos hipertensivos en el embarazo, parto y puerperio",
        "Diabetes mellitus en el embarazo",
        "Desnutrición leve",
        "Desnutrición moderada",
        "Desnutrición severa",
        "Otras hepatitis víricas",
        "Brucelosis",
        "Leptospirosis",
        "Otras helmintiasis",
        "Enteritis debida a rotavirus",
        "Efectos del calor y de la luz",
        "Absceso hepático amebiano",
        "Bocio endémico",
        "Tos ferina",
        "Toxoplasmosis",
        "Teniasis",
        "Cisticercosis",
        "Triquinosis",
        "Mal del pinto",
        "Síndrome coqueluchoide",
        "Fiebre paratifoidea",
        "Conjuntivitis epidémica aguda hemorrágica",
        "Tracoma",
        "Síndrome meníngeo",
        "Intoxicación por monóxido de carbono",
        "Hipotermia",
        "Intoxicación por plaguicidas",
        "Vulvovaginitis",
        "Sífilis adquirida",
        "Tétanos",
        "Viruela símica",
        "Infección por virus de papiloma humano",
        "Infección gonocócica del tracto genitourinario",
        "Linfogranuloma venéreo por Clamidias",
        "Chancro blando",
        "Herpes genital",
        "Tricomoniasis urogenital",
        "Parálisis flácida aguda (menores de 15 años)",
        "Infección asociada a la atención de la salud",
        "Intoxicación aguda por alcohol",
        "Enfermedad alcohólica del hígado",
        "Anencefalia",
        "Encefalocele",
        "Microcefalia",
        "Espina bífida",
        "Labio y paladar hendido",
        "Mordedura de araña viuda negra",
        "Mordedura de araña violinista",
        "Mordedura de otras arañas",
        "Picadura de abeja",
        "Picadura de avispa",
        "Picadura por otros artrópodos",
        "Picadura o intoxicación por otros animales ponzoñosos",
        "Mordedura por serpiente de cascabel",
        "Mordedura por serpiente coral",
        "Mordedura por otras serpientes",
        "Cirrosis hepática alcohólica",
        "Enfermedad por virus Chikungunya",
        "Envenenamiento autoinfligido intencionalmente por analgésicos no narcóticos, antipiréticos y antirreumáticos",
        "Envenenamiento autoinfligido intencionalmente por drogas antiepilépticas, sedantes, hipnóticas, antiparkinsonianas y psicotrópicas",
        "Lesión autoinfligida intencionalmente por ahorcamiento, estrangulamiento o sofocación",
        "Lesión autoinfligida intencionalmente por disparo de arma corta",
        "Lesión autoinfligida intencionalmente por objeto cortante",
        "Lesión autoinfligida intencionalmente al saltar desde un lugar elevado",
        "Historia personal de lesión autoinfligida intencionalmente (intento de suicidio)",
        "Otros síntomas y signos que involucran el estado emocional (ideación suicida)",
        "Violencia intrafamiliar",
        "Tuberculosis otras formas",
        "Tripanosomiasis americana (enfermedad de Chagas) aguda",
        "Tifo murino",
        "Sífilis congénita",
        "Eventos supuestamente asociados a la vacunación (ESAVI)",
        "Meningitis meningocócica",
        "Enfermedad invasiva por neumococo",
        "Infecciones invasivas por Haemophilus influenzae",
        "Herida por arma de fuego",
        "Tripanosomiasis americana (enfermedad de Chagas) crónica",
        "Infección por el virus de la inmunodeficiencia humana",
        "Meningitis tuberculosa",
        "Tuberculosis respiratoria",
        "Lepra",
        "Fiebre manchada",
        "Otras rickettsiosis",
        "Leishmaniasis cutánea",
    ]


def test_covid_sigue_invisible():
    publicados = [n.lower() for n in registry.names(published_only=True)]
    assert "covid-19" not in publicados
