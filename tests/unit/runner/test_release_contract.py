"""C7.2-A/R15.2 — contratos de identidad del release ANTES de que exista el builder.

Lo que se fija aquí es lo que hace publicable a un bundle: una identidad ACÍCLICA (el ``release_id``
sale de un payload que no contiene ni el manifest ni los checksums), una serialización canónica
byte-estable, un inventario que se excluye a sí mismo y un orden de rutas que NO depende del locale
—la causa raíz que documenta la sección 20 del plan—.

Ninguna prueba conoce Obesidad, sus motores ni sus conteos: el contrato es genérico.
"""

from __future__ import annotations

import json

import pytest

from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_contract import (
    BUILDER_VERSION,
    CHECKSUMS_FILE,
    IDENTITY_SCHEMA,
    MANIFEST_FILE,
    RELEASE_SCHEMA,
    build_checksums,
    canonical_json,
    check_bundle_path,
    check_no_activation,
    identity_payload,
    parse_checksums,
    release_id_for,
    sha256_bytes,
)

CHAIN = {
    "dataset_id": "x_1502d1a25b48",
    "dataset_digest": "a" * 64,
    "policy_digest": "b" * 64,
    "selection_digest": "c" * 64,
    "final_selection_digest": "d" * 64,
    "acceptance_run_id": "x_benchmark_test_1",
    "acceptance_digest": "e" * 64,
    "refit_run_id": "x_refit_1",
    "refit_digest": "f" * 64,
    "forecast_run_id": "x_forecast_1",
}
PAYLOADS = {
    "forecast/forecast.csv": "1" * 64,
    "refit/models/motor_a/model_index.json": "2" * 64,
    "runtime_inputs/runtime_config.json": "3" * 64,
}


def _identity(**cambios: object) -> dict[str, object]:
    datos: dict[str, object] = {
        "disease_id": "x",
        "chain": dict(CHAIN),
        "payloads": dict(PAYLOADS),
    }
    datos.update(cambios)
    return identity_payload(**datos)  # type: ignore[arg-type]


# ── Serialización canónica ────────────────────────────────────────────────────────────────────
def test_canonical_json_es_utf8_ordenado_compacto_y_con_salto_final():
    raw = canonical_json({"b": 1, "a": "Depresión"})
    assert raw == b'{"a":"Depresi\xc3\xb3n","b":1}\n'
    assert raw.endswith(b"\n")


def test_canonical_json_no_depende_del_orden_de_inserción():
    uno = canonical_json({"a": 1, "b": {"y": 2, "x": 3}})
    otro = canonical_json({"b": {"x": 3, "y": 2}, "a": 1})
    assert uno == otro


def test_canonical_json_rechaza_lo_no_serializable():
    with pytest.raises(ArtifactValidationError, match="no serializable"):
        canonical_json({"a": {1, 2}})


# ── Identidad sin ciclos ──────────────────────────────────────────────────────────────────────
def test_identity_payload_declara_su_schema_y_el_del_release():
    identidad = _identity()
    assert identidad["schema"] == IDENTITY_SCHEMA
    assert identidad["release_schema"] == RELEASE_SCHEMA
    assert identidad["builder_version"] == BUILDER_VERSION


def test_identity_payload_no_contiene_release_id_manifest_ni_checksums():
    """La autorreferencia es el error clásico: el ID no puede depender de lo que lo contiene."""
    serializado = canonical_json(_identity()).decode("utf-8")
    assert "release_id" not in serializado
    assert MANIFEST_FILE not in serializado
    assert CHECKSUMS_FILE not in serializado


@pytest.mark.parametrize("archivo", [MANIFEST_FILE, CHECKSUMS_FILE])
def test_identity_payload_rechaza_el_manifest_y_los_checksums_como_payload(archivo):
    with pytest.raises(ArtifactValidationError, match="no puede ser un payload"):
        _identity(payloads={**PAYLOADS, archivo: "9" * 64})


@pytest.mark.parametrize(
    "ruta",
    ["/etc/passwd", "../fuera.csv", "refit/../../fuera.csv", "./refit/x.csv", "refit//x.csv", ""],
)
def test_identity_payload_rechaza_rutas_no_relativas_o_con_traversal(ruta):
    with pytest.raises(ArtifactValidationError):
        _identity(payloads={ruta: "9" * 64})


def test_identity_payload_rechaza_digest_que_no_es_sha256_en_minúsculas():
    with pytest.raises(ArtifactValidationError, match="sha256"):
        _identity(payloads={"a.csv": "NOPE"})


def test_identity_payload_exige_disease_id_no_vacío():
    with pytest.raises(ArtifactValidationError):
        _identity(disease_id="")


def test_identity_payload_exige_al_menos_un_payload():
    with pytest.raises(ArtifactValidationError, match="sin payloads"):
        _identity(payloads={})


# ── release_id derivado ───────────────────────────────────────────────────────────────────────
def test_release_id_tiene_el_formato_declarado_y_es_determinista():
    release_id, digest = release_id_for(_identity())
    assert release_id == f"x_release_{digest[:12]}"
    assert len(digest) == 64
    assert release_id_for(_identity())[0] == release_id


def test_release_id_no_depende_del_orden_de_inserción_de_los_payloads():
    invertido = dict(reversed(list(PAYLOADS.items())))
    assert release_id_for(_identity())[0] == release_id_for(_identity(payloads=invertido))[0]


