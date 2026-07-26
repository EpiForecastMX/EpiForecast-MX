"""C7.2-A/R15.3+R15.6 — el bundle construido: estructura, identidad, higiene y determinismo.

Todo ocurre sobre copias en ``tmp_path``; ni un byte se escribe bajo ``runs/`` ni bajo
``artifacts/releases/``. Lo que se fija aquí es que el bundle sea autosuficiente (nada del
workspace, ninguna ruta absoluta, ningún timestamp de construcción), que su identidad se recalcule
y que dos construcciones distintas den los MISMOS bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from epiforecast import registry
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_contract import (
    ACTIVATION_KEYS,
    BUILDER_VERSION,
    CHECKSUMS_FILE,
    IDENTITY_SCHEMA,
    MANIFEST_FILE,
    MANIFEST_KEYS,
    RELEASE_SCHEMA,
    identity_payload,
    parse_checksums,
)
from epiforecast.runner.release_loader import verify_bundle
from epiforecast.runner.release_runtime import RUNTIME_CONFIG_FILE, RUNTIME_DIR
from tests.unit.runner import artifact_fixtures as af
from tests.unit.runner import release_fixtures as rf

pytestmark = pytest.mark.skipif(
    not af.hay_runs(), reason="los runs sellados de C5 no están en este entorno (runs/ gitignored)"
)

# Archivos que el release GENERA (el resto son copias byte a byte de los runs sellados).
GENERADOS = (MANIFEST_FILE, CHECKSUMS_FILE, f"{RUNTIME_DIR}/{RUNTIME_CONFIG_FILE}")


@pytest.fixture(scope="module")
def bundle(tmp_path_factory) -> Path:
    """Un único bundle prístino por módulo: construirlo cuesta, mutarlo no."""
    return rf.construir(tmp_path_factory.mktemp("release")).path


# ── Estructura e identidad ────────────────────────────────────────────────────────────────────
def test_el_bundle_verifica_entero(bundle):
    verificado = verify_bundle(bundle)
    assert verificado.release_id == bundle.name
    assert verificado.disease_id == af.DISEASE
    assert verificado.horizon >= 1
    assert sum(verificado.engines.values()) == len(verificado.selection)


def test_el_inventario_es_exacto(bundle):
    manifest = rf.leer_manifest(bundle)
    declarados = {p["path"] for p in manifest["payloads"]}
    presentes = {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()}
    assert presentes == declarados | {MANIFEST_FILE, CHECKSUMS_FILE}


def test_el_manifest_no_se_inventaría_a_sí_mismo_ni_a_los_checksums(bundle):
    declarados = {p["path"] for p in rf.leer_manifest(bundle)["payloads"]}
    assert MANIFEST_FILE not in declarados
    assert CHECKSUMS_FILE not in declarados


def test_los_checksums_cubren_payloads_y_manifest_pero_no_a_sí_mismos(bundle):
    declarados = parse_checksums((bundle / CHECKSUMS_FILE).read_text(encoding="utf-8"), "x")
    payloads = {p["path"] for p in rf.leer_manifest(bundle)["payloads"]}
    assert set(declarados) == payloads | {MANIFEST_FILE}
    assert CHECKSUMS_FILE not in declarados


def test_el_release_id_se_deriva_del_identity_digest(bundle):
    manifest = rf.leer_manifest(bundle)
    assert manifest["release_id"] == f"{af.DISEASE}_release_{manifest['identity_digest'][:12]}"


def test_el_bundle_lleva_los_modelos_de_todos_los_motores(bundle):
    verificado = verify_bundle(bundle)
    for engine, esperados in verificado.engines.items():
        carpeta = bundle / "refit" / "models" / engine
        assert (carpeta / "model_index.json").is_file()
        assert len(list(carpeta.glob("*.envelope.json"))) == esperados
        assert len(list(carpeta.glob("*.state.*"))) == esperados


def test_el_calendario_declarado_es_el_horizonte_completo(bundle):
    """Origen, primer y último periodo se DERIVAN del refit sellado y del calendario MMWR."""
    from epiforecast.data.epi_calendar import shift

    calendario = rf.leer_manifest(bundle)["calendar"]
    origen = tuple(calendario["origin"])
    resumen = json.loads((bundle / "refit" / "refit_summary.json").read_text(encoding="utf-8"))
    assert list(origen) == resumen["train_end"]
    assert calendario["n_train"] == resumen["n_train_values"][0]
    esperado = origen
    for _ in range(calendario["horizon"]):
        esperado = shift(esperado[0], esperado[1], 1)
    assert calendario["first_period"] == list(shift(origen[0], origen[1], 1))
    assert calendario["last_period"] == list(esperado)


def test_el_release_declara_point_only(bundle):
    intervalos = rf.leer_manifest(bundle)["intervals"]
    assert intervalos == {"interval_method": "none", "uncertainty_available": False}


def test_el_manifest_no_lleva_metadata_de_activación_pública(bundle):
    """C7.2-A.1: el release dice QUÉ modelos hay, nunca DÓNDE se publican."""
    manifest = rf.leer_manifest(bundle)
    assert set(manifest) == set(MANIFEST_KEYS)
    assert not ACTIVATION_KEYS & set(manifest)
    texto = (bundle / MANIFEST_FILE).read_text(encoding="utf-8")
    for prohibido in ("channel", "gallery", "lifecycle", "activated"):
        assert prohibido not in texto


@pytest.mark.parametrize(
    "politica",
    [
        {"channels": ["web"]},
        {"channels": []},
        {"gallery_enabled": False},
        {"lifecycle": "published"},
        {"channels": ["web"], "gallery_enabled": False, "lifecycle": "published"},
    ],
)
def test_cambiar_la_política_pública_no_altera_el_bundle(tmp_path, monkeypatch, politica):
    """El motivo de C7.2-A.1: encender un canal no puede obligar a reconstruir modelos intactos.

    Se construye por el ENTRY POINT real —la capa que antes leía ``disease.channels``— con el
    registry declarando otra política pública. El ``release_id`` y cada byte deben ser los mismos.
    """
    prep = rf.preparar(tmp_path)
    # El registry ya declara `runner_release`; promover exige `runner_runs`, así que se sustituye
    # por la cadena SELLADA del propio release y se le cambia encima la política pública. Los dos
    # sustitutos se resuelven ANTES de parchear: resolverlos dentro recursaría sobre el parche.
    base, alterado = rf.disease_desde_runs(), rf.disease_desde_runs(**politica)

    monkeypatch.setattr(registry, "require", lambda _: base)
    referencia = rf.construir_por_entry(prep, tmp_path / "ref")

    monkeypatch.setattr(registry, "require", lambda _: alterado)
    otro = rf.construir_por_entry(prep, tmp_path / "otro")

    assert otro.release_id == referencia.release_id
    assert otro.identity_digest == referencia.identity_digest
    rutas = {p.relative_to(referencia.path).as_posix() for p in referencia.path.rglob("*")}
    assert rutas == {p.relative_to(otro.path).as_posix() for p in otro.path.rglob("*")}
    distintos = [
        r
        for r in sorted(rutas)
        if (referencia.path / r).is_file()
        and (referencia.path / r).read_bytes() != (otro.path / r).read_bytes()
    ]
    assert not distintos


def test_el_builder_declara_su_versión_en_el_manifest(bundle):
    """La versión del builder SÍ es identidad: v1 y v2 nunca comparten `release_id`."""
    assert rf.leer_manifest(bundle)["builder_version"] == BUILDER_VERSION


def test_todo_manifest_emitido_declara_los_schemas_v2(bundle):
    """R19.1.8: el contrato que un consumidor debe interpretar va escrito, no implícito."""
    manifest = rf.leer_manifest(bundle)
    assert manifest["schema"] == RELEASE_SCHEMA == "release_manifest.v2"
    assert manifest["identity_schema"] == IDENTITY_SCHEMA == "identity_payload.v2"


def test_la_identidad_declara_el_schema_del_release_que_describe():
    """R19.1.7: el payload de identidad dice a qué forma de manifest pertenece."""
    identidad = identity_payload(
        disease_id="x", chain={"dataset_id": "x_1"}, payloads={"a.csv": "0" * 64}
    )
    assert identidad["schema"] == "identity_payload.v2"
    assert identidad["release_schema"] == "release_manifest.v2"


# ── Higiene: nada del entorno dentro del contenido inmutable ──────────────────────────────────
@pytest.mark.parametrize("archivo", GENERADOS)
def test_los_archivos_generados_no_llevan_rutas_absolutas(bundle, archivo):
    texto = (bundle / archivo).read_text(encoding="utf-8")
    assert "/Users/" not in texto and "/home/" not in texto and "/private/" not in texto
    assert str(bundle) not in texto


@pytest.mark.parametrize("archivo", GENERADOS)
def test_los_archivos_generados_no_llevan_timestamps_ni_metadata_ambiental(bundle, archivo):
    """La hora de construcción no participa en el bundle; si hace falta, va en un receipt externo."""
    texto = (bundle / archivo).read_text(encoding="utf-8")
    for prohibido in ("created_at", "built_at", "generated_at", "mtime", "uid", "gid", "hostname"):
        assert prohibido not in texto


def test_ningún_payload_lleva_una_ruta_absoluta_del_equipo(bundle):
    sospechosos = [
        p.relative_to(bundle).as_posix()
        for p in bundle.rglob("*")
        if p.is_file()
        and p.suffix in {".json", ".csv", ".yaml", ".txt"}
        and "/Users/" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not sospechosos


def test_el_bundle_no_incluye_contexto_de_ejecución_del_runner(bundle):
    """`job_context.json` lleva rutas absolutas del equipo: no puede viajar en un release."""
    assert not list(bundle.rglob("job_context.json"))
    assert not list(bundle.rglob("*.stdout.txt"))
    assert not list(bundle.rglob("*.result.json"))


def test_el_runtime_config_declara_rutas_relativas_al_bundle(bundle):
    config = json.loads((bundle / RUNTIME_DIR / RUNTIME_CONFIG_FILE).read_text(encoding="utf-8"))
    for bloque in ("geo_catalog", "exposure"):
        ruta = config[bloque]["path"]
        assert not Path(ruta).is_absolute() and ".." not in ruta
        assert (bundle / ruta).is_file()


def test_la_exposición_del_bundle_es_la_proyección_no_el_raw_inegi(bundle):
    """R15-C3: el schema por `cve_ent` y el digest del snapshot original se registran por separado."""
    config = json.loads((bundle / RUNTIME_DIR / RUNTIME_CONFIG_FILE).read_text(encoding="utf-8"))
    exposicion = config["exposure"]
    assert exposicion["sha256"] != exposicion["source_digest"]
    proyectada = (bundle / exposicion["path"]).read_text(encoding="utf-8").splitlines()[0]
    assert proyectada.split(",")[0] == "cve_ent"


# ── Determinismo, idempotencia y rechazo del destino distinto ─────────────────────────────────
def test_dos_construcciones_en_roots_distintos_dan_los_mismos_bytes(tmp_path):
    uno = rf.construir(tmp_path / "a", salida="out")
    otro = rf.construir(tmp_path / "b", salida="otro_nombre")
    assert uno.release_id == otro.release_id
    assert uno.identity_digest == otro.identity_digest
    rutas_uno = {p.relative_to(uno.path).as_posix() for p in uno.path.rglob("*") if p.is_file()}
    rutas_otro = {p.relative_to(otro.path).as_posix() for p in otro.path.rglob("*") if p.is_file()}
    assert rutas_uno == rutas_otro
    distintos = [
        ruta
        for ruta in sorted(rutas_uno)
        if (uno.path / ruta).read_bytes() != (otro.path / ruta).read_bytes()
    ]
    assert not distintos


def test_reconstruir_sobre_el_mismo_destino_es_idempotente(tmp_path):
    prep = rf.preparar(tmp_path)
    salida = tmp_path / "out"
    primero = rf.construir_en(prep, salida)
    segundo = rf.construir_en(prep, salida)
    assert primero.release_id == segundo.release_id
    assert (primero.reused, segundo.reused) == (False, True)
    assert [p.name for p in salida.iterdir()] == [primero.release_id]


def test_un_destino_existente_con_otro_contenido_se_rechaza(tmp_path):
    prep = rf.preparar(tmp_path)
    salida = tmp_path / "out"
    construido = rf.construir_en(prep, salida)
    (construido.path / "forecast" / "forecast.csv").write_text("intruso\n", encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match="contenido distinto"):
        rf.construir_en(prep, salida)


def test_el_build_no_deja_staging_ni_escribe_fuera_del_output_root(tmp_path):
    construido = rf.construir(tmp_path)
    salida = tmp_path / "out"
    assert [p.name for p in salida.iterdir()] == [construido.release_id]
    assert not list(salida.glob(".staging-*"))