def test_release_id_cambia_si_cambia_un_byte_de_cualquier_payload():
    otro = {**PAYLOADS, "forecast/forecast.csv": "1" * 63 + "0"}
    assert release_id_for(_identity(payloads=otro))[0] != release_id_for(_identity())[0]


@pytest.mark.parametrize("clave", sorted(CHAIN))
def test_release_id_cambia_si_cambia_cualquier_eslabón_de_la_cadena(clave):
    cadena = {**CHAIN, clave: CHAIN[clave] + "-otro"}
    assert release_id_for(_identity(chain=cadena))[0] != release_id_for(_identity())[0]


def test_la_identidad_no_admite_metadata_de_activación_pública():
    """C7.2-A.1: canales, galería y lifecycle no son identidad; su cambio no reconstruye nada."""
    serializado = canonical_json(_identity()).decode("utf-8")
    for prohibido in ("channel", "gallery", "lifecycle", "activated", "activation"):
        assert prohibido not in serializado


@pytest.mark.parametrize(
    "clave", ["activation", "channels", "channels_candidate", "gallery_enabled", "lifecycle"]
)
def test_check_no_activation_rechaza_la_política_pública(clave):
    with pytest.raises(ArtifactValidationError, match="activación pública"):
        check_no_activation({clave: "lo que sea"}, "x")


def test_check_no_activation_deja_pasar_lo_que_sí_es_del_release():
    check_no_activation({"disease_id": "x", "chain": {}, "payloads": {}}, "x")


def test_release_id_no_cambia_por_metadata_ambiental():
    """Nada del entorno entra: el payload de identidad es cerrado y explícito."""
    identidad = _identity()
    assert set(identidad) == {
        "schema",
        "release_schema",
        "builder_version",
        "disease_id",
        "chain",
        "payloads",
    }


# ── SHA256SUMS.txt ────────────────────────────────────────────────────────────────────────────
def test_los_checksums_incluyen_el_manifest_y_se_excluyen_a_sí_mismos():
    texto = build_checksums({**PAYLOADS, MANIFEST_FILE: "7" * 64}).decode("utf-8")
    assert f"  {MANIFEST_FILE}\n" in texto
    assert CHECKSUMS_FILE not in texto


def test_los_checksums_rechazan_incluirse_a_sí_mismos():
    with pytest.raises(ArtifactValidationError, match="no puede incluirse"):
        build_checksums({**PAYLOADS, CHECKSUMS_FILE: "7" * 64})


def test_el_formato_de_los_checksums_es_digest_dos_espacios_ruta():
    texto = build_checksums({"a.csv": "0" * 64}).decode("utf-8")
    assert texto == "0" * 64 + "  a.csv\n"


def test_los_checksums_se_ordenan_con_sorted_de_python_no_con_el_locale():
    """`sort` de shell colapsa mayúsculas y guiones bajos según LC_COLLATE; `sorted()` no (§20)."""
    rutas = {"_z.csv": "1" * 64, "B.csv": "2" * 64, "a.csv": "3" * 64, "Á.csv": "4" * 64}
    lineas = build_checksums(rutas).decode("utf-8").splitlines()
    assert [ln.split("  ", 1)[1] for ln in lineas] == sorted(rutas)


def test_parse_checksums_hace_round_trip():
    entradas = {**PAYLOADS, MANIFEST_FILE: "7" * 64}
    assert parse_checksums(build_checksums(entradas).decode("utf-8"), "x") == entradas


@pytest.mark.parametrize(
    "texto",
    [
        "0" * 64 + "  a.csv\n" + "1" * 64 + "  a.csv\n",  # ruta duplicada
        "0" * 64 + f"  {CHECKSUMS_FILE}\n",  # autorreferencia
        "0" * 63 + "  a.csv\n",  # digest corto
        "0" * 64 + "  /abs.csv\n",  # ruta absoluta
        "0" * 64 + "  ../fuera.csv\n",  # traversal
        "0" * 64 + " a.csv\n",  # separador de un solo espacio
        "no-es-una-línea\n",
    ],
)
def test_parse_checksums_falla_cerrado(texto):
    with pytest.raises(ArtifactValidationError):
        parse_checksums(texto, "x")


def test_parse_checksums_rechaza_un_archivo_vacío():
    with pytest.raises(ArtifactValidationError, match="vacío"):
        parse_checksums("", "x")


# ── Rutas del bundle ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("ruta", ["a.csv", "refit/models/m/a.json", "runtime_inputs/x.csv"])
def test_check_bundle_path_acepta_rutas_posix_relativas(ruta):
    assert check_bundle_path(ruta, "x") == ruta


@pytest.mark.parametrize(
    "ruta",
    ["/a.csv", "../a.csv", "a/../b.csv", "a/./b.csv", "a//b.csv", "a/", "", "  ", "a\\b.csv"],
)
def test_check_bundle_path_falla_cerrado(ruta):
    with pytest.raises(ArtifactValidationError):
        check_bundle_path(ruta, "x")


def test_sha256_bytes_coincide_con_el_digest_del_json_canónico():
    payload = {"a": 1}
    assert sha256_bytes(canonical_json(payload)) == sha256_bytes(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        + b"\n"
    )
